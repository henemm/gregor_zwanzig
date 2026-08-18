"""Regressions-Waechter — Issue #1944, AC-9: die Sonderpfade von
``cached_fetch()`` bleiben in ihrem beobachtbaren Verhalten unveraendert.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-9)

Diese Datei ist BEWUSST BEREITS GRUEN. Sie fixiert den Bestand VOR der
Herkunfts-Erweiterung, damit die Implementierung nicht unbemerkt daran
ruettelt: Rueckgabewert, TTL, die BISHERIGEN Schluessel des
Zwischenspeicher-Eintrags und die ``log_warn_service_call``-Argumente je
Sonderpfad.

Bewusst als Teilmengen-Pruefung formuliert (``>=`` auf den Schluesselnamen,
Feldvergleich auf den Werten): das neue ``"capture_id"``-Feld ist rein
additiv und darf hinzukommen -- aber kein bestehender Wert darf sich
aendern. Eine Gleichheitspruefung auf der Schluesselmenge waere nach der
Implementierung falsch rot.

Mock-frei: echte ``httpx.Response``-Objekte, echte Ausnahmen aus dem
``request_fn``-Seam, das Egress-Journal wird real geschrieben und real
zurueckgelesen (kein String-Check, ``json.loads`` je Zeile).
"""
from __future__ import annotations

import json

import httpx


def _fixed_clock(value: float):
    return lambda: value


def _journal(pfad) -> list[dict]:
    """Alle Egress-Zeilen, strukturell geladen."""
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]


def _bestandsfelder(eintrag: dict) -> dict:
    """Die drei Bestands-Schluessel des Zwischenspeicher-Eintrags."""
    assert {"data", "fetched_at", "ttl"} <= set(eintrag), (
        f"Bestands-Schluessel fehlen im Zwischenspeicher-Eintrag: {eintrag!r}"
    )
    return {k: eintrag[k] for k in ("data", "fetched_at", "ttl")}


class _NetzAusfall(Exception):
    """Echter Fehler aus dem ``request_fn``-Seam (kein Mock)."""


class _EigenerRueckzug(Exception):
    """Selbst auferlegter Rueckzug -- meldet sich ueber das Attribut, das
    ``cached_fetch()`` auswertet (Issue #1422 S1)."""

    self_throttled = True


def test_ac9_netzwerk_ausnahme_unveraendert(monkeypatch, tmp_path):
    """Netzwerkfehler: ``None`` zurueck, Fehlschlag-Eintrag mit
    ``failure_ttl``, Journal-Zeile ``status=None``/``cache_hit=False``/
    ``ok=False``/``self_throttled=False``."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    cache: dict = {}

    def _wirft() -> httpx.Response:
        raise _NetzAusfall("Verbindung abgebrochen")

    ergebnis = warn_egress.cached_fetch(
        cache=cache, cache_key="k-netz", service="meteoalarm",
        host="api.meteoalarm.org", request_fn=_wirft,
        parse_fn=lambda r: r.json(), clock=_fixed_clock(1000.0),
    )

    assert ergebnis is None
    assert _bestandsfelder(cache["k-netz"]) == {
        "data": None, "fetched_at": 1000.0, "ttl": warn_egress.WARN_FAILURE_TTL,
    }
    zeile = _journal(journal)[-1]
    assert (zeile["service"], zeile["host"]) == ("meteoalarm", "api.meteoalarm.org")
    assert (zeile["status"], zeile["cache_hit"], zeile["ok"], zeile["self_throttled"]) \
        == (None, False, False, False)


def test_ac9_selbst_auferlegter_rueckzug_unveraendert(monkeypatch, tmp_path):
    """``self_throttled``-Ausnahme: gleicher Fehlschlag-Pfad, aber die
    Journal-Zeile traegt ``self_throttled=True``."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    cache: dict = {}

    def _wirft() -> httpx.Response:
        raise _EigenerRueckzug("Tageskontingent selbst erschoepft")

    ergebnis = warn_egress.cached_fetch(
        cache=cache, cache_key="k-throttle", service="meteoalarm",
        host="api.meteoalarm.org", request_fn=_wirft,
        parse_fn=lambda r: r.json(), clock=_fixed_clock(1100.0),
    )

    assert ergebnis is None
    assert _bestandsfelder(cache["k-throttle"]) == {
        "data": None, "fetched_at": 1100.0, "ttl": warn_egress.WARN_FAILURE_TTL,
    }
    zeile = _journal(journal)[-1]
    assert (zeile["status"], zeile["cache_hit"], zeile["ok"], zeile["self_throttled"]) \
        == (None, False, False, True)


