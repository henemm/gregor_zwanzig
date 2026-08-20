"""
Live-Nachweis — Issue #1991 AC-12: Wegpunkt-Höhe erreicht die echte Wetterquelle.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md (AC-12)

NO MOCKS — echte Open-Meteo-Abrufe, kein Fixture-Replay.

Zwei Referenzpunkte aus `examples/stubai_skitour.json` (Gipfel + Hütte),
damit BEIDE Fehlerrichtungen belegt sind: fehlt die explizite Höhe,
verwendet Open-Meteo die MODELL-eigene Geländehöhe (Antwortfeld
"elevation", `ForecastMeta.model_elevation_m`) — die kann je nach
Gitterauflösung an der Stelle über ODER unter der tatsächlichen Punkthöhe
liegen (Gipfel: Modell meist zu niedrig; Hütte im Kar: Modell kann in
beide Richtungen abweichen).

Robust gegen Wetterwechsel: KEINE feste Gradzahl fest verdrahtet. Geprüft
wird nur:
- die RICHTUNG (Vorzeichen der erwarteten Differenz aus der
  Standardatmosphäre, 0,6 °C je 100 m, gemessen an `model_elevation_m`)
- eine großzügige Mindestgröße relativ zum tatsächlichen Höhenunterschied
  (Faktor 0,3 auf den Faustwert — toleriert Inversion/lokale Effekte).

Läuft NICHT im Standard-Testlauf (`live` ist per `pyproject.toml` von den
Default-`addopts` ausgeschlossen) — nur via `pytest -m live` bzw. der
Staging-/Deploy-Verifikation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import Location
from providers.openmeteo import OpenMeteoProvider

pytestmark = pytest.mark.live

# examples/stubai_skitour.json: ein Gipfel, eine Hütte — beide
# Fehlerrichtungen der modell-eigenen Geländehöhe sind damit abgedeckt.
_REFERENZPUNKTE = [
    ("Schaufelspitze", 47.0614, 11.1211, 3333),
    ("Dresdner Huette", 47.0753, 11.1097, 2302),
]

# Standardatmosphäre: ~0,6 °C Temperaturabfall je 100 Höhenmeter.
# Großzügige Toleranz (Faktor 0,3) gegen reale Abweichungen.
_LAPSE_RATE_C_PER_100M = 0.6
_TOLERANZ_FAKTOR = 0.3
_MIN_HOEHENDIFFERENZ_M = 50  # darunter ist kein messbarer Unterschied zu erwarten


def _erste_temperatur_c(timeseries):
    for point in timeseries.data:
        if point.t2m_c is not None:
            return point.t2m_c
    pytest.fail("Kein Datenpunkt mit t2m_c in der Antwort -- Live-Quelle nicht plausibel.")


@pytest.mark.parametrize("name,lat,lon,elevation_m", _REFERENZPUNKTE)
def test_ac12_explizite_hoehe_veraendert_temperatur_in_erwarteter_richtung(
    name: str, lat: float, lon: float, elevation_m: int
) -> None:
    """AC-12: Given zwei Abrufe für dieselbe Koordinate, einmal mit und
    einmal ohne Höhenangabe / When beide gegen die echte Wetterquelle
    laufen / Then unterscheiden sich die gelieferten Temperaturen messbar,
    und der Wert mit Höhenangabe passt zur echten Höhe des Punktes."""
    provider = OpenMeteoProvider()
    now = datetime.now(timezone.utc)
    start = now
    end = now + timedelta(hours=6)

    ohne_hoehe = provider.fetch_forecast(
        Location(latitude=lat, longitude=lon, name=name, elevation_m=None),
        start=start, end=end, enrich_ensemble=False, enrich_snow=False,
    )
    mit_hoehe = provider.fetch_forecast(
        Location(latitude=lat, longitude=lon, name=name, elevation_m=elevation_m),
        start=start, end=end, enrich_ensemble=False, enrich_snow=False,
    )

    modell_hoehe_m = ohne_hoehe.meta.model_elevation_m
    assert modell_hoehe_m is not None, (
        f"{name}: Open-Meteo meldet keine Modellhoehe (elevation-Feld fehlt) -- "
        "AC-12 kann die erwartete Richtung nicht ableiten."
    )

    hoehen_differenz_m = elevation_m - modell_hoehe_m
    if abs(hoehen_differenz_m) < _MIN_HOEHENDIFFERENZ_M:
        pytest.skip(
            f"{name}: Modellhoehe ({modell_hoehe_m} m) liegt < "
            f"{_MIN_HOEHENDIFFERENZ_M} m an der echten Hoehe ({elevation_m} m) -- "
            "kein messbarer Unterschied zu erwarten."
        )

    temp_ohne = _erste_temperatur_c(ohne_hoehe)
    temp_mit = _erste_temperatur_c(mit_hoehe)
    tatsaechliche_differenz = temp_mit - temp_ohne

    assert temp_mit != temp_ohne, (
        f"{name}: Temperatur mit ({temp_mit}) und ohne ({temp_ohne}) Hoehenangabe "
        "sind identisch -- die Hoehe erreicht die Wetterquelle nicht messbar."
    )

    erwartete_mindestgroesse = (
        abs(hoehen_differenz_m) / 100 * _LAPSE_RATE_C_PER_100M * _TOLERANZ_FAKTOR
    )
    if hoehen_differenz_m > 0:
        # Echte Hoehe liegt UEBER der Modellhoehe -> mit Hoehenangabe kaelter.
        assert tatsaechliche_differenz < 0, (
            f"{name}: echte Hoehe ({elevation_m} m) liegt {hoehen_differenz_m:.0f} m "
            f"UEBER der Modellhoehe ({modell_hoehe_m} m) -- Temperatur MIT "
            f"Hoehenangabe ({temp_mit}) muesste kaelter sein als OHNE ({temp_ohne})."
        )
    else:
        # Echte Hoehe liegt UNTER der Modellhoehe -> mit Hoehenangabe waermer.
        assert tatsaechliche_differenz > 0, (
            f"{name}: echte Hoehe ({elevation_m} m) liegt {abs(hoehen_differenz_m):.0f} m "
            f"UNTER der Modellhoehe ({modell_hoehe_m} m) -- Temperatur MIT "
            f"Hoehenangabe ({temp_mit}) muesste waermer sein als OHNE ({temp_ohne})."
        )

    assert abs(tatsaechliche_differenz) >= erwartete_mindestgroesse, (
        f"{name}: Temperaturunterschied {tatsaechliche_differenz:.2f} C ist kleiner "
        f"als die erwartete Mindestgroesse {erwartete_mindestgroesse:.2f} C "
        f"(abgeleitet aus {hoehen_differenz_m:.0f} m Hoehenunterschied, "
        f"Faustwert {_LAPSE_RATE_C_PER_100M} C/100m x Toleranz {_TOLERANZ_FAKTOR})."
    )
