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
# Umbau entfernt — das neue Verhalten deckt AC-1 (test_meteoalarm_source.py::
# test_ttl_ist_dreissig_minuten) und AC-2/AC-8 (Cache-Hit ohne echten Call)
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

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
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

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
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

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
# Issue #1397 Scheibe S1b — optionale RateLimitRetryPolicy: MeteoAlarm bremst
# Index-Seiten kurzzeitig aus (kein Retry-After, aber x-ratelimit-reset als
# Unix-Sekunden). cached_fetch() bekommt eine OPT-IN-Wiederholung; OHNE das
# neue Argument (Vigilance/GeoSphere/Météo-Forêts/Massif) bleibt das
# Verhalten bit-identisch zum Bestand.
# ---------------------------------------------------------------------------

def test_429_retry_with_ratelimit_reset_succeeds_no_partial_outage(tmp_path, monkeypatch):
    """GIVEN eine aktive RateLimitRetryPolicy und ein 429 mit
    ``x-ratelimit-reset`` auf den ERSTEN Versuch, WHEN ``cached_fetch()``
    erneut aufruft, THEN liefert der zweite (200er) Versuch das Ergebnis --
    kein Ausfall, und die Wartezeit wird exakt aus ``reset - jetzt``
    berechnet (injizierte Fake-Uhr/-Sleep, kein echtes Warten)."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
    )
    responses = [
        httpx.Response(429, headers={"x-ratelimit-reset": "1000"}),
        httpx.Response(200, json={"features": ["seite-2"]}),
    ]
    calls: list[int] = []

    def _request() -> httpx.Response:
        calls.append(1)
        return responses[len(calls) - 1]

    sleeps: list[float] = []
    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3,
        sleep_fn=sleeps.append,
        wall_clock_fn=lambda: 998.0,  # 2s vor dem Reset-Zeitpunkt
    )

    result = warn_egress.cached_fetch(
        cache={},
        cache_key="AT:p2",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(1000.0),
        rate_limit_retry=policy,
    )

    assert len(calls) == 2, (
        f"429 dann 200 muss GENAU EINE Wiederholung ausloesen, war {len(calls)} Aufrufe"
    )
    assert result == {"features": ["seite-2"]}, (
        f"Nach erfolgreicher Wiederholung muss die 200er-Antwort geliefert werden, war {result!r}"
    )
    assert sleeps == [2.0], (
        f"Wartezeit muss aus reset(1000) - jetzt(998) = 2.0s berechnet werden, war {sleeps!r}"
    )


def test_429_exhaustion_all_attempts_stays_unavailable(tmp_path, monkeypatch):
    """DARF NICHT AUFGEWEICHT WERDEN: GIVEN JEDER Versuch bis ``max_attempts``
    liefert 429, WHEN ``cached_fetch()`` sie verarbeitet, THEN bleibt es beim
    heutigen Ausfall-Verhalten -- ``None``, Cache-Eintrag mit dem ueblichen
    Backoff ``max(retry_after, success_ttl)``, KEIN endloses Wiederholen."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
    )
    calls: list[int] = []

    def _request() -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"x-ratelimit-reset": "1000"})

    sleeps: list[float] = []
    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3, sleep_fn=sleeps.append, wall_clock_fn=lambda: 998.0,
    )
    cache: dict = {}
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT:p2",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
        rate_limit_retry=policy,
    )

    assert result is None, f"Erschoepfte Versuche muessen Ausfall bleiben, war {result!r}"
    assert len(calls) == 3, f"max_attempts=3 muss genau 3 Versuche ausloesen, war {len(calls)}"
    assert len(sleeps) == 2, f"zwischen 3 Versuchen wird genau zweimal gewartet, war {sleeps!r}"
    assert cache["AT:p2"]["ttl"] == warn_egress.WARN_SUCCESS_TTL, (
        f"Backoff nach Erschoepfung bleibt der bestehende max(retry_after, success_ttl), "
        f"war {cache['AT:p2']['ttl']}"
    )


