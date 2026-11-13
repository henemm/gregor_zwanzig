"""#2795 S3b Teil 1a, Fix-Runde 1 nach Adversary BROKEN.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.1-§4.3
Findings: docs/artifacts/feature-2795-s3b-teil1-zustellung/adversary-dialog.md

* F001  „Naechstes Briefing" und Orts-Mail-Fusszeile nennen 06:45 (nicht 06:00).
* F002  Nachhol-Hinweis nach gescheitertem 06:45-Versand nennt 06:45
        (Trip und Ortsvergleich, echter Nachholweg bis zum Draht).
* F003  Migrationsprotokoll nennt Abos mit alten ``alert_rules[].channels``;
        die Datei bleibt dabei unveraendert.
* F005  Modell-Default ``send_email`` True; Loader reicht einen vorhandenen
        Altschluessel ``alert_metric_channels`` durch Laden und Speichern.
* F006  Python rundet rasterfremde Altwerte wie Go auf die Viertelstunde ab.
* §4.2  ``send_email=false`` nimmt E-Mail aus dem GEERBTEN Alarm-Anteil des
        Ortsvergleichs; ein gesetztes ``alert_channels.email`` bleibt.
* Haertung Mutation 8 (Regen-Alarm-Pfad) und 10a0 (top-level ``ampel``).

Kein Mock: echte Praedikate, echte Versandwege (``KanalRig``), echte Dateien,
Migration als Subprozess.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import time
from pathlib import Path

import pytest
from freezegun import freeze_time

from app.user import SavedLocation
from i18n import t
from services.briefing_slots import BriefingSlotStore, compare_slot_store
from tests.helpers import scheduler_sprache_fixture as fx
from tests.helpers.versand_fixture import rig_starten
from tests.test_2795_viertelstunden_faelligkeit import _trip_mit_slot, _um
from tests.tdd.test_compare_mail_fuss_naechster_versand import (
    D23, PARIS, PARIS_TZ, _fuss, _preset, _utc,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_2795_alert_metric_channels.py"


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _paris_orte() -> dict:
    return {"ort-paris": SavedLocation(id="ort-paris", name="Fuss-Ort",
                                       lat=PARIS[0], lon=PARIS[1], elevation_m=100)}


# ───────────────────────────── F001 ─────────────────────────────


def test_f001_trip_naechstes_briefing_nennt_0645():
    """Trip mit Morgen-Slot 06:45, Ortszeit 05:00 ⇒ ``local_time`` 06:45."""
    from services.next_briefing import next_trip_briefing

    user = "u2795-f001-trip"
    trip = _trip_mit_slot(user, "06:45:00")
    nb = next_trip_briefing(trip, _um(5, 0), BriefingSlotStore(user))
    assert nb["at"] is not None, nb
    assert nb["local_time"] == "06:45", f"F001: Anzeige nennt {nb['local_time']!r} statt 06:45"


def test_f001_orts_mail_fusszeile_nennt_0645():
    """Orts-Briefing mit Morgen-Slot 06:45, gerendert Fr 23.10. 05:00 ⇒ der
    Abo-Fuss „Naechster Versand" der echten Mail nennt 06:45."""
    from services.next_briefing import next_compare_briefing

    preset = _preset("ort-paris", morning_time="06:45:00")
    jetzt = _utc(PARIS_TZ, D23, 5)
    nb = next_compare_briefing(preset, _paris_orte(), jetzt, strict_after=True)
    assert nb["local_time"] == "06:45", nb
    fuss = _fuss(preset, PARIS, jetzt, D23)
    assert "06:45" in fuss, f"F001: Fusszeile ohne 06:45: {fuss!r}"
    assert "06:00" not in fuss, fuss


# ───────────────────────────── F002 ─────────────────────────────


