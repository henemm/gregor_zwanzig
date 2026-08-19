"""TDD RED — Issue #1916, AC-10 (#823-Tagesgrenze gilt auch fuer den
rollierenden Anker).

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-10.

Der rollierende Anker unterliegt derselben Tagespruefung wie der Briefing-
Anker (Issue #823/#1661): ein rollierender Anker vom FALSCHEN Kalendertag
(Ortszeit) darf nicht als "heute" durchgehen.

Angenommene API (Spec Zeile 69, "z.B."): ``WeatherSnapshotService.
save_alarm_anchor(trip_id, target_date, segments, channel)``/``load_alarm_anchor()``,
Signatur analog ``save_dated()``/``load_dated()`` -- der einzige Weg, diesen
neuen Anker-Typ ueberhaupt mit einem Tagesbezug zu erzeugen.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather


def test_ac10_rollierender_anker_vom_falschen_tag_wird_verworfen(caplog):
    """HEUTE ROT: ``save_alarm_anchor()``/``load_alarm_anchor()`` existieren
    nicht -> AttributeError. Nach der Implementierung: ein rollierender
    Anker mit ``target_date=gestern`` darf ``_get_cached_weather(
    tagesgleicher_anker_noetig=True)`` nicht als gueltige Basis liefern.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac10a-{uuid.uuid4().hex[:8]}", "trip-ac10a"
    trip = gust_alert_trip(trip_id)
    gestern = date.today() - timedelta(days=1)
    WeatherSnapshotService(user_id=user_id).save_alarm_anchor(
        trip_id, gestern, [weather(1, gust_max_kmh=10.0)], "email",
    )

    with caplog.at_level(logging.DEBUG):
        ergebnis = TripAlertService(
            settings=settings_email_only(), user_id=user_id,
        )._get_cached_weather(trip, tagesgleicher_anker_noetig=True)

    assert ergebnis is None, (
        "AC-10: ein rollierender Anker vom FALSCHEN Kalendertag "
        f"(target_date={gestern.isoformat()}) darf nicht als "
        "Vergleichsbasis dienen -- dieselbe #823-Tagesgrenze wie beim "
        f"Briefing-Anker. Zurueckgekommen sind {len(ergebnis or [])} Segmente."
    )


def test_ac10_regression_rollierender_anker_vom_heutigen_tag_bleibt_gueltig():
    """Regressionsschutz: ein rollierender Anker mit ``target_date=heute``
    bleibt gueltige Vergleichsbasis -- die Tagespruefung darf nicht zum
    Fallbeil fuer den regulaeren Fall werden.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac10b-{uuid.uuid4().hex[:8]}", "trip-ac10b"
    trip = gust_alert_trip(trip_id)
    heute = date.today()
    WeatherSnapshotService(user_id=user_id).save_alarm_anchor(
        trip_id, heute, [weather(1, gust_max_kmh=17.0)], "email",
    )

    ergebnis = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
    )._get_cached_weather(trip, tagesgleicher_anker_noetig=True)

    assert ergebnis, (
        "AC-10 (Regression): ein rollierender Anker vom HEUTIGEN Kalendertag "
        "muss weiterhin als gueltige Vergleichsbasis dienen."
    )
    assert ergebnis[0].aggregated.gust_max_kmh == 17.0
