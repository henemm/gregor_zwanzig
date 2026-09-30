"""#2465: Der de_direct-Gewitterabruf laedt jede ICON-D2-Rasterdatei je Lauf nur EINMAL.

Vorfall 2026-09-29: `alert_checks` lief ueber Stunden unvollstaendig
(`Zeitobergrenze`), weil jedes Segment eines Trips dieselben ~217 Rasterdateien
erneut lud und entpackte (gemessen: 1302 GETs / 866 MB je Trip-Lauf bei nur 217
eindeutigen URLs). Jede Datei deckt das ganze Modellgebiet ab — die Segmente
unterscheiden sich nur im Pixel.

Kern-Schicht: kein Netz. `httpx.MockTransport` ist hier ein Fake-DWD-Server, der
ECHTE bz2-gepackte Raster ausliefert (kein Mock der eigenen Annahme): die
Erwartungswerte kommen aus dem unveraenderten Direktweg `_read_point_value`.
"""
from __future__ import annotations

import bz2
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from providers import dwd
from providers.dwd import DwdDirectProvider, _read_point_value

_GITTER = (-3.95, 43.17, 20.35, 58.09)
_HOEHE, _BREITE = 60, 100


def _gradient_raster() -> bytes:
    """Jeder Pixel traegt einen eigenen Wert (row*100+col, max. 5999) — ein
    falsch indizierter Cache-Treffer faellt so sofort auf. Bewusst UNTER dem
    Fuellwert THUNDER_FILL_VALUE (9999), sonst wuerde jeder Wert zu None."""
    werte = (
        np.arange(_HOEHE, dtype="float32")[:, None] * 100
        + np.arange(_BREITE, dtype="float32")[None, :]
    )
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=_HOEHE, width=_BREITE, count=1,
            dtype="float32", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, _BREITE, _HOEHE),
        ) as dataset:
            dataset.write(werte, 1)
        return bz2.compress(memfile.read())


_RASTER = _gradient_raster()


def _konstantes_raster(wert: float) -> bytes:
    """Konstantes Raster ueber das ICON-D2-Rechteck, bz2-gepackt, OHNE nodata-Tag."""
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=_HOEHE, width=_BREITE, count=1,
            dtype="float32", crs="EPSG:4326",
            transform=from_bounds(*_GITTER, _BREITE, _HOEHE),
        ) as dataset:
            dataset.write(np.full((_HOEHE, _BREITE), wert, dtype="float32"), 1)
        return bz2.compress(memfile.read())


@pytest.fixture(autouse=True)
def _cache_leeren():
    """Prozessweiter Cache: jeder Test startet leer."""
    if hasattr(dwd, "_RASTER_CACHE"):
        dwd._RASTER_CACHE.clear()
    yield
    if hasattr(dwd, "_RASTER_CACHE"):
        dwd._RASTER_CACHE.clear()


def _provider(status: int = 200, raster: bytes = _RASTER, fehlt: str = ""):
    """Fake-DWD: liefert `raster` (oder `status`) und zaehlt GETs je URL.
    `fehlt`: URL-Bestandteil, der als 404 (einzelne fehlende Datei) antwortet."""
    aufrufe: Counter = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        aufrufe[str(request.url)] += 1
        if status != 200 or (fehlt and fehlt in str(request.url)):
            return httpx.Response(404 if status == 200 else status)
        return httpx.Response(200, content=raster)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    return DwdDirectProvider(client=client), aufrufe


def _fenster():
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return start, start + timedelta(hours=6)


def _abruf(prov, lat, lon):
    start, ende = _fenster()
    return prov.fetch_thunder_signals_named(
        Location(latitude=lat, longitude=lon), start, ende
    )


def test_mehrere_standorte_laden_jede_datei_genau_einmal():
    prov, aufrufe = _provider()
    # Drei Segmente eines Trips: verschiedene Pixel, dasselbe Modellgebiet.
    for lat, lon in [(48.14, 11.57), (48.60, 11.90), (49.10, 12.20)]:
        _abruf(prov, lat, lon)
    assert aufrufe, "es wurde nichts abgerufen"
    mehrfach = {u: n for u, n in aufrufe.items() if n > 1}
    assert not mehrfach, f"Dateien mehrfach geladen: {list(mehrfach.items())[:3]}"


