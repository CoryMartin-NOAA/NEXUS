"""
Extract a small spatial subset from larger inputs.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).parent
OUT_BASE = HERE / "data"


# Short reference to the focus location and emissions configuration
case_id_in = "ncwcp_anthro"

# Focus location
latc, lonc = 38.9721, -76.9245
latc, lonc = 38.9721, -26.9245  # testing tile1

# Input case directory
in_base = Path("~/downloads/gocart-nexus").expanduser()
assert in_base.is_dir()
print("input case directory:", in_base.as_posix())

# Grid settings
nx = ny = 3  # HEMCO grid
dx = dy = 0.1
ne = 1  # thickness of input data halo (cells)
assert nx % 2 == 1 and ny % 2 == 1, "nx and ny must be odd"

s_dx = f"{dx:.3g}".replace(".", "")
s_dy = f"{dy:.3g}".replace(".", "")
case_id = f"{case_id_in}_dx={s_dx}_dy={s_dy}_nx={nx}_ny={ny}_ne={ne}"
case_dir = OUT_BASE / case_id
case_dir.mkdir(exist_ok=True)
(case_dir / "data").mkdir(exist_ok=True)
print("full case ID:", case_id)

# Round center point to nearest grid point center, assuming [0, dx, dx + 1, ...] are edges
xc_i, yc_i = lonc, latc
rx = 1 / dx
ry = 1 / dy
yc_u = round(yc_i * ry - dy / 2) / ry + dy / 2
yc_d = round(yc_i * ry + dy / 2) / ry - dy / 2
xc_u = round(xc_i * rx - dx / 2) / rx + dx / 2
xc_d = round(xc_i * rx + dx / 2) / rx - dx / 2
yc, _ = sorted([yc_u, yc_d], key=lambda y: abs(yc_i - y))
xc, _ = sorted([xc_u, xc_d], key=lambda x: abs(xc_i - x))
yc = round(yc, 3)
xc = round(xc, 3)
xc = (xc + 180) % 360 - 180  # ensure [-180, 180)
fmt = "9.4f"
print(f"input focus   (y, x): {yc_i:{fmt}} {xc_i:{fmt}}")
print(f"rounded focus (y, x): {xc:{fmt}} {yc:{fmt}}")

# Rectangular grid (centers)
y = np.arange(
    yc - (ny - 1 + ne * 2) / 2 * dy,
    yc + (ny - 1 + ne * 2) / 2 * dy + dy,
    dy,
)[:ny + ne * 2]
x = np.arange(
    xc - (nx - 1 + ne * 2) / 2 * dx,
    xc + (nx - 1 + ne * 2) / 2 * dx + dx,
    dx,
)[:nx + ne * 2]
y = np.round(y, 3)
x = np.round(x, 3)
assert y.size == ny + ne * 2 and x.size == nx + ne * 2
x_360 = np.mod(x, 360)
print("lat (y):", y)
print("lon (x):", x)
print("lon (x) 360:", x_360)


# We need these config files
# Only the grid file, which is used to set the HEMCO grid, should need to be adjusted
# - HEMCO_Config.rc
# - HEMCO_sa_Diagn.rc
# - HEMCO_sa_Grid.rc
# - HEMCO_sa_Spec.rc
# - HEMCO_sa_Time.rc

for desc, fn in {
    "main config": "HEMCO_Config.rc",
    "diagnostic definitions": "HEMCO_sa_Diagn.rc",
    # "grid definition": "HEMCO_sa_Grid.rc",
    "species definitions": "HEMCO_sa_Spec.rc",
    "simulation time settings": "HEMCO_sa_Time.rc",
}.items():
    p_in = in_base / fn
    if p_in.is_file():
        print(f"copying {fn!r} ({desc})")
        shutil.copy(p_in, case_dir / fn)
    else:
        rc_files = sorted(in_base.glob("*.rc"))
        s_files = "\n".join(f"- {p.name}" for p in rc_files)
        raise RuntimeError(
            f"{in_base.as_posix()} is missing the {fn!r} file ({desc}). "
            f"The directory has these .rc files:\n{s_files}"
        )


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

xmin = x[ne] - dx / 2
xmax = x[-1 - ne] + dx / 2
ymin = y[ne] - dy / 2
ymax = y[-1 - ne] + dy / 2

fmt = ">8.3f"

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
fn = "HEMCO_sa_Grid.rc"
desc = "grid definition"
sep = "-" * 31
print(f"writing {fn!r} ({desc}):")
print(sep)
print(s_hemco_grid_spec, end="")
print(sep)
with open(case_dir / fn, "w") as f:
    f.write(s_hemco_grid_spec)


# Select input data and write to case directory
lat = y
lon = x
lon_360 = x_360
assert (in_base / "data").is_dir()
for p in in_base.glob("data/*.nc"):
    print(p.relative_to(in_base).as_posix())

    ds = xr.open_dataset(p, decode_times=False)

    if "grid_spec" in p.name:  # grid_xt, etc., just for regridding
        # edges: grid_lat, grid_lon (dims: grid_x, grid_y)
        # centers: grid_latt, grid_lont (dims: grid_xt, grid_yt)
        # lon in [0, 360)

        da = ds.grid_lont
        assert da.dims == ("grid_yt", "grid_xt")
        a = da.values
        inds = ((a >= lon_360[0]) & (a <= lon_360[-1])).nonzero()[1]
        assert inds.size > 0
        ix1, ix2 = inds.min(), inds.max()
        if not ix2 - ix1 > 1:
            ix1 -= 1
            ix2 += 1

        da = ds.grid_latt
        assert da.dims == ("grid_yt", "grid_xt")
        a = da.values
        inds = ((a >= lat[0]) & (a <= lat[-1])).nonzero()[0]
        assert inds.size > 0
        iy1, iy2 = inds.min(), inds.max()
        if not iy2 - iy1 > 1:
            iy1 -= 1
            iy2 += 1

        buf = 1
        ds = ds.isel(
            grid_xt=slice(ix1, ix2 + 1),
            grid_yt=slice(iy1, iy2 + 1),
            grid_x=slice(ix1, ix2 + 2),
            grid_y=slice(iy1, iy2 + 2),
        )

        print(ds.grid_lon.values)
        print(ds.grid_lont.values)

        ds.plot.scatter(x="grid_lont", y="grid_latt")
        import matplotlib.pyplot as plt; plt.show()

        continue  # FIXME


    if "HTAP" in p.name and dx == dy == 0.1:
        # Exact selection
        sel = ds.sel(lat=lat, lon=lon_360)
        print("- lat exact:", sel.lat.values)
        print("- lon exact:", sel.lon.values)
    else:
        # Note that nearest for low-res data will include duplicates
        assert ds.lon.max() < 180
        sel = ds.sel(lat=lat, lon=lon, method="nearest")
        print("- lat nearest:", sel.lat.values)
        print("- lon nearest:", sel.lon.values)

    # Replace lat/lon
    lat_attrs = sel.lat.attrs.copy()
    lon_attrs = sel.lon.attrs.copy()
    sel = sel.assign_coords(lat=lat, lon=lon)
    sel["lat"].attrs.update(lat_attrs)
    sel["lon"].attrs.update(lon_attrs)

    # print("- lat:", sel.lat.values)
    # print("- lon:", sel.lon.values)

    p_out = case_dir / "data" / p.name
    # print("->(sel)", p_out.as_posix())
    encoding = {
        k: {"zlib": True, "complevel": 3}
        for k in sel.data_vars if k not in {"UTC_OFFSET", "time"}
    }
    sel.to_netcdf(p_out, encoding=encoding)
