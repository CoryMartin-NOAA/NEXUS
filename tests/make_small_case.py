"""
Extract a small spatial subset from larger inputs.
"""
from __future__ import annotations

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
nx = ny = 3
dxy = 0.1

case_id = f"{loc_name}_anthro_01x01_nx={nx}_ny={ny}"

assert nx % 2 == 1 and ny % 2 == 1, "nx and ny must be odd"

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

# Rectangular grid
latv = np.arange(latc - (ny - 1) / 2 * dxy, latc + (ny - 1) / 2 * dxy + dxy, dxy)[:ny]
lonv = np.arange(lonc - (nx - 1) / 2 * dxy, lonc + (nx - 1) / 2 * dxy + dxy, dxy)[:nx]
assert latv.size == ny and lonv.size == nx
print("rounded center:", latc, lonc)
print("lat:", latv)
print("lon:", lonv)


# We need these config files
# Only grid file, is used to set the HEMCO grid,
# should need to be adjusted
# - HEMCO_Config.rc
# - HEMCO_sa_Diagn.rc
# - HEMCO_sa_Grid.rc
# - HEMCO_sa_Spec.rc
# - HEMCO_sa_Time.rc

print(*sorted(IN_BASE.glob("*.rc")), sep="\n")

# Create HEMCO grid spec
# Example:
# > cat HEMCO_sa_Grid.rc
# # Emission grid specifications:
# XMIN: -180.0
# XMAX:  180.0
# YMIN: -90.0
# YMAX:  90.0
# NX: 3600
# NY: 1800
# NZ: 1

xmin = lonv[0]
xmax = lonv[-1]
ymin = latv[0]
ymax = latv[-1]

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
print(s_hemco_grid_spec)


for p in IN_BASE.glob("data/*.nc"):
    print(p.name)

    if "grid_spec" in p.name:  # grid_xt, etc., just for regridding
        continue  # FIXME

    ds = xr.open_dataset(p)

    if "HTAP" in p.name:
        # Exact selection
        sel = ds.sel(lat=latv, lon=np.mod(lonv, 360))
    else:
        sel = ds.sel(lat=latv, lon=lonv, method="nearest")

    print("- lat:", sel.lat.values)
    print("- lon:", sel.lon.values)

    # encoding = {k: {"zlib": True, "complevel": 3} for k in sel.data_vars}
    # ds.to_netcdf(OUT_BASE / p.name, encoding=encoding)
    # print(p.as_posix(), "=>", (OUT_BASE / p.name).as_posix())

