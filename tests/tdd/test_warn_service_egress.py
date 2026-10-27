"""TDD RED — Issue #1348 (Scheibe 2a von #1337): geteilter Warn-Dienst-Egress-Helfer.

SPEC: docs/specs/modules/warn_service_consumption.md (AC-1 bis AC-10)
Kontext: docs/context/feat-1348-warn-consumption.md

Diese Datei deckt den geteilten Helfer ``services.official_alerts.warn_egress``
ab (Cache + 429-bewusster Rückzug + Egress-Zähler). Der Helfer existiert in der
RED-Phase noch NICHT -> alle ``from services.official_alerts import warn_egress``
laufen bewusst in einen ``ImportError`` (korrektes RED). Die Importe stehen
FUNKTIONS-lokal, damit die Sammlung (collection) durchläuft und nur die einzelnen
AC-Tests rot werden, nicht das ganze Modul.

Kein Mock-Theater (CLAUDE.md Test-Politik):
- Der "Netz-Sentinel" ist ein echtes ``request_fn``, das bei jedem Aufruf eine
  Sentinel-Exception wirft (analog ``tests/tdd/test_egress_guard.py``). Wird es
  bei einem Cache-Hit aufgerufen, fliegt die Exception = Beweis für einen
  ungewollten echten Call. Kein ``Mock()``/``patch()``/``MagicMock``.
- 429-Antworten werden als ECHTE ``httpx.Response(429, ...)``-Objekte real
  konstruiert (kein Netz, kein Mock der HTTP-Bibliothek).
- Die jsonl-Zähler-Datei wird real geschrieben (temp-Pfad via ``monkeypatch``)
  und real zurückgelesen.
- Zeit wird über den ``clock``-Parameter injiziert (Fake-Clock) — kein echtes
  Warten.

Die erste Funktion ist ein CHARAKTERISIERUNGS-TEST des HEUTIGEN Zustands und
bewusst GRÜN (Regressions-Anker vor dem Umbau) — siehe Docstring dort.
"""
from __future__ import annotations

import json

import httpx


# ---------------------------------------------------------------------------
# Netz-Sentinel: ein echtes request_fn, das bei Aufruf wirft. Beweist "kein
# echter Call" bei Cache-Hit-Pfaden (kein Mock — reale Funktion mit Nebenwirkung
# = Exception).
# ---------------------------------------------------------------------------

class _NetSentinelReached(Exception):
    """Wird geworfen, sobald ``request_fn`` fälschlich aufgerufen wird — beweist
    einen ungewollten echten HTTP-Call ohne ein einziges gesendetes Byte."""


def _net_sentinel() -> httpx.Response:
    raise _NetSentinelReached("request_fn wurde aufgerufen — Cache-Hit erwartet, kein echter Call")


def _fixed_clock(value: float):
    """Deterministische Fake-Clock: gibt immer denselben Zeitwert zurück."""
    return lambda: value


# ---------------------------------------------------------------------------
# Hinweis: Der ursprüngliche Charakterisierungs-Test (Anker CACHE_TTL==300.0,
# GRÜN gegen den Vor-Umbau-Stand) hat seinen Zweck erfüllt und wurde nach dem
# Umbau entfernt — das neue Verhalten deckt AC-1 (seit #2266
# test_warn_journal_felder.py::test_ac8_feed_ttl_bleibt_1800_sekunden) und
# AC-2/AC-8 (Cache-Hit ohne echten Call)
# vollständig ab.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AC-2 — Cache-Hit im TTL-Fenster löst KEINEN echten Call aus (Netz-Sentinel)
# ---------------------------------------------------------------------------

