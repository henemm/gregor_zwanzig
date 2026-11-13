"""#2795 S3b Teil 1a, Fix-Runde 2 nach Adversary BROKEN (F009 bis F012).

Findings: docs/artifacts/feature-2795-s3b-teil1-zustellung/adversary-dialog-runde2-broken.md

* F009  Wetter-Totalausfall bei Slot 06:45: der Nachliefer-Text nennt 06:45
        (de und en), echter Nachholweg bis zum Draht.
* F010  „Naechstes Briefing" im Zustand „Slot gerade faellig" (06:45-Slot,
        jetzt 06:50, nicht vermerkt) nennt 06:45, Trip und Orte.
* F011  Der Ortsvergleich-Vermerk traegt die Minute selbst: ein 06:45-Vermerk
        bleibt 06:45, auch wenn das Preset danach auf 07:00 geaendert wird;
        ein Bestandsvermerk ohne Minute ergibt 06:00 und wirft nicht.
* F012  Migration eines Abos mit ``alert_rules[].channels`` UND
        ``alert_metric_channels`` (Normalfall der Altdaten aus #1895): nur der
        Altschluessel faellt, die Regeln bleiben wertgleich, das Protokoll
        nennt beides.

Kein Mock: echte Praedikate, echter stuendlicher Compare-Lauf mit schaltbar
gestoertem Transport (Haus-Fixture aus #2587), echte Dateien, Migration als
Subprozess.
"""
from __future__ import annotations

import json
from datetime import time, timedelta

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir
from i18n import t
from services.briefing_slots import BriefingSlotStore, compare_slot_store
from tests.helpers import scheduler_sprache_fixture as fx
from tests.helpers.versand_fixture import rig_starten
# ruff: noqa: F811  (aus = geteilte Fixture als Testparameter)
from tests.tdd.test_compare_briefing_nachholen import (  # noqa: F401  (aus = Fixture)
    D, _ablage_schreiben, _lauf, _nutzer, _pid, _utc, _vergleich, _vergleich_vermerke,
    _vermerk, aus,
)
from tests.tdd.test_compare_mail_fuss_naechster_versand import D23, PARIS_TZ, _preset
from tests.test_2795_fixrunde1 import _abschnitt, _lauf as _migration, _paris_orte
from tests.test_2795_viertelstunden_faelligkeit import _trip_mit_slot, _um


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


# ───────────────────────────── F009 ─────────────────────────────


@pytest.mark.parametrize("lang", ["de", "en"])
def test_f009_wetter_totalausfall_um_0645_nennt_0645(rig, monkeypatch, tmp_path, lang):
    """Trip-Morgen-Slot 06:45, alle Segmente ohne Wetter (Vermerk), danach
    erholt ⇒ Mail und Telegram beginnen mit „… um 06:45 …“ in der Nutzersprache."""
    from app.loader import save_trip

    user = f"u2795-f009-{lang}"
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen(user, lang)
        trip = fx.trip_anlegen(user, [fx.INNSBRUCK, fx.INNSBRUCK])
        trip.report_config.morning_time = time(6, 45)
        save_trip(trip, user_id=user)
        svc = fx.scheduler(rig, user)
        alle = [str(s.segment_id) for s in svc._convert_trip_to_segments(trip, fx.TAG)]
        svc._write_pending_marker(trip, "morning", fx.TAG, failed_segment_ids=alle)
        fx.wetter(monkeypatch, tmp_path, "voll")
        rig.zaehler_leeren()
        assert svc._process_pending_markers(fx.JETZT, set()) == (1, 0)
        k = fx.kanaele(rig)
    praefix = t("versand.scheduler.nachgeliefert", lang, stunde="06:45")
    assert "06:45" in praefix
    assert k["mail"]["plain"].startswith(praefix + "\n\n"), k["mail"]["plain"][:120]
    assert k["telegram"][0].startswith(praefix + "\n\n"), k["telegram"][0][:120]


# ───────────────────────────── F010 ─────────────────────────────


def test_f010_trip_slot_gerade_faellig_zeigt_0645():
    """Slot 06:45, jetzt 06:50 Ortszeit, nicht vermerkt ⇒ der laufende Slot
    ist der Termin: ``at`` und ``local_time`` 06:45 (ueberfaellig)."""
    from services.next_briefing import next_trip_briefing

    user = "u2795-f010-trip"
    trip = _trip_mit_slot(user, "06:45:00")
    jetzt = _um(6, 50)
    nb = next_trip_briefing(trip, jetzt, BriefingSlotStore(user))
    assert nb.get("overdue") is True, f"Vorbedingung: Zweig „jetzt faellig“ nicht getroffen: {nb!r}"
    assert nb["local_time"] == "06:45", nb
    assert nb["at"].startswith(f"{_um(6, 45).astimezone(PARIS_TZ).date().isoformat()}T06:45"), nb


