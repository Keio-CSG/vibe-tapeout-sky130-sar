#!/usr/bin/env python3
"""Top-level macro assembly (floorplan A-top): CDAC P | comparator | CDAC N at the bottom, switch/driver banks above the arrays,
SAR logic above the banks.  BOT and top-plate connections are straight metal4 wires (pins aligned by construction), the rest is routed
with the maze router on metal3/metal4 (blocks are obstacles with their flattened metal3/metal4)."""
import sys, os, re, json, math, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import klayout.db as db
from lay import Cell
from route import Router
import fp
HERE = os.path.dirname(os.path.abspath(__file__))
U = 200.0
BLK = {'cdac': ('cdac', 'cdac_core'), 'bank': (os.environ.get('BANK_DIR', 'bank'), 'bank_side'), 'comp': (os.environ.get('COMP_DIR', 'comp'), 'comparator_core'), 'logic': (os.environ.get('LOGIC_DIR', 'logic'), 'sar_logic_core')}

def read_pins(d, cell):
    pins = {}
    for line in open(os.path.join(HERE, d, cell + '.mag')):
        m = re.match(r'flabel (\S+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) .* (\S+)$', line.strip())
        if m:
            ly, x1, y1, x2, y2, nm = m.groups()
            pins[nm] = (ly, 0.5*(int(x1) + int(x2))/U, 0.5*(int(y1) + int(y2))/U)
    return pins

def bbox_of(d, cell):
    ly = db.Layout(); ly.read(os.path.join(HERE, d, cell + '.gds')); b = ly.cell(cell).bbox()
    return (b.left/1000.0, b.bottom/1000.0, b.right/1000.0, b.top/1000.0)


def comp_m1_pieces(y_local):
    """x extents (comp-local) of the metal1 polygons of the comparator that cross the horizontal line y_local (the VSS / VDD strips)"""
    ly = db.Layout(); ly.read(os.path.join(HERE, BLK['comp'][0], BLK['comp'][1] + '.gds')); c = ly.cell(BLK['comp'][1])
    li = ly.find_layer(68, 20); r = db.Region(c.begin_shapes_rec(li)); r.merge()
    out = []
    for p in r.interacting(db.Region(db.Box(0, int((y_local - 0.02)*1000), 100000, int((y_local + 0.02)*1000)))).each():
        b = p.bbox(); out.append((b.left/1000.0, b.right/1000.0))
    return sorted(out)

class Place:
    def __init__(self, key, ox, oy, mirror=False, xoff=None):
        self.key = key; self.d, self.cell = BLK[key]; self.ox, self.oy, self.mirror = ox, oy, mirror
        self.xoff = xoff     # for mirrored blocks: macro x = xoff - x_block
        self.bbox = bbox_of(self.d, self.cell); self.pins = read_pins(self.d, self.cell)
    def tx(self, x): return (self.xoff - x) if self.mirror else (self.ox + x)
    def ty(self, y): return self.oy + y
    def pin(self, name):
        ly, x, y = self.pins[name]; return (ly, self.tx(x), self.ty(y))
    def macro_bbox(self):
        x1, y1, x2, y2 = self.bbox
        xs = sorted([self.tx(x1), self.tx(x2)])
        return (xs[0], self.ty(y1), xs[1], self.ty(y2))


XC = fp.XC
M3W = 0.4; M4W = 0.4
TP = 0.9            # track pitch of the through nets
LP = 0.8            # track pitch of the LO/HIB channel nets

