#!/bin/bash
# pex.sh <layout.gds|layout.mag> <cell> [mode]      mode: c (default) | rc | none
# Parasitic extraction with magic -> ngspice netlist  <WORKDIR>/<cell>_pex_<mode>.spice
#  mode c    : parasitic capacitance only (all caps kept, no resistors):
#       extract do local; extract all
#       ext2spice format ngspice; ext2spice cthresh 0; ext2spice rthresh infinity
#       ext2spice subcircuit top on; ext2spice hierarchy off; ext2spice -o ...
#  mode rc   : as above + parasitic resistors from magic's extresist:
#       extract do local; extract all
#       ext2sim labels on; ext2sim; extresist threshold 0; extresist minresist 0; extresist simplify off; extresist all
#       ext2spice extresist on; ext2spice cthresh 0; ext2spice rthresh 0   (+ same as above)
#  mode none : devices only (no parasitics; = LVS netlist, for A/B comparison)
# Prints counts of devices (X lines), parasitic resistors (R lines) and capacitors (C lines).
# Env: WORKDIR (default ./sky130_run/pex_<cell>), RTHR (extresist threshold in milliohm, default 0)
set -u
[ $# -ge 2 ] || { sed -n '2,5p' "$0"; exit 2; }
D="$(dirname "$(readlink -f "$0")")"; source "$D/_common.sh"
LAY=$(abspath "$1"); CELL="$2"; MODE=${3:-c}
W=${WORKDIR:-$PWD/sky130_run/pex_${CELL}_$MODE}; mkdir -p "$W"; cd "$W"
OUT=${CELL}_pex_$MODE.spice
{
  magic_load_snippet "$LAY" "$CELL"
  echo "select top cell"; echo "extract do local"
  case $MODE in
   c)    echo "extract all"
         echo "ext2spice lvs off"; echo "ext2spice cthresh 0"; echo "ext2spice rthresh infinity" ;;
   rc)   echo "extract all"
         echo "ext2sim labels on"; echo "ext2sim"
         echo "extresist threshold ${RTHR:-0}"; echo "extresist minresist 0"; echo "extresist simplify off"; echo "extresist all"
         echo "ext2spice lvs off"; echo "ext2spice extresist on"; echo "ext2spice cthresh 0"; echo "ext2spice rthresh 0" ;;
   none) echo "extract all"; echo "ext2spice lvs" ;;
   *) echo "bad mode $MODE" >&2; exit 2 ;;
  esac
  cat <<TCL
ext2spice format ngspice
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice -o $OUT
quit -noprompt
TCL
} > pex.tcl
magic -dnull -noconsole -rcfile "$MAGICRC" pex.tcl </dev/null > pex_magic.log 2>&1
[ -s "$OUT" ] || { echo "PEX failed, see $W/pex_magic.log"; exit 3; }
nx=$(grep -ci '^X' "$OUT" || true); nr=$(grep -ci '^R' "$OUT" || true); nc=$(grep -ci '^C' "$OUT" || true)
echo "PEX mode=$MODE devices=$nx resistors=$nr capacitors=$nc  netlist: $W/$OUT"
