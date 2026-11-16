"""Transistor device generation through the PDK's magic gencell + parsing of the terminal geometry.
Dev objects: .cell (file name without .mag), .bbox, .cols (S/D metal1 columns left->right), .pads (gate contact pads: (x,y,'T'|'B')), .w .l .nf kind"""
import os, re, subprocess, glob, shutil, math
HERE = os.path.dirname(os.path.abspath(__file__))
DEVDIR = os.path.join(HERE, 'devs')
MAGICRC = os.path.join(os.environ.get('PDKPATH', os.environ['PDKPATH']), 'libs.tech/magic/sky130A.magicrc')
U = 200.0
KIND = {'nfet': 'sky130_fd_pr__nfet_01v8', 'pfet': 'sky130_fd_pr__pfet_01v8', 'nfet_lvt': 'sky130_fd_pr__nfet_01v8_lvt'}
_cache = {}

class Dev:
    pass

def _key(kind, w, l, nf, guard): return 'dev_%s_w%s_l%s_nf%d_g%d' % (kind, ('%g' % w).replace('.', 'p'), ('%g' % l).replace('.', 'p'), nf, guard)

def get(kind, w, l=0.15, nf=1, guard=0):
    k = _key(kind, w, l, nf, guard)
    if k in _cache: return _cache[k]
    os.makedirs(DEVDIR, exist_ok=True)
    path = os.path.join(DEVDIR, k + '.mag')
    if not os.path.exists(path):
        tmp = os.path.join(DEVDIR, 'tmp_' + k); os.makedirs(tmp, exist_ok=True)
        tcl = "load d\nbox position 0 0\nmagic::gencell sky130::%s d w %g l %g nf %d guard %d\nsave d\nwriteall force\nquit -noprompt\n" % (KIND[kind], w, l, nf, guard)
        open(os.path.join(tmp, 'g.tcl'), 'w').write(tcl)
        subprocess.run(['magic', '-dnull', '-noconsole', '-rcfile', MAGICRC, 'g.tcl'], cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        fs = [f for f in glob.glob(os.path.join(tmp, '*.mag')) if os.path.basename(f) not in ('d.mag',)]
        assert len(fs) == 1, (k, fs)
        shutil.copy(fs[0], path); shutil.rmtree(tmp)
    d = Dev(); d.cell = k; d.kind = kind; d.w = w; d.l = l; d.nf = nf; d.guard = guard
    rects = {}; layer = None
    for line in open(path):
        line = line.strip()
        m = re.match(r'<< (\S+) >>', line)
        if m: layer = m.group(1); continue
        m = re.match(r'rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)', line)
        if m and layer: rects.setdefault(layer, []).append(tuple(int(v)/U for v in m.groups()))
    d.rects = rects
    allr = [r for ly, rs in rects.items() if ly != 'checkpaint' for r in rs]
    d.bbox = (min(r[0] for r in allr), min(r[1] for r in allr), max(r[2] for r in allr), max(r[3] for r in allr))
    m1 = rects.get('metal1', [])
    # S/D columns: tall thin metal1 rects (height >= w - 0.05, width ~0.23)
    dc = rects.get('ndiffc', []) + rects.get('pdiffc', [])
    d.cols = sorted([(0.5*(r[0]+r[2])-0.115, r[1], 0.5*(r[0]+r[2])+0.115, r[3]) for r in dc if (r[3]-r[1]) > 0.1 and r[2]-r[0] < 0.2], key=lambda r: r[0])
    d.pads = []
    for r in rects.get('polycont', []):
        cx, cy = 0.5*(r[0]+r[2]), 0.5*(r[1]+r[3])
        d.pads.append((cx, cy, 'T' if cy > 0 else 'B'))
    d.pads.sort()
    _cache[k] = d
    return d

# ---------------------------------------------------------------------------------------------------------------------
def via1_pad(cell, x, y, hy=0.2):
    cell.rect('via1', x-0.13, y-0.13, x+0.13, y+0.13)
    cell.rect('metal1', x-0.17, y-0.17, x+0.17, y+0.17)
    cell.rect('metal2', x-0.2, y-hy, x+0.2, y+hy)

class Group:
    """placed multi-finger device with S/D met2 straps and gate met1 bars.  Attributes (absolute coordinates):
    s_strap=(x1,x2,y), d_strap=(x1,x2,y), g_top=(x1,x2,y) or None, g_bot=..., bbox"""
    pass

def place(cell, dev, cx, cy, inst, swap_sd=False, gate_join=True, strap_inset=0.22):
    cell.use(dev.cell, inst, cx, cy)
    g = Group(); g.dev = dev; g.inst = inst
    cols = dev.cols
    s_idx = [i for i in range(len(cols)) if i % 2 == (1 if swap_sd else 0)]
    d_idx = [i for i in range(len(cols)) if i % 2 == (0 if swap_sd else 1)]
    y0, y1 = cy + cols[0][1], cy + cols[0][3]
    LAT = 0.17
    ys = math.ceil((y0 + strap_inset)/LAT - 1e-9)*LAT; yd = math.floor((y1 - strap_inset)/LAT + 1e-9)*LAT
    def strap(idx, y):
        xs = [cx + 0.5*(cols[i][0] + cols[i][2]) for i in idx]
        for x in xs: via1_pad(cell, x, y, 0.14)
        if len(xs) > 1: cell.rect('metal2', min(xs)-0.2, y-0.14, max(xs)+0.2, y+0.14)
        return (min(xs), max(xs), y)
    g.s_strap = strap(s_idx, ys); g.d_strap = strap(d_idx, yd)
    g.s_xs = [cx + 0.5*(cols[i][0] + cols[i][2]) for i in s_idx]; g.d_xs = [cx + 0.5*(cols[i][0] + cols[i][2]) for i in d_idx]
    tops = [(cx + px, cy + py) for px, py, sd in dev.pads if sd == 'T']
    bots = [(cx + px, cy + py) for px, py, sd in dev.pads if sd == 'B']
    def bar(pts):
        if not pts: return None
        x1, x2, y = min(p[0] for p in pts), max(p[0] for p in pts), pts[0][1]
        cell.rect('metal1', x1-0.145, y-0.115, x2+0.145, y+0.115)
        return (x1, x2, y)
    g.g_top, g.g_bot = bar(tops), bar(bots)
    if gate_join and g.g_top and g.g_bot:
        xv = cx + cols[0][0] - 0.40
        gx1 = min(g.g_top[0], g.g_bot[0])
        cell.rect('metal1', xv-0.115, g.g_bot[2]-0.115, xv+0.115, g.g_top[2]+0.115)
        cell.rect('metal1', xv-0.115, g.g_top[2]-0.115, g.g_top[0]-0.1, g.g_top[2]+0.115)
        cell.rect('metal1', xv-0.115, g.g_bot[2]-0.115, g.g_bot[0]-0.1, g.g_bot[2]+0.115)
        g.g_xv = xv
    g.bbox = (cx + dev.bbox[0], cy + dev.bbox[1], cx + dev.bbox[2], cy + dev.bbox[3])
    return g

def tap(cell, kind, x1, x2, y, h=0.17):
    """substrate tap strip, contacts over [x1,x2]; diff extends 0.12, li 0.08, metal1 0.06 beyond (inside an nwell for kind 'n'). Returns metal1 rect"""
    dl, cl = ('psubdiff', 'psubdiffcont') if kind == 'p' else ('nsubdiff', 'nsubdiffcont')
    cell.rect(dl, x1-0.12, y, x2+0.12, y+h); cell.rect(cl, x1, y, x2, y+h)
    cell.rect('locali', x1-0.08, y, x2+0.08, y+h); cell.rect('viali', x1, y, x2, y+h)
    cell.rect('metal1', x1-0.06, y-0.03, x2+0.06, y+h+0.03)
    return (x1-0.06, y-0.03, x2+0.06, y+h+0.03)

def get_mim(w, l):
    """gencell MIM cap (sky130_fd_pr__cap_mim_m3_1): top plate (capm -> metal4 over the cap) and bottom plate (metal3 tab -> via3 -> metal4)"""
    assert 0 < w <= 30 and 0 < l <= 30, 'PDK MIM generator silently clips dimensions above30um'
    k = 'dev_mim_w%s_l%s' % (('%g' % w).replace('.', 'p'), ('%g' % l).replace('.', 'p'))
    if k in _cache: return _cache[k]
    path = os.path.join(DEVDIR, k + '.mag')
    if not os.path.exists(path):
        tmp = os.path.join(DEVDIR, 'tmp_' + k); os.makedirs(tmp, exist_ok=True)
        open(os.path.join(tmp, 'g.tcl'), 'w').write("load d\nbox position 0 0\nmagic::gencell sky130::sky130_fd_pr__cap_mim_m3_1 d w %g l %g\nsave d\nwriteall force\nquit -noprompt\n" % (w, l))
        subprocess.run(['magic', '-dnull', '-noconsole', '-rcfile', MAGICRC, 'g.tcl'], cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        fs = [f for f in glob.glob(os.path.join(tmp, '*.mag')) if os.path.basename(f) != 'd.mag']
        assert len(fs) == 1, (k, fs)
        shutil.copy(fs[0], path); shutil.rmtree(tmp)
    d = Dev(); d.cell = k; d.kind = 'mim'; d.w = w; d.l = l
    rects = {}; layer = None
    for line in open(path):
        line = line.strip()
        m = re.match(r'<< (\S+) >>', line)
        if m: layer = m.group(1); continue
        m = re.match(r'rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)', line)
        if m and layer: rects.setdefault(layer, []).append(tuple(int(v)/U for v in m.groups()))
    d.rects = rects
    allr = [r for ly, rs in rects.items() if ly != 'checkpaint' for r in rs]
    d.bbox = (min(r[0] for r in allr), min(r[1] for r in allr), max(r[2] for r in allr), max(r[3] for r in allr))
    m4 = sorted(rects['metal4'], key=lambda r: -(r[2]-r[0])*(r[3]-r[1]))
    big = [r for r in m4 if (r[2]-r[0]) > 1.0]
    d.top = (min(r[0] for r in big), min(r[1] for r in big), max(r[2] for r in big), max(r[3] for r in big))
    small = [r for r in m4 if r[0] >= d.top[2] + 0.2]
    d.bot = (min(r[0] for r in small), min(r[1] for r in small), max(r[2] for r in small), max(r[3] for r in small))
    _cache[k] = d
    return d
