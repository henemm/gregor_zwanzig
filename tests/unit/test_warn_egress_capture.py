"""TDD RED — Issue #1948 (Scheibe S1): Zweig-b-Mount in
``warn_egress.cached_fetch`` schreibt bei echter (nicht gecachter) Antwort
einen System-Level-Eingangs-Datensatz.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-2)

RED-Grund: ``alert_input_capture.py`` existiert nicht; ``cached_fetch()``
ruft an ihrer bestehenden ``on_response``-Ausfuehrungsstelle
(warn_egress.py ~Z. 296-360) noch keinen Capture-Aufruf auf -- die
Verzeichnis-Existenzpruefung findet daher nichts.

Mock-frei: echtes ``request_fn`` liefert ein reales ``httpx.Response``-
Objekt (Vorbild ``tests/tdd/test_warn_service_egress.py``), kein Netz.
``WARN_CALLS_PATH_OVERRIDE`` wird wie im Vorbild auf ``tmp_path``
umgelenkt. Die pytest-isolierte Datenwurzel (#1133, autouse) sorgt dafuer,
dass ``get_data_root()`` in einem Test-tmp-Baum landet.
"""
from __future__ import annotations

import json

import httpx


def _fixed_clock(value: float):
    return lambda: value


def _capture_dir():
    from app.loader import get_data_root

    return get_data_root() / "debug" / "alert_input" / "official_alert"


def test_ac2_echte_antwort_schreibt_datensatz_cache_hit_schreibt_keinen_weiteren(monkeypatch, tmp_path):
    """AC-2: GIVEN ein amtlicher Warndienst wird ueber ``cached_fetch`` mit
    einer echten, nicht gecachten Antwort abgefragt, WHEN die Antwort
    erfolgreich geparst wird, THEN liegt ein System-Level-Eingangs-
    Datensatz mit dem rohen Response-Body sowie Service/Host/Cache-Key
    unter ``data/debug/alert_input/official_alert/``. Ein anschliessender
    Cache-Treffer fuer denselben Schluessel erzeugt KEINEN weiteren
    Datensatz (nur echte, nicht gecachte Antworten werden mitgeschnitten)."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    fixture_body = {"features": [{"id": "warn-1948", "properties": {"event": "Sturm"}}]}
    cache: dict = {}

    result = warn_egress.cached_fetch(
        cache=cache, cache_key="AT-1948-capture", service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.Response(200, json=fixture_body),
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(2000.0),
    )
    assert result == fixture_body  # Bestandsverhalten unveraendert (BIT-identisch)

    files = sorted(_capture_dir().glob("*.json"))
    assert files, (
        "Kein System-Level-Eingangs-Datensatz unter "
        "data/debug/alert_input/official_alert/ gefunden -- cached_fetch() "
        "ruft alert_input_capture.capture_system() an der on_response-"
        "Stelle nicht auf."
    )
    record = json.loads(files[-1].read_text())
    assert record.get("capture_id"), "capture_id fehlt im Eingangs-Datensatz."
    payload = record.get("payload", {})
    assert payload.get("body") == fixture_body, f"Roher Response-Body weicht ab: {payload!r}"
    assert payload.get("service") == "meteoalarm"
    assert payload.get("host") == "api.meteoalarm.org"
    assert payload.get("cache_key") == "AT-1948-capture"

    # Kehrseite: derselbe cache_key ist jetzt gueltig (WARN_SUCCESS_TTL,
    # clock unveraendert) -- ein weiterer cached_fetch()-Aufruf ist ein
    # Cache-Hit und darf keinen zusaetzlichen Datensatz erzeugen.
    def _net_sentinel():
        raise AssertionError("request_fn wurde bei einem Cache-Hit aufgerufen")

    warn_egress.cached_fetch(
        cache=cache, cache_key="AT-1948-capture", service="meteoalarm",
        host="api.meteoalarm.org", request_fn=_net_sentinel,
        parse_fn=lambda r: r.json(), clock=_fixed_clock(2000.0),
    )
    files_after_hit = sorted(_capture_dir().glob("*.json"))
    assert len(files_after_hit) == len(files), (
        f"Ein Cache-Hit hat einen zusaetzlichen Eingangs-Datensatz "
        f"geschrieben: vorher {len(files)}, nachher {len(files_after_hit)}."
    )