def test_429_retry_attempts_each_append_jsonl_line(tmp_path, monkeypatch):
    """Adversary-Fund (Issue #1397 S1c-Runde): ein 429-Zwischenversuch ist
    ein ECHTER Abruf gegen die API und muss im Egress-Zaehler auftauchen --
    sonst ist der Zaehler kein verlaesslicher Verbrauchs-Nachweis mehr.
    GIVEN 3 Versuche liefern durchgehend 429 (kurzer Reset-Abstand, also
    Kurzzeit-Bremse), WHEN ``cached_fetch()`` sie verarbeitet, THEN stehen
    GENAU 3 jsonl-Zeilen (status=429, cache_hit=false) in der Zaehler-Datei
    -- ALLE DREI mit dem aus ``x-ratelimit-reset`` ermittelten Wartewert als
    ``retry_after`` (auch der finale, erschoepfte Versuch: Tageskontingent-
    Fund, Punkt 3 -- der Zaehler soll den Reset-Zeitpunkt zeigen, auch ohne
    literalen ``Retry-After``-Header)."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

    def _request() -> httpx.Response:
        return httpx.Response(429, headers={"x-ratelimit-reset": "1000"})

    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3, sleep_fn=lambda _s: None, wall_clock_fn=lambda: 998.0,
    )
    warn_egress.cached_fetch(
        cache={},
        cache_key="AT:p2",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
        rate_limit_retry=policy,
    )

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3, (
        f"3 Versuche muessen 3 Zaehler-Zeilen ergeben (jeder Zwischenversuch ist ein "
        f"echter Abruf), war {len(lines)}"
    )
    records = [json.loads(ln) for ln in lines]
    for rec in records:
        assert rec["status"] == 429
        assert rec["cache_hit"] is False
    # Alle drei Zeilen tragen den aus x-ratelimit-reset ermittelten Wartewert
    # (reset(1000) - wall_clock(998) = 2.0s) -- auch die dritte (finaler,
    # erschoepfter 429-Zweig ohne literalen Retry-After-Header).
    assert records[0]["retry_after"] == 2.0
    assert records[1]["retry_after"] == 2.0
    assert records[2]["retry_after"] == 2.0, (
        f"finaler 429-Zweig muss ohne Retry-After-Header auf den "
        f"x-ratelimit-reset-Wert zurueckfallen, war {records[2]['retry_after']!r}"
    )


def test_ratelimit_wait_is_capped_for_far_future_reset():
    """GIVEN ein ``x-ratelimit-reset`` absurd weit in der Zukunft, WHEN
    ``RateLimitRetryPolicy.wait_seconds()`` die Wartezeit berechnet, THEN
    wird sie auf ``max_wait_seconds`` gedeckelt -- der synchrone Sendeweg darf
    dadurch nicht minutenlang haengen."""
    from services.official_alerts import warn_egress

    policy = warn_egress.RateLimitRetryPolicy(max_wait_seconds=8.0, wall_clock_fn=lambda: 1000.0)
    headers = httpx.Headers({"x-ratelimit-reset": "999999999"})
    wait = policy.wait_seconds(headers)
    assert wait == 8.0, f"Wartezeit muss auf max_wait_seconds gedeckelt werden, war {wait}"


def test_ratelimit_wait_falls_back_to_default_without_readable_header():
    """GIVEN ``x-ratelimit-reset`` fehlt oder ist unlesbar, WHEN
    ``RateLimitRetryPolicy.wait_seconds()`` aufgerufen wird, THEN greift ein
    fester Abstand (``default_wait_seconds``) -- kein Absturz."""
    from services.official_alerts import warn_egress

    policy = warn_egress.RateLimitRetryPolicy(default_wait_seconds=4.0, wall_clock_fn=lambda: 1000.0)
    assert policy.wait_seconds(httpx.Headers({})) == 4.0
    assert policy.wait_seconds(httpx.Headers({"x-ratelimit-reset": "nicht-lesbar"})) == 4.0
    assert policy.wait_seconds(None) == 4.0


def test_429_without_rate_limit_retry_param_stays_unchanged_for_other_services(
    tmp_path, monkeypatch
):
    """Regressionsnachweis Issue #1397 S1b: ruft ``cached_fetch()`` OHNE
    ``rate_limit_retry`` auf -- genau wie Vigilance/GeoSphere/Météo-Forêts/
    Massif es weiterhin tun. GIVEN eine 429-Antwort mit ``Retry-After: 45``,
    WHEN ``cached_fetch()`` sie verarbeitet, THEN wird ``request_fn()``
    GENAU EINMAL aufgerufen (keine Wiederholung) und der Backoff bleibt
    ``max(retry_after, success_ttl)`` wie vor S1b."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        f"Ohne rate_limit_retry darf request_fn() genau einmal aufgerufen werden, war {len(calls)}"
    )
    assert cache["FR"]["ttl"] == max(45.0, warn_egress.WARN_SUCCESS_TTL), (
        f"Backoff-Formel fuer die anderen Dienste bleibt unveraendert, war {cache['FR']['ttl']}"
    )


