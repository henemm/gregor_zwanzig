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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger("warn_egress")

WARN_SUCCESS_TTL = 1800.0  # Sekunden — Erfolgs-Fenster (30 min, warngerecht)
WARN_FAILURE_TTL = 60.0  # Sekunden — kurzes Failure-Fenster
# Issue #1397 S2a: TTL fuer einen "nicht zustaendig"-Statuscode (s.
# ``not_covered_statuses``). Staatsgrenzen bewegen sich nicht -- lange TTL,
# damit ein Punkt ausserhalb des Zustaendigkeitsbereichs nicht bei jedem
# 15-Minuten-Scheduler-Takt erneut abgefragt wird.
WARN_NOT_COVERED_TTL = 24 * 3600.0  # Sekunden — 24h

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


def mark_fetch_incomplete() -> None:
    """OEFFENTLICHER Weg, einen Fetch als real fehlgeschlagen zu markieren,
    OHNE dass ``cached_fetch()`` selbst einen Fehlschlag gesehen hat (Issue
    #1397 Scheibe S1c): schrittweises Blaettern kann ein Zeitbudget
    ausschoepfen, bevor alle Seiten geholt sind — die bereits geholten Seiten
    werden dann zurueckgegeben (kein STILLES Teilergebnis mehr, s. Spec),
    aber der Aufruf muss trotzdem als "nicht vollstaendig abrufbar" zaehlen.

    Wirkt identisch zu einem internen ``cached_fetch()``-Fehlschlag: markiert
    den aktiven ``observe_fetch_failure()``-Kontext (falls einer aktiv ist).
    Ausserhalb eines aktiven Kontexts ein No-Op, wie ``cached_fetch()``
    selbst."""
    _record_fetch_failure()


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