def test_cache_hit_within_ttl_makes_no_real_call(tmp_path, monkeypatch):
    """AC-2: GIVEN ein Cache-Eintrag wurde vor <1800s erfolgreich gesetzt, WHEN
    ``cached_fetch()`` erneut mit demselben ``cache_key`` aufgerufen wird, THEN
    wird ``request_fn()`` NICHT aufgerufen (Netz-Sentinel-Beweis) und die
    gecachten Daten werden zurückgegeben."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    cache = {
        "AT": {
            "data": {"features": []},
            "fetched_at": 1000.0,
            "ttl": warn_egress.WARN_SUCCESS_TTL,
        }
    }
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_net_sentinel,  # wirft bei jedem Aufruf
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),  # delta 0 < TTL -> Treffer
    )
    assert result == {"features": []}, (
        f"Cache-Hit muss die gecachten Daten zurückgeben, war {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Cache-Miss nach TTL löst echten Call aus (Fake-Clock vorgespult)
# ---------------------------------------------------------------------------

def test_cache_miss_after_ttl_triggers_real_call(tmp_path, monkeypatch):
    """AC-3: GIVEN ein Cache-Eintrag ist laut injizierter Fake-Clock älter als
    1800s, WHEN ``cached_fetch()`` erneut aufgerufen wird, THEN wird
    ``request_fn()`` tatsächlich aufgerufen (echter Cache-Miss nach Ablauf)."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    calls: list[int] = []

    def _request() -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"features": ["frisch"]})

    cache = {
        "AT": {
            "data": {"features": ["alt"]},
            "fetched_at": 0.0,
            "ttl": warn_egress.WARN_SUCCESS_TTL,
        }
    }
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(warn_egress.WARN_SUCCESS_TTL + 100.0),  # abgelaufen
    )
    assert calls == [1], "Nach TTL-Ablauf muss request_fn() genau einmal aufgerufen werden"
    assert result == {"features": ["frisch"]}, (
        f"Cache-Miss muss die frisch geparsten Daten liefern, war {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — 429 mit Retry-After: 120 -> Backoff max(120, 1800) = 1800
# ---------------------------------------------------------------------------

def test_429_with_retry_after_sets_backoff(tmp_path, monkeypatch):
    """AC-4: GIVEN eine echte HTTP-429-Antwort mit ``Retry-After: 120``, WHEN
    ``cached_fetch()`` sie verarbeitet, THEN wird das Backoff-Fenster auf
    ``max(120, 1800) = 1800`` gesetzt (Retry-After respektiert, nie kürzer als
    die Erfolgs-TTL) und als Cache-Eintrag-TTL hinterlegt."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    def _request() -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "120"})

    cache: dict = {}
    warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
    )
    entry = cache["AT"]
    assert entry["ttl"] == max(120.0, warn_egress.WARN_SUCCESS_TTL), (
        f"429 mit Retry-After:120 muss Backoff max(120, 1800) setzen, war {entry['ttl']}"
    )
    assert entry["ttl"] == 1800.0


# ---------------------------------------------------------------------------
# AC-5 — 429 ohne Retry-After -> Backoff == WARN_SUCCESS_TTL (1800)
# ---------------------------------------------------------------------------

def test_429_without_retry_after_defaults_to_success_ttl(tmp_path, monkeypatch):
    """AC-5: GIVEN eine HTTP-429-Antwort OHNE ``Retry-After``-Header, WHEN
    ``cached_fetch()`` sie verarbeitet, THEN wird das Backoff-Fenster auf
    ``WARN_SUCCESS_TTL`` (1800s) gesetzt — kein 15-Minuten-Dauerfeuer."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    def _request() -> httpx.Response:
        return httpx.Response(429)

    cache: dict = {}
    warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
    )
    entry = cache["AT"]
    assert entry["ttl"] == warn_egress.WARN_SUCCESS_TTL, (
        f"429 ohne Retry-After muss Backoff == WARN_SUCCESS_TTL (1800) setzen, war {entry['ttl']}"
    )
    assert entry["ttl"] == 1800.0


# ---------------------------------------------------------------------------
# AC-6 — 429 wird laut geloggt (WARNING mit "429" + Backoff-Dauer)
# ---------------------------------------------------------------------------

