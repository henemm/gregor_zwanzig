"""Entwarnung beim SLF-Lawinen-Lagebericht (Issue #1441 Scheibe S3, AC-26 bis AC-29).

SPEC: docs/specs/modules/feat_1441_s3_slf.md -- AC-26, AC-27, AC-28, AC-29 (Abschnitt 10)
VORBILD: tests/tdd/test_official_alert_allclear*.py (S2), Szenario-Bausteine aus
         tests/tdd/_official_alert_allclear_fixtures.py

Kein Mock-Theater:
* Quelle ist die ECHTE ``SlfSource`` in der echten Registry (``only_slf``), gespeist vom
  ``SlfFixtureTransport`` mit den AUFGEZEICHNETEN Bulletins (``tests/fixtures/slf/``).
  Stufe 4 und die Absenkung 4 -> 2 sind aus ``at_2026-03-01T08:00:00Z.json`` abgeleitet
  (nur ``mainValue`` geaendert, Testnamen tragen "abgeleitet").
* Versand laeuft durch den echten Trip-Alarm (``TripAlertService.check_all_trips``) bzw.
  Ortsvergleich-Alarm (``CompareOfficialAlertService.check_all_compare_presets``); abgegriffen an
  den vier Ausgangs-Klassen (``tests/helpers/transport_mitschrift.py``).
* Das Melde-Gedaechtnis schreibt das PRODUKT (Lauf 1 meldet eine echte SLF-Warnung). Einzige
  Ausnahme: AC-28 legt den AT-Eintrag von Hand an -- eine AT-Warnung an einem Schweizer Punkt kann
  das Produkt nicht erzeugen; der Eintrag traegt aber ``source``/``scope``/Zeitraum wie ein echter.

Zeit: alle Laeufe am 2026-03-01 ab 08:00Z (Gueltigkeit des Bulletins 07:00Z-16:00Z) unter
``freeze_time``; die Quelle bekommt eine eigene Uhr und einen eigenen Cache, der vor jedem Lauf
geleert wird -- sonst saehe Lauf 2 die gecachte Antwort von Lauf 1. Jeder Lauf muss das SLF
nachweislich abgefragt haben (Abrufzaehler), sonst ist "nichts kam" wertlos.

RED heute: ``services.official_alerts.slf`` existiert nicht (lazy Import in ``only_slf``).
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from tests.helpers.slf_support import (
    SLF_LABEL, SLF_REGISTRY_NAME, WINTER_MORGEN, FakeClock, SlfFixtureTransport, bulletin_of,
    ch_regions_at, derive, http_503, interior_point, leer, netzfehler, ok_doc, only_slf, slf_doc,
)
from tests.helpers.transport_mitschrift import ALLE_KANAELE, aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    FLAECHEN, _segment, compare_lauf, compare_nutzer, entwarnungen_gesamt, entwarnungs_sendungen,
    gedaechtnis, routen_geometrie_setzen, schnappschuss, trip_lauf, trip_nutzer,
    trip_vorbedingung_alle_kanaele,
)

UTC = timezone.utc
T0 = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)   # Morgen-Bulletin gilt 07:00Z-16:00Z
RID = "CH-7231"          # Muenstertal: erheblich/minus, ausserhalb der Tirol-Bounding-Box
RID_AT_BBOX = "CH-7121"  # Unterengadin: erheblich/minus, INNERHALB der Tirol-Bounding-Box (AC-28)
CH_LOC = "loc-ch"
VIER_AUF_ZWEI = re.compile(r"4\s*(?:→|->|>)\s*2")
#: Alle Kanaele "gering": jede Stufe erreicht jeden Kanal (AC-27/28/29).
ALLE_GERING = {"email": "LOW", "telegram": "LOW", "sms": "LOW", "premium_sms": "LOW"}
#: Premium-SMS nur ab "hoch" (AC-26): die Entwarnung 4 -> 2 erreicht sie nur mit der
#: Dringlichkeit des ALTEN Werts (Stufe 4 = hoch), nicht mit der neuen Stufe 2 (gering).
PREMIUM_NUR_HOCH = {"email": "LOW", "telegram": "LOW", "sms": "LOW", "premium_sms": "HIGH"}


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


# ---------------------------------------------------------------- lokale Ableitungen
def mit_feinstufe_abgeleitet(doc: dict, region_id: str, subdivision: str) -> dict:
    """Tiefe Kopie; im Bulletin der Region traegt jedes Rating die Feinstufe ``subdivision``
    (``customData.CH.subdivision``). Sonst nichts geaendert (Stufe, Zeiten, Probleme gleich)."""
    out = copy.deepcopy(doc)
    for rating in bulletin_of(out, region_id).get("dangerRatings") or []:
        rating.setdefault("customData", {}).setdefault("CH", {})["subdivision"] = subdivision
    return out


def ohne_region_abgeleitet(doc: dict, region_id: str) -> dict:
    """Tiefe Kopie desselben Bulletins (gleiche Gueltigkeit), in der ``region_id`` nicht mehr
    bewertet ist -- alle uebrigen Regionen bleiben (die Quelle antwortet also gesund)."""
    out = copy.deepcopy(doc)
    bulletin = bulletin_of(out, region_id)
    bulletin["regions"] = [r for r in bulletin["regions"] if r.get("regionID") != region_id]
    assert bulletin["regions"], "Testaufbau: das Bulletin muss weitere Regionen behalten"
    return out


def _texte(sendung: dict) -> str:
    return " ".join(str(sendung.get(f) or "") for f in ("subject", "body", "plain_text_body"))


def _alles_gesendete(snap) -> dict:
    return {k: snap.sendungen(k) for k in ALLE_KANAELE if snap.sendungen(k)}


# ---------------------------------------------------------------- Lage: Nutzer + Punkt + Quelle
class SlfLage:
    """EIN Nutzer auf EINER Flaeche (``"trip"`` | ``"vergleich"``) mit einem Punkt in der
    Mikroregion ``region``. ``registrieren`` setzt die echte ``SlfSource`` (plus ``andere``) als
    Registry; ``lauf(minuten, antwort)`` schaltet die SLF-Antwort, leert den Quellen-Cache, fuehrt
    EINEN regulaeren Alarmlauf um ``T0 + minuten`` aus und liefert dessen Mitschrift."""

    def __init__(self, flaeche: str, monkeypatch, mit, *, region: str = RID,
                 schwellen: dict = ALLE_GERING) -> None:
        self.flaeche, self.mit, self.region = flaeche, mit, region
        self.lat, self.lon = interior_point(region)
        assert ch_regions_at(round(self.lat, 3), round(self.lon, 3)) == [region], (
            "Testaufbau: der (auf 3 Stellen gerundete) Abfragepunkt liegt nicht allein in "
            f"{region}")
        self.clock = FakeClock(T0)
        self.cache: dict = {}
        self.transport = SlfFixtureTransport(WINTER_MORGEN)
        with freeze_time(T0):  # Etappentag/Briefing-Zeiten relativ zur Laufzeit
            if flaeche == "trip":
                self.uid, self.trip = trip_nutzer(monkeypatch, schwellen=schwellen)
                routen_geometrie_setzen(monkeypatch, [_segment(
                    1, self.lat, self.lon, T0 - timedelta(hours=2), T0 + timedelta(hours=10))])
                self.entity = self.trip.id
                from services.official_alert_allclear import scope_token
                self.scope = scope_token(round(self.lat, 3), round(self.lon, 3))
            else:
                from app.loader import save_location
                from app.user import SavedLocation

                self.uid, self.preset = compare_nutzer(
                    monkeypatch, schwellen=schwellen, location_ids=[CH_LOC])
                save_location(SavedLocation(id=CH_LOC, name="Val Müstair", lat=self.lat,
                                            lon=self.lon, elevation_m=1500), user_id=self.uid)
                self.entity = f"{self.preset['id']}:{CH_LOC}"
                self.scope = CH_LOC

    def registrieren(self, monkeypatch, *andere) -> None:
        only_slf(monkeypatch, self.transport, self.clock, others=andere, cache=self.cache)

    def lauf(self, minuten: float, antwort=None):
        if antwort is not None:
            self.transport.set(antwort)
        self.cache.clear()
        self.clock.t = 1000.0 + minuten * 60  # Quellen-Uhr folgt der Laufzeit
        vorher = self.transport.count
        zeitpunkt = T0 + timedelta(minutes=minuten)
        if self.flaeche == "trip":
            trip_lauf(self.uid, zeitpunkt)
        else:
            compare_lauf(self.uid, zeitpunkt)
        assert self.transport.count > vorher, (
            f"Vorbedingung: der Lauf um +{minuten} min hat das SLF nicht abgefragt "
            f"(Abrufe {vorher} -> {self.transport.count}) -- jede Aussage waere wertlos")
        return schnappschuss(self.mit)

    def slf_eintraege(self, region: str | None = None) -> dict:
        praefix = (f"official_alert:id:avalanche_bulletin:{region or self.region}:"
                   "avalanche_bulletin:")
        return {k: v for k, v in gedaechtnis(self.uid, self.entity).items()
                if k.startswith(praefix)}

    def slf_eintrag(self) -> dict:
        eintraege = self.slf_eintraege()
        assert len(eintraege) == 1, f"genau EIN SLF-Gedaechtnis-Eintrag erwartet: {eintraege!r}"
        return next(iter(eintraege.values()))


def erstwarnung(lage: SlfLage, antwort, stufe: int):
    """Lauf 1: echte SLF-Warnung -- das PRODUKT schreibt das Gedaechtnis. Vorbedingungen: sie
    kam auf allen vier Kanaelen an, ist keine Entwarnung, und das Gedaechtnis traegt die Quelle
    ``slf_bulletin`` mit der gemeldeten Stufe."""
    erst = lage.lauf(0, antwort)
    trip_vorbedingung_alle_kanaele(erst)
    assert entwarnungen_gesamt(erst) == 0, f"Vorbedingung: Lauf 1 ist eine Warnung: {erst!r}"
    eintrag = lage.slf_eintrag()
    assert eintrag.get("source") == SLF_REGISTRY_NAME, (
        f"Vorbedingung: das Produkt ordnet die Meldung der Quelle slf_bulletin zu: {eintrag!r}")
    assert eintrag.get("last_reported_value") == float(stufe), (
        f"Vorbedingung: Stufe {stufe} gemeldet: {eintrag!r}")
    return erst


# ═══════════════════════════ AC-26 ══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac26_absenkung_4_auf_2_abgeleitet_ergibt_genau_eine_entwarnung_ueber_vier_kanaele(
        monkeypatch, mit, flaeche):
    """AC-26 [Absenkung => Entwarnung ueber vier Kanaele, Trip-Alarm UND Ortsvergleich-Alarm]
    GIVEN Lauf 1 meldet per Alarm die SLF-Warnung Stufe 4 fuer CH-7231 (abgeleitet aus
          at_2026-03-01T08:00:00Z.json) -- das Produkt schreibt das Gedaechtnis
          (source="slf_bulletin"); Premium-SMS hat die Schwelle "hoch"
    WHEN  der Folgelauf bei gesunder Quelle Stufe 2 fuer dieselbe Mikroregion liefert
          (gleiches Bulletin, abgeleitet)
    THEN  kommt genau EINE Entwarnung je Kanal -- E-Mail und Telegram "Entwarnung" + "4 -> 2",
          SMS und Premium-SMS `+AV4>2` (Premium-SMS nur dank der Dringlichkeit des ALTEN Werts),
          die Mail nennt das SLF als Quelle, und das Gedaechtnis steht danach auf 2.
    """
    morgen = slf_doc(WINTER_MORGEN)
    lage = SlfLage(flaeche, monkeypatch, mit, schwellen=PREMIUM_NUR_HOCH)
    lage.registrieren(monkeypatch)
    erstwarnung(lage, ok_doc(derive(morgen, RID, main_value=4)), stufe=4)

    snap = lage.lauf(15, ok_doc(derive(morgen, RID, main_value=2)))

    for kanal in ALLE_KANAELE:
        ew = entwarnungs_sendungen(snap, kanal)
        assert len(ew) == 1, f"AC-26 [{flaeche}/{kanal}]: genau eine Entwarnung erwartet: {snap!r}"
        if kanal in ("sms", "premium_sms"):
            assert "+AV4>2" in ew[0]["body"], (
                f"AC-26 [{flaeche}/{kanal}]: Block `+AV4>2` fehlt: {ew[0]['body']!r}")
        else:
            text = _texte(ew[0])
            assert "Entwarnung" in text and VIER_AUF_ZWEI.search(text), (
                f"AC-26 [{flaeche}/{kanal}]: 'Entwarnung' + '4 -> 2' fehlt: {text[:600]!r}")
    mail = _texte(entwarnungs_sendungen(snap, "email")[0])
    assert SLF_LABEL in mail, f"AC-26 [{flaeche}]: Entwarnungs-Mail nennt das SLF nicht: {mail[:800]!r}"
    eintrag = lage.slf_eintrag()
    assert eintrag.get("last_reported_value") == 2.0, (
        f"AC-26 [{flaeche}]: Gedaechtnis nach Entwarnung nicht auf 2 gesenkt: {eintrag!r}")


# ═══════════════════════════ AC-27 ══════════════════════════════════════════


@pytest.mark.parametrize("erst, dann", [("plus", "minus"), ("minus", "plus")],
                         ids=["3plus-zu-3minus", "3minus-zu-3plus"])
@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac27_feinstufenwechsel_abgeleitet_ist_weder_entwarnung_noch_neuer_alarm(
        monkeypatch, mit, flaeche, erst, dann):
    """AC-27 [Feinstufenwechsel ist keine Entwarnung]
    GIVEN Lauf 1 meldet per Alarm die SLF-Stufe 3 mit Feinstufe ``erst`` (CH-7231, Feinstufe
          abgeleitet aus at_2026-03-01T08:00:00Z.json) -- das Produkt schreibt das Gedaechtnis
    WHEN  der Folgelauf dieselbe Stufe 3 mit Feinstufe ``dann`` liefert
    THEN  geht in KEINEM Kanal etwas hinaus (weder Entwarnung noch neue Warnung), und das
          Gedaechtnis bleibt bei Stufe 3.
    """
    morgen = slf_doc(WINTER_MORGEN)
    vorher = mit_feinstufe_abgeleitet(morgen, RID, erst)
    nachher = mit_feinstufe_abgeleitet(morgen, RID, dann)
    assert vorher != nachher, "Testaufbau: die Feinstufe unterscheidet die beiden Antworten"
    lage = SlfLage(flaeche, monkeypatch, mit)
    lage.registrieren(monkeypatch)
    erstwarnung(lage, ok_doc(vorher), stufe=3)

    snap = lage.lauf(15, ok_doc(nachher))

    assert not _alles_gesendete(snap), (
        f"AC-27 [{flaeche}, 3{erst}->3{dann}]: Feinstufenwechsel loeste eine Nachricht aus: {snap!r}")
    eintrag = lage.slf_eintrag()
    assert eintrag.get("last_reported_value") == 3.0, (
        f"AC-27 [{flaeche}]: Gedaechtnis verliess Stufe 3: {eintrag!r}")


# ═══════════════════════════ AC-28 ══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac28_quellenwechsel_at_zu_ch_ist_keine_entwarnung(monkeypatch, mit, flaeche):
    """AC-28 [Quellenwechsel AT<->CH ist keine Entwarnung]
    GIVEN im Gedaechtnis steht fuer den Ort-Schluessel eine Lagebericht-Warnung der Quelle
          `avalanche_report` (Tirol, aufgezeichnetes Bulletin 2026-03-01, Zeitraum laeuft noch);
          der Ort liegt in der Schweiz (CH-7121), aber in der Bounding-Box Tirols -- die AT-Quelle
          ist also gefragt und antwortet "nicht zustaendig"; die SLF-Quelle liefert Stufe 3
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  wird die AT-Warnung in keinem Lauf als "gesenkt" oder "beendet" gemeldet, der
          AT-Eintrag bleibt unveraendert, und die SLF-Warnung wird wie jede neue Warnung genau
          einmal gemeldet (Lauf 1 auf allen vier Kanaelen, Lauf 2 still).
    """
    from output.renderers.alert.official_alerts import (
        official_alert_state_entry, official_alert_state_key,
    )
    from services.alert_state import AlertStateService
    from tests.helpers.avalanche_report_support import FixtureTransport, make_source, parse_alert

    lage = SlfLage(flaeche, monkeypatch, mit, region=RID_AT_BBOX)
    at_quelle = make_source(FixtureTransport(), FakeClock(T0))
    assert at_quelle.covers(lage.lat, lage.lon), (
        "Testaufbau: die AT-Quelle muss fuer den Punkt gefragt werden (Tirol-Bounding-Box)")
    at_alert = parse_alert("2026-03-01_AT-07_de_CAAMLv6.json", "AT-07-05")
    assert at_alert.valid_from <= T0 < at_alert.valid_to, "Testaufbau: AT-Zeitraum laeuft noch"
    at_key = official_alert_state_key(at_alert)
    at_eintrag = official_alert_state_entry(
        at_alert, (T0 - timedelta(hours=1)).isoformat(), source="avalanche_report",
        scope=[lage.scope])
    AlertStateService(user_id=lage.uid).save(lage.entity, {at_key: dict(at_eintrag)})
    lage.registrieren(monkeypatch, at_quelle)

    eins = lage.lauf(0, WINTER_MORGEN)
    zwei = lage.lauf(15)

    assert entwarnungen_gesamt(eins) == 0 and entwarnungen_gesamt(zwei) == 0, (
        f"AC-28 [{flaeche}]: Quellenwechsel ergab eine Entwarnung: {eins!r} {zwei!r}")
    trip_vorbedingung_alle_kanaele(eins)  # die SLF-Warnung ist eine gewoehnliche neue Warnung
    assert not _alles_gesendete(zwei), f"AC-28 [{flaeche}]: Lauf 2 wiederholte etwas: {zwei!r}"
    eintrag = lage.slf_eintrag()
    assert eintrag.get("source") == SLF_REGISTRY_NAME and eintrag.get("last_reported_value") == 3.0, (
        f"AC-28 [{flaeche}]: SLF-Warnung nicht als neue Meldung erfasst: {eintrag!r}")
    assert gedaechtnis(lage.uid, lage.entity).get(at_key) == at_eintrag, (
        f"AC-28 [{flaeche}]: AT-Eintrag wurde veraendert (gesenkt/beendet/absent_since): "
        f"{gedaechtnis(lage.uid, lage.entity).get(at_key)!r}")


# ═══════════════════════════ AC-29 ══════════════════════════════════════════

FAELLE = {
    "abruffehler-http-503": http_503,
    "abruffehler-netz": netzfehler,
    "leere-saison": leer,
    "region-verschwunden": lambda: ok_doc(ohne_region_abgeleitet(slf_doc(WINTER_MORGEN), RID)),
}


@pytest.mark.parametrize("fall", list(FAELLE))
@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac29_ausfall_leere_saison_und_verschwundene_region_sind_keine_entwarnung(
        monkeypatch, mit, flaeche, fall):
    """AC-29 [Ausfall, leere Saison, verschwundene Region sind keine Entwarnung]
    GIVEN Lauf 1 meldet per Alarm die SLF-Stufe 3 (CH-7231, aufgezeichnet) -- das Produkt
          schreibt das Gedaechtnis
    WHEN  zwei weitere Laeufe hintereinander (a) einen SLF-Abruffehler (HTTP 503 bzw.
          Netzfehler), (b) die leere Saison-Antwort ``{"bulletins":[]}`` oder (c) dasselbe
          Bulletin ohne die Region erhalten
    THEN  geht in keinem der beiden Laeufe etwas hinaus (keine Entwarnung "gesenkt"/"beendet"),
          und das Gedaechtnis ist nach beiden Laeufen unveraendert (kein ``absent_since``, kein
          ``ended_at``, Stufe 3).
    """
    lage = SlfLage(flaeche, monkeypatch, mit)
    lage.registrieren(monkeypatch)
    erstwarnung(lage, WINTER_MORGEN, stufe=3)
    nach_lauf_1 = copy.deepcopy(lage.slf_eintraege())

    zwei = lage.lauf(15, FAELLE[fall]())
    drei = lage.lauf(30, FAELLE[fall]())

    assert entwarnungen_gesamt(zwei) == 0 and entwarnungen_gesamt(drei) == 0, (
        f"AC-29 [{flaeche}/{fall}]: Schein-Entwarnung: {zwei!r} {drei!r}")
    assert not _alles_gesendete(zwei) and not _alles_gesendete(drei), (
        f"AC-29 [{flaeche}/{fall}]: es ging etwas hinaus: {zwei!r} {drei!r}")
    assert lage.slf_eintraege() == nach_lauf_1, (
        f"AC-29 [{flaeche}/{fall}]: Gedaechtnis veraendert: vorher {nach_lauf_1!r}, "
        f"nachher {lage.slf_eintraege()!r}")
