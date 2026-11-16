#!/usr/bin/env python3
"""Comparator (StrongARM, NMOS input) layout, mirror symmetric: left = INN branch (M2,M4,M6,M8,M10, MIM on y, out n), right = INP branch.
Nets: inp inn clk outp outn x y tail vdd vss.  Rows: VSS ptap | N row | P row (nwell) | VDD ntap, MIM caps above.  Uses devgen + route."""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import devgen
from lay import Cell
from route import Router

WMIN = 1.5
# name: (kind, W, row, nets: (bottom strap net, top strap net, gate net))
DEV = {
 'M4': ('nfet', 2.0, 'N', ('y', 'outn', 'outp')), 'M2': ('nfet_lvt', 8.0, 'N', ('tail', 'y', 'inn')), 'MT': ('nfet', 4.0, 'N', ('vss', 'tail', 'clk')),
 'M1': ('nfet_lvt', 8.0, 'N', ('tail', 'x', 'inp')), 'M3': ('nfet', 2.0, 'N', ('x', 'outp', 'outn')),
 'M10': ('pfet', 1.5, 'P', ('y', 'vdd', 'clk')), 'M8': ('pfet', 1.5, 'P', ('outn', 'vdd', 'clk')), 'M6': ('pfet', 3.0, 'P', ('outn', 'vdd', 'outp')),
 'MS1': ('pfet', 2.0, 'P', ('vdd', 'inn', 'trkab')), 'MS2': ('pfet', 2.0, 'P', ('vdd', 'inp', 'trkab')),
 'M5': ('pfet', 3.0, 'P', ('outp', 'vdd', 'outn')), 'M7': ('pfet', 1.5, 'P', ('outp', 'vdd', 'clk')), 'M9': ('pfet', 1.5, 'P', ('x', 'vdd', 'clk')),
}
ORDER_N = ['M4', 'M2', 'MT', 'M1', 'M3']
ORDER_P = ['MS1', 'M10', 'M8', 'M6', 'M5', 'M7', 'M9', 'MS2']
RESET_BUFFER = bool(int(os.environ.get('COMP_RESET_BUFFER', '0')))
RESET_WIDTH = float(os.environ.get('COMP_RESET_WIDTH', '2'))
for reset in ['MS1', 'MS2']:
    DEV[reset] = ('pfet', RESET_WIDTH, 'P', ('vdd', DEV[reset][3][1], 'resetGate' if RESET_BUFFER else 'trkab'))
if RESET_BUFFER:
    DEV.update({
        'BN0': ('nfet', 4., 'N', ('vss', 'resetMid', 'trkab')),
        'BP0': ('pfet', 8., 'P', ('vdd', 'resetMid', 'trkab')),
        'BN1': ('nfet', 8., 'N', ('vss', 'resetGate', 'resetMid')),
        'BP1': ('pfet', 16., 'P', ('vdd', 'resetGate', 'resetMid')),
    })
    ORDER_N = ['M4', 'M2', 'BN0', 'MT', 'BN1', 'M1', 'M3']
    ORDER_P = ['MS1', 'M10', 'M8', 'M6', 'BP0', 'BP1', 'M5', 'M7', 'M9', 'MS2']
LAT_X, LAT_Y = 0.12, 0.17
CO1 = float(os.environ.get('COMP_CO1', '3.23'))     # OUTN load MIM slightly larger: balances the extracted OUTP/OUTN parasitic imbalance (~0.9 fF) -> |offset| < 0.5 mV (PEX)

def spec(name):
    kind, W, row, nets = DEV[name]
    nf = max(1, int(math.ceil(W/5.0 - 1e-9))); Wf = round(W/nf, 2)
    return kind, Wf, nf

