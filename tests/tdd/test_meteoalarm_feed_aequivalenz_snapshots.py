"""Kern-Nachweis: Feed-Weg AT/IT deckt die eingefrorenen EDR-Snapshots ab (Issue #2266, Epic #2258).

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md (AC-2, AC-7 Nutzbarkeit)

Herkunft der Logik: die Aequivalenz-Gates ``test_ac3_feed_menge_ist_obermenge_...``
in ``test_meteoalarm_feed_italien.py`` (~:741) und ``test_ac5_feed_menge_ist_obermenge_...``
in ``test_meteoalarm_feed_oesterreich.py`` (~:981), samt ``_alert_identitaet``,
``_pruefe_obermenge`` und ``_lade_alert_liste_aus_json``.

Warum die Originale ``live`` tragen: sie speisen Feed und ZAMG ueber ECHTE
lokale HTTP-Server (``http.server`` auf 127.0.0.1) ein. Das ist kein Fremdnetz,
aber ein Socket -- und die Kern-Schicht laeuft mit ``--disable-socket``; die
Dateien wurden deshalb modulweit in die Live-Schicht verschoben (CI-Vermessung
2026-08-04, #1196). Damit lief der einzige Aequivalenznachweis nie im Kern.

Diese Datei laeuft OHNE Marker und ohne Socket: die Daten kommen ueber den
Cache-Weg wie in ``test_meteoalarm_feed_deutschland.py`` -- ``meteoalarm_feed._cache``
und ``geosphere_warn._cache`` werden mit ECHTEN Eintraegen vorbelegt, ``fetch()``
laeuft ueber den echten Treffer-Zweig von ``warn_egress.cached_fetch()``. Der
Feed-Eintrag entsteht ueber den echten Parser ``meteoalarm_feed._parse_feed``
aus einem ``httpx.Response``-Objekt (ohne Transport), ist also exakt der Wert,
den ein echter Abruf ablegen wuerde.

Die Vergleichsmenge kommt STRIKT aus ``edr_snapshot_{it,at}.json`` (eingefroren,
Aufzeichnung 2026-08-01) -- nie aus einer EDR-Klasse, die mit #2266 entfaellt.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from services.official_alerts.models import OfficialAlert

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"

# Aufnahmezeitpunkte der beiden Aequivalenz-Aufzeichnungen (alle Seiten derselben Minute).
AUFNAHME_UTC_IT = datetime(2026, 8, 1, 16, 6, 28, tzinfo=timezone.utc)
AUFNAHME_UTC_AT = datetime(2026, 8, 1, 16, 19, 43, tzinfo=timezone.utc)

_FEED_FIXTURE_DATEIEN = (
    "edr_snapshot_it.json",
    "edr_snapshot_at.json",
    "feed_italy_equivalence.json",
    "feed_austria_equivalence.json",
    "zamg_snapshot_at.json",
    "feed_italy_sample.json",
    "feed_austria_sample.json",
    "feed_germany_sample.json",
)


def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum DIESER Testdatei stammen."""
    from services.official_alerts import meteoalarm, meteoalarm_feed

    for modul in (meteoalarm_feed, meteoalarm):
        pfad = Path(modul.__file__).resolve()
        assert str(pfad).startswith(str(_REPO_ROOT)), (
            f"Pruefling {pfad} liegt ausserhalb von {_REPO_ROOT} -- fremde Kopie"
        )


@pytest.fixture(autouse=True)
def _caches_leeren():
    """Frischer ZAMG- und Feed-Cache je Test."""
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()
    yield
    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()


# ── Vergleichslogik (1:1 aus den Live-Originalen) ─────────────────────────────

def _alert_identitaet(alert: OfficialAlert) -> tuple:
    """Gefahrenart + Stufe + Region + Gueltigkeitszeitraum. Bewusst ohne ``label``
    (Freitext); ``region_label`` MUSS mit rein (F004: sonst maskieren zwei
    zeitfeldlose Warnungen einander); Vergleich ueber ``datetime``-Objekte, nicht
    ``.isoformat()`` (sonst falscher Alarm bei zwei Notationen)."""
    return (alert.hazard, alert.level, alert.region_label, alert.valid_from, alert.valid_to)


