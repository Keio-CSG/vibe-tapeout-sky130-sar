"""Minimal magic-layout writer (units: um in the API, 1 magic unit = 0.005 um, magscale 1 2)."""
import os
U = 200  # internal units per um
LAYERS = ['nwell', 'pwell', 'ndiffusion', 'pdiffusion', 'ntransistor', 'ptransistor', 'polysilicon', 'poly', 'ndcontact', 'pdcontact', 'ndiffc', 'pdiffc',
          'nsubstratencontact', 'psubstratepcontact', 'locali', 'viali', 'metal1', 'via1', 'metal2', 'via2', 'metal3', 'via3', 'metal4', 'mimcap', 'mimcapcontact', 'nsdm', 'psdm']

def q(v):
    return int(round(v * U))

class Cell:
    def __init__(self, name):
        self.name = name
        self.rects = {}      # layer -> list of (x1,y1,x2,y2) in internal units
        self.labels = []     # (layer, x1,y1,x2,y2, text, port_index or None, class)
        self.uses = []       # (cellname, instname, transform tuple a b c d e f, bbox)
        self.props = []

    def rect(self, layer, x1, y1, x2, y2):
        if x2 < x1: x1, x2 = x2, x1
        if y2 < y1: y1, y2 = y2, y1
        a = (q(x1), q(y1), q(x2), q(y2))
        assert a[2] > a[0] and a[3] > a[1], (layer, x1, y1, x2, y2)
        self.rects.setdefault(layer, []).append(a)

    def label(self, layer, x, y, text, port=None, kind='signal bidirectional', size=0.2, flags='nsew'):
        self.labels.append((layer, q(x - size/2), q(y - size/2), q(x + size/2), q(y + size/2), text, port, kind, flags))

    def use(self, cellname, inst, x=0.0, y=0.0, orient='R0'):
        """orient: R0, MX (mirror about x axis: y -> -y), MY (x -> -x), R180"""
        t = {'R0': (1, 0, 0, 0, 1, 0), 'MX': (1, 0, 0, 0, -1, 0), 'MY': (-1, 0, 0, 0, 1, 0), 'R180': (-1, 0, 0, 0, -1, 0)}[orient]
        self.uses.append((cellname, inst, (t[0], t[1], q(x) if t[0] == 1 else q(x), t[3], t[4], q(y)), orient, q(x), q(y)))

    def write(self, directory):
        os.makedirs(directory, exist_ok=True)
        L = ["magic", "tech sky130A", "magscale 1 2", "timestamp 0"]
        for layer, rs in self.rects.items():
            L.append("<< %s >>" % layer)
            for r in rs: L.append("rect %d %d %d %d" % r)
        for cn, inst, t, orient, x, y in self.uses:
            L.append("use %s %s" % (cn, inst))
            L.append("timestamp 0")
            a, b, c, d, e, f = {'R0': (1, 0, x, 0, 1, y), 'MX': (1, 0, x, 0, -1, y), 'MY': (-1, 0, x, 0, 1, y), 'R180': (-1, 0, x, 0, -1, y)}[orient]
            L.append("transform %d %d %d %d %d %d" % (a, b, c, d, e, f))
            L.append("box 0 0 1 1")
        if self.labels:
            L.append("<< labels >>")
            for layer, x1, y1, x2, y2, text, port, kind, flags in self.labels:
                L.append("flabel %s %d %d %d %d 0 FreeSans 80 0 0 0 %s" % (layer, x1, y1, x2, y2, text))
                if port is not None: L.append("port %d %s %s" % (port, flags, kind))
        L.append("<< end >>")
        open(os.path.join(directory, self.name + '.mag'), 'w').write('\n'.join(L) + '\n')
