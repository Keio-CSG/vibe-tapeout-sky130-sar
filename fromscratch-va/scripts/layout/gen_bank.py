#!/usr/bin/env python3
"""Sampling switch + reference driver bank for one CDAC side (P orientation).  Uses devgen (gencell fets) + route (maze router).
Rows (bottom->top): VREFN bus (m3) | ptap | N row | channel buses VIN,TRK,TRKB (m3) | P row (nwell) | ntap | VREFP bus (m3).
Pins: BOT0..10 (metal4 pads, bottom edge), LO0..10 / HIB0..9 (metal4 pads, top edge), buses VIN TRK TRKB VREFN VREFP (metal3 bars, both ends), VSS/VDDA (metal1 tap strips)."""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import devgen
from lay import Cell
from route import Router

WFMAX = 5.0
def specs(k):
    wgt = 512 >> k if k < 10 else 1
    f = wgt/512.0
    S = {}
    def one(name, kind, W, wmin):
        W = max(wmin, round(W, 2)); nf = max(1, int(math.ceil(W/WFMAX - 1e-9))); Wf = round(W/nf, 2)
        if Wf < wmin: Wf = wmin
        S[name] = dict(kind=kind, nf=nf, Wf=Wf)
    one('ntg', 'nfet', 48*f, 1.5); one('ptg', 'pfet', 96*f, 1.5)
    ndr_min = 1.8 if os.environ.get('BANK_ANTENNA') == '1' and k in (6,7) else 1.5
    one('ndr', 'nfet', 6*f, ndr_min)
    if k < 10: one('pdr', 'pfet', 30*f, 1.5)
    return S

