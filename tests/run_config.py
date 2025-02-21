"""
Run one or more of our config cases on Hera to test them.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG_BASE_DIR = REPO / "config"
TMP_BASE_DIR = REPO / "tmp"
INPUT_SRC_BASE_DIR = Path("/scratch1/RDARCH/rda-arl-gpu/Barry.Baker/emissions/nexus")

CONFIG_DIRS = sorted(p for p in CONFIG_BASE_DIR.glob("*") if p.is_dir())


def current_commit() -> str | None:
    import subprocess

    cmd = ["git", "-C", REPO.as_posix(), "rev-parse", "--verify", "--short", "HEAD"]
    try:
        cp = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except Exception:
        return None
    else:
        return cp.stdout.strip()


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument(
    "-c",
    "--config",
    action="append",
    help=(
        "config case to run (exact match) "
        "or a space- or comma-separated list of words that the config name contains "
        "(e.g. 'gfs megan' or gfs,megan; "
        "at least one delimiter must be present but it can be trailing, e.g. megan,). "
        "You can use -c multiple times."
    ),
)

parser.add_argument(
    "-a",
    "--all",
    action="store_true",
    help="run all config cases (overrides --config)",
)

parser.add_argument(
    "-N",
    type=int,
    default=1,
    help="number of nodes",
)

parser.add_argument(
    "-n",
    type=int,
    default=4,
    help="number of Slurm tasks",
)

args = parser.parse_args()

if args.all:
    if args.config is not None:
        print("note: ignoring --config because --all is set")

    config_inputs = [p.name for p in CONFIG_DIRS]
else:
    if args.config is None:
        parser.error("must specify --config or --all")

    config_inputs = args.config

configs_to_run = []
for config_input in config_inputs:
    # First look for exact match
    matches = [p for p in CONFIG_DIRS if p.name == config_input]
    if not matches and {",", " "}.intersection(config_input):
        # Otherwise look for parts matches if at least one delimiter
        matches = [
            p
            for p in CONFIG_DIRS
            if set(config_input.replace(",", " ").split()) <= set(p.name.split("_"))
        ]
    if not matches:
        print(f"error: no matches for {config_input!r}")
        raise SystemExit(2)
    for config in matches:
        print(f"{config_input!r} -> {config}")
        configs_to_run.append(config)


job_tpl = r"""\
#!/bin/bash
#
#SBATCH --job-name={job_name}
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
#SBATCH --nodes={nodes}
#SBATCH --ntasks={ntasks}
#SBATCH --queue=debug
#SBATCH --account=naqfc
#SBATCH --time=30:00

module use ../../modulefiles
module load ufs_hera.intel

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
echo nproc==$(nproc)==
echo OMP_NUM_THREADS==$OMP_NUM_THREADS==

echo tic==$(date -Is)==
srun ../../build/bin/nexus -c NEXUS_Config.rc -r grid_spec.nc
echo toc==$(date -Is)==
"""


TMP_BASE_DIR.mkdir(exist_ok=True)
for config in configs_to_run:
    now = datetime.datetime.now(datetime.timezone.utc)
    settings = {
        "created": now.isoformat(),
        "commit": current_commit(),
        "nodes": args.N,
        "ntasks": args.n,
    }

    # Create base directory
    suff = uuid4().hex[:7]
    tmp_dir = TMP_BASE_DIR / f"{config.name}-{suff}"
    tmp_dir.mkdir(exist_ok=False)  # or could try another suffix

    # Write info
    with open(tmp_dir / "settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    # TODO: copy rc files (optionally modifying grid and time)

    # Create needed directories
    for dn in [
        "input",
        "output",
        # "Restarts",  # for HEMCO 3.7+
    ]:
        (tmp_dir / dn).mkdir()

    # Link in the input data (all of it)
    for p in INPUT_SRC_BASE_DIR.glob("*"):
        (tmp_dir / "input" / p.name).symlink_to(p, True)

    # Link FV3 grid spec
    # /scratch2/NCEPDEV/naqfc/Jianping.Huang/Data/nexus/fix/
    # - grid_spec_793.nc
    # - grid_spec_AQM_NA_13km.nc
    (tmp_dir / "grid_spec.nc").symlink_to(
        "/scratch2/NCEPDEV/naqfc/Jianping.Huang/Data/nexus/fix/grid_spec_793.nc",
        False,
    )

    if config.name.startswith("cmaq_gfs_megan_"):
        # We need GFS_SFC_MEGAN_INPUT.nc
        # config/megan uses MERRA-2
        ...  # TODO

    # Write job script
    job = job_tpl.format(
        job_name=f"nexus-{suff}",
        nodes=args.N,
        ntasks=args.n,
    )
    with open(tmp_dir / "job.sh", "w") as f:
        f.write(job)
