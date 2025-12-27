---
entity_id: cli_refactoring
type: feature
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [cli, architecture, refactoring, best-practices]
---

# CLI Refactoring - Modulare Architektur

## Approval

- [x] Approved (2025-12-27)

**Decisions:**
- pydantic-settings: Yes
- Async: No (sync for now)
- Formatter: Minimal version

## Purpose

Refactoring der CLI zu einer sauberen, modularen Architektur mit klarer Trennung der Verantwortlichkeiten. Ermoeglicht einfache Erweiterung um neue Provider und Ausgabekanaele.

---

## 1. Architektur-Probleme (Ist-Zustand)

| Problem | Beschreibung |
|---------|--------------|
| Monolithische main() | Alles in einer Funktion |
| Keine Provider-Abstraktion | Provider direkt aufrufen ist nicht erweiterbar |
| Keine Service-Layer | Business Logic fehlt |
| Hardcoded Config | Keine zentrale Konfiguration |
| Keine Dependency Injection | Tight coupling |

---

## 2. Ziel-Architektur (Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  (Argument Parsing, User Interaction)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│  ForecastService, ReportService                              │
│  (Orchestrierung, Business Logic)                            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Provider Layer  │ │  Output Layer   │ │  Config Layer   │
│ (WeatherProvider│ │ (OutputChannel) │ │ (Settings)      │
│  Protocol)      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
        │                   │
        ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│ GeoSphere       │ │ Console         │
│ MET             │ │ Email           │
│ SLF             │ │ SMS (future)    │
└─────────────────┘ └─────────────────┘
```

---

## 3. Design Patterns & Best Practices

### 3.1 Protocol-based Abstractions (PEP 544)

```python
from typing import Protocol

class WeatherProvider(Protocol):
    """Interface for all weather data providers."""

    def fetch_forecast(
        self,
        location: Location,
        start: datetime,
        end: datetime
    ) -> NormalizedTimeseries:
        ...

    @property
    def name(self) -> str:
        ...
```

### 3.2 Dependency Injection via Constructor

```python
class ForecastService:
    def __init__(
        self,
        provider: WeatherProvider,
        debug: DebugBuffer,
    ) -> None:
        self._provider = provider
        self._debug = debug
```

### 3.3 Configuration with Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Location
    latitude: float = 47.0
    longitude: float = 11.5

    # Provider
    provider: str = "geosphere"

    # Report
    report_type: str = "evening"
    channel: str = "console"

    class Config:
        env_prefix = "GZ_"
        env_file = ".env"
```

### 3.4 Result Types for Error Handling

```python
from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")

@dataclass
class Ok(Generic[T]):
    value: T

@dataclass
class Err:
    error: str

Result = Union[Ok[T], Err]
```

---

## 4. Module-Struktur

```
src/
├── app/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (thin)
│   ├── models.py           # DTOs (existing)
│   ├── config.py           # Settings, Location    [NEW]
│   └── debug.py            # DebugBuffer (existing)
│
├── services/                                        [NEW]
│   ├── __init__.py
│   ├── forecast.py         # ForecastService
│   └── report.py           # ReportService (future)
│
├── providers/
│   ├── __init__.py
│   ├── base.py             # WeatherProvider Protocol [NEW]
│   └── geosphere.py        # GeoSphere implementation
│
└── outputs/                                         [NEW]
    ├── __init__.py
    ├── base.py             # OutputChannel Protocol
    ├── console.py          # Console output
    └── email.py            # Email output (from core.py)
```

---

## 5. Neue/Geaenderte Dateien

### 5.1 src/app/config.py (NEW)

```python
"""Application configuration."""
from dataclasses import dataclass
from typing import Optional
from pydantic_settings import BaseSettings

@dataclass(frozen=True)
class Location:
    """Geographic location."""
    latitude: float
    longitude: float
    name: Optional[str] = None
    elevation_m: Optional[int] = None

class Settings(BaseSettings):
    """Application settings with env/file support."""

    # Location (required)
    latitude: float
    longitude: float
    location_name: str = "Unknown"

    # Provider selection
    provider: str = "geosphere"

    # Report settings
    report_type: str = "evening"  # evening, morning, alert
    channel: str = "console"      # console, email, none
    debug_level: str = "info"     # info, verbose
    dry_run: bool = False

    # SMTP (optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    mail_to: Optional[str] = None

    class Config:
        env_prefix = "GZ_"
        env_file = ".env"

    def get_location(self) -> Location:
        return Location(
            latitude=self.latitude,
            longitude=self.longitude,
            name=self.location_name,
        )
```

### 5.2 src/providers/base.py (NEW)

