#!/usr/bin/env python3
"""Prepare three-cycle TT comparator probes without changing the ADC or stimulus.

Examples (run from the repository root, after setting the PDK environment):
  python flow/probe_fromscratch.py schematic --index 64 --output fromscratch/runs/probe64
  cd fromscratch/runs/probe64/c000
  ngspice -b -o ngspice.log tb.spice

Repeat with model pex to probe equivalent extracted nodes. --tmax-ps changes
only the maximum integration step, for diagnosis; the output request stays 50 ps.
These windows are not full FFTs and do not replace the canonical result records.
"""
import argparse
import json
from pathlib import Path
import run_fft

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('model',choices=['schematic','pex'])
p.add_argument('--index',type=int,choices=range(255),default=0,metavar='0..254')
p.add_argument('--tmax-ps',type=float,default=None,
               help='Default: schematic 25 ps, PEX 50 ps; use 50 for the frozen failure window')
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
if a.tmax_ps is None:a.tmax_ps=25 if a.model=='schematic' else 50
if a.tmax_ps<=0:p.error('Maximum step must be positive')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
args=argparse.Namespace(arm='fromscratch',model=a.model,corner='tt',samples=2,chunk=2,
                       tmax_ps=a.tmax_ps,solver='klu',method='trap',reltol=1e-3)
run_fft.prepare(args,out)
d=out/'c000';deck=(d/'tb.spice').read_text()
phase=360*7*(a.index-1)/256
oldphase=360*7*(-1)/256
deck=deck.replace(f'0 0 {oldphase:.15g})',f'0 0 {phase:.15g})')
mapping=json.loads((run_fft.ROOT/'fromscratch/results/probe_aliases.json').read_text())
extra=['v(vinp)','v(vinn)']+[f'v(xdut.{v if a.model=="pex" else k})' for k,v in mapping.items()]
lines=[]
for line in deck.splitlines():
 if line.startswith('.save ') or line.startswith('wrdata wave.dat '):line+=' '+' '.join(extra)
 lines.append(line)
(d/'tb.spice').write_text('\n'.join(lines)+'\n')
(out/'diagnostic.json').write_text(json.dumps({'index':a.index,'model':a.model,'tmax_ps':a.tmax_ps,
 'scope':'one warm-up plus two retained cycles; diagnostic only','extra_probe_order':['vinp','vinn']+list(mapping)},indent=2)+'\n')
print(d/'tb.spice')
