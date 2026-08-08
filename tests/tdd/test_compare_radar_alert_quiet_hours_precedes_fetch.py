"""TDD RED + Invarianten-Waechter — Ruhezeit VOR der Datenbeschaffung
(Issue #1467 S3, AC-4 + AC-5).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md — Aenderung (c)

Heutiger Stand (gemessen 2026-08-08): ``compare_radar_alert.py:117-124`` prueft
die Ruhezeit ERST nach ``_detect_triggered_locations()`` — der Nowcast wird
also fuer jeden Ort abgerufen und erst danach verworfen. Die Ruhezeit-Pruefung
wandert vor den Abruf (Muster ``compare_official_alert.py:105-113``).

Zwei verschiedene Sorten Test in dieser Datei:

* ``test_ruhezeit_verhindert_jeden_nowcast_abruf`` (AC-4) ist ROT — er misst
  die neue Wirkung (0 Abrufe).
* ``test_meldeverhalten_bei_ruhezeit_bleibt_unveraendert`` (AC-5) ist HEUTE
  GRUEN und muss es bleiben: das Vorziehen darf am Melde-Ergebnis nichts
  aendern. Er loest zwei archivierte Zusicherungen ab (#1041 AC-6, #1041b
  AC-5: "Onset wird erkannt, Alarm unterdrueckt") — abgeloest wird die
  Erkennung, NICHT das Melde-Ergebnis.

Mock-frei: echte Presets/Orte, echter Service, zaehlende ``frame_source``-Naht
an der Stelle, an der der Abruf real Kosten verursacht. Kein Netz.
"""
from __future__ import annotations

from app.loader import save_location

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource, clean_uid, compare_radar_service, fresh_uid, location,
    quiet_window_elsewhere, quiet_window_now, radar_preset, reset_radar_cache,
    settings_email_only, write_presets, write_user_tier,
)


def _setup(uid: str, preset_id: str, *, quiet: bool) -> None:
    # premium = kein Tageslimit; Cooldown-Ablage leer -> isoliert die Ruhezeit.
    write_user_tier(uid, "premium")
    save_location(location("loc-qh", "Ruhezeitdorf"), user_id=uid)
    quiet_from, quiet_to = quiet_window_now() if quiet else quiet_window_elsewhere()
    write_presets(uid, [radar_preset(
        preset_id, ["loc-qh"], user_id=uid,
        quiet_from=quiet_from, quiet_to=quiet_to,
    )])


def _run(uid: str) -> tuple[int, list, CountingFrameSource]:
    reset_radar_cache()
    frames = CountingFrameSource(onset_minutes=8)
    mails: list = []
    sent = compare_radar_service(
        uid, settings_email_only(), frames,
        lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    return sent, mails, frames


def test_ruhezeit_verhindert_jeden_nowcast_abruf():
    """AC-4: Laeuft ``check_all_compare_presets()`` waehrend der Ruhezeit des
    Presets, wird fuer KEINEN Ort ein Nowcast abgerufen — der Abrufzaehler an
    der Radar-Naht bleibt bei 0.

    Die Frames wuerden ausloesen, wenn sie geholt wuerden — der Test beweist
    damit den unterlassenen Abruf, nicht einen zufaellig trockenen Ort.

    RED heute: die Ruhezeit greift erst nach der Erkennung, es wird 1x
    abgerufen."""
    uid, preset_id = fresh_uid("ac4"), "cp-1467s3-ac4"
    clean_uid(uid)
    try:
        _setup(uid, preset_id, quiet=True)
        sent, mails, frames = _run(uid)

        assert frames.call_count == 0, (
            f"Waehrend der Ruhezeit darf kein Nowcast abgerufen werden, es wurden "
            f"aber {frames.call_count} Abrufe gezaehlt: {frames.calls!r}"
        )
        assert sent == 0, f"Waehrend der Ruhezeit darf nichts rausgehen ({sent})"
        assert mails == [], f"Waehrend der Ruhezeit versendet: {mails!r}"
    finally:
        clean_uid(uid)


def test_meldeverhalten_bei_ruhezeit_bleibt_unveraendert():
    """AC-5 (Invariante, heute GRUEN): Identische Onset-Bedingung, einmal mit
    gesetztem Ruhezeit-Fenster um „jetzt" und einmal mit einem gesetzten
    Fenster, das „jetzt" NICHT enthaelt.

    Ergebnis vor UND nach dem Vorziehen gleich:
      * Ruhezeit AKTIV   -> kein Alarm
      * Ruhezeit INAKTIV -> Alarm

    Beide Faelle tragen ein GESETZTES Fenster — sonst liefe der zweite Fall in
    den ``not quiet_from``-Kurzschluss und wuerde die Auswertung gar nicht
    beruehren.
    """
    aktiv, inaktiv = fresh_uid("ac5-an"), fresh_uid("ac5-aus")
    clean_uid(aktiv)
    clean_uid(inaktiv)
    try:
        _setup(aktiv, "cp-1467s3-ac5-an", quiet=True)
        _setup(inaktiv, "cp-1467s3-ac5-aus", quiet=False)

        sent_aktiv, mails_aktiv, _f1 = _run(aktiv)
        sent_inaktiv, mails_inaktiv, _f2 = _run(inaktiv)

        assert (sent_aktiv, len(mails_aktiv)) == (0, 0), (
            f"Bei aktiver Ruhezeit darf KEIN Alarm rausgehen — erhalten "
            f"sent={sent_aktiv}, Mails={len(mails_aktiv)}"
        )
        assert (sent_inaktiv, len(mails_inaktiv)) == (1, 1), (
            f"Ausserhalb der Ruhezeit MUSS derselbe Onset alarmieren — erhalten "
            f"sent={sent_inaktiv}, Mails={len(mails_inaktiv)}. Ein zu frueh oder "
            f"zu breit gesetzter Riegel verschluckt echte Alarme (der "
            f"gefaehrlichste Fehler dieser Scheibe)"
        )
    finally:
        clean_uid(aktiv)
        clean_uid(inaktiv)