def test_f010_orte_slot_gerade_faellig_zeigt_0645():
    """Ortsvergleich, Slot 06:45, jetzt 06:50 Paris, nicht vermerkt ⇒ 06:45."""
    from services.next_briefing import next_compare_briefing

    user = "u2795-f010-cmp"
    preset = _preset("ort-paris", morning_time="06:45:00", user_id=user)
    jetzt = _utc_paris(6, 50)
    nb = next_compare_briefing(preset, _paris_orte(), jetzt, slot_store=compare_slot_store(user))
    assert nb.get("overdue") is True, f"Vorbedingung: Zweig „jetzt faellig“ nicht getroffen: {nb!r}"
    assert nb["local_time"] == "06:45", nb
    assert nb["at"].startswith("2026-10-23T06:45"), nb


def _utc_paris(stunde: int, minute: int):
    from tests.tdd.test_compare_mail_fuss_naechster_versand import _utc as _utc_zone

    return _utc_zone(PARIS_TZ, D23, stunde) + timedelta(minutes=minute)


# ───────────────────────────── F011 ─────────────────────────────

_ZONE_MINUTE = timedelta(minutes=45)


def _hinweis_im_plain(aus_) -> str:
    mails = aus_.mit.sendungen("email")
    assert len(mails) == 1, f"genau eine nachgeholte Mail erwartet: {aus_.mit!r}"
    return mails[0]["plain_text_body"] or ""


def test_f011_neuer_vermerk_behaelt_0645_trotz_spaeter_geaendertem_preset(aus):
    """Der Zeitplan-Versand um 06:45 scheitert (E-Mail gestoert) ⇒ der Vermerk
    traegt Stunde 6 und Minute 45. Danach stellt der Nutzer das Preset auf
    07:00 um; der Nachholversand nennt trotzdem 06:45."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f011"), morgen="06:45:00")
    aus.stoerung.add("email")
    _lauf(uid, _utc(D, 6) + _ZONE_MINUTE)
    vermerke = _vergleich_vermerke(uid)
    assert len(vermerke) == 1, vermerke
    assert (vermerke[0].get("slot_hour"), vermerke[0].get("slot_minute")) == (6, 45), vermerke[0]

    pfad = get_data_dir(uid) / "briefings" / f"{pid}.json"
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    roh["morning_time"] = "07:00:00"
    pfad.write_text(json.dumps(roh, ensure_ascii=False, indent=2), encoding="utf-8")
    aus.stoerung.clear()
    _lauf(uid, _utc(D, 11))

    erwartet = t("versand.scheduler.zustellung_fehlgeschlagen", "de", stunde="06:45")
    plain = _hinweis_im_plain(aus)
    assert plain.startswith(erwartet), f"F011: Hinweis folgt dem geaenderten Preset: {plain[:160]!r}"


def test_f011_bestandsvermerk_ohne_minute_ergibt_0600_und_wirft_nicht(aus):
    """Bestandsvermerk (nur ``slot_hour`` 6, kein ``slot_minute``), Preset steht
    inzwischen auf 06:45 ⇒ Nachholversand laeuft, der Hinweis nennt 06:00."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f011alt"), morgen="06:45:00")
    alt = _vermerk(pid, "morning", D, 6)
    assert "slot_minute" not in alt
    _ablage_schreiben(uid, [alt])
    _lauf(uid, _utc(D, 11))

    erwartet = t("versand.scheduler.zustellung_fehlgeschlagen", "de", stunde="06:00")
    plain = _hinweis_im_plain(aus)
    assert plain.startswith(erwartet), plain[:160]
    assert _vergleich_vermerke(uid) == [], "Nach Zustellung kein Vermerk mehr"


# ───────────────────────────── F012 ─────────────────────────────


def test_f012_migration_mit_regel_kanaelen_und_altschluessel(tmp_path):
    """Abo mit ``alert_rules[].channels`` UND ``alert_metric_channels`` ⇒ nach
    ``--execute`` fehlt nur der Altschluessel, ``alert_rules`` ist wertgleich,
    das Protokoll nennt die Sonderregel je Metrik UND die alten Regel-Kanaele."""
    uid = "u2795-f012"
    briefings = tmp_path / "users" / uid / "briefings"
    briefings.mkdir(parents=True)
    regeln = [{"id": "r-gust", "kind": "delta", "metric": "wind_gust", "threshold": 5.0,
               "severity": "warning", "enabled": True, "channels": ["telegram"]}]
    obj = {"id": "trip-beides", "kind": "route", "stages": [], "alert_rules": regeln,
           "alert_metric_channels": {"wind_gust": {"telegram": True, "email": False}},
           "alert_channels": {"email": True, "telegram": True, "sms": False, "premium_sms": False}}
    pfad = briefings / "trip-beides.json"
    pfad.write_text(json.dumps(obj), encoding="utf-8")

    p = _migration(tmp_path / "users", "--execute", "--backup-dir", str(tmp_path / "bk"))
    assert p.returncode == 0, p.stderr
    neu = json.loads(pfad.read_text(encoding="utf-8"))
    assert "alert_metric_channels" not in neu
    assert neu.get("alert_rules") == regeln, f"F012: alert_rules veraendert: {neu.get('alert_rules')!r}"
    assert neu == {k: v for k, v in obj.items() if k != "alert_metric_channels"}
    teil = _abschnitt(p.stdout, uid)
    assert "bisherige Sonderregel" in teil and "wind_gust: telegram" in teil, teil
    assert "alte Regel-Kanäle" in teil and "r-gust" in teil, teil