def build(name='comparator_core'):
    c = Cell(name)
    Hh = 2.5 + 0.45
    Y = {}
    Y['ptap'] = 0.4
    Y['cy_n'] = round((1.4 + Hh)/LAT_Y)*LAT_Y
    n_top = Y['cy_n'] + Hh
    Y['cy_p'] = round((n_top + 1.0 + Hh)/LAT_Y)*LAT_Y
    p_top = Y['cy_p'] + Hh
    Y['ntap'] = p_top + 0.5
    Y['nwell'] = (n_top + 0.45, Y['ntap'] + 0.17 + 0.5)
    Y['rail'] = Y['nwell'][1] + 0.4          # (unused rails)
    m2_obs = []; terms = {}
    def term(net, layer, *a): terms.setdefault(net, []).append((layer,) + a)
    devs = {}
    x0 = 1.2
    plans = {}
    for row, order, cy in (('N', ORDER_N, Y['cy_n']), ('P', ORDER_P, Y['cy_p'])):
        xc = x0
        plans[row] = []
        for nm in order:
            kind, Wf, nf = spec(nm)
            dev = devgen.get(kind, Wf, 0.15, nf)
            cx = math.ceil((xc - dev.bbox[0] + 0.55)/0.24 - 1e-9)*0.24
            plans[row].append((nm, dev, cx, cy))
            xc = cx + dev.bbox[2] + 0.6
        if row == 'N': xN = xc
        else: xP = xc
    shift_n = round((xP-xN)/2/.24)*.24 if os.environ.get('COMP_CENTER_N') == '1' else 0
    for row, plan in plans.items():
        for nm, dev, cx, cy in plan:
            devs[nm] = devgen.place(c,dev,cx+(shift_n if row=='N' else 0),cy,'x_'+nm)
    W = max(xN, xP) + 0.8
    # re-center rows horizontally?  keep left aligned; symmetric ordering gives near symmetry
    for nm, g in devs.items():
        kind, Wk, row, (nb, nt, ng) = DEV[nm]
        for which, net in (('bot', nb), ('top', nt)):
            st = g.s_strap if which == 'bot' else g.d_strap
            xs = g.s_xs if which == 'bot' else g.d_xs
            rr = (st[0]-0.2, st[2]-0.14, st[1]+0.2, st[2]+0.14)
            m2_obs.append((rr, net)); terms.setdefault(net, []).append(('rect', 'metal2', rr, tuple(xs)))
        bar = g.g_top if g.g_top else g.g_bot
        which = 'top' if g.g_top else 'bot'
        xx = math.floor(bar[1]/LAT_X + 1e-9)*LAT_X
        if xx < bar[0]: xx = math.ceil(bar[0]/LAT_X - 1e-9)*LAT_X
        yy = math.ceil((bar[2] + 0.035)/LAT_Y - 1e-9)*LAT_Y if which == 'top' else math.floor((bar[2] - 0.035)/LAT_Y + 1e-9)*LAT_Y
        devgen.via1_pad(c, xx, yy); m2_obs.append(((xx-0.2, yy-0.2, xx+0.2, yy+0.2), ng)); terms.setdefault(ng, []).append(('pt', 'metal2', xx, yy))
    devgen.tap(c, 'p', 0.5, W-0.5, Y['ptap'])
    c.rect('nwell', 0.0, Y['nwell'][0], W, Y['nwell'][1])
    devgen.tap(c, 'n', 0.5, W-0.5, Y['ntap'])
    # taps -> nets vss / vdd : terminals on the tap metal1 are reached through short via stacks placed by hand
    # MIM caps above the P row:  x (100 fF), y (100 fF), outp, outn (20 fF);  bottom plates to vss
    ymim = Y['nwell'][1] + 1.5
    mims = []
    specs_m = [('cy', 'y', 7.07), ('cx', 'x', 7.07), ('co1', 'outn', CO1), ('co2', 'outp', 3.16)]
    xm = 1.0
    for nm, net, wl in specs_m:
        m = devgen.get_mim(wl, wl)
        cxm = xm - m.bbox[0]
        cym = ymim - m.bbox[1]
        c.use(m.cell, 'x_' + nm, cxm, cym)
        top = (cxm + m.top[0], cym + m.top[1], cxm + m.top[2], cym + m.top[3]); bot = (cxm + m.bot[0], cym + m.bot[1], cxm + m.bot[2], cym + m.bot[3])
        terms.setdefault(net, []).append(('rect', 'metal4', top, ()))
        terms.setdefault('vss', []).append(('rect', 'metal4', bot, ()))
        m3r = m.rects['metal3']; m3b = (cxm + min(r[0] for r in m3r), cym + min(r[1] for r in m3r), cxm + max(r[2] for r in m3r), cym + max(r[3] for r in m3r))
        mims.append((nm, net, wl, top, bot, m3b))
        xm = cxm + m.bbox[2] + 1.6
    H = ymim + 10.0
    W = max(W, xm + 0.4)
    return c, dict(W=W, H=H, Y=Y, devs=devs, terms=terms, m2_obs=m2_obs, mims=mims)

