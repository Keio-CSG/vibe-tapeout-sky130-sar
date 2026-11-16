#!/usr/bin/env python3
"""Regenerate the locked schematic, including a unit-capacitor LVS reference."""
from pathlib import Path
import os
import subprocess
import sys
import argparse

HERE=Path(__file__).resolve().parent
ARM=HERE.parent
ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,default=ARM/'runs/schematic')
a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,SAR_PARAMS=str(HERE/'p_M3.json'),SAR_OUT=str(out))
subprocess.run([sys.executable,str(HERE/'gen_m3_netlist.py')],env=env,check=True)
subprocess.run([sys.executable,str(HERE/'layout/lib/flatten.py'),str(out/'sar_adc_m3_units.spice'),
                'sar_adc',str(out/'lvs_reference.spice')],check=True)
