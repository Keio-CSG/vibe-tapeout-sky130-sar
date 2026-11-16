# Reproduction environment

The checked environment on 2026-11-16 used the following versions:

| Component | Version |
|---|---|
| Magic | 8.3.685 |
| Netgen | 1.5.324 |
| ngspice | 47, built with KLU |
| Yosys | 0.44, git `80ba43d26` (recorded for provenance; not needed by final targets) |
| Python | 3.12.13 |
| NumPy / Matplotlib | 2.5.3 / 3.11.2 |
| gdstk / KLayout Python | 1.0.1 / 0.30.12 |
| open_pdks / Volare build | `0fe599b2afb6708d281543108caf8310912f54af` |

The installed `sky130A/SOURCES` contains exactly:

```text
open_pdks 0fe599b2afb6708d281543108caf8310912f54af
```

The same identifier is the selected Volare `sky130/versions/` directory.
No separate Volare client version is recorded by that installed PDK tree.
Use this build for exact geometry reproduction. Other tool or PDK revisions may
change extraction, device generator geometry or numerical results.

Install open-source Magic, Netgen and ngspice, and obtain the pinned sky130A build
through [Volare](https://volare.readthedocs.io/) or build the matching
[open_pdks](http://opencircuitdesign.com/open_pdks/) revision.
For example, with a Volare installation:

```sh
export PDK_ROOT="$PWD/pdk"
volare enable --pdk sky130 0fe599b2afb6708d281543108caf8310912f54af
```

The required files are `sky130A/libs.tech/ngspice/sky130.lib.spice`,
`sky130A/libs.tech/magic/sky130A.magicrc`,
`sky130A/libs.tech/netgen/sky130A_setup.tcl`, and the `sky130_fd_sc_hd`
SPICE and MAG libraries in `libs.ref/`. PDK models are supplied by that installation,
not copied into this repository.

Create a Python environment and install the pinned dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export PDK_ROOT="$PWD/pdk"
. ./env.example.sh
```

Put the open tool executables on `PATH`. A source-built Magic/Netgen installation
may also need its own Tcl/Tk and shared-library environment; follow that installation's
instructions. The public scripts never infer a private installation location.

ngspice initialization is written inside each run directory. It selects the stock PDK
parsing switches, one device-evaluation thread and the KLU solver. See the
[official ngspice application notes](https://ngspice.sourceforge.io/applic.html) for
the SKY130 setup. Use `--solver sparse` if a build lacks KLU; expect longer runs.
There is no global initialization-file modification.