def finish(c, meta):
    W, H, Y = meta['W'], meta['H'], meta['Y']; terms = meta['terms']; m2_obs = meta['m2_obs']
    sn = lambda v, p: round(v/p)*p
    # tap via stacks as terminals (vss on ptap, vdd on ntap)
    for xx in [sn(x, LAT_X) for x in (1.5, W/2, W-1.5)]:
        yy = sn(Y['ptap'] + 0.085, LAT_Y); devgen.via1_pad(c, xx, yy, 0.14); m2_obs.append(((xx-0.2, yy-0.14, xx+0.2, yy+0.14), 'vss')); terms['vss'].append(('rect', 'metal2', (xx-0.2, yy-0.14, xx+0.2, yy+0.14), ()))
        yy = sn(Y['ntap'] + 0.085, LAT_Y); devgen.via1_pad(c, xx, yy, 0.14); m2_obs.append(((xx-0.2, yy-0.14, xx+0.2, yy+0.14), 'vdd')); terms['vdd'].append(('rect', 'metal2', (xx-0.2, yy-0.14, xx+0.2, yy+0.14), ()))
    # pins (metal4 pads)
    pins = {'inn': (sn(0.8, LAT_X), sn(H*0.45, LAT_Y)), 'inp': (sn(W-0.8, LAT_X), sn(H*0.45, LAT_Y)),
            'clk': (sn(W/2-1.9, LAT_X), sn(H-0.5, LAT_Y)), 'outn': (sn(W/2-0.0, LAT_X), sn(H-0.5, LAT_Y)), 'outp': (sn(W/2+1.9, LAT_X), sn(H-0.5, LAT_Y)), 'trkab': (sn(W/2+3.8, LAT_X), sn(H-0.5, LAT_Y))}
    for n, (px, py) in pins.items(): terms.setdefault(n, []).append(('pt', 'metal4', px, py))
    r = Router((0, 0, W, H), dx=LAT_X, dy=LAT_Y, ox=0.0, oy=0.0)
    r.bridge = os.environ.get('COMP_BRIDGE') == '1'
    for rect, net in m2_obs: r.obstacle('metal2', rect, net)
    # MIM keep-out for foreign metal3 (capm.11): expand by 1.34
    for nm, net, wl, top, bot, m3b in meta['mims']:
        k = 1.34 + 0.1
        r.obstacle('metal3', (m3b[0]-k, m3b[1]-k, m3b[2]+k, m3b[3]+k), None)
    for nm, net, wl, top, bot, m3b in meta['mims']:
        r.obstacle('metal4', (top[0]-0.45, top[1]-0.45, top[2]+0.45, top[3]+0.45), net, draw=False)
        r.obstacle('metal4', (bot[0]-0.12, bot[1]-0.12, bot[2]+0.12, bot[3]+0.12), 'vss', draw=False)
    for net, ts in terms.items():
        for t in ts:
            if t[0] == 'pt': r.add(net, t[1], t[2], t[3], pad=True)
            else: r.add_rect(net, t[1], t[2], pad=False, pads=t[3])
    order = ['vss', 'vdd', 'x', 'y', 'outp', 'outn', 'tail', 'inp', 'inn', 'resetGate', 'resetMid', 'clk', 'trkab']
    if os.environ.get('COMP_CLK_FIRST') == '1':
        order.remove('clk');order.insert(2,'clk')
    fails = r.route_all(order=[n for n in order if n in r.nets], tries=10, reserve=True)
    r.extra = [(n, 'metal4', (px-0.4, py-0.4, px+0.4, py+0.4)) for n, (px, py) in pins.items()]
    r.emit(c)
    if RESET_BUFFER and RESET_WIDTH == 127.92 and os.environ.get('COMP_CENTER_N') == '1':
        # Close the 0.24um same-net notch at the right output MIM access.
        # Its two sides belong to one extracted conductor; full LVS verifies it.
        c.rect('metal4',33.03,16.34,33.27,19.57)
    for nm in r.fail:
        print('FAIL', nm, r.diags.get(r.nets[nm]))
        n = r.nets[nm]
        for gi, grp in enumerate(r.terms[n]):
            if gi == len(r.terms[n]) - 1 or True:
                t = grp[len(grp)//2]; print('   cand', t[:3], 'blk', r.blk_w[t[0]].get((t[1], t[2])), 'net', n)
            print('   grp', gi, grp[0][0], len(grp), sum(1 for t in grp if r.free(n, t[0], t[1], t[2], r.gpad[n][gi])), [round(v, 2) for v in grp[0][3:]])
    port = 1
    for n, (px, py) in pins.items():
        c.label('metal4', px, py, n.upper(), port=port, kind='signal bidirectional', size=0.4); port += 1
    c.label('metal1', 0.8, Y['ptap'] + 0.08, 'VSS', port=port, kind='ground bidirectional', size=0.1); port += 1
    c.label('metal1', 0.8, Y['ntap'] + 0.08, 'VDD', port=port, kind='power bidirectional', size=0.1)
    return fails

def lvs_ref():
    L = [".subckt comparator_core INP INN CLK OUTP OUTN VDD VSS TRKAB"]
    nm = lambda n: {'inp': 'INP', 'inn': 'INN', 'clk': 'CLK', 'outp': 'OUTP', 'outn': 'OUTN', 'vdd': 'VDD', 'vss': 'VSS', 'trkab': 'TRKAB'}.get(n, n)
    for name, (kind, W, row, (nb, nt, ng)) in DEV.items():
        k, Wf, nf = spec(name)
        model = {'nfet': 'sky130_fd_pr__nfet_01v8', 'pfet': 'sky130_fd_pr__pfet_01v8', 'nfet_lvt': 'sky130_fd_pr__nfet_01v8_lvt'}[kind]
        bulk = 'VSS' if kind.startswith('nfet') else 'VDD'
        for f in range(nf):
            L.append("x%s_%d %s %s %s %s %s w=%g l=0.15" % (name, f, nm(nt), nm(ng), nm(nb), bulk, model, Wf))
    for cn, net, wl in (('cy', 'y', 7.07), ('cx', 'x', 7.07), ('co1', 'outn', CO1), ('co2', 'outp', 3.16)):
        L.append("x%s %s VSS sky130_fd_pr__cap_mim_m3_1 w=%g l=%g" % (cn, nm(net), wl, wl))
    L.append(".ends comparator_core")
    return '\n'.join(L) + '\n'

if __name__ == '__main__':
    out = os.environ.get('COMP_OUTDIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comp'))
    c, meta = build()
    fails = finish(c, meta)
    c.write(out)
    import shutil, glob
    for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devs', 'dev_*.mag')): shutil.copy(f, out)
    open(os.path.join(out, 'comparator_core_ref.spice'), 'w').write(lvs_ref())
    json.dump(dict(W=meta['W'], H=meta['H'], fails=fails), open(os.path.join(out, 'meta.json'), 'w'))
    print('W %.1f H %.1f area %.0f fails %s' % (meta['W'], meta['H'], meta['W']*meta['H'], fails))
