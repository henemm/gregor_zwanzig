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

Issue #2961 Welle 2 (ADR-0117): eigene Prioritaet ``user_interactive`` fuer
alles, was ein Nutzer beliebig oft von Hand ausloest (Vergleich,
Etappenwetter, Vorschauen). Sie bucht nie ueber ``INTERACTIVE_THRESHOLD`` der
Tagesmenge (Reserve fuer Zeitplan-Briefings und Alarme) und je Nutzer nie
ueber ``INTERACTIVE_USER_LIMIT``. Nachtrag: ``user_manual`` fuer Handversand
und Antwort-Befehle (global bis ``MANUAL_THRESHOLD``, je Nutzer
``MANUAL_USER_LIMIT``, Vorab-Buchung der ganzen Schaetzung). Beide Klassen
werden global und je Nutzer getrennt gefuehrt und zaehlen nicht in die
Fairness der uebrigen Prioritaeten.
SPEC: docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md
"""
from __future__ import annotations

import contextvars
import fcntl
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional

from services.file_lock import (
    LOCK_TIMEOUT_SECONDS, acquire_exclusive, open_lock_file, share_state_file,
)

logger = logging.getLogger("forecast_budget")

PROVIDER = "openmeteo"
_LOCK_SUFFIX = ".lock"
_FILENAME = "forecast_budget.json"

# Issue #1539 S1b: Buchungen, die fail-open verloren gehen (Sperr-Timeout, IO-Fehler),
# werden gezaehlt und laut geloggt statt still verschluckt (Muster
# ``alert_log_lost_entries``, nur im Prozess, kein JSON-Feld -- Go-Kopplung).
forecast_budget_lost_bookings = 0
_lost_lock = threading.Lock()


def _count_lost_booking() -> None:
    global forecast_budget_lost_bookings
    with _lost_lock:
        forecast_budget_lost_bookings += 1


# --- Interaktiver und manueller Kontext (ADR-0117) ---------------------------

INTERACTIVE = "user_interactive"
#: ADR-0117 Nachtrag (#2961 Fix-Runde): alles, was ein Nutzer von Hand ausloest
#: UND versendet (Handversand, Antwort-Befehle aller Kanaele).
MANUAL = "user_manual"


class InteraktivStatus:
    """Zustand EINER markierten Anfrage (interaktiv oder manuell). Wird ueber
    kopierte Kontexte in Arbeiter-Threads geteilt (gleiches Objekt), daher mit
    eigener Sperre.

    ``gedrosselt`` zaehlt Segment-Abrufe, die das Kontingent abgelehnt hat
    (``melde_drosselung``). Nur fuer ``user_manual``: ``schaetzung`` ist die
    Obergrenze der Einheiten des ganzen Versands; sie wird beim ERSTEN Abruf
    auf einmal gebucht (``guthaben``), der Rest beim Verlassen erstattet.
    Passt sie nicht mehr ins Kontingent, ist der ganze Versand ``abgelehnt``
    -- danach wird nichts mehr abgerufen (keine Teil-Briefings)."""

    def __init__(self, prioritaet: str = INTERACTIVE, user_id: Optional[str] = None,
                 schaetzung: int = 0) -> None:
        self._lock = threading.Lock()
        self.gedrosselt = 0
        self.prioritaet = prioritaet
        self.user_id = user_id
        self.schaetzung = max(int(schaetzung), 0)
        self.guthaben = 0
        self.vorausgebucht = False
        self.abgelehnt = False

    def vermerke(self) -> None:
        with self._lock:
            self.gedrosselt += 1
            if self.prioritaet == MANUAL:
                self.abgelehnt = True


_INTERAKTIV: contextvars.ContextVar[Optional[InteraktivStatus]] = contextvars.ContextVar(
    "forecast_budget_interaktiv", default=None,
)


@contextmanager
def interaktiver_abruf(user_id: Optional[str] = None) -> Iterator[InteraktivStatus]:
    """Markiert alle Wetterabrufe innerhalb des Blocks als interaktiv: der
    Segment-Weg (und die Anreicherung, sofern ``user_id`` bekannt) bucht dann
    ``user_interactive`` statt der Prioritaet des Aufrufers. Arbeiter-Threads
    erben die Markierung nur ueber ``contextvars.copy_context()``
    (``parallel_fetch``, ``comparison_parallel``, ``stage_weather``)."""
    status = InteraktivStatus(INTERACTIVE, user_id)
    token = _INTERAKTIV.set(status)
    try:
        yield status
    finally:
        _INTERAKTIV.reset(token)


@contextmanager
def manueller_abruf(user_id: str, schaetzung: int) -> Iterator[InteraktivStatus]:
    """Markiert einen Handversand bzw. Antwort-Befehl (``user_manual``).
    ``schaetzung`` = Obergrenze der Einheiten (``manuelles_kontingent``);
    nicht verbrauchtes Vorab-Guthaben (Cache-Treffer) wird beim Verlassen
    erstattet."""
    status = InteraktivStatus(MANUAL, user_id, schaetzung)
    token = _INTERAKTIV.set(status)
    try:
        yield status
    finally:
        _INTERAKTIV.reset(token)
        with status._lock:
            rest, status.guthaben = status.guthaben, 0
        if rest > 0:
            ForecastBudgetGate(user_id).erstatte(MANUAL, rest)


def wirksame_prioritaet(priority: str) -> str:
    """Im markierten Kontext bucht jeder Segment-Abruf mit der Prioritaet des
    Kontexts, sonst bleibt die Prioritaet des Aufrufers."""
    status = _INTERAKTIV.get()
    return status.prioritaet if status is not None else priority


def kontext_zurechnung(priority: str, user_id: Optional[str]) -> tuple[str, Optional[str]]:
    """Zurechnung fuer die Anreicherung (Radar/Gewitter, F3): im markierten
    Kontext zaehlt ein Abruf beim ausloesenden Nutzer mit dessen Prioritaet;
    ausserhalb (oder ohne bekannte Kennung) bleibt alles wie bisher."""
    status = _INTERAKTIV.get()
    if status is None:
        return priority, user_id
    nutzer = user_id or status.user_id
    if nutzer is None:
        return priority, user_id
    return status.prioritaet, nutzer


def melde_drosselung() -> None:
    """Segment-Weg: ein Abruf wurde vom Kontingent abgelehnt."""
    status = _INTERAKTIV.get()
    if status is not None:
        status.vermerke()


def manuell_abgelehnt() -> bool:
    """True, wenn der laufende Handversand/Befehl am Kontingent gescheitert ist
    -- der Versand muss dann vor jeder Zustellung abbrechen."""
    status = _INTERAKTIV.get()
    return status is not None and status.prioritaet == MANUAL and status.abgelehnt


def sekunden_bis_utc_mitternacht(jetzt: Optional[datetime] = None) -> int:
    """Wartezeit bis zum Zaehler-Reset an der UTC-Tagesgrenze, aufgerundet und
    mindestens 1 (Wert fuer ``Retry-After``)."""
    import math
    from datetime import timedelta

    jetzt = jetzt or datetime.now(timezone.utc)
    naechste = (jetzt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int(math.ceil((naechste - jetzt).total_seconds())))


def kennung_maskiert(user_id: str) -> str:
    """Kennung fuer Logzeilen: zwei Zeichen plus kurzer Hash (korrelierbar,
    nicht umkehrbar)."""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8]
    return f"{user_id[:2]}***{digest}"


#: Klasse -> (globaler Zaehler, Zaehler im Nutzer-Topf).
_KLASSEN = {
    INTERACTIVE: ("interactive_calls", "interactive"),
    MANUAL: ("manual_calls", "manual"),
}


class ForecastBudgetGate:
    """`allow(priority)` ist eine reine, deterministische Funktion des
    Tageszaehlers -- kein adaptiver Rate-Limiter (ADR-0075)."""

    DAILY_BUDGET = 9000  # Sicherheitsmarge unter dem 10k-Limit
    POLLING_THRESHOLD = 0.80  # ab 80% Budget: polling abweisen
    BRIEFING_ONLY_THRESHOLD = 0.95  # ab 95%: nur noch user_briefing
    # ADR-0117: interaktive Abrufe insgesamt hoechstens bis 70 % der Tagesmenge
    # (10 Punkte unter der Polling-Schwelle), je Nutzer fest hoechstens 1500
    # Einheiten (Nachtrag: kein Teilen durch aktive Nutzer, Herleitung in der Spec).
    INTERACTIVE_THRESHOLD = 0.70
    INTERACTIVE_USER_LIMIT = 1500
    INTERACTIVE_WARN_SHARE = 0.5
    # ADR-0117 Nachtrag: Handversand und Antwort-Befehle (user_manual) global
    # hoechstens bis 90 % (Alarme erst ab 95 % gedrosselt), je Nutzer 1500.
    MANUAL_THRESHOLD = 0.90
    MANUAL_USER_LIMIT = 1500

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
                from app.loader import InvalidUserIdError, is_valid_user_id
                if not is_valid_user_id(user_id):
                    raise InvalidUserIdError("invalid user_id")  # #2163: Kennung nie im Text
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
        if priority in _KLASSEN:
            try:
                return self._klasse_erlaubt(priority, self._load_for_today(now), 1, now)
            except Exception:
                return True  # fail-open wie alle Prioritaeten
        schwelle = self._schwelle_fuer(priority)
        if schwelle is None:
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

    def reserve(
        self, priority: str, units: int = 1, now: Optional[datetime] = None
    ) -> bool:
        """Atomares ``allow()`` + ``record_call()`` (Issue #1539 S1b).

        Entscheidung und Buchung im GLOBALEN Topf laufen in EINER Read-Modify-
        Write-Sequenz unter der Dateisperre -- N parallele Aufrufer bei Restbudget
        M bekommen genau M-mal ``True``. Danach wird der Nutzer-Topf in eigener,
        NICHT verschachtelter Sperre gebucht (feste Reihenfolge global -> Nutzer,
        nie beide gehalten). Fail-open: kann die globale Datei nicht
        aktualisiert werden, gilt ``True`` und der Verlustzaehler steigt.
        ``user_briefing`` und unbekannte Prioritaeten werden nie gedrosselt,
        aber gebucht. Bei Ablehnung wird nichts gebucht.

        ``user_interactive`` und ``user_manual`` (ADR-0117) entscheiden ueber
        eigene Grenzen, siehe ``_reserve_klasse``/``_reserve_manuell``.
        ``units <= 0`` ist ein Programmfehler (ValueError): eine Null- oder
        Minusbuchung koennte Zaehler senken."""
        if not isinstance(units, int) or units <= 0:
            raise ValueError("units muss eine positive ganze Zahl sein")
        if priority == MANUAL:
            return self._reserve_manuell(units, now)
        if priority == INTERACTIVE:
            return self._reserve_klasse(INTERACTIVE, units, now)
        schwelle = self._schwelle_fuer(priority)
        entscheidung: list = []  # leer = nicht entschieden (Update fehlgeschlagen)

        def _global(data: dict) -> None:
            erlaubt = schwelle is None or (
                self._erlaubt_laut_daten(data, schwelle, now)
                # Mehrere Einheiten duerfen das Tageslimit nicht ueberbuchen.
                and data["calls"].get(PROVIDER, 0) + units <= self.DAILY_BUDGET
            )
            entscheidung.append(erlaubt)
            if not erlaubt:
                return
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + units
            if self._user_id is not None and self._user_id not in data["active_users"]:
                data["active_users"].append(self._user_id)

        def _nutzer(data: dict) -> None:
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + units

        self._safe_update(_global, now)
        if entscheidung and entscheidung[0] is False:
            return False
        self._safe_update_user(_nutzer, now)
        return True

    def _reserve_manuell(self, units: int, now: Optional[datetime]) -> bool:
        """``user_manual``: im eigenen manuellen Kontext wird beim ersten Abruf
        die ganze Schaetzung auf einmal gebucht; danach zehren die Abrufe vom
        Guthaben. Passt die Schaetzung nicht mehr, ist der Versand abgelehnt,
        bevor irgendetwas abgerufen wurde, und bleibt es."""
        status = _INTERAKTIV.get()
        if (status is None or status.prioritaet != MANUAL
                or status.user_id != self._user_id or self._user_id is None):
            return self._reserve_klasse(MANUAL, units, now)
        with status._lock:
            if status.abgelehnt:
                return False
            if not status.vorausgebucht:
                status.vorausgebucht = True
                vorab = max(status.schaetzung, units)
                if not self._reserve_klasse(MANUAL, vorab, now):
                    status.abgelehnt = True
                    return False
                status.guthaben = vorab
            if status.guthaben >= units:
                status.guthaben -= units
                return True
        # Schaetzung ueberschritten: einzeln nachbuchen (Segment-Weg meldet
        # eine Ablehnung ueber melde_drosselung, der Versand bricht dann ab).
        return self._reserve_klasse(MANUAL, units, now)

    def erstatte(self, klasse: str, units: int) -> None:
        """Nicht verbrauchtes Vorab-Guthaben zurueckbuchen (global und je
        Nutzer, nie unter 0). Fail-open wie jede Buchung."""
        if klasse not in _KLASSEN or units <= 0:
            return
        g_topf, n_topf = _KLASSEN[klasse][0], _KLASSEN[klasse][1]

        def _minus(data: dict, topf: str) -> None:
            for name in ("calls", topf):
                zaehler = data.setdefault(name, {})
                zaehler[PROVIDER] = max(zaehler.get(PROVIDER, 0) - units, 0)

        self._safe_update(lambda d: _minus(d, g_topf))
        self._safe_update_user(lambda d: _minus(d, n_topf))

    def _reserve_klasse(self, klasse: str, units: int, now: Optional[datetime]) -> bool:
        """Buchung einer Klasse mit eigener globaler Obergrenze und eigener
        Grenze je Nutzer. Entschieden wird unter der globalen Sperre; der
        Nutzer-Topf wird dort nur gelesen (Reihenfolge global -> Nutzer wie in
        ``reserve``). Eine Ablehnung bucht nichts."""
        g_topf, n_topf = _KLASSEN[klasse][0], _KLASSEN[klasse][1]
        entscheidung: list = []
        gesamt_klasse: list = []

        def _global(data: dict) -> None:
            erlaubt = self._klasse_erlaubt(klasse, data, units, now)
            entscheidung.append(erlaubt)
            if not erlaubt:
                return
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + units
            topf = data.setdefault(g_topf, {})
            topf[PROVIDER] = topf.get(PROVIDER, 0) + units
            gesamt_klasse.append(topf[PROVIDER])
            if self._user_id is not None and self._user_id not in data["active_users"]:
                data["active_users"].append(self._user_id)

        warnung: list = []

        def _nutzer(data: dict) -> None:
            data["calls"][PROVIDER] = data["calls"].get(PROVIDER, 0) + units
            eigen = data.setdefault(n_topf, {})
            eigen[PROVIDER] = eigen.get(PROVIDER, 0) + units
            if (klasse == INTERACTIVE and gesamt_klasse
                    and not data.get("interactive_warned")
                    and self._ueber_warnschwelle(eigen[PROVIDER], gesamt_klasse[0])):
                data["interactive_warned"] = True
                warnung.append((eigen[PROVIDER], gesamt_klasse[0]))

        self._safe_update(_global, now)
        if entscheidung and entscheidung[0] is False:
            return False
        self._safe_update_user(_nutzer, now)
        if warnung and self._user_id is not None:
            logger.warning(
                "Nutzer %s stellt %d von %d interaktiven Abrufen heute (mehr als %d %%)",  # i18n-log
                kennung_maskiert(self._user_id), warnung[0][0], warnung[0][1],
                int(self.INTERACTIVE_WARN_SHARE * 100),
            )
        return True

    def _ueber_warnschwelle(self, eigen: int, gesamt: int) -> bool:
        """Mehr als die Haelfte des interaktiven Tagesverbrauchs -- erst ab
        einem Gesamtverbrauch in Hoehe des Sockels (sonst meldete jeder
        erste Nutzer eines ruhigen Tages 100 %)."""
        return gesamt >= self.INTERACTIVE_USER_LIMIT and eigen > self.INTERACTIVE_WARN_SHARE * gesamt

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
            ergebnis["interactive_calls_today"] = data["interactive_calls"].get(PROVIDER, 0)
            ergebnis["manual_calls_today"] = data["manual_calls"].get(PROVIDER, 0)
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
                "interactive_calls_today": 0,
                "manual_calls_today": 0,
            }
            aktive = 0
        gesamt, interaktiv, manuell = self._user_verbrauch()
        ergebnis["user_calls_today"] = gesamt
        ergebnis["fair_share"] = self._fair_share_fuer(aktive)
        ergebnis["active_users_count"] = aktive
        # ADR-0117: interaktiver Verbrauch getrennt ausgewiesen.
        ergebnis["interactive_budget"] = self._globale_grenze(INTERACTIVE)
        ergebnis["user_interactive_calls_today"] = interaktiv
        ergebnis["interactive_limit"] = self.INTERACTIVE_USER_LIMIT
        ergebnis["manual_budget"] = self._globale_grenze(MANUAL)
        ergebnis["user_manual_calls_today"] = manuell
        ergebnis["manual_limit"] = self.MANUAL_USER_LIMIT
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

    def _schwelle_fuer(self, priority: str) -> Optional[float]:
        """Schwelle der Prioritaet; ``None`` = nie drosseln (``user_briefing``,
        unbekannte Prioritaet -> fail-open)."""
        if priority == "polling":
            return self.POLLING_THRESHOLD
        if priority == "alert_check":
            return self.BRIEFING_ONLY_THRESHOLD
        return None

    def _erlaubt_laut_daten(
        self, data: dict, schwelle: float, now: Optional[datetime]
    ) -> bool:
        """Die Stufen-Entscheidung von ``allow()`` auf bereits geladenen
        (unter Sperre gehaltenen) Daten."""
        calls = data["calls"].get(PROVIDER, 0)
        ratio = calls / self.DAILY_BUDGET if self.DAILY_BUDGET > 0 else 0.0
        if ratio < schwelle:
            return True  # Stufe 0
        if ratio >= 1.0:
            return False  # Stufe 2 -- harter Kontoschutz
        return not self._ueber_fairem_anteil_n(len(data["active_users"]), now)

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

    def _user_verbrauch(self, now: Optional[datetime] = None) -> tuple[int, int, int]:
        """Eigener Tagesverbrauch ``(gesamt, davon interaktiv, davon manuell)``.
        Fail-open (E3/ADR-0075 Punkt 3): ein unlesbarer Topf oder ein
        Lesefehler gilt als 0."""
        if self._user_path is None:
            return 0, 0, 0
        try:
            data = self._load_user_for_today(now)
            return (data["calls"].get(PROVIDER, 0), data["interactive"].get(PROVIDER, 0),
                    data["manual"].get(PROVIDER, 0))
        except Exception as exc:
            logger.warning(
                "Nutzer-Budgettopf %s nicht lesbar (%s) -- Verbrauch gilt als "
                "0, es wird NICHT gedrosselt",
                self._user_path, exc,
            )
            return 0, 0, 0

    def _user_calls_today(self, now: Optional[datetime] = None) -> int:
        return self._user_verbrauch(now)[0]

    def _globale_grenze(self, klasse: str) -> int:
        """Globale Obergrenze einer Klasse (ADR-0117 Punkt 3 und Nachtrag)."""
        anteil = self.INTERACTIVE_THRESHOLD if klasse == INTERACTIVE else self.MANUAL_THRESHOLD
        return int(anteil * self.DAILY_BUDGET)

    def _grenze_je_nutzer(self, klasse: str) -> int:
        return self.INTERACTIVE_USER_LIMIT if klasse == INTERACTIVE else self.MANUAL_USER_LIMIT

    def _klasse_erlaubt(self, klasse: str, data: dict, units: int,
                        now: Optional[datetime]) -> bool:
        """Entscheidung fuer ``user_interactive``/``user_manual`` auf geladenen
        Daten. Ohne Kennung kein Nutzer-Topf und damit keine Befreiung
        (ADR-0075 Punkt 4)."""
        if data["calls"].get(PROVIDER, 0) + units > self._globale_grenze(klasse):
            return False
        if self._user_path is None:
            return False
        verbrauch = self._user_verbrauch(now)
        eigen = verbrauch[1] if klasse == INTERACTIVE else verbrauch[2]
        return eigen + units <= self._grenze_je_nutzer(klasse)

    def _ueber_fairem_anteil(self, now: Optional[datetime] = None) -> bool:
        """Stufe 1: liegt DIESER Nutzer ueber seinem fairen Anteil?

        Eine unattributierte Instanz (`user_id=None`, Provider-Schicht)
        kann keinen Pro-Kopf-Anteil haben. Sie faellt bewusst auf das
        Bestandsverhalten zurueck -- also DROSSELN -- statt sich selbst zu
        befreien: ein Aufruf ohne Kennung darf nie mehr duerfen als ein
        Aufruf mit Kennung.
        """
        try:
            aktive = len(self._load_for_today(now)["active_users"])
        except Exception:
            aktive = 0
        return self._ueber_fairem_anteil_n(aktive, now)

    def _ueber_fairem_anteil_n(self, aktive: int, now: Optional[datetime]) -> bool:
        if self._user_path is None:
            return True
        # ADR-0117: interaktiver Verbrauch hat sein eigenes Kontingent und
        # zaehlt nicht in die Fairness von Alarm-Pruefung und Polling.
        gesamt, interaktiv, manuell = self._user_verbrauch(now)
        return gesamt - interaktiv - manuell > self._fair_share_fuer(aktive)

    def _leerer_tag(self, today: str) -> dict:
        return {
            "date": today,
            "calls": {},
            "cache_hits": 0,
            "cache_misses": 0,
            "active_users": [],
            "interactive_calls": {},
            "manual_calls": {},
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
        interaktiv = raw.get("interactive_calls")
        manuell = raw.get("manual_calls")
        return {
            "date": today,
            "calls": calls,
            "cache_hits": raw.get("cache_hits", 0),
            "cache_misses": raw.get("cache_misses", 0),
            "active_users": [u for u in aktive if isinstance(u, str)],
            "interactive_calls": interaktiv if isinstance(interaktiv, dict) else {},
            "manual_calls": manuell if isinstance(manuell, dict) else {},
        }

    def _load_user_for_today(self, now: Optional[datetime] = None) -> dict:
        """Nutzer-Topf: schlanker als die globale Datei -- `cache_hits`/
        `cache_misses` werden fuer die Fairness-Berechnung nicht gebraucht.
        Derselbe UTC-Tagesschnitt wie global."""
        today = self._today_utc(now)
        if self._user_path is None or not self._user_path.exists():
            return self._leerer_nutzertag(today)
        raw = json.loads(self._user_path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("forecast_budget.json (Nutzer-Topf): unerwartete Struktur")
        if raw.get("date") != today:
            return self._leerer_nutzertag(today)
        calls = raw.get("calls")
        if not isinstance(calls, dict):
            calls = {}
        interaktiv = raw.get("interactive")
        manuell = raw.get("manual")
        return {
            "date": today, "calls": calls,
            "interactive": interaktiv if isinstance(interaktiv, dict) else {},
            "manual": manuell if isinstance(manuell, dict) else {},
            "interactive_warned": raw.get("interactive_warned") is True,
        }

    @staticmethod
    def _leerer_nutzertag(today: str) -> dict:
        """Nutzer-Topf eines neuen Tages; seit ADR-0117 mit getrenntem
        interaktivem Zaehler und Warn-Merker (eine Warnzeile je Tag)."""
        return {"date": today, "calls": {}, "interactive": {}, "manual": {},
                "interactive_warned": False}

    def _write(self, verzeichnis: Path, pfad: Path, data: dict) -> None:
        verzeichnis.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(verzeichnis), prefix=".forecast_budget_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                share_state_file(f.fileno())
                f.write(json.dumps(data))
            os.replace(tmp_name, pfad)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _safe_update(
        self, mutate: Callable[[dict], None], now: Optional[datetime] = None
    ) -> bool:
        """Reload-merge-write der GLOBALEN Datei unter Dateisperre."""
        return self._update_datei(
            self._dir, self._path, lambda: self._load_for_today(now),
            lambda: self._leerer_tag(self._today_utc(now)), mutate,
        )

    def _safe_update_user(
        self, mutate: Callable[[dict], None], now: Optional[datetime] = None
    ) -> bool:
        """Reload-merge-write des NUTZER-Topfs unter EIGENEM Sidecar-Lock
        (weniger Contention als ein gemeinsames Lock, Muster
        `throttle_store.py:197-245`). Ohne Kennung passiert nichts."""
        if self._user_dir is None or self._user_path is None:
            return True
        return self._update_datei(
            self._user_dir, self._user_path, lambda: self._load_user_for_today(now),
            lambda: self._leerer_nutzertag(self._today_utc(now)), mutate,
        )

    def _update_datei(
        self,
        verzeichnis: Path,
        pfad: Path,
        laden: Callable[[], dict],
        leerbau: Callable[[], dict],
        mutate: Callable[[dict], None],
    ) -> bool:
        """Fail-open: JEDER Fehler (Lock-Timeout, IO, kaputtes JSON) bleibt
        ohne Ausnahme -- ein Zaehl-Defekt darf nie einen Versand verhindern.
        Seit #1539 S1b meldet die Methode den Erfolg zurueck; eine verlorene
        Buchung steigt im Prozesszaehler ``forecast_budget_lost_bookings`` und
        steht als WARNING im Log (kein stilles ``pass`` mehr)."""
        try:
            if self._update_unter_sperre(verzeichnis, pfad, laden, leerbau, mutate):
                return True
            _count_lost_booking()
            return False
        except Exception as exc:
            _count_lost_booking()
            logger.warning("Budget-Buchung in %s verloren (%s)", pfad, exc)
            return False

    def _update_unter_sperre(self, verzeichnis, pfad, laden, leerbau, mutate) -> bool:
        verzeichnis.mkdir(parents=True, exist_ok=True)
        lock_path = str(pfad) + _LOCK_SUFFIX
        fd = open_lock_file(lock_path)
        try:
            start = time.monotonic()
            if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
                # F003 (Adversary #1448 S2): tatsaechlich gewartete Zeit loggen.
                logger.warning(
                    "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                    "Buchung verloren",
                    lock_path, time.monotonic() - start,
                )
                return False
            try:
                try:
                    data = laden()
                except Exception:
                    data = leerbau()
                mutate(data)
                self._write(verzeichnis, pfad, data)
                return True
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
