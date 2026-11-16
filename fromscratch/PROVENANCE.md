# Artifact provenance

The locked version is C20G. The reference GDS SHA256 is
`2b81d91a60995599a2e70c99e6591c7d399fefb8da1fc274217e6a7107778725`.
The published GDS is the original stream after decompression, without geometry edits.

| Published material | Generator or frozen-artifact status |
|---|---|
| `schematic/sar_adc_m3.spice` | `scripts/gen_m3_netlist.py`, using `p_M3.json`, `spicegen.py`, `comp_def.py` |
| `schematic/lvs_reference.spice` | Unit-MIM form of that generator, then `scripts/layout/lib/flatten.py` with stock standard cells |
| `schematic/C20G_RECONSTRUCTION.json` | Frozen physical-capacitance coefficients; original model-location metadata omitted |
| `schematic/c20g_decoder.py` | Frozen decoder source using those coefficients |
| `layout/sar_adc_top.mag` | Frozen final top routing, placement and supply geometry |
| `layout/{cdac_p,cdac_n,dig,drv_p,drv_n,analog,cmp_half_a,cmp_half_b}.mag` | Original `scripts/layout/` generators; replayed inside the frozen top routing |
| Other child MAG files | Frozen PDK device/cell geometry cache required by the top hierarchy |
| `layout/sar_adc_top.gds` | Frozen stream from the locked hierarchy; `flow/export_gds.py` regenerates matching geometry |
| `layout/floorplan.png` | `flow/render.py` from the locked GDS |
| `verify/pex_c.spice` | Frozen small C-only extraction; `flow/extract.py` reproduces the electrical network |
| `verify/original_*` | Frozen final DRC/LVS evidence; internal file-location text removed |
| `verify/reproduced_*` | Fresh-copy `flow/drc.sh` / `flow/lvs.sh` evidence, with run locations removed |
| `model/sar_model.py` | Frozen original behavioural source, with publication naming cleanup |
| `results/original.json` | Whitelisted electrical numbers from locked design-time results; invalid SS spectrum explicitly marked |
| `results/probe_aliases.json` | Frozen topology-matched internal-node aliases for schematic and C-only extraction |
| `results/schematic_tt_diagnosis.json` / `.csv` | Frozen ngspice-only short-probe evidence; prepared using `flow/probe_fromscratch.py`, with diagnostic controls explicitly identified |
| `results/schematic_tt_diagnosis.png` | `flow/plot_schematic_diagnosis.py` from the compact frozen CSV |
| Other `results/` files | Public flow measurements and comparison outputs; see each JSON's scope |

The publication changes comments and locations, removes bundled model includes and
uses stock models in the run decks. Schematic regeneration reproduced all active
circuit lines. Seeded layout regeneration produced zero geometric XOR on every
layer, with the same 40 cells and outline. The regenerated C-only network matches
all noncapacitor lines. An independent clean rerun differed by 0.00001 fF on one
7.74011 fF wire-capacitance pair (extraction print rounding); the first rerun matched
every capacitance exactly. Capacitor numbers and ordering can also differ. Large full-RC data and later candidate
layouts are outside this minimal distribution.

The regenerated GDS stream differs only in library/cell timestamp records. After
zeroing those fields it is byte-identical to the reference, including labels and
properties. The unchanged original stream remains the publication reference.