def _pruefe_obermenge(trippunkte: list, feed_je_punkt: dict, edr_je_punkt: dict) -> list[str]:
    """Leer = die Feed-Menge ist fuer JEDEN Trip-Punkt Obermenge der Snapshot-Menge."""
    abweichungen: list[str] = []
    for punkt in trippunkte:
        feed_ids = {_alert_identitaet(a) for a in feed_je_punkt.get(punkt, [])}
        edr_ids = {_alert_identitaet(a) for a in edr_je_punkt.get(punkt, [])}
        fehlend = edr_ids - feed_ids
        if fehlend:
            abweichungen.append(
                f"Trip-Punkt {punkt}: im EDR-Snapshot, aber NICHT im Feed: {sorted(fehlend, key=repr)}"
            )
    return abweichungen


def _lade_alert_liste_aus_json(eintraege: list[dict]) -> dict:
    """``[{"lat", "lon", "alerts": [...]}]`` (Schema der EDR-Snapshots) -> Punkt -> Alerts.
    ``region_label`` ist PFLICHT (geht in die Identitaet ein)."""
    ergebnis: dict = {}
    for eintrag in eintraege:
        ergebnis[(eintrag["lat"], eintrag["lon"])] = [
            OfficialAlert(
                source="meteoalarm",
                hazard=a["hazard"],
                level=a["level"],
                label=a.get("label", ""),
                region_label=a.get("region_label"),
                valid_from=datetime.fromisoformat(a["valid_from"]) if a.get("valid_from") else None,
                valid_to=datetime.fromisoformat(a["valid_to"]) if a.get("valid_to") else None,
            )
            for a in eintrag.get("alerts", [])
        ]
    return ergebnis


# ── Einspeisung ueber den Cache-Weg (kein Socket) ─────────────────────────────

def _lade_json(name: str):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _feed_vorbelegen(land: str, feed_body: dict) -> None:
    """Echter Cache-Eintrag, wie ``warn_egress._store_entry`` ihn nach einem
    erfolgreichen Abruf ablegt -- Daten durch den echten Feed-Parser."""
    from services.official_alerts import meteoalarm_feed, warn_egress

    antwort = httpx.Response(200, json=feed_body,
                             request=httpx.Request("GET", f"https://feeds.meteoalarm.org/{land}"))
    meteoalarm_feed._cache[land] = {
        "data": meteoalarm_feed._parse_feed(antwort),
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL,
    }


def _zamg_vorbelegen(eintraege: list[dict]) -> None:
    """ZAMG-Aufzeichnung derselben Minute in den GeoSphere-Cache: Erfolgsantwort
    als Erfolg, 404 als "nicht zustaendig", jeder andere Status als Fehlschlag --
    jeweils in der Form, die ``cached_fetch`` selbst ablegt."""
    from services.official_alerts import geosphere_warn, warn_egress

    for eintrag in eintraege:
        if "status" in eintrag:
            daten, ttl = ({}, warn_egress.WARN_NOT_COVERED_TTL) if eintrag["status"] == 404 \
                else (None, warn_egress.WARN_FAILURE_TTL)
        else:
            daten, ttl = eintrag["response"], warn_egress.WARN_SUCCESS_TTL
        geosphere_warn._cache[geosphere_warn._round_coord(eintrag["lat"], eintrag["lon"])] = {
            "data": daten, "fetched_at": time.monotonic(), "ttl": ttl,
        }


def _feed_je_punkt(land: str, trippunkte: list) -> dict:
    from services.official_alerts import meteoalarm_feed

    quelle = meteoalarm_feed.MeteoAlarmFeedSource(land)
    ergebnis = {}
    for punkt in trippunkte:
        assert quelle.covers(*punkt) is True, (
            f"Aufbaupruefung: {punkt} muss von der Feed-Quelle {land} abgedeckt sein"
        )
        ergebnis[punkt] = quelle.fetch(*punkt)
    return ergebnis


def _snapshot(name: str) -> tuple[list, dict]:
    edr_je_punkt = _lade_alert_liste_aus_json(_lade_json(name))
    trippunkte = list(edr_je_punkt)
    assert len(trippunkte) == 8 and all(edr_je_punkt[p] for p in trippunkte), (
        f"Aufbaupruefung {name}: 8 Trip-Punkte mit JE mindestens einer Warnung erwartet -- "
        f"gegen leere Mengen ist jede Obermengen-Pruefung trivial erfuellt. Erhalten: "
        f"{[(p, len(edr_je_punkt[p])) for p in trippunkte]}"
    )
    return trippunkte, edr_je_punkt


