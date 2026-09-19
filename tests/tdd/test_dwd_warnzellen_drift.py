"""TDD RED -- Drift-Waechter fuer die deutschen Warnzellen (Issue #1681, AC-9).

SPEC: docs/specs/modules/feat_1681_meteoalarm_de.md (AC-9 / Test 8,
Side effects: "zusaetzliche Journal-Eintraege bei Drift-Funden (WARNCELLID im
Feed ohne eingecheckte Geometrie)").
Vorbild: ``tests/tdd/test_dpc_zone_drift.py`` (Issue #1434).

AC -> Testfunktion:
- AC-9 ``test_ac9_alle_nicht_kuesten_warnzellen_der_aufzeichnung_sind_in_der_geometrie``
  (statischer Abgleich der aufgezeichneten Feed-Zellen gegen die eingecheckte Geometrie)
- AC-9 ``test_ac9_unbekannte_warnzelle_im_feed_wird_im_journal_gemeldet_kueste_nicht``
  (Laufzeit: ein DE-Abruf meldet eine unbekannte Nicht-Kuesten-Zelle ueber
  ``warn_egress.log_zone_drift``, die bekannten ``501``-Seezellen nicht)

RED-Ursache: ``src/services/official_alerts/data/dwd_warngebiete_kreise.json``
existiert nicht, ``MeteoAlarmFeedSource("DE")`` faellt in den italienischen
Zweig und fuehrt keinen Warnzellen-Abgleich durch.

Konstruierter Drift-Fall: die Aufzeichnung vom 2026-09-19 enthaelt KEINEN
echten Drift (alle 282 Nicht-Kuesten-Zellen liegen im Kreis-Layer, s.
``tests/fixtures/meteoalarm_feed/README.md``). Ein Kreis-Neuschnitt ist nicht
herbeifuehrbar -- wie in ``test_dpc_zone_drift.py`` (Phantasie-Codes
``Zzzz-1``) wird der Drift deshalb IM TESTCODE konstruiert: eine Kopie des
echten Eintrags #245 (Nebel, Altoetting/Muehldorf/Rosenheim), deren Zelle
``109183000`` durch die nicht existierende ``109999000`` ersetzt ist. Die
eingecheckte Fixture bleibt unveraendert.

Kein Mock, kein Netz (Kern-Schicht, laeuft mit ``--disable-socket``): der
Feed wird als echter Cache-Eintrag vorbelegt (Muster
``test_official_alerts_unavailable_hint.py``), das Journal ueber
``warn_egress.WARN_CALLS_PATH_OVERRIDE`` in ``tmp_path`` umgelenkt und als
echte Datei gelesen.

Konsequenz fuer die Implementierung: weil der Feed ueber den Cache-Treffer
kommt, laeuft ``_parse_feed`` hier NICHT. Der WARNCELLID-Abgleich muss daher
auf dem Auswertungspfad liegen (``fetch()``/``_alerts_for_zone``), nicht
ausschliesslich beim Parsen -- ein 30 Minuten lang gecachter Feed wird sonst
bei jedem Abruf ungeprueft ausgewertet.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"
_GEOMETRIE = _REPO_ROOT / "src" / "services" / "official_alerts" / "data" / "dwd_warngebiete_kreise.json"

PEINE = (52.32, 10.23)  # 103157000 Kreis Peine -- zustaendiger DE-Punkt ohne Warnung
PHANTOM_ZELLE = "109999000"
ERSETZTE_ZELLE = "109183000"  # Kreis Muehldorf a. Inn, echt im Eintrag #245


def _feed_de() -> dict:
    return json.loads((_FIXTURES / "feed_germany_sample.json").read_text(encoding="utf-8"))


def _warncellids_in(obj) -> "list[str]":
    gefunden: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "WARNCELLID":
                gefunden.append(str(value))
            else:
                gefunden.extend(_warncellids_in(value))
    elif isinstance(obj, list):
        for item in obj:
            gefunden.extend(_warncellids_in(item))
    return gefunden


def _feed_zellen(feed: dict) -> set[str]:
    return {
        str(g["value"])
        for w in feed["warnings"] for i in (w["alert"].get("info") or [])
        for ar in i.get("area") or [] for g in ar.get("geocode") or []
        if g.get("valueName") == "WARNCELLID"
    }


def _geometrie_zellen() -> set[str]:
    assert _GEOMETRIE.exists(), f"Geometriedatei fehlt: {_GEOMETRIE}"
    return set(_warncellids_in(json.loads(_GEOMETRIE.read_text(encoding="utf-8"))))


@pytest.fixture(autouse=True)
def _caches_leeren():
    from services.official_alerts import meteoalarm_feed

    meteoalarm_feed._cache.clear()
    yield
    meteoalarm_feed._cache.clear()


def test_ac9_alle_nicht_kuesten_warnzellen_der_aufzeichnung_sind_in_der_geometrie():
    """AC-9 (statisch): GIVEN die aufgezeichnete DE-Stichprobe, WHEN ihre
    WARNCELLIDs gegen die eingecheckte Geometrie abgeglichen werden, THEN
    fehlt keine Zelle ausser den bewusst ausgenommenen Seezellen ``501...``
    -- ein neuer Fehlbestand (z. B. nach einer Kreisreform) wird hier rot."""
    feed_zellen = _feed_zellen(_feed_de())
    fehlend = {z for z in feed_zellen - _geometrie_zellen() if not z.startswith("501")}
    assert fehlend == set(), f"Warnzellen im Feed ohne eingecheckte Geometrie: {sorted(fehlend)}"


def test_ac9_unbekannte_warnzelle_im_feed_wird_im_journal_gemeldet_kueste_nicht(monkeypatch, tmp_path):
    """AC-9 (Laufzeit): GIVEN der DE-Feed fuehrt eine WARNCELLID, die in der
    eingecheckten Geometrie fehlt und KEINE Kuestenzelle ist (konstruierte
    Kopie von #245 mit ``109999000``), daneben die echte Seezelle
    ``501000004`` (#246), WHEN die deutsche Quelle fuer einen zustaendigen
    Punkt abruft, THEN steht der Fund als Drift-Zeile im Warn-Dienst-Journal
    (``log_zone_drift``) -- die bekannte Seezelle dagegen nicht."""
    from services.official_alerts import meteoalarm_feed, warn_egress
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert PHANTOM_ZELLE not in _geometrie_zellen(), "Testvorbedingung: Phantom-Zelle existiert nicht"

    feed = _feed_de()
    vorlage = [w for w in feed["warnings"]
               if ERSETZTE_ZELLE in _feed_zellen({"warnings": [w]})]
    assert len(vorlage) == 1, "Fixture-Vorbedingung: #245 ist der einzige Eintrag mit 109183000"
    drift = copy.deepcopy(vorlage[0])
    drift["alert"]["identifier"] += ".DRIFTTEST"
    for info in drift["alert"]["info"]:
        for area in info["area"]:
            for geocode in area["geocode"]:
                if geocode["valueName"] == "WARNCELLID" and geocode["value"] == ERSETZTE_ZELLE:
                    geocode["value"] = PHANTOM_ZELLE
    feed["warnings"].append(drift)

    journal = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)
    meteoalarm_feed._cache["DE"] = {
        "data": feed, "fetched_at": time.monotonic(), "ttl": warn_egress.WARN_SUCCESS_TTL,
    }

    de = MeteoAlarmFeedSource("DE")
    assert de.covers(*PEINE) is True, "Peine liegt in Deutschland -- die DE-Quelle ist zustaendig"
    de.fetch(*PEINE)

    zeilen = [json.loads(z) for z in journal.read_text(encoding="utf-8").splitlines() if z.strip()] \
        if journal.exists() else []
    drift_zeilen = [z for z in zeilen if "drift" in z]
    assert any(str(z.get("zone_code")) == PHANTOM_ZELLE
               and str(z.get("service", "")).startswith("meteoalarm_feed")
               for z in drift_zeilen), (
        f"unbekannte Warnzelle {PHANTOM_ZELLE} wurde nicht gemeldet. Drift-Zeilen: {drift_zeilen}"
    )
    assert not any(str(z.get("zone_code") or "").startswith("501") for z in drift_zeilen), (
        f"bekannte Kuestenzellen duerfen nicht als Drift gemeldet werden: {drift_zeilen}"
    )