def test_werte_sind_identisch_zum_direkten_lesen_auch_weit_auseinander():
    """Punkte weit auseinander (zweites Fenster) und am Gitterrand (Klemmung)
    liefern exakt den Wert des unveraenderten Direktwegs."""
    punkte = [
        (48.14, 11.57), (55.00, 15.00),   # weit auseinander -> zweites Fenster
        (43.18, -3.94), (58.08, 20.34),   # Ecken -> Klemmung auf den Rand
        (60.00, 30.00),                   # ausserhalb des Gitters -> Klemmung
    ]
    prov, _ = _provider()
    for lat, lon in punkte:  # warm: zweiter Durchlauf bedient sich aus dem Cache
        _abruf(prov, lat, lon)
    for lat, lon in punkte:
        erwartet = _read_point_value(_RASTER, lat, lon, "lpi")
        erg = _abruf(prov, lat, lon)
        werte = [v for v in erg["lpi"].values() if v is not None]
        assert werte, f"kein lpi-Wert fuer {(lat, lon)}"
        assert all(v == erwartet for v in werte), (lat, lon, erwartet, set(werte))


def test_fehlschlag_wird_nicht_gecacht():
    """404 (Lauf noch nicht veroeffentlicht) darf nicht haengenbleiben: sobald
    der Dienst liefert, muss der naechste Abruf Werte bekommen."""
    from providers.base import ThunderSourceUnavailableError

    prov, _ = _provider(status=404)
    try:
        erg = _abruf(prov, 48.14, 11.57)
        assert not any(v is not None for d in erg.values() for v in d.values())
    except ThunderSourceUnavailableError:
        pass  # alle Abrufe gescheitert: vertragsgemaess sichtbar, nichts gecacht
    prov_ok, aufrufe = _provider(status=200)
    erg = _abruf(prov_ok, 48.14, 11.57)
    assert any(v is not None for v in erg["lpi"].values())
    assert aufrufe, "nach dem 404 wurde nicht erneut abgerufen (Fehlschlag gecacht?)"


def test_fuellwert_wird_aus_dem_cache_nie_als_messwert_durchgereicht():
    """AC-2 (#1354/#1531): 9999 (ausserhalb des Modells) bzw. -999,9 (cin_ml)
    ist "keine Aussage", nie ein Messwert — auch nicht aus dem Cache."""
    prov, _ = _provider(raster=_konstantes_raster(9999.0))
    kalt = _abruf(prov, 48.14, 11.57)   # decodiert + legt Fenster an
    warm = _abruf(prov, 48.14, 11.57)   # bedient sich aus dem Cache
    for erg in (kalt, warm):
        assert all(v is None for d in erg.values() for v in d.values())

    dwd._RASTER_CACHE.clear()
    prov, _ = _provider(raster=_konstantes_raster(-999.9))
    for erg in (_abruf(prov, 48.14, 11.57), _abruf(prov, 48.14, 11.57)):
        assert all(v is None for v in erg["cin_ml"].values())


def test_cache_treffer_bestaetigt_den_lauf_kein_falscher_rueckfall():
    """Ist der Lauf durch (auch gecachte) Treffer bestaetigt, ist ein 404 nur
    eine einzelne fehlende Stunde: kein Rueckfall auf einen aelteren Lauf, der
    die Reihe verschieben wuerde (Spec AC-2/AC-7)."""
    prov, _ = _provider()
    _abruf(prov, 48.14, 11.57)                      # Cache warm
    # Die ZULETZT abgerufene Datei "verschwindet": alle davor sind Treffer und
    # bestaetigen den Lauf. (Die ERSTE zu nehmen waere ein legitimer Rueckfall —
    # ein 404 vor jeder Bestaetigung heisst "Lauf noch nicht veroeffentlicht".)
    fehl_url = list(dwd._RASTER_CACHE._data)[-1]
    dwd._RASTER_CACHE._data.pop(fehl_url)
    teil = fehl_url.rsplit("/", 1)[-1]
    prov2, aufrufe = _provider(fehlt=teil)
    _abruf(prov2, 48.14, 11.57)
    laeufe = {u.split("single-level_")[1][:10] for u in aufrufe}
    assert len(laeufe) == 1, f"Rueckfall auf aelteren Lauf: {laeufe}"


