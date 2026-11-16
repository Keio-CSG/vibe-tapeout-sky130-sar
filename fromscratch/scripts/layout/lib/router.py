"""Small multi-layer grid router (met2 V / met3 H / met4 V / met5 H). Units um.
Tracks: x pitch 0.23 (V layers), y pitch 0.34 (H layers); a used track blocks +-1 neighbour track for other nets."""
import heapq, math
import numpy as np
XP, YP = 0.23, 0.34
LAY = ["metal2", "metal3", "metal4", "metal5"]
DIR = ["V", "H", "V", "H"]
VIA = ["via2", "via3", "via4"]             # via between LAY[k] and LAY[k+1]
WID = [0.2, 0.3, 0.3, 1.6]
class Router:
    def __init__(self, x0, y0, x1, y1, nlayers=3):
        self.x0, self.y0 = x0, y0
        self.nx = int((x1 - x0) / XP) + 1; self.ny = int((y1 - y0) / YP) + 1; self.nl = nlayers
        self.own = np.full((nlayers, self.nx, self.ny), -1, dtype=np.int32)   # -1 free, -2 blocked, >=0 net
        self.paths = {}; self.names = {}; self.contest = False; self.terms = set(); self.extra = {}
        self.viaown = np.full((max(nlayers - 1, 1), self.nx, self.ny), -1, dtype=np.int32)
    def gx(self, x): return int(round((x - self.x0) / XP))
    def gy(self, y): return int(round((y - self.y0) / YP))
    def px(self, i): return self.x0 + i * XP
    def py(self, j): return self.y0 + j * YP
    def block_rect(self, layer, x1, y1, x2, y2, margin=0.0):
        """block grid nodes on 'layer' whose wire would come within margin of the rect"""
        mx = ([0.38, 0.65, 0.65, 1.6][layer] + margin); 
        i1 = self.gx(x1 - mx - 0.1) ; i2 = self.gx(x2 + mx + 0.1); j1 = self.gy(y1 - mx - 0.1); j2 = self.gy(y2 + mx + 0.1)
        i1 = max(i1, 0); j1 = max(j1, 0); i2 = min(i2, self.nx - 1); j2 = min(j2, self.ny - 1)
        for i in range(i1, i2 + 1):
            for j in range(j1, j2 + 1):
                x, y = self.px(i), self.py(j)
                if x1 - mx < x < x2 + mx and y1 - mx < y < y2 + mx: self.own[layer, i, j] = -2
    def _reserve(self, net, k, i, j):
        o = self.own
        rx = 1 if k == 0 else 2
        if DIR[k] == "V": rng = [(i + d, j + e) for d in range(-rx, rx + 1) for e in (-1, 0, 1)]
        else: rng = [(i + d, j + e) for d in (-2, -1, 0, 1, 2) for e in (-1, 0, 1)]
        for a, b in rng:
            if 0 <= a < self.nx and 0 <= b < self.ny:
                v = o[k, a, b]
                if v == -1: o[k, a, b] = net
                elif getattr(self, "contest", False) and v >= 0 and v != net and (a, b) != (i, j) and (k, a, b) not in self.terms: o[k, a, b] = -2
    def _ok(self, net, k, i, j):
        if not (0 <= i < self.nx and 0 <= j < self.ny): return False
        v = self.own[k, i, j]
        if not (v == -1 or v == net): return False
        # a node adjacent (perpendicular) that is owned by another net as a real wire would have reserved us already
        return True
    def route_net(self, net, name, terms, via_cost=12.0, wrong_way=6.0):
        """terms: list of (x,y,layer) in um (layer index). Returns True on success."""
        self.names[net] = name
        pts = [(k, self.gx(x), self.gy(y)) for x, y, k in terms]
        tree = {pts[0]}; self._reserve_nodes(net, [pts[0]])
        paths = [[pts[0]]]
        rest = pts[1:]; done = [pts[0]]
        while rest:
            # nearest-first (Manhattan distance to already connected terminals)
            t = min(rest, key=lambda q: min(abs(q[1] - a[1]) * XP + abs(q[2] - a[2]) * YP for a in done)); rest.remove(t); done.append(t)
            if t in tree: continue
            p = self._astar(net, t, tree, via_cost, wrong_way)
            if p is None: return False
            self._reserve_nodes(net, p); tree.update(p); paths.append(p)
        self.paths.setdefault(net, []).extend(paths); return True
    def halo(self, net, r):
        """keep-out halo of r tracks around the committed wires of this net for all other nets"""
        for plist in self.paths.get(net, []):
            for (k, i, j) in plist:
                for a in range(-r, r + 1):
                    for b in range(-r, r + 1):
                        x, y = i + a, j + b
                        if 0 <= x < self.nx and 0 <= y < self.ny and self.own[k, x, y] == -1: self.own[k, x, y] = -2
    def _reserve_nodes(self, net, nodes):
        for k, i, j in nodes: self._reserve(net, k, i, j)
        for a, b in zip(nodes, nodes[1:]):
            if a[0] != b[0]: self.viaown[min(a[0], b[0]), a[1], a[2]] = net
    def _via_ok(self, net, kk, i, j):
        for k2 in (kk - 1, kk, kk + 1):
            if 0 <= k2 < self.viaown.shape[0]:
                sub = self.viaown[k2, max(i - 5, 0):i + 6, max(j - 3, 0):j + 4]
                if ((sub >= 0) & (sub != net)).any(): return False
        return True
    def reach(self, net, src, limit=400000):
        from collections import deque
        seen = {src}; q = deque([src])
        while q and len(seen) < limit:
            k, i, j = q.popleft()
            nb = []
            if DIR[k] == "V": nb += [(k, i, j + 1), (k, i, j - 1)]
            else: nb += [(k, i + 1, j), (k, i - 1, j)]
            if k + 1 < self.nl and self._via_ok(net, k, i, j): nb.append((k + 1, i, j))
            if k > 0 and self._via_ok(net, k - 1, i, j): nb.append((k - 1, i, j))
            for m in nb:
                if m in seen: continue
                if self._ok(net, *m): seen.add(m); q.append(m)
        return seen
    def _astar(self, net, src, tree, via_cost, wrong_way):
        # search from src to any node in tree
        ti = [n[1] for n in tree]; tj = [n[2] for n in tree]
        bi0, bi1, bj0, bj1 = min(ti), max(ti), min(tj), max(tj)
        def h(n):
            k, i, j = n
            return (max(bi0 - i, 0, i - bi1)) * XP + (max(bj0 - j, 0, j - bj1)) * YP
        INF = float("inf"); dist = {src: 0.0}; prev = {}; pq = [(h(src), 0.0, src)]
        if not self._ok(net, *src) and src not in tree: return None
        while pq:
            f, d, n = heapq.heappop(pq)
            if n in tree and n != src:
                path = [n]
                while path[-1] != src: path.append(prev[path[-1]])
                return path[::-1]
            if d > dist.get(n, INF): continue
            k, i, j = n
            nb = []
            if DIR[k] in ("V", "B"): nb += [((k, i, j + 1), YP), ((k, i, j - 1), YP)]
            if DIR[k] in ("H", "B"): nb += [((k, i + 1, j), XP * (1 if DIR[k] == "H" else 3)), ((k, i - 1, j), XP * (1 if DIR[k] == "H" else 3))]
            if k + 1 < self.nl and self._via_ok(net, k, i, j): nb.append(((k + 1, i, j), via_cost))
            if k > 0 and self._via_ok(net, k - 1, i, j): nb.append(((k - 1, i, j), via_cost))
            for m, c in nb:
                if m in tree: ok = True
                else: ok = self._ok(net, *m)
                if not ok: continue
                nd = d + c
                if nd < dist.get(m, INF):
                    dist[m] = nd; prev[m] = n; heapq.heappush(pq, (nd + h(m), nd, m))
        return None
    def emit(self, cell):
        """write routed geometry into a maglib Cell. Per net and layer the shapes are morphologically closed
        (klayout Region) so same-net notches/slivers below the layer spacing disappear."""
        import klayout.db as db
        from maglib import Cell
        close = {"metal2": 0.08, "metal3": 0.16, "metal4": 0.16}
        netcells = {}
        for net, plist in self.paths.items():
            tmp = Cell("tmp"); self._emit_paths(tmp, {net: plist}); self.merge_vias(tmp)
            for lay, (a, b, c_, d_) in self.extra.get(net, []): tmp.layers[lay].append((int(round(a * 200)), int(round(b * 200)), int(round(c_ * 200)), int(round(d_ * 200))))
            netcells[net] = tmp
        for net, tmp in netcells.items():
            for lay, rs in tmp.layers.items():
                if lay in close:
                    reg = db.Region()
                    for (x1, y1, x2, y2) in rs: reg.insert(db.Box(x1, y1, x2, y2))
                    reg.merge(); d = int(round(close[lay] * 200))
                    reg = reg.sized(d, d, 2); reg = reg.sized(-d, -d, 2); reg.merge()
                    for p in reg.each():
                        bb = p.bbox(); ys = sorted(set(pt.y for pt in p.each_point_hull()) | set(pt.y for h in range(p.holes()) for pt in p.each_point_hole(h)))
                        for ya, yb in zip(ys, ys[1:]):
                            strip = db.Region(db.Box(bb.left - 1, ya, bb.right + 1, yb)) & db.Region(p)
                            for q in strip.each():
                                b = q.bbox(); cell.layers[lay].append((b.left, b.bottom, b.right, b.top))
                else:
                    for r_ in rs: cell.layers[lay].append(r_)
    def _emit(self, cell):
        self._emit_paths(cell, self.paths)
    def merge_vias(self, cell, gap=0.13):
        g = int(round(gap * 200))
        for lay in ("via2", "via3", "via4"):
            rs = list(set(cell.layers.get(lay, [])))
            changed = True
            while changed:
                changed = False
                for a in range(len(rs)):
                    for b in range(a + 1, len(rs)):
                        x1, y1, x2, y2 = rs[a]; p1, q1, p2, q2 = rs[b]
                        if max(p1 - x2, x1 - p2) < g and max(q1 - y2, y1 - q2) < g:
                            rs[a] = (min(x1, p1), min(y1, q1), max(x2, p2), max(y2, q2)); rs.pop(b); changed = True; break
                    if changed: break
            cell.layers[lay] = rs
            kk = {"via2": 1, "via3": 2, "via4": 3}[lay]
            for (x1, y1, x2, y2) in rs:
                if (x2 - x1) > 70 or (y2 - y1) > 70:      # merged (larger than a single 0.32 contact)
                    for ml in (LAY[kk - 1], LAY[kk]):
                        cell.layers[ml].append((x1 - 9, y1 - 9, x2 + 9, y2 + 9))
    def bridge(self, cell, minsp={"metal2": 0.14, "metal3": 0.3, "metal4": 0.3}):
        """per layer: bridge gaps below min spacing between router rects (same net by construction of the reservation)"""
        for lay, sp in minsp.items():
            rs = list(set(cell.layers.get(lay, []))); s = int(round(sp * 200)); add = []
            rs.sort()
            for a in range(len(rs)):
                x1, y1, x2, y2 = rs[a]
                for b in range(a + 1, len(rs)):
                    p1, q1, p2, q2 = rs[b]
                    if p1 >= x2 + s: break
                    gx = max(p1 - x2, x1 - p2); gy = max(q1 - y2, y1 - q2)
                    if gx >= s or gy >= s: continue
                    if gx > 0 and gy > 0: continue      # diagonal: leave
                    mw = int(round({"metal2": 0.2, "metal3": 0.3, "metal4": 0.3}[lay] * 200))
                    def widen(lo, hi):
                        if hi - lo < mw: c = (lo + hi) // 2; lo, hi = c - mw // 2, c - mw // 2 + mw
                        return lo, hi
                    if gx > 0:    # gap in x, overlap in y
                        lo, hi = max(y1, q1), min(y2, q2)
                        if hi > lo: lo, hi = widen(lo, hi); add.append((min(x2, p2), lo, max(x1, p1), hi))
                    elif gy > 0:
                        lo, hi = max(x1, p1), min(x2, p2)
                        if hi > lo: lo, hi = widen(lo, hi); add.append((lo, min(y2, q2), hi, max(y1, q1)))
            for rr in add: cell.layers[lay].append(rr)
    def _emit_paths(self, cell, paths):
        for net, plist in paths.items():
            for p in plist:
                for a, b in zip(p, p[1:]):
                    (k1, i1, j1), (k2, i2, j2) = a, b
                    if k1 == k2:
                        w = WID[k1] / 2; x1, y1, x2, y2 = self.px(i1), self.py(j1), self.px(i2), self.py(j2)
                        cell.rect(LAY[k1], min(x1, x2) - w, min(y1, y2) - w, max(x1, x2) + w, max(y1, y2) + w)
                    else:
                        kk = min(k1, k2); x, y = self.px(i1), self.py(j1)
                        self._via(cell, kk, x, y)
                if len(p) == 1:
                    k, i, j = p[0]; w = WID[k] / 2; cell.rect(LAY[k], self.px(i) - w, self.py(j) - w, self.px(i) + w, self.py(j) + w)
    PAD = {"metal2": (0.16, 0.21), "metal3": (0.33, 0.185), "metal4": (0.19, 0.33)}   # half sizes (x,y)
    def _via(self, cell, kk, x, y):
        cell.rect(VIA[kk], x - 0.16, y - 0.16, x + 0.16, y + 0.16)
        for lay in (LAY[kk], LAY[kk + 1]):
            hx, hy = self.PAD[lay]; cell.rect(lay, x - hx, y - hy, x + hx, y + hy)
