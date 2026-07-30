"""MeteoAlarmBudgetGate — Tagesbudget-Schranke fuer MeteoAlarm-Index-Abrufe.

Issue #1397 (Tageskontingent-Fund, S1c-Nachbesserung, Produktion 2026-07-27
10:37 UTC): MeteoAlarm limitiert nicht nur kurzzeitig (~1 Anfrage/4s, s.
``warn_egress.RateLimitRetryPolicy``), sondern zusaetzlich mit einem
TAGESKONTINGENT (``x-ratelimit-reset`` ~86400s in der Zukunft, Body "Daily
rate limit exceeded"). Ein Tageskontingent, das wir blind ausschoepfen, ist
dieselbe Falle wie in #1329 (open-meteo) -- diese Schranke verhindert, dass
WIR es selbst leerfeuern, bevor das echte Limit gemessen ist.

Muster: ``services.forecast_budget.ForecastBudgetGate`` (Reload-Merge-Write
unter ``fcntl``-Sperre, ``data/diagnostics/<name>.json``, fail-open bei
JEDEM Lese-/Schreibfehler -- ein kaputter Zaehler darf nie einen Abruf
blockieren). Anders als dort KEINE Prioritaetsstufen: ein einfaches An/Aus
-- erschoepft heisst KEIN Index-Abruf mehr (der Index gilt dann als
unvollstaendig, s. ``meteoalarm._get_cached_index``).

``DEFAULT_DAILY_BUDGET`` ist der von der PO belegte GEMESSENE Wert (Issue
#1397, Entscheidung 2026-07-30: reales Tageskontingent ~160 Abrufe/
rollierendem 24h-Fenster, Default konservativ auf 100 gesetzt statt des
frueheren Schaetzwerts 200) -- ueber die Umgebungsvariable
``GZ_METEOALARM_DAILY_BUDGET`` OHNE Deploy aenderbar, falls sich der reale
Wert weiter praezisiert.

Adversary-Fund (Runde 2, 2026-07-27): das Tageskontingent laeuft NICHT auf
einer UTC-Kalendertagsgrenze, sondern in einem ROLLIERENDEN 24h-Fenster ab
dem letzten beobachteten Reset -- belegt, weil ein um 10:37 UTC gemeldeter
429 einen ``x-ratelimit-reset`` ~86.399s (10:37 des FOLGETAGS) traegt, nicht
~48.180s (bis UTC-Mitternacht). Ein reiner Kalendertagszaehler wuerde also
um Mitternacht neu oeffnen, waehrend die echte Sperre noch >10h weiterlaeuft
-- und in dieser Luecke bei jedem 30-Minuten-Slot einen aussichtslosen
Abruf feuern (genau die Selbstverbrennung, die diese Schranke verhindern
soll). Fix: ``record_observed_reset()`` haelt den ECHTEN, von der API
gemeldeten Reset-Zeitpunkt fest; ``allow()`` bleibt bis dahin HART
gesperrt, unabhaengig vom eigenen Zaehlerstand. Die UTC-Kalendertagsgrenze
bleibt NUR Fallback, solange noch nie ein echter Reset beobachtet wurde.

WICHTIGE UNTERSCHEIDUNG: der eigene Zaehler (``calls``) ist eine
SELBSTBESCHRAENKUNG (unser Schaetzwert, per ENV grob nachziehbar) -- der
beobachtete Reset-Zeitpunkt (``observed_reset_ts``) ist die EINZIGE echte
Information ueber das Kontingent der Gegenseite. Beide duerfen nicht
verwechselt werden: der Zaehler kann falsch liegen (zu niedrig ODER zu
hoch geschaetzt), der beobachtete Reset ist eine harte, von der API selbst
gemeldete Tatsache und hat IMMER Vorrang.

SPEC: docs/specs/modules/warn_service_consumption.md
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

_LOCK_SUFFIX = ".lock"


class MeteoAlarmBudgetGate:
    """Ein einfaches Tagesbudget UEBER ALLE Laender (AT+IT gemeinsam) --
    kein pro-Land-Zaehler, das Tageskontingent ist ein Konto der API."""

    DEFAULT_DAILY_BUDGET = 100  # PO-belegter, gemessener Wert, s. Modul-Docstring
    # Deckel gegen einen absurden/manipulierten x-ratelimit-reset -- ein
    # einzelner falscher Header darf den Dienst nicht tagelang lahmlegen.
    # 48h statt 24h, damit der belegte reale Wert (86.399s ~ 24h) sicher
    # NICHT selbst schon gekappt wird.
    MAX_RESET_HORIZON_SECONDS = 48 * 3600.0

    def __init__(self, data_root: Optional[Path] = None) -> None:
        if data_root is not None:
            self._dir = Path(data_root) / "diagnostics"
        else:
            from app.loader import get_data_root
            self._dir = get_data_root() / "diagnostics"
        self._path = self._dir / "meteoalarm_budget.json"

    # --- Public API -----------------------------------------------------

    @property
    def daily_budget(self) -> int:
        """``GZ_METEOALARM_DAILY_BUDGET`` (positive Ganzzahl) > Default --
        ohne Deploy aenderbar, sobald das echte Limit bekannt ist."""
        raw = os.environ.get("GZ_METEOALARM_DAILY_BUDGET")
        if raw:
            try:
                value = int(raw)
            except ValueError:
                value = 0
            if value > 0:
                return value
        return self.DEFAULT_DAILY_BUDGET

    def allow(self, now: Optional[datetime] = None) -> bool:
        """Fail-open: jeder Lese-/Zaehlfehler -> ``True`` (nie blockieren).

        Ist ein ECHTER Reset-Zeitpunkt bekannt (``record_observed_reset()``
        wurde je aufgerufen) UND liegt ``now`` noch davor, bleibt die
        Schranke HART geschlossen -- unabhaengig vom eigenen Zaehlerstand
        (der zu diesem Zeitpunkt durchaus weit unter dem Budget liegen
        kann, s. Modul-Docstring)."""
        try:
            state = self._load_state(now)
        except Exception:
            return True
        reset_ts = state.get("observed_reset_ts")
        if reset_ts is not None and self._now_ts(now) < reset_ts:
            return False
        return state["calls"] < self.daily_budget

    def record_call(self) -> None:
        """Zaehlt einen tatsaechlichen Index-Seiten-Abruf (Cache-Miss, der
        den Netzwerk-Call tatsaechlich ausloest)."""
        def _op(data: dict) -> None:
            data["calls"] = data.get("calls", 0) + 1
        self._safe_update(_op)

    def record_observed_reset(self, reset_ts: float, now: Optional[datetime] = None) -> None:
        """Persistiert den ECHTEN, von der API gemeldeten Reset-Zeitpunkt
        (Unix-Sekunden, aus ``x-ratelimit-reset`` bei einem erkannten
        Tageskontingent-429 -- s. ``meteoalarm._capture_reset``), gedeckelt
        durch ``MAX_RESET_HORIZON_SECONDS``. ``allow()`` bleibt ab sofort
        bis zu diesem Zeitpunkt gesperrt, UNABHAENGIG vom Zaehlerstand."""
        capped = min(reset_ts, self._now_ts(now) + self.MAX_RESET_HORIZON_SECONDS)
        def _op(data: dict) -> None:
            data["observed_reset_ts"] = capped
        self._safe_update(_op)

    def snapshot(self) -> dict:
        """Fuer Observability. Fail-open: Nullen mit ``status:
        "unavailable"`` statt zu werfen."""
        try:
            data = self._load_state()
            calls = data["calls"]
            budget = self.daily_budget
            return {
                "date": data["date"],
                "calls_today": calls,
                "daily_budget": budget,
                "usage_ratio": calls / budget if budget else 0.0,
                "observed_reset_ts": data.get("observed_reset_ts"),
                "status": "ok",
            }
        except Exception:
            return {
                "date": None,
                "calls_today": 0,
                "daily_budget": self.daily_budget,
                "usage_ratio": 0.0,
                "observed_reset_ts": None,
                "status": "unavailable",
            }

    # --- Intern (Muster ForecastBudgetGate) ------------------------------

    @staticmethod
    def _now_ts(now: Optional[datetime] = None) -> float:
        moment = now if now is not None else datetime.now(timezone.utc)
        return moment.astimezone(timezone.utc).timestamp()

    @staticmethod
    def _today_utc(now: Optional[datetime] = None) -> str:
        """UTC-Tagesgrenze, NIE lokale Wanduhr (Muster ForecastBudgetGate
        Adversary-Fund F002). NUR Fallback-Bezugspunkt, solange noch nie ein
        echter Reset beobachtet wurde -- s. Modul-Docstring (rollierendes
        24h-Fenster, keine Kalendertagsgrenze)."""
        moment = now if now is not None else datetime.now(timezone.utc)
        return moment.astimezone(timezone.utc).date().isoformat()

    def _load_state(self, now: Optional[datetime] = None) -> dict:
        """Liefert ``{"date", "calls", "observed_reset_ts"}``.

        Ist ein beobachteter Reset bekannt UND bereits vorueber, rollt das
        Fenster: Zaehler auf 0, ``observed_reset_ts`` geloescht (der
        naechste bekannte Reset kommt erst mit dem naechsten beobachteten
        429 -- bis dahin gilt wieder der UTC-Tagesgrenze-Fallback). Ist er
        bekannt und noch NICHT vorueber, bleibt der Zaehlerstand erhalten
        (``allow()`` sperrt ohnehin unabhaengig davon hart)."""
        today = self._today_utc(now)
        if not self._path.exists():
            return {"date": today, "calls": 0, "observed_reset_ts": None}
        raw = json.loads(self._path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("meteoalarm_budget.json: unerwartete Struktur")

        reset_ts = raw.get("observed_reset_ts")
        if not isinstance(reset_ts, (int, float)):
            reset_ts = None

        if reset_ts is not None:
            if self._now_ts(now) >= reset_ts:
                return {"date": today, "calls": 0, "observed_reset_ts": None}
            calls = raw.get("calls", 0)
            if not isinstance(calls, int):
                calls = 0
            return {"date": raw.get("date"), "calls": calls, "observed_reset_ts": reset_ts}

        # Kein Reset je beobachtet -> Fallback: UTC-Kalendertagsgrenze.
        if raw.get("date") != today:
            return {"date": today, "calls": 0, "observed_reset_ts": None}
        calls = raw.get("calls", 0)
        if not isinstance(calls, int):
            calls = 0
        return {"date": today, "calls": calls, "observed_reset_ts": None}

    def _write(self, data: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._dir), prefix=".meteoalarm_budget_", suffix=".tmp"
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
        """Reload-merge-write unter Dateisperre. Fail-open: JEDER Fehler
        (Lock, IO, kaputtes JSON) wird geschluckt -- ein Zaehl-Defekt darf
        nie einen Abruf verhindern."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            lock_path = str(self._path) + _LOCK_SUFFIX
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    try:
                        data = self._load_state()
                    except Exception:
                        data = {"date": self._today_utc(), "calls": 0, "observed_reset_ts": None}
                    mutate(data)
                    self._write(data)
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        except Exception:
            pass
