#!/usr/bin/env python
"""
Collect data from runs done with run_config.py
"""

import datetime
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TMP_BASE_DIR = REPO / "tmp"

rows = []
for d in TMP_BASE_DIR.glob("*"):
    print(d)

    # Load settings info
    with open(d / "settings.json") as f:
        data = json.load(f)
    data["case_dir"] = d.as_posix()

    # Load Slurm stdout
    (slurm_stdout_p,) = d.glob("slurm-*.out")
    slurm_stdout = slurm_stdout_p.read_text()

    # Get run time from the slurm output
    tic = toc = None
    for line in slurm_stdout.splitlines():
        if line.startswith("tic=="):
            tic = datetime.datetime.fromisoformat(line.split("==")[1])
        elif line.startswith("toc=="):
            toc = datetime.datetime.fromisoformat(line.split("==")[1])
    data["run_time"] = (toc - tic).total_seconds()

    # Get mem info from the slurm output
    lines = slurm_stdout.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Peak memory usage summary:"):
            break
    else:
        raise AssertionError("Peak memory usage summary not found")
    for line in lines[i + 1 : i + 4]:
        a, b = line.split("=")
        data[f"mem_{a.strip()}"] = b.strip()

    # Load Slurm stderr
    (slurm_stderr_p,) = d.glob("slurm-*.err")
    slurm_stderr = slurm_stderr_p.read_text()

    # Check for error
    data["success"] = "srun: error: " not in slurm_stderr

    rows.append(data)

p = HERE / "data.ndjson"
if p.exists():
    while True:
        r = input(f"Overwrite {p}? [y/n]: ")
        if r == "n":
            raise SystemExit
        elif r == "y":
            break

with open(p, "w") as f:
    for data in rows:
        json.dump(data, f)
        f.write("\n")
