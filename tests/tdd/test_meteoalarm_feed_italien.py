"""TDD RED — MeteoAlarm Italien: Feed-Bestandsquelle statt EDR-Index (Issue #1445 S1).

SPEC: docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md ("## Acceptance
Criteria", AC-1 bis AC-7)

Pruefling ist ``src/services/official_alerts/meteoalarm_feed.py`` (existiert in
dieser RED-Phase noch NICHT). Der Pruefling wird ueber diese Testdatei relativ
aufgeloest -- ``_assert_pruefling_aus_diesem_baum()`` belegt das bei jedem Test
(Projektregel #1409: ein Test darf NIE die unveraenderte Hauptrepo-Kopie messen).

Kein Mock-Theater, kein echtes Netz:
- **Fake-Transport = echter lokaler HTTP-Server** (``http.server``, Muster aus
  ``test_meteoalarm_index_coverage.py``). ``_JsonServer`` liefert eine
  (mutierbare) JSON-Antwort oder einen festen Fehlerstatus aus und ZAEHLT jeden
  Abruf, der ihn tatsaechlich erreicht -- ein Cache-Treffer erreicht ihn nie.
- **Aufgezeichnete Fixture:** ``tests/fixtures/meteoalarm_feed/feed_italy_sample.json``
  -- 10 reale, unveraenderte Eintraege aus einem echten Vollabruf von
  ``https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy`` (2026-07-31,
  Herkunft/Auswahl s. README.md im selben Verzeichnis).
- **Region-Praefix -> EMMA-ID:** aus dem echten Feed-Datensatz extrahiert und
  gegen alle 187 echten Zonencodes in ``dpc_zones.json`` verifiziert (Spec
  Implementation Details Punkt 3) -- ``_VERIFIED_REGION_PREFIX_TO_EMMA`` unten
  ist die verbindliche Tabelle fuer Implementierung UND Tests.

Erwartetes Modul-Interface (aus der Spec "## Source" plus den Anforderungen
dieser Tests -- FEED_BASE_URL ist analog ``meteoalarm.METEOALARM_BASE_URL``
noetig, damit Tests einen lokalen Server injizieren koennen):

- ``meteoalarm_feed.MeteoAlarmFeedSource`` — Klasse mit ``name``/``covers()``/
  ``fetch()`` (erfuellt ``OfficialAlertSource``).
- ``meteoalarm_feed._zone_for_point(lat, lon) -> str | None`` — EMMA-ID oder
  ``None``, wenn der Punkt keiner der 187 DPC-Zonen zugeordnet werden kann.
- ``meteoalarm_feed._get_cached_feed() -> dict | None`` — TTL-gecachter
  Feed-Abruf ueber ``warn_egress.cached_fetch()``.
- ``meteoalarm_feed._parse_feed(resp) -> dict`` — Antwort-Parser.
- ``meteoalarm_feed._REGION_PREFIX_TO_EMMA: dict[str, str]`` — die verifizierte
  20-Zeilen-Tabelle.
- ``meteoalarm_feed._cache: dict`` — Modul-Cache-Dict (Konvention analog
  ``dpc._cache``), von Tests zwischen zwei Auffrischungszyklen leerbar.
- ``meteoalarm_feed.FEED_BASE_URL: str`` — Basis-URL, von Tests umlenkbar.
"""
from __future__ import annotations

import http.server
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from services.official_alerts.models import OfficialAlert

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"

# Reale Punkte + ihre DPC-/EMMA-Zone (per ``dpc._zone_at()`` gegen die
# eingecheckte Geometrie ermittelt und mit den EMMA-IDs aus dem echten Feed
# abgeglichen -- volle Herleitung in ``tests/fixtures/meteoalarm_feed/README.md``).
ROM = (41.9028, 12.4964)  # Lazi-D -> IT012 (Lazio)
AOSTA = (45.7372, 7.3201)  # VDAo-A -> IT004 (Valle d'Aosta)
MILAN = (45.4642, 9.1900)  # Lomb-09 -> IT003 (Lombardia)
MEER_UNMAPPED = (37.0, 13.5)  # in der DPC-Bbox, ausserhalb aller 187 Zonen-Polygone

# Referenzzeitpunkt fuer "aktuell gueltig" (Fixture aufgezeichnet 2026-07-31).
TEST_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

# Identifier der Lazio-Hitzewarnung in der Fixture (fuer den AC-6-Test).
_LAZIO_HITZE_ID = "2.49.0.0.380.3.IT.260731115902.089"

# Verbindliche Tabelle (Spec Implementation Details Punkt 3): aus dem echten
# Feed-Datensatz extrahiert (``area[].geocode[].valueName == "EMMA_ID"`` je
# ``areaDesc``) und gegen alle 187 ``zona``-Codes in ``dpc_zones.json``
# abgeglichen -- jeder Code traegt als ersten Bestandteil (vor dem ``-``, fest
# 4 Zeichen) genau einen dieser 20 Regionspraefixe. Deckt sich mit den drei in
# der Spec vorab genannten Paaren (VDAo->IT004, Lazi->IT012, Ligu->IT007).
_VERIFIED_REGION_PREFIX_TO_EMMA: dict[str, str] = {
    "Cala": "IT001", "Tren": "IT002", "Lomb": "IT003", "VDAo": "IT004",
    "Piem": "IT005", "Vene": "IT006", "Ligu": "IT007", "Emil": "IT008",
    "Tosc": "IT009", "Umbr": "IT010", "Marc": "IT011", "Lazi": "IT012",
    "Abru": "IT013", "Moli": "IT014", "Pugl": "IT015", "Camp": "IT016",
    "Basi": "IT017", "Sici": "IT018", "Sard": "IT019", "Friu": "IT020",
}