def test_parsing_fehler_wird_nicht_gecacht():
    """Kaputte Bytes (kein bz2/GRIB) duerfen weder Werte liefern noch einen
    Cache-Eintrag hinterlassen — sonst bliebe der Fehler bis zum Neustart."""
    kaputt, _ = _provider(raster=b"das ist kein bz2")
    erg = _abruf(kaputt, 48.14, 11.57)
    assert all(v is None for d in erg.values() for v in d.values())
    assert len(dwd._RASTER_CACHE) == 0, "Parsing-Fehler wurde gecacht"

    gut, aufrufe = _provider()
    erg = _abruf(gut, 48.14, 11.57)
    assert aufrufe, "nach dem Parsing-Fehler wurde nicht erneut abgerufen"
    assert any(v is not None for v in erg["lpi"].values())


def test_gleicher_ausschnitt_wird_nicht_doppelt_abgelegt():
    cache = dwd._PointWindowCache(max_urls=5, max_windows_per_url=4)
    f1 = dwd._decode_window(_RASTER, 48.14, 11.57)
    f2 = dwd._decode_window(_RASTER, 48.14, 11.57)  # zweiter Lauf, gleicher Punkt
    cache.put("https://x/a", f1)
    cache.put("https://x/a", f2)
    assert len(cache._data["https://x/a"]) == 1


def test_verdraengung_je_url_ist_lru_nicht_fifo():
    """Ein Treffer haelt seinen Ausschnitt am Leben: zuletzt BENUTZT fliegt
    zuletzt raus, nicht zuletzt angelegt."""
    cache = dwd._PointWindowCache(max_urls=5, max_windows_per_url=2)
    url = "https://x/a"
    a, b, c = (58.0, 11.57), (43.3, 11.57), (50.6, 11.57)  # nur je 1 Fenster enthaelt seinen Punkt
    for lat, lon in (a, b):
        cache.put(url, dwd._decode_window(_RASTER, lat, lon))
    assert cache.find(url, *a) is not None      # a wird benutzt -> ans Ende
    cache.put(url, dwd._decode_window(_RASTER, *c))   # verdraengt b, nicht a
    assert cache.find(url, *a) is not None, "a wurde trotz Benutzung verdraengt (FIFO)"
    assert cache.find(url, *b) is None


def test_fehlerzaehlung_bei_warmem_cache_kein_falscher_totalausfall():
    """Treffer zaehlen als Versuch: scheitern nur die wenigen NICHT gecachten
    Dateien, ist das kein Totalausfall (`fehlgeschlagen == versucht`)."""
    from providers.base import ThunderSourceUnavailableError

    prov, _ = _provider()
    _abruf(prov, 48.14, 11.57)
    fehlen = list(dwd._RASTER_CACHE._data)[-2:]   # die letzten zwei "verschwinden"
    for url in fehlen:
        dwd._RASTER_CACHE._data.pop(url)
    # beide fehlenden Dateien antworten mit 404 (eigener Fake mit zwei Namen)
    namen = tuple(u.rsplit("/", 1)[-1] for u in fehlen)

    def handler(request: httpx.Request) -> httpx.Response:
        if any(n in str(request.url) for n in namen):
            return httpx.Response(404)
        return httpx.Response(200, content=_RASTER)

    prov3 = DwdDirectProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    )
    try:
        erg = _abruf(prov3, 48.14, 11.57)
    except ThunderSourceUnavailableError:
        pytest.fail("Cache-Treffer wurden nicht als Versuch gezaehlt: falscher Totalausfall")
    assert any(v is not None for v in erg["lpi"].values())


