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

from services import alert_input_capture
from services.single_flight import SingleFlight

logger = logging.getLogger("warn_egress")

WARN_SUCCESS_TTL = 1800.0  # Sekunden — Erfolgs-Fenster (30 min, warngerecht)
WARN_FAILURE_TTL = 60.0  # Sekunden — kurzes Failure-Fenster
# Issue #1397 S2a: TTL fuer einen "nicht zustaendig"-Statuscode (s.
# ``not_covered_statuses``). Staatsgrenzen bewegen sich nicht -- lange TTL,
# damit ein Punkt ausserhalb des Zustaendigkeitsbereichs nicht bei jedem
# 15-Minuten-Scheduler-Takt erneut abgefragt wird.
WARN_NOT_COVERED_TTL = 24 * 3600.0  # Sekunden — 24h

# Issue #1539 S1b (C4-64): Single-flight je (Cache, Schluessel). Wartezeit der
# Mitflieger auf den Leader (Providerfrist + Puffer); danach holen sie selbst ab.
WARN_FLIGHT_WAIT_TIMEOUT_S = 90.0
_FLIGHTS = SingleFlight()

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


def mark_not_covered() -> None:
    """Issue #1681 (AC-3): vermerkt im aktiven ``observe_fetch_failure()``-
    Kontext, dass die Quelle fuer den Punkt fachlich NICHT zustaendig ist
    (ZAMG 404, AT Fall 1, keine DPC-/DWD-Zone) -- trotz ``covers() == True``
    des groben Vorfilters. ``base.py`` nimmt sie dann aus der ``covering``-
    Bilanz, damit sie den Ausfall der wirklich zustaendigen Quelle nicht
    kompensiert. Ausserhalb eines aktiven Kontexts ein No-Op."""
    sink = _fetch_failure_sink.get()
    if sink is not None:
        sink["not_covered"] = True


@contextmanager
def observe_fetch_failure() -> Iterator[dict]:
    """Beobachtet, ob innerhalb des Kontexts mindestens ein ``cached_fetch``
    real fehlschlug (im Gegensatz zu erfolgreich-leer). Liefert ein Dict mit
    Schluessel ``failed`` (bool, initial ``False``).

    Verschachtelbar und thread-/task-sicher (``contextvars``)."""
    sink: dict = {"failed": False, "not_covered": False}
    token = _fetch_failure_sink.set(sink)
    try:
        yield sink
    finally:
        _fetch_failure_sink.reset(token)


# Issue #1944: zweiter, gleich gebauter Rueckkanal fuer die Kennung des
# Eingangs-Mitschnitts (``alert_input_capture.capture_system``, #1948 S1).
# ``cached_fetch()`` behaelt seinen Rueckgabewert UNVERAENDERT -- die Kennung
# reist ausschliesslich als Seiteninformation hier entlang, damit der
# ``alert_log``-Eintrag der versendeten Warnung auf genau den Roh-Datensatz
# zeigt, der sie ausgeloest hat (Vorfall #1929). Ohne aktiven Kontext ein
# No-Op, exakt wie ``_record_fetch_failure()``.
_capture_id_sink: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "warn_capture_id_sink", default=None
)


def _record_capture_id(capture_id: Optional[str]) -> None:
    """Meldet die Kennung des gerade verwerteten Mitschnitts an den aktiven
    Beobachtungs-Kontext. Ohne Kennung oder ohne Kontext ein No-Op."""
    if not capture_id:
        return
    sink = _capture_id_sink.get()
    if sink is not None:
        sink["capture_ids"].append(capture_id)


@contextmanager
def observe_capture_id() -> Iterator[dict]:
    """Beobachtet, welche Mitschnitt-Kennungen innerhalb des Kontexts von
    ``cached_fetch()`` verwertet wurden -- sowohl bei einem echten Abruf als
    auch bei einem Treffer im Zwischenspeicher (der die Kennung seines
    Ursprungsabrufs mitfuehrt). Liefert ein Dict mit Schluessel
    ``capture_ids`` (Liste in Melde-Reihenfolge, initial leer).

    Verschachtelbar und thread-/task-sicher (``contextvars``)."""
    sink: dict = {"capture_ids": []}
    token = _capture_id_sink.set(sink)
    try:
        yield sink
    finally:
        _capture_id_sink.reset(token)


@contextmanager
def collect_capture_ids(collected: list) -> Iterator[None]:
    """Fail-open-Mantel um ``observe_capture_id()`` fuer Aufrufer, die die
    beobachteten Kennungen nur SAMMELN wollen (Issue #1944, AC-7).

    Faellt der Rueckkanal selbst aus, laeuft der umschlossene Abruf
    unveraendert weiter -- ``collected`` bleibt dann leer. Beweisaufnahme darf
    einen Alarm nie verhindern."""
    try:
        ctx = observe_capture_id()
        sink = ctx.__enter__()
    except Exception:
        logger.warning("Herkunfts-Rueckkanal nicht nutzbar", exc_info=True)
        yield
        return
    try:
        yield
    finally:
        try:
            ctx.__exit__(None, None, None)
            collected.extend(sink["capture_ids"])
        except Exception:
            logger.warning("Herkunfts-Kennungen nicht auswertbar", exc_info=True)


