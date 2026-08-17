"""Gemeinsame Fixtures fuer Issue #1417 (EINE Gehzeit-Fenster-Quelle).

Kein Test-Modul (fuehrender Unterstrich -> pytest sammelt es nicht ein), nur
echte Datenmodell-Objekte und echte Renderer-Aufrufe. Kein ``Mock()``, kein
``patch()``, kein Netz, keine Mail. Vorbild fuer den Aufbau:
``tests/tdd/_min_temp_felt_fixtures.py`` (Issue #1410) und
``tests/tdd/test_night_temp_evening_only.py``.

Zwei Eigenschaften machen den Nachweis belastbar:

1. **Das Segment-Aggregat wird nicht von Hand geschrieben**, sondern vom
   ECHTEN Produktivpfad berechnet
   (``SegmentWeatherService._aggregate_for_segment()``, ``segment_weather.py``
   — offline, kein Provider-Aufruf). Damit misst der Test die tatsaechliche
   zweite Fenster-Regel (Ankunftsstunde EXKLUSIV) und nicht eine im Test
   erfundene Zahl.
2. **Alle vier Kanaele stammen aus EINEM ``format_email()``-Lauf** — dieselben
   Segmente, dieselbe Zeitzone, derselbe Report. Was hier auseinanderlaeuft,
   laeuft im Versand genauso auseinander.

Wertelandschaft: Grundniveau 15 °C (gefuehlt 10 °C), pro Konstellation genau
EINE kalte und EINE warme Stunde. Die Extremwerte liegen so, dass zwei
unabhaengige Fenster-Regeln (inklusive vs. exklusive Ankunftsstunde)
zwangslaeufig verschiedene Zahlen liefern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)

YEAR, MONTH, DAY = 2026, 7, 20
TZ = ZoneInfo("Europe/Paris")  # GR20/KHW-typisch, CEST = UTC+2 im Juli

BASE_C = 15.0        # Grundniveau gemessen
BASE_FELT_C = 10.0   # Grundniveau gefuehlt

STAGE_NAME = "E7"
TRIP_NAME = "Issue1417"


def local_to_utc(hour: int, *, day: int = DAY) -> datetime:
    """Ortszeit-Wanduhr (Europe/Paris) -> echter UTC-Instant."""
    return datetime(YEAR, MONTH, day, hour, 0, tzinfo=TZ).astimezone(timezone.utc)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(YEAR, MONTH, DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _dp(hour: int, *, temp: float, felt: float, day: int = DAY) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=local_to_utc(hour, day=day),
        t2m_c=temp,
        wind_chill_c=felt,
        wind10m_kmh=12.0,
        gust_kmh=18.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _trip_segment(seg_id: int, start_h: int, end_h: int, *, day: int = DAY) -> TripSegment:
    return TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.0 + seg_id * 0.05, lon=9.0,
                             elevation_m=500.0, distance_from_start_km=seg_id * 5.0),
        end_point=GPXPoint(lat=42.0 + (seg_id + 1) * 0.05, lon=9.1,
                           elevation_m=900.0, distance_from_start_km=(seg_id + 1) * 5.0),
        start_time=local_to_utc(start_h, day=day),
        end_time=local_to_utc(end_h, day=day),
        duration_hours=float(end_h - start_h),
        distance_km=5.0,
        ascent_m=400.0,
        descent_m=100.0,
    )


def _full_day_timeseries(
    temps: dict[int, float], felt: dict[int, float], *, day: int = DAY,
) -> NormalizedTimeseries:
    """24 Stunden Ortszeit — so wie ein Provider sie liefert (Ganztags-Antwort,
    aus der jedes Segment sein eigenes Fenster schneidet)."""
    data = [
        _dp(h, temp=temps.get(h, BASE_C), felt=felt.get(h, BASE_FELT_C), day=day)
        for h in range(24)
    ]
    return NormalizedTimeseries(meta=_meta(), data=data)


def _aggregating_service():
    """``SegmentWeatherService`` nur fuer ``_aggregate_for_segment()``.

    Reine Rechenfunktion ohne Netz: sie filtert eine vorhandene Zeitreihe auf
    das Segmentfenster und aggregiert. Der Provider liefert lediglich einen
    Namen. Vorbild: ``tests/test_provider_tz_normalization.py`` (F001-Test).
    """
    from providers.openmeteo import OpenMeteoProvider
    from services.segment_weather import SegmentWeatherService

    return SegmentWeatherService(OpenMeteoProvider())


def build_segments(
    bounds: list[tuple[int, int]],
    temps: dict[int, float],
    felt: dict[int, float],
    *,
    day: int = DAY,
) -> list[SegmentWeatherData]:
    """Etappe aus mehreren Teilen — Aggregat vom ECHTEN Produktivpfad.

    ``bounds``: Ortszeit-Fenster je Etappenteil ``[(start, ende), ...]``. Jeder
    Teil bekommt dieselbe volle 24-Stunden-Zeitreihe (Provider-Realitaet) und
    sein Aggregat aus ``_aggregate_for_segment()``.
    """
    ts = _full_day_timeseries(temps, felt, day=day)
    service = _aggregating_service()
    fetched_at = datetime(YEAR, MONTH, day, 4, 0, tzinfo=timezone.utc)
    return [
        service._aggregate_for_segment(
            _trip_segment(idx + 1, start_h, end_h, day=day), ts, fetched_at=fetched_at,
        )
        for idx, (start_h, end_h) in enumerate(bounds)
    ]


def segments_without_aggregation_config(
    bounds: list[tuple[int, int]],
    temps: dict[int, float],
    felt: dict[int, float],
    *,
    day: int = DAY,
) -> list[SegmentWeatherData]:
    """Wie ``build_segments()``, aber ohne ``aggregation_config`` im Aggregat.

    Die Werte bleiben die ECHTEN (aus ``_aggregate_for_segment()``), nur die
    Aggregations-Regelkarte fehlt. ``SegmentWeatherSummary.aggregation_config``
    hat den Default ``{}`` (``models.py:403``) und wird ausschliesslich von
    ``compute_basis_metrics()``/``compute_extended_metrics()`` gefuellt — jedes
    anderswo entstandene Aggregat kommt ohne sie an. Genau das ist die Form der
    eingefrorenen Referenz-Fixture ``gr20-summer-evening``.

    Folge: ``aggregate_stage()`` iteriert ueber eine leere Regelkarte und
    liefert ein Etappen-Aggregat, in dem JEDES Feld ``None`` ist. Der
    Kurzzusammenfassungssatz verliert dadurch seinen Temperaturteil, obwohl
    dieselbe Mail eine Stunde darueber eine Temperatur-Kachel zeigt.
    """
    import dataclasses

    return [
        dataclasses.replace(
            s, aggregated=dataclasses.replace(s.aggregated, aggregation_config={}),
        )
        for s in build_segments(bounds, temps, felt, day=day)
    ]


def failed_segment(seg_id: int, start_h: int, end_h: int, *, day: int = DAY) -> SegmentWeatherData:
    """Etappenteil mit Provider-Ausfall: keine Zeitreihe, LEERES Aggregat.

    Exakt die Form, die ``segment_weather.py:161,208`` im Fehlerfall baut.
    """
    return SegmentWeatherData(
        segment=_trip_segment(seg_id, start_h, end_h, day=day),
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(YEAR, MONTH, day, 4, 0, tzinfo=timezone.utc),
        provider="openmeteo",
        has_error=True,
        error_message="provider_unavailable",
    )


def aggregate_only_segment(
    seg_id: int, start_h: int, end_h: int, *,
    temp_min: float, temp_max: float, felt_min: float, felt_max: float,
    day: int = DAY,
) -> SegmentWeatherData:
    """Etappenteil OHNE Stunden-Zeitreihe, aber mit brauchbarem Aggregat.

    Der Fail-soft-Fall aus ``sms_trip.py`` (Bug #398-Verhalten): der Kanal muss
    weiter einen Wert zeigen, auch wenn keine Rohpunkte vorliegen.
    """
    return SegmentWeatherData(
        segment=_trip_segment(seg_id, start_h, end_h, day=day),
        timeseries=None,
        aggregated=SegmentWeatherSummary(
            temp_min_c=temp_min, temp_max_c=temp_max,
            temp_avg_c=(temp_min + temp_max) / 2,
            wind_chill_min_c=felt_min, wind_chill_max_c=felt_max,
        ),
        fetched_at=datetime(YEAR, MONTH, day, 4, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def night_weather(
    arrival_h: int, *, temp_min: float, felt_min: float, low_hour: int = 3,
    day: int = DAY,
) -> NormalizedTimeseries:
    """Nacht-Zeitreihe Ankunft -> 06:00 Folgetag am Etappenziel.

    Tiefpunkt bei ``low_hour`` (Folgetag), sonst milder — so beweist ein
    korrekter Nachtwert, dass ueber das Nachtfenster MINIMIERT wurde.
    """
    mild_c, mild_felt_c = temp_min + 4.0, felt_min + 4.0
    points = [_dp(h, temp=mild_c, felt=mild_felt_c, day=day) for h in range(arrival_h, 24)]
    for h in range(0, 7):
        is_low = h == low_hour
        points.append(_dp(
            h, temp=temp_min if is_low else mild_c,
            felt=felt_min if is_low else mild_felt_c, day=day + 1,
        ))
    return NormalizedTimeseries(meta=_meta(), data=points)


def dc(*metric_ids: str) -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration mit genau den genannten Metriken aktiv.

    Issue #1728 Scheibe 1: der ``aggregations``-Parameter (#1357) ist
    entfernt -- die gespeicherte Auswertungswahl wird an keinem Trip-Wirkort
    mehr gelesen.
    """
    return UnifiedWeatherDisplayConfig(
        trip_id="i1417",
        metrics=[
            MetricConfig(metric_id=m, enabled=True)
            for m in metric_ids
        ],
    )


# ---------------------------------------------------------------------------
# Konstellationen (AC-5-Matrix)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Constellation:
    """Eine Etappen-Konstellation mit den Werten, die ALLE Kanaele nennen muessen.

    ``expected_*`` sind von Hand nach der fachlich richtigen Regel bestimmt
    (Ankunftsstunde des LETZTEN Teils zaehlt mit, innere Grenzen genau einmal —
    #1146 + #806/#807), nicht aus dem Produktivcode abgeleitet.
    """
    name: str
    bounds: list[tuple[int, int]]
    temps: dict[int, float]
    felt: dict[int, float]
    expected_min_c: float
    expected_max_c: float
    expected_felt_min_c: float
    expected_felt_max_c: float
    diverges_today: bool  # laufen die beiden heutigen Regeln hier auseinander?
    note: str = ""

    def segments(self) -> list[SegmentWeatherData]:
        return build_segments(self.bounds, self.temps, self.felt)

    @property
    def arrival_hour(self) -> int:
        return self.bounds[-1][1]


COLD_C, WARM_C = 5.0, 22.0
COLD_FELT_C, WARM_FELT_C = 0.0, 17.0
DEEP_COLD_C, HOT_C = 3.0, 24.0
DEEP_COLD_FELT_C, HOT_FELT_C = -2.0, 19.0


CONSTELLATIONS: list[Constellation] = [
    Constellation(
        name="extremwert_an_der_ankunftsstunde",
        bounds=[(8, 10), (10, 12)],
        temps={9: COLD_C, 12: WARM_C},
        felt={9: COLD_FELT_C, 12: WARM_FELT_C},
        expected_min_c=COLD_C, expected_max_c=WARM_C,
        expected_felt_min_c=COLD_FELT_C, expected_felt_max_c=WARM_FELT_C,
        diverges_today=True,
        note="Der gemeldete Fall #1417: waermste Stunde ist die Ankunft.",
    ),
    Constellation(
        name="extremwert_an_innerer_segmentgrenze",
        bounds=[(8, 10), (10, 12)],
        temps={9: COLD_C, 10: WARM_C},
        felt={9: COLD_FELT_C, 10: WARM_FELT_C},
        expected_min_c=COLD_C, expected_max_c=WARM_C,
        expected_felt_min_c=COLD_FELT_C, expected_felt_max_c=WARM_FELT_C,
        diverges_today=False,
        note="Grenzstunde zweier Teile — beide Regeln sehen sie, Kontrollfall.",
    ),
    Constellation(
        name="extremwert_mitten_im_segment",
        bounds=[(8, 10), (10, 13)],
        temps={9: COLD_C, 11: WARM_C},
        felt={9: COLD_FELT_C, 11: WARM_FELT_C},
        expected_min_c=COLD_C, expected_max_c=WARM_C,
        expected_felt_min_c=COLD_FELT_C, expected_felt_max_c=WARM_FELT_C,
        diverges_today=False,
        note="Normalfall ohne Randberuehrung — muss unveraendert bleiben.",
    ),
    Constellation(
        name="ein_einziges_segment_extremwert_an_der_ankunft",
        bounds=[(8, 12)],
        temps={9: COLD_C, 12: WARM_C},
        felt={9: COLD_FELT_C, 12: WARM_FELT_C},
        expected_min_c=COLD_C, expected_max_c=WARM_C,
        expected_felt_min_c=COLD_FELT_C, expected_felt_max_c=WARM_FELT_C,
        diverges_today=True,
        note="Einteilige Etappe — der Sonderfall 'letztes Segment' ist hier das einzige.",
    ),
    Constellation(
        name="drei_segmente_extremwert_an_der_ankunft",
        bounds=[(7, 9), (9, 11), (11, 14)],
        temps={8: DEEP_COLD_C, 14: HOT_C},
        felt={8: DEEP_COLD_FELT_C, 14: HOT_FELT_C},
        expected_min_c=DEEP_COLD_C, expected_max_c=HOT_C,
        expected_felt_min_c=DEEP_COLD_FELT_C, expected_felt_max_c=HOT_FELT_C,
        diverges_today=True,
        note="Drei Teile — die Ankunft liegt am Ende des dritten.",
    ),
    Constellation(
        name="drei_segmente_extremwert_an_innerer_grenze",
        bounds=[(7, 9), (9, 11), (11, 14)],
        temps={8: DEEP_COLD_C, 11: HOT_C},
        felt={8: DEEP_COLD_FELT_C, 11: HOT_FELT_C},
        expected_min_c=DEEP_COLD_C, expected_max_c=HOT_C,
        expected_felt_min_c=DEEP_COLD_FELT_C, expected_felt_max_c=HOT_FELT_C,
        diverges_today=False,
        note="Drei Teile, Extremwert an der zweiten inneren Grenze — Kontrollfall.",
    ),
]

CONSTELLATIONS_BY_NAME = {c.name: c for c in CONSTELLATIONS}


# ---------------------------------------------------------------------------
# Beobachtung: EIN Report -> vier Kanaele, nur gerenderter Text wird gelesen
# ---------------------------------------------------------------------------

_PILL_HEADER = "━━ Metriken-Überblick ━━"
_SPAN_UNIT = "°C"
_DASH = "–"  # En-Dash der Spannen-Formatierung

# Kachelzeile gemessen: "13–17°C · Max 12:00" (0 Nachkommastellen).
_MAIL_TEMP_PILL = re.compile(
    rf"^(?:\S+\s+)?(?P<lo>-?\d+)(?:{_DASH}(?P<hi>-?\d+))?{_SPAN_UNIT} · Max (?P<h>\d{{2}}):00$"
)
# Kachelzeile gefuehlt: "gef. 1.0–18.0°C · Max 11:00" (1 Nachkommastelle).
_MAIL_FELT_PILL = re.compile(
    rf"^(?:\S+\s+)?gef\. (?P<lo>-?\d+\.\d)(?:{_DASH}(?P<hi>-?\d+\.\d))?"
    rf"{_SPAN_UNIT} · Max (?P<h>\d{{2}}):00$"
)
# Telegram-Kurzuebersicht: "T 5.0-22.0@12" bzw. "T 15.0".
_TG_SPAN = re.compile(r"^(?P<lo>-?\d+\.\d)(?:-(?P<hi>-?\d+\.\d))?(?:@(?P<h>\d{1,2}))?$")
# Kurzzusammenfassung gemessen: "5–22°C"; gefuehlt: "gef. 0–17°C".
_COMPACT_TEMP = re.compile(rf"^(?P<lo>-?\d+)(?:{_DASH}(?P<hi>-?\d+))?{_SPAN_UNIT}$")
_COMPACT_FELT = re.compile(rf"^gef\. (?P<lo>-?\d+)(?:{_DASH}(?P<hi>-?\d+))?{_SPAN_UNIT}$")


@dataclass(frozen=True)
class Extrema:
    """Tiefst-/Hoechstwert, wie EIN Kanal sie nennt (``None`` = nicht genannt)."""
    low: Optional[float]
    high: Optional[float]
    raw: str = ""

    def as_pair(self) -> tuple[Optional[float], Optional[float]]:
        return (self.low, self.high)


def _from_match(m: Optional[re.Match], raw: str) -> Extrema:
    if m is None:
        return Extrema(None, None, raw)
    lo = float(m.group("lo"))
    hi_raw = m.groupdict().get("hi")
    hi = float(hi_raw) if hi_raw is not None else lo
    return Extrema(lo, hi, raw)


def render_report(
    segments: list[SegmentWeatherData],
    *,
    report_type: str,
    metrics: tuple[str, ...] = ("temperature",),
    night: Optional[NormalizedTimeseries] = None,
):
    """EIN echter Briefing-Lauf — Quelle fuer alle vier Kanaele."""
    from output.renderers.trip_report import TripReportFormatter

    return TripReportFormatter().format_email(
        segments,
        trip_name=TRIP_NAME,
        report_type=report_type,
        night_weather=night,
        display_config=dc(*metrics),
        stage_name=STAGE_NAME,
        tz=TZ,
    )


def pill_lines(report) -> list[str]:
    """Die Kachelzeilen des ``Metriken-Überblick``-Blocks der echten Mail."""
    lines = report.email_plain.splitlines()
    try:
        start = lines.index(_PILL_HEADER) + 1
    except ValueError:
        return []
    out = []
    for line in lines[start:]:
        if not line.strip():
            break
        out.append(line.strip())
    return out


def mail_temp(report) -> Extrema:
    """Gemessene Temperatur der Mail-Kachelzeile."""
    for line in pill_lines(report):
        m = _MAIL_TEMP_PILL.match(line)
        if m is not None:
            return _from_match(m, line)
    return Extrema(None, None, " | ".join(pill_lines(report)))


def mail_felt(report) -> Extrema:
    """Gefuehlte Temperatur der Mail-Kachelzeile."""
    for line in pill_lines(report):
        m = _MAIL_FELT_PILL.match(line)
        if m is not None:
            return _from_match(m, line)
    return Extrema(None, None, " | ".join(pill_lines(report)))


# Issue #1728 Scheibe 1: ``mail_temp_average()`` (Mittelwert-Kachel, #1357)
# ist ERSATZLOS entfernt -- die Kachel zeigt seit dieser Scheibe unbedingt die
# Spanne, einen gerenderten Mittelwert gibt es nicht mehr. Ein Helfer, der
# eine Ausgabe sucht, die es nicht gibt, liefert stumm ``None`` und laedt zum
# Fehlschluss ein.


# Issue #1824 (A): siehe _min_temp_felt_fixtures.py — bei gewaehltem Tiefst-
# UND Hoechstwert steht EIN Bereichs-Token ('D13/27'). 'K'/'FK' bezeichnen
# weiterhin den Tiefstwert, 'D'/'FD' den Hoechstwert.
# Fix #1926: temperature_day_low/wind_chill_day_low SMS-Wire-Token K->L,
# FK->FL (PO-Konsistenzentscheid 2026-08-17, Kollisionsvermeidung).
_HALF = r"-?\d+|-|\?"
_RANGE_PARTNER = {"L": "D", "FL": "FD"}


def sms_token_value(sms: str, symbol: str) -> Optional[str]:
    """Wert eines Temperatur-Tokens aus der gerenderten SMS (``None`` = fehlt).

    ``fullmatch`` auf dem einzelnen Token schliesst Praefix-Verwechslungen aus:
    'FK1' ist kein 'K'-Token.
    """
    body = sms.split(": ", 1)[1] if ": " in sms else sms
    tokens = body.split(" ")
    pattern = re.compile(rf"{re.escape(symbol)}({_HALF})(?:/({_HALF}))?$")
    for token in tokens:
        m = pattern.fullmatch(token)
        if m:
            return m.group(2) if m.group(2) is not None else m.group(1)
    partner = _RANGE_PARTNER.get(symbol)
    if partner is None:
        return None
    ranged = re.compile(rf"{re.escape(partner)}({_HALF})/({_HALF})$")
    for token in tokens:
        m = ranged.fullmatch(token)
        if m:
            return m.group(1)
    return None


def _sms_num(sms: str, symbol: str) -> Optional[float]:
    raw = sms_token_value(sms, symbol)
    if raw is None or raw in ("-", "?"):
        return None
    return float(raw)


def sms_temp(report) -> Extrema:
    """Gehzeit-Extrema der SMS (Token ``L``/``D``, Fix #1926: vormals ``K``)."""
    sms = report.sms_text or ""
    return Extrema(_sms_num(sms, "L"), _sms_num(sms, "D"), sms)


def sms_felt(report) -> Extrema:
    """Gefuehlte Gehzeit-Extrema der SMS (Token ``FL``/``FD``, Fix #1926:
    vormals ``FK``)."""
    sms = report.sms_text or ""
    return Extrema(_sms_num(sms, "FL"), _sms_num(sms, "FD"), sms)


def sms_night(report) -> Extrema:
    """Nacht-Tiefstwerte der SMS (Token ``N``/``FN``) — als (gemessen, gefuehlt)."""
    sms = report.sms_text or ""
    return Extrema(_sms_num(sms, "N"), _sms_num(sms, "FN"), sms)


def overview_bubble(report) -> str:
    for bubble in report.telegram_bubbles or []:
        text = bubble if isinstance(bubble, str) else getattr(bubble, "text", "")
        if "Kurzübersicht" in text:
            return text
    return ""


def overview_line(report, label: str) -> str:
    for line in overview_bubble(report).splitlines():
        if line.startswith(f"{label} "):
            return line
    return ""


def _telegram_extrema(report, label: str) -> Extrema:
    line = overview_line(report, label)
    value = line.split(" ", 1)[1].strip() if " " in line else ""
    return _from_match(_TG_SPAN.match(value), line or overview_bubble(report))


def telegram_temp(report) -> Extrema:
    """Gemessene Temperatur der Telegram-Kurzuebersicht (Zeile ``T``)."""
    return _telegram_extrema(report, "T")


def telegram_felt(report) -> Extrema:
    """Gefuehlte Temperatur der Telegram-Kurzuebersicht (Zeile ``TF``)."""
    return _telegram_extrema(report, "TF")


def compact_sentence(report) -> str:
    """Der Kurzzusammenfassungssatz, wie er in der echten Mail steht."""
    prefix = f"{STAGE_NAME}: "
    for line in report.email_plain.splitlines():
        if line.startswith(prefix):
            return line
    return ""


def compact_parts(report) -> list[str]:
    sentence = compact_sentence(report)
    body = sentence.split(": ", 1)[1] if ": " in sentence else ""
    return body.split(", ") if body else []


def compact_temp(report) -> Extrema:
    """Gemessene Temperatur der E-Mail-Kurzzusammenfassung."""
    for part in compact_parts(report):
        m = _COMPACT_TEMP.match(part)
        if m is not None:
            return _from_match(m, compact_sentence(report))
    return Extrema(None, None, compact_sentence(report))


def compact_felt(report) -> Extrema:
    """Gefuehlte Temperatur der E-Mail-Kurzzusammenfassung."""
    for part in compact_parts(report):
        m = _COMPACT_FELT.match(part)
        if m is not None:
            return _from_match(m, compact_sentence(report))
    return Extrema(None, None, compact_sentence(report))


CHANNEL_LABELS = {
    "mail": "Mail-Kachelzeile",
    "sms": "SMS",
    "compact": "E-Mail-Kurzzusammenfassung",
    "telegram": "Telegram-Kurzübersicht",
}


def measured_by_channel(report) -> dict[str, Extrema]:
    return {
        "mail": mail_temp(report),
        "sms": sms_temp(report),
        "compact": compact_temp(report),
        "telegram": telegram_temp(report),
    }


def felt_by_channel(report) -> dict[str, Extrema]:
    return {
        "mail": mail_felt(report),
        "sms": sms_felt(report),
        "compact": compact_felt(report),
        "telegram": telegram_felt(report),
    }


def describe(channels: dict[str, Extrema]) -> str:
    """Menschenlesbare Gegenueberstellung fuer Fehlermeldungen."""
    return "\n".join(
        f"  {CHANNEL_LABELS[name]:<28} Tiefst={ex.low!r} Hoechst={ex.high!r}"
        f"   <- {ex.raw!r}"
        for name, ex in channels.items()
    )
