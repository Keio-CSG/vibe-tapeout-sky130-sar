# Experiment protocol for these two designs

Both SAR ADCs were produced by LLM design agents from scratch, without a reference design.
Only the shared specification, open toolchain and public process documentation were available.
Existing ADC implementations were excluded. FromScratch received the specification alone.
FromScratch-VA also received the two methodology instructions in this directory.
Random mismatch and Monte Carlo qualification were out of scope.

The common milestones and checkpoint texts were:

| Milestone | Required outcome |
|---|---|
| M1 | Architecture and behavioural model meeting the specification with margin |
| M2 | Transistor schematic meeting the typical-corner targets; functional slow and fast corners |
| M3 | Full macro layout, DRC 0 and LVS match |
| M4 | Post-layout extraction and simulation |
| M5 | Final results and limitations |

**CP-A, after M3:** “Render your layout to PNG at full scale with block outlines and look at it.
Identify empty area, asymmetry in differential paths, and how the most sensitive nets are routed
(references, sampling/top plates, virtual grounds, clocks). Improve the layout and keep DRC/LVS clean.”

**CP-B, after M4:** “Explain the gap between schematic and post-layout performance with experiments
that change one thing at a time. Fix the largest contributors in the layout and re-run PEX.”

**CP-C, before closing:** “List anything that passes DRC and LVS but could still make the chip fail
or miss the spec. Check each item and fix what you can.”

The publication flow reimplements simulation using ngspice and stock open_pdks models.
Historical measurements and new reproduction measurements are identified separately.
This is a clean account of the applicable instructions; operational records are omitted.
