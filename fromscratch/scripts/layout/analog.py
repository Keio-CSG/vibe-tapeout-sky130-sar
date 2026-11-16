"""Comparator and sampling-switch device placement (flat; routed by the top-level router)."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from maglib import Cell
import devlib
CELLS = devlib.CELLS
DEVCELLS = {}
PARAMS = json.load(open(os.path.join(os.path.dirname(__file__), "..", "p_M3.json")))
def _mk(kind, W, L, nf, frame_W=None, frame_ref=None):
    c, pins, bbox = devlib.mos(kind, W, L, nf, frame_W=frame_W, frame_ref=frame_ref); c.write(CELLS); DEVCELLS[c.name] = c; return c.name, pins, bbox
class Block:
    def __init__(self, c, x0, y0):
        self.c, self.x, self.y = c, x0, y0; self.terms = {}; self.devs = []; self.xmax = x0
    def add(self, inst, kind, W, L, nf, nets, gap=4.4, flipy=False, frame_W=None, inactive=False, frame_ref=None):
        """nets: dict S,D,G,B -> net name. Places the device with its left bbox edge at self.xmax+gap."""
        name, pins, bbox = _mk(kind, W, L, nf, frame_W=frame_W, frame_ref=frame_ref)
        if inactive:
            # Keep the external metal interface and placement reservation while
            # removing the dummy transistor and its well/active/contact geometry.
            from collections import defaultdict
            cell = DEVCELLS[name]
            cell.uses = []
            cell.layers = defaultdict(list, {k:v for k,v in cell.layers.items() if k in ("metal2", "metal3", "via2")})
            cell.write(CELLS)
        cx = self.xmax + gap - bbox[0]; cy = self.y
        self.c.use(name, inst, cx, cy, "R0")
        for p, net in nets.items():
            lay, (x1, y1, x2, y2) = pins[p]
            self.terms.setdefault(net, []).append((lay, (cx + x1, cy + y1, cx + x2, cy + y2), f"{inst}.{p}"))
        self.xmax = cx + bbox[2]; self.devs.append((inst, kind, W, L, nf, cx, cy, bbox))
        return cx
def comparator(c, x0, y0, nets):
    """nets: dict with keys ck inp inn oa ob VDD VSS ; internal t xa xb"""
    b = Block(c, x0, y0); n = nets
    f = lambda **k: k
    b.add("cm_tail", "n", 4, 0.15, 1, f(S=n["VSS"], D="t", G=n["ck"], B=n["VSS"]), gap=3.0)
    b.add("cm_ina", "n", 5, 0.15, 1, f(S="t", D="xa", G=n["inp"], B=n["VSS"]), gap=3.0)
    b.add("cm_inb", "n", 5, 0.15, 1, f(S="t", D="xb", G=n["inn"], B=n["VSS"]))
    b.add("cm_lna", "n", 2, 0.15, 1, f(S="xa", D=n["oa"], G=n["ob"], B=n["VSS"]))
    b.add("cm_lnb", "n", 2, 0.15, 1, f(S="xb", D=n["ob"], G=n["oa"], B=n["VSS"]))
    for nm, dnet, gnet, w in (("lpa", n["oa"], n["ob"], 4), ("lpb", n["ob"], n["oa"], 4), ("ra", n["oa"], n["ck"], 2), ("rb", n["ob"], n["ck"], 2), ("rxa", "xa", n["ck"], 2), ("rxb", "xb", n["ck"], 2)):
        b.add("cm_" + nm, "p", w, 0.15, 1, f(S=n["VDD"], D=dnet, G=gnet, B=n["VDD"]), gap=3.6)
    return b
def tgswitch(c, x0, y0, nets, tag):
    """nets: a(b in schematic naming: a=input, b=top plate) g gb VDDA VSS"""
    b = Block(c, x0, y0); n = nets
    b.add(f"{tag}_n", "nl", PARAMS["sw_wn"]/8, 0.15, 8, dict(S=n["a"], D=n["b"], G=n["g"], B=n["VSS"]), gap=4.4, frame_W=PARAMS.get("sampling_frame_w"))
    b.add(f"{tag}_dn", "nl" if PARAMS.get("sw_dummy_n_match",PARAMS.get("sw_dummy_match",0)) else "n", PARAMS["sw_wn"]/8*PARAMS.get("sw_dummy_n_scale",1), 0.15, 4, dict(S=n["b"], D=n["b"], G=n["gb"], B=n["VSS"]), gap=4.4, frame_W=PARAMS.get("sampling_frame_w"), inactive=not PARAMS.get("sw_dummy",1))
    b.add(f"{tag}_p", "pl", PARAMS["sw_wp"]/16, 0.35, 16, dict(S=n["a"], D=n["b"], G=n["gb"], B=n["VDDA"]), gap=5.0, frame_W=PARAMS.get("sampling_frame_w"))
    b.add(f"{tag}_dp", "pl" if PARAMS.get("sw_dummy_p_match",PARAMS.get("sw_dummy_match",0)) else "p", PARAMS["sw_wp"]/16*PARAMS.get("sw_dummy_p_scale",1), 0.35 if PARAMS.get("sw_dummy_p_match",PARAMS.get("sw_dummy_match",0)) else 0.15, 8, dict(S=n["b"], D=n["b"], G=n.get("gp",n["g"]), B=n["VDDA"]), gap=5.0, frame_W=PARAMS.get("sampling_frame_w"), inactive=not PARAMS.get("sw_dummy",1), frame_ref=("p",4,.15,8) if PARAMS.get("sampling_dummy_p_frame",0) else None)
    return b
if __name__ == "__main__":
    c = Cell("analog_test")
    cm = comparator(c, 0, 0, dict(ck="ck", inp="topp", inn="topn", oa="oa", ob="ob", VDD="VDDA", VSS="VSS"))
    tg = tgswitch(c, 0, -20, dict(a="VINP", b="topp", g="trk", gb="trkb", VDDA="VDDA", VSS="VSS"), "tgp")
    c.write(CELLS); print(cm.xmax, tg.xmax)

# ---------------------------------------------------------------------------------------------------------------
#  mirror-symmetric comparator block with local low-threshold detectors (nor3, VDDA).
# Root cause of the post-layout SNDR loss: the routed comparator had asymmetric parasitics on oa/ob and xa/xb (long
# oa/ob wires to the nor3 detectors in the logic block), which gives an offset that depends on the input common mode
# (+2 mV at 0.9 V -> -35 mV at 1.79 V; the common mode rises during the monotonic conversion), i.e. a different
# threshold for every bit.  Here half A (x < axis) is drawn once and mirrored exactly to half B; all internal nets are
# hand-wired; oa/ob only reach local devices; the cross-coupled pair crosses the axis with one symmetric crossing.
def flat_copy(dst, cellname, dx, dy):
    """paint of a .mag cell (recursively, R0/identity-transform subcells only) copied into dst at (dx,dy) um"""
    import re as _re
    ox, oy = int(round(dx * 200)), int(round(dy * 200))
    txt = open(os.path.join(CELLS, cellname + ".mag")).read().split("\n"); lay = None; i = 0
    while i < len(txt):
        l = txt[i]
        if l.startswith("<< "):
            lay = l[3:-3].strip(); lay = None if lay in ("checkpaint", "properties", "labels", "end") else lay
        elif l.startswith("rect ") and lay:
            a, b, c_, d_ = map(int, l.split()[1:5]); dst.layers[lay].append((a + ox, b + oy, c_ + ox, d_ + oy))
        elif l.startswith("use "):
            sub = l.split()[1]; tr = [t for t in txt[i:i + 4] if t.startswith("transform")][0].split()[1:]
            assert tr[0] == "1" and tr[1] == "0" and tr[3] == "0" and tr[4] == "1", (cellname, tr)
            flat_copy(dst, sub, dx + int(tr[2]) / 200, dy + int(tr[5]) / 200)
        i += 1
class SymBlock:
    def __init__(self): self.terms = {}; self.devs = []; self.keepout = []; self.xmax = 0
def comparator_sym(c, X0, Y0, nets=None, CH=5.0, one_input=False):
    """Half A at x < X0, half B its exact mirror (MY).  CH: half-width of a central routing channel (the router may
    cross the block there on met2/met4 only; every vertical there crosses both cross-coupling lines -> symmetric).
    Order from the axis outward: detector (tap + nor3_1 on VDDA), tail/2, in, ln, lp, r, rx."""
    import stdplace
    n = dict(ck="ck", inp="topp", inn="topn", VDD="VDDA", VSS="VSS", ya="ia_d", yb="ib_d")
    if nets: n.update(nets)
    blk = SymBlock()
    h = Cell("cmp_half")                       # half A in local coordinates (axis x=0); B = the same cell mirrored
    def R(lay, x1, y1, x2, y2, mirror=True):
        if mirror: h.rect(lay, x1, y1, x2, y2)
        else: c.rect(lay, X0 + x1, Y0 + y1, X0 + x2, Y0 + y2)
    def m3pad(x, y, mirror=True): R("metal3", x - 0.33, y - 0.21, x + 0.33, y + 0.21, mirror)
    def v3(x, y, mirror=True):
        R("via3", x - 0.16, y - 0.16, x + 0.16, y + 0.16, mirror); m3pad(x, y, mirror); R("metal4", x - 0.33, y - 0.33, x + 0.33, y + 0.33, mirror)
    def m4v(x, y1, y2, mirror=True):          # met4 vertical with via3 + pads at both ends
        lo, hi = min(y1, y2), max(y1, y2); R("metal4", x - 0.17, lo, x + 0.17, hi, mirror); v3(x, y1, mirror); v3(x, y2, mirror)
    def m3h(y, x1, x2, w=0.3, mirror=True):
        lo, hi = min(x1, x2), max(x1, x2); R("metal3", lo - 0.33, y - w / 2, hi + 0.33, y + w / 2, mirror)
    a, b = CH + 2.0, CH + 1.0                  # crossing columns (|x|)
    # ---- detector: nor3_1 + tap on VDDA, rails y=+-1.36.
    # In one_input mode only A senses oa; B/C are grounded below.
    xn = -(CH + 6.8); yr = -1.36
    nor = stdplace.ensure("nor3_1", "ana"); tap = stdplace.ensure("tapvpwrvgnd_1", "ana")
    h.use(nor, "Xnd", xn, yr, "R0"); h.use(tap, "cs_tap", xn + 1.84, yr, "R0")
    pa = (xn + 1.615, yr + 0.85); pb = (xn + 0.695, yr + 1.53); pc = (xn + 0.235, yr + 1.19); py = (xn + 0.235, yr + 2.21)
    for (x, y) in (pa, pb, pc):
        R("viali", x - 0.085, y - 0.085, x + 0.085, y + 0.085); R("metal1", x - 0.16, y - 0.13, x + 0.16, y + 0.13)
    R("viali", py[0] - 0.085, py[1] - 0.085, py[0] + 0.085, py[1] + 0.085)
    pys = (py[0], yr + 1.72)                   # Y via stack moved down, away from the VPWR rail
    R("metal1", py[0] - 0.145, pys[1] - 0.16, py[0] + 0.145, py[1] + 0.115)
    R("metal1", pc[0] - 0.16, pc[1] - 0.13, pb[0] + 0.16, pc[1] + 0.13)          # C -> B (met1, L-shapes, no notches)
    R("metal1", pb[0] - 0.16, pc[1] - 0.13, pb[0] + 0.16, pb[1] + 0.13)
    if one_input:
        # A senses the latch; B/C join the existing VGND rail.
        # This reduces detector input loading while retaining the NOR3 cell.
        R("metal1", pb[0] - 0.16, yr, pb[0] + 0.16, pb[1] + 0.13)
    else:
        R("metal1", pb[0] - 0.16, pb[1] - 0.13, pa[0] + 0.16, pb[1] + 0.13)      # B -> A
        R("metal1", pa[0] - 0.16, pa[1] - 0.16, pa[0] + 0.16, pb[1] + 0.13)
    def stack12(x, y):                         # via1 + met1/met2 pads + via2 (met3 pad by v3)
        R("via1", x - 0.13, y - 0.13, x + 0.13, y + 0.13); R("metal1", x - 0.16, y - 0.16, x + 0.16, y + 0.16)
        R("metal2", x - 0.21, y - 0.21, x + 0.21, y + 0.21); R("via2", x - 0.16, y - 0.16, x + 0.16, y + 0.16)
    stack12(*pa); stack12(*pys)
    xg, xp = xn + 2.64, xn + 3.64              # VGND / VPWR rail taps (rails extended toward the axis)
    R("metal1", xn + 1.84, yr - 0.24, xg + 0.35, yr + 0.24); R("metal1", xn + 1.84, -yr - 0.24, xp + 0.35, -yr + 0.24)
    stack12(xg, yr); stack12(xp, -yr)
    # ---- devices (half A), mirrored copies (MY) for half B
    devs = [("tail", "n", 2, 0.0), ("in", "n", PARAMS.get("c_win",5), 5.6), ("ln", "n", 2, 5.6), ("lp", "p", 4, 4.6), ("r", "p", 2, 4.6), ("rx", "p", 2, 4.6)]
    P = {}; CX = {}; cx = xn - 2.8
    for (nm, kind, W, dp) in devs:
        cx -= dp; CX[nm] = cx
        name, pins, bbox = _mk(kind, W, 0.15, 1)
        flat_copy(h, name, cx, 0.0)            # flattened: devices + wiring in one cell -> identical extraction of A and B
        P[nm] = {p: (cx + (r[0] + r[2]) / 2, (r[1] + r[3]) / 2) for p, (lay, r) in pins.items()}
    # ---- tracks (half A; shared nets continue to the axis and merge with the mirror)
    yT = dict(g=4.0, xa=4.8, t=5.6, ck=6.4, vss=7.4, vdd=8.6); yB = dict(o=-3.0, xa=-3.8, t=-4.6); yTerm = 10.6
    xlt = (CX["tail"] + CX["in"]) / 2; xlx = (CX["in"] + CX["ln"]) / 2      # link columns (gap centres)
    conn = [("tail", "S", "vss"), ("tail", "B", "vss"), ("in", "B", "vss"), ("ln", "B", "vss"),
            ("lp", "S", "vdd"), ("lp", "B", "vdd"), ("r", "S", "vdd"), ("r", "B", "vdd"), ("rx", "S", "vdd"), ("rx", "B", "vdd"),
            ("tail", "G", "ck"), ("r", "G", "ck"), ("rx", "G", "ck"),
            ("ln", "G", "g"), ("lp", "G", "g"), ("ln", "S", "xa"), ("in", "S", "t")]
    connb = [("ln", "D", "o"), ("lp", "D", "o"), ("r", "D", "o"), ("in", "D", "xa"), ("rx", "D", "xa"), ("tail", "D", "t")]
    for d, p, tr in conn:
        x, y = P[d][p]; m4v(x, y, yT[tr])
    for d, p, tr in connb:
        x, y = P[d][p]; m4v(x, y, yB[tr])
    m4v(xg, yr, yT["vss"]); m4v(xp, -yr, yT["vdd"]); m4v(pa[0], pa[1], yB["o"])
    m4v(xlx, yB["xa"], yT["xa"]); m4v(xlt, yB["t"], yT["t"])     # links
    xs = lambda tr, lst, extra=(): [P[d][p][0] for d, p, t_ in lst if t_ == tr] + list(extra)
    m3h(yT["vss"], min(xs("vss", conn)), 0.0, w=0.8); m3h(yT["vdd"], min(xs("vdd", conn)), 0.0, w=0.8)
    m3h(yT["ck"], min(xs("ck", conn)), 0.0); m3h(yB["t"], xlt, 0.0)
    m3h(yT["g"], min(xs("g", conn)), -b); m3h(yT["xa"], min(xs("xa", conn)), xlx); m3h(yT["t"], min(xs("t", conn)), xlt)
    m3h(yB["o"], min(xs("o", connb)), -a); m3h(yB["xa"], min(xs("xa", connb)), max(xs("xa", connb)))
    # ---- cross-coupling across the axis (one crossing): oa (A output) -> gates of B ; ob mirrored
    # twisted pair: each net runs at y1 on its own side and at y2 on the other side (mirror-symmetric); the two swap
    # levels at the axis: oa bridges on met4 (Z over |x| <= d), ob stays on met3 (Z through x = 0).
    y1, y2, d = 0.4, -0.4, 0.8
    m4v(-a, yB["o"], y1, mirror=False); m3h(y1, -a, -d, mirror=False); v3(-d, y1, False)          # oa
    R("metal4", -d - 0.17, -0.17, -d + 0.17, y1, False); R("metal4", -d - 0.17, -0.17, d + 0.17, 0.17, False)
    R("metal4", d - 0.17, y2, d + 0.17, 0.17, False); v3(d, y2, False); m3h(y2, d, b, mirror=False); m4v(b, y2, yT["g"], mirror=False)
    m4v(a, yB["o"], y1, mirror=False); R("metal3", -0.15, y1 - 0.15, a + 0.33, y1 + 0.15, False)   # ob
    R("metal3", -0.15, y2 - 0.15, 0.15, y1 + 0.15, False); R("metal3", -b - 0.33, y2 - 0.15, 0.15, y2 + 0.15, False)
    m4v(-b, y2, yT["g"], mirror=False)
    # ---- external terminals (met3 pads at yTerm): inputs, detector outputs, ck, supplies
    x_in = P["in"]["G"]; m4v(x_in[0], x_in[1], yTerm); m4v(pys[0], pys[1], yTerm)
    xvdd = -14.0
    m4v(-b, yT["ck"], yTerm, mirror=False); m4v(b, yT["vss"], yTerm, mirror=False); m4v(xvdd, yT["vdd"], yTerm, mirror=False)
    def term(net, x):
        r = (X0 + x - 0.33, Y0 + yTerm - 0.21, X0 + x + 0.33, Y0 + yTerm + 0.21); blk.terms.setdefault(net, []).append(("metal3", r, net))
    term(n["inp"], x_in[0]); term(n["inn"], -x_in[0]); term(n["ya"], pys[0]); term(n["yb"], -pys[0])
    term(n["ck"], -b); term(n["VSS"], b); term(n["VDD"], xvdd)
    # net-name labels (not ports) on the internal nodes, for probing the extracted netlist
    lx = (min(xs("o", connb)) + (-a)) / 2
    h.label("o", "metal3", lx - 0.1, yB["o"] - 0.1, lx + 0.1, yB["o"] + 0.1, port=False)
    h.label("x", "metal3", xlx - 1.0, yB["xa"] - 0.1, xlx - 0.8, yB["xa"] + 0.1, port=False)
    # two identical defs (A: R0, B: MY): magic's ext2spice attributes junction areas differently to the second instance
    # of one def (node total to the first device, 0 to the others), which BSIM turns into a perimeter asymmetry
    h.name = "cmp_half_a"; h.write(CELLS); h.name = "cmp_half_b"; h.write(CELLS)
    c.use("cmp_half_a", "cmpA", X0, Y0, "R0"); c.use("cmp_half_b", "cmpB", X0, Y0, "MY")
    xe = CX["rx"] - 2.12 - 0.6; yb0 = Y0 + yB["t"] - 0.8
    yk = Y0 + 9.3
    blk.keepout = [(1, X0 + xe, yb0, X0 - xe, yk)] + [(k, X0 + xe, yb0, X0 - CH, yk) for k in (0, 2)] + \
                  [(k, X0 + CH, yb0, X0 - xe, yk) for k in (0, 2)] + [(k, X0 - 1.2, yb0, X0 + 1.2, yk) for k in (0, 2)]
    # CP-B: grounded met2 shield under the lighter B-side output.
    # Join its existing VGND pad; stay inside the comparator routing keepout.
    # Ground loading avoids adding signal-dependent coupling to x/t nodes.
    R("metal2", -xg - 0.10, yB["o"] - 0.10, -xg + 0.10, yr, mirror=False)
    shield_w = float(PARAMS.get("cmp_shield_w", 0.20))
    assert 0.20 <= shield_w <= 0.60
    R("metal2", -xg - 0.10, -3.0 - shield_w / 2, 18.65, -3.0 + shield_w / 2, mirror=False)
    # Jog below the input transistor's bottom gate strap at x=19.1..20.41.
    R("metal2", 18.45, -3.35, 18.65, -2.90, mirror=False)
    R("metal2", 18.45, -3.35, 21.10, -3.15, mirror=False)
    R("metal2", 20.90, -3.35, 21.10, -2.90, mirror=False)
    R("metal2", 20.90, -3.0 - shield_w / 2, 22.60, -3.0 + shield_w / 2, mirror=False)
    for net, lst in blk.terms.items():           # met4 terminal verticals above the keepout: keep router met4 away
        for (lay, (x1, y1_, x2, y2_), nm) in lst: blk.keepout.append((2, (x1 + x2) / 2 - 0.35, Y0 + 8.9, (x1 + x2) / 2 + 0.35, Y0 + yTerm - 0.45))
    blk.xmax = X0 - xe; blk.bbox = (X0 + xe, yb0, X0 - xe, Y0 + yTerm + 0.4)
    return blk