def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum DIESER Testdatei
    stammen -- sonst misst der Test aus einem Worktree die unveraenderte
    Hauptrepo-Kopie und meldet falsches Gruen."""
    from services.official_alerts import meteoalarm_feed

    modul = Path(meteoalarm_feed.__file__).resolve()
    assert str(modul).startswith(str(_REPO_ROOT)), (
        f"Pruefling {modul} liegt ausserhalb von {_REPO_ROOT} -- der Test wuerde "
        f"eine fremde Kopie messen"
    )


@pytest.fixture(autouse=True)
def _feed_cache_leeren():
    """Frischer Feed-Cache je Test -- No-Op, solange der Pruefling noch nicht
    existiert (RED-Phase)."""
    try:
        from services.official_alerts import meteoalarm_feed
    except ImportError:
        yield
        return
    meteoalarm_feed._cache.clear()
    yield
    meteoalarm_feed._cache.clear()


def _load_sample_feed() -> dict:
    return json.loads((_FIXTURES / "feed_italy_sample.json").read_text(encoding="utf-8"))


class _Zaehler:
    """Zaehlt ausschliesslich Anfragen, die den lokalen Server WIRKLICH erreichen."""

    def __init__(self) -> None:
        self.treffer = 0
        self.pfade: list[str] = []


class _JsonServer:
    """Echter lokaler HTTP-Server (kein Mock): liefert ``.body`` als JSON oder
    ``.fail_status`` als festen Fehlerstatus. ``.body`` ist zwischen zwei
    Anfragen austauschbar (AC-6: zweiter Auffrischungszyklus mit anderem
    Feed-Inhalt)."""

    def __init__(self, body: dict, *, fail_status: "int | None" = None) -> None:
        self.body = body
        self.fail_status = fail_status
        self.zaehler = _Zaehler()
        aussen = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib-Signatur
                aussen.zaehler.treffer += 1
                aussen.zaehler.pfade.append(self.path)
                if aussen.fail_status is not None:
                    self.send_response(aussen.fail_status)
                    self.end_headers()
                    return
                payload = json.dumps(aussen.body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
                pass

        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Region-Praefix-Tabelle: Vollstaendigkeit + exakter Inhalt (Spec Implementation
# Details Punkt 3, Pflicht-Herleitung vor Implementierung).
# ---------------------------------------------------------------------------

def test_region_prefix_tabelle_ist_vollstaendig_und_exakt():
    """GIVEN die eingecheckte DPC-Zonen-Geometrie (187 Zonen, 20 Regionspraefixe)
    WHEN die Region-Praefix-EMMA-Tabelle des Pruefling-Moduls gelesen wird THEN
    deckt sie ALLE 20 realen Praefixe ab UND stimmt exakt mit der in der
    RED-Phase gegen den echten Feed-Datensatz verifizierten Tabelle ueberein."""
    from services.official_alerts import dpc

    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    zona_prefixes = {z["zona"].split("-", 1)[0] for z in dpc._ZONES}
    assert len(zona_prefixes) == 20, (
        f"Aufbaupruefung: die eingecheckte Geometrie muss genau 20 Regions-"
        f"Praefixe tragen, gefunden: {sorted(zona_prefixes)}"
    )
    assert zona_prefixes == set(_VERIFIED_REGION_PREFIX_TO_EMMA), (
        f"Tabelle deckt nicht alle 187 echten Zonencodes ab. Fehlend: "
        f"{sorted(zona_prefixes - set(_VERIFIED_REGION_PREFIX_TO_EMMA))}"
    )
    assert meteoalarm_feed._REGION_PREFIX_TO_EMMA == _VERIFIED_REGION_PREFIX_TO_EMMA, (
        f"die Modul-Tabelle muss exakt der in der RED-Phase verifizierten "
        f"Tabelle entsprechen (s. tests/fixtures/meteoalarm_feed/README.md). "
        f"Erhalten: {getattr(meteoalarm_feed, '_REGION_PREFIX_TO_EMMA', None)}"
    )


def test_zone_for_point_resolves_reale_punkte():
    """Grundlage fuer AC-1/AC-5: ``_zone_for_point()`` loest reale Punkte auf die
    verifizierten EMMA-IDs auf, ein Punkt ausserhalb aller Zonen liefert None."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._zone_for_point(*ROM) == "IT012"
    assert meteoalarm_feed._zone_for_point(*AOSTA) == "IT004"
    assert meteoalarm_feed._zone_for_point(*MILAN) == "IT003"
    assert meteoalarm_feed._zone_for_point(*MEER_UNMAPPED) is None


# ---------------------------------------------------------------------------
# Regress-Waechter (Fix-Runde 1): die franzoesische Ausnahme aus
# MeteoAlarmSource.covers() (Issue #1397 S2b, meteoalarm.py:1046-1057) MUSS
# auch fuer die neue Feed-Quelle gelten -- die DPC-Bbox reicht (wie die
# INCA-Bbox) rund 100 km in die Provence hinein. Ohne die Ausnahme wuerde
# ein einzelner franzoesischer Ort (Fréjus) im Ortsvergleich wieder den
# "nicht abrufbar"-Hinweis fuer die gesamte Matrix kippen.
# ---------------------------------------------------------------------------

FREJUS = (43.4330, 6.7370)  # Frankreich (Var), liegt in der DPC-Bbox


