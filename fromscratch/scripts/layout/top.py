"""Top-level macro assembly: sar_adc layout (placement + routing)."""
import sys, os, re, collections, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "lib")); sys.path.insert(0, HERE)
from maglib import Cell
import stdlib, stdplace, netlist, cdac, analog, digital, structs
from router import Router, LAY
CELLS = os.path.join(HERE, "cells")
import maglib; maglib.SEARCH.append(CELLS)
NETL = os.path.join(HERE, "..", "..", "schematic", "sar_adc_m3.spice")
GAP = 90.01; XP = 10.0
W_ARR = cdac.build.__defaults__ and 0
def build():
    t0 = time.time()
    ports, insts, other = netlist.parse_top(NETL)
    top = Cell("sar_adc_top")
    # ---- CDAC arrays
    amap = cdac.assignment()
    for nm, sd in (("cdac_p", "p"), ("cdac_n", "n")):
        cc, info = cdac.build(nm, CELLS, amap, 32, 32, side=sd); cc.write(CELLS)
    W = info["w"]; H = info["h"]
    XN = XP + W + GAP + W + 0.12
    top.use("cdac_p", "cdacp", XP, 0.0, "R0"); top.use("cdac_n", "cdacn", XN, 0.0, "MY")
    xbus0 = info["xbus0"]
    # terminal tables: net -> list of (kind, data)
    T = collections.defaultdict(list)
    def cdac_x(side, xl):     # local x -> global x
        return XP + xl if side == "p" else XN - xl
    for k, n in enumerate(cdac.NETS):
        xl = xbus0 + k * cdac.BUS_P
        for side in ("p", "n"):
            nm = {"vrefn": "VSS", "vss": "VSS"}.get(n, f"bot{side}{n[1:]}")
            if nm == "VSS": VSSBUS.append(cdac_x(side, xl)); continue
            T[nm].append(("met2", (cdac_x(side, xl), 0.4)))
    # ---- digital rows (VDDD) -------------------------------------------------
    dig = [i for i in insts if not re.match(r"Xdr[pn]\d+_\d+", i["name"]) and i["name"] not in ("Xnda", "Xndb") and not i["name"].startswith("Xsignoff_")]   #  detectors live in the comparator block
    drv = [i for i in insts if re.match(r"Xdr[pn]\d+_\d+", i["name"])]
    DX, DY = 0.23 * 811 - 10.32, 8.05
    dcell = Cell("dig")
    placed, rows = digital.build_rows(dcell, digital.order(dig, "dig"), 70.0, gap=3.4, variant="dig")
    dcell.write(CELLS); top.use("dig", "dig", DX, DY, "R0")
    for p in placed:
        for pn, net in p.conn.items():
            if pn in ("VPWR", "VGND", "VPB", "VNB"): continue
            (a, b, c_, d_) = p.pin(pn)[0]
            T[net].append(("pin", ((a + c_) / 2 + DX, (b + d_) / 2 + DY)))
    # ---- driver rows (VREFP) ---------------------------------------------------
    for side in ("p", "n"):
        cells = [i for i in drv if i["name"].startswith("Xdr" + side)]
        # order: bit 9 first -> bit 0 last (bit k = 10 - slice index)
        cells.sort(key=lambda i: (int(re.match(r"Xdr[pn](\d+)_(\d+)", i["name"]).group(1)), i["name"]))
        c = Cell("drv_" + side)
        pl, rw = digital.build_rows(c, cells, 400.0, tap_pitch=12.0, variant="drv")
        c.write(CELLS)
        wrow = rw[0]
        ox = 0.23 * 63 - 10.32 if side == "p" else round((XN + 4.0 - wrow + 10.32) / 0.23) * 0.23 - 10.32
        oy = -24.25
        top.use("drv_" + side, "drv" + side, ox, oy, "R0"); DRVG[side] = (ox, ox + wrow, oy)
        for p in pl:
            for pn, net in p.conn.items():
                if pn in ("VPWR", "VGND", "VPB", "VNB"): continue
                (a, b, c_, d_) = p.pin(pn)[0]
                T[net].append(("pin", ((a + c_) / 2 + ox, (b + d_) / 2 + oy)))
    # ---- comparator and sampling switches (VDDA) ------------------------------
    ac = Cell("analog")
    ycen = -12.0
    cm = analog.comparator(ac, 0, 0, dict(ck="ck", inp="topp", inn="topn", oa="oa", ob="ob", VDD="VDDA", VSS="VSS"))
    xc0 = 0.5 * (XP + 142.7 + XN - 142.7) - cm.xmax / 2
    ac2 = Cell("analog")
    detectors = [i for i in insts if i['name'] in ('Xnda', 'Xndb')]
    one_input = all(i['conn']['B'] == i['conn']['C'] == 'VSS' for i in detectors)
    cm = analog.comparator_sym(ac2, (XP + XN) / 2, -20.06, one_input=one_input)   # mirror-symmetric comparator + local detectors
    tgp = analog.tgswitch(ac2, XP + 142.7 - 40, ycen, dict(a="VINP", b="topp", g="trk", gb="trkb", gp="dummy_ptrk" if analog.PARAMS.get("sw_dummy_p_inv",0) else "trk", VDDA="VDDA", VSS="VSS"), "tgp")
    tgn = analog.tgswitch(ac2, (XP + XN) - tgp.xmax, ycen, dict(a="VINN", b="topn", g="trk", gb="trkb", gp="dummy_ptrk" if analog.PARAMS.get("sw_dummy_p_inv",0) else "trk", VDDA="VDDA", VSS="VSS"), "tgn")
    ac2.write(CELLS); top.use("analog", "analog", 0, 0, "R0")
    for blk in (cm, tgp, tgn):
        for net, lst in blk.terms.items():
            for lay, (x1, y1, x2, y2), nm in lst: T[net].append((lay, ((x1 + x2) / 2, (y1 + y2) / 2, (x1, y1, x2, y2))))
    # ---- explicit power / strap / pad structures ----------------------------------
    S = structs.Struct(top, (XP + XN) / 2)
    for side in ("p", "n"):
        avoid = [px for net, lst in T.items() for k in lst if k[0] == "pin" for (px, py) in [k[1]] if DRVG[side][2] - 1 < py < DRVG[side][2] + 4 and DRVG[side][0] - 1 < px < DRVG[side][1] + 1]
        S.driver_power(side, DRVG[side][0], DRVG[side][1], DRVG[side][2], avoid)
    S.trunks(-17.5, 2 * S.axis + 17.5)
    nrows = len(rows)
    xa, xb = structs.dig_power2(S, DX, DY, nrows, 6.12, -4.0)
    # top plate straps (met5) and ring straps (met4): terminals on pads at the strap bottoms
    for (cx, net) in ((XP + 143.3, "topp"), (XN - 143.3, "topn")):
        top.rect("via4", cx - 0.6, -2.9, cx + 0.6, -1.7); top.rect("metal4", cx - 0.9, -3.1, cx + 0.9, -1.5)
        T[net].append(("m4", (cx, -2.3, 0.9)))
    VSSBAR_X = [XP - 1.1, XP + 153.9, XN + 1.1, XN - 153.9]
    yb0, yb1 = -5.2, -4.0
    xr_end = S.axis * 2 + 13.5
    top.rect("metal4", -13.5, yb0, xr_end, yb1)
    S.block(2, -13.5, yb0, xr_end, yb1)
    for cx in VSSBAR_X: top.rect("metal4", cx - 0.8, yb0, cx + 0.8, -3.0)
    for (a_, b_) in ((-13.5, -10.0), (S.axis * 2 - (-10.0), xr_end)):
        top.rect("metal4", a_, -26.5, b_, yb1)
    for bx in VSSBUS:
        top.rect("metal2", bx - 0.1, -4.6, bx + 0.1, 0.4)
        top.rect("via2", bx - 0.16, -4.76, bx + 0.16, -4.44); top.rect("metal2", bx - 0.16, -4.97, bx + 0.16, -4.23)
        top.rect("via3", bx - 0.16, -4.76, bx + 0.16, -4.44)
        S.block(0, bx - 0.2, -4.97, bx + 0.2, -1.6)
    vb = sorted(VSSBUS)
    for a_, b_ in ((vb[0], vb[1]), (vb[2], vb[3])):
        top.rect("metal3", a_ - 0.33, -4.97, b_ + 0.33, -4.23); S.block(1, a_ - 0.33, -4.97, b_ + 0.33, -4.23)
    return top, T, dict(W=W, H=H, XN=XN, insts=insts, other=other, ports=ports, info=info, rows=rows, ac=ac2, blocks=(cm, tgp, tgn), S=S)
