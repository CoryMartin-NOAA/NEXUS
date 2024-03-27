"""
Extract a small spatial subset from larger inputs.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).parent
IN_BASE = Path("~/downloads/gocart-nexus").expanduser()
OUT_BASE = HERE / "data"


# NCWCP
latc, lonc = 38.9721, -76.9245
loc_name = "ncwcp"

# Grid settings
nx = ny = 3  # HEMCO grid
dxy = 0.1
assert nx % 2 == 1 and ny % 2 == 1, "nx and ny must be odd"
ne = 1  # edge

s_dxy = f"{dxy:.3g}".replace(".", "")
case_id = f"{loc_name}_anthro_{s_dxy}x{s_dxy}_nx={nx}_ny={ny}_ne={ne}"
case_dir = OUT_BASE / case_id
case_dir.mkdir(exist_ok=True)
(case_dir / "data").mkdir(exist_ok=True)

# Round center to nearest HTAP grid point, which 0.1 deg but on the 0.05s
print("original center:", latc, lonc)
r = 1 / dxy
latc_u = round(latc * r - dxy / 2) / r + dxy / 2
latc_d = round(latc * r + dxy / 2) / r - dxy / 2
lonc_u = round(lonc * r - dxy / 2) / r + dxy / 2
lonc_d = round(lonc * r + dxy / 2) / r - dxy / 2
if abs(latc - latc_u) < abs(latc - latc_d):
    latc = latc_u
else:
    latc = latc_d
if abs(lonc - lonc_u) < abs(lonc - lonc_d):
    lonc = lonc_u
else:
    lonc = lonc_d
latc = round(latc, 3)
lonc = round(lonc, 3)
lonc = (lonc + 180) % 360 - 180  # ensure [-180, 180)

# Rectangular grid
latv = np.arange(
    latc - (ny - 1 + ne * 2) / 2 * dxy,
    latc + (ny - 1 + ne * 2) / 2 * dxy + dxy,
    dxy,
)[:ny + ne * 2]
lonv = np.arange(
    lonc - (nx - 1 + ne * 2) / 2 * dxy,
    lonc + (nx - 1 + ne * 2) / 2 * dxy + dxy,
    dxy,
)[:nx + ne * 2]
latv = np.round(latv, 3)
lonv = np.round(lonv, 3)
assert latv.size == ny + ne * 2 and lonv.size == nx + ne * 2
print("rounded center:", latc, lonc)
print("lat:", latv)
print("lon:", lonv)
lonv_360 = np.mod(lonv, 360)


# We need these config files
# Only grid file, is used to set the HEMCO grid,
# should need to be adjusted
# - HEMCO_Config.rc
# - HEMCO_sa_Diagn.rc
# - HEMCO_sa_Grid.rc
# - HEMCO_sa_Spec.rc
# - HEMCO_sa_Time.rc

rc_files = sorted(IN_BASE.glob("*.rc"))
s_files = "\n".join(f"- {p.name}" for p in rc_files)
print(f"Found:\n{s_files}")

for desc, fn in {
    "main config": "HEMCO_Config.rc",
    "diagnostic definitions": "HEMCO_sa_Diagn.rc",
    # "grid definition": "HEMCO_sa_Grid.rc",
    "species definitions": "HEMCO_sa_Spec.rc",
    "simulation time settings": "HEMCO_sa_Time.rc",
}.items():
    p_in = IN_BASE / fn
    if p_in.is_file():
        print(f"Copying {desc} from {p_in.relative_to(IN_BASE).as_posix()}")
        shutil.copy(p_in, case_dir / fn)


# Create HEMCO grid spec
# The MIN/MAX correspond to outer grid cell edges
# HEMCO computes the spacing as (MAX - MIN) / N
# Example (global):
# > cat HEMCO_sa_Grid.rc
# # Emission grid specifications:
# XMIN: -180.0
# XMAX:  180.0
# YMIN: -90.0
# YMAX:  90.0
# NX: 3600
# NY: 1800
# NZ: 1

xmin = lonv[ne] - dxy / 2
xmax = lonv[-1 - ne] + dxy / 2
ymin = latv[ne] - dxy / 2
ymax = latv[-1 - ne] + dxy / 2

fmt = ">9.4f"

s_hemco_grid_spec = f"""\
# Emission grid specifications:
XMIN: {xmin:{fmt}}
XMAX: {xmax:{fmt}}
YMIN: {ymin:{fmt}}
YMAX: {ymax:{fmt}}
NX: {nx}
NY: {ny}
NZ: 1
"""
sep = "-" * 31
print("Writing HEMCO grid spec:")
print(sep)
print(s_hemco_grid_spec, end="")
print(sep)
print("to", case_dir / "HEMCO_sa_Grid.rc")
with open(case_dir / "HEMCO_sa_Grid.rc", "w") as f:
    f.write(s_hemco_grid_spec)


for p in IN_BASE.glob("data/*.nc"):
    print(p.relative_to(IN_BASE).as_posix())

    if "grid_spec" in p.name:  # grid_xt, etc., just for regridding
        continue  # FIXME

    ds = xr.open_dataset(p)

    if "HTAP" in p.name:
        # Exact selection
        sel = ds.sel(lat=latv, lon=lonv_360)
        print("- lat exact:", sel.lat.values)
        print("- lon exact:", sel.lon.values)
    else:
        sel = ds.sel(lat=latv, lon=lonv, method="nearest")
        print("- lat nearest:", sel.lat.values)
        print("- lon nearest:", sel.lon.values)

    # Replace lat/lon
    u_lat = sel.lat.units
    u_lon = sel.lon.units
    sel = sel.assign_coords(lat=latv, lon=lonv)
    sel["lat"].attrs.update(units=u_lat)
    sel["lon"].attrs.update(units=u_lon)

    print("- lat:", sel.lat.values)
    print("- lon:", sel.lon.values)

    p_out = case_dir / "data" / p.name
    print("->(sel)", p_out.as_posix())
    encoding = {k: {"zlib": True, "complevel": 3} for k in sel.data_vars}
    sel.to_netcdf(p_out, encoding=encoding)
