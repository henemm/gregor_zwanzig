"""TDD RED — Der Ortsvergleich-Nowcast bekommt die Tages-Obergrenze
(Issue #1467 Scheibe S3, AC-1).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md — Aenderung (a)

Heutiger Stand (gemessen 2026-08-08): ``compare_radar_alert.py`` importiert
``alert_daily_limit`` ueberhaupt nicht. Die Bremse gegen Meldungsfluten fehlt
im Vergleichs-Nowcast vollstaendig — er versendet auch dann noch, wenn das
Tagesbudget des Nutzers laengst aufgebraucht ist.

RED-Grund: der Lauf stellt trotz erreichter Tages-Obergrenze zu (``sent == 1``
statt ``0``), weil keine Pruefung existiert.

Mock-frei: echtes Preset/Ort auf Platte, echter ``CompareRadarAlertService``,
echte Zaehlerdatei ``alert_daily_count.json``; Radar ueber den
``frame_source``-Seam, Versand ueber ``mail_sink``. Kein Netz.
"""
from __future__ import annotations

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource, clean_uid, compare_radar_service, fresh_uid, location,
    quiet_window_now, radar_preset, read_daily_counter, read_log,
    seed_daily_counter, settings_email_only, write_presets, write_user_tier,
)
from app.loader import save_location


def _setup(uid: str, preset_id: str, *, count: int) -> None:
    write_user_tier(uid, "free")  # Tages-Obergrenze 2
    seed_daily_counter(uid, count)
    save_location(location("loc-dl", "Limitdorf"), user_id=uid)
    write_presets(uid, [radar_preset(preset_id, ["loc-dl"], user_id=uid)])


def test_erreichte_tages_obergrenze_unterdrueckt_den_vergleichs_nowcast():
    """AC-1: Tagesbudget des Nutzers ist aufgebraucht (free = 2/Tag, zwei
    Alarme heute bereits verschickt). Ein Nowcast-Onset in einem Preset dieses
    Nutzers fuehrt trotzdem NICHT mehr zu einem Alarm — kein Versand auf
    keinem Kanal, kein neuer Zustellungs-Eintrag im Protokoll, Zaehler bleibt
    stehen.

    RED heute: der Vergleichs-Nowcast kennt keine Tages-Obergrenze und stellt
    zu."""
    uid, preset_id = fresh_uid("ac1"), "cp-1467s3-ac1"
    clean_uid(uid)
    try:
        _setup(uid, preset_id, count=2)
        mails: list = []
        sent = compare_radar_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
            lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 0, (
            f"Tages-Obergrenze erreicht (2 von 2) — der Vergleichs-Nowcast darf "
            f"nicht mehr zustellen, hat aber {sent} Alarm(e) versendet"
        )
        assert mails == [], (
            f"Trotz aufgebrauchtem Tagesbudget wurde versendet: {mails!r}"
        )
        assert read_daily_counter(uid) == 2, (
            f"Der Tageszaehler darf beim unterdrueckten Alarm nicht wachsen, "
            f"steht auf {read_daily_counter(uid)}"
        )
        zustellungen = [
            e for e in read_log(uid)["entries"] if e.get("entity_id") == preset_id
        ]
        assert zustellungen == [], (
            f"Ein unterdrueckter Alarm darf keinen Zustellungs-Eintrag "
            f"erzeugen: {zustellungen!r}"
        )
    finally:
        clean_uid(uid)


