"""#1354: `_read_point_value` darf den nodata-Fuellwert (9999.0) ausserhalb
des ICON-D2-Modellgebiets nie als Messwert durchreichen.

Kern-Schicht: kein Netz, kein HTTP, kein Mock — echtes `bz2`+`rasterio` gegen
die bereits im Repo liegende, echt aufgezeichnete Fixture.
"""
from __future__ import annotations

import bz2
import sys
from pathlib import Path

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from providers.dwd import THUNDER_FILL_VALUE, _read_point_value

_FIXTURE = (
    _REPO / "tests" / "fixtures" / "dwd"
    / "icon_d2_muenchen_t_2m_2026072221_001.grib2.bz2"
)


def test_nodata_pixel_ausserhalb_modellgebiet_liefert_none():
    # Rasterecke (row=0, col=0) des `regular-lat-lon`-Rechtecks — liegt
    # ausserhalb des Modellgebiets und traegt dort den Fuellwert 9999.0.
    wert = _read_point_value(_FIXTURE.read_bytes(), lat=58.08, lon=-3.94)
    assert wert is None


def test_echter_messwert_im_modellgebiet_bleibt_erhalten():
    wert = _read_point_value(_FIXTURE.read_bytes(), lat=48.14, lon=11.57)
    assert wert is not None
    assert -40.0 <= wert <= 50.0


_GITTER = (-3.95, 43.17, 20.35, 58.09)


def _raster_ohne_nodata_tag(wert: float) -> bytes:
    """Konstantes Raster ueber das ICON-D2-Rechteck, bz2-gepackt wie beim
    echten Dienst — bewusst OHNE `dataset.nodata`-Tag."""
    hoehe, breite = 60, 100
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1,
            dtype="float64", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(np.full((hoehe, breite), wert, dtype="float64"), 1)
        return bz2.compress(memfile.read())


def test_sentinel_ohne_nodata_tag_liefert_none():
    # Traegt das Raster kein nodata-Tag, steht der Fuellwert als blosser
    # Datenwert darin — dann muss der Rueckfall auf THUNDER_FILL_VALUE greifen.
    roh = _raster_ohne_nodata_tag(THUNDER_FILL_VALUE)
    assert _read_point_value(roh, lat=48.14, lon=11.57) is None
