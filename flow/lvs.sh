#!/bin/bash
# lvs.sh <layout.gds|layout.mag> <cell> <schematic.spice> <subckt>
# 1) magic: load layout, `extract all`, `ext2spice lvs` -> <WORKDIR>/<cell>.lvs.spice (flat, LVS mode: no parasitics)
# 2) netgen: lvs "<cell>.lvs.spice <cell>" "<schematic.spice> <subckt>" with the PDK setup file
#    $PDKPATH/libs.tech/netgen/sky130A_setup.tcl ; log in <WORKDIR>/lvs_<cell>.log
# Prints "LVS MATCH" or "LVS MISMATCH"; exit 0 on match, 1 on mismatch, 3 on tool failure.
# Env: WORKDIR (default ./sky130_run/lvs_<cell>)
set -u
[ $# -ge 4 ] || { sed -n '2,8p' "$0"; exit 2; }
D="$(dirname "$(readlink -f "$0")")"; source "$D/_common.sh"
LAY=$(abspath "$1"); CELL="$2"; SCH=$(abspath "$3"); SUB="$4"
W=${WORKDIR:-$PWD/sky130_run/lvs_$CELL}; mkdir -p "$W"; cd "$W"
{
  magic_load_snippet "$LAY" "$CELL"
  cat <<TCL
select top cell
extract do local
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice format ngspice
ext2spice -o $CELL.lvs.spice
quit -noprompt
TCL
} > extract.tcl
magic -dnull -noconsole -rcfile "$MAGICRC" extract.tcl </dev/null > extract_magic.log 2>&1
[ -s "$CELL.lvs.spice" ] || { echo "LVS: extraction failed, see $W/extract_magic.log"; exit 3; }
cat > run_netgen.tcl <<TCL
lvs "$CELL.lvs.spice $CELL" "$SCH $SUB" $NETGEN_SETUP lvs_$CELL.log -json
quit
TCL
netgen -batch source run_netgen.tcl > netgen_stdout.log 2>&1
[ -s "lvs_$CELL.log" ] || { echo "LVS: netgen failed, see $W/netgen_stdout.log"; exit 3; }
if grep -q "Circuits match uniquely" "lvs_$CELL.log" && ! grep -qiE "property errors|do not match|mismatch|Top level cell failed" "lvs_$CELL.log"; then
  echo "LVS MATCH   ($(grep -c . lvs_$CELL.log) log lines: $W/lvs_$CELL.log)"; exit 0
else
  echo "LVS MISMATCH   (see $W/lvs_$CELL.log)"; grep -iE "mismatch|do not match|property errors|delta=|Netlists" "lvs_$CELL.log" | head -5; exit 1
fi