def _store_entry(
    cache: dict, cache_key: str, *, data: Any, fetched_at: float, ttl: float,
    capture_id: Optional[str],
) -> dict:
    """Schreibt den Zwischenspeicher-Eintrag und meldet die Herkunft.

    ``capture_id`` ist rein additiv (Issue #1944): ohne Kennung entsteht das
    Feld gar nicht erst, bestehende Leser des Eintrags bleiben unberuehrt."""
    entry: dict = {"data": data, "fetched_at": fetched_at, "ttl": ttl}
    if capture_id is not None:
        entry["capture_id"] = capture_id
    cache[cache_key] = entry
    _record_capture_id(capture_id)
    return entry

# Append-only JSONL für jeden Warn-Dienst-Egress (Cache-Hit wie echter Call).
# Issue #1633: Test-Override (Path) oder None. Der frühere Modul-Konstanten-Name
# `WARN_CALLS_PATH` steuert NICHTS mehr — er band beim Import einen
# repo-relativen Pfad und hat den Datenwurzel-Umzug (#1595) ausgehebelt.
WARN_CALLS_PATH_OVERRIDE: Optional[Path] = None


def warn_calls_path() -> Path:
    """Zielpfad des Warn-Dienst-Journals, bei jedem Zugriff aufgelöst."""
    if WARN_CALLS_PATH_OVERRIDE is not None:
        return Path(WARN_CALLS_PATH_OVERRIDE)
    from app.loader import get_data_root

    return Path(get_data_root()) / "diagnostics" / "warn_service_calls.jsonl"


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
    ok: bool = False,
    self_throttled: bool = False,
) -> None:
    """Einen Warn-Dienst-Egress protokollieren (fail-soft, analog ``log_api_call``).

    Hängt eine JSONL-Zeile (``ts, service, host, status, cache_hit, retry_after,
    ok, self_throttled``) an ``warn_calls_path()`` an. Jeder Fehler wird geschluckt
    — Observability darf den Abruf NIE beeinträchtigen.

    ``ok`` (Issue #1422 S1) trägt den TATSAECHLICHEN Ausgang: ``True`` bei
    Erfolg — auch bei "nicht zustaendig" (fachlich gueltige Antwort) und bei
    Cache-Treffern auf gute Daten; ``False`` bei jedem Fehlschlag, auch beim
    Cache-Treffer auf einen GECACHTEN Fehlschlag (bisher von aussen nicht von
    einem Treffer auf gute Daten unterscheidbar: ``status=null,
    cache_hit=true``). ``self_throttled`` ist nur ``True``, wenn der Fehlschlag
    ein SELBST auferlegter Rueckzug war (eigenes Tageskontingent erschoepft) —
    andere Gegenmassnahme als ein Anbieter-Ausfall. Seit dem Rueckbau der
    MeteoAlarm-EDR-Klasse samt Tageskontingent (#2266) setzt kein Dienst das
    Feld mehr -- es bleibt aus Schema-Stabilitaet (Go-Auswertung
    ``warn_service_health.go``) und ist praktisch konstant ``False``. Beide
    Felder sind rein additiv; bestehende Leser (z.B. #1397-Verbrauchsmessung ueber
    ``cache_hit``) bleiben unberuehrt.
    """
    try:
        path = warn_calls_path()
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


