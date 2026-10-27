"""Entwarnung amtlicher Warnungen -- Gesundheit der MELDENDEN Quelle an jeder
Wirkstelle (Issue #1441 Scheibe S2, Adversary Runde 2: F009, F010, F011).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- AC-6 (Teilausfall der
      meldenden Quelle ist keine Entwarnung), Abschnitt 2 (Pro-Quelle-Ergebnis:
      ok nur, wenn ALLE zustaendigen Instanzen ok sind; Registry-Name als
      `source` im Gedaechtnis), AC-1/AC-2.

Abgedeckt sind die Faelle, die die Ein-Instanz-/Ein-Ort-Tests nie ausueben:
* ein Eintrag ueber ZWEI Orte, die meldende Quelle faellt nur an einem aus;
* zwei GLEICHNAMIGE Quell-Instanzen (MeteoAlarm IT/AT/DE heissen alle
  `meteoalarm_feed`), eine faellt aus;
* die meldende Quelle fehlt im Pro-Quelle-Ergebnis ganz (`covers()` False
  oder wirft);
* Registry-Name ungleich `OfficialAlert.source` wie in Produktion
  (`meteoalarm_feed` / `meteoalarm`, `avalanche_report` / `avalanche_report:AT-07`).

Jeder Test traegt eine Gegenprobe (gesunde, leere bzw. gesenkte Lage ergibt
die Entwarnung) -- sonst waere "still" auch bei kaputtem Aufbau gruen.
Versandpfade laufen durch die ECHTEN Einstiege; ersetzt sind nur Wetter-Naht,
Quellen (echte Klassen in der echten Registry) und Transport-Klassen.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    AUSFALLARTEN, FLAECHEN, LAT, LAT_B, LON, LON_B, Szenario, Warnquelle, _segment,
    basis_jetzt, entwarnungen_gesamt, entwarnungs_sendungen, lauf_erstwarnung, quellen,
)


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


class SchaltbareQuelle(Warnquelle):
    """Echte Quelle (Protocol-Subtyping) mit zwei Zusatz-Schaltern:
    ``ausfall_bei``: faellt NUR an diesem Punkt aus (``ausfall``), antwortet an
    allen anderen gesund; ``zustaendig``: ``True`` | ``False`` | ``"wirft"``
    (Ergebnis von ``covers()``)."""

    def __init__(self, name: str, **kw) -> None:
        super().__init__(name, **kw)
        self.ausfall_bei = None
        self.zustaendig = True

    def covers(self, lat: float, lon: float) -> bool:
        if self.zustaendig == "wirft":
            raise RuntimeError(f"{self.name}: covers() kaputt (Test)")
        return bool(self.zustaendig)

    def fetch(self, lat: float, lon: float) -> list:
        if self.ausfall_bei is not None and (round(lat, 3), round(lon, 3)) != self.ausfall_bei:
            ausfall, self.ausfall = self.ausfall, None
            try:
                return super().fetch(lat, lon)
            finally:
                self.ausfall = ausfall
        return super().fetch(lat, lon)


def _schaltbar(sz: Szenario) -> SchaltbareQuelle:
    """Ersetzt die meldende Quelle des Szenarios durch eine schaltbare
    gleichen Namens (vor dem Registrieren)."""
    sz.x = SchaltbareQuelle(sz.x.name, nur_bei=sz.x.nur_bei)
    sz.x.alerts = [sz.warnung(4)]
    return sz.x


def _ausfall_ergab_nichts_und_gegenprobe_endet(sz: Szenario, eins, zwei, vorher, nachher,
                                                drei, vier, fall: str) -> None:
    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"[{fall}] Schein-Entwarnung trotz nicht gesunder meldender Quelle: {eins!r} {zwei!r}")
    assert nachher == vorher, f"[{fall}] Gedaechtnis veraendert: {vorher!r} -> {nachher!r}"
    assert entwarnungen_gesamt(drei) == 0, f"[{fall}] Gegenprobe Lauf 1 muss still sein: {drei!r}"
    assert entwarnungs_sendungen(vier, "email"), (
        f"[{fall}] Gegenprobe: gesunde, leere meldende Quelle muss nach zwei Laeufen "
        f"\"beendet\" ergeben (sonst misst der Test nichts): {vier!r}")


# ═══════════════ F009: Eintrag ueber zwei Orte, Ausfall an einem ═════════════


@pytest.mark.parametrize("ausfall", AUSFALLARTEN)
def test_ausfall_der_meldenden_quelle_an_einem_von_zwei_orten_ist_keine_entwarnung(
        monkeypatch, mit, ausfall):
    """AC-6 [Teilausfall] ueber zwei Orte (Trip mit zwei Segmenten A und B).
    GIVEN die Warnung Stufe 4 wurde an A UND B gemeldet (ein Eintrag, Scope
          beide Orte); jetzt faellt die meldende Quelle NUR an A aus und
          antwortet an B gesund und leer
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung, das Gedaechtnis bleibt unveraendert (an A ist die
          Lage unbekannt). Gegenprobe: an beiden Orten gesund leer -> nach zwei
          Laeufen "beendet".
    """
    t0 = basis_jetzt()
    geometrie = [_segment(1, LAT, LON, t0 - timedelta(hours=2), t0 + timedelta(hours=5)),
                 _segment(2, LAT_B, LON_B, t0 + timedelta(hours=5), t0 + timedelta(hours=10))]
    sz = Szenario("trip", monkeypatch, mit, t0, geometrie=geometrie)
    x = _schaltbar(sz)
    with quellen(x):
        lauf_erstwarnung(sz)
        vorher = sz.eintraege()
        x.alerts, x.ausfall, x.ausfall_bei = [], ausfall, (round(LAT, 3), round(LON, 3))
        eins, zwei = sz.lauf(15), sz.lauf(30)
        nachher = sz.eintraege()
        x.ausfall, x.ausfall_bei = None, None
        drei, vier = sz.lauf(45), sz.lauf(60)

    (eintrag,) = vorher.values()
    assert len(eintrag.get("scope") or []) == 2, f"Vorbedingung: Eintrag ueber zwei Orte: {eintrag!r}"
    _ausfall_ergab_nichts_und_gegenprobe_endet(
        sz, eins, zwei, vorher, nachher, drei, vier, f"zwei Orte, {ausfall} an A")


# ═══════════════ F010a: gleichnamige Instanzen, eine faellt aus ═════════════


@pytest.mark.parametrize("reihenfolge", ["ausgefallene_zuerst", "gesunde_zuerst"])
def test_gleichnamige_instanzen_eine_ausgefallen_ergibt_quelle_nicht_ok(reihenfolge):
    """Spec Abschnitt 2 (Pro-Quelle-Ergebnis) am echten Abruf
    `get_official_alerts_with_sources`: zwei Instanzen `meteoalarm_feed`, eine
    faellt aus, die andere antwortet gesund leer -> `ok` ist False, in BEIDEN
    Registrier-Reihenfolgen. Gegenprobe: beide gesund -> `ok` True."""
    from services.official_alerts import get_official_alerts_with_sources

    kaputt, gesund = Warnquelle("meteoalarm_feed"), Warnquelle("meteoalarm_feed")
    kaputt.ausfall = "fetch_failed"
    reihe = (kaputt, gesund) if reihenfolge == "ausgefallene_zuerst" else (gesund, kaputt)
    with quellen(*reihe):
        teil = get_official_alerts_with_sources(LAT, LON)
        kaputt.ausfall = None
        heil = get_official_alerts_with_sources(LAT, LON)

    assert kaputt.fetch_calls == 2 and gesund.fetch_calls == 2, "Vorbedingung: beide Instanzen abgefragt"
    assert teil["meteoalarm_feed"][0] is False, f"[{reihenfolge}] Teilausfall als gesund vereint: {teil!r}"
    assert heil["meteoalarm_feed"][0] is True, f"[{reihenfolge}] Gegenprobe: beide gesund: {heil!r}"


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_gleichnamige_instanz_der_meldenden_quelle_ausgefallen_ist_keine_entwarnung(
        monkeypatch, mit, flaeche):
    """AC-6 [Teilausfall] bei gleichnamigen Instanzen, Wirkung am Versand.
    GIVEN zwei Instanzen `meteoalarm_feed` (die ausgefallene ist ZUERST
          registriert); die meldende Instanz faellt aus, die andere antwortet
          gesund und leer
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung, Gedaechtnis unveraendert. Gegenprobe: beide gesund
          leer -> nach zwei Laeufen "beendet".
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt(), quelle="meteoalarm_feed")
    andere = Warnquelle("meteoalarm_feed", nur_bei=sz.x.nur_bei)
    with quellen(sz.x, andere):
        lauf_erstwarnung(sz)
        vorher = sz.eintraege()
        sz.x.alerts, sz.x.ausfall = [], "fetch_failed"
        eins, zwei = sz.lauf(15), sz.lauf(30)
        nachher = sz.eintraege()
        sz.x.ausfall = None
        drei, vier = sz.lauf(45), sz.lauf(60)

    assert andere.fetch_calls > 0, "Vorbedingung: zweite Instanz abgefragt"
    _ausfall_ergab_nichts_und_gegenprobe_endet(
        sz, eins, zwei, vorher, nachher, drei, vier, f"{flaeche}, gleichnamige Instanz aus")


