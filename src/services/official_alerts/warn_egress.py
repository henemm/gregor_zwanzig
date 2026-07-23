"""Geteilter Egress-Kern für die amtlichen Warn-Dienste (Issue #1348, Scheibe 2a von #1337).

Konsolidiert die bei allen fünf ``official_alerts``-Diensten strukturell
identische Cache-/429-Backoff-/Observability-Logik an EINER Stelle (Projektregel
„Code-Duplikate konsolidieren"):

- **Warngerechter TTL:** Erfolg 1800s (30 min, warngerecht länger als der
  15-Minuten-Scheduler-Takt), Fehler 60s (unverändert).
- **429-bewusster Rückzug:** HTTP 429 wird explizit erkannt (kein generisches
  ``raise_for_status()``), ``Retry-After`` (numerische Sekunden) respektiert,
  Backoff = ``max(retry_after, WARN_SUCCESS_TTL)`` — nie kürzer als die
  Erfolgs-TTL, damit kein 15-Minuten-Dauerfeuer entsteht. 429 wird LAUT geloggt.
- **Egress-Zähler:** jeder Durchlauf (Cache-Hit wie echter Call) schreibt eine
  fail-soft JSONL-Zeile nach ``data/diagnostics/warn_service_calls.jsonl``
  (Vorbild: ``src/providers/call_log.py``).

Jeder Dienst behält seinen eigenen Modul-Cache-Dict und übergibt ihn als
Parameter — kein globaler Cache-State, keine Kollision zwischen Diensten.
Dienst-spezifisch bleibt außerhalb: URL-Bau, Query, Auth, Antwort-Parsing
(``parse_fn``). Zeit wird über ``clock`` injiziert (deterministische Tests).

SPEC: docs/specs/modules/warn_service_consumption.md
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger("warn_egress")

WARN_SUCCESS_TTL = 1800.0  # Sekunden — Erfolgs-Fenster (30 min, warngerecht)
WARN_FAILURE_TTL = 60.0  # Sekunden — kurzes Failure-Fenster

# Issue #1348 (Real-Pfad-Fix): ``cached_fetch`` faengt JEDEN Fehlschlag fail-soft
# ab und gibt ``None`` zurueck; die Quellen wandeln ``None`` -> ``[]`` und werfen
# NICHT. Damit ``get_official_alerts_with_status`` "Abruf real fehlgeschlagen"
# (Block/429/HTTP>=400/Netz-/Parse-Fehler ODER gecachter Fehlschlag) von
# "erfolgreich leer" unterscheiden kann, vermerkt jeder Fehlschlag-Pfad einen
# Marker im aktuell aktiven Beobachtungs-Kontext (falls einer gesetzt ist).
# OHNE aktiven Kontext ist das ein No-Op — der Fail-soft-Vertrag von ``fetch()``
# und ``get_official_alerts_for_location()`` und damit alle Bestandsaufrufer
# bleiben unveraendert. ``ContextVar`` isoliert korrekt ueber Threads/Tasks.
_fetch_failure_sink: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "warn_fetch_failure_sink", default=None
)


def _record_fetch_failure() -> None:
    """Vermerkt einen realen Fetch-Fehlschlag im aktiven Beobachtungs-Kontext.

    Ausserhalb jeder ``observe_fetch_failure()``-Beobachtung ein No-Op."""
    sink = _fetch_failure_sink.get()
    if sink is not None:
        sink["failed"] = True


@contextmanager
def observe_fetch_failure() -> Iterator[dict]:
    """Beobachtet, ob innerhalb des Kontexts mindestens ein ``cached_fetch``
    real fehlschlug (im Gegensatz zu erfolgreich-leer). Liefert ein Dict mit
    Schluessel ``failed`` (bool, initial ``False``).

    Verschachtelbar und thread-/task-sicher (``contextvars``)."""
    sink: dict = {"failed": False}
    token = _fetch_failure_sink.set(sink)
    try:
        yield sink
    finally:
        _fetch_failure_sink.reset(token)

# Append-only JSONL für jeden Warn-Dienst-Egress (Cache-Hit wie echter Call).
# Verzeichnis `data/diagnostics/` ist in .gitignore.
WARN_CALLS_PATH = Path("data/diagnostics/warn_service_calls.jsonl")


def _parse_retry_after(headers: Any) -> Optional[float]:
    """``Retry-After`` als numerische Sekunden auswerten.

    Nur das numerische Sekunden-Format wird ausgewertet — die alternative
    HTTP-Date-Form wird als „kein Header" behandelt (siehe Known Limitations
    der Spec). Fehlt der Header, ``None``.
    """
    raw = headers.get("Retry-After") if headers is not None else None
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def log_warn_service_call(
    service: str,
    host: str,
    status: Optional[int],
    cache_hit: bool,
    retry_after: Optional[float] = None,
) -> None:
    """Einen Warn-Dienst-Egress protokollieren (fail-soft, analog ``log_api_call``).

    Hängt eine JSONL-Zeile (``ts, service, host, status, cache_hit, retry_after``)
    an ``WARN_CALLS_PATH`` an. Jeder Fehler wird geschluckt — Observability darf
    den Abruf NIE beeinträchtigen.
    """
    try:
        path = WARN_CALLS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "host": host,
            "status": status,
            "cache_hit": cache_hit,
            "retry_after": retry_after,
        })
        with path.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # Observability darf den Abruf NIE beeinträchtigen


def cached_fetch(
    *,
    cache: dict,
    cache_key: str,
    service: str,
    host: str,
    request_fn: Callable[[], Any],
    parse_fn: Callable[[Any], Any],
    clock: Callable[[], float] = time.monotonic,
    success_ttl: float = WARN_SUCCESS_TTL,
    failure_ttl: float = WARN_FAILURE_TTL,
    log: logging.Logger = logger,
) -> Optional[Any]:
    """TTL-Cache mit 429-bewusstem Rückzug und Egress-Zähler.

    Cache-Hit im Fenster ruft ``request_fn`` NICHT auf. Bei Cache-Miss löst
    ``request_fn()`` einen echten Aufruf aus; ``resp.status_code`` wird explizit
    ausgewertet (kein ``raise_for_status()``):

    - **2xx/andere <400:** ``parse_fn(resp)`` -> Erfolg, ``success_ttl``.
    - **429:** Backoff ``max(retry_after, success_ttl)``, LAUTER WARNING,
      Cache-Eintrag als Fehlschlag (Daten ``None``, ``ttl=backoff``), Rückgabe
      ``None``.
    - **>=400 (außer 429) / Netzwerkfehler / Parse-Fehler:** ``failure_ttl``,
      Rückgabe ``None`` (unverändertes Fail-soft-Verhalten).
    """
    now = clock()
    entry = cache.get(cache_key)
    if entry is not None and entry.get("fetched_at") is not None \
            and (now - entry["fetched_at"]) < entry["ttl"]:
        log_warn_service_call(service, host, status=None, cache_hit=True)
        # Ein gecachter Fehlschlag (data=None, z.B. waehrend 429-Backoff) ist
        # weiterhin "nicht abrufbar" — nicht "erfolgreich leer" (Issue #1348).
        if entry["data"] is None:
            _record_fetch_failure()
        return entry["data"]

    try:
        resp = request_fn()
    except Exception:
        log.warning("%s-Abruf fehlgeschlagen (%s)", service, host, exc_info=True)
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        log_warn_service_call(service, host, status=None, cache_hit=False)
        _record_fetch_failure()
        return None

    status = resp.status_code
    if status == 429:
        retry_after = _parse_retry_after(resp.headers)
        backoff = max(retry_after or 0.0, success_ttl)
        log.warning(
            "%s: HTTP 429 (Kontingent erschöpft) — Rückzug für %.0fs "
            "(Retry-After=%s)",
            service, backoff, retry_after,
        )
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": backoff}
        log_warn_service_call(service, host, status=429, cache_hit=False,
                              retry_after=retry_after)
        _record_fetch_failure()
        return None

    if status >= 400:
        log.warning("%s-Abruf fehlgeschlagen (%s, HTTP %s)", service, host, status)
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        log_warn_service_call(service, host, status=status, cache_hit=False)
        _record_fetch_failure()
        return None

    try:
        data = parse_fn(resp)
    except Exception:
        log.warning("%s-Abruf fehlgeschlagen (%s, Parse)", service, host, exc_info=True)
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        log_warn_service_call(service, host, status=status, cache_hit=False)
        _record_fetch_failure()
        return None

    cache[cache_key] = {"data": data, "fetched_at": now, "ttl": success_ttl}
    log_warn_service_call(service, host, status=status, cache_hit=False)
    return data