# ── Tests ────────────────────────────────────────────────────────────────────

def test_ac7_alle_feed_fixtures_bleiben_vorhanden():
    """AC-7 (zweiter Teil): GIVEN der Rueckbau, WHEN das Fixture-Verzeichnis
    geprueft wird, THEN liegen alle bleibenden Feed-Fixtures weiterhin vor."""
    fehlend = [n for n in _FEED_FIXTURE_DATEIEN if not (_FIXTURES / n).is_file()]
    assert not fehlend, f"Feed-Fixtures fehlen: {fehlend}"


def test_ac2_feed_italien_deckt_eingefrorenen_edr_snapshot_je_trippunkt_ab():
    """AC-2 (IT): GIVEN ``feed_italy_equivalence.json`` und der zur selben Minute
    eingefrorene ``edr_snapshot_it.json`` (8 reale Trip-Punkte), WHEN
    ``MeteoAlarmFeedSource("IT").fetch()`` je Punkt ueber den Cache-Weg laeuft,
    THEN ist die Feed-Menge je Punkt Obermenge der Snapshot-Menge.

    Verglichen wird die ROHE Quellenausgabe (kein ``now``-Fenster, kein
    Registry-Dedup) -- wie im Original begruendet: beides sitzt in ``base.py``
    HINTER der Quelle und koennte eine fehlende Warnung maskieren."""
    import services.official_alerts.base as oa_base

    _assert_pruefling_aus_diesem_baum()
    trippunkte, edr_je_punkt = _snapshot("edr_snapshot_it.json")
    alle_edr = [a for p in trippunkte for a in edr_je_punkt[p]]
    assert len(oa_base.filter_alerts_to_window(alle_edr, AUFNAHME_UTC_IT, None)) == len(alle_edr), (
        "Aufbaupruefung: der IT-Snapshot darf zum Aufnahmezeitpunkt keine abgelaufene "
        "Warnung tragen -- sonst waeren die Seiten nicht zeitgleich gezogen"
    )

    _feed_vorbelegen("IT", _lade_json("feed_italy_equivalence.json"))
    abweichungen = _pruefe_obermenge(trippunkte, _feed_je_punkt("IT", trippunkte), edr_je_punkt)

    assert not abweichungen, "\n".join(abweichungen)