def build(name='bank_side'):
    c = Cell(name)
    H = WFMAX/2 + 0.45
    Y = {}
    Y['bus_n'] = (0.0, 1.5)
    Y['ptap'] = 1.85
    Y['cy_n'] = round((2.6 + H)/0.17)*0.17
    n_top = Y['cy_n'] + H
    Y['vin'] = (n_top + 0.7, n_top + 1.4); Y['trk'] = (n_top + 1.8, n_top + 2.5); Y['trkb'] = (n_top + 2.9, n_top + 3.6)
    Y['cy_p'] = round((Y['trkb'][1] + 0.9 + H)/0.17)*0.17
    p_top = Y['cy_p'] + H
    Y['ntap'] = p_top + 0.5
    Y['nwell'] = (Y['trkb'][1] + 0.35, Y['ntap'] + 0.17 + 0.5)
    Y['bus_p'] = (Y['nwell'][1] + 0.5, Y['nwell'][1] + 2.0)
    Y['top'] = Y['bus_p'][1] + 1.2
    # ---- place devices ----------------------------------------------------------------------------------------------
    x = 1.0
    slices = []
    nets_term = {}     # net -> list of (layer, x, y)
    m2_obs = []        # (rect, net)
    def term(net, layer, xx, yy): nets_term.setdefault(net, []).append(('pt', layer, xx, yy))
    def term_rect(net, layer, rect, pads=()): nets_term.setdefault(net, []).append(('rect', layer, rect, pads))
    def term_bar(net, layer, pts): nets_term.setdefault(net, []).append(('bar', layer, pts))
    order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    lvs = []           # (name, kind, W, nf, d, g, s, b)
    for k in order:
        sp = specs(k)
        sx0 = x
        devs = {}
        # N row: ndr then ntg ; P row: pdr then ptg
        for row, names, cy in (('N', ['ndr', 'ntg'], Y['cy_n']), ('P', ['pdr', 'ptg'], Y['cy_p'])):
            xc = sx0 + 0.3
            for nm in names:
                if nm not in sp: continue
                s = sp[nm]; dev = devgen.get(s['kind'], s['Wf'], 0.15, s['nf'])
                cx = math.ceil((xc - dev.bbox[0] + 0.55)/0.24 - 1e-9)*0.24
                g = devgen.place(c, dev, cx, cy, 'x_%s%d' % (nm, k))
                devs[nm] = g; xc = g.bbox[2] + 0.35
            devs['_end_' + row] = xc
        x = max(max(devs['_end_N'], devs['_end_P']) + 0.3, sx0 + float(os.environ.get('MINW', '5.0')))
        slices.append((k, sx0, x, devs, sp))
    W = x + 0.4
    # ---- net assignment: strap parity: 'bot strap' = s_strap (even cols, at bottom), 'top strap' = d_strap ---------------------------
    def m2rect(r, net): c.rect('metal2', *r); m2_obs.append((r, net))
    for k, sx0, sx1, devs, sp in slices:
        bot, lo, hib = 'BOT%d' % k, 'LO%d' % k, 'HIB%d' % k
        def strap_term(g, which, net):
            st = g.s_strap if which == 'bot' else g.d_strap
            xs = (g.s_xs if which == 'bot' else g.d_xs)
            rr = (st[0]-0.2, st[2]-0.14, st[1]+0.2, st[2]+0.14)
            m2_obs.append((rr, net))
            if net in ('VREFN', 'VREFP') and os.environ.get('BANK_PADS', '1') == '1':       # one terminal per S/D column pad: parallel routes to the bus (star routing)
                for x_ in xs: term_rect(net, 'metal2', (x_-0.2, st[2]-0.14, x_+0.2, st[2]+0.14), (x_,))
            else: term_rect(net, 'metal2', rr, tuple(xs))
        def gate_term(g, which, net):
            bar = g.g_top if which == 'top' else g.g_bot
            # via pad on the bar, snapped to the router lattice (x within the bar, y shifted away from the S/D column ends)
            xx = math.floor(bar[1]/0.24 + 1e-9)*0.24
            if xx < bar[0]: xx = math.ceil(bar[0]/0.24 - 1e-9)*0.24
            yy = math.ceil((bar[2] + 0.035)/0.17 - 1e-9)*0.17 if which == 'top' else math.floor((bar[2] - 0.035)/0.17 + 1e-9)*0.17
            devgen.via1_pad(c, xx, yy); m2_obs.append(((xx-0.2, yy-0.2, xx+0.2, yy+0.2), net)); term(net, 'metal2', xx, yy)
        g = devs['ntg']; strap_term(g, 'bot', bot); strap_term(g, 'top', 'VIN'); gate_term(g, 'top', 'TRK')
        g = devs['ndr']; strap_term(g, 'bot', 'VREFN'); strap_term(g, 'top', bot); gate_term(g, 'top', lo)
        g = devs['ptg']; strap_term(g, 'bot', 'VIN'); strap_term(g, 'top', bot); gate_term(g, 'bot', 'TRKB')
        if 'pdr' in devs:
            g = devs['pdr']; strap_term(g, 'bot', bot); strap_term(g, 'top', 'VREFP'); gate_term(g, 'top', hib)
        # pins
        sn = lambda v, p: round(v/p)*p
        term(bot, 'metal4', sn(sx0 + 0.9, 0.24), sn(Y['bus_n'][0] + 0.5, 0.17))
        term(lo, 'metal4', sn(sx0 + 0.9, 0.24), sn(Y['top'] - 0.5, 0.17))
        if 'pdr' in devs: term(hib, 'metal4', sn(sx0 + 2.7, 0.24), sn(Y['top'] - 0.5, 0.17))
        # LVS device list (per finger)
        for nm, (kd, d, gg) in {'ntg': ('nfet', 'VIN', 'TRK'), 'ptg': ('pfet', 'VIN', 'TRKB'), 'ndr': ('nfet', 'VREFN', lo), 'pdr': ('pfet', 'VREFP', hib)}.items():
            if nm not in sp: continue
            s = sp[nm]
            for f in range(s['nf']):
                lvs.append(('x%s%d_%d' % (nm, k, f), kd, s['Wf'], d, gg, bot))
    # ---- buses (metal3) and taps -------------------------------------------------------------------------------------------
    buses = {'VREFN': Y['bus_n'], 'VIN': Y['vin'], 'TRK': Y['trk'], 'TRKB': Y['trkb'], 'VREFP': Y['bus_p']}
    for net, (y1, y2) in buses.items():
        c.rect('metal3', 0.0, y1, W, y2)
        c.label('metal3', 0.4, 0.5*(y1+y2), net, port=None)
        for xx in (0.0, W):
            pass
        # a terminal at each device terminal x: add bus terminals
    for net in ('VIN', 'TRK', 'TRKB', 'VREFN', 'VREFP'):
        y1, y2 = buses[net]; term_rect(net, 'metal3', (0.3, y1, W-0.3, y2))
    devgen.tap(c, 'p', 0.5, W-0.5, Y['ptap'])
    c.rect('nwell', 0.0, Y['nwell'][0], W, Y['nwell'][1])
    devgen.tap(c, 'n', 0.5, W-0.5, Y['ntap'])
    # ---- routing ----------------------------------------------------------------------------------------------------------
    names = {}
    r = Router((0, 0, W, Y['top']), dx=0.24, dy=0.17, ox=0.0, oy=0.0)
    for rect, net in m2_obs: r.obstacle('metal2', rect, net)
    for net, (y1, y2) in buses.items(): r.obstacle('metal3', (0.0, y1, W, y2), net)
    gmap = {}
    for net, ts in nets_term.items():
        for t in ts:
            if t[0] == 'pt': r.add(net, t[1], t[2], t[3], pad=True)
            elif t[0] == 'rect': r.add_rect(net, t[1], t[2], pad=False, pads=(t[3] if len(t) > 3 else ()))
            else: r.add_group(net, t[1], t[2], pad=True); gmap[(net, len(r.terms[r.nid(net)])-1)] = 1
    if os.environ.get('BANK_STAR', '1') == '1': r.star = set(r.nets[k] for k in ('VREFN', 'VREFP') if k in r.nets)   # each driver strap gets its own route to the bus (no daisy chain)
    if False:
        r.claim_terminals(); bad = []
        for n, ts in r.terms.items():
            for (l, i, j, x, y) in ts:
                if not r.free(n, l, i, j, True): bad.append((round(x, 2), round(y, 2), l, [k for k, v in r.nets.items() if v == n][0]))
        print('blocked terminals', len(bad), bad[:20])
    if os.environ.get('BANK_DEBUG'):
        bad = {}
        for n, groups in r.terms.items():
            for gi, grp in enumerate(groups):
                nfree = sum(1 for t in grp if r.free(n, t[0], t[1], t[2], r.gpad[n][gi]))
                if nfree == 0: bad[(r.nets and [k for k, v in r.nets.items() if v == n][0], gi)] = [(round(t[3], 2), round(t[4], 2), t[0]) for t in grp[:1]]
        print('pristine blocked groups:', len(bad)); [print('  ', k, v) for k, v in list(bad.items())[:25]]
    if os.environ.get('ONLY_NET'):
        keep = os.environ['ONLY_NET'].split(',')
        for nm in list(r.nets):
            if nm not in keep: r.terms[r.nets[nm]] = []; r.gpad[r.nets[nm]] = []
    order = [n for n in ('VREFN', 'VREFP', 'VIN', 'TRK', 'TRKB') if n in r.nets] + sorted([n for n in r.nets if n.startswith('BOT')]) + sorted([n for n in r.nets if n.startswith(('LO', 'HIB'))])
    fails = r.route_all(order=order, tries=int(os.environ.get('BANK_TRIES', '3')))
    r.emit(c)
    from route import chosen_xy
    for nm in r.fail:
        print('FAIL', nm, r.diags.get(r.nets[nm]))
    if r.fail:
        print('diag', r.diag, [k for k, v in r.nets.items() if v == r.diag[0]])
        for nm in r.fail[:6]:
            n = r.nets[nm]
            for gi, grp in enumerate(r.terms[n]):
                nfree = sum(1 for t in grp if r.free(n, t[0], t[1], t[2], r.gpad[n][gi]))
                print('  ', nm, 'group', gi, 'layer', grp[0][0], 'cands', len(grp), 'free', nfree, 'at', [(round(t[3], 2), round(t[4], 2)) for t in grp[:2]])
    # ---- pins/labels ----------------------------------------------------------------------------------------------------------
    port = 1
    for net, (y1, y2) in buses.items():
        c.label('metal3', 0.3, 0.5*(y1+y2), net, port=port, kind='signal bidirectional', size=0.3); port += 1
    for net in nets_term:
        if net.startswith(('BOT', 'LO', 'HIB')):
            ly, xx, yy = [t[1:] for t in nets_term[net] if t[0] == 'pt' and t[1] == 'metal4'][0]
            c.rect('metal4', xx-0.4, yy-0.4, xx+0.4, yy+0.4)
            c.label('metal4', xx, yy, net, port=port, kind='signal bidirectional', size=0.4); port += 1
    c.label('metal1', 0.6, Y['ptap'] + 0.08, 'VSS', port=port, kind='ground bidirectional', size=0.1); port += 1
    c.label('metal1', 0.6, Y['ntap'] + 0.08, 'VDDA', port=port, kind='power bidirectional', size=0.1)
    bot_x = {int(net[3:]): [t for t in nets_term[net] if t[0] == 'pt' and t[1] == 'metal4'][0][2] for net in nets_term if net.startswith('BOT')}
    meta = dict(W=W, H=Y['top'], fails=fails, Y={k: v for k, v in Y.items()}, lvs=lvs, bot_x=bot_x)
    return c, meta

if __name__ == '__main__':
    out = os.environ.get('BANK_OUTDIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bank'))
    c, meta = build('bank_side')
    c.write(out)
    # copy device cells
    import shutil, glob
    for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devs', 'dev_*.mag')): shutil.copy(f, out)
    json.dump(meta, open(os.path.join(out, 'meta.json'), 'w'))
    print('W %.1f H %.1f area %.0f  fails %s  devices %d' % (meta['W'], meta['H'], meta['W']*meta['H'], meta['fails'], len(meta['lvs'])))
