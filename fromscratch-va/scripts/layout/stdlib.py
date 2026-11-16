"""Standard-cell (sky130_fd_sc_hd) abstract access: pins (label rects on locali), metal1 obstruction, bbox; pad candidates"""
import os, re, math
D = os.path.join(os.environ['PDKPATH'], 'libs.ref/sky130_fd_sc_hd/mag')
U = 200.0
_cache = {}
class Cell:
    pass
def load(cname):
    if cname in _cache: return _cache[cname]
    path = os.path.join(D, 'sky130_fd_sc_hd__%s.mag' % cname)
    c = Cell(); c.name = 'sky130_fd_sc_hd__' + cname; c.rects = {}; c.pins = {}
    layer = None; pending = None
    for line in open(path):
        line = line.strip()
        m = re.match(r'<< (\S+) >>', line)
        if m: layer = m.group(1); continue
        m = re.match(r'rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)', line)
        if m and layer: c.rects.setdefault(layer, []).append(tuple(int(v)/U for v in m.groups()))
        m = re.match(r'flabel (\S+) \S+ (-?\d+) (-?\d+) (-?\d+) (-?\d+) .* (\S+)$', line)
        if m:
            ly, x1, y1, x2, y2, nm = m.groups()
            if ly == 'locali': c.pins.setdefault(nm, []).append(tuple(int(v)/U for v in (x1, y1, x2, y2)))
        m = re.match(r'string FIXED_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)', line)
        if m: c.bbox = tuple(int(v)/U for v in m.groups())
    _cache[cname] = c
    return c
def free_pads(c, pad=0.30, clear=0.16):
    """for every signal pin: list of pad centres (cx,cy) whose metal1 pad (pad x pad) keeps >= clear from the cell's own metal1 shapes"""
    m1 = c.rects.get('metal1', [])
    out = {}
    for pn, rs in c.pins.items():
        if pn in ('VPWR', 'VGND', 'VPB', 'VNB'): continue
        ok = []
        for (x1, y1, x2, y2) in rs:
            cx, cy = 0.5*(x1+x2), 0.5*(y1+y2)
            px1, py1, px2, py2 = cx-pad/2-clear, cy-pad/2-clear, cx+pad/2+clear, cy+pad/2+clear
            conflict = any(r[2] > px1 and r[0] < px2 and r[3] > py1 and r[1] < py2 for r in m1)
            ok.append(((cx, cy), not conflict))
        out[pn] = ok
    return out
if __name__ == '__main__':
    import sys
    for cn in sys.argv[1:]:
        c = load(cn)
        print(cn, c.bbox, {k: [(round(p[0][0], 2), round(p[0][1], 2), p[1]) for p in v] for k, v in free_pads(c).items()})

# ---------------------------------------------------------------------------------------------------------------------------
def _touch(a, b):
    return a[2] >= b[0] and b[2] >= a[0] and a[3] >= b[1] and b[3] >= a[1]
def _gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0.0); dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return max(dx, dy)          # Chebyshev, conservative