def parse_ratelimit_reset(headers: Any) -> Optional[float]:
    """``x-ratelimit-reset`` als Unix-Zeitstempel (Sekunden, float) auswerten.

    Issue #1397 Scheibe S1b: MeteoAlarm liefert bei 429 KEINEN ``Retry-After``,
    aber ``x-ratelimit-reset`` mit dem Unix-Zeitpunkt, ab dem die naechste
    Anfrage wieder durchgeht (Messung 2026-07-27). Fehlt der Header oder ist
    er unlesbar, ``None`` — Aufrufer fallen dann auf einen festen Abstand
    zurueck."""
    raw = headers.get("x-ratelimit-reset") if headers is not None else None
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RateLimitRetryPolicy:
    """Optionale 429-Wiederholung fuer ``cached_fetch`` (Issue #1397 S1b,
    um die Kurzzeit-/Tageskontingent-Unterscheidung der S1c-Nachbesserung
    erweitert).

    OHNE dieses Objekt (Parameter ``rate_limit_retry=None``, Standard fuer
    alle Aufrufer) verhaelt sich ``cached_fetch()`` BIT-IDENTISCH zum Bestand
    — nur MeteoAlarms Index-Seiten-Abruf schaltet es ein.

    MeteoAlarm limitiert auf ZWEI Ebenen (Messung 2026-07-27, S1c-Nach-
    besserung): eine Kurzzeit-Ratenbremse (~1 Anfrage/4s, ``x-ratelimit-
    reset`` wenige Sekunden in der Zukunft -- Wiederholen lohnt sich) UND ein
    TAGESKONTINGENT (``x-ratelimit-reset`` ~86400s in der Zukunft, Body
    "Daily rate limit exceeded"). Die Unterscheidung laeuft NICHT ueber den
    Statuscode (immer 429), sondern ueber den Abstand des ``x-ratelimit-
    reset`` zu jetzt: liegt er innerhalb ``short_wait_ceiling_seconds``,
    gilt die Kurzzeit-Bremse (warten + wiederholen); liegt er darueber, gilt
    das Tageskontingent -- dann wird NICHT wiederholt (jeder Versuch waere
    verschenkt), sondern sofort mit einem bis zum Reset reichenden Rueckzug
    (gedeckelt durch ``long_backoff_cap_seconds``, gegen absurde Werte)
    aufgegeben.

    ``max_attempts`` zaehlt den ERSTEN Versuch mit — bei ``max_attempts=3``
    wird bei einer KURZZEIT-Bremse hoechstens zweimal gewartet und
    wiederholt, danach gilt die Seite wie bisher als Fehlschlag (langer
    Rueckzug, kein Teilergebnis, s. ``cached_fetch``-429-Zweig).
    ``max_wait_seconds`` deckelt die Wartezeit je Versuch der Kurzzeit-
    Bremse. ``default_wait_seconds`` greift, wenn der Header fehlt/unlesbar
    ist (dann gilt IMMER die Kurzzeit-Annahme -- ohne Reset-Zeitpunkt ist
    ein Tageskontingent nicht erkennbar). ``sleep_fn``/``wall_clock_fn`` sind
    injizierbar, damit Tests nicht real warten muessen."""
    max_attempts: int = 3
    max_wait_seconds: float = 8.0
    default_wait_seconds: float = 4.0
    short_wait_ceiling_seconds: float = 60.0
    long_backoff_cap_seconds: float = 24 * 3600.0
    sleep_fn: Callable[[float], None] = time.sleep
    wall_clock_fn: Callable[[], float] = time.time

    def _raw_wait(self, headers: Any) -> Optional[float]:
        reset_ts = parse_ratelimit_reset(headers)
        if reset_ts is None:
            return None
        return reset_ts - self.wall_clock_fn()

    def is_long_lived(self, headers: Any) -> bool:
        """True, wenn ``x-ratelimit-reset`` weiter als
        ``short_wait_ceiling_seconds`` in der Zukunft liegt (Tageskontingent-
        Verdacht). Fehlt der Header, ``False`` (Kurzzeit-Annahme -- ohne
        Reset-Zeitpunkt nicht als Tageskontingent erkennbar)."""
        raw = self._raw_wait(headers)
        if raw is None:
            return False
        return raw > self.short_wait_ceiling_seconds

    def wait_seconds(self, headers: Any) -> float:
        """Wartezeit fuer die KURZZEIT-Wiederholung (nur relevant, wenn
        ``is_long_lived()`` ``False`` ist)."""
        raw = self._raw_wait(headers)
        if raw is None:
            return self.default_wait_seconds
        return min(max(raw, 0.0), self.max_wait_seconds)

    def long_backoff_seconds(self, headers: Any) -> Optional[float]:
        """Rueckzugsdauer bis zum Reset-Zeitpunkt fuer ein erkanntes
        Tageskontingent, gedeckelt durch ``long_backoff_cap_seconds``.
        ``None``, wenn kein ``x-ratelimit-reset`` auswertbar ist (Aufrufer
        faellt dann auf die bestehende ``Retry-After``-Backoff-Formel
        zurueck)."""
        raw = self._raw_wait(headers)
        if raw is None:
            return None
        return min(max(raw, 0.0), self.long_backoff_cap_seconds)