def test_429_logs_loudly(caplog, tmp_path, monkeypatch):
    """AC-6: GIVEN eine HTTP-429-Antwort tritt auf, WHEN der Fehlerpfad
    durchlaufen wird, THEN enthält ein WARNING-Log-Eintrag explizit den Text
    "429" UND die berechnete Backoff-Dauer (1800), unterscheidbar von der
    generischen Fehler-Meldung anderer Statuscodes."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    def _request() -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "120"})

    cache: dict = {}
    with caplog.at_level("WARNING"):
        warn_egress.cached_fetch(
            cache=cache,
            cache_key="AT",
            service="meteoalarm",
            host="api.meteoalarm.org",
            request_fn=_request,
            parse_fn=lambda r: r.json(),
            clock=_fixed_clock(5000.0),
        )

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("429" in m for m in warnings), (
        f"Ein WARNING-Log muss explizit '429' enthalten, Records: {warnings}"
    )
    assert any("1800" in m for m in warnings), (
        f"Ein WARNING-Log muss die berechnete Backoff-Dauer (1800) enthalten, Records: {warnings}"
    )


# ---------------------------------------------------------------------------
# AC-7 — echter Call schreibt reale jsonl-Zeile (cache_hit=false)
# ---------------------------------------------------------------------------

def test_real_call_appends_jsonl_line(tmp_path, monkeypatch):
    """AC-7: GIVEN ein Cache-Miss löst einen echten HTTP-Call aus, WHEN die
    Antwort verarbeitet ist, THEN wird eine REALE jsonl-Zeile mit
    ``service, host, status, cache_hit=false`` an die Zähler-Datei angehängt
    (temp-Pfad via monkeypatch, danach real zurückgelesen)."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", jsonl)

    def _request() -> httpx.Response:
        return httpx.Response(200, json={"features": []})

    cache: dict = {}
    warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
    )

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"Genau eine jsonl-Zeile erwartet, war {len(lines)}"
    rec = json.loads(lines[0])
    assert rec["service"] == "meteoalarm"
    assert rec["host"] == "api.meteoalarm.org"
    assert rec["status"] == 200
    assert rec["cache_hit"] is False


# ---------------------------------------------------------------------------
# AC-8 — Cache-Hit schreibt jsonl-Zeile (cache_hit=true, status=null) OHNE Call
# ---------------------------------------------------------------------------

def test_cache_hit_appends_jsonl_line_without_call(tmp_path, monkeypatch):
    """AC-8: GIVEN ein Cache-Hit innerhalb der TTL, WHEN ``cached_fetch()``
    aufgerufen wird, THEN wird eine jsonl-Zeile mit ``cache_hit=true,
    status=null`` angehängt UND per Netz-Sentinel bewiesen, dass kein echter
    Call erfolgte (request_fn würde sonst werfen)."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", jsonl)

    cache = {
        "AT": {
            "data": {"features": []},
            "fetched_at": 1000.0,
            "ttl": warn_egress.WARN_SUCCESS_TTL,
        }
    }
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_net_sentinel,  # wirft, falls ein echter Call versucht wird
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
    )
    assert result == {"features": []}

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"Genau eine jsonl-Zeile erwartet, war {len(lines)}"
    rec = json.loads(lines[0])
    assert rec["cache_hit"] is True
    assert rec["status"] is None, (
        f"Cache-Hit-Zeile muss status=null tragen (kein echter Call), war {rec['status']!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 — 429-Zeile im Zähler: status=429, retry_after gefüllt bzw. null
# ---------------------------------------------------------------------------

def test_429_marked_in_jsonl(tmp_path, monkeypatch):
    """AC-9: GIVEN ein 429 tritt auf, WHEN die Zähler-Zeile geschrieben wird,
    THEN enthält sie ``status=429`` und ``retry_after`` (Sekundenwert bei
    vorhandenem Header, ``null`` bei fehlendem)."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", jsonl)

    # (1) 429 MIT Retry-After -> retry_after gefüllt.
    warn_egress.cached_fetch(
        cache={},
        cache_key="AT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.Response(429, headers={"Retry-After": "120"}),
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
    )
    # (2) 429 OHNE Retry-After -> retry_after == null.
    warn_egress.cached_fetch(
        cache={},
        cache_key="IT",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.Response(429),
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
    )

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2, f"Zwei 429-Zeilen erwartet, war {len(lines)}"
    with_header = json.loads(lines[0])
    without_header = json.loads(lines[1])

    assert with_header["status"] == 429
    assert with_header["retry_after"] == 120, (
        f"429 mit Header muss retry_after=120 tragen, war {with_header['retry_after']!r}"
    )
    assert without_header["status"] == 429
    assert without_header["retry_after"] is None, (
        f"429 ohne Header muss retry_after=null tragen, war {without_header['retry_after']!r}"
    )