def test_ac9_gecachter_fehlschlag_unveraendert(monkeypatch, tmp_path):
    """Gecachter Fehlschlag (``data=None`` im TTL-Fenster): kein echter
    Abruf, ``None`` zurueck, Eintrag unangetastet, Journal-Zeile
    ``cache_hit=True``/``ok=False``. Zusaetzlich der Fehlschlag-Marker fuer
    ``observe_fetch_failure()``."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    vorher = {"data": None, "fetched_at": 1200.0, "ttl": warn_egress.WARN_FAILURE_TTL}
    cache: dict = {"k-cached-fail": dict(vorher)}

    def _verboten() -> httpx.Response:
        raise AssertionError("request_fn darf beim Cache-Treffer nicht laufen")

    with warn_egress.observe_fetch_failure() as status:
        ergebnis = warn_egress.cached_fetch(
            cache=cache, cache_key="k-cached-fail", service="meteoalarm",
            host="api.meteoalarm.org", request_fn=_verboten,
            parse_fn=lambda r: r.json(), clock=_fixed_clock(1230.0),
        )

    assert ergebnis is None
    assert status["failed"] is True, "Ein gecachter Fehlschlag bleibt 'nicht abrufbar'."
    assert _bestandsfelder(cache["k-cached-fail"]) == vorher
    zeile = _journal(journal)[-1]
    assert (zeile["status"], zeile["cache_hit"], zeile["ok"]) == (None, True, False)


def test_ac9_not_covered_status_unveraendert(monkeypatch, tmp_path):
    """``not_covered_statuses``: neutraler Erfolg ``{}``, lange TTL, KEIN
    Fehlschlag-Marker, Journal-Zeile mit echtem Statuscode und ``ok=True``."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    cache: dict = {}
    with warn_egress.observe_fetch_failure() as status:
        ergebnis = warn_egress.cached_fetch(
            cache=cache, cache_key="k-not-covered", service="geosphere",
            host="dataset.api.hub.geosphere.at",
            request_fn=lambda: httpx.Response(404, json={"detail": "outside"}),
            parse_fn=lambda r: r.json(), clock=_fixed_clock(1300.0),
            not_covered_statuses=frozenset({404}),
        )

    assert ergebnis == {}, "Neutraler Erfolgs-Wert bleibt {} (nicht None)."
    assert status["failed"] is False, "'Nicht zustaendig' ist KEIN Ausfall."
    assert _bestandsfelder(cache["k-not-covered"]) == {
        "data": {}, "fetched_at": 1300.0, "ttl": warn_egress.WARN_NOT_COVERED_TTL,
    }
    zeile = _journal(journal)[-1]
    assert (zeile["status"], zeile["cache_hit"], zeile["ok"]) == (404, False, True)


def test_ac9_erfolgspfad_und_429_rueckzug_unveraendert(monkeypatch, tmp_path):
    """Anker fuer die beiden verbleibenden Pfade: Erfolg (``success_ttl``,
    ``ok=True``) und terminales 429 (Rueckzug ``max(Retry-After,
    success_ttl)``, ``ok=False``)."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    body = {"features": []}
    cache: dict = {}
    erfolg = warn_egress.cached_fetch(
        cache=cache, cache_key="k-ok", service="meteoalarm", host="h",
        request_fn=lambda: httpx.Response(200, json=body),
        parse_fn=lambda r: r.json(), clock=_fixed_clock(1400.0),
    )
    assert erfolg == body
    assert _bestandsfelder(cache["k-ok"]) == {
        "data": body, "fetched_at": 1400.0, "ttl": warn_egress.WARN_SUCCESS_TTL,
    }
    assert (_journal(journal)[-1]["status"], _journal(journal)[-1]["ok"]) == (200, True)

    rueckzug = warn_egress.cached_fetch(
        cache=cache, cache_key="k-429", service="meteoalarm", host="h",
        request_fn=lambda: httpx.Response(
            429, json={"error": "rate"}, headers={"Retry-After": "7200"},
        ),
        parse_fn=lambda r: r.json(), clock=_fixed_clock(1500.0),
    )
    assert rueckzug is None
    assert _bestandsfelder(cache["k-429"]) == {
        "data": None, "fetched_at": 1500.0, "ttl": 7200.0,
    }
    zeile = _journal(journal)[-1]
    assert (zeile["status"], zeile["retry_after"], zeile["ok"]) == (429, 7200.0, False)
