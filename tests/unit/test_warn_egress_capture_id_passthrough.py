"""TDD RED — Issue #1944 (Scheibe 2 aus #1929), AC-1: ein Cache-Treffer meldet
DIESELBE ``capture_id`` wie der Ursprungsabruf -- ohne einen zweiten
Mitschnitt zu schreiben.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-1)

RED-Grund: ``warn_egress.observe_capture_id()`` existiert nicht; der
Zwischenspeicher-Eintrag traegt kein ``"capture_id"``-Feld.

🔴 VERTRAG des Rueckkanals (von diesem RED-Test festgelegt, exaktes Vorbild
``warn_egress.observe_fetch_failure()`` Z. 86-98):

    with warn_egress.observe_capture_id() as senke:
        ...                       # cached_fetch()-Aufrufe
    senke["capture_ids"]          # Liste, Melde-Reihenfolge, initial []

Verschachtelbar und thread-/task-sicher ueber ``contextvars``, ausserhalb
jeder Beobachtung ein No-Op (wie ``_record_fetch_failure()``).

Mock-frei: echtes ``request_fn`` mit echten ``httpx.Response``-Objekten
(Vorbild ``tests/unit/test_warn_egress_capture.py``), Zeit ueber ``clock``
injiziert, Mitschnitt-Dateien real geschrieben und per ``json.loads``
strukturell gelesen. Die pytest-isolierte Datenwurzel (#1133, autouse) haelt
alle Schreibvorgaenge im tmp-Baum.
"""
from __future__ import annotations

import json

import httpx


def _fixed_clock(value: float):
    return lambda: value


def _capture_dir():
    from app.loader import get_data_root

    return get_data_root() / "debug" / "alert_input" / "official_alert"


def _capture_records() -> list[dict]:
    """Alle Mitschnitte des Zweigs b, strukturell geladen (kein String-Check)."""
    return [json.loads(p.read_text()) for p in sorted(_capture_dir().glob("*.json"))]


class _ZweitabrufVerboten(Exception):
    """Positivkontrolle: fliegt, sobald ``request_fn`` beim Cache-Treffer doch
    aufgerufen wird -- der Test scheitert dann HART statt nur eine falsche
    Kennung zu melden."""


