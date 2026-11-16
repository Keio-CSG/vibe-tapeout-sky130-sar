"""Small grid maze router for the SKY130 layout generators (metal2 V / metal3 H / metal4 V), DRC-aware by construction.
Footprints: wire squares of side W[l], via pads PAD[l]; spacing S[l]; two nets conflict if |dx|<hA+hB+S and |dy|<hA+hB+S on the same layer.
usage: r = Router((x1,y1,x2,y2)); r.obstacle('metal2', rect, net); r.add('netname', 'metal2', x, y) ...; r.route_all(); r.emit(cell)"""
import heapq, math, os
LAYERS = ['metal2', 'metal3', 'metal4']
W = {'metal2': 0.20, 'metal3': 0.30, 'metal4': 0.30}
PAD = {'metal2': 0.34, 'metal3': 0.50, 'metal4': 0.80}
S = {'metal2': 0.14, 'metal3': 0.30, 'metal4': 0.30}
VIA = {(0, 1): ('via2', 0.28), (1, 2): ('via3', 0.32)}
PREF = {0: 'V', 1: 'H', 2: 'V'}
VIA_N = {('metal2', 'metal3'): ('via2', 0.28), ('metal3', 'metal4'): ('via3', 0.32)}
PREF_N = {'metal2': 'V', 'metal3': 'H', 'metal4': 'V'}