```python
"""Provider protocol and registry."""
from typing import Protocol, Optional
from datetime import datetime
from app.models import NormalizedTimeseries
from app.config import Location

class WeatherProvider(Protocol):
    """Protocol for weather data providers."""

    @property
    def name(self) -> str:
        """Provider identifier."""
        ...

    def fetch_forecast(
        self,
        location: Location,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> NormalizedTimeseries:
        """Fetch weather forecast for location."""
        ...

def get_provider(name: str) -> WeatherProvider:
    """Factory function for providers."""
    providers = {
        "geosphere": lambda: GeoSphereProvider(),
        # "met": lambda: METProvider(),
        # "slf": lambda: SLFProvider(),
    }
    if name not in providers:
        raise ValueError(f"Unknown provider: {name}")
    return providers[name]()
```

### 5.3 src/services/forecast.py (NEW)

```python
"""Forecast service - orchestrates data fetching."""
from datetime import datetime, timezone
from typing import Optional

from app.config import Location, Settings
from app.models import NormalizedTimeseries
from app.debug import DebugBuffer
from providers.base import WeatherProvider

class ForecastService:
    """Service for fetching and processing weather forecasts."""

    def __init__(
        self,
        provider: WeatherProvider,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        self._provider = provider
        self._debug = debug or DebugBuffer()

    def get_forecast(
        self,
        location: Location,
        hours_ahead: int = 48,
    ) -> NormalizedTimeseries:
        """Fetch forecast for location."""
        self._debug.add(f"provider: {self._provider.name}")
        self._debug.add(f"location: {location.latitude:.4f}N, {location.longitude:.4f}E")

        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)

        ts = self._provider.fetch_forecast(location, start=now, end=end)

        self._debug.add(f"forecast.points: {len(ts.data)}")
        self._debug.add(f"forecast.model: {ts.meta.model}")

        return ts
```

### 5.4 src/outputs/base.py (NEW)

```python
"""Output channel protocol."""
from typing import Protocol
from app.models import NormalizedTimeseries

class OutputChannel(Protocol):
    """Protocol for output channels."""

    @property
    def name(self) -> str:
        ...

    def send(self, subject: str, body: str) -> None:
        ...

class ConsoleOutput:
    """Console output channel."""

    @property
    def name(self) -> str:
        return "console"

    def send(self, subject: str, body: str) -> None:
        print(f"=== {subject} ===")
        print(body)
```

### 5.5 src/app/cli.py (REFACTORED)

```python
"""CLI entry point - thin layer."""
import argparse
import sys
from typing import Optional

from app.config import Settings
from app.debug import DebugBuffer
from providers.base import get_provider
from services.forecast import ForecastService
from outputs.console import ConsoleOutput
from outputs.email import EmailOutput

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gregor-zwanzig",
        description="Weather risk reports for outdoor activities"
    )
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--provider", choices=["geosphere"], default=None)
    parser.add_argument("--report", choices=["evening", "morning", "alert"])
    parser.add_argument("--channel", choices=["console", "email", "none"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--debug", choices=["info", "verbose"])
    return parser

def main(argv: Optional[list[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load settings (env + args override)
    settings = Settings(
        latitude=args.lat or Settings().latitude,
        longitude=args.lon or Settings().longitude,
        provider=args.provider or Settings().provider,
        # ... more overrides
    )

    # Setup
    debug = DebugBuffer()
    provider = get_provider(settings.provider)
    service = ForecastService(provider, debug)

    # Fetch data
    location = settings.get_location()
    forecast = service.get_forecast(location)

    # Format output
    body = format_report(forecast, settings.report_type)
    subject = f"GZ {settings.report_type.title()} Report"

    # Output
    if settings.channel == "console" or settings.dry_run:
        ConsoleOutput().send(subject, body)
    elif settings.channel == "email":
        EmailOutput(settings).send(subject, body)

    return 0
```

---

## 6. Implementierungs-Reihenfolge

1. **config.py** - Settings & Location
2. **providers/base.py** - Protocol & Factory
3. **providers/geosphere.py** - Anpassen an Protocol
4. **services/forecast.py** - ForecastService
5. **outputs/** - Console & Email Channel
6. **cli.py** - Refactoring
7. **Tests** aktualisieren

---

## 7. Abhaengigkeiten

| Package | Zweck | Optional |
|---------|-------|----------|
| pydantic-settings | Config mit ENV-Support | Nein |
| httpx | HTTP Client (bereits vorhanden) | Nein |

---

## 8. Offene Fragen

1. **pydantic-settings:** Soll ich es verwenden oder reicht dataclass + manuelles ENV-Loading?
2. **Async:** Soll die Architektur async-ready sein (httpx supports both)?
3. **Formatter:** Soll der Report-Formatter Teil dieser Iteration sein oder spaeter?

---

## Changelog

- 2025-12-27: Initial spec created