def test_ac2_feed_oesterreich_deckt_eingefrorenen_edr_snapshot_je_trippunkt_ab():
    """AC-2 (AT): GIVEN ``feed_austria_equivalence.json``, die ZAMG-Zonenzuordnung
    ``zamg_snapshot_at.json`` und der eingefrorene ``edr_snapshot_at.json`` (8
    reale Trip-Punkte, inkl. Karnischer Hoehenweg), WHEN
    ``MeteoAlarmFeedSource("AT").fetch()`` je Punkt ueber den Cache-Weg laeuft,
    THEN ist die Feed-Menge je Punkt Obermenge der Snapshot-Menge."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn

    _assert_pruefling_aus_diesem_baum()
    trippunkte, edr_je_punkt = _snapshot("edr_snapshot_at.json")
    alle_edr = [a for p in trippunkte for a in edr_je_punkt[p]]
    assert len(oa_base.filter_alerts_to_window(alle_edr, AUFNAHME_UTC_AT, None)) < len(alle_edr), (
        "Aufbaupruefung: der AT-Snapshot traegt zum Aufnahmezeitpunkt bereits abgelaufene "
        "Warnungen -- genau sie belegen, dass der Rohvergleich (ohne now-Filter) noetig ist"
    )

    zamg = _lade_json("zamg_snapshot_at.json")
    zamg_punkte = {geosphere_warn._round_coord(e["lat"], e["lon"]) for e in zamg}
    assert all(geosphere_warn._round_coord(*p) in zamg_punkte for p in trippunkte), (
        "Aufbaupruefung: die ZAMG-Aufzeichnung muss jeden Trip-Punkt abdecken"
    )
    _zamg_vorbelegen(zamg)
    _feed_vorbelegen("AT", _lade_json("feed_austria_equivalence.json"))
    abweichungen = _pruefe_obermenge(trippunkte, _feed_je_punkt("AT", trippunkte), edr_je_punkt)

    assert not abweichungen, "\n".join(abweichungen)


@pytest.mark.parametrize("land,snapshot", [("IT", "edr_snapshot_it.json"), ("AT", "edr_snapshot_at.json")])
def test_ac2_negativkontrolle_leerer_feed_meldet_jeden_trippunkt(land, snapshot):
    """AC-2 Negativkontrolle mit ECHTEN Snapshots: GIVEN der Feed traegt keine
    einzige Warnung, WHEN derselbe Vergleich laeuft, THEN meldet er JEDEN der 8
    Trip-Punkte als Abweichung -- belegt, dass die eingespeisten Feed-Daten das
    Ergebnis tatsaechlich treiben (sonst waere das Gruen oben wertlos)."""
    trippunkte, edr_je_punkt = _snapshot(snapshot)
    if land == "AT":
        _zamg_vorbelegen(_lade_json("zamg_snapshot_at.json"))
    _feed_vorbelegen(land, {"warnings": []})

    abweichungen = _pruefe_obermenge(trippunkte, _feed_je_punkt(land, trippunkte), edr_je_punkt)

    assert len(abweichungen) == len(trippunkte), (
        f"leerer Feed muss alle {len(trippunkte)} Punkte als Luecke melden, erhalten "
        f"{len(abweichungen)}"
    )


def test_pruefe_obermenge_erkennt_fehlende_snapshot_warnung(tmp_path):
    """Gegenprobe der Vergleichslogik (beide Richtungen): Obermenge erfuellt =>
    keine Abweichung; eine Snapshot-Warnung fehlt im Feed => Abweichung."""
    edr_datei = tmp_path / "edr_konstruiert.json"
    edr_datei.write_text(json.dumps([{
        "lat": 46.7597, "lon": 12.4177,
        "alerts": [{
            "hazard": "extreme_heat", "level": 2, "region_label": "Lienz",
            "valid_from": "2026-08-01T00:00:00+02:00", "valid_to": "2026-08-01T23:59:59+02:00",
        }],
    }]), encoding="utf-8")
    edr_je_punkt = _lade_alert_liste_aus_json(json.loads(edr_datei.read_text(encoding="utf-8")))
    punkt = (46.7597, 12.4177)
    cest = timezone(timedelta(hours=2))

    obermenge = {punkt: [
        OfficialAlert(source="meteoalarm", hazard="extreme_heat", level=2, label="Hitze",
                      region_label="Lienz", valid_from=datetime(2026, 8, 1, tzinfo=cest),
                      valid_to=datetime(2026, 8, 1, 23, 59, 59, tzinfo=cest)),
        OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=2, label="Gewitter"),
    ]}
    assert _pruefe_obermenge([punkt], obermenge, edr_je_punkt) == []

    abweichungen = _pruefe_obermenge([punkt], {punkt: []}, edr_je_punkt)
    assert abweichungen and "extreme_heat" in abweichungen[0]


def test_alert_identitaet_ohne_zeitfelder_maskiert_keine_fehlende_warnung():
    """F004 Teil 1: zwei zeitfeldlose Warnungen gleicher Gefahr/Stufe, aber
    verschiedener Region, duerfen einander nicht maskieren."""
    punkt = (1.0, 2.0)
    edr = {punkt: [OfficialAlert(source="meteoalarm", hazard="flood", level=2, label="Hochwasser",
                                 region_label="Comune Alpha")]}
    feed = {punkt: [OfficialAlert(source="meteoalarm", hazard="flood", level=2, label="Hochwasser",
                                  region_label="Comune Beta")]}

    assert _pruefe_obermenge([punkt], feed, edr), "fehlende Warnung wurde maskiert"


def test_alert_identitaet_gleicher_zeitpunkt_verschiedene_notation_gilt_als_gleich():
    """F004 Teil 2: derselbe Zeitpunkt in zwei ISO-Notationen ist gleich."""
    zeit_utc = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    zeit_offset = datetime(2026, 8, 1, 11, 0, tzinfo=timezone(timedelta(hours=2)))
    assert zeit_utc.isoformat() != zeit_offset.isoformat(), "Testaufbau: Notationen muessen sich unterscheiden"

    a = OfficialAlert(source="meteoalarm", hazard="storm", level=2, label="Sturm",
                      valid_from=zeit_utc, valid_to=zeit_utc)
    b = OfficialAlert(source="meteoalarm", hazard="storm", level=2, label="Sturm",
                      valid_from=zeit_offset, valid_to=zeit_offset)

    assert _alert_identitaet(a) == _alert_identitaet(b)
