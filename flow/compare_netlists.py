#!/usr/bin/env python3
"""Compare extracted capacitance networks while ignoring capacitor numbering/order."""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import re

def read(path):
    other=[];caps=defaultdict(float)
    for line in re.sub(r'\n\+',' ',Path(path).read_text()).splitlines():
        f=line.split(';')[0].split()
        if not f or f[0].startswith('*'):continue
        if f[0].lower().startswith('c') and len(f)==4:
            m=re.fullmatch(r'([-+0-9.eE]+)([afpnum]?)',f[3])
            v=float(m[1])*{'':1,'a':1e-18,'f':1e-15,'p':1e-12,'n':1e-9,'u':1e-6,'m':1e-3}[m[2]]
            if v and f[1]!=f[2]:caps[tuple(sorted(f[1:3]))]+=v
        else:other.append(' '.join(f))
    return other,caps

def compare(a,b):
    oa,ca=read(a);ob,cb=read(b)
    keys=set(ca)|set(cb)
    errors=[abs(ca.get(k,0)-cb.get(k,0)) for k in keys]
    maxerr=max(errors,default=0)
    return dict(noncapacitor_lines_equal=oa==ob,capacitance_pairs_reference=len(ca),
                capacitance_pairs_generated=len(cb),max_capacitance_difference_F=maxerr,
                exact=oa==ob and maxerr<1e-25,
                rounding_tolerance_F=1e-19,
                equivalent_within_print_precision=oa==ob and set(ca)==set(cb) and maxerr<=1e-19)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('reference');ap.add_argument('generated');ap.add_argument('--output')
    a=ap.parse_args();result=compare(a.reference,a.generated);t=json.dumps(result,indent=2)+'\n'
    if a.output:Path(a.output).write_text(t)
    else:print(t)
    if not result['equivalent_within_print_precision']:raise SystemExit(1)