def log_warn_service_call(
    service: str,
    host: str,
    status: Optional[int],
    cache_hit: bool,
    retry_after: Optional[float] = None,
    ok: bool = False,
    self_throttled: bool = False,
) -> None:
    """Einen Warn-Dienst-Egress protokollieren (fail-soft, analog ``log_api_call``).

    Hängt eine JSONL-Zeile (``ts, service, host, status, cache_hit, retry_after,
    ok, self_throttled``) an ``WARN_CALLS_PATH`` an. Jeder Fehler wird geschluckt
    — Observability darf den Abruf NIE beeinträchtigen.

    ``ok`` (Issue #1422 S1) trägt den TATSAECHLICHEN Ausgang: ``True`` bei
    Erfolg — auch bei "nicht zustaendig" (fachlich gueltige Antwort) und bei
    Cache-Treffern auf gute Daten; ``False`` bei jedem Fehlschlag, auch beim
    Cache-Treffer auf einen GECACHTEN Fehlschlag (bisher von aussen nicht von
    einem Treffer auf gute Daten unterscheidbar: ``status=null,
    cache_hit=true``). ``self_throttled`` ist nur ``True``, wenn der Fehlschlag
    ein SELBST auferlegter Rueckzug war (eigenes Tageskontingent erschoepft) —
    andere Gegenmassnahme als ein Anbieter-Ausfall. Beide Felder sind rein
    additiv; bestehende Leser (z.B. #1397-Verbrauchsmessung ueber
    ``cache_hit``) bleiben unberuehrt.
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
            "ok": bool(ok),
            "self_throttled": bool(self_throttled),
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
    rate_limit_retry: Optional[RateLimitRetryPolicy] = None,
    on_response: Optional[Callable[[Any], None]] = None,
    not_covered_statuses: Optional[frozenset[int]] = None,
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

    ``rate_limit_retry`` (Issue #1397 S1b, Standard ``None``): ist ein
    ``RateLimitRetryPolicy`` gesetzt, wird ein 429 NICHT sofort als
    Fehlschlag gewertet, solange Versuche uebrig sind — stattdessen wird laut
    geloggt, gewartet (Policy) und ``request_fn()`` erneut aufgerufen. Erst
    wenn die Versuche erschoepft sind, greift der unveraenderte 429-Zweig
    oben. Ohne dieses Argument (alle Bestandsaufrufer) ist das Verhalten
    BIT-IDENTISCH zum Vor-S1b-Stand. ``on_response`` (Standard ``None``) wird
    bei JEDEM echten (nicht gecachten) HTTP-Response-Objekt aufgerufen, bevor
    ``parse_fn`` laeuft — Beobachtungshaken fuer Aufrufer, die z.B. den
    ``x-ratelimit-reset`` der letzten Antwort fuer eine vorbeugende Pause vor
    dem naechsten Aufruf mitschneiden wollen (nie ausserhalb try/except).

    ``not_covered_statuses`` (Issue #1397 S2a, Standard ``None`` -- OHNE
    dieses Argument ist ``cached_fetch()`` BIT-IDENTISCH zum Bestand): eine
    Menge von Statuscodes, die NICHT als Fehlschlag gelten, sondern als
    "fuer diesen Punkt/Parameter nicht zustaendig" (Vorbild: ZAMG antwortet
    ausserhalb Oesterreichs auf den koordinaten-scoped Endpunkt mit 404).
    Trifft ein solcher Status zu, wird ein neutraler leerer Wert (``{}``)
    als ERFOLG mit ``WARN_NOT_COVERED_TTL`` gecacht -- kein
    ``_record_fetch_failure()``, die Egress-Zeile traegt weiterhin den
    echten Statuscode. ``{}`` ist bewusst kein ``None`` (der Cache-Treffer-
    Zweig oben unterscheidet Fehlschlag von Erfolg ueber ``data is None``)
    und wird von den bestehenden ``_extract_alerts()``-Implementierungen
    (KeyError auf ``data["properties"]``) bereits sauber zu ``[]``.
    """
    now = clock()
    entry = cache.get(cache_key)
    if entry is not None and entry.get("fetched_at") is not None \
            and (now - entry["fetched_at"]) < entry["ttl"]:
        # Ein gecachter Fehlschlag (data=None, z.B. waehrend 429-Backoff) ist
        # weiterhin "nicht abrufbar" — nicht "erfolgreich leer" (Issue #1348)
        # — und traegt genau das jetzt auch im Journal (Issue #1422 S1: sonst
        # sieht er von aussen aus wie ein Treffer auf gute Daten).
        cached_ok = entry["data"] is not None
        log_warn_service_call(service, host, status=None, cache_hit=True, ok=cached_ok)
        if not cached_ok:
            _record_fetch_failure()
        return entry["data"]

    attempt = 1
    while True:
        try:
            resp = request_fn()
        except Exception as exc:
            # Issue #1422 S1: ein selbst auferlegter Rueckzug (eigenes
            # Tageskontingent erschoepft, KEIN Netzwerk-Call) meldet sich ueber
            # ein Attribut an der Ausnahme — keine Exception-Hierarchie noetig,
            # jede fremde Ausnahme bleibt ein echter Anbieter-Ausfall.
            self_throttled = bool(getattr(exc, "self_throttled", False))
            log.warning("%s-Abruf fehlgeschlagen (%s)", service, host, exc_info=True)
            cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
            log_warn_service_call(service, host, status=None, cache_hit=False,
                                  ok=False, self_throttled=self_throttled)
            _record_fetch_failure()
            return None

        if on_response is not None:
            try:
                on_response(resp)
            except Exception:
                pass  # Beobachtungshaken darf den Abruf NIE beeintraechtigen

        status = resp.status_code
        # S1c-Nachbesserung (Tageskontingent-Fund): ein Tageskontingent
        # (is_long_lived()) wird NIE wiederholt -- jeder Zwischenversuch
        # waere gegen ein bereits erschoepftes Tageslimit verschenkt UND
        # verfaelscht die Verbrauchsmessung. Nur eine erkannte KURZZEIT-
        # Bremse (kurzer Reset-Abstand oder gar kein Reset-Header) ist
        # wiederholungswuerdig.
        if status == 429 and rate_limit_retry is not None \
                and not rate_limit_retry.is_long_lived(resp.headers) \
                and attempt < rate_limit_retry.max_attempts:
            wait = rate_limit_retry.wait_seconds(resp.headers)
            log.warning(
                "%s: HTTP 429 (Ratenbremse) — warte %.1fs und wiederhole "
                "(Versuch %d/%d)",
                service, wait, attempt, rate_limit_retry.max_attempts,
            )
            # Adversary-Fund (Issue #1397 S1c-Runde): ein Zwischenversuch ist
            # ein ECHTER Abruf gegen die API -- muss im Egress-Zaehler
            # auftauchen, sonst ist der Zaehler kein verlaesslicher
            # Verbrauchs-Nachweis mehr (gerade die Ratenbremse soll darin
            # sichtbar sein). status=429/cache_hit=False wie beim finalen
            # 429-Zweig unten, zusaetzlich der ermittelte Wartewert.
            log_warn_service_call(service, host, status=429, cache_hit=False,
                                  retry_after=wait, ok=False)
            rate_limit_retry.sleep_fn(wait)
            attempt += 1
            continue
        break

    if status == 429:
        retry_after = _parse_retry_after(resp.headers)
        backoff = max(retry_after or 0.0, success_ttl)
        # Tageskontingent-Fund (S1c-Nachbesserung): ohne diese Erweiterung
        # wuerde ein Tageslimit (x-ratelimit-reset ~86400s entfernt, KEIN
        # Retry-After) auf die warngerechte success_ttl (45 min) zurueckfallen
        # -- viel zu kurz, das Kontingent waere binnen Minuten erneut leer-
        # gefeuert. long_backoff_seconds() liefert den bis zum Reset
        # reichenden, gedeckelten Rueckzug; er GEWINNT nur, wenn er laenger
        # ist als die bestehende Formel (nie kuerzer als vorher).
        reset_backoff = rate_limit_retry.long_backoff_seconds(resp.headers) \
            if rate_limit_retry is not None else None
        if reset_backoff is not None:
            backoff = max(backoff, reset_backoff)
        logged_retry_after = retry_after if retry_after is not None else reset_backoff
        log.warning(
            "%s: HTTP 429 (Kontingent erschöpft) — Rückzug für %.0fs "
            "(Retry-After=%s)",
            service, backoff, logged_retry_after,
        )
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": backoff}
        log_warn_service_call(service, host, status=429, cache_hit=False,
                              retry_after=logged_retry_after, ok=False)
        _record_fetch_failure()
        return None

    if not_covered_statuses is not None and status in not_covered_statuses:
        # Issue #1397 S2a: "nicht zustaendig" ist KEIN Ausfall -- kein
        # _record_fetch_failure(), lange Erfolgs-TTL (Staatsgrenzen bewegen
        # sich nicht), Egress-Zeile behaelt den echten Statuscode.
        log.debug(
            "%s: HTTP %s -- ausserhalb des Zustaendigkeitsbereichs, kein Ausfall",
            service, status,
        )
        neutral_value: Any = {}
        cache[cache_key] = {"data": neutral_value, "fetched_at": now, "ttl": WARN_NOT_COVERED_TTL}
        # Issue #1422 S1: "nicht zustaendig" ist fachlich ein ERFOLG (ok=True),
        # auch wenn der Statuscode 404 sonst ein Fehlschlag waere.
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=True)
        return neutral_value

    if status >= 400:
        log.warning("%s-Abruf fehlgeschlagen (%s, HTTP %s)", service, host, status)
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=False)
        _record_fetch_failure()
        return None

    try:
        data = parse_fn(resp)
    except Exception:
        log.warning("%s-Abruf fehlgeschlagen (%s, Parse)", service, host, exc_info=True)
        cache[cache_key] = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=False)
        _record_fetch_failure()
        return None

    cache[cache_key] = {"data": data, "fetched_at": now, "ttl": success_ttl}
    log_warn_service_call(service, host, status=status, cache_hit=False, ok=True)
    return data