def test_fenster_ist_41x41_und_werte_bleiben_float64_bit_identisch():
    """Fenstergroesse fest (kleinere Fenster = mehr Fehltreffer), und float64-Werte
    mit Nachkommastellen kommen bit-identisch wie beim Direktlesen heraus."""
    hoehe, breite = 60, 100
    werte = (
        np.arange(hoehe, dtype="float64")[:, None] * 100.1
        + np.arange(breite, dtype="float64")[None, :] * 0.123456789
    )
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1, dtype="float64",
            crs="EPSG:4326", transform=from_bounds(*_GITTER, breite, hoehe),
        ) as dataset:
            dataset.write(werte, 1)
        roh = bz2.compress(memfile.read())
    fenster = dwd._decode_window(roh, 50.6, 8.0)   # Rastermitte
    assert fenster.array.shape == (41, 41)
    assert fenster.array.dtype == np.float64
    for lat, lon in [(50.6, 8.0), (50.0, 7.0), (51.2, 9.3)]:
        if fenster.contains(lat, lon):
            assert fenster.value_at(lat, lon, "lpi") == _read_point_value(roh, lat, lon, "lpi")


def test_sentinel_kommt_aus_dem_nodata_tag_des_rasters():
    """Traegt das Raster ein nodata-Tag (hier 500), gilt DIESES als Fuellwert-
    Grenze, nicht die feste 9999 — wie beim Direktlesen."""
    hoehe, breite = 60, 100
    werte = (
        np.arange(hoehe, dtype="float32")[:, None] * 100
        + np.arange(breite, dtype="float32")[None, :]
    )
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=hoehe, width=breite, count=1, dtype="float32",
            crs="EPSG:4326", transform=from_bounds(*_GITTER, breite, hoehe), nodata=500.0,
        ) as dataset:
            dataset.write(werte, 1)
        roh = bz2.compress(memfile.read())
    lat, lon = 50.6, 8.0        # Mitte: Wert weit ueber 500
    erwartet = _read_point_value(roh, lat, lon, "lpi")
    assert erwartet is None
    assert dwd._decode_window(roh, lat, lon).value_at(lat, lon, "lpi") is None


def test_produktivgrenzen_des_prozessweiten_cache():
    assert dwd._RASTER_CACHE._max_urls == dwd._RASTER_CACHE_MAX_URLS == 512
    assert dwd._RASTER_CACHE._max_windows == dwd._RASTER_CACHE_MAX_WINDOWS_PER_URL == 8
    f = dwd._decode_window(_RASTER, 48.14, 11.57)
    for i in range(600):
        dwd._RASTER_CACHE.put(f"https://x/{i}", f)
    assert len(dwd._RASTER_CACHE) == 512
    # bis zu 8 verschiedene Ausschnitte je URL, danach wird verdraengt
    for lat in [58.0, 56.0, 54.0, 52.0, 50.0, 48.0, 46.0, 44.0, 43.3, 57.0, 55.0]:
        dwd._RASTER_CACHE.put("https://x/viele", dwd._decode_window(_RASTER, lat, 11.57))
    assert 1 < len(dwd._RASTER_CACHE._data["https://x/viele"]) <= 8


def test_url_ebene_lru_neuester_bleibt_und_benutzter_ueberlebt():
    cache = dwd._PointWindowCache(max_urls=3, max_windows_per_url=2)
    f = dwd._decode_window(_RASTER, 48.14, 11.57)
    for i in range(3):
        cache.put(f"https://x/{i}", f)
    assert cache.find("https://x/0", 48.14, 11.57) is not None   # 0 wird benutzt
    cache.put("https://x/3", f)                                   # verdraengt 1 (aeltester unbenutzter)
    assert len(cache) == 3
    assert cache.find("https://x/1", 48.14, 11.57) is None
    assert cache.find("https://x/0", 48.14, 11.57) is not None
    assert cache.find("https://x/3", 48.14, 11.57) is not None    # der NEUESTE bleibt


def test_cache_ist_begrenzt():
    cache_cls = getattr(dwd, "_PointWindowCache", None)
    assert cache_cls is not None, "_PointWindowCache fehlt"
    cache = cache_cls(max_urls=3, max_windows_per_url=2)
    fenster = dwd._decode_window(_RASTER, 48.14, 11.57)
    assert fenster is not None
    for i in range(10):
        cache.put(f"https://x/{i}", fenster)
    assert len(cache) <= 3
