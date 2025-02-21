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

    # Load Slurm stdout
    (slurm_output_p,) = d.glob("slurm-*.out")
    slurm_output = slurm_output_p.read_text()

    # Get run time from the slurm output
    tic = toc = None
    for line in slurm_output.splitlines():
        if line.startswith("tic=="):
            tic = datetime.datetime.fromisoformat(line.split("==")[1])
        elif line.startswith("toc=="):
            toc = datetime.datetime.fromisoformat(line.split("==")[1])
    data["run_time"] = (toc - tic).total_seconds()

    # Get mem info from the slurm output
    lines = slurm_output.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Peak memory usage summary:"):
            break
    else:
        raise AssertionError("Peak memory usage summary not found")
    for line in lines[i + 1 : i + 4]:
        a, b = line.split("=")
        data[f"mem_{a.strip()}"] = b.strip()

    rows.append(data)

with open(HERE / "data.ndjson", "w") as f:
    for data in rows:
        json.dump(data, f)
        f.write("\n")
