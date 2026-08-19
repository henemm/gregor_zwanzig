"""TDD RED — Issue #1944, AC-5: nach einer Ratenbremsen-Wiederholung traegt
der finale Zwischenspeicher-Eintrag die Kennung des LETZTEN, tatsaechlich
verwerteten Versuchs -- nicht die des verworfenen Zwischenversuchs.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-5)

RED-Grund: der Zwischenspeicher-Eintrag traegt kein ``"capture_id"``-Feld und
``warn_egress.observe_capture_id()`` existiert nicht.

Die beiden Versuche sind UNTERSCHEIDBAR gemacht (429 mit Fehler-Body vs. 200
mit Nutzdaten-Body): nur so ist „zeigt auf den zweiten" ueberhaupt von „zeigt
auf den ersten" trennbar. Beide Versuche schreiben je einen eigenen
Mitschnitt (``cached_fetch`` schneidet JEDE echte Antwort mit) -- die
Zuordnung laeuft strukturell ueber ``payload.status``/``payload.body``.

Mock-frei: echte ``httpx.Response``-Objekte, echte ``RateLimitRetryPolicy``
mit injizierter ``sleep_fn``/``wall_clock_fn`` (kein reales Warten, Vorbild
``tests/tdd/test_warn_service_egress.py``).
"""
from __future__ import annotations

import json

import httpx


def _fixed_clock(value: float):
    return lambda: value


def _capture_records() -> list[dict]:
    from app.loader import get_data_root

    verzeichnis = get_data_root() / "debug" / "alert_input" / "official_alert"
    return [json.loads(p.read_text()) for p in sorted(verzeichnis.glob("*.json"))]


def _record_by_status(datensaetze: list[dict], status: int) -> dict:
    treffer = [r for r in datensaetze if r.get("payload", {}).get("status") == status]
    assert len(treffer) == 1, (
        f"Erwartet genau EINEN Mitschnitt mit status={status}, "
        f"gefunden {len(treffer)}: {[r.get('payload', {}).get('status') for r in datensaetze]}"
    )
    return treffer[0]


def test_ac5_kennung_zeigt_auf_den_verwerteten_zweiten_versuch(monkeypatch, tmp_path):
    """AC-5: GIVEN ein Warndienst antwortet zunaechst mit HTTP 429 und einer
    konfigurierten Kurzzeit-Ratenbremse, WHEN ``cached_fetch()`` den
    Zwischenversuch verwirft und ein zweiter, erfolgreicher Versuch das
    Ergebnis liefert, THEN traegt der finale Zwischenspeicher-Eintrag die
    ``capture_id`` des ZWEITEN Mitschnitts."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    body_429 = {"error": "rate limited", "versuch": 1}
    body_200 = {"features": [{"id": "warn-1944-retry"}], "versuch": 2}
    antworten = [
        httpx.Response(429, json=body_429),
        httpx.Response(200, json=body_200),
    ]

    def _request_fn() -> httpx.Response:
        return antworten.pop(0)

    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3, default_wait_seconds=0.0,
        sleep_fn=lambda _s: None, wall_clock_fn=lambda: 0.0,
    )
    cache: dict = {}
    with warn_egress.observe_capture_id() as senke:
        ergebnis = warn_egress.cached_fetch(
            cache=cache, cache_key="AT-1944-retry", service="meteoalarm",
            host="api.meteoalarm.org", request_fn=_request_fn,
            parse_fn=lambda r: r.json(), clock=_fixed_clock(4000.0),
            rate_limit_retry=policy,
        )
        gemeldet = list(senke["capture_ids"])

    assert ergebnis == body_200, (
        f"Bestandsverhalten: der Wiederholungsversuch liefert die Nutzdaten, war {ergebnis!r}"
    )
    assert antworten == [], "Voraussetzung: beide Antworten muessen verbraucht worden sein."

    datensaetze = _capture_records()
    assert len(datensaetze) == 2, (
        f"Beide echten Versuche muessen je einen Mitschnitt erzeugen, "
        f"es waren {len(datensaetze)}."
    )
    verworfen = _record_by_status(datensaetze, 429)
    verwertet = _record_by_status(datensaetze, 200)
    assert verwertet["payload"]["body"] == body_200
    assert verworfen["capture_id"] != verwertet["capture_id"], (
        "Voraussetzung der Messung: beide Versuche muessen unterscheidbare "
        "Kennungen tragen."
    )

    eintrag = cache["AT-1944-retry"]
    assert eintrag.get("capture_id") == verwertet["capture_id"], (
        f"Der finale Zwischenspeicher-Eintrag muss die Kennung des VERWERTETEN "
        f"(zweiten) Versuchs tragen, nicht die des verworfenen: "
        f"eingetragen={eintrag.get('capture_id')!r}, "
        f"verwertet={verwertet['capture_id']!r}, verworfen={verworfen['capture_id']!r}"
    )
    assert gemeldet and gemeldet[-1] == verwertet["capture_id"], (
        f"Der Rueckkanal muss zuletzt die Kennung des verwerteten Versuchs "
        f"melden: {gemeldet!r}"
    )


def test_ac5_terminales_429_traegt_die_kennung_seines_eigenen_abrufs(monkeypatch, tmp_path):
    """Kehrseite: sind die Versuche erschoepft, ist der letzte 429 selbst der
    verwertete Abruf -- der Fehlschlag-Cache-Eintrag traegt dessen Kennung
    (die Kette bricht nicht ab, nur weil kein Erfolg herauskam)."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    antworten = [
        httpx.Response(429, json={"error": "rate limited", "versuch": i})
        for i in (1, 2)
    ]

    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=2, default_wait_seconds=0.0,
        sleep_fn=lambda _s: None, wall_clock_fn=lambda: 0.0,
    )
    cache: dict = {}
    ergebnis = warn_egress.cached_fetch(
        cache=cache, cache_key="AT-1944-retry-erschoepft", service="meteoalarm",
        host="api.meteoalarm.org", request_fn=lambda: antworten.pop(0),
        parse_fn=lambda r: r.json(), clock=_fixed_clock(4000.0),
        rate_limit_retry=policy,
    )

    assert ergebnis is None, "Bestandsverhalten: erschoepfte Versuche liefern None."
    datensaetze = _capture_records()
    assert len(datensaetze) == 2, f"Zwei echte Versuche, {len(datensaetze)} Mitschnitte."
    letzter = [r for r in datensaetze if r["payload"]["body"]["versuch"] == 2]
    assert len(letzter) == 1, f"Genau ein Mitschnitt des zweiten Versuchs: {datensaetze!r}"
    assert cache["AT-1944-retry-erschoepft"].get("capture_id") == letzter[0]["capture_id"], (
        f"Auch der Fehlschlag-Eintrag traegt die Kennung des letzten, "
        f"tatsaechlich verwerteten Abrufs: {cache['AT-1944-retry-erschoepft']!r}"
    )
