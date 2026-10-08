"""TDD RED -- Aufbewahrung der Alarm-Eingangsmitschnitte je Quelle und nach
Alter statt je Verzeichnis nach Anzahl (Issue #2218 Scheibe C, Eintrag B2-71).

SPEC: docs/specs/modules/fix_2218_scheibe_c_observability.md (AC-13 bis AC-18)
Vorgaenger: Issue #1948 S1 (alarm_eingangsprotokoll.md AC-5) nagelte "50 pro
Verzeichnis" fest -- diese Datei ersetzt diese Zusicherung: ein Mitschnitt
bleibt mindestens 24 Stunden abrufbar, solange der Gesamtdeckel nicht greift.

Mock-frei: echte JSON-Dateien mit real gesetzten ``st_mtime``-Werten
(``os.utime``) im pytest-isolierten Datenverzeichnis (#1133); ein echter
Schreibvorgang (``capture_system`` / ``capture_user_scoped``) loest die
Bereinigung aus. Der Gesamtdeckel wird ueber die Modul-Konstanten
``_MAX_FILES_PER_DIR_TOTAL`` / ``_MAX_BYTES_PER_DIR`` klein gesetzt (kein
Zehntausend-Dateien-Test); ``raising=False``, damit der Test vor der
Umsetzung an der ZUSICHERUNG scheitert, nicht am fehlenden Attribut.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


H = 3600.0


def _uid(prefix: str) -> str:
    return f"tdd-2218c-retention-{prefix}-{uuid.uuid4().hex[:6]}"


def _system_dir(branch: str) -> Path:
    from app.loader import get_data_root

    d = get_data_root() / "debug" / "alert_input" / branch
    d.mkdir(parents=True, exist_ok=True)
    return d


def _altdatei(dir_path: Path, key: str, alter_s: float, *, padding: int = 0) -> Path:
    """Legt einen Mitschnitt im Namensschema der Produktion an
    (``{key}_{%Y%m%dT%H%M%S%f}.json``) mit gesetzter Aenderungszeit und einem
    ``captured_at``, das zum Alter passt (``latest_capture_id`` liest es)."""
    from services import alert_input_capture

    jetzt = datetime.now(timezone.utc)
    zeit = jetzt - timedelta(seconds=alter_s)
    name = f"{alert_input_capture._safe_key(key)}_{zeit.strftime('%Y%m%dT%H%M%S%f')}.json"
    f = dir_path / name
    f.write_text(json.dumps({
        "capture_id": uuid.uuid4().hex,
        "captured_at": zeit.isoformat(),
        "branch": dir_path.name,
        "source_key": key,
        "payload": {"pad": "x" * padding},
    }))
    ts = time.time() - alter_s
    os.utime(f, (ts, ts))
    return f


def _schreibe(key: str, branch: str = "nowcast") -> str:
    from services import alert_input_capture

    cid = alert_input_capture.capture_system(branch=branch, source_key=key, payload={"n": 1})
    assert cid, "Testaufbau: der Mitschnitt wurde nicht geschrieben"
    return cid


def _namen(dir_path: Path) -> set:
    return {p.name for p in dir_path.glob("*.json")}


# ---------------------------------------------------------------------------
# AC-13 -- Alter je Key
# ---------------------------------------------------------------------------

def test_ac13_mitschnitte_aelter_als_24h_werden_entfernt_juengere_bleiben():
    """AC-13: Dateien eines Keys mit 30/25/23/1 h Alter -> nach einem weiteren
    Schreiben sind die ueber 24 h alten weg, 23 h und 1 h sowie die neue Datei
    bleiben, ``latest_capture_id`` findet den juengsten Eintrag."""
    from services import alert_input_capture

    d = _system_dir("nowcast")
    key = "nowcast_ac13"
    alt30 = _altdatei(d, key, 30 * H)
    alt25 = _altdatei(d, key, 25 * H)
    alt23 = _altdatei(d, key, 23 * H)
    alt1 = _altdatei(d, key, 1 * H)

    neue_id = _schreibe(key)

    assert not alt30.exists(), "30 h alter Mitschnitt haette entfernt werden muessen"
    assert not alt25.exists(), "25 h alter Mitschnitt haette entfernt werden muessen"
    assert alt23.exists(), "23 h alter Mitschnitt wurde faelschlich entfernt"
    assert alt1.exists(), "1 h alter Mitschnitt wurde faelschlich entfernt"
    assert len(_namen(d)) == 3, f"23 h + 1 h + neue Datei erwartet: {sorted(_namen(d))}"
    assert alert_input_capture.latest_capture_id("nowcast", key, max_age=24 * H) == neue_id


# ---------------------------------------------------------------------------
# AC-14 -- die juengste Datei je Key bleibt immer
# ---------------------------------------------------------------------------

def test_ac14_einzige_datei_eines_keys_bleibt_auch_wenn_aelter_als_24h():
    """AC-14: ein seltener Key, dessen einzige und juengste Datei ueber 24 h alt
    ist, verschwindet nicht -- das Alterslimit loescht nie die juengste je Key."""
    d = _system_dir("nowcast")
    selten = _altdatei(d, "nowcast_ac14_selten", 30 * H)

    _schreibe("nowcast_ac14_anderer")  # Schreibvorgang eines ANDEREN Keys loest Prune aus

    assert selten.exists(), (
        "die einzige Datei eines Keys wurde vom Alterslimit geloescht "
        "(die juengste je Key muss bleiben)"
    )


# ---------------------------------------------------------------------------
# AC-15 -- haeufiger Schreiber verdraengt niemanden mehr
# ---------------------------------------------------------------------------

def test_ac15_haeufiger_key_behaelt_alle_dateien_und_verdraengt_keine_seltenen():
    """AC-15 (Regression zum Befund "Nowcast verdraengt sich selbst"): 120
    Dateien eines Keys innerhalb der letzten Stunde plus drei seltene Keys mit
    je einer Datei -> nach dem Prune sind alle 120 da (kein 50er-Fenster) und
    keine der seltenen Dateien wurde verdraengt."""
    d = _system_dir("nowcast")
    haeufig = [_altdatei(d, "nowcast_ac15_heiss", 60 + i * 30) for i in range(120)]
    selten = [_altdatei(d, f"nowcast_ac15_selten{i}", 2 * H + i) for i in range(3)]

    _schreibe("nowcast_ac15_heiss")

    fehlend = [f.name for f in haeufig if not f.exists()]
    assert not fehlend, f"{len(fehlend)} von 120 Dateien des haeufigen Keys verdraengt"
    assert all(f.exists() for f in selten), "seltene Keys wurden verdraengt"


# ---------------------------------------------------------------------------
# AC-16 -- Gesamtdeckel (Dateizahl und Bytes), sichtbar per Warnung
# ---------------------------------------------------------------------------

def test_ac16_dateideckel_verdraengt_die_aeltesten_und_warnt(monkeypatch, caplog):
    """AC-16 (Dateizahl): ueber dem Gesamtdeckel liegt die Dateizahl danach
    hoechstens am Deckel, die aeltesten sind verdraengt (Deckel hat Vorrang vor
    "juengste je Key"), und eine Warnzeile nennt den Eingriff."""
    from services import alert_input_capture

    monkeypatch.setattr(alert_input_capture, "_MAX_FILES_PER_DIR_TOTAL", 5, raising=False)
    d = _system_dir("nowcast")
    dateien = [_altdatei(d, f"nowcast_ac16_k{i}", (i + 1) * H) for i in range(8)]

    with caplog.at_level(logging.WARNING, logger="alert_input_capture"):
        neue_id = _schreibe("nowcast_ac16_neu")

    assert len(_namen(d)) <= 5, f"Dateideckel 5 ueberschritten: {len(_namen(d))} Dateien"
    assert dateien[0].exists(), "die juengste Altdatei (1 h) muss vor den aelteren bleiben"
    assert not dateien[-1].exists(), "die aelteste Datei (8 h) haette verdraengt werden muessen"
    assert alert_input_capture.latest_capture_id(
        "nowcast", "nowcast_ac16_neu", max_age=H,
    ) == neue_id, "die frisch geschriebene Datei muss den Deckel ueberleben"
    assert [r for r in caplog.records if r.levelno == logging.WARNING], (
        "der Eingriff des Deckels ist still -- eine Warnzeile fehlt"
    )


def test_ac16_bytedeckel_greift_bei_wenigen_sehr_grossen_dateien(monkeypatch, caplog):
    """AC-16 (Bytes): wenige sehr grosse Dateien ueberschreiten den Bytedeckel,
    obwohl die Dateizahl klein ist -> die aeltesten werden verdraengt, danach
    liegt die Summe am Deckel, eine Warnzeile nennt den Eingriff."""
    from services import alert_input_capture

    grenze = 3000
    monkeypatch.setattr(alert_input_capture, "_MAX_BYTES_PER_DIR", grenze, raising=False)
    d = _system_dir("nowcast")
    for i in range(4):
        _altdatei(d, f"nowcast_ac16b_k{i}", (i + 1) * H, padding=1500)

    with caplog.at_level(logging.WARNING, logger="alert_input_capture"):
        _schreibe("nowcast_ac16b_neu")

    summe = sum(p.stat().st_size for p in d.glob("*.json"))
    assert summe <= grenze, f"Bytedeckel {grenze} ueberschritten: {summe} Bytes"
    assert [r for r in caplog.records if r.levelno == logging.WARNING], (
        "der Eingriff des Bytedeckels ist still -- eine Warnzeile fehlt"
    )


# ---------------------------------------------------------------------------
# AC-17 -- alle drei Zweige, ueber die echten Schreibfunktionen
# ---------------------------------------------------------------------------

def test_ac17_alle_drei_zweige_behalten_ueber_50_dateien_der_letzten_24h():
    """AC-17: Zweig a (``capture_user_scoped``), Zweig b (``official_alert``) und
    Zweig c (``nowcast``) schreiben je 60 Mitschnitte (mehr als das fruehere
    50er-Limit) -> in jedem Zweig bleiben alle 60, die Zweige beeinflussen sich
    nicht."""
    from app.loader import get_data_dir
    from services import alert_input_capture

    uid = _uid("ac17")
    # Begrenzung je Zweig (Adversary F003): je Zweig ein ueber 24 h alter
    # Mitschnitt eines Keys, der danach frisch beschrieben wird -- er muss weg.
    dir_a = get_data_dir(uid) / "alert_input"
    dir_a.mkdir(parents=True, exist_ok=True)
    alt_a = _altdatei(dir_a, "forecast_change_trip_e0", 30 * H)
    alt_b = _altdatei(_system_dir("official_alert"), "vigilance_0", 30 * H)
    alt_c = _altdatei(_system_dir("nowcast"), "nowcast_0", 30 * H)
    for i in range(60):
        assert alert_input_capture.capture_user_scoped(
            uid, entity_type="trip", entity_id=f"e{i % 3}",
            payload={"changes": [{
                "metric": "gust", "old_value": 1.0, "new_value": 2.0,
                "delta": 1.0, "threshold": 0.5, "severity": "minor",
                "direction": "increase", "segment_id": "1",
            }]},
        )
        _schreibe(f"vigilance_{i % 3}", branch="official_alert")
        _schreibe(f"nowcast_{i % 3}", branch="nowcast")

    a = list((get_data_dir(uid) / "alert_input").glob("*.json"))
    b = list(_system_dir("official_alert").glob("*.json"))
    c = list(_system_dir("nowcast").glob("*.json"))
    assert (len(a), len(b), len(c)) == (60, 60, 60), (
        f"je Zweig 60 Mitschnitte erwartet (a, b, c): {(len(a), len(b), len(c))}"
    )
    assert (alt_a.exists(), alt_b.exists(), alt_c.exists()) == (False, False, False), (
        "je Zweig muss der ueber 24 h alte Mitschnitt entfernt sein (a, b, c): "
        f"{(alt_a.exists(), alt_b.exists(), alt_c.exists())}"
    )


# ---------------------------------------------------------------------------
# AC-18 -- Korrelation ueberlebt den Ansturm anderer Keys
# ---------------------------------------------------------------------------

def test_ac18_latest_capture_id_findet_den_mitschnitt_nach_6h_und_50_fremden_dateien():
    """AC-18: zwischen dem Mitschnitt eines Keys (6 h alt) und der Korrelation
    liegen mehr als 50 Mitschnitte anderer Keys -> ``latest_capture_id`` liefert
    weiterhin die ``capture_id`` des passenden Mitschnitts."""
    from services import alert_input_capture

    d = _system_dir("nowcast")
    key = "nowcast_ac18_korreliert"
    datei = _altdatei(d, key, 6 * H)
    erwartet = json.loads(datei.read_text())["capture_id"]

    for i in range(60):
        _schreibe(f"nowcast_ac18_fremd{i % 5}")

    assert alert_input_capture.latest_capture_id(
        "nowcast", key, max_age=24 * H,
    ) == erwartet, "der Mitschnitt wurde vom Ansturm fremder Keys verdraengt"


# ---------------------------------------------------------------------------
# Adversary F006 -- latest_capture_id filtert per Dateinamen-Praefix, bevor es
# JSON liest; Ergebnis unveraendert (Key mit ``_``, gekuerzter Key)
# ---------------------------------------------------------------------------

def test_f006_key_mit_unterstrich_und_praefix_nachbar_liefert_den_richtigen():
    """``nowcast_f6`` und ``nowcast_f6_b`` teilen ein Namenspraefix; jede
    Abfrage liefert die capture_id IHRES Keys, auch wenn der Nachbar juenger ist."""
    from services import alert_input_capture

    a = _schreibe("nowcast_f6")
    b = _schreibe("nowcast_f6_b")
    assert alert_input_capture.latest_capture_id("nowcast", "nowcast_f6", max_age=H) == a
    assert alert_input_capture.latest_capture_id("nowcast", "nowcast_f6_b", max_age=H) == b


def test_f006_gekuerzte_keys_mit_gleichem_dateipraefix_werden_per_json_getrennt():
    """``_safe_key`` kuerzt auf 80 Zeichen: zwei Keys, die sich erst danach
    unterscheiden, landen unter demselben Dateinamen-Praefix -- die Abfrage
    verifiziert ``source_key`` im JSON und liefert den richtigen Mitschnitt,
    nicht den juengeren des Nachbarn."""
    from services import alert_input_capture

    lang_a, lang_b = "n" * 80 + "_A", "n" * 80 + "_B"
    a = _schreibe(lang_a)
    b = _schreibe(lang_b)
    assert alert_input_capture.latest_capture_id("nowcast", lang_a, max_age=H) == a
    assert alert_input_capture.latest_capture_id("nowcast", lang_b, max_age=H) == b


def test_f006_dateien_fremder_keys_werden_nicht_gelesen():
    """Eine juengere Datei unter FREMDEM Dateinamen-Praefix, deren JSON
    (faelschlich) denselben ``source_key`` traegt, wird nicht beruecksichtigt
    -- Beleg, dass Dateien fremder Keys gar nicht erst geoeffnet werden (sonst
    gewaenne sie als juengster Treffer)."""
    from services import alert_input_capture

    d = _system_dir("nowcast")
    eigen_datei = _altdatei(d, "nowcast_f6_eigen", 120)       # 2 min alt
    eigene = json.loads(eigen_datei.read_text())["capture_id"]
    fremd = _altdatei(d, "nowcast_f6_fremd", 5)               # 5 s alt, juenger
    record = json.loads(fremd.read_text())
    record["source_key"] = "nowcast_f6_eigen"                 # faelschlich gleicher Key
    fremd.write_text(json.dumps(record))

    assert alert_input_capture.latest_capture_id(
        "nowcast", "nowcast_f6_eigen", max_age=H,
    ) == eigene, "eine Datei unter fremdem Dateinamen-Praefix wurde gelesen"


# ---------------------------------------------------------------------------
# Adversary F008 -- Altersfenster von latest_capture_id
# ---------------------------------------------------------------------------

def test_f008_abgelaufener_einziger_mitschnitt_liefert_none():
    """Einzige Datei des Keys mit ``captured_at = jetzt - 2*max_age`` (liegt
    noch im Verzeichnis, juenger als 24 h) -> ausserhalb ``max_age`` -> None."""
    from services import alert_input_capture

    max_age = 60.0
    datei = _altdatei(_system_dir("nowcast"), "nowcast_f8_alt", 2 * max_age)
    assert datei.exists(), "Aufbau: Datei liegt noch im Verzeichnis"
    assert alert_input_capture.latest_capture_id(
        "nowcast", "nowcast_f8_alt", max_age=max_age,
    ) is None


def test_f008_zukunftszeitstempel_liefert_none():
    """Ein Mitschnitt mit ``captured_at`` in der Zukunft ist kein gueltiger
    Treffer (Uhrensprung/kaputte Datei) -> None."""
    from services import alert_input_capture

    _altdatei(_system_dir("nowcast"), "nowcast_f8_zukunft", -H)
    assert alert_input_capture.latest_capture_id(
        "nowcast", "nowcast_f8_zukunft", max_age=24 * H,
    ) is None


def test_f008_zukunftsdatei_wird_uebersprungen_aelterer_gueltiger_gewinnt():
    """Die (nach Namen) juengste Datei liegt in der Zukunft und wird
    uebersprungen; geliefert wird der naechstaeltere gueltige Mitschnitt."""
    from services import alert_input_capture

    d = _system_dir("nowcast")
    gueltig = _altdatei(d, "nowcast_f8_misch", 10 * 60)
    _altdatei(d, "nowcast_f8_misch", -H)
    erwartet = json.loads(gueltig.read_text())["capture_id"]
    assert alert_input_capture.latest_capture_id(
        "nowcast", "nowcast_f8_misch", max_age=H,
    ) == erwartet


# ---------------------------------------------------------------------------
# Adversary F009 -- Dateien ohne passendes Namensmuster im Prune
# ---------------------------------------------------------------------------

def test_f009_fremddatei_ohne_namensmuster_stoert_den_mitschnitt_nicht():
    """Eine ueber 24 h alte Datei, deren Name NICHT dem Muster
    ``{key}_{zeitstempel}.json`` folgt, liegt im Verzeichnis -> das Schreiben
    eines Mitschnitts funktioniert, ``latest_capture_id`` findet ihn, und die
    Fremddatei bleibt unangetastet (nur der Gesamtdeckel duerfte sie treffen)."""
    from services import alert_input_capture

    d = _system_dir("nowcast")
    fremd = d / "notizen.json"
    inhalt = '{"hinweis": "kein Mitschnitt"}'
    fremd.write_text(inhalt)
    ts = time.time() - 30 * H
    os.utime(fremd, (ts, ts))

    cid = alert_input_capture.capture_system(
        branch="nowcast", source_key="nowcast_f9", payload={"n": 1},
    )

    assert cid, "Mitschnitt wurde nicht geschrieben (Prune an der Fremddatei gescheitert?)"
    assert alert_input_capture.latest_capture_id("nowcast", "nowcast_f9", max_age=H) == cid
    assert fremd.exists() and fremd.read_text() == inhalt, "Fremddatei wurde angetastet"
