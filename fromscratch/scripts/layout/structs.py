"""Explicit power / strap / pad structures of the macro (global coordinates, um)."""
TR = {"VREFP": (-47.5, -44.0), "VSS": (-53.0, -49.5)}
M = {1: "metal1", 2: "metal2", 3: "metal3", 4: "metal4", 5: "metal5"}
def via_stack(c, x, y, k0, k1, pad=None):
    """vias from metal k0 up to k1 at (x,y); pad = (hx,hy) landing pads per metal (default 0.21/0.33)."""
    for k in range(k0, k1):
        if k == 1: c.rect("via1", x - 0.13, y - 0.13, x + 0.13, y + 0.13)
        elif k in (2, 3): c.rect("via%d" % k, x - 0.16, y - 0.16, x + 0.16, y + 0.16)
        elif k == 4: c.rect("via4", x - 0.6, y - 0.6, x + 0.6, y + 0.6)
    for k in range(k0, k1 + 1):
        hx, hy = {1: (0.2, 0.2), 2: (0.21, 0.21), 3: (0.33, 0.21), 4: (0.33, 0.33), 5: (0.8, 0.8)}[k] if pad is None else pad[k]
        c.rect(M[k], x - hx, y - hy, x + hx, y + hy)
def via_array(c, k, x1, y1, x2, y2, size=None, pitch=None):
    """fill rect with via cuts of layer k->k+1 (k=3: via3, 4: via4, 2: via2)"""
    s, p = {2: (0.32, 0.52), 3: (0.32, 0.52), 4: (1.2, 2.0)}[k]
    nx = max(int((x2 - x1 - 0.2) // p), 1) if k != 4 else max(int((x2 - x1) // p), 1)
    ny = max(int((y2 - y1 - 0.2) // p), 1) if k != 4 else max(int((y2 - y1) // p), 1)
    xc, yc = (x1 + x2) / 2, (y1 + y2) / 2
    for i in range(nx):
        for j in range(ny):
            cx = xc + (i - (nx - 1) / 2) * p; cy = yc + (j - (ny - 1) / 2) * p
            c.rect("via%d" % k, cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2)
def mirror(x, axis): return 2 * axis - x
class Struct:
    def __init__(self, c, axis): self.c = c; self.axis = axis; self.obst = {0: [], 1: [], 2: []}; self.labels = []
    def block(self, k, x1, y1, x2, y2): self.obst[k].append((x1, y1, x2, y2))
    def driver_power(self, side, x0, x1, oy, avoid=()):
        """VREFP strap above and VSS strap below a single driver row (R0) at oy; ribs left (P) / right (N) of the macro."""
        c = self.c; ax = self.axis
        rf = (-17.5, -14.0); rv = (-13.5, -10.0)          # P ribs: VREFP, VSS (x ranges, 3.5 wide)
        if side == "n": rf = (mirror(rf[1], ax), mirror(rf[0], ax)); rv = (mirror(rv[1], ax), mirror(rv[0], ax))
        yv = oy + 2.72
        sp = (yv + 0.9, yv + 3.9); sb = (oy - 3.9 + 0.0, oy - 0.9)         # straps (met3) 3.0 tall
        for (net, strap, rib, yr) in (("VREFP", sp, rf, yv), ("VSS", sb, rv, oy)):
            xa, xb = (min(x0, rib[0]), max(x1, rib[1])) if True else None
            c.rect("metal3", xa, strap[0], xb, strap[1]); self.block(1, xa, strap[0], xb, strap[1])
            # via3 array strap->rib
            via_array(c, 3, rib[0], strap[0], rib[1], strap[1])
            # rail stubs every 8 um
            x = x0 + 2.0
            while x < x1 - 1.0:
                while any(abs(px - x) < 0.9 for px in avoid): x += 0.23
                c.rect("metal1", x - 0.3, yr - 0.24, x + 0.3, yr + 0.24)
                c.rect("via1", x - 0.13, yr - 0.13, x + 0.13, yr + 0.13)
                ys = (strap[0] + strap[1]) / 2
                c.rect("metal2", x - 0.21, min(yr, ys) - 0.21, x + 0.21, max(yr, ys) + 0.21); self.block(0, x - 0.2, min(yr, ys), x + 0.2, max(yr, ys))
                c.rect("via2", x - 0.16, ys - 0.16, x + 0.16, ys + 0.16)
                c.rect("metal3", x - 0.33, ys - 0.21, x + 0.33, ys + 0.21)
                x += 8.0
            # rib (met4) from strap down to trunk
            ytr = {"VREFP": TR["VREFP"], "VSS": TR["VSS"]}[net]
            c.rect("metal4", rib[0], ytr[0], rib[1], strap[1]); self.block(2, rib[0], ytr[0], rib[1], strap[1])
            via_array(c, 4, rib[0], ytr[0], rib[1], ytr[1])
        return rf, rv
    def trunks(self, xl, xr):
        c = self.c
        for net, (y0, y1) in (("VREFP", TR["VREFP"]), ("VSS", TR["VSS"])):
            c.rect("metal5", xl, y0, xr, y1); self.labels.append((net, "metal5", (xl + xr) / 2 - 1.0, y0 + 0.5, (xl + xr) / 2 + 1.0, y0 + 2.5))
    def dig_power(self, DX, DY, nrows, pitch):
        """VDDD rib (left, outer) and VSS rib (inner), met3 0.8 wide; returns xa (VDDD), xb (VSS)"""
        c = self.c; xb = DX - 1.4; xa = DX - 7.4
        ytop = DY + (nrows - 1) * pitch + 2.72 + 0.4
        for r in range(nrows):
            yb = DY + r * pitch; yt = yb + 2.72
            for (yy, xr) in ((yb, xb), (yt, xa)):
                c.rect("metal1", xr - 0.4, yy - 0.24, DX + 0.3, yy + 0.24)
                via_stack(c, xr, yy, 1, 3, pad={1: (0.2, 0.2), 2: (0.21, 0.21), 3: (0.4, 0.3)})
                self.block(0, xr - 0.3, yy - 0.3, xr + 0.3, yy + 0.3)
        ybot = -91.3
        for xr in (xa, xb):
            c.rect("metal3", xr - 0.4, ybot - 0.4, xr + 0.4, ytop); self.block(1, xr - 0.4, ybot, xr + 0.4, ytop)
        # VDDD pad (met4 3.0 x 3.0) at the bottom of its rib; VSS rib continues down to the VSS trunk
        c.rect("metal4", xa - 1.5, ybot - 1.5, xa + 1.5, ybot + 1.5); via_array(c, 3, xa - 0.4, ybot - 0.4, xa + 0.4, ybot + 0.4)
        c.rect("via3", xa - 0.16, ybot - 0.16, xa + 0.16, ybot + 0.16)
        self.labels.append(("VDDD", "metal4", xa - 0.5, ybot - 0.5, xa + 0.5, ybot + 0.5))
        c.rect("metal4", xb - 1.5, -102.0, xb + 1.5, ybot + 1.5); c.rect("via3", xb - 0.16, ybot - 0.16, xb + 0.16, ybot + 0.16)
        c.rect("metal3", xb - 0.4, ybot - 0.4, xb + 0.4, ybot + 0.4)
        via_array(c, 4, xb - 1.5, -102.0, xb + 1.5, -98.5)
        return xa, xb, ybot

def dig_power2(S, DX, DY, nrows, pitch, yvss_bar_top):
    """digital rails inside the array gap: ribs go UP to a VDDD pad; the VSS rib drops on met4 to the VSS bar below the arrays."""
    c = S.c; xb = DX - 1.4; xa = DX - 7.4
    ytop = DY + (nrows - 1) * pitch + 2.72 + 0.4
    for r in range(nrows):
        yb = DY + r * pitch; yt = yb + 2.72
        for (yy, xr) in ((yb, xb), (yt, xa)):
            c.rect("metal1", xr - 0.4, yy - 0.24, DX + 0.3, yy + 0.24)
            via_stack(c, xr, yy, 1, 3, pad={1: (0.2, 0.2), 2: (0.21, 0.21), 3: (0.4, 0.3)})
            S.block(0, xr - 0.3, yy - 0.3, xr + 0.3, yy + 0.3)
    yp = ytop + 3.0
    c.rect("metal3", xa - 0.4, DY - 0.4, xa + 0.4, yp); S.block(1, xa - 0.4, DY - 0.4, xa + 0.4, yp)
    c.rect("metal3", xb - 0.4, DY - 1.4, xb + 0.4, ytop); S.block(1, xb - 0.4, DY - 1.4, xb + 0.4, ytop)
    c.rect("metal4", xa - 1.5, yp - 1.5, xa + 1.5, yp + 1.5); c.rect("via3", xa - 0.16, yp - 0.16, xa + 0.16, yp + 0.16)
    c.rect("metal3", xa - 0.4, yp - 0.4, xa + 0.4, yp + 0.4)
    S.labels.append(("VDDD", "metal4", xa - 0.5, yp - 0.5, xa + 0.5, yp + 0.5))
    # VSS rib bottom: via3 -> met4 vertical to the VSS bar
    yv = DY - 1.0
    c.rect("via3", xb - 0.16, yv - 0.16, xb + 0.16, yv + 0.16); c.rect("metal3", xb - 0.4, yv - 0.4, xb + 0.4, yv + 0.4)
    c.rect("metal4", xb - 0.8, yvss_bar_top - 0.5, xb + 0.8, yv + 0.5); S.block(2, xb - 0.8, yvss_bar_top - 0.5, xb + 0.8, yv + 0.5)
    return xa, xb