class Top:
    def __init__(self):
        self.c = Cell('sar_adc_macro'); self.port = 1
    def rect(self, ly, x1, y1, x2, y2): self.c.rect(ly, x1, y1, x2, y2)
    def seg(self, ly, xa, ya, xb, yb, w):
        self.rect(ly, min(xa, xb) - w/2, min(ya, yb) - w/2, max(xa, xb) + w/2, max(ya, yb) + w/2)
    def via34(self, x, y):
        self.rect('via3', x-0.16, y-0.16, x+0.16, y+0.16); self.rect('metal3', x-0.25, y-0.25, x+0.25, y+0.25); self.rect('metal4', x-0.25, y-0.25, x+0.25, y+0.25)
    def via12(self, x, y):
        self.rect('via1', x-0.13, y-0.13, x+0.13, y+0.13); self.rect('metal1', x-0.2, y-0.2, x+0.2, y+0.2); self.rect('metal2', x-0.25, y-0.2, x+0.25, y+0.2)
    def path(self, pts, layers, w=None):
        """pts: corner list [(x,y)...]; layers: one layer per segment ('metal3'/'metal4'); vias where the layer changes"""
        for (a, b), ly in zip(zip(pts[:-1], pts[1:]), layers):
            self.seg(ly, a[0], a[1], b[0], b[1], M4W if ly == 'metal4' else M3W)
        for k in range(1, len(layers)):
            if layers[k] != layers[k-1]: self.via34(*pts[k])
    def label(self, ly, x, y, name, kind='signal bidirectional', size=0.4):
        self.c.label(ly, x, y, name, port=self.port, kind=kind, size=size); self.port += 1