# ---------------------------------------------------------------------------
# Tageskontingent-Fund (Issue #1397 S1c-Nachbesserung, Produktion 2026-07-27
# 10:37 UTC): MeteoAlarm liefert bei erschoepftem TAGESKONTINGENT ebenfalls
# 429, aber mit ``x-ratelimit-reset`` ~86400s in der Zukunft statt weniger
# Sekunden. Wiederholen waere hier verschenkt (das Kontingent bleibt bis zum
# Reset erschoepft) -- die Unterscheidung laeuft ueber den Abstand des
# Reset-Zeitpunkts, NICHT ueber den Statuscode.
# ---------------------------------------------------------------------------

def test_is_long_lived_unterscheidet_kurzzeit_von_tageskontingent():
    """GIVEN verschiedene ``x-ratelimit-reset``-Abstaende, WHEN
    ``is_long_lived()`` sie bewertet, THEN gilt: Abstand <=
    ``short_wait_ceiling_seconds`` -> Kurzzeit (``False``), Abstand darueber
    -> Tageskontingent (``True``), fehlender/unlesbarer Header -> Kurzzeit-
    Annahme (``False``, ohne Reset-Zeitpunkt nicht als Tageskontingent
    erkennbar)."""
    from services.official_alerts import warn_egress

    policy = warn_egress.RateLimitRetryPolicy(
        short_wait_ceiling_seconds=60.0, wall_clock_fn=lambda: 1000.0,
    )

    assert policy.is_long_lived(httpx.Headers({"x-ratelimit-reset": "1002"})) is False, (
        "2s Abstand ist eindeutig Kurzzeit-Bremse"
    )
    assert policy.is_long_lived(httpx.Headers({"x-ratelimit-reset": "1060"})) is False, (
        "genau an der Grenze (60s) gilt noch als Kurzzeit"
    )
    assert policy.is_long_lived(httpx.Headers({"x-ratelimit-reset": "1061"})) is True, (
        "1s ueber der Grenze gilt als Tageskontingent"
    )
    assert policy.is_long_lived(httpx.Headers({"x-ratelimit-reset": str(1000 + 86399)})) is True, (
        "belegter Produktions-Fall (86399s) muss als Tageskontingent erkannt werden"
    )
    assert policy.is_long_lived(httpx.Headers({})) is False, (
        "fehlender Header -> Kurzzeit-Annahme (kein Reset-Zeitpunkt erkennbar)"
    )
    assert policy.is_long_lived(None) is False


