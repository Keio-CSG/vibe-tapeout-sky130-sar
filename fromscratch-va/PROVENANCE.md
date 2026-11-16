# Artifact provenance

The locked version is the reset-buffer and top-shunt design. Reference GDS SHA256:
`017fa9500d027441cfad2d3ed8a4901e71439ee7dd80983e033985cd108a8259`.
The published stream is unchanged after decompression.

| Published material | Generator or frozen-artifact status |
|---|---|
| Five `schematic/{cdac,comparator,sar_logic,sar_adc,sar_adc_all}.spice` files | `scripts/gen_adc.py`, `gen_comp.py`, then the six-per-side shunt addition in `generate_schematic.py` |
| `schematic/lvs_reference.spice` | Frozen actual-drawn-device reference, assembled from block references by `scripts/layout/gen_top.py` |
| `layout/sar_logic_core.mag` | Frozen selected routed logic seed; no new routing search is required |
| `layout/{cdac_core,bank_side,comparator_core,sar_adc_macro}.mag` | Original `scripts/layout/gen_*.py` and selected settings in `generate_layout.py` |
| Other child MAG files | Frozen PDK device/cell geometry cache used by the selected hierarchy |
| `scripts/layout/*/{meta.json,*_ref.spice}` | Frozen block interfaces/references needed by the seeded rebuild; regenerated blocks overwrite their own references |
| `layout/sar_adc_macro.gds` | Frozen locked stream; `flow/export_gds.py` regenerates identical geometry |
| `layout/floorplan.png` | `flow/render.py` from the locked GDS |
| `verify/pex_c.spice` | Frozen physical-flattened C extraction compacted by `scripts/compact_caps.py` |
| `verify/original_*` | Frozen final DRC/LVS evidence with internal locations removed |
| `verify/reproduced_*` | Fresh-copy `flow/drc.sh` / `flow/lvs.sh` evidence with run locations removed |
| `model/fm_blocks.va` | Frozen original functional block models, retained as design source |
| `results/original.json` | Whitelisted locked design-time electrical results |
| Other `results/` files | Public reproduction measurements and comparison outputs |

All five regenerated schematic components match the active lines of the locked
netlists. Seeded layout regeneration produced zero flattened XOR on every layer,
with the same 63 cells and outline. Fresh flattened extraction and exact parallel
capacitor compaction reproduce all noncapacitor lines and every summed capacitance
exactly. Arbitrary capacitor names and ordering may change. `MANIFEST.json` in the
repository root records the published file hashes. This distribution retains the
locked C-only scope; it does not add a full-RC signoff claim.

The regenerated GDS stream differs only in library/cell timestamp records. After
zeroing those fields it is byte-identical to the reference, including labels and
properties. The unchanged original stream remains the publication reference.
