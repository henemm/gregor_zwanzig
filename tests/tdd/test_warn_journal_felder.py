"""Sicherungsnetz -- Warn-Journal behaelt sein Schema ohne Retry-Policy (Issue #2266, Epic #2258).

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md (AC-6 Python-Teil, AC-8 Wert)

Beim Rueckbau entfallen ``RateLimitRetryPolicy`` und der 429-Retry-Zweig in
``warn_egress``; das Journal-Feld ``self_throttled`` bleibt aus Gruenden der
Schema-Stabilitaet (Go-Auswertung ``warn_service_health.go`` liest es). Diese
Tests sind bewusst SCHON HEUTE gruen und muessen es nach jedem Rueckbauschritt
bleiben. Sie referenzieren keinerlei Retry-Symbol und rufen ``cached_fetch``
ohne ``rate_limit_retry`` auf -- so kompilieren sie nach dem Rueckbau unveraendert.

Kein Mock-Theater: der Abruf scheitert ueber eine echte Ausnahme bzw. gelingt
ueber ein echtes ``httpx.Response``-Objekt; das Journal wird ueber den dafuer
vorgesehenen Test-Override ``WARN_CALLS_PATH_OVERRIDE`` in ``tmp_path`` gelenkt
und danach als Datei gelesen. Kern-Schicht, ohne Netz.
"""
from __future__ import annotations

import json

import httpx

_JOURNAL_FELDER = {"ts", "service", "host", "status", "cache_hit", "retry_after", "ok", "self_throttled"}


def _journal_zeilen(pfad) -> list[dict]:
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def test_ac6_fehlgeschlagener_abruf_schreibt_vollstaendige_zeile_mit_self_throttled_false(
    monkeypatch, tmp_path,
):
    """AC-6: GIVEN ein Warn-Abruf ueber ``cached_fetch`` OHNE Retry-Policy, WHEN
    der Abruf mit einem Netzwerkfehler scheitert, THEN steht im Journal genau
    eine Zeile mit allen bisherigen Feldern, ``ok`` False und
    ``self_throttled`` False (nicht fehlend, nicht None)."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "diagnostics" / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    def _scheitert() -> httpx.Response:
        raise httpx.ConnectError("Verbindung abgelehnt (Testeingabe)")

    cache: dict = {}
    data = warn_egress.cached_fetch(
        cache=cache, cache_key="IT", service="meteoalarm_feed:IT",
        host="feeds.meteoalarm.org", request_fn=_scheitert,
        parse_fn=lambda resp: resp.json(),
    )

    assert data is None, "ein gescheiterter Abruf liefert None (fail-soft)"
    zeilen = _journal_zeilen(journal)
    assert len(zeilen) == 1, f"genau eine Journal-Zeile erwartet, erhalten: {zeilen}"
    zeile = zeilen[0]
    assert _JOURNAL_FELDER <= set(zeile), (
        f"Journal-Zeile muss alle bisherigen Felder tragen, es fehlen: "
        f"{sorted(_JOURNAL_FELDER - set(zeile))}"
    )
    assert zeile["service"] == "meteoalarm_feed:IT"
    assert zeile["host"] == "feeds.meteoalarm.org"
    assert zeile["cache_hit"] is False
    assert zeile["ok"] is False
    assert zeile["self_throttled"] is False, (
        f"self_throttled bleibt im Schema und ist konstant False, erhalten: {zeile['self_throttled']!r}"
    )
    assert cache["IT"]["data"] is None and cache["IT"]["ttl"] == warn_egress.WARN_FAILURE_TTL


def test_ac6_erfolgreicher_abruf_schreibt_vollstaendige_zeile_mit_self_throttled_false(
    monkeypatch, tmp_path,
):
    """AC-6 (Gegenrichtung): GIVEN derselbe Weg, WHEN der Abruf gelingt, THEN
    traegt auch die Erfolgszeile alle Felder, ``ok`` True und ``self_throttled``
    False."""
    from services.official_alerts import warn_egress

    journal = tmp_path / "diagnostics" / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)

    def _gelingt() -> httpx.Response:
        return httpx.Response(
            200, json={"warnings": []},
            request=httpx.Request("GET", "https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy"),
        )

    data = warn_egress.cached_fetch(
        cache={}, cache_key="IT", service="meteoalarm_feed:IT",
        host="feeds.meteoalarm.org", request_fn=_gelingt,
        parse_fn=lambda resp: resp.json(),
    )

    assert data == {"warnings": []}
    zeilen = _journal_zeilen(journal)
    assert len(zeilen) == 1, f"genau eine Journal-Zeile erwartet, erhalten: {zeilen}"
    zeile = zeilen[0]
    assert _JOURNAL_FELDER <= set(zeile), (
        f"es fehlen Felder: {sorted(_JOURNAL_FELDER - set(zeile))}"
    )
    assert zeile["ok"] is True
    assert zeile["status"] == 200
    assert zeile["self_throttled"] is False


def test_ac8_feed_ttl_bleibt_1800_sekunden():
    """AC-8 (Wert, nicht Quelltext): GIVEN das Lizenz-Pruefergebnis aendert die
    TTL nicht, WHEN ``warn_egress`` importiert wird, THEN betraegt die
    Erfolgs-TTL weiterhin 1800 Sekunden (30 min, ADR-0074)."""
    from services.official_alerts import warn_egress

    assert warn_egress.WARN_SUCCESS_TTL == 1800