# ═══════════════ F010b: meldende Quelle fehlt im Ergebnis ganz ══════════════


@pytest.mark.parametrize("zustaendig", [False, "wirft"], ids=["covers_false", "covers_wirft"])
@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_meldende_quelle_fehlt_im_pro_quelle_ergebnis_ist_keine_entwarnung(
        monkeypatch, mit, flaeche, zustaendig):
    """AC-6 [Nicht-Zustaendigkeit]: die meldende Quelle X erscheint im
    Pro-Quelle-Ergebnis gar nicht (``covers()`` False bzw. wirft), eine zweite
    Quelle Y antwortet gesund und leer.
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung, Gedaechtnis unveraendert (fehlend = unbekannt, nie
          "gesund leer"). Gegenprobe: X wieder zustaendig, gesund leer ->
          nach zwei Laeufen "beendet".
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    x = _schaltbar(sz)
    y = Warnquelle("quelle-y", nur_bei=sz.x.nur_bei)
    with quellen(x, y):
        lauf_erstwarnung(sz)
        vorher = sz.eintraege()
        x.alerts, x.zustaendig = [], zustaendig
        abrufe = x.fetch_calls
        eins, zwei = sz.lauf(15), sz.lauf(30)
        nachher = sz.eintraege()
        assert x.fetch_calls == abrufe, "Vorbedingung: X wurde mangels Zustaendigkeit nicht abgefragt"
        x.zustaendig = True
        drei, vier = sz.lauf(45), sz.lauf(60)

    assert y.fetch_calls > 0, "Vorbedingung: Y antwortet"
    _ausfall_ergab_nichts_und_gegenprobe_endet(
        sz, eins, zwei, vorher, nachher, drei, vier, f"{flaeche}, X fehlt ({zustaendig})")


# ═══════════════ F011: Registry-Name ungleich alert.source ══════════════════


@pytest.mark.parametrize("register_name, alert_source", [
    ("meteoalarm_feed", "meteoalarm"),
    ("avalanche_report", "avalanche_report:AT-07"),
])
@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_registry_name_ungleich_alert_source_ergibt_entwarnung(
        monkeypatch, mit, flaeche, register_name, alert_source):
    """AC-1 bei Produktions-Namen: die Quelle heisst in der Registry anders,
    als ihre Warnungen in `OfficialAlert.source` tragen.
    GIVEN gemeldet Stufe 4 der Quelle `register_name` (Warnung traegt
          `alert_source`)
    WHEN  die Quelle die Warnung mit Stufe 2 liefert
    THEN  kommt die Entwarnung und das Gedaechtnis steht auf 2; im Eintrag
          steht der Registry-Name (nur so ist die Quelle spaeter auffindbar).
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt(), quelle=register_name)
    sz.x.alerts = [dataclasses.replace(a, source=alert_source) for a in sz.x.alerts]
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        erst = sz.eintrag()
        sz.x.alerts = [dataclasses.replace(sz.warnung(2), source=alert_source)]
        folge = sz.lauf(15)
        danach = sz.eintrag()

    assert entwarnungs_sendungen(folge, "email"), (
        f"[{flaeche}] {register_name}/{alert_source}: Absenkung 4 -> 2 ohne Entwarnung: {folge!r}")
    assert danach.get("last_reported_value") == 2.0, f"[{flaeche}] Gedaechtnis nicht gesenkt: {danach!r}"
    assert erst.get("source") == register_name, f"[{flaeche}] Registry-Name fehlt im Eintrag: {erst!r}"
