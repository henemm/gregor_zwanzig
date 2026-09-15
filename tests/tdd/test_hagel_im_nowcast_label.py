"""TDD RED — Nowcast-/Radar-Label unterscheidet Wettercode 95 von 96/99
(Issue #2205, AC-7/AC-8).

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Befund: ``radar_service.INTENSITY_CONVECTIVE = "Starker Hagel/Gewitter"``
(Z. 137) gilt fuer JEDEN konvektiven Frame; ``_is_convective_weathercode``
(Z. 461-463) wirft 95/96/99 zu einem ``bool`` zusammen. Code 95 ist aber kein
Hagel-Code -- die Aussage "Hagel" ist dort falsch.

Zielverhalten: Code 95 -> Label mit "Gewitter", ohne "Hagel"; Code 96/99 ->
Label mit Hagelbegriff.

Einstieg so hoch wie netzfrei moeglich: ``RadarNowcastService.get_nowcast()``
im Offline-Fixture-Modus (``GZ_TEST_FIXTURE_DIR``). Nur dieser Weg traegt den
WETTERCODE als Eingang (``_load_radar_fixture_frames`` liest
``weather_code`` je Frame) -- die ``frame_source``-Naht kennt nur
``is_convective: bool`` und kann 95 von 96 nicht unterscheiden. Die Fixture
liegt im ``tmp_path`` (die Repo-Fixture ``fixtures/radar/minutely_15.json``
bleibt unberuehrt). Danach wird das Ergebnis ueber die echte Projektion
``to_multi_location_onset_alert_message`` in E-Mail- und Telegram-Alarmtext
gerendert: geprueft wird am Label UND am gerenderten Text.

Netz-Tripwire (kein Mock-Theater, Muster
``tests/unit/test_radar_offline_fixture_mode.py``): ``httpx.Client`` wird
durch eine Klasse ersetzt, die jeden Versuch aufzeichnet; der Test verlangt
eine LEERE Liste.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from output.renderers.alert.project import (  # noqa: E402
    to_multi_location_onset_alert_message,
)
from output.renderers.alert.render import render_email, render_telegram  # noqa: E402
from services.radar_cache import RadarNowcastCacheService  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402

HAGEL_CODES = (96, 99)
OHNE_HAGEL_CODE = 95

# Ausserhalb aller Radar-Bounding-Boxen -> reiner open-meteo-Pfad, der im
# Offline-Modus die Radar-Fixture liest.
_LAT, _LON = 35.0, -40.0
_JETZT = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)

_NETZVERSUCHE: list[str] = []


class _NetzTripwire:
    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _NETZVERSUCHE.append(str(url))
        raise AssertionError(f"Netzcall im Offline-Test: {url}")


@pytest.fixture
def nowcast(tmp_path, monkeypatch):
    """Liefert ``code -> NowcastResult`` ueber den echten ``get_nowcast()``.

    Fixture-Frames: jetzt trocken, ab +15 Min 4 mm/h mit dem Wettercode des
    Tests (ueber Trockenschwelle, im 180-Min-Fenster -> konvektiv zaehlt).
    """
    _NETZVERSUCHE.clear()
    monkeypatch.setattr(httpx, "Client", _NetzTripwire)
    forecast_dir = tmp_path / "openmeteo"
    forecast_dir.mkdir()
    (tmp_path / "radar").mkdir()
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(forecast_dir))

    def _hole(code: int):
        frames = [{"offset_min": 0, "precip_mm_h": 0.0, "weather_code": 3}] + [
            {"offset_min": m, "precip_mm_h": 4.0, "weather_code": code}
            for m in (15, 30, 45, 60)
        ]
        (tmp_path / "radar" / "minutely_15.json").write_text(
            json.dumps({"frames": frames}))
        svc = RadarNowcastService(
            cache=RadarNowcastCacheService(), now_fn=lambda: _JETZT,
        )
        ergebnis = svc.get_nowcast(_LAT, _LON)
        assert _NETZVERSUCHE == [], f"Netzcall ausgeloest: {_NETZVERSUCHE}"
        assert ergebnis.onset_minutes is not None and ergebnis.is_convective, (
            f"Vorbedingung: Fixture muss einen konvektiven Beginn liefern "
            f"(Code {code}), erhalten {ergebnis!r}")
        return ergebnis

    return _hole


def _alarmtexte(ergebnis) -> dict[str, str]:
    msg = to_multi_location_onset_alert_message(
        [("Testort", ergebnis)], tz=timezone.utc, stand_at="12:00",
    )
    _html, plain = render_email(msg)
    return {"email": plain, "telegram": render_telegram(msg)}


@pytest.mark.parametrize("code", HAGEL_CODES)
def test_ac7_nowcast_label_nennt_hagel_bei_96_99(nowcast, code):
    """AC-7.

    GIVEN eine Nowcast-Zeitreihe, deren nasse Frames Wettercode 96 bzw. 99
          tragen (Offline-Radar-Fixture).
    WHEN  ``get_nowcast()`` das Intensitaets-Label ermittelt und der
          Radar-Onset-Alarm fuer E-Mail und Telegram gerendert wird.
    THEN  enthaelt das Label -- und damit beide Alarmtexte -- einen
          Hagelbegriff.

    Zusaetzlich: das Hagel-Label ist von dem Label derselben Lage mit Code 95
    verschieden -- ohne das waere "enthaelt Hagel" auch mit dem pauschalen
    Alt-Label erfuellt und der Test bewachte keine Unterscheidung.

    RED heute: Code 95 und 96/99 liefern dasselbe Label
    "Starker Hagel/Gewitter".
    """
    ergebnis = nowcast(code)
    assert "Hagel" in ergebnis.intensity_label, (
        f"AC-7: Nowcast-Label muss bei Code {code} einen Hagelbegriff tragen, "
        f"ist {ergebnis.intensity_label!r}")
    label_95 = nowcast(OHNE_HAGEL_CODE).intensity_label
    assert ergebnis.intensity_label != label_95, (
        f"AC-7: das Label bei Code {code} muss sich vom Label bei Code 95 "
        f"unterscheiden (nur 96/99 tragen Hagel), beide sind "
        f"{label_95!r}")
    for kanal, text in _alarmtexte(ergebnis).items():
        assert ergebnis.intensity_label in text, (
            f"Vorbedingung: {kanal}-Alarmtext muss das Label tragen: {text!r}")
        assert "Hagel" in text, (
            f"AC-7: {kanal}-Alarmtext muss bei Code {code} Hagel nennen: {text!r}")


def test_ac8_nowcast_label_ohne_hagel_bei_95(nowcast):
    """AC-8.

    GIVEN eine Nowcast-Zeitreihe, deren nasse Frames ausschliesslich
          Wettercode 95 tragen.
    WHEN  ``get_nowcast()`` das Label ermittelt und der Radar-Onset-Alarm fuer
          E-Mail und Telegram gerendert wird.
    THEN  enthaelt das Label "Gewitter", aber keinen Hagelbegriff -- und
          keiner der beiden Alarmtexte nennt Hagel.

    RED heute: das pauschale Alt-Label "Starker Hagel/Gewitter".
    """
    ergebnis = nowcast(OHNE_HAGEL_CODE)
    assert "Gewitter" in ergebnis.intensity_label, (
        f"AC-8: Nowcast-Label muss bei Code 95 'Gewitter' nennen, ist "
        f"{ergebnis.intensity_label!r}")
    assert "Hagel" not in ergebnis.intensity_label, (
        f"AC-8: Nowcast-Label darf bei Code 95 keinen Hagel behaupten, ist "
        f"{ergebnis.intensity_label!r}")
    for kanal, text in _alarmtexte(ergebnis).items():
        assert "Gewitter" in text, (
            f"Vorbedingung: {kanal}-Alarmtext ohne Gewitteraussage: {text!r}")
        assert "Hagel" not in text, (
            f"AC-8: {kanal}-Alarmtext darf bei Code 95 keinen Hagel nennen: "
            f"{text!r}")


# ═══════ Mutationsluecken aus dem Adversary-Dialog (F001, F002-B) ═══════


@pytest.mark.parametrize("hagel_zuerst", (False, True), ids=("95-dann-96", "96-dann-95"))
def test_zone_mit_hagel_und_gewitterpunkt_bleibt_hagelzone(hagel_zuerst):
    """AC-7/AC-8 auf der Strecke (F001).

    GIVEN eine zusammenhaengende Nass-Zone aus einem Gewitterpunkt ohne Hagel
          (Label "Gewitter", Code 95) und einem Hagelpunkt (Code 96/99) -- in
          beiden Reihenfolgen entlang der Strecke.
    WHEN  ``derive_rain_zones()`` die Zone bildet.
    THEN  traegt die Zone das Hagel-Label: ein Nicht-Hagel-Punkt verwaessert
          die Hagelaussage nie. Die Reihenfolge "95 zuerst" ist der
          diskriminierende Fall (bei Ranggleichheit gewaenne der erste Punkt).
    """
    from app.models import GPXPoint
    from services.radar_service import (
        INTENSITY_CONVECTIVE,
        INTENSITY_CONVECTIVE_NO_HAIL,
        NowcastResult,
    )
    from services.rain_extent import derive_rain_zones

    svc = RadarNowcastService(cache=RadarNowcastCacheService(), now_fn=lambda: _JETZT)
    hagel = svc.intensity_to_text(4.0, is_convective=True, hail=True)
    gewitter = svc.intensity_to_text(4.0, is_convective=True, hail=False)
    assert (hagel, gewitter) == (INTENSITY_CONVECTIVE, INTENSITY_CONVECTIVE_NO_HAIL)
    labels = [hagel, gewitter] if hagel_zuerst else [gewitter, hagel]
    punkte = [GPXPoint(lat=0.0, lon=km / 111.0, elevation_m=1000.0,
                       distance_from_start_km=km) for km in (0.0, 2.0)]
    ergebnisse = [NowcastResult(onset_minutes=10, intensity_label=lb, source="radar")
                  for lb in labels]

    zonen = derive_rain_zones(punkte, ergebnisse)

    assert len(zonen) == 1, f"Vorbedingung: genau eine Zone, erhalten {zonen!r}"
    assert "Hagel" in zonen[0].intensity_label, (
        f"F001: Zone mit Hagelpunkt muss Hagel nennen (Reihenfolge {labels!r}), "
        f"ist {zonen[0].intensity_label!r}")


@pytest.mark.parametrize("hagel", (True, False), ids=("sidecar-hagel", "sidecar-ohne-hagel"))
def test_inca_label_uebernimmt_hagel_aus_zusatzabruf(monkeypatch, hagel):
    """AC-7/AC-8 im INCA-Pfad (F002-B).

    GIVEN ein Ort im INCA-Gebiet (Wien): INCA liefert nur die Regenrate, das
          Gewitter-/Hagel-Kennzeichen kommt aus dem Open-Meteo-Zusatzabruf.
    WHEN  ``get_nowcast()`` (frischer Cache, feste Uhr) das Label bildet und
          der Radar-Onset-Alarm gerendert wird.
    THEN  traegt das Label -- und der Alarmtext -- Hagel genau dann, wenn der
          Zusatzabruf-Frame Hagel meldet; sonst nur "Gewitter".

    Nachgebildet sind nur die zwei Netzabrufe (echte ``RadarFrame``/
    ``NormalizedTimeseries``-Objekte, Muster test_issue_1161_inca_convective.py).
    """
    from datetime import timedelta

    from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
    from providers.brightsky import RadarFrame
    from providers.geosphere import GeoSphereProvider

    _NETZVERSUCHE.clear()
    monkeypatch.setattr(httpx, "Client", _NetzTripwire)
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    zeiten = [_JETZT + timedelta(minutes=m) for m in (15, 30, 45, 60)]
    inca = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.GEOSPHERE, model="NOWCAST", run=_JETZT,
                          grid_res_km=1.0, interp="bilinear"),
        data=[ForecastDataPoint(ts=t, precip_1h_mm=1.0) for t in zeiten],
    )
    aufrufe: list[tuple[float, float]] = []

    def _zusatzabruf(self, lat, lon, models=None, elevation_m=None):
        aufrufe.append((lat, lon))
        return [RadarFrame(timestamp=t + timedelta(minutes=2), precip_mm_h=2.0,
                           is_convective=True, hail=hagel) for t in zeiten]

    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", lambda self, lat, lon: inca)
    monkeypatch.setattr(RadarNowcastService, "_fetch_openmeteo_15", _zusatzabruf)

    ergebnis = RadarNowcastService(
        cache=RadarNowcastCacheService(), now_fn=lambda: _JETZT,
    ).get_nowcast(48.21, 16.37)

    assert _NETZVERSUCHE == [], f"Netzcall ausgeloest: {_NETZVERSUCHE}"
    assert aufrufe and ergebnis.source == "INCA" and ergebnis.is_convective, (
        f"Vorbedingung: INCA-Pfad mit Zusatzabruf und Gewitter, erhalten "
        f"{ergebnis!r}, Aufrufe {aufrufe!r}")
    texte = _alarmtexte(ergebnis)
    if hagel:
        assert "Hagel" in ergebnis.intensity_label, (
            f"F002-B: Hagel aus dem Zusatzabruf muss im INCA-Label ankommen, "
            f"ist {ergebnis.intensity_label!r}")
        assert all("Hagel" in t for t in texte.values()), texte
    else:
        assert ergebnis.intensity_label == "Gewitter", ergebnis.intensity_label
        assert not any("Hagel" in t for t in texte.values()), texte
