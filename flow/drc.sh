#!/bin/bash
# drc.sh <layout.gds|layout.mag> <cell>   -- magic DRC (style drc(full), sky130A tech)
# Prints "DRC_COUNT <n>" (total number of error tiles/rects as reported by 'drc count total'),
# writes <WORKDIR>/drc_<cell>.rpt (text, one section per rule) and exits 0 if clean, 1 otherwise.
# DRC_COUNT = number of error rectangles over the whole hierarchy (`drc listall why`), excluding rules whose
# text matches the optional regex DRC_WAIVE (e.g. DRC_WAIVE="nwell.4|LU\\.[23]" for tap-less std cells).
# Env: WORKDIR (default ./sky130_run/drc_<cell>), DRC_STYLE (default "drc(full)"), DRC_WAIVE
set -u
[ $# -ge 2 ] || { sed -n '2,6p' "$0"; exit 2; }
D="$(dirname "$(readlink -f "$0")")"; source "$D/_common.sh"
LAY=$(abspath "$1"); CELL="$2"
W=${WORKDIR:-$PWD/sky130_run/drc_$CELL}; mkdir -p "$W"; cd "$W"
STYLE=${DRC_STYLE:-drc(full)}; WAIVE=${DRC_WAIVE:-}
{
  magic_load_snippet "$LAY" "$CELL"
  cat <<TCL
select top cell
drc style $STYLE
drc euclidean on
drc check
drc catchup
set fout [open drc_$CELL.rpt w]
puts \$fout "cell $CELL  style $STYLE"
puts \$fout "--- magic per-cell error counts (hierarchical, may double count) ---"
foreach item [drc listall count] { puts \$fout \$item }
set total 0; set waived 0; set waive {$WAIVE}
puts \$fout "--- rules violated in the whole hierarchy (rule : error rectangles) ---"
foreach {why rects} [drc listall why] {
  set n [llength \$rects]
  if {\$waive ne {} && [regexp -- \$waive \$why]} { incr waived \$n; puts \$fout "WAIVED \$why : \$n" } else { incr total \$n; puts \$fout "\$why : \$n   \$rects" }
}
puts \$fout "--- total (non-waived): \$total   waived: \$waived ---"
close \$fout
puts "DRC_TOTAL=\$total"
quit -noprompt
TCL
} > drc.tcl
magic -dnull -noconsole -rcfile "$MAGICRC" drc.tcl </dev/null > drc_magic.log 2>&1
N=$(grep -o 'DRC_TOTAL=[0-9]*' drc_magic.log | tail -1 | cut -d= -f2)
[ -n "$N" ] || { echo "DRC FAILED TO RUN, see $W/drc_magic.log"; tail -5 drc_magic.log; exit 3; }
echo "DRC_COUNT $N   (report: $W/drc_$CELL.rpt)"
[ "$N" = 0 ]
