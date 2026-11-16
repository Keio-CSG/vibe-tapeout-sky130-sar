import os
"""Transistor cells from magic gencell + strapping in metal2. Frame: gencell origin = device centre. Units um."""
import os, re, subprocess, glob, shutil
from maglib import Cell, iu, U
HERE = os.path.dirname(os.path.abspath(__file__)); CELLS = os.path.join(HERE, "..", "cells")
os.makedirs(CELLS, exist_ok=True)
KINDS = {"n": "sky130_fd_pr__nfet_01v8", "p": "sky130_fd_pr__pfet_01v8", "nl": "sky130_fd_pr__nfet_01v8_lvt", "pl": "sky130_fd_pr__pfet_01v8_lvt"}
def _gen(kind, w, l, nf):
    name = f"g_{kind}_w{w:g}_l{l:g}_nf{nf}".replace(".", "p")
    dst = os.path.join(CELLS, name + ".mag")
    if os.path.exists(dst): return name
    tmp = os.path.join(CELLS, "_tmp"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    tcl = f"load {name}\nbox position 0 0\nmagic::gencell sky130::{KINDS[kind]} m1 w {w:g} l {l:g} nf {nf} guard 1\nsave {name}\nwriteall force\nquit -noprompt\n"
    open(os.path.join(tmp, "g.tcl"), "w").write(tcl)
    rc = os.path.join(os.environ["PDKPATH"], "libs.tech/magic/sky130A.magicrc")
    subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", rc, "g.tcl"], cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    gen = [f for f in glob.glob(tmp + "/sky130_fd_pr__*.mag")]
    assert len(gen) == 1, (name, gen)
    shutil.move(gen[0], dst); shutil.rmtree(tmp)
    return name
def _parse(path):
    f = open(path).read(); secs = re.split(r"<< (\w+) >>", f); d = {secs[i]: secs[i + 1] for i in range(1, len(secs) - 1, 2)}
    def rects(n): return [tuple(map(int, l.split()[1:])) for l in d.get(n, "").strip().split("\n") if l.startswith("rect")]
    return d, rects, f
def _merge(rs):
    rs = list(rs); out = []
    while rs:
        a = list(rs.pop()); ch = True
        while ch:
            ch = False
            for r in rs[:]:
                if not (r[2] < a[0] or r[0] > a[2] or r[3] < a[1] or r[1] > a[3]):
                    a = [min(a[0], r[0]), min(a[1], r[1]), max(a[2], r[2]), max(a[3], r[3])]; rs.remove(r); ch = True
        out.append(tuple(a))
    return sorted(out)
def mos(kind, W, L, nf, name=None, ring_body=True, frame_W=None, frame_ref=None):
    """W = width per finger (um). Returns (Cell, pins) ; pins: dict name -> (layer, (x1,y1,x2,y2) um) ; bbox (um)."""
    g = _gen(kind, W, L, nf); d, rects, txt = _parse(os.path.join(CELLS, g + ".mag"))
    m1 = _merge(rects("metal1"))
    stripes = [r for r in m1 if (r[3] - r[1]) > 0.5 * U and (r[2] - r[0]) < 0.3 * U]
    pads = [r for r in m1 if r not in stripes]
    stripes.sort(); u = lambda v: v / U
    ymax = max(r[3] for r in stripes) / U; ymin = min(r[1] for r in stripes) / U
    c = Cell(name or f"m_{kind}_w{W:g}_l{L:g}_nf{nf}".replace(".", "p"))
    bb = re.search(r"string FIXED_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", txt)
    bbox = tuple(int(v) / U for v in bb.groups())
    c.use(g, "d", 0, 0, bbox=tuple(int(v) for v in bb.groups()))
    pins = {}
    def pad(x, y, hw=0.21):    # via1 stack: met1 pad, via1, met2 pad
        c.rect("metal1", x - hw, y - 0.13, x + hw, y + 0.13); c.rect("via1", x - 0.13, y - 0.13, x + 0.13, y + 0.13); c.rect("metal2", x - hw, y - 0.13, x + hw, y + 0.13)
    sx = [(r[0] + r[2]) / 2 / U for i, r in enumerate(stripes) if i % 2 == 0]; dx = [(r[0] + r[2]) / 2 / U for i, r in enumerate(stripes) if i % 2 == 1]
    ys = ymax - 0.25; yd = ymin + 0.25
    for x in sx: pad(x, ys, 0.165)
    for x in dx: pad(x, yd, 0.165)
    c.rect("metal2", min(sx) - 0.21, ys - 0.13, max(sx) + 0.21, ys + 0.13); pins["S"] = ("metal2", (min(sx) - 0.21, ys - 0.13, max(sx) + 0.21, ys + 0.13))
    c.rect("metal2", min(dx) - 0.21, yd - 0.13, max(dx) + 0.21, yd + 0.13); pins["D"] = ("metal2", (min(dx) - 0.21, yd - 0.13, max(dx) + 0.21, yd + 0.13))
    # gates
    top = [((r[0] + r[2]) / 2 / U, (r[1] + r[3]) / 2 / U) for r in pads if r[3] > 0]; bot = [((r[0] + r[2]) / 2 / U, (r[1] + r[3]) / 2 / U) for r in pads if r[3] < 0]
    xr = max(max(sx), max(dx)) + 0.75
    gy = []
    for grp in (top, bot):
        if not grp: continue
        yg = grp[0][1]; gy.append(yg)
        for x, y in grp: pad(x, y)
        c.rect("metal2", min(x for x, y in grp) - 0.21, yg - 0.13, xr + 0.13, yg + 0.13)
    if len(gy) == 2: c.rect("metal2", xr - 0.13, min(gy) - 0.13, xr + 0.13, max(gy) + 0.13)
    pins["Gy"] = ("metal2", (xr - 0.13, min(gy) - 0.13, xr + 0.13, max(gy) + 0.13))
    gtop = max(gy)
    half = bbox[2]; xL = -(half + 1.0); xRc = half + 1.0
    c.rect("metal2", xL - 0.21, ys - 0.13, min(sx) + 0.0, ys + 0.13)          # S bar extended to the left column
    c.rect("metal2", xL - 0.21, yd - 0.13, min(dx) + 0.0, yd + 0.13)          # D bar extended to the left column
    c.rect("metal2", xr - 0.13, gtop - 0.13, xRc + 0.21, gtop + 0.13)         # top gate bar extended to the right column
    # body: tie point on guard ring top edge
    ring = _merge(rects("nsubdiffcont") + rects("psubdiffcont"))
    top_r = max(ring, key=lambda r: r[3]); xc = (top_r[0] + top_r[2]) / 2 / U; yc = (top_r[1] + top_r[3]) / 2 / U
    c.rect("viali", xc - 0.085, yc - 0.085, xc + 0.085, yc + 0.085); c.rect("metal1", xc - 0.16, yc - 0.13, xc + 0.16, yc + 0.13)
    c.rect("via1", xc - 0.13, yc - 0.13, xc + 0.13, yc + 0.13); c.rect("metal2", xc - 0.21, yc - 0.21, xc + 0.21, yc + 0.21)
    def m3pad(x, y):
        c.rect("via2", x - 0.16, y - 0.16, x + 0.16, y + 0.16); c.rect("metal2", x - 0.21, y - 0.21, x + 0.21, y + 0.21)
        c.rect("metal3", x - 0.33, y - 0.21, x + 0.33, y + 0.21); return ("metal3", (x - 0.33, y - 0.21, x + 0.33, y + 0.21))
    pins = {"S": m3pad(xL, ys), "D": m3pad(xL, yd), "G": m3pad(xRc, gtop), "B": m3pad(xc, yc)}
    if frame_ref is not None or (frame_W is not None and frame_W > W):
        spec = frame_ref or (kind, frame_W, L, nf)
        refcell, refpins, refbbox = mos(*spec, ring_body=ring_body)
        frame = refcell.bbox()
        realbbox = tuple(iu(v) for v in bbox)
        assert all((realbbox[j]>=frame[j] if j<2 else realbbox[j]<=frame[j]) for j in range(4)), ("device outside original wrapper frame",realbbox,frame)
        # Preserve the old external terminals and placement frame. The smaller
        # device and new metal2 extensions stay inside that original footprint.
        c.layers["metal3"] = []; c.layers["via2"] = []
        # The original external frame is wider than the original diffusion.
        # Clip redundant new metal2 terminal extensions to that frame, while
        # leaving all actual gencell contacts and transistor geometry intact.
        c.layers["metal2"] = [(max(a,frame[0]),max(b,frame[1]),min(d,frame[2]),min(e,frame[3])) for a,b,d,e in c.layers["metal2"] if min(d,frame[2])>max(a,frame[0]) and min(e,frame[3])>max(b,frame[1])]
        oldpins = pins
        for key, (lay, rb) in refpins.items():
            assert lay == "metal3" and oldpins[key][0] == "metal3"
            ob = oldpins[key][1]
            xo, yo = (ob[0]+ob[2])/2, (ob[1]+ob[3])/2
            xo = max(frame[0]/U+.21,min(frame[2]/U-.21,xo))
            yo = max(frame[1]/U+.21,min(frame[3]/U-.21,yo))
            xn, yn = (rb[0]+rb[2])/2, (rb[1]+rb[3])/2
            c.rect("metal2", min(xo,xn)-.21,min(yo,yn)-.21,max(xo,xn)+.21,max(yo,yn)+.21)
            c.rect("via2",xn-.16,yn-.16,xn+.16,yn+.16)
            c.rect("metal3",*rb)
        cell, inst, xx, yy, orient, _ = c.uses[0]
        reserved = tuple(min(realbbox[j],iu(refbbox[j])) if j<2 else max(realbbox[j],iu(refbbox[j])) for j in range(4))
        c.uses[0] = (cell,inst,xx,yy,orient,reserved)
        pins, bbox = refpins, refbbox
        assert c.bbox() == refcell.bbox(), ("sampler footprint changed",c.bbox(),refcell.bbox())
    return c, pins, bbox
if __name__ == "__main__":
    import sys
    c, pins, bbox = mos("nl", 4, 0.15, 8); c.write(CELLS); print(pins, bbox)
    c, pins, bbox = mos("pl", 4, 0.35, 16); c.write(CELLS); print(pins, bbox)
    c, pins, bbox = mos("n", 5, 0.15, 1); c.write(CELLS); print(pins, bbox)
