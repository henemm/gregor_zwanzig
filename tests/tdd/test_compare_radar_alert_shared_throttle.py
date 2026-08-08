"""TDD RED — Die Sperrzeit des Vergleichs-Nowcast wirkt aus dem GETEILTEN
Speicher, nicht mehr aus einer eigenen Datei (Issue #1467 S3, AC-2 + AC-3).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md — Aenderung (b)

Heutiger Stand (gemessen 2026-08-08): ``compare_radar_alert.py`` fuehrt seine
Sperrzeit in ``compare_radar_alert_throttle.json`` — einem flachen
``{preset_id: iso}``-Dict ohne Dateisperre und ohne atomaren Schreibvorgang.
Der geteilte ``ThrottleStore`` (``throttle_state.json``, ``fcntl``-Lock,
atomar) kennt den Vergleichs-Nowcast nicht.

Ziel: neuer Scope ``compare_radar`` mit dem Preset als Schluessel. Bewusst
NICHT ``radar`` (dort liegen Trip-Kennungen; seit dem #1250-Cutover sind
Trip- und Vergleichs-Kennungen frei gewaehlte Slugs im selben Verzeichnis,
Kollision also real moeglich) und bewusst NICHT ``compare_preset`` (dort liegt
bereits der Aenderungsalarm auf demselben Preset-Schluessel).

RED-Gruende:
- AC-2: ein Eintrag im geteilten Speicher entfaltet heute KEINE Sperrwirkung
  (der Alarm geht raus, ``sent == 1`` statt ``0``).
- AC-3: die Altdatei sperrt heute noch (``sent == 0`` statt ``1``).

Mock-frei: echter ``ThrottleStore`` schreibt/liest die echte Zustandsdatei,
echter Service, echtes Preset auf Platte; kein Netz.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.loader import get_data_dir, save_location

from tests.helpers.nowcast_gate_fixtures import (
    LEGACY_COMPARE_RADAR_FILE, SCOPE_COMPARE_RADAR, CountingFrameSource,
    clean_uid, compare_radar_service, fresh_uid, location, radar_preset,
    read_throttle_state, record_throttle, settings_email_only,
    write_legacy_compare_throttle, write_presets, write_user_tier,
)


def _setup(uid: str, preset_id: str) -> None:
    # premium = kein Tageslimit: dieser Test misst ausschliesslich die
    # Sperrzeit, nicht die Tages-Obergrenze aus Aenderung (a).
    write_user_tier(uid, "premium")
    save_location(location("loc-cd", "Sperrzeitdorf"), user_id=uid)
    write_presets(uid, [radar_preset(preset_id, ["loc-cd"], user_id=uid,
                                     cooldown_minutes=120)])


def _run(uid: str) -> tuple[int, list]:
    mails: list = []
    sent = compare_radar_service(
        uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    return sent, mails


def test_eintrag_im_geteilten_speicher_sperrt_den_vergleichs_nowcast():
    """AC-2: Ein frischer Sperrzeit-Eintrag im geteilten Speicher (Scope
    ``compare_radar``, Schluessel = Preset-Kennung) unterdrueckt den erneuten
    Alarm desselben Presets.

    RED heute: der Vergleichs-Nowcast liest seine eigene Datei und ignoriert
    den geteilten Speicher — der Alarm geht raus."""
    uid, preset_id = fresh_uid("ac2"), "cp-1467s3-ac2"
    clean_uid(uid)
    try:
        _setup(uid, preset_id)
        record_throttle(uid, SCOPE_COMPARE_RADAR, preset_id,
                        datetime.now(timezone.utc) - timedelta(minutes=5))

        sent, mails = _run(uid)

        assert sent == 0, (
            f"Sperrzeit aus dem geteilten Speicher (Scope {SCOPE_COMPARE_RADAR!r}, "
            f"Schluessel {preset_id!r}, vor 5 Minuten, Cooldown 120 Min) muss den "
            f"Alarm unterdruecken — es wurden {sent} Alarm(e) versendet"
        )
        assert mails == [], f"Trotz laufender Sperrzeit versendet: {mails!r}"
    finally:
        clean_uid(uid)


def test_zustellung_bucht_die_sperrzeit_im_geteilten_speicher():
    """AC-2 (Schreibseite): Nach einer erfolgreichen Zustellung liegt die
    Sperrzeit im geteilten Speicher unter Scope ``compare_radar`` mit der
    Preset-Kennung — und ein zweiter Lauf ist dadurch gesperrt.

    Der zweite Lauf ist die eigentliche Zusicherung: eine Buchung, die nicht
    sperrt, waere Buchhaltung ohne Wirkung.

    RED heute: der Eintrag landet in der presetseigenen Altdatei, der geteilte
    Speicher bleibt fuer diesen Scope leer."""
    uid, preset_id = fresh_uid("ac2-write"), "cp-1467s3-ac2-write"
    clean_uid(uid)
    try:
        _setup(uid, preset_id)

        erster, mails1 = _run(uid)
        assert erster == 1, f"Voraussetzung: der erste Lauf muss alarmieren ({erster})"

        state = read_throttle_state(uid)
        assert preset_id in state.get(SCOPE_COMPARE_RADAR, {}), (
            f"Nach der Zustellung fehlt die Sperrzeit im geteilten Speicher unter "
            f"Scope {SCOPE_COMPARE_RADAR!r}: {state!r}"
        )
        assert preset_id not in state.get("radar", {}), (
            "Die Vergleichs-Sperrzeit darf NICHT im Trip-Scope 'radar' landen — "
            f"dort liegen Trip-Kennungen: {state!r}"
        )
        assert preset_id not in state.get("compare_preset", {}), (
            "Die Nowcast-Sperrzeit darf NICHT im Scope 'compare_preset' landen — "
            f"den belegt bereits der Aenderungsalarm auf demselben Schluessel: {state!r}"
        )

        zweiter, mails2 = _run(uid)
        assert zweiter == 0, (
            f"Der zweite Lauf innerhalb des Cooldown-Fensters darf nicht erneut "
            f"versenden ({zweiter})"
        )
        assert len(mails1) + len(mails2) == 1, (
            f"Erwartet genau EINE Mail ueber beide Laeufe, erhalten "
            f"{len(mails1) + len(mails2)}"
        )
    finally:
        clean_uid(uid)


def test_alte_sperrzeit_datei_wirkt_nicht_mehr():
    """AC-3: Ein frischer Eintrag ausschliesslich in der abgeloesten Datei
    ``compare_radar_alert_throttle.json`` — der geteilte Speicher ist leer —
    entfaltet KEINE Sperrwirkung mehr. Der Alarm geht raus. Es gibt bewusst
    keinen Uebernahme-Mechanismus (Spec (b), "Altdaten").

    Die Altdatei bleibt dabei unangetastet liegen: sie wird nicht mehr
    geschrieben (Zeitstempel unveraendert) und nicht geloescht.

    RED heute: die Altdatei sperrt — es geht nichts raus."""
    uid, preset_id = fresh_uid("ac3"), "cp-1467s3-ac3"
    clean_uid(uid)
    try:
        _setup(uid, preset_id)
        alt_zeit = datetime.now(timezone.utc) - timedelta(minutes=5)
        legacy_path = write_legacy_compare_throttle(uid, preset_id, alt_zeit)
        assert read_throttle_state(uid) == {}, (
            "Voraussetzung: der geteilte Speicher muss zu Beginn leer sein"
        )

        sent, mails = _run(uid)

        assert sent == 1, (
            f"Die abgeloeste Datei {LEGACY_COMPARE_RADAR_FILE} darf keine "
            f"Sperrwirkung mehr haben — es wurden {sent} Alarme versendet"
        )
        assert len(mails) == 1, f"Erwartet genau EINE Mail, erhalten {len(mails)}"

        inhalt = json.loads(legacy_path.read_text())
        assert inhalt == {preset_id: alt_zeit.isoformat()}, (
            f"Die Altdatei darf nicht mehr geschrieben werden, wurde aber "
            f"veraendert: {inhalt!r}"
        )
        assert preset_id in read_throttle_state(uid).get(SCOPE_COMPARE_RADAR, {}), (
            "Die neue Sperrzeit muss im geteilten Speicher landen"
        )
    finally:
        clean_uid(uid)


def test_alte_datei_wird_bei_leerer_ausgangslage_gar_nicht_mehr_angelegt():
    """AC-3 (Ergaenzung): Ein Lauf ohne Altdatei legt sie auch nicht neu an —
    der Vergleichs-Nowcast hat keine eigene Sperrzeit-Ablage mehr.

    RED heute: der Service schreibt sie bei jeder Zustellung."""
    uid, preset_id = fresh_uid("ac3-neu"), "cp-1467s3-ac3-neu"
    clean_uid(uid)
    try:
        _setup(uid, preset_id)
        sent, _mails = _run(uid)
        assert sent == 1, f"Voraussetzung: der Lauf muss alarmieren ({sent})"

        legacy = get_data_dir(uid) / LEGACY_COMPARE_RADAR_FILE
        assert not legacy.exists(), (
            f"Die abgeloeste Sperrzeit-Datei {legacy} wurde neu angelegt — "
            "der Vergleichs-Nowcast fuehrt weiterhin eine eigene Ablage"
        )
    finally:
        clean_uid(uid)
