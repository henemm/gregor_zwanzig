"""Trip Alert-Kanal-Praezedenz: `alert_channels` ersetzt Briefing-Erbe (#1258 S3).

SPEC: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
      (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen", AC-24, AC-25)
KONTEXT: docs/context/feat-1258-s3-trip-alarme-tab.md (Entscheidung D2)

RED-Ursache: `app.trip.Trip` kennt das Feld `alert_channels` noch nicht --
jede Konstruktion mit diesem Keyword-Argument schlaegt bereits mit
`TypeError: __init__() got an unexpected keyword argument 'alert_channels'`
fehl (Trip ist ein reines `@dataclass`, keine `**kwargs`-Toleranz). Das ist
die geforderte RED-Evidenz fuer AC-24/AC-25 -- die nachfolgenden Assertions
in jedem Test pruefen zusaetzlich die ERWARTETE Semantik, sobald das Feld
existiert (GREEN-Zielbild).

`TripAlertService._effective_alert_channels` (src/services/trip_alert.py:988-1022)
liest `trip.alert_channels` heute nicht -- nach der Implementierung muss ein
gesetztes `alert_channels` NUR den geerbten Briefing-Anteil ersetzen (Legacy-
Pfad ohne aktive Regeln :1010-1011 UND per-Regel-Fallback :1017-1018);
nicht-leere `rule.channels`-Overrides (#638) und das SMS-Tier-Gate bleiben
unveraendert.

Mock-frei: echte `Trip`-/`AlertRule`-/`TripReportConfig`-Objekte, echter
`TripAlertService`, echter `sms_allowed()`-Tier-Lookup ueber echte
`data/users/<id>/user.json` (Vorbild:
tests/tdd/test_issue_1069_tier_channel_gating.py, Klasse
`TestAC8AlertChannelsRespectTier` + Helper `_make_alert_trip`/`clean_user_dirs`).
"""
from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures (Vorbild: test_issue_1069_tier_channel_gating.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def clean_user_dirs():
    """Raeumt echte data/users/tdd-1258-s3-*-Verzeichnisse vor und nach dem Test."""
    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for user_id in created:
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)


def _write_user_json(user_id: str, tier: str | None) -> None:
    path = Path(f"data/users/{user_id}")
    path.mkdir(parents=True, exist_ok=True)
    data = {"id": user_id}
    if tier is not None:
        data["tier"] = tier
    (path / "user.json").write_text(json.dumps(data))


def _stage():
    from app.trip import Stage, Waypoint
    return Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )


def _service(user_id: str = "tdd-1258-s3-default"):
    from app.config import Settings
    from services.trip_alert import TripAlertService
    return TripAlertService(settings=Settings().with_user_profile(user_id), user_id=user_id)


def _rule(channels: list[str]):
    from app.models import AlertRule, AlertRuleKind, AlertMetric, AlertSeverity
    return AlertRule(
        id=f"r-{len(channels)}-{'-'.join(channels) or 'inherit'}",
        kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.WIND_GUST,
        threshold=50.0, severity=AlertSeverity.WARNING, enabled=True,
        channels=channels,
    )


# ---------------------------------------------------------------------------
# AC-24 — alert_channels=None: exakt heutiges Verhalten
# ---------------------------------------------------------------------------

def test_trip_alert_channels_legacy_unchanged():
    """AC-24: Given ein Bestandstrip ohne `alert_channels` (explizit `None`)
    / When die effektiven Alert-Kanaele berechnet werden / Then ergeben sie
    sich exakt wie heute -- geerbte Briefing-Kanaele, `{"email"}`-Default ohne
    report_config, per-Regel-Overrides gewinnen weiter."""
    from app.trip import Trip
    from app.models import TripReportConfig

    stage = _stage()
    svc = _service("tdd-1258-s3-legacy")

    # (a) ohne report_config -> {"email"} (Default NUR bei fehlendem report_config).
    trip_no_config = Trip(
        id="t-legacy-a", name="Legacy A", stages=[stage],
        alert_channels=None,
    )
    assert svc._effective_alert_channels(trip_no_config) == {"email"}, (
        "RED: alert_channels=None ohne report_config muss weiterhin auf den "
        "E-Mail-Default fallen (heutiges Legacy-Verhalten, unveraendert)."
    )

    # (b) report_config mit send_telegram=True (send_email-Default bleibt True)
    #     -> geerbte Briefing-Kanaele {"email", "telegram"}.
    trip_with_config = Trip(
        id="t-legacy-b", name="Legacy B", stages=[stage],
        alert_channels=None,
        report_config=TripReportConfig(trip_id="t-legacy-b", send_telegram=True),
    )
    assert svc._effective_alert_channels(trip_with_config) == {"email", "telegram"}, (
        "RED: alert_channels=None muss weiterhin die Briefing-Kanaele aus "
        "report_config erben (unveraendert)."
    )

    # (c) aktive Regel mit eigenem channels-Override gewinnt weiter (#638).
    trip_with_rule = Trip(
        id="t-legacy-c", name="Legacy C", stages=[stage],
        alert_channels=None,
        alert_rules=[_rule(["telegram"])],
        report_config=TripReportConfig(trip_id="t-legacy-c"),  # send_email default True
    )
    assert svc._effective_alert_channels(trip_with_rule) == {"telegram"}, (
        "RED: eine Regel mit eigenem channels-Override muss weiterhin gewinnen, "
        "unabhaengig von alert_channels=None (#638-Verhalten unveraendert)."
    )