BLOCKVIA = []
VSSBUS = []
M4PADS = []
DRVG = {}
POWER = {"VDDD", "VREFP"}
EXT = {"CLK": (150.0, -40.0), "DV": (360.0, -40.0), "VINP": (110.0, -40.0), "VINN": (340.0, -40.0), "VDDA": (300.0, -40.0)}
def route_all(top, T, d):
    t0 = time.time()
    region_y = max(62.0, 8.05 + len(d["rows"])*6.12 + 4.0)
    R = Router(-10.09, analog.PARAMS.get("routing_ymin", -41.76), 2 * d['S'].axis + 10.09 - 7.0, region_y, 3)
    for (ax1, ax2) in ((-11.0, 164.0), (2 * d['S'].axis - 164.0, 2 * d['S'].axis + 11.0)):
        for kk_ in (0, 1, 2): R.block_rect(kk_, ax1, -1.2, ax2, region_y, margin=-0.3)
    # obstacles: met2 shapes of the analog block
    for blk in d["blocks"]:
        for (inst, kind, W_, L_, nf_, cx, cy, bb) in blk.devs:
            cell = analog.DEVCELLS[f"m_{kind}_w{W_:g}_l{L_:g}_nf{nf_}".replace(".", "p")]
            for lay, rs in cell.layers.items():
                kk = {"metal2": 0, "metal3": 1}.get(lay)
                if kk is None: continue
                for (a, b, c_, d_) in rs: R.block_rect(kk, cx + a / 200, cy + b / 200, cx + c_ / 200, cy + d_ / 200)
    for blk in d["blocks"]:
        for (kk_, a_, b_, c_, d_) in getattr(blk, "keepout", []): R.block_rect(kk_, a_, b_, c_, d_)
    for kk, rs in d['S'].obst.items():
        for (a, b, c_, d_) in rs: R.block_rect(kk, a, b, c_, d_)
    # external pads
    for i in range(11): EXT[f"D{i}"] = (180.0 + 8.0 * i, -40.0)
    for _n, (_x, _y) in EXT.items():
        R.block_rect(1, _x - 0.5, _y - 0.5, _x + 0.5, _y + 0.5); R.block_rect(2, _x - 1.0, _y - 1.0, _x + 1.0, _y + 1.0)
    nets = {}
    for net, lst in T.items():
        if net in POWER: continue
        terms = []
        for k in lst:
            if k[0] == "pin": terms.append(("pin", k[1][0], k[1][1], None))
            elif k[0] == "met2": terms.append(("bus", k[1][0], -1.6, None)); top.rect("metal2", k[1][0] - 0.1, -1.7, k[1][0] + 0.1, 0.4)
            elif k[0] == "m4": terms.append(("m4", k[1][0], k[1][1], k[1][2]))
            elif k[0] == "m3pt": terms.append(("m3pt", k[1][0], k[1][1], None))
            else: terms.append(("rect3" if k[0] == "metal3" else "rect", k[1][0], k[1][1], k[1][2]))
        if net in EXT: terms.append(("ext", EXT[net][0], EXT[net][1], None))
        if len(terms) >= 2: nets[net] = terms
    nid = {n: i for i, n in enumerate(sorted(nets))}
    node_of = {}
    for n, terms in nets.items():
        out = []
        for kind, x, y, rect in terms:
            if kind == "pin": stdplace.pin_stack(top, x, y, R.px(R.gx(x)))
            kl = 1 if kind in ("rect3", "m3pt") else (2 if kind == "m4" else 0)
            i, j = R.gx(x), R.gy(y); out.append((kl, i, j))
            if kind == "m4":
                top.rect("metal4", min(x, R.px(i)) - 0.15, min(y, R.py(j)) - 0.15, max(x, R.px(i)) + 0.15, max(y, R.py(j)) + 0.15)
                M4PADS.append((i, j, rect))
            if kind == "m3pt":
                top.rect("metal3", min(x, R.px(i)) - 0.15, min(y, R.py(j)) - 0.15, max(x, R.px(i)) + 0.15, max(y, R.py(j)) + 0.15)
                BLOCKVIA.append((i, j))
            if kind == "rect3":
                rx1, ry1, rx2, ry2 = rect; R.extra.setdefault(nid[n], []).append(("metal3", rect))
                top.rect("metal3", min(rx1, R.px(i) - 0.15), min(ry1, R.py(j) - 0.15), max(rx2, R.px(i) + 0.15), max(ry2, R.py(j) + 0.15))
                BLOCKVIA.append((i, j))
            if kind in ("bus", "rect") and (abs(R.px(i) - x) > 0.02 or abs(R.py(j) - y) > 0.02):
                top.rect("metal2", min(x, R.px(i)) - 0.1, min(y, R.py(j)) - 0.1, max(x, R.px(i)) + 0.1, max(y, R.py(j)) + 0.1)

        node_of[n] = out
    R.terms = set(x for n in nets for x in node_of[n])
    def apply_blockvia():
        for (i, j) in BLOCKVIA:
            pass
    apply_blockvia()
    pads = []
    for n in nets:
        for kind, x, y, rect in nets[n]:
            if kind == "rect3": pads.append((n, rect))
    FREED = []
    def free_own_margins():
        mg = 0.65
        for n, (rx1, ry1, rx2, ry2) in pads:
            i1, i2 = R.gx(rx1 - mg), R.gx(rx2 + mg); j1, j2 = R.gy(ry1 - mg), R.gy(ry2 + mg)
            for i in range(max(i1, 0), min(i2, R.nx - 1) + 1):
                for j in range(max(j1, 0), min(j2, R.ny - 1) + 1):
                    if R.own[1, i, j] != -2: continue
                    x, y = R.px(i), R.py(j)
                    if not (rx1 - mg < x < rx2 + mg and ry1 - mg < y < ry2 + mg): continue
                    bad = False
                    for m, (a, b, c_, d_) in pads:
                        if m == n: continue
                        if a - mg < x < c_ + mg and b - mg < y < d_ + mg: bad = True; break
                    if not bad: R.own[1, i, j] = nid[n]; FREED.append((i, j, nid[n]))
    free_own_margins()
    def reserve_terms():
        R.contest = True
        for n in nets:
            for (kl, i, j) in node_of[n]:
                R.own[kl, i, j] = nid[n]
        for n in nets:
            for (kl, i, j) in node_of[n]: R._reserve(nid[n], kl, i, j)
        R.contest = False
        for n in nets:
            for (kl, i, j) in node_of[n]:
                if kl == 2:
                    for a in range(-4, 5):
                        for b in range(-3, 4):
                            if 0 <= i + a < R.nx and 0 <= j + b < R.ny and R.own[2, i + a, j + b] == -1: R.own[2, i + a, j + b] = nid[n]
    reserve_terms()
    print('DBG', [[int(R.own[1, R.gx(x), R.gy(yy)]) for x in (121, 122, 122.5, 123, 123.5, 124, 125)] for yy in (-9.8, -9.46, -9.12, -8.78, -8.44)], 'nid VSS', nid.get('VSS'), 'trk', nid.get('trk'))
    def hpwl(n):
        xs = [t[1] for t in nets[n]]; ys = [t[2] for t in nets[n]]; return (max(xs) - min(xs)) + (max(ys) - min(ys))
    order = sorted(nets, key=lambda n: (-1 if n in ('VSS', 'VDDA', 'topp', 'topn') else 0, -len(nets[n]) if len(nets[n]) > 4 else 0, hpwl(n))); fails = []
    for it in range(8):   #  4 -> 8 rip-up iterations
        if it > 0:
            R.own[R.own >= 0] = -1; R.viaown[:] = -1; apply_blockvia()
            for (fi, fj, fn) in FREED: R.own[1, fi, fj] = fn
            reserve_terms()
            R.paths = {}
            order = fails + [n for n in order if n not in fails]
        fails = []
        for n in order:
            terms = [(R.px(i), R.py(j), k) for (k, i, j) in node_of[n]]
            ok = R.route_net(nid[n], n, terms)
            if ok and n in ('topp', 'topn'): R.halo(nid[n], 3)
            if not ok: fails.append(n)
        print("iteration", it, "failed", fails, flush=True)
        if it == 7:
            for n in fails:
                tl = node_of[n]; s = R.reach(nid[n], tl[0])
                if n == "topp":
                    k, i, j = tl[0]
                    print("  TERM0", k, R.px(i), R.py(j))
                    for kk_ in (0, 1, 2):
                        print("   layer", kk_, "own at node", R.own[kk_, i, j], "ok", R._ok(nid[n], kk_, i, j), "viaok", [R._via_ok(nid[n], q, i, j) for q in (0, 1)])
                    print("   layer1 row:", [int(R.own[1, ii, j]) for ii in range(i - 8, i + 9)])
                for (k, i, j) in tl:
                    if (k, i, j) not in s:
                        print("   NODE", k, round(R.px(i), 2), round(R.py(j), 2), [int(R.own[q, i, j]) for q in (0, 1, 2)], "viaok", [R._via_ok(nid[n], q, i, j) for q in (0, 1)], "nbr own L2 col", [int(R.own[2, i, j + d]) for d in (-2, -1, 1, 2)], "L1 row", [int(R.own[1, i + d, j]) for d in (-2, -1, 1, 2)], "L0 col", [int(R.own[0, i, j + d]) for d in (-2, -1, 1, 2)])
                print("  UNREACHED", n, [(round(R.px(i), 2), round(R.py(j), 2), k) for (k, i, j) in tl if (k, i, j) not in s])
                print("  REACH", n, "from first terminal:", len(s), "nodes; terminals reached:", sum(1 for x in tl if x in s), "of", len(tl))
        if not fails: break
    for n in fails:
        for (k, i, j) in node_of[n]:
            print("  fail", n, "term", round(R.px(i), 2), round(R.py(j), 2), "own", R.own[k, i, j], "nid", nid[n], "nbrs", [int(R.own[k, min(max(i + a, 0), R.nx - 1), min(max(j + b, 0), R.ny - 1)]) for a, b in ((1,0),(-1,0),(0,1),(0,-1))])
    print("routed", len(nets) - len(fails), "of", len(nets), "failed:", fails, "time", round(time.time() - t0, 1))
    occ = {}
    for net, plist in R.paths.items():
        for p in plist:
            for (k, i, j) in p: occ.setdefault((k, i, j), set()).add(net)
    bad = 0
    for (k, i, j), ns in occ.items():
        if len(ns) > 1: bad += 1; print("  SHARED node", k, R.px(i), R.py(j), [R.names[n] for n in ns])
        for di, dj in ((1, 0), (0, 1)):
            o = occ.get((k, i + di, j + dj))
            if o and (o - ns) and (ns - o):
                bad += 1
                if bad < 30: print("  ADJ", k, round(R.px(i), 2), round(R.py(j), 2), [R.names[n] for n in ns], [R.names[n] for n in o])
    print("adjacent/shared violations:", bad)
    for (k, i, j), ns in sorted(occ.items()):
        if 388.5 < R.px(i) < 390.6 and R.py(j) > -3: print("  NODE", k, round(R.px(i), 2), round(R.py(j), 2), [R.names[n] for n in ns])
    R.emit(top)
    # IO pads
    for net, (x, y) in EXT.items():
        if net not in nets: continue
        i, j = R.gx(x), R.gy(y); xx, yy = R.px(i), R.py(j)
        top.rect("via2", xx - 0.16, yy - 0.16, xx + 0.16, yy + 0.16); top.rect("metal2", xx - 0.16, yy - 0.21, xx + 0.16, yy + 0.21)
        top.rect("metal3", xx - 0.5, yy - 0.5, xx + 0.5, yy + 0.5); top.rect("via3", xx - 0.16, yy - 0.16, xx + 0.16, yy + 0.16)
        top.rect("metal4", xx - 1.0, yy - 1.0, xx + 1.0, yy + 1.0)
        top.label(net, "metal4", xx - 0.5, yy - 0.5, xx + 0.5, yy + 0.5)
    for (name, lay, a, b, c_, d_) in d["S"].labels: top.label(name, lay, a, b, c_, d_)
    return R, fails
if __name__ == "__main__":
    top, T, d = build()
    R, fails = route_all(top, T, d)
    top.write(CELLS)
    print("written")
