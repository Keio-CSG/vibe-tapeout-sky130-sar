#!/usr/bin/env python3
"""Common-centroid CDAC array generator (one side), version 3 (identical unit access also in the centre columns).
Unit: MIM 1.24 (mimcap), plate metal3 (+0.14), top plate: mimcapcontact -> metal4 pad -> metal4 stub -> metal4 strip in the gap above the row.
Bottom plate: short metal3 tab (0.27 um) -> via2 -> metal2 pad -> via1 -> metal1 'lane' (vertical).  Main columns: lane = column trunk of the bit
(columns 0..14 tab to the left, 17..31 to the right, i.e. mirror symmetric).  Centre columns 15 (tab right) and 16 (tab left): lane segments per
run of units of one bit, joined by metal2 jumpers (in the empty gaps between rows) to 7 vertical metal1 gap lines (one per small bit).
Dummy ring (1 unit deep): plates shorted and tied to a metal2 VSS ring.  Bit nets end in metal3 strap tracks above the array."""
import sys, os, json
from lay import Cell

PX, PY = 3.0, 2.76
CENTER_D = 6.0
CU = 4.0128e-15 and 1.24
CUF = 1.24
PL = 0.14
HALF = CUF/2
NC = 32
TAB = 0.86          # via2 centre distance from the unit centre
LINE_P = 0.5

def col_x(i):
    x = i*PX
    if i >= 16: x += CENTER_D - PX
    return x
def row_y(j): return j*PY

def _pinx():
    import json, fp
    try:
        m = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bank', 'meta.json')))
        return {k: fp.BANK_OX + m['bot_x'][str(k)] - fp.CDAC_OX for k in range(11)}
    except Exception:
        return {k: 14.0 + 8.0*k for k in range(11)}
PINX = _pinx()
COLS = {0: list(range(0, 8)) + list(range(24, 32)), 1: list(range(8, 12)) + list(range(20, 24)), 2: [12, 13, 18, 19], 3: [14, 17]}
def bit_of(i, j):
    for k, cs in COLS.items():
        if i in cs: return k
    if (i, j) in ((15, 15), (16, 16)): return 8
    if (i, j) == (16, 15): return 9
    if (i, j) == (15, 16): return 10
    r = (15 - j) if j <= 15 else (j - 16)
    if r == 1: return 7
    if r <= 3: return 6
    if r <= 7: return 5
    return 4
GAPLINE = {4: 0, 5: 1, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6}

def runs_for_centre():
    """list of (bit, column, row0, row1, jumper_gap) for the centre columns; jumper_gap g: y = row_y(g)+PY/2"""
    out = []
    for col in (15, 16):
        j = 0
        while j < NC:
            k = bit_of(col, j); j1 = j
            while j1 + 1 < NC and bit_of(col, j1 + 1) == k: j1 += 1
            out.append([k, col, j, j1])
            j = j1 + 1
    # jumper gaps (all distinct per bit run, see header comment)
    gap = {}
    for k, col, r0, r1 in out:
        if k == 4: g = -1 if r1 < 16 else 31
        elif k == 5: g = 7 if r1 < 16 else 23
        elif k == 6: g = 11 if r1 < 16 else 19
        elif k == 7: g = 13 if r1 < 16 else 17
        elif k == 8: g = 15
        elif k == 9: g = 14
        elif k == 10: g = 16
        gap[(k, col, r0)] = g
    return [(k, col, r0, r1, gap[(k, col, r0)]) for k, col, r0, r1 in out]

