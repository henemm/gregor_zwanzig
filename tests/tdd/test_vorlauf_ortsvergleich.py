"""TDD RED — Issue #2261 Teil A (A-1), AC-11: der Ortsvergleich erbt die
Schwelle = Reichweite der Quelle, ein Ereignis ergibt genau einen Alarm.

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md — AC-11,
Implementation Details §7.

Der Ortsvergleich liest die Schwelle ueber dieselbe Modulreferenz wie der
Trip (`radar_service_mod.RADAR_ONSET_THRESHOLD_MIN`, ADR-0021). Mit 180 sieht
er ein Ereignis schon bei Onset 170 -- und sieht es danach in jedem
Viertelstunden-Lauf erneut, bis es eintrifft. Sein Schutz vor Doppelalarmen
ist Cooldown 120 plus Ereignis-Identitaet; entscheidend ist der Abschnitt
NACH Ablauf der 120 Minuten, in dem nur noch die Identitaet traegt.

Aufbau: echter `CompareRadarAlertService.check_all_compare_presets()`,
echter `RadarNowcastService` an der `frame_source`-Naht mit FESTEN,
absoluten Frames (das Ereignis rueckt Lauf fuer Lauf naeher; ein
`wet_frames`-Helfer, der je Aufruf an "jetzt" neu verankert, wuerde das
nicht abbilden). Tier premium, damit kein Tageslimit einen Doppelalarm
verdeckt. Zwei Nutzer.

Docstring-Pruefung `compare_radar_alert.py:6` als Doku-Abnahme.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, fresh_uid, location, radar_preset,
    reset_radar_cache, settings_email_only, write_presets, write_user_tier,
)

# 10:00 UTC = 12:00 Wien (Sommerzeit), mitten im Preset-Fenster 9-16 Uhr.
_T0 = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)
_ERSTSICHT_ONSET = 170
_RATE = 2.0


class _FestesEreignis:
    """Echter `frame_source`: ein Ereignis mit FESTEM Beginn
    `_T0 + 170 Min`, 15-Minuten-Raster von `_T0 - 15` bis Ereignis + 180,
    davor trocken, ab dem Beginn nass (2 mm/h, nicht konvektiv -- die
    Dringlichkeit bleibt ueber alle Laeufe gleich, kein Eskalations-
    Durchbruch)."""

    def __init__(self, onset_min: int = _ERSTSICHT_ONSET) -> None:
        self.beginn = _T0 + timedelta(minutes=onset_min)
        self.calls = 0

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.calls += 1
        frames = []
        t = self.beginn - timedelta(minutes=15 * 13)
        while t <= self.beginn + timedelta(minutes=180):
            frames.append(RadarFrame(
                timestamp=t,
                precip_mm_h=(_RATE if t >= self.beginn else 0.0),
                is_convective=False,
            ))
            t += timedelta(minutes=15)
        return frames


def _aufbau(nutzer: str, preset_id: str) -> None:
    clean_uid(nutzer)
    write_user_tier(nutzer, "premium")
    from app.loader import save_location

    save_location(location("loc-2261", "Innsbruck-Vorlauf"), user_id=nutzer)
    write_presets(nutzer, [radar_preset(
        preset_id, ["loc-2261"], user_id=nutzer, cooldown_minutes=120,
    )])


def _lauf(nutzer: str, quelle, at: datetime) -> tuple[int, list]:
    mails: list = []
    reset_radar_cache()
    with freeze_time(at):
        svc = compare_radar_service(
            nutzer, settings_email_only(), quelle,
            lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_all_compare_presets()
    return sent, mails


# ═══════════════════════════════ AC-11 ════════════════════════════════════


def test_erstsicht_170_ergibt_genau_einen_alarm():
    """AC-11: Given ein Ortsvergleich-Preset mit einem Ort, an dem Regen
    erstmals bei Onset 170 gesehen wird (fester Beginn)
    When der Ortsvergleich-Radar-Lauf alle 15 Minuten ueber die
    Cooldown-Dauer (120) hinaus laeuft (Onset 170, 155, ..., 20)
    Then wird schon beim ERSTEN Lauf (Onset 170) alarmiert, und ueber alle
    Laeufe entsteht GENAU EIN Ortsvergleich-Alarm -- auch nach Ablauf der
    Sperrzeit, wenn nur noch die Ereignis-Identitaet schuetzt. Zwei Nutzer.

    RED heute: Schwelle 55 -> der erste Lauf (Onset 170) schweigt; der erste
    Alarm kaeme erst bei Onset 50."""
    for nr in (1, 2):
        nutzer = fresh_uid(f"2261-ac11-n{nr}")
        preset_id = f"cp-2261-ac11-{nr}"
        try:
            _aufbau(nutzer, preset_id)
            quelle = _FestesEreignis()
            protokoll: list[tuple[int, int, int, int]] = []
            for j in range(0, 11):  # Laeufe bei +0 ... +150 Min
                at = _T0 + timedelta(minutes=15 * j)
                vorher = quelle.calls
                sent, mails = _lauf(nutzer, quelle, at)
                protokoll.append(
                    (15 * j, _ERSTSICHT_ONSET - 15 * j, sent, quelle.calls - vorher)
                )
                if j == 0:
                    assert sent == 1 and len(mails) == 1, (
                        f"AC-11 (Nutzer {nr}): die Erstsicht bei Onset "
                        f"{_ERSTSICHT_ONSET} muss den Ortsvergleich-Alarm "
                        f"ausloesen (sent={sent}, mails={len(mails)}). "
                        f"Fehlender Schritt: RADAR_ONSET_THRESHOLD_MIN = "
                        f"NOWCAST_HORIZON_MIN, gelesen ueber die Modulreferenz."
                    )
            gesamt = sum(p[2] for p in protokoll)
            assert gesamt == 1, (
                f"AC-11 (Nutzer {nr}): ueber alle Laeufe genau EIN Alarm "
                f"erwartet, waren {gesamt}. Protokoll (Minute, Onset, "
                f"gesendet, Quellabrufe): {protokoll!r}"
            )
            # Nach Ablauf der Sperrzeit (>= 120 Min nach dem Alarm) muss
            # die Quelle wieder befragt worden sein -- sonst haette die
            # Sperrzeit allein geschuetzt und die Identitaet bliebe ungeprueft.
            nach_sperrzeit = [p for p in protokoll if p[0] >= 120]
            assert nach_sperrzeit and all(p[3] >= 1 for p in nach_sperrzeit), (
                f"Vorbedingung (Nutzer {nr}): nach Ablauf der Sperrzeit muss "
                f"jeder Lauf die Quelle befragen. Protokoll: {protokoll!r}"
            )
        finally:
            clean_uid(nutzer)


def test_ortsvergleich_liest_schwelle_ueber_modulreferenz(monkeypatch):
    """AC-11 (Laufzeit-Drift-Probe): Given Regen bei Onset 170
    When `radar_service.RADAR_ONSET_THRESHOLD_MIN` zur Laufzeit auf 165
    bzw. 175 gesetzt wird
    Then folgt der Ortsvergleich dem MODULWERT: 165 -> kein Alarm,
    175 -> Alarm. Eine im Ortsvergleich gebundene eigene Zahl (Literal oder
    `from ... import` zur Importzeit) waere gegen den Patch blind.

    Regressionswaechter (heute gruen): faengt Spec-Mutation (11)
    "Ortsvergleich mit eigener Literal-Schwelle"."""
    from services import radar_service as radar_service_mod

    for nr, schwelle, erwartet in ((1, 165, 0), (2, 175, 1)):
        monkeypatch.setattr(radar_service_mod, "RADAR_ONSET_THRESHOLD_MIN", schwelle)
        nutzer = fresh_uid(f"2261-ac11-drift-n{nr}")
        preset_id = f"cp-2261-ac11-drift-{nr}"
        try:
            _aufbau(nutzer, preset_id)
            sent, mails = _lauf(nutzer, _FestesEreignis(), _T0)
            assert sent == erwartet and len(mails) == erwartet, (
                f"AC-11: mit Modulwert {schwelle} und Onset 170 erwartet "
                f"{erwartet} Alarm(e), waren sent={sent}/mails={len(mails)} -- "
                f"der Ortsvergleich liest die Schwelle nicht ueber die "
                f"Modulreferenz radar_service.RADAR_ONSET_THRESHOLD_MIN."
            )
        finally:
            clean_uid(nutzer)


def test_docstring_nennt_geteilte_schwelle_statt_20_min():
    """AC-11 Doku-Abnahme: der Modul-Docstring von `compare_radar_alert.py`
    nennt nicht mehr "Onset ≤ 20 Min", sondern die geteilte Schwelle
    (Horizont der Quelle bzw. `RADAR_ONSET_THRESHOLD_MIN`).

    RED heute: Zeile 6 sagt "bei Regen-Onset ≤ 20 Min"."""
    # doc-compliance-test
    import services.compare_radar_alert as cmp_mod

    doc = cmp_mod.__doc__ or ""
    assert "20 Min" not in doc, (
        f"AC-11: Docstring nennt noch die veraltete '≤ 20 Min'-Schwelle:\n{doc}"
    )
    assert "RADAR_ONSET_THRESHOLD_MIN" in doc or "Horizont" in doc, (
        f"AC-11: Docstring muss die geteilte Schwelle nennen "
        f"(RADAR_ONSET_THRESHOLD_MIN bzw. Horizont der Quelle):\n{doc}"
    )