def build():
    T = Top(); c = T.c
    mir = lambda x: 2*XC - x
    cdP = Place('cdac', fp.CDAC_OX, fp.CDAC_OY)
    cdN = Place('cdac', fp.CDAC_OX, fp.CDAC_OY, mirror=True, xoff=2*XC - fp.CDAC_OX)
    cb = cdP.macro_bbox()
    BANK_GAP = float(os.environ.get('BANK_GAP', '14.0'))
    bank_y = round((cb[3] + BANK_GAP)/0.17)*0.17
    bkP = Place('bank', fp.BANK_OX, bank_y)
    bkN = Place('bank', fp.BANK_OX, bank_y, mirror=True, xoff=2*XC - fp.BANK_OX)
    bb = bkP.macro_bbox()
    top_pin = cdP.pin('TOP')[2]
    cmp_ = Place('comp', 0.0, 0.0)
    cmp_.ox = XC - 0.5*(cmp_.pins['INN'][1] + cmp_.pins['INP'][1])     # centre the input pins on the macro axis
    cmp_.oy = top_pin - cmp_.pin('INN')[2] + cmp_.oy      # INN level with the CDAC TOP pin -> straight wire
    # ---- channel plan (bottom of logic follows from the number of tracks) ----------------------------------------------------------------
    ytop_bank = bb[3]
    yL0 = ytop_bank + 1.3                                  # first through-net track
    nthru = 6
    yT_lo0 = ytop_bank + 1.5                               # first LO/HIB track (no through-net tracks any more)
    nlh = 21
    y_last = yT_lo0 + LP*(nlh - 1)
    lg = Place('logic', 0, 0)
    ylp = lg.pins['lo_p0'][2]                              # block-local y of the bottom pins
    lg.ox = XC - 0.5*(lg.bbox[0] + lg.bbox[2])
    y_l = y_last + 1.3                                     # macro y of the logic bottom pins
    lg.oy = y_l - ylp
    lgb = lg.macro_bbox()
    for p, nm in ((cdP, 'cdacP'), (cdN, 'cdacN'), (bkP, 'bankP'), (bkN, 'bankN'), (cmp_, 'comp'), (lg, 'logic')):
        orient = 'MY' if p.mirror else 'R0'
        c.use(p.cell, nm, p.xoff if p.mirror else p.ox, p.oy, orient)
    # ---- 1. BOT wires (CDAC pin -> bank pin, straight metal4) ---------------------------------------------------------------------------
    for k in range(11):
        for cd, bk in ((cdP, bkP), (cdN, bkN)):
            a = cd.pin('B%d' % k); b = bk.pin('BOT%d' % k)
            assert abs(a[1] - b[1]) < 1e-3, (k, a, b)
            T.seg('metal4', a[1], a[2], b[1], b[2], 0.8)
    # ---- 2. top plates to the comparator ---------------------------------------------------------------------------------------------------
    for cd, nm in ((cdP, 'INN'), (cdN, 'INP')):
        a = cd.pin('TOP'); b = cmp_.pin(nm); assert abs(a[2] - b[2]) < 1e-3, (a, b)
        T.seg('metal4', a[1], a[2], b[1], b[2], 0.8)
    # ---- 3. bank buses: extensions to the macro edges (VIN, VREFP, VREFN) and joins in the middle (VREFP, VREFN, TRK, TRKB) -----------------
    Yb = json.load(open(os.path.join(HERE, BLK['bank'][0], 'meta.json')))['Y']
    buses = {'VREFN': Yb['bus_n'], 'VIN': Yb['vin'], 'TRK': Yb['trk'], 'TRKB': Yb['trkb'], 'VREFP': Yb['bus_p']}
    xl_b, xr_b = bkP.macro_bbox()[0], bkP.macro_bbox()[2]
    for nm, (y1, y2) in buses.items():
        y1 += bank_y; y2 += bank_y
        pn = {'VIN': ('VINP', 'VINN'), 'VREFP': ('VREFP', 'VREFP'), 'VREFN': ('VREFN', 'VREFN')}.get(nm)
        if pn:
            if nm=='VIN' and os.environ.get('CPB_INPUT_FILTER')=='1':
                import cpb_input_filter
                cpb_input_filter.add(T,0.5*(y1+y2),xl_b,y1,y2)
            else:
                T.rect('metal3', 0.0, y1, xl_b + 0.3, y2); T.rect('metal3', mir(xl_b) - 0.3, y1, 2*XC, y2)
            T.label('metal3', 0.4, 0.5*(y1 + y2), pn[0], size=0.3); T.label('metal3', 2*XC - 0.4, 0.5*(y1 + y2), pn[1] + '', size=0.3)
        if nm != 'VIN': T.rect('metal3', xr_b - 0.3, y1, mir(xr_b) + 0.3, y2)
    ybar = {nm: bank_y + 0.5*(buses[nm][0] + buses[nm][1]) for nm in buses}
    # ---- 4. supplies -------------------------------------------------------------------------------------------------------------------------
    ystrip_vss = bank_y + 1.935; ystrip_vdda = bank_y + 19.515
    for side in (0, 1):
        f = (lambda x: x) if side == 0 else mir
        # macro edge pins (metal1 strips extended to the macro edge)
        xs = (0.0, 2*XC)[side]
        xe = bkP.macro_bbox()[0] + 0.44
        for y, nm in ((ystrip_vss, 'VSS'), (ystrip_vdda, 'VDDA')):
            if side == 0: T.rect('metal1', 0.0, y - 0.115, xe + 0.1, y + 0.115)
            else: T.rect('metal1', mir(xe) - 0.1, y - 0.115, 2*XC, y + 0.115)
            T.label('metal1', (0.5 if side == 0 else 2*XC - 0.5), y, nm, kind=('ground bidirectional' if nm == 'VSS' else 'power bidirectional'), size=0.2)
        # VSS: CDAC inner ground strap (macro x = 105.86) goes up to the bank VSS strip level; comparator VSS ties into it
        xg = f(fp.CDAC_OX + 99.86)
        ytopg = 159.2 if side == 0 else bank_y + 1.935 + 2
        T.rect('metal2', xg - 0.2, cdP.macro_bbox()[3] - 14.0, xg + 0.2, (ystrip_vss + 0.2))       # bridge from the strap top (macro y ~93.7) to the bank strip level
        T.via12(xg, ystrip_vss)
        xin = f(xr_b - 0.44) if side == 0 else mir(xr_b - 0.44)
        T.rect('metal1', min(xin, xg) - 0.2, ystrip_vss - 0.115, max(xin, xg) + 0.2, ystrip_vss + 0.115)
        ycv = cmp_.pin('VSS')[2]; xcv = cmp_.pin('VSS')[1] if side == 0 else cmp_.ox + comp_m1_pieces(cmp_.pin('VSS')[2] - cmp_.oy)[-1][0] + 0.1
        if side == 0 or os.environ.get('VSS_BOTH', '1') == '1': T.via12(xg, ycv); T.rect('metal1', min(xg, xcv) - 0.2, ycv - 0.17, max(xg, xcv) + 0.2, ycv + 0.17)
        # VDDA: m2 vertical beside the comparator from comp VDD strip up to the bank VDDA strip level
        xv = f(109.2); ycd = cmp_.pin('VDD')[2]; xcd = cmp_.pin('VDD')[1] if side == 0 else cmp_.ox + comp_m1_pieces(cmp_.pin('VDD')[2] - cmp_.oy)[-1][0] + 0.1
        T.via12(xv, ycd); T.rect('metal1', min(xv, xcd) - 0.2, ycd - 0.17, max(xv, xcd) + 0.2, ycd + 0.17)
        T.rect('metal2', xv - 0.2, ycd - 0.2, xv + 0.2, ystrip_vdda + 0.2)
        T.via12(xv, ystrip_vdda)
        T.rect('metal1', min(xin, xv) - 0.2, ystrip_vdda - 0.115, max(xin, xv) + 0.2, ystrip_vdda + 0.115)
    # ---- 5. LO/HIB channel -------------------------------------------------------------------------------------------------------------------
    for side, bk, sfx in ((0, bkP, 'p'), (1, bkN, 'n')):
        nets = [('LO%d' % k, 'lo_%s%d' % (sfx, k)) for k in range(11)] + [('HIB%d' % k, 'hib_%s%d' % (sfx, k)) for k in range(10)]
        nets.sort(key=lambda t: lg.pin(t[1])[1], reverse=(side == 1))
        for i, (bn, ln) in enumerate(nets):
            b = bk.pin(bn); l = lg.pin(ln); yt = yT_lo0 + LP*i
            T.path([(b[1], b[2]), (b[1], yt), (l[1], yt), (l[1], l[2])], ['metal4', 'metal3', 'metal4'])
    # ---- 6. comparator / track nets: logic bottom-centre pins straight down through the void (jog band above the VREFP-free area) -----------------
    import itertools
    mids = [('clkc', 'CLK'), ('coN', 'OUTN'), ('coP', 'OUTP'), ('trkA_b', 'TRKAB'), ('trkB', None), ('trkB_b', None)]
    band0 = bank_y + buses['TRKB'][1] + 0.3 + 0.25 + 0.3
    levels = [band0 + 0.9*i for i in range(6)]
    assert levels[-1] + 0.8 < bank_y + buses['VREFP'][0], (levels, bank_y + buses['VREFP'][0])
    xt = {'trkB': XC - 12.0, 'trkB_b': XC - 13.5}
    info = []
    for name, cp in mids:
        if name=='clk' and os.environ.get('CPB_CLOCK_WINDOW')=='1':continue
        lp = lg.pin(name)
        if cp: tp = cmp_.pin(cp); info.append((name, lp[1], lp[2], tp[1], tp[2]))
        else: info.append((name, lp[1], lp[2], xt[name], ybar['TRK' if name == 'trkB' else 'TRKB']))
    def ok(perm):
        v = []
        for (name, x1, y1, x2, y2), lv in zip(info, perm):
            v.append((x1, lv, y1, name)); v.append((x2, y2, lv, name))
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                a_, b_ = v[i], v[j]
                if a_[3] == b_[3]: continue
                if abs(a_[0] - b_[0]) < 0.95 and min(a_[2], b_[2]) + 0.6 > max(a_[1], b_[1]) - 0.0 and True:
                    if not (a_[2] + 0.6 < b_[1] or b_[2] + 0.6 < a_[1]): return False
        return True
    perm = next((p for p in itertools.permutations(levels) if ok(p)), None)
    assert perm is not None, 'no feasible jog-level assignment'
    for (name, x1, y1, x2, y2), lv in zip(info, perm):
        T.path([(x1, y1), (x1, lv), (x2, lv), (x2, y2)], ['metal4', 'metal3', 'metal4'])
        if name in xt: T.via34(x2, y2)
    ym = lgb[3] + 1.5
    # ---- 7. macro pins at the top edge ------------------------------------------------------------------------------------------------------
    for name, mp in [('clk', 'CLK'), ('dv', 'DV')] + [('d%d' % k, 'D%d' % k) for k in range(11)]:
        if name=='clk' and os.environ.get('CPB_CLOCK_WINDOW')=='1':continue
        lp = lg.pin(name)
        T.seg('metal4', lp[1], lp[2], lp[1], ym, 0.8); T.rect('metal4', lp[1] - 0.4, ym - 0.4, lp[1] + 0.4, ym + 0.4)
        T.label('metal4', lp[1], ym, mp, size=0.4)
    # logic supply straps: VDDD up to the top edge, VSS strap down to the backbone
    xvd = lg.tx(-2.0); xvs = lg.tx(-1.2)
    ys_top = lg.ty(38.38); ys_bot = lg.ty(-0.3)
    T.rect('metal2', xvd - 0.25, ys_top - 0.1, xvd + 0.25, ym + 0.5)
    T.label('metal2', xvd, ym + 0.2, 'VDDD', kind='power bidirectional', size=0.3)
    ybb = lgb[1] - 1.0
    T.rect('metal2', xvs - 0.25, ybb - 0.2, xvs + 0.25, ys_bot + 0.1)
    xg = fp.CDAC_OX + 99.86
    T.rect('metal2', xvs - 0.25, ybb - 0.2, xg + 0.2, ybb + 0.2)
    T.rect('metal2', xg - 0.2, ystrip_vss - 0.2, xg + 0.2, ybb + 0.2)
    import cpb_routes
    if os.environ.get('CPB_SHIELD') == '1': cpb_routes.shields(T,lg,cmp_)
    if os.environ.get('CPB_POWER') == '1': cpb_routes.power(T,lg,cmp_,bank_y,ym)
    meta = dict(places={n: dict(bbox=p.macro_bbox()) for n, p in (('cdacP', cdP), ('cdacN', cdN), ('bankP', bkP), ('bankN', bkN), ('comp', cmp_), ('logic', lg))}, ym=ym, bank_y=bank_y, y_l=y_l, cpb_input_filter=os.environ.get('CPB_INPUT_FILTER')=='1',cpb_shield=os.environ.get('CPB_SHIELD')=='1',cpb_power=os.environ.get('CPB_POWER')=='1')
    if os.environ.get('CPB_LOGIC_MESH')=='1':
        import cpb_logic_mesh
        meta['logic_power_mesh']=cpb_logic_mesh.add(T,lg)
    if os.environ.get('CPB_TOPSHUNT')=='1':
        import cpb_shunt
        meta['places'].update(cpb_shunt.add(T,cdP,cdN));meta['top_shunt_fF_per_side']=6220.8951
    if os.environ.get('CPB_CLOCK_WINDOW')=='1':
        import cpb_clock_window
        meta['places']['phase']=cpb_clock_window.add(T,lg,cmp_,bank_y)
    return c, dict(cdP=cdP, cdN=cdN, bkP=bkP, bkN=bkN, cmp=cmp_, lg=lg, meta=meta, ym=ym)