def test_f002_trip_nachhol_hinweis_nennt_0645(rig, monkeypatch, tmp_path):
    """Trip-Morgen-Slot 06:45, Zustellung gescheitert ⇒ der echte Nachholweg
    stellt Mail und Telegram den Hinweis „… um 06:45 …“ voran."""
    from app.loader import save_trip

    user = "u2795-f002-trip"
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen(user, "de")
        trip = fx.trip_anlegen(user, [fx.INNSBRUCK, fx.INNSBRUCK])
        trip.report_config.morning_time = time(6, 45)
        save_trip(trip, user_id=user)
        svc = fx.scheduler(rig, user)
        svc._write_pending_marker(trip, "morning", fx.TAG, failed_segment_ids=[],
                                  reason="dispatch_error")
        fx.wetter(monkeypatch, tmp_path, "voll")
        rig.zaehler_leeren()
        assert svc._process_pending_markers(fx.JETZT, set()) == (1, 0)
        k = fx.kanaele(rig)
    hinweis = t("versand.scheduler.zustellung_fehlgeschlagen", "de", stunde="06:45")
    assert k["mail"]["plain"].startswith(hinweis + "\n\n"), k["mail"]["plain"][:120]
    assert k["telegram"][0].startswith(hinweis + "\n\n")


def test_f002_vergleich_nachhol_hinweis_nennt_0645(rig, monkeypatch):
    """Ortsvergleich-Morgen-Slot 06:45, Zustellung gescheitert (Vermerk mit
    ``slot_hour`` 6 und ``slot_minute`` 45, Fix-Runde 2 F011: die Minute steht
    im Vermerk) ⇒ der Nachholversand nennt 06:45."""
    from services import scheduler_dispatch_service as sds

    user = "u2795-f002-cmp"
    with freeze_time(fx.JETZT):
        fx.vergleich_engine(monkeypatch)
        fx.nutzer_anlegen(user, "de")
        preset = {**fx.vergleich_preset(user), "morning_time": "06:45:00"}
        rig.zaehler_leeren()
        sds._mark_compare_undelivered(user, preset["id"], "morning", fx.TAG, 6, slot_minute=45)
        sds.process_compare_pending_markers(
            [preset], user, "", rig.settings(), fx.JETZT, fx._vergleich_orte(), [],
        )
        k = fx.kanaele(rig)
    hinweis = t("versand.scheduler.zustellung_fehlgeschlagen", "de", stunde="06:45")
    assert k["mail"] is not None, "Nachholversand fand nicht statt"
    assert k["mail"]["plain"].startswith(hinweis + "\n\n"), k["mail"]["plain"][:120]


# ───────────────────────────── F003 / 10a0 ─────────────────────────────


def _lauf(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True, timeout=60)


def _abschnitt(ausgabe: str, uid: str) -> str:
    start = ausgabe.index(f"== Nutzer {uid} ==")
    ende = ausgabe.find("== Nutzer ", start + 1)
    return ausgabe[start:] if ende < 0 else ausgabe[start:ende]


def test_f003_protokoll_nennt_abo_mit_alten_regel_kanaelen(tmp_path):
    """Trip ohne ``alert_metric_channels``, aber mit aktiver Regel
    ``channels=["telegram", "sms"]`` ⇒ Probelauf UND Ausfuehrung nennen
    Nutzer, Trip, Regel/Metrik und die alten Kanaele; die Datei bleibt
    byte-gleich (nur protokolliert, Regeln unveraendert)."""
    uid = "u2795-f003"
    briefings = tmp_path / "users" / uid / "briefings"
    briefings.mkdir(parents=True)
    trip = {
        "id": "trip-regelkanal", "name": "Regelkanal", "kind": "route", "stages": [],
        "alert_rules": [
            {"id": "r-gust", "kind": "delta", "metric": "wind_gust", "threshold": 5.0,
             "severity": "warning", "enabled": True, "channels": ["telegram", "sms"]},
            {"id": "r-leer", "kind": "delta", "metric": "temperature", "threshold": 5.0,
             "severity": "warning", "enabled": True, "channels": []},
        ],
        "alert_channels": {"email": True, "telegram": False, "sms": False, "premium_sms": False},
    }
    pfad = briefings / "trip-regelkanal.json"
    pfad.write_text(json.dumps(trip, indent=2), encoding="utf-8")
    vorher = pfad.read_bytes()

    for args in ((), ("--execute", "--backup-dir", str(tmp_path / "bk"))):
        p = _lauf(tmp_path / "users", *args)
        assert p.returncode == 0, p.stderr
        teil = _abschnitt(p.stdout, uid)
        assert "trip-regelkanal" in teil, teil
        assert "r-gust" in teil and "wind_gust" in teil, teil
        assert "telegram, sms" in teil, teil
        assert "r-leer" not in teil, f"Regel ohne Kanaele gehoert nicht ins Protokoll: {teil}"
        assert pfad.read_bytes() == vorher, "F003: Abo mit Regel-Kanaelen darf nicht geaendert werden"


