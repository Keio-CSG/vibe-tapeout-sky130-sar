# SAR ADC — specification (SKY130)

Design an 11-bit SAR ADC macro in SKY130 (sky130A) using only open-source tools. The targets below define the common experiment.

## Process and supplies
- PDK: sky130A, devices from `sky130_fd_pr` (1.8 V core devices; LVT allowed) and standard cells from
  `sky130_fd_sc_hd`. MIM and VPP/MOM capacitors are allowed. 5 V devices are not allowed.
- One analog supply VDDA = 1.8 V, one digital supply VDDD = 1.8 V (may be shorted), ground VSS.
- References: VREFP = 1.8 V and VREFN = 0 V come from ideal off-macro sources. **Everything inside the
  macro outline is in the extraction, including reference wiring.**
- Temperature 27 °C.

## Interface
- Fully differential input (VINP, VINN). Input common mode is chosen by the designer and stated in the report.
- One external clock CLK at fs (50 % duty). Conversion inside a period may be asynchronous.
- Digital output: 11-bit code (or raw decisions plus a documented reconstruction) and a data-valid signal.

## Performance targets

| Item | Target | Condition |
|---|---|---|
| Resolution | 11 bit | — |
| Sampling rate fs | 5.12 MS/s | — |
| Full scale | ≥ 1.4 V differential peak | designer states FS |
| SNDR | **≥ 60 dB** (relaxed from 62 dB on 2026-10-09) | post-layout (PEX), tt, noiseless transient, −1 dBFS sine |
| SFDR | **≥ 70 dB** | same |
| Power | **≤ 450 µW** | all supplies including reference current; report a breakdown |
| Walden FoM | report (≈ ≤ 50 fJ/step expected) | P / (2^ENOB · fs) |
| Area | **≤ 0.14 mm²** | macro outline |
| Corners | functional at ss and ff (schematic) | report SNDR at each |

FFT method (updated 2026-10-09):
- 256-point coherent FFT, input in bin 7 (fin = 7/256 · fs = 140 kHz), rectangular window.
- Report the window and bins used.
- Results already obtained with 512 points may be reported as well, but the spec check uses 256 points.

## Public deliverables
- Behavioural models, final schematic netlists and reproducible generation scripts.
- Final hierarchical MAG and GDS, with a rendered floorplan.
- DRC and LVS reports for the locked version, portable extraction and ngspice workflows.
- Clean design documentation, measured results and explicit qualification limits.

This public specification preserves the electrical targets and FFT method. The
introductory background and internal record-keeping deliverables have been omitted.
