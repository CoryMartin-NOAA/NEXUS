"""
Run one or more of our config cases on Hera to test them.
"""

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG_BASE_DIR = REPO / "config"
TMP_BASE_DIR = REPO / "tmp"

config_dirs = sorted(p for p in CONFIG_BASE_DIR.glob("*") if p.is_dir())

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument(
    "-c",
    "--config",
    nargs="+",
)

parser.add_argument(
    "-a",
    "--all",
    action="store_true",
    help="run all config cases (overrides --config)",
)

args = parser.parse_args()

if args.all:
    if args.config is not None:
        print("note: ignoring --config because --all is set")

    config_inputs = [p.name for p in config_dirs]
else:
    if args.config is None:
        parser.error("must specify --config or --all")

    config_inputs = args.config

for config_input in config_inputs:
    # First look for exact match
    matches = [p for p in config_dirs if p.name == config_input]
    if not matches:
        # Otherwise look for parts matches
        matches = [
            p
            for p in config_dirs
            if set(config_input.replace("_", " ").split()) <= set(p.name.split("_"))
        ]
    if not matches:
        print(f"error: no matches for {config_input!r}")
        raise SystemExit(2)
    elif len(matches) > 1:
        print(f"error: multiple matches for {config_input!r}:")
        for match in matches:
            print(f"- {match}")
        raise SystemExit(2)
    (config,) = matches
    print(f"{config_input!r} -> {config}")