def write_ref(out):
    L = []
    for d, cell in BLK.values():
        f = os.path.join(HERE, d, cell + '_ref.spice'); L.append(open(f).read())
    if os.environ.get('CPB_CLOCK_WINDOW')=='1':L.append(open(os.path.join(HERE,os.environ.get('CLOCK_PHASE_DIR','clock_phase'),'clock_phase.spice')).read())
    ports = ['VINP', 'VINN', 'VREFP', 'VREFN', 'VDDA', 'VDDD', 'VSS', 'CLK'] + ['D%d' % k for k in range(10, -1, -1)] + ['DV']
    T = ['.subckt sar_adc_macro ' + ' '.join(ports)]
    T.append('xcdP top_p VSS ' + ' '.join('bp%d' % k for k in range(11)) + ' cdac_core')
    T.append('xcdN top_n VSS ' + ' '.join('bn%d' % k for k in range(11)) + ' cdac_core')
    for sfx, vin in (('p', 'VINP'), ('n', 'VINN')):
        T.append('xbk%s %s trkB trkB_b VREFP VREFN VDDA VSS ' % (sfx.upper(), vin) + ' '.join('b%s%d' % (sfx, k) for k in range(11)) + ' ' + ' '.join('lo_%s%d' % (sfx, k) for k in range(11)) + ' ' + ' '.join('hib_%s%d' % (sfx, k) for k in range(10)) + ' bank_side')
    T.append('xcmp top_n top_p CLKC coP coN VDDA VSS trkA_b comparator_core'.replace('CLKC', 'clkc'))
    if os.environ.get('CPB_CLOCK_WINDOW')=='1':T.append('xphase CLK CLK_Q VDDD VSS clock_phase')
    T.append('xlogic '+('CLK_Q' if os.environ.get('CPB_CLOCK_WINDOW')=='1' else 'clk')+' coP coN trkA_b trkB trkB_b clkc ' + ' '.join('lo_p%d' % k for k in range(11)) + ' ' + ' '.join('hib_p%d' % k for k in range(10)) + ' ' + ' '.join('lo_n%d' % k for k in range(11)) + ' ' + ' '.join('hib_n%d' % k for k in range(10)) + ' ' + ' '.join('d%d' % k for k in range(10, -1, -1)) + ' dv VDDD VSS sar_logic_core')
    if os.environ.get('CPB_TOPSHUNT')=='1':
        for s in ['p','n']:
            for i in range(6):T.append('xshunt%s%d top_%s VSS sky130_fd_pr__cap_mim_m3_1 w=27 l=18.92'%(s,i,s))
    T.append('.ends')
    open(out, 'w').write('\n'.join(L) + '\n' + '\n'.join(T) + '\n')

if __name__ == '__main__':
    c, P = build()
    out = os.environ.get('TOP_OUTDIR', os.path.join(HERE, 'top')); os.makedirs(out, exist_ok=True)
    for d, cell in BLK.values():
        shutil.copy(os.path.join(HERE, d, cell + '.mag'), out)
        for f in os.listdir(os.path.join(HERE, d)):
            if f.endswith('.mag') and f not in ('neg.mag',): shutil.copy(os.path.join(HERE, d, f), out)
    if os.environ.get('CPB_CLOCK_WINDOW')=='1':
        for f in os.listdir(os.path.join(HERE,os.environ.get('CLOCK_PHASE_DIR','clock_phase'))):
            if f.endswith('.mag'):shutil.copy(os.path.join(HERE,os.environ.get('CLOCK_PHASE_DIR','clock_phase'),f),out)
    c.write(out)
    if os.environ.get('CPB_TOPSHUNT')=='1':shutil.copy(os.path.join(HERE,'devs','dev_mim_w27_l18p92.mag'),out)
    write_ref(os.path.join(out, 'sar_adc_macro_ref.spice'))
    json.dump(P['meta'], open(os.path.join(out, 'meta.json'), 'w'), indent=1)
    print(json.dumps(P['meta']))
