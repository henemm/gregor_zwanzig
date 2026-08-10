"""TDD RED — Issue #1459: Das Alarm-Protokoll haelt fest, WORUM es ging.

SPEC: docs/specs/modules/feat_1459_alert_protokoll.md (AC-1..AC-4, AC-7)

Geprueft wird die Wettergroesse als **Register-Paar** (``metric_id`` +
``aggregation`` aus ``app.metric_catalog``, O1), die Gefahrenart amtlicher
Warnungen als eigenes Feld ``hazards`` und der Ausloese-Grund ``reason``.

RED-Grund heute: ``_append_alert_log()`` schreibt ausschliesslich
``trip_id``/``sent_at``/``changes_count``/``severity`` -- ``metrics``,
``hazards`` und ``reason`` fehlen komplett; ``services.alert_log`` existiert
nicht.

Mock-frei: echte ``TripAlertService``-Laeufe, echte Persistenz ueber die
pytest-isolierte ``get_data_dir()``-Basis, Transport ueber die vorhandenen
``mail_sink``/``radar_service``-DI-Naehte (kein Netz).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.loader import get_briefings_dir, get_data_dir
from app.models import Corridor, ThunderLevel

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

from tests.helpers.alert_log_fixtures import (
    LAT, LON, fresh_user, gust_alert_trip, read_log, settings_email_only, weather,
)


def _service(user_id: str, sink: list, **kwargs):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)), **kwargs,
    )


def _latest_entry(user_id: str) -> dict:
    entries = read_log(user_id)["entries"]
    assert entries, "Es wurde ueberhaupt kein Protokoll-Eintrag geschrieben."
    return entries[-1]


def _pairs(entry: dict) -> list[tuple[str, str]]:
    assert "metrics" in entry, (
        f"Der Eintrag haelt die Wettergroesse nicht fest: {sorted(entry)!r}"
    )
    return sorted((m["metric_id"], m["aggregation"]) for m in entry["metrics"])


# ───────────────────────────────── AC-1 ────────────────────────────────────

def test_ac1_boeen_aenderung_protokolliert_register_paar_und_grund():
    """AC-1 GIVEN eine Boeen-Vorhersage-Aenderung (20 -> 60 km/h) wird
    erfolgreich versendet
    WHEN der Protokoll-Eintrag geschrieben wird
    THEN steht dort genau ``[("gust", "max")]``, ``hazards`` ist leer und
    ``reason`` ist ``"forecast_change"``."""
    uid = fresh_user("ac1")
    trip = gust_alert_trip("trip-ac1")
    mails: list = []

    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )

    assert sent is True and mails, "Voraussetzung: der Boeen-Alarm muss versendet werden."
    entry = _latest_entry(uid)
    assert _pairs(entry) == [("gust", "max")], (
        f"Erwartet die Register-Kennung ('gust','max'), erhalten: {entry.get('metrics')!r}"
    )
    assert entry.get("hazards") == [], (
        "Eine Vorhersage-Aenderung darf keine Gefahrenart tragen: "
        f"{entry.get('hazards')!r}"
    )
    assert entry.get("reason") == "forecast_change", (
        f"Falscher Grund: {entry.get('reason')!r}"
    )


# ───────────────────────────────── AC-2 ────────────────────────────────────

def test_ac2_beide_korridor_namensraeume_liefern_dasselbe_register_paar():
    """AC-2 GIVEN zwei Grenzwert-Treffer derselben Wettergroesse — einer mit
    der Kennung aus dem Alarm-Namensraum (``thunder_level``), einer mit der
    Kennung aus dem Vergleichs-Katalog (``thunder_level_max``)
    WHEN beide auf Register-Paare abgebildet werden
    THEN tragen beide dasselbe Paar ``("thunder", "max")``."""
    from services.alert_log import register_pairs_from_corridor_hits
    from services.corridor_threshold import evaluate_corridor_thresholds

    hits = evaluate_corridor_thresholds(
        [weather(1, thunder_level_max=ThunderLevel.MED)],
        [
            Corridor(metric="thunder_level", range=[None, 0], notify=True),
            Corridor(metric="thunder_level_max", range=[None, 0], notify=True),
        ],
    )
    assert len(hits) == 2, f"Voraussetzung: zwei Treffer erwartet, erhalten {len(hits)}"
    assert {h.metric for h in hits} == {"thunder_level", "thunder_level_max"}, (
        "Voraussetzung: die beiden Treffer stammen aus verschiedenen Namensraeumen."
    )

    paare = [register_pairs_from_corridor_hits([hit]) for hit in hits]
    assert paare[0] == [("thunder", "max")] and paare[1] == [("thunder", "max")], (
        f"Die beiden Namensraeume laufen auseinander: {paare!r}"
    )


# ───────────────────────────────── AC-3 ────────────────────────────────────

def _save_radar_trip(user_id: str, trip_id: str) -> None:
    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    # #1667 S1: Ankunftszeiten aus dem wanduhr-robusten Helfer statt aus roher
    # now+Nh-Arithmetik — sonst laeuft die Folge ab 23:00 UTC steigend ueber
    # Mitternacht, der Rollover wird nicht erkannt und das Segment landet
    # 23 h in der Vergangenheit ("alle Segmente vorbei" -> 0 Alarme).
    arr0, arr1 = active_window_offsets(LAT, LON, 60, 240)
    (briefings / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Radar-Trip",
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": stage_date(LAT, LON).isoformat(),
            "waypoints": [
                {"id": "W0", "name": "Start", "lat": LAT, "lon": LON,
                 "elevation_m": 1000.0,
                 "arrival_calculated": arr0},
                {"id": "W1", "name": "Ziel", "lat": LAT + 0.1, "lon": LON + 0.1,
                 "elevation_m": 1500.0,
                 "arrival_calculated": arr1},
            ],
        }],
        "report_config": {"trip_id": trip_id, "send_email": True, "send_telegram": False},
    }))


def _frames(is_convective: bool):
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return lambda lat, lon: [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0,
                   is_convective=is_convective),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0,
                   is_convective=is_convective),
    ]


def _run_radar(uid: str, *, is_convective: bool) -> dict:
    from services.radar_service import RadarNowcastService

    _save_radar_trip(uid, "trip-radar")
    mails: list = []
    svc = _service(uid, mails,
                   radar_service=RadarNowcastService(frame_source=_frames(is_convective)))
    assert svc.check_radar_alerts() == 1, "Voraussetzung: der Radar-Alarm muss feuern."
    return _latest_entry(uid)


def test_ac3_konvektiver_nowcast_protokolliert_gewitter():
    """AC-3 GIVEN ein Radar-Alarm mit konvektiver Gefahr
    WHEN protokolliert wird
    THEN steht ``[("thunder","max")]`` in ``metrics`` und ``reason`` ist
    ``"nowcast"``."""
    entry = _run_radar(fresh_user("ac3-konv"), is_convective=True)
    assert _pairs(entry) == [("thunder", "max")], (
        f"Konvektiver Nowcast muss auf Gewitter abbilden: {entry.get('metrics')!r}"
    )
    assert entry.get("reason") == "nowcast", f"Falscher Grund: {entry.get('reason')!r}"


def test_ac3_nicht_konvektiver_nowcast_protokolliert_niederschlag():
    """AC-3 (zweite Haelfte) GIVEN ein Radar-Alarm ohne konvektive Gefahr
    WHEN protokolliert wird
    THEN steht ``[("precipitation","sum")]`` in ``metrics``."""
    entry = _run_radar(fresh_user("ac3-regen"), is_convective=False)
    assert _pairs(entry) == [("precipitation", "sum")], (
        f"Nicht-konvektiver Nowcast muss auf Niederschlag abbilden: "
        f"{entry.get('metrics')!r}"
    )
    assert entry.get("reason") == "nowcast", f"Falscher Grund: {entry.get('reason')!r}"


# ───────────────────────────────── AC-4 ────────────────────────────────────

def test_ac4_amtliche_warnung_protokolliert_gefahrenart_statt_register_paar():
    """AC-4 GIVEN eine amtliche Warnung mit der Gefahrenart ``thunderstorm``
    loest eine eigenstaendige Meldung aus
    WHEN protokolliert wird
    THEN steht ``"thunderstorm"`` unveraendert in ``hazards``, ``metrics``
    bleibt leer (eigenes Vokabular, O1) und ``reason`` ist
    ``"official_alert"``."""
    from services.official_alerts.models import OfficialAlert

    uid = fresh_user("ac4")
    get_data_dir(uid).mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        source="tdd-1459", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=6),
        region_label="Testregion",
    )
    trip = gust_alert_trip("trip-ac4")
    mails: list = []

    sent = _service(uid, mails)._send_official_alert_only(trip, [(alert, ["1"])])

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    entry = _latest_entry(uid)
    assert entry.get("hazards") == ["thunderstorm"], (
        f"Die Gefahrenart fehlt oder ist verfremdet: {entry.get('hazards')!r}"
    )
    assert entry.get("metrics") == [], (
        "Eine Gefahrenart darf NICHT als Register-Kennung protokolliert werden: "
        f"{entry.get('metrics')!r}"
    )
    assert entry.get("reason") == "official_alert", (
        f"Falscher Grund: {entry.get('reason')!r}"
    )


# ───────────────────────────────── AC-7 ────────────────────────────────────

def test_ac7_zwei_ausloeser_ergeben_genau_einen_eintrag():
    """AC-7 GIVEN in EINEM Lauf feuern ZWEI Ausloeser — eine Boeen-Aenderung
    (20 -> 60 km/h) UND ein Gewitter-Stufenwechsel (kein Gewitter -> hoch)
    WHEN die gebuendelte Meldung versendet wird
    THEN entsteht GENAU EIN Protokoll-Eintrag, dessen ``metrics`` BEIDE
    Register-Paare traegt (nicht zwei Eintraege — sonst verdoppelt sich die
    im Cockpit gezeigte Alarm-Zahl).

    Issue #1460: Der zweite Ausloeser war bis dahin ein gerissener
    Wertebereich (``corridors[].notify``). Der ist seit P1a kein
    Alarm-Ausloeser mehr (ADR-0043); die gepruefte Zusicherung — mehrere
    gleichzeitige Ausloeser, EIN Eintrag, ALLE Register-Paare darin — bleibt
    wortgleich, sie wird nur ueber den heute gueltigen zweiten Ausloeger
    gefuehrt: die Gewitter-Empfindlichkeitsstufe (P1b).
    """
    uid = fresh_user("ac7")
    trip = gust_alert_trip("trip-ac7", with_thunder=True)
    vorher = len(read_log(uid)["entries"])
    mails: list = []

    sent = _service(uid, mails).check_and_send_alerts(
        trip,
        [weather(1, gust_max_kmh=20.0, thunder_level_max=ThunderLevel.NONE)],
        fresh_weather=[weather(1, gust_max_kmh=60.0, thunder_level_max=ThunderLevel.HIGH)],
    )

    assert sent is True and len(mails) == 1, (
        "Voraussetzung: genau EINE gebuendelte Meldung geht raus."
    )
    entries = read_log(uid)["entries"]
    assert len(entries) - vorher == 1, (
        f"Erwartet genau 1 neuer Eintrag, erhalten {len(entries) - vorher}."
    )
    assert _pairs(entries[-1]) == [("gust", "max"), ("thunder", "max")], (
        "Beide Ausloeser muessen in EINEM Eintrag stehen: "
        f"{entries[-1].get('metrics')!r}"
    )
