"""Lossless parallel-capacitor reduction and raw coupling analysis.
The raw flow/pex.sh output is always retained for audit and LVS.
"""
from collections import defaultdict
from pathlib import Path
import re, json, sys

def value(s):
    m=re.fullmatch(r'([-+0-9.eE]+)([a-zA-Z]*)',s)
    return float(m[1])*{'':1,'a':1e-18,'f':1e-15,'p':1e-12,'n':1e-9,'u':1e-6,'m':1e-3}[m[2].lower()]

def lines(path):
    # Magic may append '; **FLOATING' to substrate capacitances. They are
    # still electrical capacitors and must be included in all analyses.
    return [line.split(';',1)[0].rstrip() for line in Path(path).read_text().replace('\n+',' ').splitlines()]

def compact(src,dst):
    groups={}; caps=defaultdict(float); other=[]
    nx=0
    for line in lines(src):
        fields=line.split()
        if not fields: continue
        if fields[0][0].lower()=='x' and 'sky130_fd_pr__cap_mim_m3_1' in fields:
            nx+=1
            key=tuple(fields[1:])
            groups[key]=groups.get(key,0)+1
        elif fields[0][0].lower()=='c' and len(fields)==4:
            caps[tuple(sorted(fields[1:3]))]+=value(fields[3])
        else: other.append(line)
    ends=[s for s in other if s.lower().startswith('.ends')]
    other=[s for s in other if not s.lower().startswith('.ends')]
    for i,(key,n) in enumerate(groups.items()):
        other.append('XMC%d '%i+' '.join(key)+' m=%d'%n)
    for i,((a,b),c) in enumerate(caps.items()):
        if a!=b and c: other.append('CPC%d %s %s %.12g'%(i,a,b,c))
    other+=ends
    Path(dst).write_text('* Parallel-identical MIMs reduced; coupling capacitors summed exactly.\n'+'\n'.join(other)+'\n')
    return dict(raw_mim_instances=nx,compact_mim_instances=len(groups),coupling_pairs=len(caps))

if __name__ == "__main__":
    print(json.dumps(compact(sys.argv[1],sys.argv[2]),indent=2))