def test_covers_schliesst_franzoesisches_departement_aus_wie_meteoalarm_py():
    """GIVEN Fréjus (Frankreich, Var-Département) liegt geografisch innerhalb
    der groben DPC-Bbox, WHEN MeteoAlarmFeedSource.covers() geprueft wird,
    THEN gilt der Punkt NICHT als abgedeckt -- exakt dieselbe Ausnahme wie in
    MeteoAlarmSource.covers() (Issue #1397 S2b). Ein italienischer
    Kontrollpunkt (Mailand) bleibt dabei unveraendert abgedeckt."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    source = meteoalarm_feed.MeteoAlarmFeedSource("IT")

    assert source.covers(*FREJUS) is False, (
        "Fréjus (FR) muss von MeteoAlarmFeedSource.covers() ausgenommen sein -- "
        "sonst faerbt ein franzoesischer Ort im Ortsvergleich wieder alles ein "
        "(Regress zu Issue #1397 S2b)"
    )
    assert source.covers(*MILAN) is True, (
        "ein italienischer Kontrollpunkt (Mailand) muss weiterhin abgedeckt bleiben"
    )


def test_covers_ausschluss_loest_keinen_ausfallhinweis_fuer_frejus_aus():
    """GIVEN Fréjus liegt in einem franzoesischen Département, WHEN die
    amtlichen Warnungen ueber die echte Registry ermittelt werden, THEN bleibt
    unavailable=False -- vor dem Fix rief covers()==True fetch() auf,
    _zone_for_point() lieferte None, und mark_fetch_incomplete() faerbte den
    Ort faelschlich als 'nicht abrufbar' ein."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        _alerts, unavailable = get_official_alerts_with_status(*FREJUS, now=TEST_NOW)

        assert unavailable is False, (
            "ein franzoesischer Ort darf keinen 'nicht abrufbar'-Hinweis ueber die "
            "MeteoAlarm-Feed-Quelle ausloesen -- covers() muss ihn ausschliessen, "
            "bevor fetch() ueberhaupt aufgerufen wird"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-1: aktuell gueltige Warnung erscheint, kein EDR-Journal-Eintrag.
# ---------------------------------------------------------------------------

def test_ac1_aktuell_gueltige_warnung_erscheint_ohne_edr_journal_eintrag(monkeypatch):
    """AC-1: GIVEN Rom (Lazio, IT012) liegt in einer Zone mit aktuell gueltiger
    amtlicher Warnung (Hitze, orange, Fixture-Eintrag), WHEN die amtlichen
    Warnungen fuer diesen Ort ermittelt werden, THEN erscheint die Warnung im
    Ergebnis UND im Diagnose-Journal steht KEIN Eintrag mit
    host=api.meteoalarm.org."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed, warn_egress

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is False, f"Abruf muss erfolgreich sein, erhalten unavailable={unavailable}"
        assert any(a.hazard == "extreme_heat" and a.level == 3 for a in alerts), (
            f"die aktuell gueltige Hitzewarnung (orange, Stufe 3) fuer Lazio muss "
            f"erscheinen. Erhalten: {alerts}"
        )
        journal = warn_egress.WARN_CALLS_PATH.read_text(encoding="utf-8") \
            if warn_egress.WARN_CALLS_PATH.exists() else ""
        assert '"host": "api.meteoalarm.org"' not in journal, (
            f"kein Abruf gegen den bisherigen kontingentierten Warndienst darf "
            f"verzeichnet sein. Journal:\n{journal}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-2: mehrere Punkte im selben Fenster -> nur EIN echter Abruf.
# ---------------------------------------------------------------------------

def test_ac2_mehrere_punkte_im_selben_fenster_loesen_nur_einen_abruf_aus(monkeypatch):
    """AC-2: GIVEN Rom und Aosta (zwei verschiedene EMMA-Zonen) werden
    nacheinander abgefragt, WHEN beide ``fetch()``-Aufrufe im selben
    Auffrischungsfenster laufen, THEN erreicht nur EIN echter Aufruf den
    lokalen Server -- der zweite wird aus dem Bestand bedient (eine nationale
    Momentaufnahme deckt alle Zonen ab)."""
    from services.official_alerts import meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer(_load_sample_feed())
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        quelle = meteoalarm_feed.MeteoAlarmFeedSource("IT")

        quelle.fetch(*ROM)
        quelle.fetch(*AOSTA)

        assert server.zaehler.treffer == 1, (
            f"zwei Punkte im selben Fenster duerfen den Feed-Host nur EINMAL "
            f"erreichen, gemessen: {server.zaehler.treffer} echte Treffer"
        )
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# AC-3: Aequivalenz-Pflicht-Gate gegen einen zeitgleich aufgezeichneten
# EDR-Snapshot. Die EDR-Seite steht noch aus (Anbieter-Tageskontingent
# gesperrt bis 2026-08-01T15:45 UTC laut
# docs/context/fix-1397-wiederanlauf-ausbruch.md) -- der Test schlaegt deshalb
# BEWUSST fehl statt zu skippen (ein uebersprungener Sicherheits-Pflichttest
# waere ein getarnter Erfolg ohne Nachweis).
#
# Adversary-Fund F002 (Fix-Loop): die Obermengen-Pruefung war bisher nur ein
# Docstring-Versprechen -- der Test pruefte ausschliesslich ``edr_path.
# exists()``. Die Vergleichslogik (``_alert_identitaet``/``_pruefe_obermenge``/
# ``_lade_alert_liste_aus_json``) ist jetzt vollstaendig ausprogrammiert UND
# per Gegenprobe (``test_pruefe_obermenge_...``, kuenstliche tmp_path-Datei,
# NICHT die echte Fixture) in beide Richtungen bewiesen: Obermenge erfuellt
# => gruen, eine im EDR vorhandene Warnung fehlt im Feed => rot. Der
# eigentliche ``test_ac3_...`` bleibt UNVERAENDERT rot, solange
# ``edr_snapshot_it.json`` fehlt (kein Skip, kein getarnter Erfolg).
# ---------------------------------------------------------------------------

def _alert_identitaet(alert: "OfficialAlert") -> tuple:
    """Stabile Kennung fuer den AC-3-Obermengen-Vergleich: Gefahrenart +
    Stufe + Region + Gueltigkeitszeitraum. Bewusst NICHT ``label`` -- das ist
    Freitext und kann zwischen Feed- und EDR-Rendering variieren (Sprache/
    Formatierung/Gross-Kleinschreibung), ohne dass die Warnung inhaltlich
    eine andere ist; ``hazard``+``level``+Zeitraum sind dagegen die
    normalisierten, formatunabhaengigen Felder, die
    ``_group_and_map_info_entries`` fuer BEIDE Sammelwege (Feed wie EDR/XML)
    identisch befuellt.

    F004-Fix (Fix-Loop 2, Adversary-Fund):
    - ``region_label`` (von ``_group_and_map_info_entries`` fuer BEIDE
      Sammelwege identisch aus ``area_desc`` befuellt, meteoalarm.py:638)
      geht mit in die Kennung ein. Ohne dieses Feld kollidierten zwei
      voellig verschiedene Warnungen ohne Zeitfelder (laut base.py:67 ein
      realer, erwarteter Fall) auf ``(hazard, level, None, None)`` -- eine
      im EDR vorhandene, im Feed fehlende Warnung wurde durch eine
      unabhaengige Feed-Warnung MASKIERT.
    - Verglichen werden die ``datetime``-OBJEKTE selbst, nicht ihre
      ``.isoformat()``-Stringform: zwei Notationen desselben Zeitpunkts
      (z.B. ``...Z`` vs. ``...+02:00``) sind als ``datetime`` gleich, als
      String aber verschieden -- die Stringform erzeugte einen FALSCHEN
      ALARM."""
    return (
        alert.hazard,
        alert.level,
        alert.region_label,
        alert.valid_from,
        alert.valid_to,
    )


def _pruefe_obermenge(
    tourpunkte: list[tuple[float, float]],
    feed_je_punkt: dict,
    edr_je_punkt: dict,
) -> list[str]:
    """Vergleicht je Tourpunkt die Feed- gegen die EDR-Warnungsmenge (ueber
    ``_alert_identitaet``). Liefert eine Liste menschenlesbarer Abweichungen
    -- leer bedeutet: die Feed-Menge ist fuer JEDEN Tourpunkt eine Obermenge
    der EDR-Menge (AC-3)."""
    abweichungen: list[str] = []
    for punkt in tourpunkte:
        feed_ids = {_alert_identitaet(a) for a in feed_je_punkt.get(punkt, [])}
        edr_ids = {_alert_identitaet(a) for a in edr_je_punkt.get(punkt, [])}
        fehlend = edr_ids - feed_ids
        if fehlend:
            abweichungen.append(
                f"Tourpunkt {punkt}: im EDR-Snapshot, aber NICHT im Feed: {sorted(fehlend)}"
            )
    return abweichungen


def _lade_alert_liste_aus_json(eintraege: list[dict]) -> dict:
    """Laedt eine Liste von ``{"lat", "lon", "alerts": [...]}``-Eintraegen
    (Schema von ``edr_snapshot_it.json``, s. README im Fixture-Verzeichnis)
    in eine Punkt -> ``OfficialAlert``-Liste-Abbildung fuer
    ``_pruefe_obermenge``."""
    ergebnis: dict = {}
    for eintrag in eintraege:
        punkt = (eintrag["lat"], eintrag["lon"])
        ergebnis[punkt] = [
            OfficialAlert(
                source="meteoalarm",
                hazard=a["hazard"],
                level=a["level"],
                label=a.get("label", ""),
                valid_from=datetime.fromisoformat(a["valid_from"]) if a.get("valid_from") else None,
                valid_to=datetime.fromisoformat(a["valid_to"]) if a.get("valid_to") else None,
            )
            for a in eintrag.get("alerts", [])
        ]
    return ergebnis


# ---------------------------------------------------------------------------
# Adversary-Fund F004 (Fix-Loop 2, Issue #1445 S1): die AC-3-Vergleichs-
# kennung ``_alert_identitaet`` maskierte eine fehlende Warnung (fehlende
# Zeitfelder kollidieren auf ``(hazard, level, None, None)``) UND meldete
# einen falschen Alarm bei zwei Notationen desselben Zeitpunkts (Vergleich
# ueber ``.isoformat()``-Strings statt der ``datetime``-Objekte selbst).
# ---------------------------------------------------------------------------

def test_alert_identitaet_ohne_zeitfelder_maskiert_keine_fehlende_warnung():
    """F004 Teil 1 (Maskierung, die gefaehrliche Richtung): GIVEN eine im
    EDR-Snapshot vorhandene Warnung UND eine davon unabhaengige, im Feed
    vorhandene Warnung teilen sich hazard+level, tragen aber KEINE Zeitfelder
    (laut base.py:67 ein realer, erwarteter Fall) UND unterscheiden sich im
    ``region_label``, WHEN beide ueber ``_alert_identitaet``/``_pruefe_obermenge``
    verglichen werden, THEN erscheint die EDR-Warnung als Abweichung (fehlt im
    Feed) -- sie darf NICHT durch die unabhaengige Feed-Warnung maskiert
    werden. Vor dem Fix kollidierten beide auf ``(hazard, level, None, None)``
    und die fehlende Warnung wurde geraeuschlos verschluckt."""
    edr_alert = OfficialAlert(
        source="meteoalarm", hazard="flood", level=2, label="Hochwasser",
        region_label="Comune Alpha",
    )
    feed_alert_andere_warnung = OfficialAlert(
        source="meteoalarm", hazard="flood", level=2, label="Hochwasser",
        region_label="Comune Beta",
    )
    punkt = (1.0, 2.0)
    edr_je_punkt = {punkt: [edr_alert]}
    feed_je_punkt = {punkt: [feed_alert_andere_warnung]}

    abweichungen = _pruefe_obermenge([punkt], feed_je_punkt, edr_je_punkt)

    assert abweichungen, (
        "eine im EDR vorhandene Warnung ohne Zeitfelder darf NICHT durch eine "
        "unabhaengige Feed-Warnung mit gleichem hazard/level, aber anderem "
        "region_label, maskiert werden -- sie muss als Abweichung erscheinen"
    )


def test_alert_identitaet_gleicher_zeitpunkt_verschiedene_notation_gilt_als_gleich():
    """F004 Teil 2 (falscher Alarm, die harmlose Richtung): GIVEN dieselbe
    Warnung liegt im EDR- und im Feed-Snapshot mit demselben Gueltigkeits-
    Zeitpunkt, aber in zwei verschiedenen ISO-Notationen (Z vs. +02:00-Offset),
    WHEN ``_alert_identitaet`` beide vergleicht, THEN gelten sie als GLEICH --
    ein reiner Notationsunterschied darf keine Abweichung erzeugen. Vor dem
    Fix verglich ``_alert_identitaet`` ``.isoformat()``-Strings, die fuer
    denselben Zeitpunkt in verschiedener Notation unterschiedlich sind."""
    zeit_utc = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    zeit_offset = datetime(2026, 8, 1, 11, 0, tzinfo=timezone(timedelta(hours=2)))
    assert zeit_utc == zeit_offset, "Testaufbau: beide Notationen muessen denselben Zeitpunkt meinen"
    assert zeit_utc.isoformat() != zeit_offset.isoformat(), (
        "Testaufbau: die Stringformen muessen sich unterscheiden -- sonst beweist "
        "der Test nichts"
    )

    edr_alert = OfficialAlert(
        source="meteoalarm", hazard="storm", level=2, label="Sturm",
        valid_from=zeit_utc, valid_to=zeit_utc,
    )
    feed_alert = OfficialAlert(
        source="meteoalarm", hazard="storm", level=2, label="Sturm",
        valid_from=zeit_offset, valid_to=zeit_offset,
    )

    assert _alert_identitaet(edr_alert) == _alert_identitaet(feed_alert), (
        "derselbe Zeitpunkt in zwei ISO-Notationen muss als gleich gelten -- "
        "der Vergleich muss ueber die datetime-Objekte laufen, nicht ueber "
        "ihre .isoformat()-Stringform"
    )


def test_pruefe_obermenge_erkennt_fehlende_edr_warnung_im_feed(tmp_path):
    """Gegenprobe fuer die AC-3-Vergleichslogik (F002-Fix): eine kleine,
    KUENSTLICH konstruierte Vergleichsdatei in ``tmp_path`` (NICHT die echte
    Fixture, die weiterhin fehlt) beweist beide Richtungen der
    Obermengen-Pruefung -- Obermenge erfuellt => gruen, eine im EDR
    vorhandene Warnung fehlt im Feed => rot. Ohne diese Gegenprobe waere die
    Vergleichslogik selbst wieder nur eine unbewiesene Behauptung."""
    edr_datei = tmp_path / "edr_konstruiert.json"
    edr_datei.write_text(json.dumps([
        {
            "lat": 41.9028, "lon": 12.4964,
            "alerts": [{
                "hazard": "extreme_heat", "level": 3,
                "valid_from": "2026-08-01T00:00:00+00:00",
                "valid_to": "2026-08-02T00:00:00+00:00",
            }],
        },
    ]), encoding="utf-8")
    edr_je_punkt = _lade_alert_liste_aus_json(json.loads(edr_datei.read_text(encoding="utf-8")))
    punkt = (41.9028, 12.4964)

    # Richtung 1: Obermenge erfuellt -- Feed enthaelt dieselbe Warnung UND
    # eine zusaetzliche (zusaetzliche Feed-Warnungen sind fuer AC-3 unschaedlich).
    feed_je_punkt_obermenge = {
        punkt: [
            OfficialAlert(
                source="meteoalarm", hazard="extreme_heat", level=3, label="Hitze",
                valid_from=datetime(2026, 8, 1, tzinfo=timezone.utc),
                valid_to=datetime(2026, 8, 2, tzinfo=timezone.utc),
            ),
            OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=2, label="Gewitter"),
        ],
    }
    assert _pruefe_obermenge([punkt], feed_je_punkt_obermenge, edr_je_punkt) == [], (
        "eine Feed-Menge, die die EDR-Warnung UND eine weitere enthaelt, muss "
        "als Obermenge durchgehen (keine Abweichung)"
    )

    # Richtung 2: Obermenge verletzt -- die EDR-Warnung fehlt im Feed.
    feed_je_punkt_luecke = {punkt: []}
    abweichungen = _pruefe_obermenge([punkt], feed_je_punkt_luecke, edr_je_punkt)
    assert abweichungen, (
        "eine im EDR-Snapshot vorhandene, im Feed fehlende Warnung MUSS als "
        "Abweichung erkannt werden -- sonst ist die Obermengen-Pruefung wirkungslos"
    )
    assert "extreme_heat" in abweichungen[0]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "PO-Entscheidung 2026-08-01: Auslieferung erfolgt VOR diesem "
        "Nachweis. Grundlage: das EDR-Anbieter-Tageskontingent ist bis "
        "2026-08-01T15:45 UTC gesperrt, der Aequivalenz-Vergleich gegen "
        "edr_snapshot_it.json kann bis dahin nicht gefuehrt werden. Als "
        "Ersatznachweis liegt ein am 2026-08-01 gefuehrter Kreuzvergleich "
        "gegen die Ursprungsquelle (Meteoalarm-Ursprungsdaten, acht reale "
        "Orte, darunter Sillian und Lienz am Karnischen Hoehenweg) vor: "
        "keine einzige fehlende Warnung, dazu 117 gruene Tests und zwei "
        "bestandene Gegenproben (test_pruefe_obermenge_...). strict=True "
        "ist Absicht: sobald edr_snapshot_it.json aufgezeichnet ist und "
        "der Test besteht, MUSS diese Markierung entfernt werden -- ein "
        "stiller Uebergang in 'gruen, aber nie geprueft' waere sonst "
        "moeglich (Adversary-Fund F002 der Schwesterscheibe)."
    ),
)
def test_ac3_feed_menge_ist_obermenge_der_edr_menge_fuer_reale_tourpunkte(monkeypatch):
    """AC-3 (Pflicht-Gate vor Freigabe, Spec Implementation Details Punkt 3 /
    Randbedingung 1): GIVEN ein zur selben Minute aufgezeichneter EDR-Ausschnitt
    und der Feed-Ausschnitt fuer dieselbe Liste realer Tourpunkte, WHEN beide
    Ergebnismengen ueber ``_pruefe_obermenge`` gegenuebergestellt werden, THEN
    ist die Feed-Menge fuer JEDEN Tourpunkt eine Obermenge der EDR-Menge
    (Vergleichs-Kennung: ``_alert_identitaet`` -- Gefahrenart + Stufe +
    Gueltigkeitszeitraum, s. Docstring dort).

    NOCH OFFEN: ``tests/fixtures/meteoalarm_feed/edr_snapshot_it.json`` ist
    noch nicht aufgezeichnet (EDR-Tageskontingent gesperrt, Reset
    2026-08-01T15:45 UTC). Der Fehlschlag hier belegt NUR das Fehlen des
    Sicherheitsnachweises -- die Vergleichslogik selbst ist bereits
    vollstaendig ausprogrammiert und per ``test_pruefe_obermenge_...``
    (kuenstliche tmp_path-Datei) bewiesen, s. Kommentarblock oben."""
    edr_path = _FIXTURES / "edr_snapshot_it.json"
    assert edr_path.exists(), (
        f"Aequivalenz-Pflicht-Gate (AC-3) kann noch nicht gefuehrt werden: "
        f"{edr_path} fehlt. Die EDR-Vergleichsaufzeichnung steht aus (Anbieter-"
        f"Tageskontingent gesperrt bis 2026-08-01T15:45 UTC). Dieser Test MUSS "
        f"solange rot bleiben -- ein pytest.skip wuerde den fehlenden "
        f"Sicherheitsnachweis als Erfolg tarnen."
    )

    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    edr_je_punkt = _lade_alert_liste_aus_json(json.loads(edr_path.read_text(encoding="utf-8")))
    tourpunkte = list(edr_je_punkt.keys())

    server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        feed_je_punkt = {}
        for punkt in tourpunkte:
            alerts, _unavailable = get_official_alerts_with_status(*punkt, now=TEST_NOW)
            feed_je_punkt[punkt] = alerts

        abweichungen = _pruefe_obermenge(tourpunkte, feed_je_punkt, edr_je_punkt)
        assert not abweichungen, "\n".join(abweichungen)
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-4: fehlgeschlagener Feed-Abruf -> unavailable=True.
# ---------------------------------------------------------------------------

def test_ac4_fehlgeschlagener_feed_abruf_meldet_nicht_abrufbar(monkeypatch):
    """AC-4: GIVEN der Feed ist beim Abruf nicht erreichbar (HTTP 503), WHEN
    die amtlichen Warnungen fuer einen abgedeckten italienischen Ort ermittelt
    werden, THEN liefert der Aufruf unavailable=True statt einer leeren, als
    'keine Warnung' interpretierbaren Liste."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer({"warnings": []}, fail_status=503)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is True, (
            f"ein fehlgeschlagener Feed-Abruf muss 'nicht abrufbar' melden statt "
            f"faelschlich 'keine Warnung'. Erhalten: alerts={alerts}, "
            f"unavailable={unavailable}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Adversary-Fund F001 (Fix-Loop nach BROKEN-Verdict, Issue #1445 S1): ein
# syntaktisch gueltiges, aber strukturell leeres/falsch typisiertes JSON
# (fehlender "warnings"-Schluessel, null, Objekt oder String statt Liste)
# bestand die reine ``isinstance(data, dict)``-Pruefung und wurde MIT der
# Erfolgs-TTL gecacht -- der Nutzer sah "keine Warnung" statt "nicht
# abrufbar". Ein tatsaechlich LEERES ``{"warnings": []}`` bleibt Erfolg
# (gueltige fachliche Aussage "derzeit keine Warnungen").
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {},
    {"warnings": None},
    {"warnings": {}},
    {"warnings": "text"},
], ids=["fehlender_schluessel", "warnings_null", "warnings_objekt", "warnings_string"])
def test_parse_feed_lehnt_fehlende_oder_falsch_typisierte_warnings_ab(body):
    """F001-Fix: ``_parse_feed()`` muss jede Antwort ablehnen, deren
    ``"warnings"``-Schluessel fehlt oder keine Liste ist -- sonst cached
    ``warn_egress.cached_fetch()`` sie faelschlich mit der Erfolgs-TTL."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    resp = httpx.Response(200, json=body, request=httpx.Request("GET", "http://example.test"))
    with pytest.raises(ValueError):
        meteoalarm_feed._parse_feed(resp)


def test_parse_feed_akzeptiert_leere_warnings_liste_als_erfolg():
    """Gegenprobe zu F001: ``{"warnings": []}`` ist eine gueltige fachliche
    Aussage ("derzeit keine Warnungen in Italien") und MUSS weiterhin als
    Erfolg durchgehen -- der Unterschied zwischen 'nichts los' und 'kaputt'
    ist genau der Punkt des Fixes."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    resp = httpx.Response(200, json={"warnings": []}, request=httpx.Request("GET", "http://example.test"))
    assert meteoalarm_feed._parse_feed(resp) == {"warnings": []}