class Router:
    def __init__(self, bbox, dx=0.23, dy=0.17, layers=LAYERS, ox=None, oy=None):
        self.bbox = bbox; self.dx = dx; self.dy = dy; self.layers = layers
        self.ox = bbox[0] if ox is None else ox; self.oy = bbox[1] if oy is None else oy
        self.nx = int((bbox[2] - self.ox)/dx) + 1; self.ny = int((bbox[3] - self.oy)/dy) + 1
        self.blk_w = [dict() for _ in layers]     # cell -> owner net id (0 = obstacle: blocks all, -1 = several)
        self.blk_p = [dict() for _ in layers]
        self.nets = {}                            # name -> id
        self.terms = {}                           # id -> list of groups (list of (l,i,j,x,y))
        self.gpad = {}                            # id -> list of bool (terminal needs a pad-sized free node)
        self.ginfl = {}
        self.paths = {}                           # id -> set of nodes (l,i,j)
        self.rects_extra = []                     # (layer, rect) connector rects from true terminal to its node
        self.vianodes = {}                        # id -> set of via locations (l_low,i,j)
        self.maxit = int(os.environ.get('RMAXIT', '60000'))
        self.diags = {}
        self.pin_inflate = float(os.environ.get('PIN_INFLATE', '0.10'))
        self.fail = []
        self._obs = []

    # -- designs
    def ij(self, x, y): return (int(round((x - self.ox)/self.dx)), int(round((y - self.oy)/self.dy)))
    def xy(self, i, j): return (self.ox + i*self.dx, self.oy + j*self.dy)
    def nid(self, name):
        if name not in self.nets: self.nets[name] = len(self.nets) + 1; self.terms[self.nets[name]] = []; self.gpad[self.nets[name]] = []; self.ginfl.setdefault(self.nets[name], [])
        return self.nets[name]

    def _mark(self, d, i, j, owner):
        v = d.get((i, j))
        if v is None: d[(i, j)] = owner
        elif v != owner: d[(i, j)] = -1

    def _halo(self, l, hA, owner, i0, j0, wire=True):
        """mark all cells where another node (wire half W/2 or pad half PAD/2) would conflict with a footprint of half hA at (i0,j0)"""
        lay = self.layers[l]
        for blk, hB in ((self.blk_w[l], W[lay]/2), (self.blk_p[l], PAD[lay]/2)):
            rx = hA + hB + S[lay]
            ry = rx + (0.10 if lay == 'metal2' else 0.0)      # metal2 pads/terminal stubs are 0.06 taller than their width
            ni = int(math.ceil(rx/self.dx - 1e-9)) - 1; nj = int(math.ceil(ry/self.dy - 1e-9)) - 1
            for di in range(-ni, ni+1):
                for dj in range(-nj, nj+1):
                    self._mark(blk, i0+di, j0+dj, owner)

    def obstacle(self, layer, rect, net=None, draw=True):
        """existing metal: block nodes whose footprint would be closer than the spacing (owner net may still use them)"""
        self._obs.append((layer, rect, net, draw))
        l = self.layers.index(layer); owner = 0 if net is None else self.nid(net)
        x1, y1, x2, y2 = rect
        for blk, hB in ((self.blk_w[l], W[layer]/2), (self.blk_p[l], PAD[layer]/2)):
            m = hB + S[layer]
            i1 = int(math.floor((x1 - m - self.ox)/self.dx)); i2 = int(math.ceil((x2 + m - self.ox)/self.dx))
            j1 = int(math.floor((y1 - m - self.oy)/self.dy)); j2 = int(math.ceil((y2 + m - self.oy)/self.dy))
            for i in range(i1, i2+1):
                xx = self.ox + i*self.dx
                if xx <= x1 - m + 1e-9 or xx >= x2 + m - 1e-9: continue
                for j in range(j1, j2+1):
                    yy = self.oy + j*self.dy
                    if yy <= y1 - m + 1e-9 or yy >= y2 + m - 1e-9: continue
                    self._mark(blk, i, j, owner)

    def add(self, net, layer, x, y, pad=False):
        self.add_group(net, layer, [(x, y)], pad)

    def add_group(self, net, layer, pts, pad=False, inflate=None):
        """terminal of `net` on `layer`: any ONE of the candidate true positions pts=[(x,y),...] may be used; each is snapped to the lattice"""
        n = self.nid(net); l = self.layers.index(layer)
        g = []
        for (x, y) in pts:
            i, j = self.ij(x, y); g.append((l, i, j, x, y))
        self.terms[n].append(g); self.gpad[n].append(pad); self.ginfl[n].append(inflate)

    def add_rect(self, net, layer, rect, pad=False, pads=()):
        """terminal = a pre-drawn metal rect: candidates are all lattice nodes whose wire square overlaps the rect"""
        x1, y1, x2, y2 = rect; n = self.nid(net); l = self.layers.index(layer); w = W[layer]/2
        i1 = int(math.ceil((x1 + w*0 - self.ox)/self.dx - 1e-9)); i2 = int(math.floor((x2 - w*0 - self.ox)/self.dx + 1e-9))
        j1 = int(math.ceil((y1 - self.oy)/self.dy - 1e-9)); j2 = int(math.floor((y2 - self.oy)/self.dy + 1e-9))
        g = []
        for i in range(i1, i2+1):
            for j in range(j1, j2+1):
                x, y = self.xy(i, j)
                if pads and any(0.12 < abs(x - px) < 0.48 for px in pads): continue
                g.append((l, i, j, x, y))
        if not g:    # thin rect between lattice rows: use the nearest row (connector rect added on emit)
            xm, ym = 0.5*(x1+x2), 0.5*(y1+y2)
            i, j = self.ij(xm, ym)
            for ii in range(max(0, int((x1-self.ox)/self.dx)), int((x2-self.ox)/self.dx)+2):
                g.append((l, ii, j, self.ox+ii*self.dx, ym))
        self.terms[n].append(g); self.gpad[n].append(pad); self.ginfl[n].append(None)

    # -- node usability
    def free(self, n, l, i, j, pad):
        if i < 0 or j < 0 or i >= self.nx or j >= self.ny: return False
        v = (self.blk_p[l] if pad else self.blk_w[l]).get((i, j))
        return v is None or v == n

    def route_net(self, n):
        groups = self.terms[n]
        if len(groups) < 2: 
            self.paths[n] = set(); return True
        # start: first free candidate of group 0
        def cands(gi): return [(t[0], t[1], t[2]) for t in groups[gi] if self.free(n, t[0], t[1], t[2], self.gpad[n][gi])]
        star = n in getattr(self, 'star', ())          # star net: the LAST group is the root (e.g. a supply bus); every other group connects to the root separately
        root = len(groups) - 1 if star else 0
        c0 = cands(root)
        if not c0: self.diag = (n, root); return False
        tree = {c0[len(c0)//2]}
        if star: tree0 = set(c0); alltree = set(tree)
        self.chosen = getattr(self, 'chosen', {}); self.chosen[(n, root)] = tree.copy().pop()
        if self.gpad[n][root]:
            l0, i0, j0 = self.chosen[(n, root)]; self._halo(l0, PAD[self.layers[l0]]/2, n, i0, j0)
        remaining = [g_ for g_ in range(len(groups)) if g_ != root]
        self.vianodes[n] = set(); self.pathlist = getattr(self, 'pathlist', {}); self.pathlist[n] = []
        ok = True
        while remaining:
            targets = {}
            for gi in remaining:
                for t in cands(gi): targets[t] = gi
            if not targets: self.diag = (n, remaining[0]); self.diags[n] = ('notarget', remaining[0]); ok = False; break
            tl = list(targets)
            # heuristic bounding via nearest target
            bi1 = min(t[1] for t in tl); bi2 = max(t[1] for t in tl); bj1 = min(t[2] for t in tl); bj2 = max(t[2] for t in tl)
            def h(node):
                l, i, j = node
                return (max(bi1 - i, 0, i - bi2))*self.dx + (max(bj1 - j, 0, j - bj2))*self.dy
            heap = []; g = {}; prev = {}
            for s0 in (tree0 if star else tree):
                g[s0] = 0; heapq.heappush(heap, (h(s0), 0.0, s0))
            found = None; it = 0
            while heap:
                f, gc, cur = heapq.heappop(heap)
                if gc > g.get(cur, 1e18) + 1e-9: continue
                if cur in targets: found = cur; break
                it += 1
                if it > self.maxit: break
                l, i, j = cur
                moves = []
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    vertical = (dj != 0)
                    pref = (PREF_N[self.layers[l]] == 'V') == vertical
                    cost = (self.dy if vertical else self.dx) * (1.0 if pref else 3.0)
                    moves.append(((l, i+di, j+dj), cost))
                for dl in (-1, 1):
                    l2 = l + dl
                    if 0 <= l2 < len(self.layers): moves.append(((l2, i, j), 6.0))
                for nb, cost in moves:
                    l2, i2, j2 = nb
                    if l2 != l:
                        if not (self.free(n, l, i, j, True) and self.free(n, l2, i2, j2, True)): continue
                    else:
                        if not self.free(n, l2, i2, j2, False): continue
                    ng = gc + cost
                    if ng < g.get(nb, 1e18) - 1e-9:
                        g[nb] = ng; prev[nb] = cur; heapq.heappush(heap, (ng + h(nb), ng, nb))
            if found is None:
                self.diag = (n, remaining[0]); self.diags[n] = ('nopath', remaining[0], it, [(t[3], t[4]) for t in groups[remaining[0]][:1]]); ok = False; break
            gi = targets[found]; remaining.remove(gi); self.chosen[(n, gi)] = found
            if self.gpad[n][gi]:
                lf, if_, jf = found; self._halo(lf, PAD[self.layers[lf]]/2, n, if_, jf)
            node = found; path = [node]
            while node not in (tree0 if star else tree):
                node = prev[node]; path.append(node)
            for a, b in zip(path[:-1], path[1:]):
                (alltree if star else tree).add(a); (alltree if star else tree).add(b)
                if a[0] != b[0]: self.vianodes[n].add((min(a[0], b[0]), a[1], a[2]))
            self._claim_path(n, path); self.pathlist[n].append(list(path))
        self.paths[n] = alltree if star else tree
        return ok

    def _claim_path(self, n, path):
        vias = set()
        for a, b in zip(path[:-1], path[1:]):
            if a[0] != b[0]: vias.add(a); vias.add(b)
        for node in path:
            l, i, j = node
            h = (PAD[self.layers[l]]/2) if node in vias else (W[self.layers[l]]/2)
            self._halo(l, h, n, i, j)

    def claim_terminals(self):
        return

    def reset(self):
        obs = self._obs; self._obs = []
        self.blk_w = [dict() for _ in self.layers]; self.blk_p = [dict() for _ in self.layers]
        self.paths = {}; self.vianodes = {}; self.fail = []; self.chosen = {}; self.pathlist = {}
        for layer, rect, net, draw in obs: self.obstacle(layer, rect, net, draw)

    def reserve_groups(self, retry_nets=(), attempt=0):
        """pre-claim one candidate per terminal group so that other routes cannot squat on pin access nodes; on retries the groups of failed nets rotate their candidate"""
        if not hasattr(self, 'orig_groups'):
            self.orig_groups = {n: [list(g) for g in gs] for n, gs in self.terms.items()}
        for n, groups in self.terms.items():
            for gi in range(len(groups)):
                cl = self.orig_groups[n][gi]
                import random
                rng = random.Random(attempt * 7919 + n * 131 + gi)
                start = (rng.randrange(len(cl)) if (n in retry_nets or (attempt > 0 and rng.random() < 0.35)) else 0)
                order = cl[start:] + cl[:start]
                chosen = None
                for t in order:
                    if self.free(n, t[0], t[1], t[2], self.gpad[n][gi]): chosen = t; break
                if chosen is None: chosen = order[0]
                groups[gi] = [chosen]
                h = (PAD[self.layers[chosen[0]]]/2) if self.gpad[n][gi] else (W[self.layers[chosen[0]]]/2)
                infl = self.ginfl[n][gi] if self.ginfl[n][gi] is not None else self.pin_inflate
                self._halo(chosen[0], h + infl, n, chosen[1], chosen[2])

    def route_all(self, order=None, tries=6, reserve=False):
        names = order or sorted(self.nets, key=lambda k: self._span(self.nets[k]))
        best = None; failed_prev = []
        for t in range(tries):
            if t: self.reset()
            self.claim_terminals()
            if reserve: self.reserve_groups(set(self.nets[k] for k in failed_prev), t)
            self.fail = []
            for name in names:
                n = self.nets[name]
                if not self.route_net(n): self.fail.append(name)
            if best is None or len(self.fail) < len(best[0]): best = (list(self.fail), dict(self.paths), dict(self.vianodes), {k: [list(p) for p in v] for k, v in self.pathlist.items()}, dict(self.chosen))
            if not self.fail: break
            failed_prev = list(self.fail)
            names = self.fail + [k for k in names if k not in self.fail]
        self.fail, self.paths, self.vianodes, self.pathlist, self.chosen = best
        self._rebuild([n for n in self.paths if self.paths[n] is not None and n in self.pathlist and self.nets_by_id(n) not in self.fail])
        return self.fail


    # ---- rip-up and reroute around failed terminals --------------------------------------------------------------------------------
    def _rebuild(self, keep):
        """clear all blockage, re-add obstacles + pin reservations + the paths of the nets in keep"""
        saved = {n: (self.paths.get(n), self.vianodes.get(n), self.pathlist.get(n)) for n in keep}
        chosen = dict(self.chosen)
        obs = self._obs; self._obs = []
        self.blk_w = [dict() for _ in self.layers]; self.blk_p = [dict() for _ in self.layers]
        for layer, rect, net, draw in obs: self.obstacle(layer, rect, net, draw)
        for n, groups in self.terms.items():
            for gi, g in enumerate(groups):
                if len(g) != 1: continue
                t = g[0]
                h = (PAD[self.layers[t[0]]]/2) if self.gpad[n][gi] else (W[self.layers[t[0]]]/2)
                infl = self.ginfl[n][gi] if self.ginfl[n][gi] is not None else self.pin_inflate
                self._halo(t[0], h + infl, n, t[1], t[2])
        self.paths = {}; self.vianodes = {}; self.pathlist = {}; self.chosen = chosen
        for n, (p, v, pl) in saved.items():
            if p is None: continue
            self.paths[n] = p; self.vianodes[n] = v; self.pathlist[n] = pl
            for path in pl: self._claim_path(n, path)

    def ripup(self, iters=60, radius=1.0, seed=1):
        import random
        rng = random.Random(seed)
        names = {v: k for k, v in self.nets.items()}
        def snap(): return (list(self.fail), {n: (set(self.paths[n]), set(self.vianodes.get(n, ())), [list(p) for p in self.pathlist.get(n, [])]) for n in self.paths}, dict(self.chosen), dict(self.diags))
        best = snap(); cnt = {}
        for it in range(iters):
            if not self.fail: break
            f = self.nets[self.fail[0]] if isinstance(self.fail[0], str) else self.fail[0]
            fname = names[f]
            cnt[f] = cnt.get(f, 0) + 1
            gi = (self.diags.get(f) or (None, 0))[1]
            tx, ty = self.terms[f][gi][0][3], self.terms[f][gi][0][4]
            rad = radius + 0.6*cnt[f]
            near = []
            for n, pl in self.pathlist.items():
                if n == f or n in [self.nets[x] for x in self.fail]: continue
                d = 1e9
                for path in pl:
                    for (l, i, j) in path:
                        x, y = self.xy(i, j); d = min(d, abs(x - tx) + abs(y - ty))
                if d < rad: near.append((d, n))
            near.sort(); rip = [n for d, n in near[:8]]
            keep = [n for n in self.paths if n != f and n not in rip and names[n] not in self.fail]
            self._rebuild(keep)
            order = [f] + rip + [self.nets[x] for x in self.fail if self.nets[x] != f]
            rng.shuffle(order[1:len(rip)+1]) if False else None
            self.fail = []; self.diags.pop(f, None)
            for n in order:
                self.paths.pop(n, None)
                if not self.route_net(n): self.fail.append(names[n])
            print('ripup', it, fname, 'ripped', len(rip), 'fails', len(self.fail), flush=True)
            if len(self.fail) < len(best[0]): best = snap()
        if len(self.fail) > len(best[0]):
            fl, ps, ch, dg = best
            self.fail = fl; self.diags = dg
            self.paths = {n: v[0] for n, v in ps.items()}; self.vianodes = {n: v[1] for n, v in ps.items()}; self.pathlist = {n: v[2] for n, v in ps.items()}; self.chosen = ch
        return self.fail

    def nets_by_id(self, n):
        return [k for k, v in self.nets.items() if v == n][0]

    def _span(self, n):
        ts = [g[0] for g in self.terms[n]]
        if len(ts) < 2: return 0
        xs = [t[3] for t in ts]; ys = [t[4] for t in ts]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def emit(self, cell):
        import klayout.db as db
        coll = {}      # (net, layer) -> list of (x1,y1,x2,y2) floats
        def R(n, lay, x1, y1, x2, y2): coll.setdefault((n, lay), []).append((x1, y1, x2, y2))
        vias = []      # (layer, rect)
        for n, tree in self.paths.items():
            if len(self.terms[n]) < 2 or not tree: continue
            nodes = set(tree)
            for (l, i, j) in nodes:
                lay = self.layers[l]; x, y = self.xy(i, j); w = W[lay]
                R(n, lay, x - w/2, y - w/2, x + w/2, y + w/2)
            for (l, i, j) in nodes:
                lay = self.layers[l]; x, y = self.xy(i, j); w = W[lay]
                for di, dj in ((1, 0), (0, 1)):
                    if (l, i+di, j+dj) in nodes:
                        x2, y2 = self.xy(i+di, j+dj)
                        R(n, lay, min(x, x2) - w/2, min(y, y2) - w/2, max(x, x2) + w/2, max(y, y2) + w/2)
            for (l, i, j) in self.vianodes.get(n, ()):
                x, y = self.xy(i, j)
                vlay, vs = VIA_N[(self.layers[l], self.layers[l+1])]
                vias.append((vlay, (x - vs/2, y - vs/2, x + vs/2, y + vs/2)))
                for ll in (l, l+1):
                    lay = self.layers[ll]; p = PAD[lay]
                    hy = p/2 + (0.03 if lay == 'metal2' else 0.0)       # via2 needs 0.045 metal2 overlap in one direction
                    R(n, lay, x - p/2, y - hy, x + p/2, y + hy)
        for (n, gi), node in getattr(self, 'chosen', {}).items():
            if len(self.terms[n]) < 2 or n not in self.paths or not self.paths[n]: continue
            l, i, j = node
            for t in self.terms[n][gi]:
                if (t[0], t[1], t[2]) == node:
                    sx, sy = self.xy(i, j); lay = self.layers[l]; w = W[lay]
                    if abs(sx - t[3]) > 1e-6 or abs(sy - t[4]) > 1e-6:
                        R(n, lay, min(t[3], sx) - w/2, min(t[4], sy) - w/2, max(t[3], sx) + w/2, max(t[4], sy) + w/2)
        for (net, layer, rect) in getattr(self, 'extra', []):
            n = self.nets.get(net)
            if n is not None: coll.setdefault((n, layer), []).append(rect)
        # pre-drawn metal of the same net (obstacles) takes part in the notch closing
        for layer, rect, net, draw in self._obs:
            if draw and net is not None and (self.nets.get(net), layer) in coll: coll[(self.nets[net], layer)].append(rect)
        regs = {}
        for (n, lay), rects in coll.items():
            reg = db.Region()
            for (x1, y1, x2, y2) in rects: reg.insert(db.Box(int(round(x1*1000)), int(round(y1*1000)), int(round(x2*1000)), int(round(y2*1000))))
            reg.merge(); regs[(n, lay)] = reg
        if getattr(self, 'bridge', False):
            tot = {}
            for (n, lay), reg in regs.items(): tot.setdefault(lay, db.Region()).insert(reg)
            for k in tot: tot[k].merge()
        for (n, lay), reg in regs.items():
            d = int(round(S[lay]*1000/2)) + 5
            if getattr(self, 'bridge', False):      # opt-in (route_pf): W-wide fillers for same-net gaps < S, then close only gaps < S
                reg = bridge_gaps(reg, lay, tot[lay] - reg); d = 5*((int(round(S[lay]*1000/2)) - 1)//5)     # stay on the 5 nm grid
            reg = reg.sized(d).sized(-d)
            reg.merge()
            for poly in reg.each():
                for tz in poly.decompose_trapezoids(0):
                    b = tz.bbox()
                    cell.rect(lay, b.left/1000.0, b.bottom/1000.0, b.right/1000.0, b.top/1000.0)
        for vlay, r in vias: cell.rect(vlay, *r)

def chosen_xy(r, net, gi):
    n = r.nets[net]; node = r.chosen.get((n, gi))
    if node is None: return None
    for t in r.terms[n][gi]:
        if (t[0], t[1], t[2]) == node: return (t[3], t[4])


def bridge_gaps(reg, lay, others=None, passes=3):
    """same-net shapes closer than the spacing S that the box closing would not merge cleanly (diagonal corner gaps, facing
    gaps with an overlap shorter than the min width): add a filler of at least min width.  Several filler shapes are tried
    (centred box, the two L-shaped detours around a corner, end-aligned bars); the first one that keeps >= S to the metal
    of the other nets (`others`) is used.  Used by route_pf.PFRouter (attribute bridge=True)."""
    import klayout.db as db
    s = int(round(S[lay]*1000)); w = int(round(W[lay]*1000)); e = 50
    g5 = lambda v: 5*int(math.floor(v/5.0)); c5 = lambda v: 5*int(math.ceil(v/5.0))
    def B(x1, y1, x2, y2): return db.Box(g5(min(x1, x2)), g5(min(y1, y2)), c5(max(x1, x2)), c5(max(y1, y2)))
    def ok(boxes):
        if others is None: return True
        r = db.Region()
        for b in boxes: r.insert(b)
        return (r.sized(s - 1) & others).is_empty()
    nbad = 0; orig = reg.dup(); added = False
    for _ in range(passes):
        polys = list(reg.each())
        boxes = [tz.bbox() for poly in polys for tz in poly.decompose_trapezoids(0)]
        pbox = [poly.bbox() for poly in polys for tz in poly.decompose_trapezoids(0)]
        add = []
        for a in range(len(boxes)):
            A = boxes[a]
            for b in range(a+1, len(boxes)):
                Bb = boxes[b]
                gx = max(Bb.left - A.right, A.left - Bb.right, 0); gy = max(Bb.bottom - A.top, A.bottom - Bb.top, 0)
                if gx == 0 and gy == 0: continue
                if gx >= s or gy >= s or (gx*gx + gy*gy) >= s*s: continue
                L_, R_ = (A, Bb) if A.left <= Bb.left else (Bb, A)
                cands = []
                if gx > 0 and gy > 0:
                    up = L_.top < R_.bottom           # L below-left of R (else above-left)
                    ly = L_.top if up else L_.bottom; ry = R_.bottom if up else R_.top; sg = 1 if up else -1
                    cands.append([B((L_.right + R_.left)//2 - w//2, (ly + ry)//2 - w//2, (L_.right + R_.left)//2 + w//2, (ly + ry)//2 + w//2)])
                    cands.append([B(L_.right - e, ly - sg*w, R_.left + w, ly), B(R_.left, ly - sg*w, R_.left + w, ry + sg*e)])   # under/over R
                    cands.append([B(L_.right - w, ly - sg*e, L_.right, ry + sg*w), B(L_.right - w, ry, R_.left + e, ry + sg*w)])  # beside L
                elif gx > 0:
                    lo, hi = max(A.bottom, Bb.bottom), min(A.top, Bb.top); x1, x2 = L_.right - e, R_.left + e
                    if hi - lo >= w: cands.append([B(x1, lo, x2, hi)])
                    else:
                        c = (lo + hi)//2
                        cands += [[B(x1, c - w//2, x2, c + w//2)], [B(x1, lo, x2, lo + w)], [B(x1, hi - w, x2, hi)]]
                else:
                    D_, U_ = (A, Bb) if A.bottom <= Bb.bottom else (Bb, A)
                    lo, hi = max(A.left, Bb.left), min(A.right, Bb.right); y1, y2 = D_.top - e, U_.bottom + e
                    if hi - lo >= w: cands.append([B(lo, y1, hi, y2)])
                    else:
                        c = (lo + hi)//2
                        cands += [[B(c - w//2, y1, c + w//2, y2)], [B(lo, y1, lo + w, y2)], [B(hi - w, y1, hi, y2)]]
                # skip if the gap is already metal (strips of one polygon)
                pr = cands[0][0]
                if gx > 0 and gy > 0: probe = B(L_.right, min(ly, ry), R_.left, max(ly, ry))
                elif gx > 0: probe = B(L_.right, max(A.bottom, Bb.bottom), R_.left, max(min(A.top, Bb.top), max(A.bottom, Bb.bottom) + 10))
                else: probe = B(max(A.left, Bb.left), D_.top, max(min(A.right, Bb.right), max(A.left, Bb.left) + 10), U_.bottom)
                if (db.Region(probe) - reg).is_empty(): continue
                hull = pbox[a] + pbox[b]          # prefer fillers inside the bounding box of the two polygons (no fins)
                def prot(c): return sum(bx.area() - (bx & hull).area() for bx in c)
                cands.sort(key=prot)
                pick = next((c for c in cands if ok(c)), None)
                if pick is None: pick = cands[0]; nbad += 1
                add += pick
        if not add: break
        for bx in add: reg.insert(bx)
        reg.merge(); added = True
    if added:     # drop filler slivers thinner than the min width (opening), never removing original metal
        h = w//2 - 1
        reg = orig + reg.sized(-h).sized(h); reg.merge()
    if nbad: print('bridge_gaps: %d fillers on %s too close to other nets' % (nbad, lay), flush=True)
    return reg
