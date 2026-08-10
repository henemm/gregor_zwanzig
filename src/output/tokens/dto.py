"""DTOs for the token builder. See output_token_builder.md v1.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

ReportType = Literal["morning", "evening", "update", "compare"]
TokenCategory = Literal[
    "forecast", "vigilance", "official_alert", "fire", "wintersport", "debug",
    "unavailable",
]


@dataclass(frozen=True)
class HourlyValue:
    """One hourly sample (hour 0-23 + value)."""
    hour: int
    value: float


@dataclass(frozen=True)
class DailyForecast:
    """One day of normalized forecast data."""
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    rain_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    pop_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    wind_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    gust_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    thunder_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    snow_depth_cm: Optional[float] = None
    snow_new_24h_cm: Optional[float] = None
    snowfall_limit_m: Optional[float] = None
    avalanche_level: Optional[int] = None
    wind_chill_c: Optional[float] = None
    # Issue #1410: vier additive Felder (Default None -> kein Bestandsaufrufer
    # bricht). `temp_min_c` bleibt ab jetzt IMMER der Gehzeit-Tiefstwert (K);
    # der aufgeloeste Nachtwert am Ziel wohnt in `night_temp_min_c` (N) statt
    # `temp_min_c` in-place zu ueberschreiben.
    wind_chill_min_c: Optional[float] = None       # Gehzeit-Tiefst, gefuehlt (FK)
    wind_chill_max_c: Optional[float] = None       # Gehzeit-Hoechst, gefuehlt (FD)
    night_temp_min_c: Optional[float] = None       # Nacht-Tiefst am Ziel, gemessen (N)
    night_wind_chill_min_c: Optional[float] = None  # Nacht-Tiefst am Ziel, gefuehlt (FN)
    confidence_pct_min: Optional[int] = None  # Issue #121: worst-case daily confidence
    has_data_gap: bool = False  # Issue #1328: True -> "-" wird zu "?" (unbekannt)
    # Issue #1475 S5a: Hagel-Kennzeichen des Tages (ja/unbekannt/nein). Additiv,
    # Default None -> jeder Bestandsaufruf bleibt zeichengleich. NUR `True`
    # erzeugt ueberhaupt ein sichtbares Zeichen (Suffix am `TH:`-Token).
    hail_flag: Optional[bool] = None
    # Issue #1660 Scheibe B: 14 additive Felder (Muster #1410/#1475) fuer
    # bisher waehlbare, aber wirkungslose Metriken. Alle mit Default (leeres
    # Tupel bzw. None) -> jeder Bestandsaufruf bleibt zeichengleich (AC-11).
    # Klasse (a) Threshold-Peak, Stunden-Samples:
    humidity_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    dewpoint_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    cape_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    uv_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    cloud_total_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    cloud_low_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    cloud_mid_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    cloud_high_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    # Klasse (b) Invers-Min, Stunden-Samples:
    visibility_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    freezing_level_hourly: tuple[HourlyValue, ...] = field(default_factory=tuple)
    # Klasse (c) Tageswert ohne Stunde:
    wind_direction_sector: Optional[str] = None   # 8-Sektor-Kompasswert (WD)
    precip_type_dominant: Optional[str] = None    # Ein-Buchstaben-Code G/S/M/R (PT)
    sunshine_hours: Optional[float] = None        # unrunde Sonnenstunden (SU)
    pressure_avg_hpa: Optional[float] = None      # Tagesmittel hPa (HP)


@dataclass(frozen=True)
class NormalizedForecast:
    """Multi-day normalized forecast input."""
    days: tuple[DailyForecast, ...] = field(default_factory=tuple)
    provider: str = "open-meteo"
    country: str = ""
    vigilance_hr_level: Optional[str] = None
    vigilance_hr_hour: Optional[int] = None
    vigilance_th_level: Optional[str] = None
    vigilance_th_hour: Optional[int] = None
    # Issue #1318: gefilterte, gekuerzelte amtliche Warnungen des Tages als
    # (Kuerzel, Stufenbuchstabe, Stunde) — Stufenbuchstabe "" = blankes Kuerzel
    # ohne Stufe (access_ban), Stunde None = ganztaegig (kein '@h').
    # Bereits sortiert (Stufe absteigend, dann Katalog-Reihenfolge).
    official_alerts: tuple[tuple[str, str, Optional[int]], ...] = field(default_factory=tuple)
    # Issue #1349: mindestens eine abdeckende amtliche Warn-Quelle beim Fetch
    # ausgefallen (kein Neuaufbau der Erkennung — Flag wird 1:1 durchgereicht).
    # Additiv, Default False -> Byte-Identitaet fuer alle Bestandsaufrufer.
    official_alerts_unavailable: bool = False
    fire_zones_high: tuple[str, ...] = field(default_factory=tuple)
    fire_zones_max: tuple[str, ...] = field(default_factory=tuple)
    fire_massifs: tuple[str, ...] = field(default_factory=tuple)
    debug_provider: Optional[str] = None
    debug_confidence: Optional[str] = None


@dataclass(frozen=True)
class MetricSpec:
    """Per-metric configuration consumed by the builder."""
    symbol: str
    enabled: bool = True
    morning_enabled: bool = True
    evening_enabled: bool = True
    threshold: Optional[float] = None
    use_friendly_format: bool = False
    friendly_label: str = ""
    # Issue #435: explicit format_mode (raw/scale/simplified/symbol).
    # When set to "symbol" or "scale", the builder emits a friendly token
    # bit-identical to legacy use_friendly_format=True (Backward-Compat).
    format_mode: Optional[str] = None


@dataclass(frozen=True)
class Token:
    """A single token. Render: '{symbol}{value}' or '{symbol}-' for null;
    friendly tokens encode label as '\\x00{label}' and render as the label.
    """
    symbol: str
    value: str
    category: TokenCategory
    priority: int
    morning_visible: bool = True
    evening_visible: bool = True

    def render(self) -> str:
        if self.value.startswith("\x00"):
            return self.value[1:]
        if self.value == "-":
            return f"{self.symbol}-"
        return f"{self.symbol}{self.value}"


@dataclass(frozen=True)
class TokenLine:
    """Full token line per sms_format.md §2/§3 (POSITIONAL)."""
    stage_name: str
    report_type: ReportType
    tokens: tuple[Token, ...] = field(default_factory=tuple)
    truncated: bool = False
    full_length: int = 0
    main_risk: str | None = None  # β2: Top-Risk-Label aus RiskEngine (English; subject.py übersetzt zu DE)
    trip_name: str | None = None  # β2: Optional, für Subject-Präfix [{trip_name}]
    shortcode: str | None = None  # Bug #775: GZ#XXXX — primärer Routing-Key im Betreff

    def render(self, max_length: int = 160) -> str:
        from output.tokens.render import render_line
        return render_line(self, max_length)

    def filter_for_subject(self) -> "TokenLine":
        """Subset for E-Mail Subject (sms_format.md §11):
        '{Etappe} - {ReportType} - {MainRisk} - D{val} W{val} G{val} TH:{level}'.

        Note: 'D' here means **Tag-Max temperature** (NOT 'Debug').

        β1 stub - returns self. β2 implements the real filter.
        """
        return self
