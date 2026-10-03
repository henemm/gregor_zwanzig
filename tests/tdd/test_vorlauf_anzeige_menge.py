"""TDD RED — Issue #2261 Teil A (A-1), AC-7: Anzeige-Menge entfaellt, wenn
ihr Fenster am Quell-Horizont abgeschnitten ist.

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md — AC-7,
Implementation Details §4 ("Anzeige-Menge `onset_precip_mm`").

`onset_precip_mm` ist die Menge der ersten 60 Minuten AB DEM BEGINN. Die
Quelle reicht 180 Minuten weit; bei `onset + 60 > 180` (Onset > 120) fehlt
ein Teil des Fensters, die Zahl waere falsch klein (Onset 150: 1,5 statt
2,0 mm bei 2 mm/h; Onset 170: 0,5 mm). Sie wird deshalb AN DER QUELLE
(`RadarNowcastService._derive_result`) auf `None` gesetzt; die Intensitaet
bleibt, `window_precip_mm`/`max_rate_mm_h` bleiben unberuehrt. Alle vier
Kanaele lesen dasselbe Feld -- keine Kanal-eigene Sonderlogik.

Zwei Wirkorte, beide geprueft:
  * QUELLE: echtes `NowcastResult` aus echtem `RadarNowcastService` mit
    festen 15-Minuten-Frames (kein Mock, nur die `frame_source`-Naht);
  * KANAELE: echter Prueflauf (`AlarmPruefstrecke`) -- die Mengenangabe
    erscheint nur in der Kurzform (`sms_body`), die SMS, Premium-SMS und
    Telegram-Kurzform tragen. Telegram laeuft deshalb im Stil `kurzform`;
    E-Mail wird zusaetzlich gegen jede Langform-Mengenzahl geprueft.
Die Positivprobe (`test_menge_bleibt_bei_vollem_fenster`) eicht das
Mengentoken-Muster an einem echten Alarm, damit die Abwesenheitspruefung
bei Onset 150 etwas misst.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from tests.helpers.nowcast_gate_fixtures import reset_radar_cache
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_vorlauf_kanalparitaet import (
    ISLAND_LAT, ISLAND_LON, MENGE_LANGFORM, MENGEN_TOKEN, RATE_MM_H,
    alle_kanaele_konfig, feste_frames, kurzer_trip, pruef_lauf, uid,
)

_JETZT = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
# Sonntag 22:30 Ortszeit (Island = UTC): Onset 150 -> 01:00 Montag.
_AT = datetime(2026, 5, 10, 22, 30, tzinfo=timezone.utc)


def _nowcast(onset_min: int, *, jetzt: datetime = _JETZT):
    """Echtes `NowcastResult` aus echtem `RadarNowcastService`."""
    from services.radar_service import RadarNowcastService

    reset_radar_cache()
    with freeze_time(jetzt):
        return RadarNowcastService(
            frame_source=feste_frames(jetzt, onset_min),
        ).get_nowcast(ISLAND_LAT, ISLAND_LON)


def _kanaltexte(lauf) -> dict[str, str]:
    return {
        "E-Mail": "\n".join(f"{b}\n{k}" for b, k in lauf.mail),
        "Telegram": "\n".join(lauf.telegram),
        "SMS": "\n".join(lauf.sms),
        "Premium-SMS": "\n".join(lauf.premium_sms),
    }


def _lauf_mit_kurzform(nutzer: str, nr: int, onset_min: int):
    trip = kurzer_trip(f"trip-2261-ac7-{onset_min}-{nr}", _AT.date(), "22:00", "23:59")
    trip.report_config = alle_kanaele_konfig(trip.id, telegram_style="kurzform")
    return pruef_lauf(nutzer, _AT, trip, feste_frames(_AT, onset_min))


# ═══════════════════════════════ AC-7 ═════════════════════════════════════


def test_menge_entfaellt_bei_abgeschnittenem_fenster():
    """AC-7: Given Regenbeginn bei Onset 150 (und Grenzfall 135) mit echten
    15-Minuten-Frames bis zum Horizont (2 mm/h ab Beginn)
    When die Quelle das Ergebnis bildet und der Alarm in allen Kanaelen
    gerendert wird
    Then ist `onset_precip_mm is None` (keine falsch kleine Zahl), die
    Intensitaet bleibt "Mäßiger Regen", `window_precip_mm`/`max_rate_mm_h`
    bleiben bei ihren aus den Frames hergeleiteten Werten (0,0 -- das
    60-Min-Fenster ab jetzt ist trocken), und KEINER der vier Kanaele traegt
    eine Mengenangabe -- fuer zwei Nutzer.

    RED heute: Quelle liefert 1,5 (Onset 150) bzw. 2,0 (Onset 135, Frame bei
    180 ueber den Horizont gestreckt); zudem loest Onset 150 bei Schwelle 55
    keinen Alarm aus."""
    from services.radar_service import INTENSITY_MODERATE

    # --- Quelle ---
    for onset in (150, 135):
        nc = _nowcast(onset)
        assert nc.onset_minutes == onset, (
            f"Vorbedingung: Beginn bei {onset} erwartet, war {nc.onset_minutes}"
        )
        assert nc.onset_precip_mm is None, (
            f"AC-7 Quelle: bei Onset {onset} reicht das 60-Min-Mengenfenster "
            f"ueber den Horizont (onset+60 > 180) -- onset_precip_mm muss None "
            f"sein, war {nc.onset_precip_mm!r}. Fehlender Schritt: Kappung in "
            f"radar_service._derive_result."
        )
        assert nc.intensity_label == INTENSITY_MODERATE, (
            f"AC-7 Quelle: die Intensitaet muss bleiben, war {nc.intensity_label!r}"
        )
        assert nc.window_precip_mm == 0.0 and nc.max_rate_mm_h == 0.0, (
            f"AC-7 Quelle: window_precip_mm/max_rate_mm_h (60 Min ab jetzt, "
            f"trocken) muessen 0.0 bleiben, waren {nc.window_precip_mm!r}/"
            f"{nc.max_rate_mm_h!r}"
        )

    # --- Kanaele ---
    for nr in (1, 2):
        nutzer = uid(f"ac7-cut-n{nr}")
        _clean_user(nutzer)
        try:
            lauf = _lauf_mit_kurzform(nutzer, nr, 150)
            assert lauf.triggered_count == 1, (
                f"AC-7 Vorbedingung (Nutzer {nr}): Regen in 150 Min muss einen "
                f"Alarm ausloesen (war {lauf.triggered_count}). Fehlender "
                f"Schritt: Schwelle = NOWCAST_HORIZON_MIN (AC-1)."
            )
            for kanal, text in _kanaltexte(lauf).items():
                assert text, f"AC-7 (Nutzer {nr}): {kanal} hat nichts erhalten."
                assert not MENGEN_TOKEN.search(text), (
                    f"AC-7 (Nutzer {nr}): {kanal} traegt eine Mengenangabe, "
                    f"obwohl das Fenster am Horizont abgeschnitten ist.\n{text!r}"
                )
                assert not MENGE_LANGFORM.search(text), (
                    f"AC-7 (Nutzer {nr}): {kanal} traegt eine Mengenzahl in "
                    f"mm.\n{text!r}"
                )
        finally:
            _clean_user(nutzer)


def test_menge_bleibt_bei_vollem_fenster():
    """AC-7: Given Regenbeginn bei Onset <= 120 (Grenzfall 120:
    onset + 60 == 180, NICHT > 180; Normalfall 30)
    When die Quelle das Ergebnis bildet
    Then bleibt `onset_precip_mm` der aus den Frames hergeleitete Wert
    (4 nasse Frames x 15 Min x 2 mm/h = 2,0 mm), und `window_precip_mm`/
    `max_rate_mm_h` sind unveraendert (Onset 30: 2 nasse Frames im Fenster ab
    jetzt = 1,0 mm, Spitze 2,0 mm/h; Onset 120: 0,0/0,0).
    Wirkung: ein echter Alarm bei Onset 38 traegt die Menge in SMS,
    Premium-SMS und Telegram-Kurzform (`R2.0@...`) -- Positivprobe fuer das
    Mengentoken-Muster der Abwesenheitspruefung -- fuer zwei Nutzer.

    Regressionswaechter (heute gruen): faengt eine Kappung mit `>=` statt
    `>` (Onset 120 verloere die Menge), eine pauschale Kappung jeder Menge
    sowie eine Kappung, die `window_precip_mm`/`max_rate_mm_h` mitreisst."""
    from services.radar_service import INTENSITY_MODERATE

    for onset, fenster_mm, spitze in ((120, 0.0, 0.0), (30, 1.0, RATE_MM_H)):
        nc = _nowcast(onset)
        assert nc.onset_minutes == onset
        assert nc.onset_precip_mm == 2.0, (
            f"AC-7: bei Onset {onset} (onset+60 <= 180) muss die Menge "
            f"unveraendert 2.0 mm sein, war {nc.onset_precip_mm!r}"
        )
        assert nc.intensity_label == INTENSITY_MODERATE
        assert nc.window_precip_mm == fenster_mm and nc.max_rate_mm_h == spitze, (
            f"AC-7: window_precip_mm/max_rate_mm_h bei Onset {onset} muessen "
            f"{fenster_mm}/{spitze} sein, waren {nc.window_precip_mm!r}/"
            f"{nc.max_rate_mm_h!r}"
        )

    for nr in (1, 2):
        nutzer = uid(f"ac7-voll-n{nr}")
        _clean_user(nutzer)
        try:
            lauf = _lauf_mit_kurzform(nutzer, nr, 38)
            assert lauf.triggered_count == 1, (
                f"AC-7 Positivprobe (Nutzer {nr}): Onset 38 muss ausloesen "
                f"(war {lauf.triggered_count})."
            )
            texte = _kanaltexte(lauf)
            for kanal in ("Telegram", "SMS", "Premium-SMS"):
                assert MENGEN_TOKEN.search(texte[kanal]) and "R2.0@" in texte[kanal], (
                    f"AC-7 Positivprobe (Nutzer {nr}): {kanal} muss bei vollem "
                    f"Fenster die Menge 'R2.0@' tragen.\n{texte[kanal]!r}"
                )
        finally:
            _clean_user(nutzer)