def test_10a0_migration_behaelt_top_level_ampel(tmp_path):
    """Ein Abo mit top-level ``ampel`` UND ``alert_metric_channels`` ⇒ nach
    ``--execute`` fehlt nur der Altschluessel, ``ampel`` ist wertgleich."""
    uid = "u2795-10a0"
    briefings = tmp_path / "users" / uid / "briefings"
    briefings.mkdir(parents=True)
    ampel = {"template": "allgemein", "metrics": {"gust": {"alarm_ab": "rot"}}}
    obj = {"id": "trip-ampel", "kind": "route", "stages": [], "ampel": ampel,
           "alert_metric_channels": {"gust": {"email": True}}}
    pfad = briefings / "trip-ampel.json"
    pfad.write_text(json.dumps(obj), encoding="utf-8")
    p = _lauf(tmp_path / "users", "--execute", "--backup-dir", str(tmp_path / "bk"))
    assert p.returncode == 0, p.stderr
    neu = json.loads(pfad.read_text(encoding="utf-8"))
    assert "alert_metric_channels" not in neu
    assert neu.get("ampel") == ampel, f"10a0: top-level ampel veraendert: {neu.get('ampel')!r}"
    assert {k: v for k, v in neu.items()} == {k: v for k, v in obj.items() if k != "alert_metric_channels"}


# ───────────────────────────── F005 ─────────────────────────────


def test_f005_compare_preset_ohne_feld_hat_send_email_true():
    """AC-22: ein ComparePreset ohne ``send_email`` gilt als E-Mail an."""
    from app.models import ComparePreset

    assert ComparePreset(id="p", name="n").send_email is True


def test_f005_loader_reicht_alert_metric_channels_durch(tmp_path):
    """§4.3 lesetolerant: ein Bestands-Trip mit ``alert_metric_channels`` (vor
    der Migration) behaelt den Schluessel ueber Laden UND Speichern
    (Read-Modify-Write) — sonst koennte die Migration ihn nicht mehr nennen."""
    from app.loader import load_trip, save_trip

    user = "u2795-f005-amc"
    briefings = tmp_path / "users" / user / "briefings"
    briefings.mkdir(parents=True)
    amc = {"wind_gust": {"email": True, "telegram": False}}
    roh = {"id": "trip-amc", "name": "Alt", "kind": "route",
           "stages": [{"id": "S1", "name": "E1", "date": "2026-08-20",
                       "waypoints": [{"id": "W1", "name": "S", "lat": 46.0, "lon": 9.0,
                                      "elevation_m": 1200}]}],
           "alert_metric_channels": amc}
    pfad = briefings / "trip-amc.json"
    pfad.write_text(json.dumps(roh), encoding="utf-8")
    trip = load_trip("trip-amc", data_dir=tmp_path, user_id=user)
    assert trip.alert_metric_channels == amc, (
        f"§4.3 lesetolerant: Altschluessel beim Laden verloren: {trip.alert_metric_channels!r}"
    )
    save_trip(trip, user, data_dir=tmp_path)
    assert json.loads(pfad.read_text(encoding="utf-8")).get("alert_metric_channels") == amc


# ───────────────────────────── F006 ─────────────────────────────


