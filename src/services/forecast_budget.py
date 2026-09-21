"""ForecastBudgetGate — Tagesbudget-Zaehler mit Prioritaetssteuerung.

Issue #1329, Scheibe C+, Teil 2. Datei-basierter Tageszaehler pro Provider,
Muster `ThrottleStore`/`AVAILABILITY_CACHE_PATH` (`openmeteo.py:258-274`):
Reload-Merge-Write unter `fcntl`-Sperre, Pfad automatisch prod/staging
getrennt ueber `app.loader.get_data_root()` (Tech-Lead-Entscheidung
2026-07-20: die Spec nannte faelschlich `_data_root()` -- der tatsaechliche
Funktionsname ist `get_data_root()`).

Issue #2387 (Scheibe S1 von #2150, Epic #2138): zusaetzlich ein Zaehler JE
NUTZER unter `data/users/<user_id>/diagnostics/forecast_budget.json`. Der
globale Topf bleibt der alleinige Kontoschutz gegenueber open-meteo; der
Nutzer-Topf entscheidet nur, WEN eine erreichte Schwelle trifft -- den
Vielverbraucher, nicht alle (ADR-0075).

Fail-open (Muster `openmeteo.py:_load_availability_cache`): JEDER
Lese-/Schreibfehler des Zaehlers blockiert NIEMALS einen Aufruf. Ein
kaputter Zaehler darf keinen Versand verhindern. Das gilt seit #2387 auch
je Nutzer: ein unlesbarer Nutzer-Topf gilt als "nicht ueberschritten".

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md (Teil 2, AC-5/AC-7)
SPEC: docs/specs/modules/forecast_budget_je_nutzer.md (#2387)
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from services.file_lock import LOCK_TIMEOUT_SECONDS, acquire_exclusive

logger = logging.getLogger("forecast_budget")

PROVIDER = "openmeteo"
_LOCK_SUFFIX = ".lock"
_FILENAME = "forecast_budget.json"


class ForecastBudgetGate:
    """`allow(priority)` ist eine reine, deterministische Funktion des
    Tageszaehlers -- kein adaptiver Rate-Limiter (ADR-0075)."""

    DAILY_BUDGET = 9000  # Sicherheitsmarge unter dem 10k-Limit
    POLLING_THRESHOLD = 0.80  # ab 80% Budget: polling abweisen
    BRIEFING_ONLY_THRESHOLD = 0.95  # ab 95%: nur noch user_briefing

    def __init__(self, user_id: Optional[str], data_root: Optional[Path] = None) -> None:
        """`user_id` ist PFLICHT-Parameter OHNE Default (Muster
        `ThrottleStore.__init__`, ADR-0003) -- ein Aufruf ohne Kennung
        bricht laut, statt still auf ein fremdes Konto zu buchen.

        `user_id=None` ist die EINZIGE zulaessige Ausnahme und muss vom
        Aufrufer ausdruecklich hingeschrieben werden: die bewusst
        nutzerfreie Provider-Schicht (`thunder_enrichment.py` ueber
        `providers/openmeteo.py`, ADR-0075 Punkt 4) bucht unattributiert in
        den globalen Topf. Sie legt KEINEN Nutzer-Topf an und traegt sich
        NICHT in die Menge der aktiven Nutzer ein -- im Unterschied zu einem
        Ersatzwert wie ``"default"`` entsteht damit keine Fehlzuordnung.

        Eine UNGUELTIGE Kennung (leerer String, Pfadtrenner) wirft dagegen
        ``ValueError`` aus dem Konstruktor -- wortgleich zu
        ``ThrottleStore.__init__`` (beide ueber ``loader.get_data_dir``).
        Bewusst kein fail-open an dieser Stelle: ein stilles Umdeuten auf
        "unattributiert" verloere die Zuordnung unbemerkt, waehrend ein
        leerer String immer ein Programmierfehler des Aufrufers ist, nie
        ein Datenzustand.
        """
        self._user_id = user_id
        if data_root is not None:
            root = Path(data_root)
            self._dir = root / "diagnostics"
            user_root: Optional[Path] = root / "users"
        else:
            from app.loader import get_data_root
            self._dir = get_data_root() / "diagnostics"
            user_root = None
        self._path = self._dir / _FILENAME

        self._user_dir: Optional[Path] = None
        self._user_path: Optional[Path] = None
        if user_id is not None:
            if user_root is not None:
                from app.loader import VALID_USER_ID_RE
                if not VALID_USER_ID_RE.match(user_id):
                    raise ValueError(f"invalid user_id: {user_id!r}")
                self._user_dir = user_root / user_id / "diagnostics"
            else:
                from app.loader import get_data_dir
                self._user_dir = get_data_dir(user_id) / "diagnostics"
            self._user_path = self._user_dir / _FILENAME

    # --- Public API -----------------------------------------------------

    def allow(self, priority: str, now: Optional[datetime] = None) -> bool:
        """Fail-open: jeder Lese-/Zaehlfehler -> True (nie blockieren).

        Dreistufig seit #2387 (ADR-0075 Punkt 2):

        * Stufe 0 -- globaler Anteil unter der Schwelle der Prioritaet:
          niemand wird gedrosselt (Bestandsverhalten).
        * Stufe 2 -- globaler Anteil >= 100%: JEDE Prioritaet ausser
          `user_briefing` wird gedrosselt, UNABHAENGIG vom fairen Anteil.
          Harter Kontoschutz, uebersteuert Stufe 1. Steht bewusst VOR
          Stufe 1: ein unlesbarer Nutzer-Topf darf den Kontoschutz nicht
          aufweichen.
        * Stufe 1 -- Schwelle erreicht, aber unter 100%: gedrosselt wird
          nur, wer mit seinem eigenen Tagesverbrauch UEBER seinem fairen
          Anteil (`DAILY_BUDGET / max(N, 1)`) liegt.

        Args:
            now: Optionale, injizierbare UTC-Uhr fuer deterministische Tests
                des Tageswechsels (Adversary-Fund F002). Ohne Angabe wird
                `datetime.now(timezone.utc)` verwendet -- NIE die lokale
                Wanduhr (`date.today()`), da der Zaehler sich am
                open-meteo-Kontingent orientiert (UTC-naher Reset).
        """
        if priority == "user_briefing":
            return True
        if priority == "polling":
            schwelle = self.POLLING_THRESHOLD
        elif priority == "alert_check":
            schwelle = self.BRIEFING_ONLY_THRESHOLD
        else:
            return True  # unbekannte Prioritaet -> nie drosseln (fail-open)
        try:
            ratio = self._read_usage_ratio(now)
        except Exception:
            return True  # kaputter/unlesbarer Zaehler blockiert nie
        if ratio < schwelle:
            return True  # Stufe 0
        if ratio >= 1.0:
            return False  # Stufe 2 -- harter Kontoschutz (AC-8)
        return not self._ueber_fairem_anteil(now)  # Stufe 1 (AC-1/AC-10)

    def record_call(self) -> None:
        """Zaehlt einen tatsaechlichen Upstream-Call (Cache-Miss, der den
        Provider erreicht hat) -- global UND, sofern die Instanz eine
        Kennung traegt, im eigenen Nutzer-Topf."""
        def _global(data: dict) -> None:
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + 1
            if self._user_id is not None and self._user_id not in data["active_users"]:
                # Diese Menge liefert N fuer den fairen Anteil, ohne bei
                # jedem allow() das Nutzerverzeichnis scannen zu muessen.
                data["active_users"].append(self._user_id)

        def _nutzer(data: dict) -> None:
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + 1

        self._safe_update(_global)
        self._safe_update_user(_nutzer)

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
        `status: "unavailable"` statt zu werfen.

        Die globale Ausgabe ist gegenueber #1329 UNVERAENDERT. Seit #2387
        kommen drei ADDITIVE Felder dazu (`user_calls_today`, `fair_share`,
        `active_users_count`) -- sie sind die einzige oeffentliche
        Lesequelle fuer den Nutzer-Topf-Zustand. Der Go-Leser
        (`forecast_budget_health.go:121-127`) liest die globale JSON-Datei
        direkt vom Dateisystem und ruft `snapshot()` nie auf; die neuen
        Felder erreichen `/api/scheduler/status` also strukturell nicht
        (ADR-0075 Punkt 5).
        """
        try:
            data = self._load_for_today()
            calls = data["calls"].get(PROVIDER, 0)
            ratio = calls / self.DAILY_BUDGET if self.DAILY_BUDGET else 0.0
            ergebnis = {
                "date": data["date"],
                "calls_today": calls,
                "daily_budget": self.DAILY_BUDGET,
                "usage_ratio": ratio,
                "cache_hits": data.get("cache_hits", 0),
                "cache_misses": data.get("cache_misses", 0),
                "status": "ok",
            }
            aktive = len(data["active_users"])
        except Exception:
            ergebnis = {
                "date": None,
                "calls_today": 0,
                "daily_budget": self.DAILY_BUDGET,
                "usage_ratio": 0.0,
                "cache_hits": 0,
                "cache_misses": 0,
                "status": "unavailable",
            }
            aktive = 0
        ergebnis["user_calls_today"] = self._user_calls_today()
        ergebnis["fair_share"] = self._fair_share_fuer(aktive)
        ergebnis["active_users_count"] = aktive
        return ergebnis

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

    def _fair_share_fuer(self, aktive: int) -> float:
        """Fairer Pro-Kopf-Anteil, zur LAUFZEIT aus `DAILY_BUDGET`
        abgeleitet. Lebt NEBEN den Bestandskonstanten, nie an ihrer Stelle
        (ADR-0075 Punkt 6): `TestForecastBudgetConstantsMatchPython`
        (`forecast_budget_health_test.go:256`) liest den Python-Quelltext
        zur Laufzeit und wird rot, sobald eine Konstante wandert."""
        return self.DAILY_BUDGET / max(aktive, 1)

    def _user_calls_today(self, now: Optional[datetime] = None) -> int:
        """Eigener Tagesverbrauch. Fail-open (E3/ADR-0075 Punkt 3): ein
        unlesbarer Topf oder ein Lesefehler gilt als 0."""
        if self._user_path is None:
            return 0
        try:
            return self._load_user_for_today(now)["calls"].get(PROVIDER, 0)
        except Exception as exc:
            logger.warning(
                "Nutzer-Budgettopf %s nicht lesbar (%s) -- Verbrauch gilt als "
                "0, es wird NICHT gedrosselt",
                self._user_path, exc,
            )
            return 0

    def _ueber_fairem_anteil(self, now: Optional[datetime] = None) -> bool:
        """Stufe 1: liegt DIESER Nutzer ueber seinem fairen Anteil?

        Eine unattributierte Instanz (`user_id=None`, Provider-Schicht)
        kann keinen Pro-Kopf-Anteil haben. Sie faellt bewusst auf das
        Bestandsverhalten zurueck -- also DROSSELN -- statt sich selbst zu
        befreien: ein Aufruf ohne Kennung darf nie mehr duerfen als ein
        Aufruf mit Kennung.
        """
        if self._user_path is None:
            return True
        try:
            aktive = len(self._load_for_today(now)["active_users"])
        except Exception:
            aktive = 0
        return self._user_calls_today(now) > self._fair_share_fuer(aktive)

    def _leerer_tag(self, today: str) -> dict:
        return {
            "date": today,
            "calls": {},
            "cache_hits": 0,
            "cache_misses": 0,
            "active_users": [],
        }

    def _load_for_today(self, now: Optional[datetime] = None) -> dict:
        """Tageswechsel: beim ersten Zugriff nach UTC-Datumswechsel gilt der
        Zaehler als zurueckgesetzt (kein Replace der Datei -- erst beim
        naechsten `_safe_update` wird sie tatsaechlich neu geschrieben).

        Der Reset erfasst seit #2387 ausdruecklich AUCH `active_users`
        (AC-5): bliebe die Menge stehen, truege N die Nutzer von gestern in
        den fairen Anteil von heute.
        """
        today = self._today_utc(now)
        if not self._path.exists():
            return self._leerer_tag(today)
        raw = json.loads(self._path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("forecast_budget.json: unerwartete Struktur")
        if raw.get("date") != today:
            return self._leerer_tag(today)
        calls = raw.get("calls")
        if not isinstance(calls, dict):
            calls = {}
        aktive = raw.get("active_users")
        if not isinstance(aktive, list):
            # Bestandsformat VOR #2387 kennt das Feld nicht -- der globale
            # Zaehlerstand bleibt unberuehrt, je Nutzer wird frisch
            # begonnen (Migrationsweg der Spec, AC-9).
            aktive = []
        return {
            "date": today,
            "calls": calls,
            "cache_hits": raw.get("cache_hits", 0),
            "cache_misses": raw.get("cache_misses", 0),
            "active_users": [u for u in aktive if isinstance(u, str)],
        }

    def _load_user_for_today(self, now: Optional[datetime] = None) -> dict:
        """Nutzer-Topf: schlanker als die globale Datei -- `cache_hits`/
        `cache_misses` werden fuer die Fairness-Berechnung nicht gebraucht.
        Derselbe UTC-Tagesschnitt wie global."""
        today = self._today_utc(now)
        if self._user_path is None or not self._user_path.exists():
            return {"date": today, "calls": {}}
        raw = json.loads(self._user_path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("forecast_budget.json (Nutzer-Topf): unerwartete Struktur")
        if raw.get("date") != today:
            return {"date": today, "calls": {}}
        calls = raw.get("calls")
        if not isinstance(calls, dict):
            calls = {}
        return {"date": today, "calls": calls}

    def _write(self, verzeichnis: Path, pfad: Path, data: dict) -> None:
        verzeichnis.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(verzeichnis), prefix=".forecast_budget_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(data))
            os.replace(tmp_name, pfad)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _safe_update(self, mutate: Callable[[dict], None]) -> None:
        """Reload-merge-write der GLOBALEN Datei unter Dateisperre."""
        self._update_datei(
            self._dir, self._path, self._load_for_today,
            lambda: self._leerer_tag(self._today_utc()), mutate,
        )

    def _safe_update_user(self, mutate: Callable[[dict], None]) -> None:
        """Reload-merge-write des NUTZER-Topfs unter EIGENEM Sidecar-Lock
        (weniger Contention als ein gemeinsames Lock, Muster
        `throttle_store.py:197-245`). Ohne Kennung passiert nichts."""
        if self._user_dir is None or self._user_path is None:
            return
        self._update_datei(
            self._user_dir, self._user_path, self._load_user_for_today,
            lambda: {"date": self._today_utc(), "calls": {}}, mutate,
        )

    def _update_datei(
        self,
        verzeichnis: Path,
        pfad: Path,
        laden: Callable[[], dict],
        leerbau: Callable[[], dict],
        mutate: Callable[[dict], None],
    ) -> None:
        """Fail-open: JEDER Fehler (Lock-Timeout, IO, kaputtes JSON) wird
        geschluckt -- ein Zaehl-Defekt darf nie einen Versand verhindern.
        Ein Sperren-Timeout wirft dabei NICHT (`acquire_exclusive`, #1448
        S2) -- die WARNING wird explizit VOR dem `return` geloggt, damit
        sie nicht von diesem `except Exception: pass` erfasst werden kann."""
        try:
            verzeichnis.mkdir(parents=True, exist_ok=True)
            lock_path = str(pfad) + _LOCK_SUFFIX
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                start = time.monotonic()
                if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
                    # F003 (Adversary #1448 S2): tatsaechlich gewartete Zeit
                    # loggen, nicht die konfigurierte Zeitgrenze.
                    elapsed = time.monotonic() - start
                    logger.warning(
                        "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                        "Schreibvorgang uebersprungen",
                        lock_path, elapsed,
                    )
                    return
                try:
                    try:
                        data = laden()
                    except Exception:
                        data = leerbau()
                    mutate(data)
                    self._write(verzeichnis, pfad, data)
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        except Exception:
            pass