# ---------------------------------------------------------------------------
# Issue #2266: die fruehere optionale 429-Wiederholung (Issue #1397 S1b/S1c,
# einziger Nutzer war die MeteoAlarm-EDR-Klasse) ist zurueckgebaut -- samt
# ihrer Tests. Der folgende Regressionsnachweis bleibt: ein 429 loest GENAU
# EINEN Abruf aus, der Backoff bleibt max(retry_after, success_ttl).
# ---------------------------------------------------------------------------

def test_429_is_never_retried_and_keeps_backoff_formula(
    tmp_path, monkeypatch
):
    """Regressionsnachweis (Issue #1397 S1b, seit #2266 fuer ALLE Dienste):
    GIVEN eine 429-Antwort mit ``Retry-After: 45``,
    WHEN ``cached_fetch()`` sie verarbeitet, THEN wird ``request_fn()``
    GENAU EINMAL aufgerufen (keine Wiederholung) und der Backoff bleibt
    ``max(retry_after, success_ttl)``."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    calls: list[int] = []

    def _request() -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "45"})

    cache: dict = {}
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="FR",
        service="vigilance",
        host="vigilance-api.meteofrance.fr",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
    )

    assert result is None
    assert len(calls) == 1, (
        f"Ein 429 darf request_fn() genau einmal aufrufen, war {len(calls)}"
    )
    assert cache["FR"]["ttl"] == max(45.0, warn_egress.WARN_SUCCESS_TTL), (
        f"Backoff-Formel fuer die anderen Dienste bleibt unveraendert, war {cache['FR']['ttl']}"
    )


# ---------------------------------------------------------------------------
# Issue #1397 S2a — optionaler ``not_covered_statuses``-Parameter: bestimmte
# Statuscodes (z.B. ZAMG-404 ausserhalb Oesterreichs) gelten als "nicht
# zustaendig", nicht als Fehlschlag. OHNE das Argument (Vigilance/Massif/
# Météo-Forêts/MeteoAlarm) bleibt cached_fetch() BIT-IDENTISCH zum Bestand.
# ---------------------------------------------------------------------------

def test_not_covered_status_is_success_not_failure(tmp_path, monkeypatch):
    """GIVEN eine echte HTTP-404-Antwort UND ``not_covered_statuses={404}``,
    WHEN ``cached_fetch()`` sie verarbeitet, THEN liefert sie einen neutralen
    Wert (kein ``None``) statt eines Fehlschlags, und der Eintrag wird als
    ERFOLG mit ``WARN_NOT_COVERED_TTL`` (24h) gecacht."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    def _request() -> httpx.Response:
        return httpx.Response(404)

    cache: dict = {}
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="46.85,9.53",
        service="geosphere_warn",
        host="warnungen.zamg.at",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
        not_covered_statuses=frozenset({404}),
    )
    assert result is not None, (
        "Ein 'nicht zustaendig'-Status darf NICHT wie ein Fehlschlag als "
        "None zurueckgegeben werden"
    )
    entry = cache["46.85,9.53"]
    assert entry["data"] is not None, (
        "gecachte Daten duerfen nicht None sein, sonst gilt der naechste "
        "Cache-Treffer faelschlich wieder als Fehlschlag"
    )
    assert entry["ttl"] == warn_egress.WARN_NOT_COVERED_TTL == 24 * 3600.0


