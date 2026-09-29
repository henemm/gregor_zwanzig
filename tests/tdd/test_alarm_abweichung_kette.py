"""TDD RED — Issue #2422 Scheibe S4, Bein Abweichungsalarm: Kanal-Auflösung +
Schwelle über alle vier Kanäle (AC-1) und Cooldown/Quiet-Hours (AC-6).

SPEC: docs/specs/modules/fix_2422_s4_alarm_familie_kette.md (AC-1, AC-6).

Einstieg wie im echten Betrieb: der Trip liegt im Persistenzformat des
Editors (Golden-Fixture `tests/fixtures/alarm_kette/golden_abweichung.json`)
und wird über den ECHTEN `app.loader.load_trip()` gelesen (Migration inklusive) —
kein `Trip(...)`-Konstruktor im Speicher. Ausgelöst wird über die ECHTE
Auslöseentscheidung `TripAlertService.check_and_send_alerts()`
(`tests/helpers/alarm_pruefstrecke.py`, #2050 S1), abgegriffen an allen vier
Kanälen ohne echten Versand (lokale Loopback-Stubs), kein `Mock()`/`patch()`.

Beide ACs sind heute bereits GRÜN (Charakterisierung, kein Bug-Fall) — sie
schützen die bestehende Kanal-/Schwellen-/Sperrzeit-Logik vor stillschweigender
Regression, während S4 die zwei echten Bugs in der amtlichen-Warnungen-Kette
behebt (separate Datei `test_alarm_amtliche_warnungen_kette.py`).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir, load_trip
from app.models import (
    ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _settings_all_channels, _write_tier,
)

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "alarm_kette"


def _golden_dict(name: str) -> dict:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text())


def _uid(tag: str) -> str:
    return f"tdd-2422s4-{tag}-{uuid.uuid4().hex[:6]}"


def _abweichungs_trip(uid: str, **overrides):
    """Golden-Abweichungs-Trip ECHT über `app.loader.load_trip()` geladen —
    danach werden nur die je AC variablen Alarm-Felder gesetzt (reale
    Dataclass-Attribute, kein Mock)."""
    d = _golden_dict("golden_abweichung")
    d["id"] = f"trip-{uid}"
    trip = load_trip(d, user_id=uid)
    for feld, wert in overrides.items():
        setattr(trip, feld, wert)
    return trip


def _wd(segment_id: int = 1, **summary) -> SegmentWeatherData:
    """Synthetische Wetterdaten EINES Segments, Vorbild
    `test_alarm_szenario_ein_ereignis_ein_alarm.py::_wd`."""
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.2692, lon=11.4041, elevation_m=600, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.30, lon=11.45, elevation_m=900, distance_from_start_km=8.0),
        start_time=_AT - timedelta(hours=2), end_time=_AT + timedelta(hours=2),
        duration_hours=4.0, distance_km=8.0, ascent_m=300, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=_AT, provider="openmeteo",
    )


def _erlaube_premium_sms(uid: str) -> None:
    """Ergänzt `user.json` um die gelernte Rückadresse (Issue #1676 S1) —
    ohne sie kennt `PremiumSmsOutput._resolve_recipient()` keinen Empfänger
    ("keine gelernte Rueckadresse vorhanden"). Read-Modify-Write, damit
    bereits gesetzte Felder (Tier, Kanal-Ziele) erhalten bleiben (Regel
    Daten-Schema-Reworks)."""
    pfad = get_data_dir(uid) / "user.json"
    profil = json.loads(pfad.read_text())
    profil.setdefault("premium_sms_reply_to", "+490000000008")
    profil.setdefault("premium_sms_reply_at", datetime.now(timezone.utc).isoformat())
    pfad.write_text(json.dumps(profil), encoding="utf-8")


def _strecke(uid: str) -> AlarmPruefstrecke:
    # Reihenfolge PFLICHT: `AlarmPruefstrecke.__init__` liest `user.json` per
    # Read-Modify-Write und baut daraus EINMALIG die profilierten `Settings`
    # (`base.with_user_profile(user_id)`) -- premium_sms_reply_to/_at muessen
    # VOR diesem Zeitpunkt auf der Platte stehen, sonst fehlen sie im bereits
    # gebauten Settings-Objekt.
    _write_tier(uid, "premium")
    _erlaube_premium_sms(uid)
    return AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())


def _kanaele(lauf) -> dict:
    return {
        "mail": len(lauf.mail), "telegram": len(lauf.telegram),
        "sms": len(lauf.sms), "premium_sms": len(lauf.premium_sms),
    }


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_kanalmatrix_und_schwelle_konsistent_bis_zum_versand():
    """AC-1 (Charakterisierung, heute GRÜN). GIVEN ein über `app.loader`
    geladener Trip mit `alert_channels` = genau zwei Kanälen (E-Mail,
    Telegram), `alert_metric_channels` mit einer ABWEICHENDEN Kanalauswahl
    für `precipitation` (Katalog-`metric_id` von `precip_sum_mm`, NICHT zu
    verwechseln mit dem Schlüssel `precipitation_sum` in
    `display_config.metric_alert_levels` — andere Namensebene; SMS +
    Premium-SMS) und einer
    `alert_channel_thresholds`-Schwelle, die SMS (HIGH) unterdrückt, während
    Premium-SMS (Default LOW) bei der gemessenen Dringlichkeit MODERATE
    durchkommt.
    WHEN ein Abweichungsalarm über `alarm_pruefstrecke.lauf()` ausgelöst wird.
    THEN bedient der Aufzeichner GENAU Premium-SMS — E-Mail/Telegram (vom
    Zwei-Kanal-Override) bleiben aus, weil `precipitation` die EINZIGE
    auslösende Metrik ist und ihr Eintrag den Override gemäß
    `resolve_alert_channels()` Schritt 4 VOLLSTÄNDIG ersetzt; SMS scheitert
    an der Schwelle. Alle vier Kanäle werden gleich streng geprüft.

    Orakel (unabhängig von `resolve_alert_channels()`/`split_by_threshold()`
    von Hand nachgebildet, NICHT aus der Produktfunktion übernommen): einzige
    auslösende Metrik `precip_sum_mm` → Katalog-`metric_id` `precipitation` →
    `alert_metric_channels`-Eintrag {sms, premium_sms} ersetzt den
    Zwei-Kanal-Override vollständig → vor der
    Schwelle {sms, premium_sms}. Fest verdrahteter Rang LOW < MODERATE < HIGH:
    sms braucht HIGH, die Dringlichkeit ist MODERATE (Regen 2→18mm, empirisch
    gemessene Stufe, s. `test_alarm_szenario_ein_ereignis_ein_alarm.py`-
    Moduldoku) → sms fällt raus; premium_sms (kein eigener Eintrag → Default
    LOW) bleibt.
    """
    uid = _uid("ac1")
    try:
        trip = _abweichungs_trip(
            uid,
            alert_channels={"email": True, "telegram": True},
            alert_metric_channels={"precipitation": {"sms": True, "premium_sms": True}},
            alert_channel_thresholds={"sms": "HIGH"},
        )
        strecke = _strecke(uid)
        cached = [_wd(1, precip_sum_mm=2.0)]
        fresh = [_wd(1, precip_sum_mm=18.0)]

        lauf = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )

        assert lauf.triggered_count == 1, (
            f"AC-1 Vorbedingung: der Regen-Sprung muss auslösen (war "
            f"{lauf.triggered_count})."
        )
        assert _kanaele(lauf) == {"mail": 0, "telegram": 0, "sms": 0, "premium_sms": 1}, (
            f"AC-1: nur Premium-SMS darf bedient werden (Metrik-Override "
            f"ersetzt den Zwei-Kanal-Override, SMS fällt an der Schwelle "
            f"raus): {_kanaele(lauf)!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


@pytest.mark.parametrize("sperre", ["quiet_hours", "cooldown"])
def test_cooldown_und_quiet_hours_unterdruecken_den_alarm(sperre):
    """AC-6 (Charakterisierung, heute GRÜN). GIVEN ein Trip mit
    `alert_quiet_from`/`_to` bzw. `alert_cooldown_minutes`, ein
    Abweichungsalarm, der WÄHREND der Ruhezeit bzw. INNERHALB des
    Cooldown-Fensters (nach einem bereits versendeten Alarm) geprüft wird /
    WHEN beide Fälle über die Prüfstrecke laufen / THEN bleibt die
    Auslieferung in beiden Fällen aus; AUSSERHALB der Sperre liefert
    derselbe Auslöser normal aus (Gegenprobe im selben Testlauf, Pflicht bei
    einem geprüften Ausbleiben — sonst könnte die Stille auch an einer
    anderen Sperre liegen).

    Ruhezeit 13:00–14:00 Ortszeit (Innsbruck, Europe/Vienna); `_AT` = 12:00
    Ortszeit liegt AUSSERHALB und dient als freier Referenzlauf (Vorbild
    `test_radar_cooldown_overtake.py::test_ac6_...`).
    """
    uid = _uid(f"ac6-{sperre}")
    try:
        trip = _abweichungs_trip(uid, alert_channels={"telegram": True})
        strecke = _strecke(uid)

        if sperre == "quiet_hours":
            trip.alert_quiet_from = "13:00"
            trip.alert_quiet_to = "14:00"

            gesperrt = strecke.lauf(
                at=_AT + timedelta(hours=1, minutes=30), zweig="deviation", trip=trip,
                cached_weather=[_wd(1, precip_sum_mm=2.0)],
                fresh_weather=[_wd(1, precip_sum_mm=18.0)],
            )
            assert gesperrt.triggered_count == 0, (
                f"AC-6 (quiet_hours): während der Ruhezeit darf nichts "
                f"ausgelöst werden (war {gesperrt.triggered_count})."
            )

            frei = strecke.lauf(
                at=_AT, zweig="deviation", trip=trip,
                cached_weather=[_wd(1, precip_sum_mm=2.0)],
                fresh_weather=[_wd(1, precip_sum_mm=18.0)],
            )
            assert frei.triggered_count == 1, (
                f"AC-6 (quiet_hours) Gegenprobe: AUSSERHALB der Ruhezeit "
                f"muss derselbe Auslöser normal ausliefern (war "
                f"{frei.triggered_count})."
            )
        else:  # cooldown
            trip.alert_cooldown_minutes = 120

            erster = strecke.lauf(
                at=_AT, zweig="deviation", trip=trip,
                cached_weather=[_wd(1, precip_sum_mm=2.0)],
                fresh_weather=[_wd(1, precip_sum_mm=18.0)],
            )
            assert erster.triggered_count == 1, (
                f"AC-6 (cooldown) Vorbedingung: der erste Alarm muss "
                f"ausliefern (war {erster.triggered_count})."
            )

            innerhalb = strecke.lauf(
                at=_AT + timedelta(minutes=30), zweig="deviation", trip=trip,
                cached_weather=[_wd(1, precip_sum_mm=2.0)],
                fresh_weather=[_wd(1, precip_sum_mm=20.0)],
            )
            assert innerhalb.triggered_count == 0, (
                f"AC-6 (cooldown): innerhalb des Cooldown-Fensters darf "
                f"nichts ausgelöst werden (war {innerhalb.triggered_count})."
            )

            nach_ablauf = strecke.lauf(
                at=_AT + timedelta(minutes=125), zweig="deviation", trip=trip,
                cached_weather=[_wd(1, precip_sum_mm=2.0)],
                fresh_weather=[_wd(1, precip_sum_mm=30.0)],
            )
            assert nach_ablauf.triggered_count == 1, (
                f"AC-6 (cooldown) Gegenprobe: NACH Ablauf des Cooldowns muss "
                f"derselbe Auslöser normal ausliefern (war "
                f"{nach_ablauf.triggered_count})."
            )
    finally:
        _clean_user(uid)
