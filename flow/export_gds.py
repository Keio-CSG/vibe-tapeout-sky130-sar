#!/usr/bin/env python3
"""Stream a local Magic hierarchy to GDS in an output directory."""
import argparse
import os
from pathlib import Path
import subprocess

def export(directory,cell):
    directory=Path(directory).resolve()
    script=directory/'export.tcl'
    script.write_text(f'addpath {{{directory}}}\nload {cell}\ngds write {cell}.gds\nquit -noprompt\n')
    rc=Path(os.environ['PDK_ROOT'])/os.environ.get('PDK','sky130A')/'libs.tech/magic'/f'{os.environ.get("PDK","sky130A")}.magicrc'
    with (directory/'export.log').open('w') as f:
        subprocess.run(['magic','-dnull','-noconsole','-rcfile',str(rc),str(script)],
                       cwd=directory,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
    if not (directory/(cell+'.gds')).exists():raise RuntimeError('No GDS produced')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory');ap.add_argument('cell')
    a=ap.parse_args();export(a.directory,a.cell)