@pytest.mark.parametrize("ortszeit, erwartet", [((7, 14), False), ((7, 15), True)])
def test_f006_trip_altwert_0720_gilt_wie_go_als_0715(ortszeit, erwartet):
    """Rasterfremder Altwert 07:20 (vor #2795 gespeichert) ⇒ Python rechnet
    wie Go mit 07:15: faellig ab 07:15, nicht erst im Takt 07:30."""
    from services.trip_report_scheduler import trip_slot_due

    user = "u2795-f006-trip"
    trip = _trip_mit_slot(user, "07:20:00")
    assert trip_slot_due(trip, "morning", _um(*ortszeit), store=BriefingSlotStore(user)) is erwartet


def test_f006_vergleich_altwert_0720_gilt_wie_go_als_0715():
    """Ortsvergleich mit Altwert 07:20 ⇒ faellig um 07:15, Anzeige 07:15."""
    from services.compare_slot_scheduler import presets_due_for_hour
    from services.next_briefing import next_compare_briefing

    user = "u2795-f006-cmp"
    preset = _preset("ort-paris", morning_time="07:20:00", evening_enabled=False, user_id=user)
    um_0715 = _utc(PARIS_TZ, D23, 7).replace(minute=15)
    due = presets_due_for_hour([preset], _paris_orte(), um_0715, store=compare_slot_store(user))
    assert [d.tage_ab_ortstag for d in due] == [0], due
    nb = next_compare_briefing(preset, _paris_orte(), _utc(PARIS_TZ, D23, 5))
    assert nb["local_time"] == "07:15", nb


# ───────────────────────────── §4.2 ─────────────────────────────


@pytest.mark.parametrize("felder, email_erwartet", [
    ({}, True),
    ({"send_email": False}, False),
    ({"send_email": False, "alert_channels": {"email": True, "telegram": True}}, True),
])
def test_42_send_email_false_nimmt_email_nur_aus_dem_geerbten_alarm_anteil(felder, email_erwartet):
    """§4.2 (Orchestrator-Klaerung): ohne ``alert_channels`` erbt der Alarm
    E-Mail nur, wenn ``send_email`` nicht false ist; ein ausdruecklich
    gesetztes ``alert_channels.email`` bleibt wirksam."""
    from services.alert_channels import effective_alert_channels

    preset = {"id": "cp-42", "kind": "vergleich", "send_telegram": True, **felder}
    kanaele = effective_alert_channels(preset, None, "u2795-42")
    assert ("email" in kanaele) is email_erwartet, kanaele
    assert "telegram" in kanaele, kanaele


# ───────────────────── Haertung Mutation 8 (Regen-Alarm) ─────────────────────


def test_m8_regen_alarm_ignoriert_alten_telegram_regel_kanal(monkeypatch):
    """Kanal-Tabelle nur E-Mail, dazu eine aktive Alt-Regel ``channels=["telegram"]``
    (Telegram ist nicht tarifgesperrt) ⇒ der Regen-Alarm loest genau E-Mail
    auf, Telegram bleibt ``channel_disabled``."""
    from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
    from services.alert_log import REASON_CHANNEL_DISABLED
    from tests.helpers.alert_log_fixtures import reason_for_channel
    from tests.helpers.nowcast_gate_fixtures import (
        clean_uid, fresh_uid, settings_no_channel_reachable, write_user_tier,
    )
    from tests.unit.test_radar_alert_channel_resolution import (
        _aufgeloeste_kanaele, _radar_trip, _run_radar, _single_entry, _trip_id,
    )

    uid = fresh_uid("m8")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        trip_id = _trip_id("m8")
        regel = AlertRule(id="rule-2795-tg", kind=AlertRuleKind.DELTA,
                          metric=AlertMetric.WIND_GUST, threshold=20.0,
                          severity=AlertSeverity.WARNING, enabled=True, unit="km/h",
                          channels=["telegram"])
        trip = _radar_trip(trip_id, send_email=True,
                           alert_channels={"email": True, "telegram": False, "sms": False},
                           rules=[regel])
        _run_radar(monkeypatch, uid, [trip], settings_no_channel_reachable())
        entry = _single_entry(uid, trip_id)
        assert _aufgeloeste_kanaele(entry) == {"email"}, entry
        assert reason_for_channel(entry, "telegram") == REASON_CHANNEL_DISABLED, entry
    finally:
        clean_uid(uid)
