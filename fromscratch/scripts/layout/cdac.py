"""Common-centroid CDAC array generator (one side). Units: um."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from maglib import Cell
PARAMS = json.load(open(os.path.join(os.path.dirname(__file__), "..", "p_M3.json")))
PX, PY = PARAMS.get("cdac_pitch_x",4.5), PARAMS.get("cdac_pitch_y",4.9)
CAP = PARAMS["cu_w"]
CAP_L = PARAMS.get("cu_l",CAP)
NETS = ["b9","b8","b7","b6","b5","b4","b3","b2","b1","b0","vrefn","vss"]   # track order (bottom->top within a row)
TRK_W, TRK_P, TRK_Y0 = 0.26, 0.4, 0.0   # met1 track width, pitch, first track y offset in site
BUS_P = 0.69
def assignment():
    """32x32 common-centroid map: returns dict (row,col)->net for the 32x32 core (row 0 = bottom). 4-fold orbit symmetric."""
    orbits = []
    for a in range(16):
        for b in range(16):
            orbits.append((a + 0.5, b + 0.5))
    central = (0.5, 0.5)
    rest = sorted([o for o in orbits if o != central], key=lambda o: (o[0]**2 + o[1]**2, o[0], o[1]))
    amap = {}
    for r, o in enumerate(rest, start=1):
        tz = (r & -r).bit_length() - 1
        bit = 9 - tz               # tz 0 -> b9 ... tz 7 -> b2
        for sx in (-1, 1):
            for sy in (-1, 1):
                amap[(sx * o[0], sy * o[1])] = f"b{bit}"
    # central orbit: bit1 on one diagonal, bit0 + dummy on the other
    amap[(0.5, 0.5)] = "b1"; amap[(-0.5, -0.5)] = "b1"
    amap[(0.5, -0.5)] = "b0"; amap[(-0.5, 0.5)] = "vrefn"
    return amap
def build(name, out_dir, amap=None, nrow=32, ncol=32, ring=True, mirror=False, side='p'):
    """Returns (cell, info). Site (ir,ic) of the full (nrow+2)x(ncol+2) grid including the ring. mirror: buses on the right."""
    c = Cell(name)
    full_r, full_c = nrow + 2 * ring, ncol + 2 * ring
    off = 1 if ring else 0
    def net_of(ir, ic):
        if ring and (ir in (0, full_r - 1) or ic in (0, full_c - 1)): return "vss"
        x = ic - off - (ncol - 1) / 2.0; y = ir - off - (nrow - 1) / 2.0
        return amap[(x, y)]
    ntr = len(NETS); xbus0 = -(ntr + 1) * BUS_P - 1.0     # buses left of the array
    rowtracks = {}
    for ir in range(full_r):
        y0 = ir * PY
        used = {}
        for ic in range(full_c):
            x0 = ic * PX; n = net_of(ir, ic)
            xc = x0 + 1.64
            # capacitor
            c.rect("mimcap", x0 + 0.14, y0 + 0.54, x0 + CAP + 0.14, y0 + CAP_L + 0.54)
            c.rect("mimcapcontact", x0 + 0.34, y0 + 0.74, x0 + CAP - 0.06, y0 + CAP_L + 0.34)
            c.rect("metal3", x0, y0, x0 + CAP + 0.28, y0 + CAP_L + 0.68)
            c.rect("via2", xc - 0.16, y0 + 0.04, xc + 0.16, y0 + 0.36)
            k = NETS.index(n); yk = y0 + TRK_Y0 + 0.25 + k * TRK_P
            # met2 stub from via2 to via1 at track
            c.rect("metal2", xc - 0.21, y0 + 0.02, xc + 0.21, y0 + 0.38)       # pad over via2
            c.rect("metal2", xc - 0.1, y0 + 0.02, xc + 0.1, yk + 0.13)
            c.rect("metal2", xc - 0.21, yk - 0.13, xc + 0.21, yk + 0.13)       # pad over via1
            c.rect("via1", xc - 0.13, yk - 0.13, xc + 0.13, yk + 0.13)
            used.setdefault(n, []).append(xc)
        # row tracks
        for n, xs in used.items():
            k = NETS.index(n); yk = y0 + TRK_Y0 + 0.25 + k * TRK_P
            xb = xbus0 + k * BUS_P
            c.rect("metal1", xb - 0.21, yk - TRK_W / 2, max(xs) + 0.25, yk + TRK_W / 2)
            c.rect("via1", xb - 0.13, yk - 0.13, xb + 0.13, yk + 0.13)
            c.rect("metal2", xb - 0.21, yk - 0.13, xb + 0.21, yk + 0.13)
        rowtracks[ir] = used
        # top-plate bar (met4): active cells -> one bar; ring cells -> separate (VSS) pads/bars
        act = [ic for ic in range(full_c) if net_of(ir, ic) != "vss"]
        if act:
            c.rect("metal4", min(act) * PX + 0.34, y0 + 0.64, max(act) * PX + CAP + 0.04, y0 + CAP_L + 0.44)
        if ring and ir in (0, full_r - 1):
            c.rect("metal4", 0.24, y0 + 0.64, (full_c - 1) * PX + CAP + 0.04, y0 + CAP_L + 0.44)
        else:
            for ic in range(full_c):
                if net_of(ir, ic) == "vss":
                    c.rect("metal4", ic * PX + 0.24, y0 + 0.64, ic * PX + CAP + 0.04, y0 + CAP_L + 0.44)
    # top-plate collector: met5 strap over the last active column, via4 from every active row bar; ring VSS straps (met4)
    xs5 = (off + ncol - 2) * PX + 3.2
    for ir in range(off, off + nrow):
        y0 = ir * PY
        c.rect("via4", xs5, y0 + 0.9, xs5 + 1.2, y0 + 2.1)
    c.rect("metal5", xs5 - 0.2, -3.2, xs5 + 1.4, full_r * PY + 1.5)
    c.label("top" + side, "metal5", xs5, 1.0, xs5 + 1.0, 2.0)
    xl, xr = -1.9, full_c * PX + 0.1
    for xx in (xl, xr):
        c.rect("metal4", xx, -3.2, xx + 1.6, full_r * PY + 0.5)
    for ir in range(full_r):
        y0 = ir * PY
        if True:
            c.rect("metal4", xl, y0 + 0.64, 0.24 + 0.0, y0 + CAP_L + 0.44)           # left ring column pad -> strap
            c.rect("metal4", (full_c - 1) * PX + CAP + 0.04, y0 + 0.64, xr + 0.0, y0 + CAP_L + 0.44)
    c.label("vssring" + side, "metal4", xl, 5.0, xl + 1.0, 6.0)
    # vertical buses
    ytop = full_r * PY
    for k, n in enumerate(NETS):
        xb = xbus0 + k * BUS_P
        bus_w = float(PARAMS.get("cdac_bus_widths", {}).get(n, 0.20))
        assert 0.20 <= bus_w <= 0.50
        c.rect("metal2", xb - bus_w / 2, 0.0, xb + bus_w / 2, ytop)
        if n == 'b9' and PARAMS.get('cdac_msb_m3', 0):
            # Parallel MSB conductor outside the array; connect at each row.
            # Preserve the original met2 terminal and every unit-cap access.
            strap_w = float(PARAMS.get('cdac_msb_m3_width', 1.0))
            c.rect('metal3', xb - strap_w / 2, 0.0, xb + strap_w / 2, ytop)
            for ir in range(full_r):
                yy = ir * PY + TRK_Y0 + 0.25
                c.rect('via2', xb - 0.16, yy - 0.16, xb + 0.16, yy + 0.16)
                c.rect('metal3', xb - .23, yy - .28, xb + .23, yy + .28)
        if n == 'b8' and PARAMS.get('cdac_b8_m4', 0):
            c.rect('metal4', xb - .50, 0.0, xb + .50, ytop)
            for ir in range(full_r):
                yy = ir * PY + 1.35
                c.rect('metal2', xb - .23, yy - .23, xb + .23, yy + .23)
                c.rect('via2', xb - .16, yy - .16, xb + .16, yy + .16)
                c.rect('metal3', xb - .23, yy - .28, xb + .23, yy + .28)
                c.rect('via3', xb - .16, yy - .16, xb + .16, yy + .16)
        c.label({"vrefn": "VSS", "vss": "VSS"}.get(n, "bot" + side + n[1:]), "metal2", xb - 0.1, 2.0, xb + 0.1, 3.0)
    return c, dict(xbus0=xbus0, nrow=full_r, ncol=full_c, w=full_c * PX, h=full_r * PY)
if __name__ == "__main__":
    a = assignment()
    from collections import Counter
    cnt = Counter(a.values()); print(sorted(cnt.items()), sum(cnt.values()))
    # centroid check
    for n in sorted(cnt):
        xs = [k[0] for k, v in a.items() if v == n]; ys = [k[1] for k, v in a.items() if v == n]
        print(n, round(sum(xs) / len(xs), 3), round(sum(ys) / len(ys), 3), end=" | ")
    print()
    c, info = build("cdac_test", ".", a, nrow=32, ncol=32)
    c.write("."); print(info)