def access(cname, clear=0.14, latx=0.115, laty=0.17):
    """candidate via1-pad centres per signal pin ON THE ROUTER LATTICE (local x multiple of latx, y multiple of laty): (x, y, needs_mcon, orient, mcon_cx, mcon_cy)
    pad = 0.26 x 0.32 ('v') or 0.32 x 0.26 ('h') metal1; with needs_mcon an extra 0.23 x 0.23 metal1 pad is drawn over the mcon at the pin li centre"""
    c = load(cname)
    if hasattr(c, 'acc'): return c.acc
    li = c.rects.get('locali', []); mc = c.rects.get('viali', []); m1 = c.rects.get('metal1', [])
    nodes = [('li', r) for r in li] + [('m1', r) for r in m1]
    parent = list(range(len(nodes)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j): parent[find(i)] = find(j)
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            if nodes[i][0] == nodes[j][0] and _touch(nodes[i][1], nodes[j][1]): union(i, j)
    for m in mc:
        idx = [i for i, n in enumerate(nodes) if _touch(n[1], m) and n[0] in ('li', 'm1')]
        for a in idx[1:]: union(a, idx[0])
    c.acc = {}
    c.force_stub = set()
    if cname == 'edfxtp_1': c.force_stub = {'D'}
    for pn, rs in c.pins.items():
        if pn in ('VPWR', 'VGND', 'VPB', 'VNB'): continue
        comps = set()
        for (x1, y1, x2, y2) in rs:
            for i, n in enumerate(nodes):
                if n[0] == 'li' and _touch(n[1], (x1, y1, x2, y2)): comps.add(find(i))
        own_m1 = [n[1] for i, n in enumerate(nodes) if n[0] == 'm1' and find(i) in comps]
        foreign = [n[1] for i, n in enumerate(nodes) if n[0] == 'm1' and find(i) not in comps]
        def fitsrect(r): return all(_gap(r, f) >= clear for f in foreign)
        cands = []
        for orient, (pw, ph) in (('v', (0.26, 0.32)), ('h', (0.32, 0.26))):
            for (x1, y1, x2, y2) in own_m1:
                if x2 - x1 < pw - 0.001 or y2 - y1 < ph - 0.001: continue
                ix1 = int(math.ceil((x1 + pw/2)/latx - 1e-9)); ix2 = int(math.floor((x2 - pw/2)/latx + 1e-9))
                iy1 = int(math.ceil((y1 + ph/2)/laty - 1e-9)); iy2 = int(math.floor((y2 - ph/2)/laty + 1e-9))
                for a in range(ix1, ix2 + 1):
                    for b in range(iy1, iy2 + 1):
                        px, py = a*latx, b*laty
                        if fitsrect((px - pw/2, py - ph/2, px + pw/2, py + ph/2)): cands.append((round(px, 4), round(py, 4), False, orient, 0, 0))
            for (x1, y1, x2, y2) in rs:
                cx, cy = 0.5*(x1+x2), 0.5*(y1+y2)
                px = round(cx/latx)*latx; py = round(cy/laty)*laty
                if abs(px - cx) > 0.06 or abs(py - cy) > 0.001: continue
                r_via = (px - pw/2, py - ph/2, px + pw/2, py + ph/2); r_mc = (cx - 0.145, cy - 0.115, cx + 0.145, cy + 0.115)
                if fitsrect(r_via) and fitsrect(r_mc): cands.append((round(px, 4), round(py, 4), True, orient, cx, cy))
        if not cands:     # fall back: off-lattice pads (the router snaps and adds a connector)
            step = 0.04
            for orient, (pw, ph) in (('v', (0.26, 0.32)), ('h', (0.32, 0.26))):
                for (x1, y1, x2, y2) in own_m1:
                    if x2 - x1 < pw - 0.001 or y2 - y1 < ph - 0.001: continue
                    nx = int((x2 - x1 - pw)/step + 1e-9); ny = int((y2 - y1 - ph)/step + 1e-9)
                    for a in range(nx + 1):
                        for b in range(ny + 1):
                            px, py = x1 + pw/2 + a*step, y1 + ph/2 + b*step
                            if fitsrect((px - pw/2, py - ph/2, px + pw/2, py + ph/2)): cands.append((round(px, 4), round(py, 4), False, orient, 0, 0))
                for (x1, y1, x2, y2) in rs:
                    cx, cy = 0.5*(x1+x2), 0.5*(y1+y2)
                    if fitsrect((cx - pw/2, cy - ph/2, cx + pw/2, cy + ph/2)) and fitsrect((cx - 0.145, cy - 0.115, cx + 0.145, cy + 0.115)): cands.append((round(cx, 4), round(cy, 4), True, orient, cx, cy))
        if pn in c.force_stub: cands = []
        if not cands:
            # li1 stub: extend the pin's local interconnect (L shape, 0.17 wide) to a lattice point with room for mcon + via1 pads
            own_li = [n[1] for i, n in enumerate(nodes) if n[0] == 'li' and find(i) in comps]
            foreign_li = [n[1] for i, n in enumerate(nodes) if n[0] == 'li' and find(i) not in comps]
            def li_ok(r): return all(_gap(r, f) >= 0.17 for f in foreign_li)
            for (x1, y1, x2, y2) in rs:
                cx, cy = 0.5*(x1+x2), 0.5*(y1+y2)
                found = []
                for ia in range(-12, 13):
                    for ib in range(-8, 9):
                        px = round(cx/latx)*latx + ia*latx; py = round(cy/laty)*laty + ib*laty
                        if abs(px - cx) + abs(py - cy) > 1.3 or (abs(px - cx) < 0.06 and abs(py - cy) < 0.06): continue
                        for orient, (pw, ph) in (('v', (0.26, 0.32)),):
                            if not (fitsrect((px - pw/2, py - ph/2, px + pw/2, py + ph/2)) and fitsrect((px - 0.145, py - 0.115, px + 0.145, py + 0.115))): continue
                            # L shaped li path: horizontal first
                            h = (min(cx, px) - 0.085, cy - 0.085, max(cx, px) + 0.085, cy + 0.085); v = (px - 0.085, min(cy, py) - 0.085, px + 0.085, max(cy, py) + 0.085)
                            if li_ok(h) and li_ok(v): found.append((abs(px - cx) + abs(py - cy), px, py, orient, (h, v)))
                if cname == 'edfxtp_1' and pn == 'D': found = [f for f in found if math.hypot(f[1] - 2.21, f[2] - 0.85) >= 0.75]
                found.sort()
                for d_, px, py, orient, (h, v) in found[:3]:
                    cands.append((round(px, 4), round(py, 4), True, orient, px, py, ((cx, cy), h, v)))
        c.acc[pn] = cands
    return c.acc
