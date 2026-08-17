"""TDD RED — Issue #1916, AC-9 (kritischer Regressionstest: Trend-Erkennung).

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-9; Kontext-Dokument
"Zentraler Zusatzbefund"; ADR-0056 "Verworfene Alternativen".

Ein naives "Anker bei jedem Check-Lauf ohne Alarm ueberschreiben" schrumpft
das Δ-Vergleichsfenster auf ein Check-Intervall (15 Min) und bricht damit die
Erkennung eines langsamen, ueber mehrere Laeufe kumulierenden Anstiegs, bei
dem jeder EINZELSCHRITT unter der Schwelle bleibt. Dieser Test simuliert
genau diese Sequenz und beweist, dass die Vergleichsbasis stabil bleibt,
SOLANGE weder Trigger (a, Alarm) noch Trigger (b, 4h-Ceiling) greifen.

Methodik: die Vergleichsbasis (``cached``) wird je Lauf explizit auf den
ROLLIERENDEN Anker aktualisiert, FALLS er nach dem vorherigen Lauf existiert
(das ist genau das, was ``_get_cached_weather()`` nach Slice 2 am naechsten
Check-Tick auch tun wuerde) -- so isoliert der Test die Schreibtrigger-Logik
in ``check_and_send_alerts()`` selbst, ohne den (noch unbekannten) Anker-
Prioritaets-Code in ``_get_cached_weather()`` mitzusimulieren.

Mutations-Gegenprobe (Spec-Vorgabe): ueberschriebe eine Implementierung den
rollierenden Anker bei JEDEM Lauf (auch ohne Alarm, auch unterhalb der
Ceiling), wuerde ``load_alarm_anchor()`` nach jedem Sub-Schwellen-Lauf einen
frischen Wert liefern -- die Testschleife wuerde diesen dann als naechste
Vergleichsbasis uebernehmen, jeder Folgeschritt bliebe unterschwellig, und
der LETZTE Lauf (der nur GEGEN DEN URSPRUENGLICHEN Anker ueber die Schwelle
kommt) wuerde NICHT mehr ausloesen -- die abschliessende Zusicherung faellt
dann durch.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather

# Standard-Schwelle wind_gust: 20 km/h Delta (alert_preset.py:13).
_URSPRUNGSWERT = 10.0
# Jeder Schritt ggue. dem URSPRUENGLICHEN Anker: Deltas 2,5,8,12,17,32 -- die
# ersten fuenf bleiben unter 20, nur der kumulierte letzte Schritt (32) reisst
# die Schwelle. Kein Schritt-ueber-Schritt-Delta wird geprueft (irrelevant --
# die Engine vergleicht immer gegen den AKTUELLEN Anker, nie gegen den
# vorherigen Messwert).
_SCHRITTE = [12.0, 15.0, 18.0, 22.0, 27.0, 42.0]


def _wetter(gust_kmh: float, fetched_at: datetime):
    return dataclasses.replace(weather(1, gust_max_kmh=gust_kmh), fetched_at=fetched_at)


def test_ac9_kumulativer_trend_ueber_mehrere_laeufe_loest_dennoch_aus():
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac9-{uuid.uuid4().hex[:8]}", "trip-ac9"
    trip = gust_alert_trip(trip_id)
    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    snap_svc = WeatherSnapshotService(user_id=user_id)

    aktueller_anker = [_wetter(_URSPRUNGSWERT, datetime.now(timezone.utc))]
    ausgeloest_je_lauf: list[bool] = []
    for wert in _SCHRITTE:
        fresh = [_wetter(wert, datetime.now(timezone.utc))]
        ausgeloest = svc.check_and_send_alerts(trip, aktueller_anker, fresh_weather=fresh)
        ausgeloest_je_lauf.append(ausgeloest)
        rollierend = snap_svc.load_alarm_anchor(trip_id)
        if rollierend:
            aktueller_anker = rollierend

    assert not any(ausgeloest_je_lauf[:-1]), (
        f"Fixtur-Schutz: jeder EINZELSCHRITT ({_SCHRITTE[:-1]} gegen "
        f"{_URSPRUNGSWERT}) muss unter der 20-km/h-Schwelle bleiben. "
        f"Ausgeloest je Lauf: {ausgeloest_je_lauf}"
    )
    assert ausgeloest_je_lauf[-1], (
        f"AC-9: das KUMULIERTE Delta seit dem zuletzt GESCHRIEBENEN Anker "
        f"({_SCHRITTE[-1]} vs. urspruenglich {_URSPRUNGSWERT} = "
        f"{_SCHRITTE[-1] - _URSPRUNGSWERT} km/h) muss spaetestens im "
        f"letzten Lauf einen Alarm ausloesen -- die Vergleichsbasis bleibt "
        f"stabil, solange kein Alarm feuert und die 4h-Ceiling nicht "
        f"ueberschritten ist. Ausgeloest je Lauf: {ausgeloest_je_lauf}. "
        f"HEUTE ROT, solange load_alarm_anchor() nicht existiert."
    )
