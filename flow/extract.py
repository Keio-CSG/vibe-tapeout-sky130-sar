#!/usr/bin/env python3
"""Reproduce each arm's published C-only extraction from its locked MAG layout."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('arm',choices=['fromscratch','fromscratch-va'])
ap.add_argument('--output',type=Path)
a=ap.parse_args();arm=ROOT/a.arm
out=(a.output or arm/'runs/pex').resolve();out.mkdir(parents=True,exist_ok=True)
va=a.arm.endswith('-va');cell='sar_adc_macro' if va else 'sar_adc_top'
layout=arm/'layout'
if va:
    flat=out/'flat';flat.mkdir(exist_ok=True)
    script=flat/'flatten.tcl'
    script.write_text(f'addpath {{{layout}}}\nload {cell}\nselect top cell\nflatten {cell}_flat\nload {cell}_flat\nsave {cell}_flat\nquit -noprompt\n')
    rc=Path(os.environ['PDKPATH'])/'libs.tech/magic'/f'{os.environ.get("PDK","sky130A")}.magicrc'
    with (flat/'flatten.log').open('w') as log:
        subprocess.run(['magic','-dnull','-noconsole','-rcfile',str(rc),str(script)],cwd=flat,
                       stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
    layout=flat;cell+='_flat'
env=dict(os.environ,WORKDIR=str(out))
subprocess.run(['bash',str(ROOT/'flow/pex.sh'),str(layout/(cell+'.mag')),cell,'c'],env=env,check=True)
net=out/(cell+'_pex_c.spice')
if va:
    subprocess.run([sys.executable,str(arm/'scripts/compact_caps.py'),str(net),str(out/'pex_c.spice')],check=True)
else:
    (out/'pex_c.spice').write_bytes(net.read_bytes())