def build(name='cdac_core'):
    c = Cell(name)
    xL, xR = col_x(15), col_x(16)
    M = 0.5*(xL + xR)
    def line_x(k): return M + (GAPLINE[k] - 3)*LINE_P
    def lane_x(i):
        if i == 15: return xL + TAB
        if i == 16: return xR - TAB
        return col_x(i) - TAB if i <= 14 else col_x(i) + TAB
    def stack(x, y):
        c.rect('via2', x-0.14, y-0.14, x+0.14, y+0.14); c.rect('metal2', x-0.2, y-0.2, x+0.2, y+0.2)
        c.rect('via1', x-0.13, y-0.13, x+0.13, y+0.13); c.rect('metal1', x-0.17, y-0.17, x+0.17, y+0.17)
    def via1pad(x, y):
        c.rect('via1', x-0.13, y-0.13, x+0.13, y+0.13); c.rect('metal2', x-0.2, y-0.2, x+0.2, y+0.2); c.rect('metal1', x-0.17, y-0.17, x+0.17, y+0.17)
    units = []
    ytop_trunk = row_y(NC) + PY + 1.5
    for j in range(-1, NC + 1):
        for i in range(-1, NC + 1):
            x, y = col_x(i), row_y(j)
            core = (0 <= i < NC and 0 <= j < NC)
            c.rect('mimcap', x-HALF, y-HALF, x+HALF, y+HALF)
            c.rect('mimcapcontact', x-0.3, y-0.3, x+0.3, y+0.3)
            c.rect('metal4', x-0.35, y-0.35, x+0.35, y+0.35)
            c.rect('metal3', x-HALF-PL, y-HALF-PL, x+HALF+PL, y+HALF+PL)
            if core:
                lx = lane_x(i)
                if lx < x: c.rect('metal3', lx-0.17, y-0.17, x-HALF-PL+0.01, y+0.17)
                else:      c.rect('metal3', x+HALF+PL-0.01, y-0.17, lx+0.17, y+0.17)
                stack(lx, y)
                units.append((i, j, 'core', bit_of(i, j)))
            else:
                if i == -1: tx, ty = -1, 0
                elif i == NC: tx, ty = 1, 0
                elif j == -1: tx, ty = 0, -1
                else: tx, ty = 0, 1
                P = lambda d: (x + tx*d, y + ty*d)
                (xa, ya), (xb, yb) = P(HALF + PL - 0.01), P(1.6)
                c.rect('metal3', min(xa, xb) - (0.2 if tx == 0 else 0), min(ya, yb) - (0.2 if ty == 0 else 0), max(xa, xb) + (0.2 if tx == 0 else 0), max(ya, yb) + (0.2 if ty == 0 else 0))
                vx, vy = P(0.86)
                c.rect('via2', vx-0.14, vy-0.14, vx+0.14, vy+0.14); c.rect('metal2', vx-0.2, vy-0.2, vx+0.2, vy+0.2)
                wx, wy = P(1.3)
                c.rect('via3', wx-0.16, wy-0.16, wx+0.16, wy+0.16)
                c.rect('metal4', min(x, wx) - 0.2, min(y, wy) - 0.2, max(x, wx) + 0.2, max(y, wy) + 0.2)
                units.append((i, j, 'dummy', None))
    # ---- top plate -------------------------------------------------------------------------------------------------
    xl, xr = col_x(-1) - 2.6, col_x(NC) + 2.6
    ybus = row_y(-1) - 2.2
    for j in range(NC):
        ys = row_y(j) + PY/2
        c.rect('metal4', xl, ys-0.3, xr, ys+0.3)
        for i in range(NC):
            c.rect('metal4', col_x(i)-0.25, row_y(j), col_x(i)+0.25, ys+0.3)
    for xs in (xl, xr):
        c.rect('metal4', xs-0.4, row_y(0)+PY/2-0.3, xs+0.4, row_y(NC-1)+PY/2+0.3)
    # ---- ground ring (metal2) --------------------------------------------------------------------------------------
    gx0, gx1 = col_x(-1) - TAB, col_x(NC) + TAB
    gy0, gy1 = row_y(-1) - TAB, row_y(NC) + TAB
    for yy in (gy0, gy1): c.rect('metal2', gx0-0.2, yy-0.2, gx1+0.2, yy+0.2)
    for xx in (gx0, gx1): c.rect('metal2', xx-0.2, gy0-0.2, xx+0.2, gy1+0.2)
    # ---- main-column trunks (metal1 lanes through the whole column) ---------------------------------------------------
    ybot = row_y(0) - 0.4
    track_cols = {}
    for i in range(NC):
        if i in (15, 16): continue
        lx = lane_x(i)
        c.rect('metal1', lx-0.17, ybot, lx+0.17, ytop_trunk)
        track_cols.setdefault(bit_of(i, 0), []).append(lx)
    # ---- centre columns: lane segments, jumpers, gap lines ----------------------------------------------------------------
    jump_ymin = {}
    for k, col, r0, r1, g in runs_for_centre():
        lx = lane_x(col); gy = row_y(g) + PY/2
        y0s, y1s = row_y(r0) - 0.17, max(row_y(r1) + 0.17, gy + 0.2) if g >= r1 else row_y(r1) + 0.17
        y0s = min(y0s, gy - 0.2) if g < r0 else y0s
        c.rect('metal1', lx-0.17, y0s, lx+0.17, y1s)
        via1pad(lx, gy)
        gx = line_x(k)
        via1pad(gx, gy)
        c.rect('metal2', min(lx, gx)-0.2, gy-0.14, max(lx, gx)+0.2, gy+0.14)
        jump_ymin[k] = min(jump_ymin.get(k, 1e9), gy)
    for k in GAPLINE:
        gx = line_x(k)
        c.rect('metal1', gx-0.17, jump_ymin[k]-0.2, gx+0.17, ytop_trunk)
        track_cols[k] = [gx]
    # ---- strap tracks (metal3, one per bit, MSB nearest the array) + pins: via3 -> metal4 line to the top edge ----------------------------------
    TP = 0.9; y0 = ytop_trunk - 0.6; track_y = {}
    ytop_pin = y0 + 10*TP + 1.8
    for k in range(11):
        yk = y0 + k*TP; track_y[k] = yk
        xs = track_cols[k]
        xpin = PINX[k]
        lo, hi = min(min(xs) - 0.4, xpin - 0.4), max(max(xs) + 0.4, xpin + 0.4)
        c.rect('metal3', lo, yk-0.25, hi, yk+0.25)
        for x in xs:
            c.rect('metal1', x-0.17, ytop_trunk-0.1, x+0.17, yk+0.2)
            c.rect('via1', x-0.13, yk-0.13, x+0.13, yk+0.13); c.rect('metal2', x-0.2, yk-0.2, x+0.2, yk+0.2); c.rect('via2', x-0.14, yk-0.14, x+0.14, yk+0.14)
        c.rect('via3', xpin-0.16, yk-0.16, xpin+0.16, yk+0.16); c.rect('metal3', xpin-0.25, yk-0.25, xpin+0.25, yk+0.25)
        c.rect('metal4', xpin-0.4, yk-0.4, xpin+0.4, yk+0.4)
        c.rect('metal4', xpin-0.15, yk, xpin+0.15, ytop_pin)
        c.rect('metal4', xpin-0.4, ytop_pin-0.4, xpin+0.4, ytop_pin+0.4)
        c.label('metal4', xpin, ytop_pin, 'B%d' % k, port=k+1, kind='signal bidirectional', size=0.4)
    c.label('metal4', xr, row_y(NC//2), 'TOP', port=12, kind='signal bidirectional', size=0.6)
    c.label('metal2', gx0, row_y(0), 'VSS', port=13, kind='ground bidirectional', size=0.3)
    meta = dict(units=units, track_y=track_y, xl=xl, xr=xr, ring=(col_x(-1), col_x(NC)), ground=(gx0, gx1, gy0, gy1), ybus=ybus,
                height=(y0 + 11*TP + 0.5) - ybus + 0.4, width=(xr - xl) + 0.8, y_track_top=ytop_pin + 0.4, pins=dict((k, (PINX[k], ytop_pin)) for k in range(11)))
    return c, meta

if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cdac')
    c, meta = build('cdac_core')
    c.write(out)
    cnt = {}
    for i, j, kind, k in meta['units']:
        if kind == 'core': cnt[k] = cnt.get(k, 0) + 1
    print('units per bit', sorted(cnt.items()))
    pm = []
    for j in range(NC-1, -1, -1):
        pm.append(' '.join('%2s' % ('D' if bit_of(i, j) == 10 else bit_of(i, j)) for i in range(NC)))
    open(os.path.join(out, 'placement_map.txt'), 'w').write('bit index per core unit (0=512 ... 9=1, D=dummy unit), rows top to bottom, columns left to right\n' + '\n'.join(pm) + '\n')
    json.dump({k: v for k, v in meta.items() if k != 'units'}, open(os.path.join(out, 'meta.json'), 'w'))
    print('width %.1f height %.1f area %.0f' % (meta['width'], meta['height'], meta['width']*meta['height']))
