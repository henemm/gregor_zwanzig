"""Issue #1944, AC-5 (Adversary-Fund F002): schlaegt der Mitschnitt des
tatsaechlich VERWERTETEN Versuchs fehl, darf am finalen Zwischenspeicher-
Eintrag KEINE Kennung eines frueheren, VERWORFENEN Versuchs haengen bleiben.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-5, sowie
die AC-4-Randbedingung "eine falsche Zuordnung ist schlimmer als keine")

RED-Grund: ``capture_id`` wird EINMAL vor der Ratenbremsen-Schleife
initialisiert; der Fail-open-``except`` um ``capture_system()`` setzt sie bei
einem Fehlschlag nicht zurueck -- die Kennung des verworfenen 429-Versuchs
ueberlebt bis in ``_store_entry()``.

Mock-frei: echte ``httpx.Response``-Objekte, echter Mitschnitt des ersten
Versuchs ueber ``alert_input_capture.capture_system`` (echte Datei), echte
``RateLimitRetryPolicy`` mit injizierter ``sleep_fn`` (kein reales Warten).
Ersetzt wird ausschliesslich die NAHT zum Mitschnitt, und nur um deren
Ausfall (Plattenfehler o.ae.) real herbeizufuehren -- keine Rueckspiegelung
einer Annahme.
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


def test_ac5_fehlgeschlagener_mitschnitt_erbt_keine_kennung_des_verworfenen_versuchs(
    monkeypatch, tmp_path
):
    """AC-5: GIVEN ein Warndienst antwortet erst mit HTTP 429 (Mitschnitt
    gelingt) und dann mit HTTP 200 (Mitschnitt schlaegt fehl), WHEN
    ``cached_fetch()`` den 429-Versuch verwirft und die 200-Antwort verwertet,
    THEN traegt der finale Zwischenspeicher-Eintrag NICHT die Kennung des
    verworfenen Versuchs -- lieber keine Herkunft als eine falsche."""
    from services import alert_input_capture
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    body_429 = {"error": "rate limited", "versuch": 1}
    body_200 = {"features": [{"id": "warn-1944-stale"}], "versuch": 2}
    antworten = [
        httpx.Response(429, json=body_429),
        httpx.Response(200, json=body_200),
    ]

    echter_mitschnitt = alert_input_capture.capture_system
    aufrufe = {"n": 0}

    def _mitschnitt_faellt_beim_zweiten_versuch_aus(*args, **kwargs):
        aufrufe["n"] += 1
        if aufrufe["n"] == 1:
            return echter_mitschnitt(*args, **kwargs)
        raise RuntimeError("Mitschnitt des verwerteten Versuchs schlaegt fehl")

    monkeypatch.setattr(
        alert_input_capture, "capture_system", _mitschnitt_faellt_beim_zweiten_versuch_aus
    )

    policy = warn_egress.RateLimitRetryPolicy(
        max_attempts=3, default_wait_seconds=0.0,
        sleep_fn=lambda _s: None, wall_clock_fn=lambda: 0.0,
    )
    cache: dict = {}
    with warn_egress.observe_capture_id() as senke:
        ergebnis = warn_egress.cached_fetch(
            cache=cache, cache_key="AT-1944-stale", service="meteoalarm",
            host="api.meteoalarm.org", request_fn=lambda: antworten.pop(0),
            parse_fn=lambda r: r.json(), clock=_fixed_clock(4200.0),
            rate_limit_retry=policy,
        )
        gemeldet = list(senke["capture_ids"])

    assert ergebnis == body_200, (
        f"Bestandsverhalten: der Wiederholungsversuch liefert die Nutzdaten, war {ergebnis!r}"
    )
    assert aufrufe["n"] == 2, (
        f"Voraussetzung der Messung: beide echten Versuche muessen einen "
        f"Mitschnitt versucht haben, es waren {aufrufe['n']}."
    )

    datensaetze = _capture_records()
    verworfen = [r for r in datensaetze if r.get("payload", {}).get("status") == 429]
    assert len(verworfen) == 1, (
        f"Voraussetzung: der VERWORFENE 429-Versuch muss real mitgeschnitten "
        f"worden sein, gefunden {len(verworfen)}."
    )
    assert not [r for r in datensaetze if r.get("payload", {}).get("status") == 200], (
        "Voraussetzung: der Mitschnitt des verwerteten Versuchs muss "
        "fehlgeschlagen sein -- es darf keinen 200-Datensatz geben."
    )
    kennung_des_verworfenen = verworfen[0]["capture_id"]

    eintrag = cache["AT-1944-stale"]
    assert eintrag.get("capture_id") != kennung_des_verworfenen, (
        f"Der finale Eintrag darf NIE die Kennung des verworfenen "
        f"Zwischenversuchs tragen -- eine falsche Zuordnung ist schlimmer als "
        f"keine: eingetragen={eintrag.get('capture_id')!r}, "
        f"verworfen={kennung_des_verworfenen!r}"
    )
    assert eintrag.get("capture_id") is None, (
        f"Ohne gelungenen Mitschnitt des verwerteten Versuchs bleibt die "
        f"Herkunft ungesetzt, war {eintrag!r}"
    )
    assert kennung_des_verworfenen not in gemeldet, (
        f"Auch der Rueckkanal darf die Kennung des verworfenen Versuchs nicht "
        f"melden: {gemeldet!r}"
    )