def test_f001_leeres_gueltiges_json_ohne_warnings_meldet_nicht_abrufbar(monkeypatch):
    """F001 (Adversary-Fund, KRITISCH, End-zu-End-Reproduktion): HTTP 200 mit
    Body ``{}`` (syntaktisch gueltiges JSON, aber ohne "warnings"-Schluessel)
    darf NICHT als Erfolg mit leerer Liste durchgehen. Vor dem Fix:
    ``_parse_feed()`` pruefte nur ``isinstance(data, dict)`` und liess ``{}``
    durch, ``cached_fetch()`` cachte das mit der Erfolgs-TTL (30 min),
    ``unavailable`` blieb ``False`` -- der Nutzer haette eine ruhige Mail
    gesehen, obwohl die Quelle strukturell kaputt war."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer({})
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is True, (
            f"leeres, aber syntaktisch gueltiges JSON ohne 'warnings'-Schluessel "
            f"muss als Fehlschlag gelten (nicht als 'keine Warnung'). Erhalten: "
            f"alerts={alerts}, unavailable={unavailable}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Adversary-Fund F003 (Fix-Loop 2, Issue #1445 S1): ein einzelner strukturell
# kaputter ``warnings[]``-Eintrag (kein oder leerer ``"alert"``) wurde bisher
# via ``warning.get("alert") or {}`` STILL uebersprungen -- eine leere
# EMMA-Menge traf nie die gesuchte Zone, kein Fehlschlag wurde vermerkt. Eine
# ANDERE, wohlgeformte Warnung im selben Feed (andere Zone) verdeckte den
# Defekt zusaetzlich: der Aufruf sah komplett unauffaellig aus
# (alerts=[], unavailable=False).
# ---------------------------------------------------------------------------

def _wohlgeformter_alert_fuer_aosta() -> dict:
    """Ein vollstaendiges, gueltiges CAP-``alert``-Objekt fuer die Zone
    IT004 (Aosta) -- dient als "die andere, intakte Warnung im selben Feed",
    die den kaputten Eintrag bisher verdeckte."""
    return {
        "identifier": "test-f003-aosta-001",
        "info": [{
            "language": "en-US",
            "event": "Thunderstorm",
            "headline": "Thunderstorm warning",
            "onset": "2026-08-01T00:00:00Z",
            "expires": "2026-08-02T00:00:00Z",
            "parameter": [
                {"valueName": "awareness_level", "value": "2; yellow; Moderate"},
                {"valueName": "awareness_type", "value": "3; thunderstorm"},
            ],
            "area": [{
                "areaDesc": "VDAo-A",
                "geocode": [{"valueName": "EMMA_ID", "value": "IT004"}],
            }],
        }],
    }


def test_f003_kaputter_warnungseintrag_neben_intakter_warnung_meldet_nicht_abrufbar(monkeypatch):
    """F003 (Adversary-Fund, HOCH): GIVEN ein Feed enthaelt EINE wohlgeformte
    Warnung fuer eine ANDERE Zone (Aosta, IT004) PLUS einen strukturell
    kaputten Eintrag (``{}`` -- weder ``"alert"`` noch sonstiger Inhalt), WHEN
    die amtlichen Warnungen fuer Rom (IT012) ermittelt werden, THEN meldet der
    Aufruf ``unavailable=True`` -- der kaputte Eintrag haette ausgerechnet die
    Warnung fuer Rom sein koennen und darf nicht geraeuschlos verschwinden.
    Vor dem Fix: ``warning.get(\"alert\") or {}`` ergab eine leere EMMA-Menge,
    der Eintrag wurde still uebersprungen, ``unavailable`` blieb ``False``."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    feed = {"warnings": [{"alert": _wohlgeformter_alert_fuer_aosta()}, {}]}
    server = _JsonServer(feed)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is True, (
            f"ein einzelner kaputter warnings[]-Eintrag (leeres/fehlendes "
            f"'alert') muss als Fehlschlag zaehlen, auch wenn eine andere, "
            f"wohlgeformte Warnung im selben Feed steht. Erhalten: "
            f"alerts={alerts}, unavailable={unavailable}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def test_f003_gueltiger_feed_mit_vielen_eintraegen_bleibt_verfuegbar(monkeypatch):
    """Gegenprobe zu F003: ein vollstaendig gueltiger Feed mit mehreren
    Eintraegen (aus der aufgezeichneten Fixture) darf durch den F003-Fix
    NICHT faelschlich als unvollstaendig gelten."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        _alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is False, (
            f"ein vollstaendig gueltiger Feed mit vielen Eintraegen darf nicht "
            f"faelschlich als unvollstaendig gelten. Erhalten: unavailable={unavailable}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Adversary-Fund F005 (Fix-Loop 3, Issue #1445 S1): der F003-Fix pruefte die
# Malformation VOR der Zonenzugehoerigkeit -- ein einziger CAP-Ruecknahme-
# Eintrag (msgType "Cancel", konventionsgemaess OHNE info[]) irgendwo im
# Feed markierte damit JEDE Ortsabfrage im ganzen Land als "nicht abrufbar",
# auch wenn der abgefragte Ort seine vollstaendige, korrekte Warnung bekam.
# Der Feed traegt taeglich rund 450 Eintraege, Ruecknahmen kommen real vor --
# das haette dauerhaft grundlos angeschlagen.
# ---------------------------------------------------------------------------

def _cancel_ohne_info_fuer_andere_zone() -> dict:
    """Ein CAP-Ruecknahme-Eintrag (msgType 'Cancel') fuer eine ANDERE Zone
    (Aosta, IT004) -- traegt konventionsgemaess KEIN info[]. Regelkonforme
    Form, kein Datenfehler (F005)."""
    return {
        "identifier": "test-f005-cancel-aosta-001",
        "msgType": "Cancel",
        "references": "Italian Air Force National Meteorological Service,test-f005-original-001,2026-07-31T00:00:00+02:00",
    }


def test_f005_cancel_eintrag_ohne_info_fuer_andere_zone_faerbt_rom_nicht_ein(monkeypatch):
    """F005 (Adversary-Fund, HOCH): GIVEN ein Feed enthaelt EINEN CAP-
    Ruecknahme-Eintrag (msgType 'Cancel', ohne info[]) fuer eine ANDERE Zone
    (Aosta) PLUS eine vollstaendige, wohlgeformte Warnung fuer Rom (Lazio),
    WHEN die amtlichen Warnungen fuer Rom ermittelt werden, THEN erscheint
    die Warnung fuer Rom UND unavailable bleibt False -- ein regelkonformer
    Ruecknahme-Eintrag fuer eine fremde Zone darf die Ortsabfrage nicht
    einfaerben. Vor dem Fix: die Malformations-Pruefung lief vor der
    Zonenzugehoerigkeit, der fehlende info[]-Schluessel des Cancel-Eintrags
    markierte JEDE Ortsabfrage im ganzen Land als 'nicht abrufbar'."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    feed = _load_sample_feed()
    feed = {"warnings": [{"alert": _cancel_ohne_info_fuer_andere_zone()}, *feed["warnings"]]}
    server = _JsonServer(feed)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is False, (
            f"ein regelkonformer Cancel-Eintrag ohne info[] fuer eine ANDERE "
            f"Zone darf die Ortsabfrage nicht als 'nicht abrufbar' einfaerben. "
            f"Erhalten: alerts={alerts}, unavailable={unavailable}"
        )
        assert any(a.hazard == "extreme_heat" and a.level == 3 for a in alerts), (
            f"Rom muss trotz des Cancel-Eintrags fuer eine andere Zone seine "
            f"eigene, vollstaendige Warnung bekommen. Erhalten: {alerts}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def test_f005_kaputter_eintrag_ohne_jede_zonenangabe_bleibt_f003_geschuetzt(monkeypatch):
    """Gegenprobe zu F005 -- der F003-Schutz bleibt: GIVEN ein Feed enthaelt
    einen strukturell kaputten Eintrag OHNE jede auswertbare Zonenangabe
    (weder info[] noch msgType 'Cancel') PLUS eine wohlgeformte Warnung fuer
    eine ANDERE Zone, WHEN Rom abgefragt wird, THEN bleibt unavailable=True --
    der kaputte Eintrag haette ausgerechnet die Warnung fuer Rom sein koennen
    und ist auch nach dem F005-Fix kein legitimer Ruecknahme-Eintrag."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    feed = {"warnings": [{"alert": _wohlgeformter_alert_fuer_aosta()}, {}]}
    server = _JsonServer(feed)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        _alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is True, (
            f"ein kaputter Eintrag ohne jede auswertbare Zonenangabe und ohne "
            f"CAP-Cancel-Kennzeichnung muss weiterhin als Fehlschlag zaehlen "
            f"(F003-Schutz nach dem F005-Fix). Erhalten: unavailable={unavailable}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-5: Punkt ohne auflösbare Zone -> unavailable=True + zaehlbarer Drift.
# ---------------------------------------------------------------------------

def test_ac5_punkt_ohne_zone_meldet_nicht_abrufbar_und_zaehlbaren_drift(monkeypatch):
    """AC-5: GIVEN ein Punkt liegt innerhalb der DPC-Bbox, aber ausserhalb aller
    187 bekannten Zonenpolygone (Meer zwischen Sizilien und dem Festland), WHEN
    die amtlichen Warnungen fuer diesen Punkt ermittelt werden, THEN liefert
    der Aufruf unavailable=True UND im Diagnose-Journal erscheint eine
    zaehlbare log_zone_drift-Zeile mit drift='point_unmapped' (Spec
    Implementation Details Punkt 4: exakt
    ``log_zone_drift("meteoalarm_feed", None, True, "point_unmapped")``)."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed, warn_egress

    _assert_pruefling_aus_diesem_baum()
    server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*MEER_UNMAPPED, now=TEST_NOW)

        assert unavailable is True, (
            f"ein Punkt ohne aufloesbare Zone MUSS 'nicht abrufbar' melden, nie "
            f"'keine Warnung'. Erhalten: alerts={alerts}, unavailable={unavailable}"
        )
        journal = warn_egress.WARN_CALLS_PATH.read_text(encoding="utf-8") \
            if warn_egress.WARN_CALLS_PATH.exists() else ""
        drift_zeilen = [json.loads(z) for z in journal.splitlines() if '"drift"' in z]
        treffer = [
            z for z in drift_zeilen
            if z.get("service") == "meteoalarm_feed" and z.get("drift") == "point_unmapped"
        ]
        assert treffer, (
            f"es muss eine zaehlbare log_zone_drift-Zeile mit "
            f"service='meteoalarm_feed', drift='point_unmapped' stehen. "
            f"Journal-Drift-Zeilen: {drift_zeilen}"
        )
    finally:
        server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-6: ueberholte/zurueckgezogene Fassung erscheint nach der naechsten
# Momentaufnahme nicht mehr zusaetzlich (kein kumulierender Bestand).
# ---------------------------------------------------------------------------

def test_ac6_nicht_mehr_im_feed_enthaltene_warnung_verschwindet_sofort(monkeypatch):
    """AC-6: GIVEN eine zuvor im Feed enthaltene Warnung fuer Lazio ist in der
    naechsten Momentaufnahme nicht mehr enthalten (abgelaufen/zurueckgezogen),
    WHEN das Ergebnis fuer Rom nach der Auffrischung neu gebildet wird, THEN
    erscheint nur, was AKTUELL im Feed steht -- die Quelle fuehrt anders als
    meteoalarm.py KEINEN eigenen kumulierenden Bestand (Spec Implementation
    Details Punkt 6)."""
    from services.official_alerts import meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    voller_feed = _load_sample_feed()
    ohne_lazio_hitze = {
        "warnings": [
            w for w in voller_feed["warnings"]
            if w["alert"]["identifier"] != _LAZIO_HITZE_ID
        ],
    }
    assert len(ohne_lazio_hitze["warnings"]) == len(voller_feed["warnings"]) - 1, (
        "Testaufbau: genau EIN Eintrag (die Lazio-Hitzewarnung) muss entfernt sein"
    )

    server = _JsonServer(voller_feed)
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        quelle = meteoalarm_feed.MeteoAlarmFeedSource("IT")

        erster = quelle.fetch(*ROM)
        assert any(a.hazard == "extreme_heat" for a in erster), (
            f"Aufbaupruefung: im ersten Zyklus muss die Hitzewarnung stehen. "
            f"Erhalten: {erster}"
        )

        meteoalarm_feed._cache.clear()  # naechstes Auffrischungsfenster
        server.body = ohne_lazio_hitze
        zweiter = quelle.fetch(*ROM)

        assert not any(a.hazard == "extreme_heat" for a in zweiter), (
            f"eine in der aktuellen Momentaufnahme nicht mehr enthaltene Warnung "
            f"darf NICHT zusaetzlich erscheinen -- kein eigener kumulierender "
            f"Bestand. Erhalten im zweiten Zyklus: {zweiter}"
        )
        assert server.zaehler.treffer == 2, (
            f"Aufbaupruefung: nach dem Cache-Clear muss ein zweiter echter Abruf "
            f"stattgefunden haben, gemessen: {server.zaehler.treffer}"
        )
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# AC-7: ein AT-Indexfehlschlag darf das IT-Ergebnis nicht einfaerben
# (Randbedingung 3 -- setzt voraus, dass MeteoAlarmSource.covers() italienische
# Punkte nach dieser Scheibe nicht mehr zaehlt, Spec Implementation Details
# Punkt 7).
# ---------------------------------------------------------------------------

def test_ac7_at_indexfehlschlag_faerbt_it_ergebnis_nicht_ein(monkeypatch):
    """AC-7: GIVEN der bisherige kontingentierte Weg fuer Oesterreich faellt aus
    (HTTP 503 auf jede AT-Indexseite), WHEN die amtlichen Warnungen fuer einen
    italienischen Ort (Rom) ermittelt werden, THEN bleibt unavailable=False --
    ein AT-Fehlschlag darf IT nicht mehr einfaerben."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    at_server = _JsonServer({}, fail_status=503)
    it_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    meteoalarm._index_cache.clear()
    meteoalarm._geometry_cache.clear()
    meteoalarm._cap_cache.clear()
    try:
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-1445-ac7")
        monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "100000")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{at_server.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{it_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))

        alerts, unavailable = get_official_alerts_with_status(*ROM, now=TEST_NOW)

        assert unavailable is False, (
            f"ein AT-Indexfehlschlag darf das Ergebnis fuer einen italienischen "
            f"Ort nicht als 'nicht abrufbar' einfaerben -- MeteoAlarmSource."
            f"covers() muss italienische Punkte nach dieser Scheibe ausschliessen "
            f"UND die Laenderliste in fetch() auf ('AT',) verengt sein. Erhalten: "
            f"unavailable={unavailable}, alerts={alerts}"
        )
    finally:
        at_server.shutdown()
        it_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        meteoalarm._index_cache.clear()
        meteoalarm._geometry_cache.clear()
        meteoalarm._cap_cache.clear()
