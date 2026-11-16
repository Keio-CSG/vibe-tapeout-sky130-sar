# Reproduction flow

All commands run from the repository root after `. ./env.example.sh`.
The default `make drc` and `make lvs` check the locked reference artifacts.
`make layout` rebuilds into the arm's `runs/layout/` directory. To check the rebuilt
version directly, for example:

```sh
WORKDIR="$PWD/fromscratch/runs/rebuilt_drc" bash flow/drc.sh \
  fromscratch/runs/layout/sar_adc_top.gds sar_adc_top
WORKDIR="$PWD/fromscratch/runs/rebuilt_lvs" bash flow/lvs.sh \
  fromscratch/runs/layout/sar_adc_top.gds sar_adc_top \
  fromscratch/schematic/lvs_reference.spice sar_adc
```

For the other arm substitute `fromscratch-va`, `sar_adc_macro` and the LVS reference
subcircuit `sar_adc_macro`. DRC uses the full PDK rule style with no waivers. LVS
requires unique circuit equivalence and rejects property mismatches.

`extract.py` reproduces the C-only extraction, including flattening and exact parallel
capacitor compaction for FromScratch-VA. `compare_gds.py` reports the flattened XOR
area by layer. `compare_netlists.py` checks all noncapacitor lines and the summed
capacitance matrix while ignoring arbitrary capacitor numbers and ordering. It reports
exact equality separately from a 0.0001 fF extraction print-rounding tolerance; the
independent FromScratch check differed by 0.00001 fF on one pair. The
general `pex.sh` also exposes native `rc` extraction for further research; the
published performance workflow is C-only.

## Simulation and analysis

```sh
python3 flow/run_fft.py fromscratch schematic tt
python3 flow/run_fft.py fromscratch-va pex tt --samples 4 --chunk 4
python3 flow/run_fft.py fromscratch-va pex tt
```

The default is a 256-point record, coherent bin 7 (140 kHz), 5.12 MS/s, rectangular
window, 27 °C and stock TT models. The maximum transient step defaults to 25 ps
for schematic runs because of trapezoidal ringing in the dynamic comparator at 50 ps;
PEX keeps 50 ps, and the output-step request stays 50 ps for both. No mismatch or
transient noise is enabled. Both supplies and VREFP are 1.8 V, VSS/VREFN are 0 V.
The published runs use trapezoidal integration, RELTOL=1e-3, ABSTOL=1e-13 A,
VNTOL=1e-6 V and GMIN=1e-14 S. `--tmax-ps` or `make TMAX_PS=...` overrides the
model-dependent maximum step. `--method gear --reltol 1e-5` exposes a stricter
numerical control; a completed code record alone does not establish convergence
for every integration method or corner.
Input amplitudes and common modes preserve the locked arm testbenches:

| Arm | Differential peak | Declared full-scale peak | Input common mode |
|---|---:|---:|---:|
| FromScratch | 1.426 V | 1.6 V | 0.9 V |
| FromScratch-VA | 1.60434 V | 1.8 V | 0.95 V |

Both amplitudes are approximately −1 dBFS. FromScratch starts the clock high and
warms for one cycle. FromScratch-VA uses the original rising initial clock and three
warm cycles. Each chunk shifts the sine phase to retain the appropriate segment of
the same coherent record. The default is eight 32-sample chunks; `--chunk 16`
uses shorter restart segments. Chunks run sequentially by default. Warm-up is excluded
from the power integral. Chunk restart behaviour is a numerical-method uncertainty,
not an additional physical circuit correction.

Eleven outputs are thresholded at 0.9 V. FromScratch schematic codes are read at
190 ns into each cycle; PEX and FromScratch-VA use 1 ns before the next period.
Each retained sample must follow exactly one DV rising edge in the conversion
half-cycle, have DV high and have stable rail-level output bits around the strobe.
The original FromScratch-VA analysis read its held output register 150 ns after
the sampling phase; the public strobe reads the same held word earlier and also
checks completion within the specified half-cycle. This avoids relying on a later
track interval for code validity. An early-ended transient is rejected.

Power is −∫V×I dt divided by the complete retained sample duration, separately for
VDDA, VDDD, VREFP and VREFN. The total includes references. Input/clock source power
is outside this specified supply-power sum. Conversion time is nominal CLK falling
phase to the first interpolated DV crossing at 0.9 V. ENOB=(SNDR−1.76)/6.02 and
Walden FoM=P/(2^ENOB×fs).

FFT analysis removes DC, treats bin 7 as the signal, and includes every other positive
frequency bin through Nyquist in noise-plus-distortion. SFDR compares the signal to
the largest remaining bin. An incomplete or unstable record is marked invalid.
Partial smoke runs produce codes, timing and power but no FFT metrics. FromScratch
PEX reports both ordinary binary decoding and the frozen fractional reconstruction.
Schematic results use nominal binary decoding.

To use an external execution system without changing the portable source:

```sh
python3 flow/run_fft.py fromscratch schematic tt --prepare
# In each generated cNNN directory, run: ngspice -b -o ngspice.log tb.spice
python3 flow/run_fft.py fromscratch schematic tt --collect
```

Keep each deck's adjacent `.spiceinit`, run from its directory, and retain the complete
record. The collector accepts only the plan associated with those decks. `result.json`
and `codes.csv` are small; waveform and extraction scratch files belong in `runs/`.
