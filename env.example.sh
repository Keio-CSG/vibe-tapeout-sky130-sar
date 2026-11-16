# Source from the repository root after setting PDK_ROOT.
: "${PDK_ROOT:?Set PDK_ROOT to the directory containing sky130A}"
export PDK=${PDK:-sky130A}
export PDKPATH="$PDK_ROOT/$PDK"
# Optional: export PATH="/path/to/open-tools/bin:$PATH" before sourcing.
export NGSPICE=${NGSPICE:-ngspice}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export NGTHREADS=${NGTHREADS:-1}
