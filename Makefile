SHELL := /bin/bash
ARM ?= fromscratch
CORNER ?= tt
MODEL ?= schematic
TMAX_PS ?= $(if $(filter schematic,$(MODEL)),25,50)
PYTHON ?= python3
TOP = $(if $(filter fromscratch-va,$(ARM)),sar_adc_macro,sar_adc_top)
SUB = $(if $(filter fromscratch-va,$(ARM)),sar_adc_macro,sar_adc)

.PHONY: help schematic layout drc lvs pex fft smoke model render compare fromscratch fromscratch-va
help:
	@echo 'make ARM=fromscratch|fromscratch-va schematic|layout|drc|lvs|pex|fft|smoke|model|render|compare'
	@echo 'Simulation: MODEL=schematic|pex CORNER=tt|ss|ff. Outputs go to ARM/runs/.'
schematic:
	$(PYTHON) $(ARM)/scripts/generate_schematic.py
layout:
	$(PYTHON) $(ARM)/scripts/generate_layout.py
drc:
	WORKDIR="$(CURDIR)/$(ARM)/runs/drc_mag" bash flow/drc.sh $(ARM)/layout/$(TOP).mag $(TOP)
	WORKDIR="$(CURDIR)/$(ARM)/runs/drc_gds" bash flow/drc.sh $(ARM)/layout/$(TOP).gds $(TOP)
lvs:
	WORKDIR="$(CURDIR)/$(ARM)/runs/lvs_mag" bash flow/lvs.sh $(ARM)/layout/$(TOP).mag $(TOP) $(ARM)/schematic/lvs_reference.spice $(SUB)
	WORKDIR="$(CURDIR)/$(ARM)/runs/lvs_gds" bash flow/lvs.sh $(ARM)/layout/$(TOP).gds $(TOP) $(ARM)/schematic/lvs_reference.spice $(SUB)
pex:
	$(PYTHON) flow/extract.py $(ARM)
fft:
	$(PYTHON) flow/run_fft.py $(ARM) $(MODEL) $(CORNER) --tmax-ps $(TMAX_PS)
smoke:
	$(PYTHON) flow/run_fft.py $(ARM) $(MODEL) $(CORNER) --tmax-ps $(TMAX_PS) --samples 4 --chunk 4 --output $(ARM)/runs/$(MODEL)_$(CORNER)_smoke
model:
	$(PYTHON) flow/behavioural.py $(ARM)
render:
	@mkdir -p $(ARM)/runs
	$(PYTHON) flow/render.py $(ARM)/layout/$(TOP).gds $(TOP) $(ARM)/runs/floorplan.png
compare:
	$(PYTHON) flow/compare_gds.py $(ARM)/layout/$(TOP).gds $(ARM)/runs/layout/$(TOP).gds $(TOP) --output $(ARM)/runs/geometry_comparison.json
	$(PYTHON) flow/compare_netlists.py $(ARM)/verify/pex_c.spice $(ARM)/runs/pex/pex_c.spice --output $(ARM)/runs/extraction_comparison.json
fromscratch:
	$(MAKE) ARM=fromscratch schematic layout drc lvs pex compare
fromscratch-va:
	$(MAKE) ARM=fromscratch-va schematic layout drc lvs pex compare