def log_zone_drift(service: str, zone_code: str, has_warning: bool, drift: str) -> None:
    """Additive Ereigniszeile fuer einen Zonen-Drift zwischen Bulletin und
    eingecheckter Geometrie (Issue #1434) -- bewusst NEBEN
    ``log_warn_service_call()`` und nicht als Erweiterung davon, weil beide
    Zeilenarten unterschiedlich oft entstehen (je echtem Abruf vs. je
    betroffenem Zonencode/Ort).

    Traegt BEWUSST KEIN ``ok``-Feld: die bestehende Go-Aggregation
    (``entry.Ok == nil -> continue``) ueberspringt diese Zeilen dadurch
    automatisch und meldet keinen falschen Ausfall (Spec fix_1434, Implementation
    Details Punkt 3). Jeder Fehler beim Schreiben wird geschluckt -- Beobachtung
    darf den Abruf nie beeintraechtigen (analog ``log_warn_service_call``)."""
    try:
        path = warn_calls_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "zone_code": zone_code,
            "has_warning": bool(has_warning),
            "drift": drift,
        })
        with path.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # Beobachtung darf den Abruf NIE beeintraechtigen


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
    on_response: Optional[Callable[[Any], None]] = None,
    not_covered_statuses: Optional[frozenset[int]] = None,
    not_covered_ttl: float = WARN_NOT_COVERED_TTL,
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

    Eine 429-Wiederholung gibt es nicht mehr: die fruehere optionale
    Retry-Policy (Issue #1397 S1b) hatte als einzigen Nutzer die
    MeteoAlarm-EDR-Klasse und ist mit ihr zurueckgebaut (#2266) -- jeder
    Abruf ist genau EIN ``request_fn()``-Aufruf. ``on_response`` (Standard ``None``) wird
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

    ``not_covered_ttl`` (Issue #1441, Standard ``WARN_NOT_COVERED_TTL`` = 24 h,
    Bestand bit-identisch): Cache-Dauer des neutralen "nicht zustaendig"-
    Ergebnisses. Der Lawinen-Lagebericht nutzt 404 als "kein aktueller
    Bericht" -- das darf nicht 24 h verborgen bleiben (Neuausgabe 17:00).
    """
    now = clock()
    entry = cache.get(cache_key)
    if _is_fresh(entry, now):
        return _serve_entry(service, host, entry)

    fetch_kwargs = dict(
        cache=cache, cache_key=cache_key, service=service, host=host,
        request_fn=request_fn, parse_fn=parse_fn, clock=clock,
        success_ttl=success_ttl, failure_ttl=failure_ttl, log=log,
        on_response=on_response,
        not_covered_statuses=not_covered_statuses, not_covered_ttl=not_covered_ttl,
    )

    def leader_fn() -> tuple:
        # Zweite Pruefung: ein Vorgaenger-Flug kann den Eintrag zwischen
        # unserer Pruefung und dem Flug-Start frisch geschrieben haben.
        current = cache.get(cache_key)
        if _is_fresh(current, clock()):
            return current, True
        return _fetch_and_store(**fetch_kwargs), False

    res = _FLIGHTS.run((id(cache), cache_key), leader_fn,
                       wait_timeout_s=WARN_FLIGHT_WAIT_TIMEOUT_S)
    if res.is_leader:
        if res.error is not None:
            raise res.error
        flight_entry, was_hit = res.value
        if was_hit:
            return _serve_entry(service, host, flight_entry)
        return flight_entry["data"]
    if res.error is not None or res.timed_out:
        # Fail-open: Flug gescheitert/zu lang -- selbst abholen.
        return _fetch_and_store(**fetch_kwargs)["data"]
    # Wartender: Entry stammt aus dem Flug (nicht per erneutem cache.get --
    # eine TTL, die waehrend des Leader-Schlafs ablaeuft, waere ein falscher
    # Miss). Eigene Senken ueber _serve_entry.
    return _serve_entry(service, host, res.value[0])


def _is_fresh(entry: Optional[dict], now: float) -> bool:
    return entry is not None and entry.get("fetched_at") is not None \
        and (now - entry["fetched_at"]) < entry["ttl"]


def _serve_entry(service: str, host: str, entry: dict) -> Any:
    """Bedient Journal und die Senken des AKTUELLEN Kontexts aus einem Entry
    (Cache-Treffer oder Flug-Ergebnis)."""
    # Ein gecachter Fehlschlag (data=None, z.B. waehrend 429-Backoff) ist
    # weiterhin "nicht abrufbar" -- nicht "erfolgreich leer" (Issue #1348) --
    # und traegt genau das jetzt auch im Journal (Issue #1422 S1).
    cached_ok = entry["data"] is not None
    log_warn_service_call(service, host, status=None, cache_hit=True, ok=cached_ok)
    if not cached_ok:
        _record_fetch_failure()
    elif entry["ttl"] == WARN_NOT_COVERED_TTL or entry.get("not_covered"):
        mark_not_covered()  # Issue #1681: gecachtes "nicht zustaendig"
    # Issue #1944 (Luecke a): der Treffer meldet die Kennung SEINES
    # Ursprungsabrufs -- kein zusaetzlicher Mitschnitt noetig.
    _record_capture_id(entry.get("capture_id"))
    return entry["data"]


def _fetch_and_store(
    *, cache: dict, cache_key: str, service: str, host: str,
    request_fn: Callable[[], Any], parse_fn: Callable[[Any], Any],
    clock: Callable[[], float], success_ttl: float, failure_ttl: float,
    log: logging.Logger,
    on_response: Optional[Callable[[Any], None]],
    not_covered_statuses: Optional[frozenset[int]],
    not_covered_ttl: float = WARN_NOT_COVERED_TTL,
) -> dict:
    """Echter Abruf (Leader-Zweig von ``cached_fetch``): schreibt den Eintrag in
    den Zwischenspeicher, bedient die Senken des Leaders und liefert den Eintrag."""
    now = clock()
    try:
        resp = request_fn()
    except Exception as exc:
        # Issue #1422 S1: ein selbst auferlegter Rueckzug (KEIN Netzwerk-Call)
        # meldet sich ueber ein Attribut an der Ausnahme — keine
        # Exception-Hierarchie noetig, jede fremde Ausnahme bleibt ein echter
        # Anbieter-Ausfall. Seit #2266 setzt kein Dienst das Attribut mehr;
        # der Zweig haelt das Journal-Feld schema-stabil.
        self_throttled = bool(getattr(exc, "self_throttled", False))
        log.warning("%s-Abruf fehlgeschlagen (%s)", service, host, exc_info=True)
        entry = {"data": None, "fetched_at": now, "ttl": failure_ttl}
        cache[cache_key] = entry
        log_warn_service_call(service, host, status=None, cache_hit=False,
                              ok=False, self_throttled=self_throttled)
        _record_fetch_failure()
        return entry

    if on_response is not None:
        try:
            on_response(resp)
        except Exception:
            pass  # Beobachtungshaken darf den Abruf NIE beeintraechtigen

    # Issue #1948 (S1, AC-2/AC-7): roher Eingangs-Datensatz der ECHTEN
    # Antwort -- nur geparster Body plus Service/Host/Cache-Key/Status,
    # KEINE Header/Auth (strukturell nicht uebergeben).
    capture_id: Optional[str] = None
    try:
        capture_id = alert_input_capture.capture_system(
            branch="official_alert", source_key=service,
            payload={
                "body": resp.json(), "service": service, "host": host,
                "cache_key": cache_key, "status": resp.status_code,
            },
        )
    except Exception as e:
        # Ein gescheiterter Mitschnitt hinterlaesst KEINE Kennung -- eine
        # falsche Zuordnung ist schlimmer als keine (Issue #1944, AC-4).
        capture_id = None
        log.warning("%s: Eingangs-Mitschnitt fehlgeschlagen (%s)", service, e)

    status = resp.status_code
    if status == 429:
        retry_after = _parse_retry_after(resp.headers)
        backoff = max(retry_after or 0.0, success_ttl)
        log.warning(
            "%s: HTTP 429 (Kontingent erschöpft) — Rückzug für %.0fs "
            "(Retry-After=%s)",
            service, backoff, retry_after,
        )
        entry = _store_entry(cache, cache_key, data=None, fetched_at=now, ttl=backoff,
                     capture_id=capture_id)
        log_warn_service_call(service, host, status=429, cache_hit=False,
                              retry_after=retry_after, ok=False)
        _record_fetch_failure()
        return entry

    if not_covered_statuses is not None and status in not_covered_statuses:
        # Issue #1397 S2a: "nicht zustaendig" ist KEIN Ausfall -- kein
        # _record_fetch_failure(), lange Erfolgs-TTL (Staatsgrenzen bewegen
        # sich nicht), Egress-Zeile behaelt den echten Statuscode.
        log.debug(
            "%s: HTTP %s -- ausserhalb des Zustaendigkeitsbereichs, kein Ausfall",
            service, status,
        )
        neutral_value: Any = {}
        entry = _store_entry(cache, cache_key, data=neutral_value, fetched_at=now,
                     ttl=not_covered_ttl, capture_id=capture_id)
        if not_covered_ttl != WARN_NOT_COVERED_TTL:
            entry["not_covered"] = True  # #1441: Treffer bleibt "nicht zustaendig"
        # Issue #1422 S1: "nicht zustaendig" ist fachlich ein ERFOLG (ok=True),
        # auch wenn der Statuscode 404 sonst ein Fehlschlag waere.
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=True)
        mark_not_covered()  # Issue #1681
        return entry

    if status >= 400:
        log.warning("%s-Abruf fehlgeschlagen (%s, HTTP %s)", service, host, status)
        entry = _store_entry(cache, cache_key, data=None, fetched_at=now,
                     ttl=failure_ttl, capture_id=capture_id)
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=False)
        _record_fetch_failure()
        return entry

    try:
        data = parse_fn(resp)
    except Exception:
        log.warning("%s-Abruf fehlgeschlagen (%s, Parse)", service, host, exc_info=True)
        entry = _store_entry(cache, cache_key, data=None, fetched_at=now,
                     ttl=failure_ttl, capture_id=capture_id)
        log_warn_service_call(service, host, status=status, cache_hit=False, ok=False)
        _record_fetch_failure()
        return entry

    entry = _store_entry(cache, cache_key, data=data, fetched_at=now,
                 ttl=success_ttl, capture_id=capture_id)
    log_warn_service_call(service, host, status=status, cache_hit=False, ok=True)
    return entry
