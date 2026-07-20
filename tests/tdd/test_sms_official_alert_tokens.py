"""Amtliche Warnungen als `!`-Warn-Block in der Trip-Briefing-SMS (#1318, Scheibe A).

SPEC: docs/specs/modules/sms_official_alert_tokens.md — AC-1..AC-7, AC-12..AC-14
WIRE: docs/reference/sms_format.md §2/§3.4/§6

TDD RED. Vor der Implementierung MUESSEN diese Tests rot sein:
  - `src/output/tokens/hazard_symbols.py` existiert noch nicht (ImportError in
    den katalog-getriebenen Tests AC-5/AC-14).
  - `_segments_to_normalized_forecast()` (sms_trip.py) liest `seg.official_alerts`
    ueberhaupt nicht -> die Token-Zeile traegt strukturell nie einen `!`-Block
    (AC-1/AC-2/AC-6/AC-7/AC-12).
  - `_HAZARD_DISPLAY` (official_alerts.py) fuehrt weiterhin die deutsch
    abgeleiteten Kuerzel HZ/ST/RR/GL/ZG/WB (AC-13).

Ausnahmen, die schon heute gruen sein sollen:
  - AC-3 (gelbe Warnung erscheint nicht) — heute trivial gruen, weil gar keine
    Warnung erscheint; der Test sichert den Filter NACH der Implementierung ab.
  - AC-4 (Non-Regression) — die Token-Zeile ohne Warnung ist eingefroren und
    darf sich durch #1318 nicht um ein Byte aendern.

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`/`SegmentWeatherData`-
Objekte, echte Renderer-Aufrufe (`SMSTripFormatter().format_sms`,
`render_official_alert_sms`), netzfrei.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from output.renderers.sms_trip import SMSTripFormatter
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
_TZ = ZoneInfo("UTC")
_YEAR, _MONTH, _DAY = 2026, 7, 15

# Warn-Zeitraeume: 14:00-18:00 (stundengenau) bzw. ganztaegig (00:00-23:59).
WARN_FROM = datetime(_YEAR, _MONTH, _DAY, 14, 0, tzinfo=UTC)
WARN_TO = datetime(_YEAR, _MONTH, _DAY, 18, 0, tzinfo=UTC)
ALLDAY_FROM = datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=UTC)
ALLDAY_TO = datetime(_YEAR, _MONTH, _DAY, 23, 59, tzinfo=UTC)

# Die 9 Gefahrenarten mit ihrem Kuerzel laut Spec Abschnitt 1 (Reihenfolge =
# Katalog-Reihenfolge). Bewusst hier NICHT aus `hazard_symbols.py` importiert:
# die Tabelle ist die Zusage der Spec, gegen die der Katalog geprueft wird.
SPEC_SYMBOLS: list[tuple[str, str]] = [
    ("thunderstorm", "TH"),
    ("rain", "HR"),
    ("wind_gust", "W"),
    ("snow", "SN"),
    ("black_ice", "IC"),
    ("extreme_heat", "HT"),
    ("extreme_cold", "CD"),
    ("wildfire_risk", "FR"),
    ("access_ban", "CL"),
]

# Die deutsch abgeleiteten Alt-Kuerzel, die ersatzlos verschwinden (Spec 1b).
OLD_SYMBOLS = ["HZ", "ST", "RR", "GL", "ZG", "WB", "KL"]

_HAZARD_LABELS = {
    "thunderstorm": "Gewitter",
    "rain": "Starkregen",
    "wind_gust": "Sturm",
    "snow": "Schneefall",
    "black_ice": "Glatteis",
    "extreme_heat": "Hitze",
    "extreme_cold": "Kaelte",
    "wildfire_risk": "Waldbrand-Gefahr",
    "access_ban": "Zugang gesperrt",
}


# ---------------------------------------------------------------------------
# Fixtures — echte Objekte, keine Doubles
# ---------------------------------------------------------------------------

def _alert(hazard: str, level: int, *, allday: bool = False) -> OfficialAlert:
    vf, vt = (ALLDAY_FROM, ALLDAY_TO) if allday else (WARN_FROM, WARN_TO)
    return OfficialAlert(
        source="meteoalarm", hazard=hazard, level=level,
        label=_HAZARD_LABELS.get(hazard, hazard),
        valid_from=vf, valid_to=vt, region_label="Haute-Corse",
    )


def _dp(hour: int, *, rain: float = 0.0, wind: float = 0.0, gust: float = 0.0,
        pop: float = 0.0, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=UTC),
        t2m_c=18.0, wind10m_kmh=wind, gust_kmh=gust, precip_1h_mm=rain,
        cloud_total_pct=40, thunder_level=thunder, humidity_pct=55, pop_pct=pop,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=UTC),
        grid_res_km=1.0, interp="point_grid",
    )


def _segment(
    alerts: list[OfficialAlert] | None = None,
    *,
    hourly: list[ForecastDataPoint] | None = None,
    segment_id: int = 1,
) -> SegmentWeatherData:
    """Ein Segment 07:00-17:00 mit 24h-Zeitreihe.

    `hourly=None` -> ruhiges Wetter (alle Vorhersage-Token "-"), damit die
    Assertions auf den Warn-Block eindeutig sind.
    """
    data = hourly if hourly is not None else [_dp(h) for h in range(24)]
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, 7, 0, tzinfo=UTC),
        end_time=datetime(_YEAR, _MONTH, _DAY, 17, 0, tzinfo=UTC),
        duration_hours=10.0, distance_km=14.0, ascent_m=800.0, descent_m=600.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=_meta(), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=9.0, temp_max_c=24.0,
            wind_max_kmh=max((dp.wind10m_kmh or 0.0) for dp in data),
            gust_max_kmh=max((dp.gust_kmh or 0.0) for dp in data),
            precip_sum_mm=sum((dp.precip_1h_mm or 0.0) for dp in data),
            pop_max_pct=max((dp.pop_pct or 0.0) for dp in data),
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=UTC),
        provider="openmeteo",
        official_alerts=list(alerts or []),
    )


def _sms(alerts: list[OfficialAlert] | None = None, **kwargs) -> str:
    seg = _segment(alerts)
    return SMSTripFormatter().format_sms(
        [seg], stage_name="Etappe 5", tz=_TZ, **kwargs
    )


def _notice(alert: OfficialAlert):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )


def _word_present(text: str, token: str) -> bool:
    """Wortgrenzen-sichere Praesenz — 'HZ' darf nicht in 'Hermagor' treffen."""
    return re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text) is not None


# ---------------------------------------------------------------------------
# AC-1 — Gewitter ROT mit Uhrzeit -> `!TH:H@14`
# ---------------------------------------------------------------------------
def test_ac1_red_thunderstorm_warning_appears_as_warn_block():
    sms = _sms([_alert("thunderstorm", 4)])
    assert "!TH:H@14" in sms, (
        f"Amtliche Gewitterwarnung (ROT, ab 14:00) fehlt in der SMS: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — zwei Warnungen: genau EIN `!`, schwerste zuerst, ganztaegig ohne @h
# ---------------------------------------------------------------------------
def test_ac2_two_warnings_single_marker_severest_first():
    sms = _sms([
        _alert("wind_gust", 3, allday=True),   # absichtlich schwaechere zuerst
        _alert("thunderstorm", 4),
    ])
    assert "!TH:H@14 W:M" in sms, f"Warn-Block falsch aufgebaut: {sms!r}"
    assert sms.count("!") == 1, (
        f"Der `!`-Marker muss genau einmal erscheinen, gezaehlt: {sms.count('!')} in {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — gelbe/gruene Warnung wird gefiltert
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", [1, 2])
def test_ac3_yellow_and_green_warnings_are_filtered(level: int):
    sms = _sms([_alert("rain", level)])
    assert "!" not in sms, (
        f"Warnung der Stufe {level} darf nicht in der SMS erscheinen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Non-Regression: Token-Zeile ohne Warnung bleibt bit-identisch
# ---------------------------------------------------------------------------
# Eingefrorener Ist-Stand vor #1318 (erzeugt mit demselben Fixture, leerer
# official_alerts-Liste). Aendert sich dieser String, hat #1318 eine
# bestehende Token-Zeile verschoben — genau das darf nicht passieren.
GOLDEN_NO_ALERTS = "E5: N9 D24 R- PR- W- G- TH:- TH+:-"
GOLDEN_WET_NO_ALERTS = (
    "E5: N9 D24 R0.4@11(2.5@16) PR60%@11(80%@16) W18@11(28@16) "
    "G30@11(45@16) TH:M@16 TH+:-"
)


def test_ac4_token_line_without_alerts_is_bit_identical():
    sms = _sms([])
    assert sms == GOLDEN_NO_ALERTS, (
        "Token-Zeile ohne amtliche Warnung hat sich veraendert.\n"
        f"  erwartet: {GOLDEN_NO_ALERTS!r}\n  erhalten: {sms!r}"
    )


def test_ac4_wet_day_without_alerts_is_bit_identical():
    """Zweiter Golden-Fall mit aktiven Vorhersage-Token (nicht nur '-')."""
    hourly = [_dp(h) for h in range(24)]
    hourly[11] = _dp(11, rain=0.4, wind=18.0, gust=30.0, pop=60.0)
    hourly[16] = _dp(16, rain=2.5, wind=28.0, gust=45.0, pop=80.0,
                     thunder=ThunderLevel.MED)
    seg = _segment([], hourly=hourly)
    sms = SMSTripFormatter().format_sms([seg], stage_name="Etappe 5", tz=_TZ)
    assert sms == GOLDEN_WET_NO_ALERTS, (
        "Token-Zeile (Regentag) ohne amtliche Warnung hat sich veraendert.\n"
        f"  erwartet: {GOLDEN_WET_NO_ALERTS!r}\n  erhalten: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — alle 9 Gefahrenarten mit ihrem Kuerzel, ASCII/GSM-7-konform
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hazard,symbol", SPEC_SYMBOLS)
def test_ac5_all_nine_hazards_render_their_symbol(hazard: str, symbol: str):
    sms = _sms([_alert(hazard, 3)])
    expected = "!CL" if hazard == "access_ban" else f"!{symbol}:M"
    assert expected in sms, (
        f"Gefahrenart {hazard} muss als {expected!r} erscheinen: {sms!r}"
    )
    assert sms.isascii(), f"SMS enthaelt Nicht-ASCII-Zeichen (GSM-7-Bruch): {sms!r}"


def test_ac5_catalog_matches_spec_table():
    """Der Katalog `hazard_symbols.py` ist die einzige Quelle — und traegt
    exakt die 9 Paare der Spec-Tabelle."""
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS
    assert dict(SPEC_SYMBOLS) == dict(HAZARD_SMS_SYMBOLS), (
        "Katalog weicht von der Spec-Tabelle (Abschnitt 1) ab: "
        f"{dict(HAZARD_SMS_SYMBOLS)!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — access_ban ist binaer: `CL` ohne Doppelpunkt/Stufe
# ---------------------------------------------------------------------------
def test_ac6_access_ban_has_no_level_suffix():
    sms = _sms([_alert("access_ban", 4)])
    assert "!CL" in sms, f"Zugangssperre fehlt: {sms!r}"
    assert "CL:" not in sms, (
        f"Zugangssperre darf keine Stufe tragen (kein 'CL:'): {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Truncation: der Warn-Block ueberlebt, PR faellt zuerst
# ---------------------------------------------------------------------------
def test_ac7_warn_block_survives_truncation_before_pr():
    hourly = [_dp(h) for h in range(24)]
    for h in (8, 11, 14, 16):
        hourly[h] = _dp(h, rain=1.5 + h / 10, wind=20.0 + h, gust=35.0 + h,
                        pop=45.0 + h, thunder=ThunderLevel.MED)
    seg = _segment([_alert("thunderstorm", 4)], hourly=hourly)
    formatter = SMSTripFormatter()

    full = formatter.format_sms([seg], stage_name="Etappe 5", tz=_TZ, max_length=1000)
    assert "PR" in full, f"Fixture taugt nicht: kein PR-Token in {full!r}"
    assert "!TH:H@14" in full, f"Fixture taugt nicht: kein Warn-Block in {full!r}"

    # Die Rangfolge wird ueber das ganze Budget-Spektrum geprueft statt an
    # einer magischen Zahl: bei KEINEM Budget darf die amtliche Warnung fallen,
    # solange PR noch in der Zeile steht. Das 160er-Produktionsbudget ist der
    # obere Rand des Spektrums.
    pr_dropped_at_least_once = False
    for budget in range(40, min(len(full), 160) + 1):
        try:
            short = formatter.format_sms(
                [seg], stage_name="Etappe 5", tz=_TZ, max_length=budget,
            )
        except ValueError:
            continue  # Budget unterhalb der Mindestzeile — nicht Gegenstand des ACs
        assert len(short) <= budget, (
            f"Budget {budget} verletzt ({len(short)} Zeichen): {short!r}"
        )
        if "PR" in short:
            assert "!TH:H@14" in short, (
                f"Bei Budget {budget} fiel die amtliche Warnung vor PR: {short!r}"
            )
        else:
            pr_dropped_at_least_once = True
            assert "!TH:H@14" in short, (
                f"Bei Budget {budget} fehlt die amtliche Warnung trotz "
                f"gedropptem PR: {short!r}"
            )

    assert pr_dropped_at_least_once, (
        "Kein Budget im geprueften Bereich hat PR gedroppt — die Rangfolge "
        "wurde nicht wirklich ausgeuebt."
    )


# ---------------------------------------------------------------------------
# AC-12 — Mehrbenutzer-Isolation: Warnung von A faerbt nicht auf B ab
# ---------------------------------------------------------------------------
def test_ac12_warning_of_user_a_does_not_leak_into_user_b():
    formatter = SMSTripFormatter()
    seg_a = _segment([_alert("thunderstorm", 4)])
    seg_b = _segment([], segment_id=2)

    sms_a = formatter.format_sms([seg_a], stage_name="Etappe 5", tz=_TZ)
    sms_b = formatter.format_sms([seg_b], stage_name="Etappe 5", tz=_TZ)

    assert "!TH:H@14" in sms_a, f"Nutzer A ohne Warn-Block: {sms_a!r}"
    assert "!" not in sms_b, (
        f"Nutzer B darf keinen Warn-Block bekommen (Datenleck): {sms_b!r}"
    )
    assert sms_b == GOLDEN_NO_ALERTS, (
        f"SMS von Nutzer B weicht vom warnungsfreien Stand ab: {sms_b!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 — Standalone-Warn-SMS nutzt die neuen internationalen Kuerzel
# ---------------------------------------------------------------------------
_AC13_CASES = [
    ("wind_gust", "W"),
    ("extreme_heat", "HT"),
    ("rain", "HR"),
    ("black_ice", "IC"),
    ("access_ban", "CL"),
    ("wildfire_risk", "FR"),
]


@pytest.mark.parametrize("hazard,symbol", _AC13_CASES)
def test_ac13_standalone_alert_sms_uses_new_symbols(hazard: str, symbol: str):
    from output.renderers.alert.official_alerts import render_official_alert_sms
    text = render_official_alert_sms(
        [_notice(_alert(hazard, 3))], sms_prefix="GZ20", tz=_TZ,
    )
    assert _word_present(text, symbol), (
        f"Neues Kuerzel {symbol!r} fehlt in der Standalone-Warn-SMS: {text!r}"
    )
    for old in OLD_SYMBOLS:
        assert not _word_present(text, old), (
            f"Alt-Kuerzel {old!r} erscheint noch in der Standalone-Warn-SMS: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-14 — Anti-Divergenz: beide SMS-Pfade liefern dasselbe Kuerzel
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hazard,symbol", SPEC_SYMBOLS)
def test_ac14_both_sms_paths_use_the_same_symbol(hazard: str, symbol: str):
    from output.renderers.alert.official_alerts import render_official_alert_sms
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

    catalog_symbol = HAZARD_SMS_SYMBOLS[hazard]
    assert catalog_symbol == symbol, (
        f"Katalog-Kuerzel fuer {hazard}: {catalog_symbol!r}, Spec: {symbol!r}"
    )

    trip_sms = _sms([_alert(hazard, 3)])
    standalone = render_official_alert_sms(
        [_notice(_alert(hazard, 3))], sms_prefix="GZ20", tz=_TZ,
    )

    trip_expected = "!CL" if hazard == "access_ban" else f"!{catalog_symbol}:M"
    assert trip_expected in trip_sms, (
        f"Trip-Briefing-SMS ohne {trip_expected!r}: {trip_sms!r}"
    )
    assert _word_present(standalone, catalog_symbol), (
        f"Standalone-Warn-SMS ohne {catalog_symbol!r}: {standalone!r}"
    )


# ---------------------------------------------------------------------------
# F001 — unbekannte Gefahrenart darf nicht still verschwinden
# ---------------------------------------------------------------------------
def test_unknown_hazard_red_still_appears_in_trip_sms():
    """Ein neuer amtlicher Warntyp ausserhalb des 9er-Katalogs ist rot und
    muss trotzdem sichtbar sein — sonst stiller Sicherheitsverlust (#1239 F004)."""
    sms = _sms([_alert("volcanic_ash", 4)])
    assert "!VO:H@14" in sms, (
        f"Unbekannte rote Warnung wurde aus der Trip-SMS verworfen: {sms!r}"
    )


def test_unknown_hazard_same_symbol_in_both_sms_paths():
    from output.renderers.alert.official_alerts import render_official_alert_sms

    trip_sms = _sms([_alert("volcanic_ash", 3)])
    standalone = render_official_alert_sms(
        [_notice(_alert("volcanic_ash", 3))], sms_prefix="GZ20", tz=_TZ,
    )
    assert "!VO:M" in trip_sms, f"Trip-Briefing-SMS ohne 'VO': {trip_sms!r}"
    assert _word_present(standalone, "VO"), (
        f"Standalone-Warn-SMS ohne 'VO': {standalone!r}"
    )


def test_unknown_hazard_yellow_is_still_filtered():
    """Der Stufenfilter bleibt wirksam — nur der Katalog-Filter faellt weg."""
    sms = _sms([_alert("volcanic_ash", 2)])
    assert "!" not in sms, (
        f"Gelbe Warnung eines unbekannten Typs darf nicht erscheinen: {sms!r}"
    )


@pytest.mark.parametrize("hazard", ["", "___", "42"])
def test_hazard_without_ascii_letters_falls_back_to_xx(hazard: str):
    sms = _sms([_alert(hazard, 4)])
    assert "!XX:H@14" in sms, (
        f"hazard {hazard!r} ergibt kein 'XX'-Kuerzel: {sms!r}"
    )


# ---------------------------------------------------------------------------
# F002 — Fallback-Kuerzel darf sich nie als andere Gefahr ausgeben
# ---------------------------------------------------------------------------
# Unbekannte hazards, deren naive 2-Buchstaben-Ableitung auf ein vergebenes
# Katalog-Kuerzel fallen wuerde.
_COLLIDING_UNKNOWNS = [
    "thunder_squall",   # -> TH (thunderstorm)
    "snow_drift",       # -> SN (snow)
    "hr_advisory",      # -> HR (rain)
    "ice_jam",          # -> IC (black_ice)
    "htx_warning",      # -> HT (extreme_heat)
    "cd_alert",         # -> CD (extreme_cold)
    "frost_burst",      # -> FR (wildfire_risk)
    "closure_notice",   # -> CL (access_ban)
    "w",                # -> W  (wind_gust), zu kurz fuer 3 Buchstaben
]


@pytest.mark.parametrize("hazard", _COLLIDING_UNKNOWNS)
def test_f002_fallback_symbol_never_equals_a_catalog_symbol(hazard: str):
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for
    symbol = sms_symbol_for(hazard)
    assert symbol, f"Fallback fuer {hazard!r} ist leer"
    assert symbol not in set(HAZARD_SMS_SYMBOLS.values()), (
        f"Unbekannte Gefahr {hazard!r} gibt sich als Katalog-Gefahr {symbol!r} aus"
    )
    assert symbol.isascii(), f"Fallback {symbol!r} ist nicht GSM-7-rein"


def test_f002_thunder_squall_is_distinguishable_from_thunderstorm():
    from output.tokens.hazard_symbols import sms_symbol_for
    assert sms_symbol_for("thunder_squall") != "TH"
    assert sms_symbol_for("snow_drift") != "SN"


def test_f002_two_similar_hazards_render_as_two_distinct_tokens():
    """thunderstorm(ROT) + thunder_squall(ORANGE) duerfen im `!`-Block nicht
    zweimal dasselbe Kuerzel zeigen."""
    sms = _sms([_alert("thunderstorm", 4), _alert("thunder_squall", 3)])
    assert "!" in sms, f"Kein Warn-Block: {sms!r}"
    # Nur der `!`-Warn-Block wird geprueft — 'TH:-' davor ist das
    # Vorhersage-Token, keine amtliche Warnung.
    warn_block = sms.split("!", 1)[1]
    warn_symbols = re.findall(r"(?<![A-Za-z])([A-Z]+)(?=:[LMH])", warn_block)
    assert len(warn_symbols) == 2, (
        f"Erwartet zwei Warn-Token im Block: {warn_block!r}"
    )
    assert len(set(warn_symbols)) == 2, (
        f"Zwei verschiedene Gefahren tragen dasselbe Kuerzel: {sms!r}"
    )
    assert "!TH:H@14" in sms, f"Gewitterwarnung fehlt: {sms!r}"


def test_f002_fallback_is_deterministic():
    from output.tokens.hazard_symbols import sms_symbol_for
    for hazard in ("thunder_squall", "snow_drift", "volcanic_ash", ""):
        results = {sms_symbol_for(hazard) for _ in range(5)}
        assert len(results) == 1, (
            f"Fallback fuer {hazard!r} ist nicht deterministisch: {results!r}"
        )


@pytest.mark.parametrize("hazard", ["thunder_squall", "snow_drift"])
def test_f002_colliding_unknown_same_symbol_in_both_sms_paths(hazard: str):
    from output.renderers.alert.official_alerts import render_official_alert_sms
    from output.tokens.hazard_symbols import sms_symbol_for

    symbol = sms_symbol_for(hazard)
    trip_sms = _sms([_alert(hazard, 3)])
    standalone = render_official_alert_sms(
        [_notice(_alert(hazard, 3))], sms_prefix="GZ20", tz=_TZ,
    )
    assert f"!{symbol}:M" in trip_sms, (
        f"Trip-Briefing-SMS ohne {symbol!r}: {trip_sms!r}"
    )
    assert _word_present(standalone, symbol), (
        f"Standalone-Warn-SMS ohne {symbol!r}: {standalone!r}"
    )