def test_long_lived_429_wird_nicht_wiederholt(tmp_path, monkeypatch):
    """Tageskontingent-Fund: GIVEN ein 429 mit ``x-ratelimit-reset`` weit in
    der Zukunft (belegter Fall: 86399s), WHEN ``cached_fetch()`` es
    verarbeitet, THEN wird ``request_fn()`` GENAU EINMAL aufgerufen (KEINE
    Wiederholung, jeder Versuch waere gegen ein erschoepftes Tageskontingent
    verschenkt) UND der Rueckzug reicht bis zum Reset-Zeitpunkt (nicht die
    kurze warngerechte success_ttl)."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
    )
    calls: list[int] = []

    def _request() -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"x-ratelimit-reset": "87399"})

    sleeps: list[float] = []
    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3, sleep_fn=sleeps.append, wall_clock_fn=lambda: 1000.0,
    )
    cache: dict = {}
    result = warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT:p1",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
        rate_limit_retry=policy,
    )

    assert result is None
    assert len(calls) == 1, (
        f"Tageskontingent darf NICHT wiederholt werden -- request_fn() genau einmal, war {len(calls)}"
    )
    assert sleeps == [], "kein Zwischenversuch bedeutet keine Wartezeit vor einer Wiederholung"
    expected_backoff = 87399.0 - 1000.0  # 86399s -- reicht bis zum Reset-Zeitpunkt
    assert cache["AT:p1"]["ttl"] == expected_backoff, (
        f"Rueckzug muss bis zum Reset-Zeitpunkt reichen (nicht die kurze success_ttl), "
        f"war {cache['AT:p1']['ttl']}"
    )


def test_long_lived_429_backoff_wird_gedeckelt(tmp_path, monkeypatch):
    """GIVEN ein ``x-ratelimit-reset`` absurd weit in der Zukunft (weiter
    als 24h), WHEN ``cached_fetch()`` den Rueckzug berechnet, THEN wird er
    auf ``long_backoff_cap_seconds`` gedeckelt -- ein einzelner falscher/
    manipulierter Header darf den Dienst nicht tagelang lahmlegen."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
    )

    def _request() -> httpx.Response:
        return httpx.Response(429, headers={"x-ratelimit-reset": str(10_000_000)})

    policy = warn_egress.RateLimitRetryPolicy(
        long_backoff_cap_seconds=24 * 3600.0, wall_clock_fn=lambda: 0.0,
    )
    cache: dict = {}
    warn_egress.cached_fetch(
        cache=cache,
        cache_key="AT:p1",
        service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
        rate_limit_retry=policy,
    )

    assert cache["AT:p1"]["ttl"] == 24 * 3600.0, (
        f"Rueckzug muss auf long_backoff_cap_seconds gedeckelt werden, war {cache['AT:p1']['ttl']}"
    )


def test_long_lived_429_counter_zeigt_reset_zeitpunkt(tmp_path, monkeypatch):
    """Tageskontingent-Fund Punkt 3: GIVEN ein Tageskontingent-429 (kein
    literaler ``Retry-After``-Header), WHEN die Zaehler-Zeile geschrieben
    wird, THEN traegt sie den aus ``x-ratelimit-reset`` ermittelten
    (gedeckelten) Wert als ``retry_after`` -- morgen muss aus dem Zaehler
    ablesbar sein, WANN das Tageskontingent zuschlug."""
    from services.official_alerts import warn_egress

    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

    def _request() -> httpx.Response:
        return httpx.Response(429, headers={"x-ratelimit-reset": "87399"})

    policy = warn_egress.RateLimitRetryPolicy(wall_clock_fn=lambda: 1000.0)
    warn_egress.cached_fetch(
        cache={},
        cache_key="AT:p1",
        service="meteoalarm:AT:p1",
        host="api.meteoalarm.org",
        request_fn=_request,
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(5000.0),
        rate_limit_retry=policy,
    )

    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["service"] == "meteoalarm:AT:p1", (
        "Land+Seite muessen im service-Feld unterscheidbar sein (Punkt 3)"
    )
    assert rec["retry_after"] == 86399.0, (
        f"Zaehler muss den ermittelten Reset-Abstand zeigen, war {rec['retry_after']!r}"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)

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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
        warn_egress, "WARN_CALLS_PATH", tmp_path / "warn_service_calls.jsonl"
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