def test_not_covered_status_does_not_set_failure_marker(tmp_path, monkeypatch):
    """GIVEN ``observe_fetch_failure()`` beobachtet den Aufruf, WHEN ein
    'nicht zustaendig'-Status auftritt, THEN bleibt ``failed`` False -- der
    #1348-Ausfall-Marker (der ``unavailable=True`` fuer die gesamte
    Registry-Abfrage ausloesen wuerde) wird NICHT gesetzt."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )

    with warn_egress.observe_fetch_failure() as status:
        warn_egress.cached_fetch(
            cache={},
            cache_key="AT",
            service="geosphere_warn",
            host="warnungen.zamg.at",
            request_fn=lambda: httpx.Response(404),
            parse_fn=lambda r: r.json(),
            clock=_fixed_clock(1000.0),
            not_covered_statuses=frozenset({404}),
        )
    assert status["failed"] is False, (
        "Ein 'nicht zustaendig'-404 darf den Fehlschlag-Marker NICHT setzen"
    )


def test_not_covered_status_egress_line_keeps_real_status_code(tmp_path, monkeypatch):
    """GIVEN ein 404 als 'nicht zustaendig' behandelt wird, WHEN die
    Zaehler-Zeile geschrieben wird, THEN traegt sie weiterhin den ECHTEN
    Statuscode 404 (keine Verschleierung des Egress-Nachweises) UND
    ``cache_hit=False`` (echter Call fand statt)."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", jsonl)

    warn_egress.cached_fetch(
        cache={},
        cache_key="AT",
        service="geosphere_warn",
        host="warnungen.zamg.at",
        request_fn=lambda: httpx.Response(404),
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
        not_covered_statuses=frozenset({404}),
    )

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["status"] == 404, "Egress-Zeile muss den echten Statuscode tragen"
    assert rec["cache_hit"] is False


def test_not_covered_cache_hit_stays_success_on_second_call(tmp_path, monkeypatch):
    """GIVEN ein gecachter 'nicht zustaendig'-Eintrag, WHEN ``cached_fetch()``
    innerhalb der 24h-TTL erneut mit demselben ``cache_key`` aufgerufen wird,
    THEN wird ``request_fn()`` NICHT erneut aufgerufen (Netz-Sentinel) und der
    Cache-Treffer gilt weiterhin als Erfolg, nicht als Fehlschlag."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    cache = {
        "AT": {"data": {}, "fetched_at": 1000.0, "ttl": warn_egress.WARN_NOT_COVERED_TTL}
    }
    with warn_egress.observe_fetch_failure() as status:
        result = warn_egress.cached_fetch(
            cache=cache,
            cache_key="AT",
            service="geosphere_warn",
            host="warnungen.zamg.at",
            request_fn=_net_sentinel,
            parse_fn=lambda r: r.json(),
            clock=_fixed_clock(1000.0),
            not_covered_statuses=frozenset({404}),
        )
    assert result == {}
    assert status["failed"] is False


def test_other_statuses_stay_real_failures_with_not_covered_param_set(tmp_path, monkeypatch):
    """Gegenprobe: GIVEN ``not_covered_statuses={404}`` ist gesetzt, WHEN eine
    ANDERE Fehlerantwort (HTTP 500) auftritt, THEN bleibt es beim
    bestehenden Ausfall-Verhalten (``None``, Fehlschlag-Marker gesetzt,
    kurze ``failure_ttl``) -- der neue Parameter darf echte Ausfaelle nicht
    verschlucken."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    cache: dict = {}
    with warn_egress.observe_fetch_failure() as status:
        result = warn_egress.cached_fetch(
            cache=cache,
            cache_key="AT",
            service="geosphere_warn",
            host="warnungen.zamg.at",
            request_fn=lambda: httpx.Response(500),
            parse_fn=lambda r: r.json(),
            clock=_fixed_clock(1000.0),
            not_covered_statuses=frozenset({404}),
        )
    assert result is None
    assert status["failed"] is True
    assert cache["AT"]["ttl"] == warn_egress.WARN_FAILURE_TTL


def test_without_not_covered_param_404_stays_a_failure_like_before(tmp_path, monkeypatch):
    """Regressionsnachweis: OHNE ``not_covered_statuses`` (Standard ``None``,
    wie Vigilance/Massif/Météo-Forêts/MeteoAlarm es weiterhin aufrufen)
    bleibt ein 404 ein GEWOEHNLICHER Fehlschlag -- exakt wie vor #1397 S2a."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    cache: dict = {}
    with warn_egress.observe_fetch_failure() as status:
        result = warn_egress.cached_fetch(
            cache=cache,
            cache_key="AT",
            service="geosphere_warn",
            host="warnungen.zamg.at",
            request_fn=lambda: httpx.Response(404),
            parse_fn=lambda r: r.json(),
            clock=_fixed_clock(1000.0),
        )
    assert result is None
    assert status["failed"] is True
    assert cache["AT"]["ttl"] == warn_egress.WARN_FAILURE_TTL
