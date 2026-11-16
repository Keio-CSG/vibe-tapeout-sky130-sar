set -euo pipefail
: "${PDK_ROOT:?Source env.example.sh first}"
export PDK=${PDK:-sky130A}
export PDKPATH="$PDK_ROOT/$PDK"
MAGICRC="$PDKPATH/libs.tech/magic/$PDK.magicrc"
NETGEN_SETUP="$PDKPATH/libs.tech/netgen/${PDK}_setup.tcl"
abspath() { python3 -c 'import os,sys;print(os.path.abspath(sys.argv[1]))' "$1"; }
magic_load_snippet() {
  local f="$1" c="$2"
  case "$f" in
    *.gds|*.gds.gz) printf 'gds readonly true\ngds flatten false\ngds read {%s}\nload %s\n' "$f" "$c" ;;
    *.mag) printf 'addpath {%s}\nload %s\n' "$(dirname "$f")" "$c" ;;
    *) echo 'Expected GDS or MAG' >&2; return 2 ;;
  esac
}
