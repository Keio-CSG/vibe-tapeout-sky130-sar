# Two SKY130 SAR ADCs from scratch

This repository contains two 11-bit SAR ADCs produced by LLM design agents from scratch, without a reference design.
Both used the same SKY130 specification and open physical-design tools.
FromScratch received the specification alone.
FromScratch-VA also received a functional-model/block-test method and a floorplan/block-extraction method.
The public reproduction flow uses only ngspice, Magic, Netgen and Python with stock open_pdks sky130A models.

Paper: K. Yoshioka, "The Era of Vibe Tapeout: Dark Age or Golden Age for Analog Circuit Design?",
[arXiv:2610.15240](https://arxiv.org/abs/2610.15240), 2026 (see [Citation](#citation)).
Code and included geometry: Apache-2.0; the PDK is obtained separately.
Random mismatch and Monte Carlo qualification were out of scope.

## Locked versions and original results

These are verified design-time records, not new ngspice measurements. The locked reference GDS is preserved.

| Arm | Locked scope | Original PEX TT SNDR / SFDR | Power | Area | Status |
|---|---|---:|---:|---:|---|
| [FromScratch](fromscratch/) | C20G; full-RC result with fixed fractional decoding | 61.800 / 71.166 dB | 384.077 µW | 0.099745 mm² | **Signoff not reached**; SS incomplete, FF fails |
| [FromScratch-VA](fromscratch-va/) | Buffered reset + matched top shunts; C-only PEX | 61.952 / 75.398 dB | 307.744 µW | 0.055498 mm² | **Original C-only signoff reached**, TT/SS/FF; full-RC FFT incomplete |

Both locked layouts and their seeded rebuilds pass full-rule Magic DRC with zero errors and exact Netgen LVS,
on native MAG and streamed GDS. Both rebuilt GDS files have zero geometric XOR against the locked references; stream bytes differ only in timestamps.
Fresh extraction preserves every device and capacitance pair. One independent FromScratch rerun differs by
0.00001 fF on one 7.74011 fF wire-capacitance pair; VA matches exactly. Capacitor numbering/order may change.
See each arm's `results/`, [provenance](fromscratch/PROVENANCE.md),
[VA provenance](fromscratch-va/PROVENANCE.md) and `verify/` evidence.
Passing DRC/LVS and C-only tests is not silicon or voltage-reliability qualification.

## Public ngspice reproduction

All complete rows use 256 coherent points, bin 7, 5.12 MS/s, a rectangular window
and 27 °C. Schematic maximum step is 25 ps; C-only PEX uses 50 ps.

| Arm | Model | SNDR dB | SFDR dB | Total µW | Max conversion ns | Valid conversions |
|---|---|---:|---:|---:|---:|---|
| fromscratch | Schematic TT | 64.942 | 74.104 | 257.879 | 55.046 | 256/256 |
| fromscratch | C-only PEX TT | 62.837 | 72.553 | 386.976 | 89.368 | 256/256 |
| fromscratch-va | Schematic TT | 65.970 | 78.850 | 196.209 | 37.937 | 256/256 |
| fromscratch-va | C-only PEX TT | 62.030 | 75.201 | 307.988 | 66.242 | 256/256 |

Historical schematic TT SNDR/SFDR values were 64.969/72.702 dB for FromScratch
and 65.841/79.232 dB for FromScratch-VA. An ngspice step-size artefact at 50 ps
caused trapezoidal ringing in the FromScratch dynamic comparator; 25 ps resolves
it in the full 256-point TT record. Only the numerical maximum step changed;
the circuit, sizing, timing, stimulus and frozen decoder are unchanged.
The [diagnostic waveform](fromscratch/results/schematic_tt_diagnosis.png) records
the failure mechanism and short controls.

FromScratch's historical PEX row uses full RC, while the public run is C-only;
these have different extraction scope. Physical and all-corner qualification
limits remain in the design notes. See [VALIDATION.md](VALIDATION.md) for the
historical/new values and measured run times.

## Quick start

Install the pinned tools and PDK described in [tools/INSTALL.md](tools/INSTALL.md), then:

```sh
git clone https://github.com/keio-csg/vibe-tapeout-sky130-sar.git
cd vibe-tapeout-sky130-sar
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export PDK_ROOT="$PWD/pdk"   # directory containing sky130A
. ./env.example.sh
make ARM=fromscratch model schematic layout drc lvs pex compare
make ARM=fromscratch MODEL=schematic CORNER=tt fft
make ARM=fromscratch MODEL=pex CORNER=tt smoke
make ARM=fromscratch MODEL=pex CORNER=tt fft
```

Use `ARM=fromscratch-va` for the other design. Use `CORNER=ss` or `ff` for the other schematic/PEX corners.
The `layout` target uses explicitly documented frozen routing seeds and cached device geometry.
`drc` and `lvs` check the locked reference. See [flow/README.md](flow/README.md) for rebuilt-layout checks,
deck-only preparation, collection, FFT definitions and output timing. All generated outputs go to `ARM/runs/`.

## Repository map

- `spec/`: electrical specification; `protocol/`: milestones, CP-A/B/C and the two VA methods.
- `flow/`: stock-PDK simulation, DRC/LVS/extraction, rendering and comparison programs.
- Each arm: clean design notes, original behavioural source, portable generators, locked schematic/MAG/GDS,
  small C-only PEX, final verification evidence and compact result summaries.
- `MANIFEST.json`: SHA256 hashes of the publication files.

Later candidate layouts, operational records, waveforms and large extraction scratch files are excluded.
Full-RC reproduction, broader static/noise/voltage qualification and package integration remain research tasks.

## Expected run times

| Arm | Model | Elapsed wall time | Sum of chunk wall times | Valid conversions |
|---|---|---:|---:|---:|
| fromscratch | schematic TT | 32.12 min | 251.77 min | 256/256 |
| fromscratch | pex TT | 32.64 min | 213.59 min | 256/256 |
| fromscratch-va | schematic TT | 39.60 min | 311.68 min | 256/256 |
| fromscratch-va | pex TT | 58.73 min | 225.70 min | 256/256 |

The sum column estimates sequential execution on comparable hardware. Physical
regeneration and checks took about 34 s / 81 s. Exact times depend on the tool
build, solver, input segment and computer; start with the smoke target.

## Citation

If you use this repository, please cite:

```bibtex
@misc{yoshioka2026vibetapeout,
  title         = {The Era of Vibe Tapeout: Dark Age or Golden Age for Analog Circuit Design?},
  author        = {Yoshioka, Kentaro},
  year          = {2026},
  eprint        = {2610.15240},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AR},
  doi           = {10.48550/arXiv.2610.15240},
  url           = {https://arxiv.org/abs/2610.15240}
}
```
