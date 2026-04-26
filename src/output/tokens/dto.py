"""DTOs for the token builder. See output_token_builder.md v1.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

ReportType = Literal["morning", "evening", "update", "compare"]
Profile = Literal["standard", "wintersport"]
TokenCategory = Literal["forecast", "vigilance", "fire", "wintersport", "debug"]


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

    def render(self, max_length: int = 160) -> str:
        from src.output.tokens.render import render_line
        return render_line(self, max_length)

    def filter_for_subject(self) -> "TokenLine":
        """Subset for E-Mail Subject (sms_format.md §11):
        '{Etappe} - {ReportType} - {MainRisk} - D{val} W{val} G{val} TH:{level}'.

        Note: 'D' here means **Tag-Max temperature** (NOT 'Debug').

        β1 stub - returns self. β2 implements the real filter.
        """
        return self