def test_ac1_cache_treffer_meldet_dieselbe_kennung_ohne_zweiten_mitschnitt(monkeypatch, tmp_path):
    """AC-1: GIVEN ein Warndienst wurde erfolgreich ueber ``cached_fetch()``
    abgerufen und der Zwischenspeicher-Eintrag ist noch gueltig, WHEN ein
    zweiter Aufruf mit demselben ``cache_key`` erfolgt (ohne dass
    ``request_fn`` erneut laufen darf), THEN meldet der Rueckkanal exakt
    dieselbe ``capture_id`` wie der erste, echte Abruf -- und es entsteht
    KEIN zusaetzlicher Mitschnitt."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    body = {"features": [{"id": "warn-1944", "properties": {"event": "Sturm"}}]}
    cache: dict = {}

    def _echter_abruf() -> httpx.Response:
        return httpx.Response(200, json=body)

    def _verbotener_abruf() -> httpx.Response:
        raise _ZweitabrufVerboten(
            "request_fn wurde beim Cache-Treffer aufgerufen — der Rueckkanal "
            "darf die Kennung aus dem Zwischenspeicher melden, nicht neu holen."
        )

    with warn_egress.observe_capture_id() as senke_erst:
        erstes = warn_egress.cached_fetch(
            cache=cache, cache_key="AT-1944-passthrough", service="meteoalarm",
            host="api.meteoalarm.org", request_fn=_echter_abruf,
            parse_fn=lambda r: r.json(), clock=_fixed_clock(3000.0),
        )
        gemeldet_erst = list(senke_erst["capture_ids"])

    assert erstes == body, "Rueckgabewert des echten Abrufs muss unveraendert bleiben."
    datensaetze_nach_erst = _capture_records()
    assert len(datensaetze_nach_erst) == 1, (
        f"Der echte Abruf muss genau EINEN Mitschnitt schreiben, "
        f"es waren {len(datensaetze_nach_erst)}."
    )
    geschriebene_id = datensaetze_nach_erst[0]["capture_id"]
    assert gemeldet_erst == [geschriebene_id], (
        f"Der Rueckkanal muss die Kennung des geschriebenen Mitschnitts melden: "
        f"gemeldet={gemeldet_erst!r}, geschrieben={geschriebene_id!r}"
    )

    # Zweiter Aufruf: gueltiger Cache-Eintrag (clock unveraendert), request_fn
    # wirft — ein faelschlicher Zweitabruf scheitert hart.
    with warn_egress.observe_capture_id() as senke_zweit:
        zweites = warn_egress.cached_fetch(
            cache=cache, cache_key="AT-1944-passthrough", service="meteoalarm",
            host="api.meteoalarm.org", request_fn=_verbotener_abruf,
            parse_fn=lambda r: r.json(), clock=_fixed_clock(3000.0),
        )
        gemeldet_zweit = list(senke_zweit["capture_ids"])

    assert zweites == body, "Der Cache-Treffer muss dieselben Daten liefern wie zuvor."
    assert gemeldet_zweit == [geschriebene_id], (
        f"Der Cache-Treffer muss DIESELBE Kennung melden wie der Ursprungsabruf: "
        f"gemeldet={gemeldet_zweit!r}, erwartet=[{geschriebene_id!r}]"
    )
    assert cache["AT-1944-passthrough"].get("capture_id") == geschriebene_id, (
        f"Der Zwischenspeicher-Eintrag muss die Kennung mitfuehren: "
        f"{cache['AT-1944-passthrough']!r}"
    )
    assert len(_capture_records()) == 1, (
        f"Ein Cache-Treffer darf KEINEN zusaetzlichen Mitschnitt schreiben, "
        f"es sind jetzt {len(_capture_records())}."
    )


def test_ac1_gegenprobe_die_zaehlung_schlaegt_bei_einem_echten_zweitabruf_an(monkeypatch, tmp_path):
    """Gegenprobe zur Abwesenheits-Zusicherung oben: dieselbe Messung
    (Dateizaehlung im Mitschnitt-Verzeichnis) MUSS anschlagen, wenn wirklich
    ein zweiter echter Abruf laeuft. Ohne diesen Nachweis waere „bleibt bei 1"
    auch die Antwort einer toten Messung."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    cache: dict = {}
    for schluessel in ("AT-1944-gegenprobe-a", "AT-1944-gegenprobe-b"):
        warn_egress.cached_fetch(
            cache=cache, cache_key=schluessel, service="meteoalarm",
            host="api.meteoalarm.org",
            request_fn=lambda k=schluessel: httpx.Response(200, json={"k": k}),
            parse_fn=lambda r: r.json(), clock=_fixed_clock(3000.0),
        )

    assert len(_capture_records()) == 2, (
        "Zwei echte Abrufe muessen zwei Mitschnitte erzeugen — sonst misst die "
        "Zaehlung im Test oben nichts."
    )


def test_ac1_rueckkanal_ausserhalb_der_beobachtung_ist_ein_no_op(monkeypatch, tmp_path):
    """Bestandsschutz (Vorbild ``_record_fetch_failure``): ohne aktiven
    ``observe_capture_id()``-Kontext bleibt ``cached_fetch()`` unveraendert --
    kein Fehler, unveraenderter Rueckgabewert."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    body = {"features": []}
    ergebnis = warn_egress.cached_fetch(
        cache={}, cache_key="AT-1944-no-op", service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.Response(200, json=body),
        parse_fn=lambda r: r.json(), clock=_fixed_clock(3000.0),
    )
    assert ergebnis == body
    # Der unbeobachtete Abruf darf keine Spur hinterlassen: ein danach
    # geoeffneter Kontext startet leer.
    with warn_egress.observe_capture_id() as senke:
        assert senke["capture_ids"] == [], (
            f"Ein frisch geoeffneter Rueckkanal muss leer starten, war {senke!r}"
        )
