"""ForecastBudgetGate — Tagesbudget-Zaehler mit Prioritaetssteuerung.

Issue #1329, Scheibe C+, Teil 2. Datei-basierter Tageszaehler pro Provider,
Muster `ThrottleStore`/`AVAILABILITY_CACHE_PATH` (`openmeteo.py:258-274`):
Reload-Merge-Write unter `fcntl`-Sperre, Pfad automatisch prod/staging
getrennt ueber `app.loader.get_data_root()` (Tech-Lead-Entscheidung
2026-07-20: die Spec nannte faelschlich `_data_root()` -- der tatsaechliche
Funktionsname ist `get_data_root()`).

Fail-open (Muster `openmeteo.py:_load_availability_cache`): JEDER
Lese-/Schreibfehler des Zaehlers blockiert NIEMALS einen Aufruf. Ein
kaputter Zaehler darf keinen Versand verhindern.

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md (Teil 2, AC-5/AC-7)
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

PROVIDER = "openmeteo"
_LOCK_SUFFIX = ".lock"


class ForecastBudgetGate:
    """`allow(priority)` ist eine reine, deterministische Funktion des
    Tageszaehlers -- kein adaptiver Rate-Limiter (ADR-0032)."""

    DAILY_BUDGET = 9000  # Sicherheitsmarge unter dem 10k-Limit
    POLLING_THRESHOLD = 0.80  # ab 80% Budget: polling abweisen
    BRIEFING_ONLY_THRESHOLD = 0.95  # ab 95%: nur noch user_briefing

    def __init__(self, data_root: Optional[Path] = None) -> None:
        if data_root is not None:
            self._dir = Path(data_root) / "diagnostics"
        else:
            from app.loader import get_data_root
            self._dir = get_data_root() / "diagnostics"
        self._path = self._dir / "forecast_budget.json"

    # --- Public API -----------------------------------------------------

    def allow(self, priority: str, now: Optional[datetime] = None) -> bool:
        """Fail-open: jeder Lese-/Zaehlfehler -> True (nie blockieren).

        Args:
            now: Optionale, injizierbare UTC-Uhr fuer deterministische Tests
                des Tageswechsels (Adversary-Fund F002). Ohne Angabe wird
                `datetime.now(timezone.utc)` verwendet -- NIE die lokale
                Wanduhr (`date.today()`), da der Zaehler sich am
                open-meteo-Kontingent orientiert (UTC-naher Reset).
        """
        if priority == "user_briefing":
            return True
        try:
            ratio = self._read_usage_ratio(now)
        except Exception:
            return True  # kaputter/unlesbarer Zaehler blockiert nie
        if priority == "polling":
            return ratio < self.POLLING_THRESHOLD
        if priority == "alert_check":
            return ratio < self.BRIEFING_ONLY_THRESHOLD
        return True  # unbekannte Prioritaet -> nie drosseln (fail-open)

    def record_call(self) -> None:
        """Zaehlt einen tatsaechlichen Upstream-Call (Cache-Miss, der den
        Provider erreicht hat)."""
        def _op(data: dict) -> None:
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + 1
        self._safe_update(_op)

    def record_cache_hit(self) -> None:
        def _op(data: dict) -> None:
            data["cache_hits"] = data.get("cache_hits", 0) + 1
        self._safe_update(_op)

    def record_cache_miss(self) -> None:
        def _op(data: dict) -> None:
            data["cache_misses"] = data.get("cache_misses", 0) + 1
        self._safe_update(_op)

    def snapshot(self) -> dict:
        """Fuer Observability-Export (z.B. Go-Status-Endpunkt, AC-8 --
        nicht Teil dieser Scheibe). Fail-open: liefert Nullen mit
        `status: "unavailable"` statt zu werfen."""
        try:
            data = self._load_for_today()
            calls = data["calls"].get(PROVIDER, 0)
            ratio = calls / self.DAILY_BUDGET if self.DAILY_BUDGET else 0.0
            return {
                "date": data["date"],
                "calls_today": calls,
                "daily_budget": self.DAILY_BUDGET,
                "usage_ratio": ratio,
                "cache_hits": data.get("cache_hits", 0),
                "cache_misses": data.get("cache_misses", 0),
                "status": "ok",
            }
        except Exception:
            return {
                "date": None,
                "calls_today": 0,
                "daily_budget": self.DAILY_BUDGET,
                "usage_ratio": 0.0,
                "cache_hits": 0,
                "cache_misses": 0,
                "status": "unavailable",
            }

    # --- Intern -----------------------------------------------------------

    @staticmethod
    def _today_utc(now: Optional[datetime] = None) -> str:
        """UTC-Tagesgrenze (Adversary-Fund F002): NIE `date.today()`
        (lokale Wanduhr) -- der Zaehler ist ein globaler Tageszaehler, der
        sich am open-meteo-Kontingent orientiert, dessen Reset-Zeitpunkt
        UTC-nah ist, nicht an der Server-Lokalzeit gebunden."""
        moment = now if now is not None else datetime.now(timezone.utc)
        return moment.astimezone(timezone.utc).date().isoformat()

    def _read_usage_ratio(self, now: Optional[datetime] = None) -> float:
        data = self._load_for_today(now)
        calls = data["calls"].get(PROVIDER, 0)
        if self.DAILY_BUDGET <= 0:
            return 0.0
        return calls / self.DAILY_BUDGET

    def _load_for_today(self, now: Optional[datetime] = None) -> dict:
        """Tageswechsel: beim ersten Zugriff nach UTC-Datumswechsel gilt der
        Zaehler als zurueckgesetzt (kein Replace der Datei -- erst beim
        naechsten `_safe_update` wird sie tatsaechlich neu geschrieben)."""
        today = self._today_utc(now)
        if not self._path.exists():
            return {"date": today, "calls": {}, "cache_hits": 0, "cache_misses": 0}
        raw = json.loads(self._path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("forecast_budget.json: unerwartete Struktur")
        if raw.get("date") != today:
            return {"date": today, "calls": {}, "cache_hits": 0, "cache_misses": 0}
        calls = raw.get("calls")
        if not isinstance(calls, dict):
            calls = {}
        return {
            "date": today,
            "calls": calls,
            "cache_hits": raw.get("cache_hits", 0),
            "cache_misses": raw.get("cache_misses", 0),
        }

    def _write(self, data: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._dir), prefix=".forecast_budget_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(data))
            os.replace(tmp_name, self._path)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _safe_update(self, mutate: Callable[[dict], None]) -> None:
        """Reload-merge-write unter Dateisperre (Muster `ThrottleStore`).
        Fail-open: JEDER Fehler (Lock, IO, kaputtes JSON) wird geschluckt --
        ein Zaehl-Defekt darf nie einen Versand verhindern."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            lock_path = str(self._path) + _LOCK_SUFFIX
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    try:
                        data = self._load_for_today()
                    except Exception:
                        data = {
                            "date": self._today_utc(),
                            "calls": {},
                            "cache_hits": 0,
                            "cache_misses": 0,
                        }
                    mutate(data)
                    self._write(data)
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        except Exception:
            pass