def test_freies_tagesbudget_stellt_den_vergleichs_nowcast_weiterhin_zu():
    """Gegenprobe zum obigen Test: bei freiem Tagesbudget geht derselbe Onset
    unveraendert raus, und die Zustellung verbraucht GENAU EINEN Platz des
    Tagesbudgets.

    Ohne diese Haelfte waere AC-1 auch von einer Implementierung erfuellt, die
    den Vergleichs-Nowcast pauschal abschaltet — der gefaehrlichste Fehler
    dieser Scheibe.

    RED heute: der Zaehler wird nicht erhoeht (0 statt 1), weil der
    Vergleichs-Nowcast das Tagesbudget nicht kennt."""
    uid, preset_id = fresh_uid("ac1-frei"), "cp-1467s3-ac1-frei"
    clean_uid(uid)
    try:
        _setup(uid, preset_id, count=0)
        mails: list = []
        sent = compare_radar_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
            lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 1, f"Bei freiem Tagesbudget muss der Onset alarmieren: {sent}"
        assert len(mails) == 1, f"Erwartet genau EINE Mail, erhalten {len(mails)}"
        assert read_daily_counter(uid) == 1, (
            f"Eine zugestellte Vergleichs-Nowcast-Meldung muss GENAU EINEN Platz "
            f"des Tagesbudgets verbrauchen, Zaehler steht auf "
            f"{read_daily_counter(uid)}"
        )
    finally:
        clean_uid(uid)


def test_ruhezeit_verhindert_auch_den_nowcast_abruf():
    """AC-1 (Kostenseite) — TEILWEISE ABGELOEST durch #2050 S3b, deshalb hier
    an der Stufe festgenagelt, an der die Zusicherung UNVERAENDERT gilt.

    Bis #2050 S3b hiess dieser Test
    ``test_erreichte_tages_obergrenze_verhindert_auch_den_nowcast_abruf`` und
    sicherte zu, dass ALLE drei Freigabe-Stufen vollstaendig VOR der
    Datenbeschaffung laufen. Fuer die TAGES-OBERGRENZE ist das seit Szenario 7
    strukturell nicht mehr moeglich: ob eine akut eskalierende Lage das
    erschoepfte Budget durchbrechen darf, entscheidet sich an ihrer
    Dringlichkeit — und die entsteht ERST aus dem Abruf. Der Abruf ist dort
    also die Voraussetzung der Entscheidung, nicht ihre Folge (Spec
    ``feat_2050_s3b_budget_und_unterdrueckungsgrund.md``, AC-20).

    Fuer RUHEZEIT und Sperrzeit gilt die Kostenzusicherung unveraendert — sie
    bleiben harte Stops VOR dem Abruf. Genau das wird hier gemessen, damit die
    Ablösung nicht als „Kostenschutz entfernt" durchrutscht: die
    Fallunterscheidung im Pruefling (``not gate.allowed and not
    _budget_erschoepft``) muss die Ruhezeit weiterhin sofort anhalten.

    ZWEITE HAELFTE (Gegenprobe): bei erschoepftem Budget wird zwar abgerufen,
    zugestellt wird ohne echte Eskalation aber nichts — der teurere Abruf
    kauft keine Meldungsflut ein. Das deckt der Test
    ``test_erreichte_tages_obergrenze_unterdrueckt_den_vergleichs_nowcast``
    oben mit derselben Lage ab."""
    uid, preset_id = fresh_uid("ac1-abruf"), "cp-1467s3-ac1-abruf"
    clean_uid(uid)
    try:
        write_user_tier(uid, "free")
        save_location(location("loc-dl", "Limitdorf"), user_id=uid)
        quiet_from, quiet_to = quiet_window_now()
        write_presets(uid, [radar_preset(
            preset_id, ["loc-dl"], user_id=uid,
            quiet_from=quiet_from, quiet_to=quiet_to,
        )])
        frames = CountingFrameSource(onset_minutes=8)
        sent = compare_radar_service(
            uid, settings_email_only(), frames, lambda subject, body: None,
        ).check_all_compare_presets()

        assert sent == 0, (
            f"Vorbedingung: die Ruhezeit muss den Vergleichs-Nowcast "
            f"unterdruecken, hat aber {sent} Alarm(e) versendet"
        )
        assert frames.call_count == 0, (
            f"Waehrend der Ruhezeit darf kein Nowcast abgerufen werden, es "
            f"wurden aber {frames.call_count} Abrufe gezaehlt: {frames.calls!r}"
        )
    finally:
        clean_uid(uid)
