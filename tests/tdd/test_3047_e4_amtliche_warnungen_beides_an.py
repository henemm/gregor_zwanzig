"""Issue #3047 Runde 7, Befund E4: Amtliche Warnungen im Altbestand-Mischzustand.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(„Nachtrag Runde 7", PO-Entscheidung „Amtliche Warnungen Altbestand-Mischzustand",
AC-26).

PO-Regel (Trip UND Orte): Ist der Briefing-Schalter (``official_alerts_enabled``)
ODER der Alarm-Schalter (``official_warnings.enabled`` bzw. Altfeld
``official_alert_triggers_enabled``) an, gilt „beides an": das Briefing enthaelt
die Warnungen UND der amtliche Alarm geht raus. Nur wenn beide aus sind, ist
beides aus. Der Editor zeigt denselben Wert (``amtlicheWarnungen.ts``).

Weg je Fall (kein Mock-Theater): Konfiguration als gespeichertes JSON ->
echter Loader -> echter Briefing-/Alarm-Dienst -> Transport-Mitschrift bzw.
``mail_sink``. Ersetzt sind nur die Netz-Naehte (Warnquelle als echtes
Quell-Objekt ueber die Registrierungs-Naht, Wetter ueber den FixtureProvider
der Testumgebung, Routen-Geometrie des Alarms). Je Fall laufen zwei Nutzer mit
verschiedener Konfiguration ueber denselben Weg (Mandantentrennung).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, load_all_trips, load_trip
from services.official_alerts.models import OfficialAlert
from services.trip_alert import TripAlertService
from services.trip_report_scheduler import TripReportSchedulerService

from tests.helpers.briefing_imminent_fixtures import (
    FakeOfficialAlertSource, nur_diese_warnquelle,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._alarm_amtlich_fixtures import (
    amtlich_dict, amtliche_warnung, segmentgeometrie, stelle_amtliche_quelle,
    stelle_cache_fuer_amtliche_kette,
)
from tests.tdd._compare_kette_fixtures import transport_einrichten
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV
from tests.tdd.test_2794_teil3_amtliche_warnungen_lesart import FEHLT, _vergleich_lauf
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import _AT, _settings_all_channels, _write_tier
from tests.tdd.test_issue_1040_alerts_toggle import (
    _capture_official_alerts_enabled, _preset, _resolvable_location,
)

INNSBRUCK = (47.2692, 11.4041)
WARN_LABEL = "Sturmwarnung E4"

# (Name, official_alerts_enabled, official_warnings, official_alert_triggers_enabled,
#  erwartet „an" fuer Briefing UND Alarm). ``None`` = Feld fehlt.
FAELLE = [
    ("briefing_aus_alarm_altfeld_default", False, FEHLT, None, True),
    ("briefing_aus_alarm_an_migriert", False, {"enabled": True}, None, True),
    ("briefing_an_alarm_aus_migriert", True, {"enabled": False}, None, True),
    ("briefing_fehlt_alarm_aus_migriert", None, {"enabled": False}, None, True),
    ("briefing_an_alarm_altfeld_aus", True, FEHLT, False, True),
    ("nur_sources", None, {"sources": ["tdd-2794-ac20"]}, None, True),  # Quelle des Orte-Laufs
    # official_warnings ohne Schluessel ``enabled`` = nicht migriert -> Altfeld (fehlend = an).
    ("briefing_aus_ow_ohne_enabled", False, {"sources": ["tdd-2794-ac20"]}, None, True),
    ("beides_aus", False, {"enabled": False}, None, False),
    ("beides_aus_altfeld", False, FEHLT, False, False),
]
IDS = [f[0] for f in FAELLE]
#: Gegen-Nutzer je Fall: dieselbe Strecke, die andere Konfiguration.
GEGEN_AN = (None, FEHLT, None)  # alles Standard -> an
GEGEN_AUS = (False, {"enabled": False}, None)  # beides aus


def _felder(d: dict, oae, ow, trig) -> dict:
    for k in ("official_alerts_enabled", "official_warnings", "official_alert_triggers_enabled"):
        d.pop(k, None)
    if oae is not None:
        d["official_alerts_enabled"] = oae
    if ow is not FEHLT:
        d["official_warnings"] = json.loads(json.dumps(ow))
    if trig is not None:
        d["official_alert_triggers_enabled"] = trig
    return d


def _gegen(an: bool) -> tuple:
    return GEGEN_AUS if an else GEGEN_AN


def _aufraeumen(*uids: str) -> None:
    for uid in uids:
        shutil.rmtree(get_data_dir(uid), ignore_errors=True)


# ───────────────────────── Trip: Briefing ─────────────────────────────────────


def _trip_briefing_lauf(monkeypatch, oae, ow, trig) -> tuple[list, int]:
    """Trip-JSON -> ``load_all_trips`` -> ``send_test_report`` -> Mail-Mitschrift.
    Gibt (Mail-Sendungen, Abrufe der Warnquelle) zurueck."""
    uid = f"tdd-3047e4-trip-{uuid.uuid4().hex[:6]}"
    ordner = get_data_dir(uid)
    (ordner / "briefings").mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium", "mail_to": f"{uid}@example.invalid",
        "email_verified_at": "2026-10-01T08:00:00Z",
    }))
    heute = datetime.now(timezone.utc).date().isoformat()
    trip = _felder({
        "id": f"trip-{uid}", "name": "E4 Trip", "kind": "route",
        "stages": [{"id": "T1", "name": "Etappe", "date": heute, "waypoints": [
            {"id": "G1", "name": "Start", "lat": INNSBRUCK[0], "lon": INNSBRUCK[1], "elevation_m": 600},
            {"id": "G2", "name": "Ziel", "lat": INNSBRUCK[0] + 0.02, "lon": INNSBRUCK[1] + 0.02,
             "elevation_m": 900},
        ]}],
        "report_config": {"send_email": True, "send_sms": False, "send_telegram": False,
                          "send_premium_sms": False},
        "alert_rules": [],
    }, oae, ow, trig)
    (ordner / "briefings" / f"{trip['id']}.json").write_text(json.dumps(trip))
    geladen = next(t for t in load_all_trips(uid) if t.id == trip["id"])
    mit = aufzeichner_installieren(monkeypatch)
    quelle = FakeOfficialAlertSource(*INNSBRUCK, alerts=[_warnung_ganzer_tag()])
    try:
        with nur_diese_warnquelle(quelle):
            TripReportSchedulerService(user_id=uid).send_test_report(geladen, "morning")
        return mit.sendungen("email"), quelle.fetch_calls
    finally:
        _aufraeumen(uid)


def _warnung_ganzer_tag() -> OfficialAlert:
    """Gilt zwei Tage vor bis zwei Tage nach jetzt: deckt die Etappe von heute
    unabhaengig von der Laufzeit-Uhr."""
    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-3047e4", hazard="wind", level=3, label=WARN_LABEL,
        valid_from=jetzt - timedelta(days=2), valid_to=jetzt + timedelta(days=2),
        region_label="Testregion",
    )


def _hat_warnung(sendungen: list) -> bool:
    return any(WARN_LABEL in (s["body"] or "") + (s["plain_text_body"] or "") for s in sendungen)


@pytest.mark.parametrize("name, oae, ow, trig, an", FAELLE, ids=IDS)
def test_trip_briefing_enthaelt_warnungen_nach_regel(monkeypatch, name, oae, ow, trig, an):
    transport_einrichten(monkeypatch)
    mails, abrufe = _trip_briefing_lauf(monkeypatch, oae, ow, trig)
    gegen_mails, gegen_abrufe = _trip_briefing_lauf(monkeypatch, *_gegen(an))

    assert mails and gegen_mails, f"{name}: Vorbedingung, beide Briefings zugestellt"
    assert _hat_warnung(mails) is an and (abrufe > 0) is an, (
        f"{name}: Briefing-Warnungen erwartet={an}, Abrufe={abrufe} "
        "(Regel: Briefing ODER Alarm an -> beides an)"
    )
    assert _hat_warnung(gegen_mails) is (not an), f"{name}: Gegen-Nutzer vermischt"


# ───────────────────────── Trip: Alarm ────────────────────────────────────────


def _trip_alarm_lauf(monkeypatch, oae, ow, trig) -> list:
    """Golden-Trip-JSON mit den Feldern -> ``load_trip`` ->
    ``check_official_alert_triggers`` -> ``_send_official_alert_only`` -> Mitschrift."""
    uid = f"tdd-3047e4-alarm-{uuid.uuid4().hex[:6]}"
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    _write_tier(uid, "premium")
    d = _felder(amtlich_dict("golden_amtlich_fall1"), oae, ow, trig)
    d["id"] = f"trip-{uid}"
    d["alert_channels"] = {"email": True}
    trip = load_trip(d, user_id=uid)
    svc = TripAlertService(settings=_settings_all_channels(), user_id=uid)
    try:
        with freeze_time(_AT):
            notices = svc.check_official_alert_triggers(trip)
            if notices:
                svc._send_official_alert_only(trip, notices)
        return mit.sendungen("email")
    finally:
        _aufraeumen(uid)


@pytest.mark.parametrize("name, oae, ow, trig, an", FAELLE, ids=IDS)
def test_trip_alarm_nach_regel(monkeypatch, name, oae, ow, trig, an):
    alert = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
    stelle_amtliche_quelle(monkeypatch, [alert])
    stelle_cache_fuer_amtliche_kette(monkeypatch, route_geometrie=segmentgeometrie(_AT))

    mails = _trip_alarm_lauf(monkeypatch, oae, ow, trig)
    gegen = _trip_alarm_lauf(monkeypatch, *_gegen(an))

    assert bool(mails) is an, f"{name}: Alarm erwartet={an}, Mails={len(mails)}"
    assert bool(gegen) is (not an), f"{name}: Gegen-Nutzer vermischt"


# ───────────────────────── Orte: Alarm ────────────────────────────────────────


@pytest.mark.parametrize("name, oae, ow, trig, an", FAELLE, ids=IDS)
def test_orte_alarm_nach_regel(name, oae, ow, trig, an):
    mails = _vergleich_lauf(ow, oae, trig)
    gegen_oae, gegen_ow, gegen_trig = _gegen(an)
    gegen = _vergleich_lauf(gegen_ow, gegen_oae, gegen_trig)

    assert bool(mails) is an, f"{name}: Orts-Alarm erwartet={an}, Mails={mails!r}"
    assert bool(gegen) is (not an), f"{name}: Gegen-Nutzer vermischt"


# ───────────────────────── Orte: Briefing ─────────────────────────────────────


def _orte_briefing_abruf(tmp_path, oae, ow, trig) -> object:
    """Preset (Versandpfad ``send_one_compare_preset``) -> Abruf-Schalter, den
    die Vergleichs-Engine fuer die amtlichen Warnungen bekommt (#1040-Naht)."""
    loc = _resolvable_location("loc-3047e4")
    preset = _felder(_preset(f"cp-3047e4-{uuid.uuid4().hex[:4]}", None, "loc-3047e4"), oae, ow, trig)
    preset["_user_id"] = f"tdd-3047e4-orte-{uuid.uuid4().hex[:6]}"
    return _capture_official_alerts_enabled(preset, loc, tmp_path)


@pytest.mark.parametrize("name, oae, ow, trig, an", FAELLE, ids=IDS)
def test_orte_briefing_holt_warnungen_nach_regel(tmp_path, name, oae, ow, trig, an):
    abruf = _orte_briefing_abruf(tmp_path, oae, ow, trig)
    gegen = _orte_briefing_abruf(tmp_path, *_gegen(an))

    assert abruf is an, f"{name}: Orts-Briefing-Abruf erwartet={an}, erhalten={abruf!r}"
    assert gegen is (not an), f"{name}: Gegen-Nutzer vermischt"


# ───────────────────────── Orte: Vorschau = Versand ───────────────────────────


def _orte_vorschau_abruf(oae, ow, trig) -> object:
    """Gespeichertes Preset -> ``ComparePreviewService`` -> Abruf-Schalter an
    der Vergleichs-Engine (dieselbe Naht wie der Versand-Fall oben)."""
    import services.comparison_engine as ce_mod
    from app.loader import get_data_root, save_location
    from services.compare_preview_service import ComparePreviewService
    from tests.helpers.compare_briefings import write_compare_briefings
    from tests.tdd.test_issue_1040_alerts_toggle import _OfficialAlertsEnabledRecorded

    uid = f"tdd-3047e4-vorschau-{uuid.uuid4().hex[:6]}"
    loc = _resolvable_location("loc-3047e4v")
    save_location(loc, user_id=uid)
    preset = _felder(_preset("cp-3047e4v", None, "loc-3047e4v"), oae, ow, trig)
    preset["user_id"] = uid
    write_compare_briefings(get_data_root() / "users" / uid, [preset])
    original = ce_mod.ComparisonEngine

    class _Aufzeichner(original):  # echte Unterklasse, bricht vor dem Netz ab
        @staticmethod
        def run(*args, **kwargs):
            raise _OfficialAlertsEnabledRecorded(kwargs.get("official_alerts_enabled", "FEHLT"))

    ce_mod.ComparisonEngine = _Aufzeichner
    try:
        with pytest.raises(_OfficialAlertsEnabledRecorded) as info:
            ComparePreviewService().render_all_channels("cp-3047e4v", user_id=uid)
        return info.value.official_alerts_enabled
    finally:
        ce_mod.ComparisonEngine = original
        _aufraeumen(uid)


@pytest.mark.parametrize("name, oae, ow, trig, an", FAELLE, ids=IDS)
def test_orte_vorschau_holt_warnungen_wie_versand(name, oae, ow, trig, an):
    assert _orte_vorschau_abruf(oae, ow, trig) is an, f"{name}: Vorschau weicht vom Versand ab"