# ---------------------------------------------------------------------------
# AC-25 — gesetztes alert_channels ersetzt NUR den Briefing-Erbe-Anteil
# ---------------------------------------------------------------------------

def test_trip_alert_channels_replaces_briefing_inheritance():
    """AC-25: Given ein Trip mit gesetztem `alert_channels` (nur Telegram
    aktiv) / When ein Alert versendet wird / Then ersetzt das Kanal-Set den
    geerbten Briefing-Anteil -- obwohl `report_config.send_email=True` ist,
    erbt eine Regel OHNE eigene `channels` das neue Set (nur Telegram),
    NICHT die Briefing-Kanaele."""
    from app.trip import Trip
    from app.models import TripReportConfig

    stage = _stage()
    svc = _service("tdd-1258-s3-replace")

    trip = Trip(
        id="t-replace", name="Replace", stages=[stage],
        alert_channels={"email": False, "telegram": True, "sms": False},
        alert_rules=[_rule([])],  # aktive Regel OHNE eigenen Override -> erbt neues Set
        report_config=TripReportConfig(trip_id="t-replace"),  # send_email default True
    )
    channels = svc._effective_alert_channels(trip)
    assert channels == {"telegram"}, (
        "RED: gesetztes alert_channels muss den geerbten Briefing-Anteil "
        f"ersetzen (report_config.send_email=True darf NICHT durchschlagen), "
        f"bekommen: {channels!r}"
    )


def test_trip_alert_channels_rule_override_still_wins():
    """AC-25: Given ein Trip mit gesetztem `alert_channels` (nur Telegram)
    UND einer zusaetzlichen aktiven Regel mit eigenem `channels=["email"]`
    / When die effektiven Kanaele berechnet werden / Then ist das Ergebnis
    die Union {telegram, email} -- der explizite Regel-Override gewinnt
    weiterhin neben dem (ersetzten) geerbten Set."""
    from app.trip import Trip

    stage = _stage()
    svc = _service("tdd-1258-s3-override")

    trip = Trip(
        id="t-override", name="Override", stages=[stage],
        alert_channels={"email": False, "telegram": True, "sms": False},
        alert_rules=[_rule([]), _rule(["email"])],
    )
    channels = svc._effective_alert_channels(trip)
    assert channels == {"telegram", "email"}, (
        "RED: Union aus geerbtem (ersetztem) alert_channels-Set {telegram} und "
        f"explizitem Regel-Override {{email}} erwartet, bekommen: {channels!r}"
    )


def test_trip_alert_channels_sms_tier_gate(clean_user_dirs):
    """AC-25: Given ein Trip mit `alert_channels` inkl. `sms=True`, dessen
    Besitzer KEINE SMS-Berechtigung hat (free-Tier) / When die effektiven
    Kanaele berechnet werden / Then bleibt das SMS-Tier-Gate aktiv -- "sms"
    fehlt im Ergebnis, andere aktivierte Kanaele bleiben erhalten."""
    from app.trip import Trip

    user_id = clean_user_dirs("tdd-1258-s3-sms-gate")
    _write_user_json(user_id, tier=None)  # kein tier-Feld -> Default free (kein SMS)

    stage = _stage()
    trip = Trip(
        id="t-sms-gate", name="SMS Gate", stages=[stage],
        alert_channels={"email": False, "telegram": True, "sms": True},
    )
    svc = _service(user_id)
    channels = svc._effective_alert_channels(trip)

    assert "sms" not in channels, (
        "RED: SMS-Tier-Gate muss auch fuer ein gesetztes alert_channels=sms:True "
        f"greifen (free-Tier, kein SMS erlaubt), bekommen: {channels!r}"
    )
    assert "telegram" in channels, (
        f"Telegram muss trotz SMS-Gate erhalten bleiben, bekommen: {channels!r}"
    )
