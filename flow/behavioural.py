#!/usr/bin/env python3
"""Portable, noiseless architecture check. Historical detailed models are in model/."""
import argparse
import importlib.util
from pathlib import Path
import json
import numpy as np
from run_fft import spectrum

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('arm',choices=['fromscratch','fromscratch-va']);a=ap.parse_args()
if a.arm=='fromscratch':
    spec=importlib.util.spec_from_file_location('sar_model',ROOT/a.arm/'model/sar_model.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    _,codes=m.run(N=256,Cu=19.96225e-15,Cp=0,sig_u=0,vos=0,vn=0,ktc=False)
else:
    # Ideal steady charge redistribution for the bottom-plate-sampled array.
    # Added linear TOP loads affect gain, not ideal binary capacitor ratios.
    v=1.60434*np.sin(2*np.pi*7*(np.arange(256)+3.5)/256)
    codes=np.clip(np.floor(v/1.8*1024+1024),0,2047).astype(int)
out=ROOT/a.arm/'runs/model';out.mkdir(parents=True,exist_ok=True)
(out/'result.json').write_text(json.dumps(dict(samples=256,bin=7,scope='ideal architecture only; no mismatch or transistor timing',**spectrum(codes)),indent=2)+'\n')
print((out/'result.json').read_text())
