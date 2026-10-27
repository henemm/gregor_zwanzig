"""TDD RED — Issue #2185 (Epic #2133, Scheibe S2): Ad-hoc-Verlauf nennt
WECHSELPUNKTE statt jeder Einzelstunde.

SPEC: docs/specs/modules/feat_2185_verlauf_wechselpunkte.md

Warum diese Datei existiert: ``_format_drilldown`` listet heute jede Stunde
einzeln. Die Frage unterwegs ist aber "wann verzieht sich der Nebel?" — also
der WECHSELPUNKT, nicht der Einzelmesswert. Aufeinanderfolgende Stunden mit
identischem formatiertem Wert muessen zu EINEM Zeitbereich verschmelzen.

Mock-frei: echte ``DrilldownPoint``/``DrilldownResult``-Dataclasses, echte
Katalog-Formatierer (``_metric_formatter(get_metric(...))``), echte
``TripCommandProcessor``-Methode. Die Ende-zu-Ende-Wachen (AC-9/AC-10) laufen
ueber echten Trip + echten Stunden-Snapshot (``tests/helpers/
adhoc_metrik_fixtures.py``), also ueber genau den Weg, den ein getipptes Wort
produktiv nimmt.

Der Kern der Nachweisform ist ``abdeckung()``: sie rekonstruiert aus den
ausgelieferten Zeilen, welche Datenpunkte jede Zeile abdeckt, und erzwingt
eine LUECKENLOSE, UEBERSCHNEIDUNGSFREIE Partition der ``res.points``. Das
loest die alte Form-Regel "mindestens 6 Zeilen, je Uhrzeit eine"
(``telegram_tier3_drilldown.md`` AC-1) ab und prueft staerker: sie faengt
sowohl einen verschluckten Punkt als auch einen Bereich, der eine Datenluecke
ueberbrueckt.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.metric_catalog import get_metric
from app.models import ThunderLevel
from services.trip_command_processor import (
    TripCommandProcessor,
    _metric_formatter,
)
from services.weather_extractor import DrilldownPoint, DrilldownResult
from tests.helpers.adhoc_metrik_fixtures import lege_trip_an, sende
from tests.helpers.verlauf_abdeckung import grenzen, zeilen
from utils.timezone import local_fmt

# ---------------------------------------------------------------------------
# Feste Bezugspunkte — bewusst Europe/Paris (Ortszeit != Weltzeit, #1470) und
# ein Fensterbeginn weit weg von der Ortsmitternacht, damit keine Zusicherung
# still an einem Tageswechsel haengt.
# ---------------------------------------------------------------------------

TZ = ZoneInfo("Europe/Paris")
START = datetime(2026, 9, 10, 6, 0, tzinfo=timezone.utc)   # 08:00 Ortszeit
STUNDE = timedelta(hours=1)

TEMP_FMT = _metric_formatter(get_metric("temperature"))
THUNDER_FMT = _metric_formatter(get_metric("thunder"))


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def _res(werte, *, schritt=STUNDE, start=START) -> DrilldownResult:
    """``DrilldownResult`` aus einer Werteliste, ein Punkt je ``schritt``."""
    return DrilldownResult(
        trip_id="tdd-2185",
        metric="t2m_c",
        points=[
            DrilldownPoint(ts=start + i * schritt, value=v)
            for i, v in enumerate(werte)
        ],
        available=True,
    )


def _res_versetzt(paare, *, start=START) -> DrilldownResult:
    """``DrilldownResult`` aus ``(stunden_offset, wert)``-Paaren.

    Erlaubt es, eine Stunde AUSZULASSEN — genau der Fall, den AC-5 braucht.
    """
    return DrilldownResult(
        trip_id="tdd-2185",
        metric="t2m_c",
        points=[
            DrilldownPoint(ts=start + timedelta(hours=h), value=v)
            for h, v in paare
        ],
        available=True,
    )


def _formatiere(res, fmt=TEMP_FMT, *, with_emoji: bool = True, hail=None) -> str:
    """Der ECHTE Produktiv-Formatierer, nicht seine Nachbildung."""
    return TripCommandProcessor()._format_drilldown(
        res, "Temperatur", fmt, TZ, with_emoji=with_emoji, hail_by_ts=hail,
    )


def abdeckung(body: str, res: DrilldownResult) -> list[list[DrilldownPoint]]:
    """Welcher Datenpunkt wird von welcher Zeile abgedeckt?

    Erzwingt eine lueckenlose, ueberschneidungsfreie Partition von
    ``res.points`` (AC-7) und verbietet, dass ein Bereich eine Datenluecke
    ueberbrueckt: innerhalb einer Bereichszeile duerfen zwei aufeinander
    folgende Punkte hoechstens eine Stunde auseinanderliegen, sonst
    behauptete der Bereich Gueltigkeit fuer eine ungemessene Stunde (#2167).
    """
    punkte = list(res.points)
    i = 0
    gruppen: list[list[DrilldownPoint]] = []
    for von, bis in grenzen(body):
        assert i < len(punkte), (
            f"Zeile {von}–{bis} deckt einen Zeitpunkt ab, fuer den kein "
            f"Datenpunkt vorliegt (alle {len(punkte)} Punkte sind bereits "
            f"von frueheren Zeilen abgedeckt).\n{body}"
        )
        assert local_fmt(punkte[i].ts, TZ) == von, (
            f"Zeile beginnt bei {von}, der naechste unabgedeckte Datenpunkt "
            f"liegt aber bei {local_fmt(punkte[i].ts, TZ)}.\n{body}"
        )
        anfang = i
        if bis is None:
            i += 1
        else:
            while i < len(punkte) and local_fmt(punkte[i].ts, TZ) != bis:
                i += 1
            assert i < len(punkte), (
                f"Bereichsende {bis} entspricht keinem Datenpunkt.\n{body}"
            )
            i += 1
        gruppe = punkte[anfang:i]
        for a, b in zip(gruppe, gruppe[1:]):
            assert b.ts - a.ts <= STUNDE, (
                f"Bereich {von}–{bis} ueberbrueckt eine Luecke von "
                f"{b.ts - a.ts} zwischen {local_fmt(a.ts, TZ)} und "
                f"{local_fmt(b.ts, TZ)}.\n{body}"
            )
        gruppen.append(gruppe)
    assert i == len(punkte), (
        f"{len(punkte) - i} Datenpunkte sind von keiner Zeile abgedeckt "
        f"(ab {local_fmt(punkte[i].ts, TZ) if i < len(punkte) else '-'}).\n"
        f"{body}"
    )
    return gruppen


# ---------------------------------------------------------------------------
# AC-1: zwei gleiche Folgestunden werden EIN Zeitbereich
# ---------------------------------------------------------------------------

def test_ac1_zwei_gleiche_folgestunden_ergeben_einen_zeitbereich():
    """
    GIVEN: 08:00 und 09:00 (Ortszeit) tragen denselben formatierten Wert
    WHEN:  der Nutzer den Verlauf abruft
    THEN:  beide erscheinen als EIN Zeitbereich 08:00–09:00, nicht als zwei
           Einzelzeilen
    """
    res = _res([18.0, 18.0])
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "09:00")], (
        f"Erwartet EINE Bereichszeile 08:00–09:00, erhalten "
        f"{grenzen(body)}:\n{body}"
    )
    assert abdeckung(body, res) == [res.points]


# ---------------------------------------------------------------------------
# AC-2: unveraenderter Wert ueber das ganze Fenster = GENAU EIN Bereich
# ---------------------------------------------------------------------------

def test_ac2_durchgehend_gleicher_wert_ergibt_genau_einen_bereich():
    """
    GIVEN: zwoelf Stunden mit identischem formatiertem Wert (durchgehend
           trocken)
    WHEN:  der Verlauf abgerufen wird
    THEN:  GENAU EIN Zeitbereich vom ersten bis zum letzten Zeitpunkt — es
           wird kein Wechselpunkt erfunden, wo keiner ist
    """
    res = _res([18.0] * 12)
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "19:00")], (
        f"Erwartet GENAU EINEN Bereich 08:00–19:00, erhalten "
        f"{grenzen(body)}:\n{body}"
    )
    assert len(abdeckung(body, res)) == 1


# ---------------------------------------------------------------------------
# AC-3: stuendlicher Wechsel = je Stunde eine Zeile (Regressionswaechter)
# ---------------------------------------------------------------------------

def test_ac3_stuendlicher_wechsel_behaelt_je_stunde_eine_zeile():
    """
    GIVEN: zwoelf Stunden mit paarweise unterschiedlichem formatiertem Wert
    WHEN:  der Verlauf abgerufen wird
    THEN:  je Stunde eine eigene Zeile mit Einzeluhrzeit — kein Wert geht
           verloren, keiner rutscht auf eine falsche Uhrzeit

    Regressionswaechter: dieser Fall ist schon heute erfuellt und MUSS es
    nach der Verdichtung bleiben.
    """
    res = _res([10.0 + i for i in range(12)])
    body = _formatiere(res)

    assert grenzen(body) == [
        (f"{h:02d}:00", None) for h in range(8, 20)
    ], f"Erwartet zwoelf Einzelzeilen 08:00..19:00, erhalten:\n{body}"

    for treffer, punkt in zip(zeilen(body), res.points):
        assert treffer.group("text") == TEMP_FMT(punkt.value, with_emoji=True), (
            f"Wert der Zeile {treffer.group('von')} passt nicht zum "
            f"Datenpunkt {local_fmt(punkt.ts, TZ)}:\n{body}"
        )
    assert [len(g) for g in abdeckung(body, res)] == [1] * 12


# ---------------------------------------------------------------------------
# AC-4: die Gruppierung vergleicht den ANZEIGETEXT, nicht den Rohwert
# ---------------------------------------------------------------------------

def test_ac4_gleicher_anzeigetext_bei_verschiedenem_rohwert_gruppiert():
    """
    GIVEN: zwei Folgestunden mit UNTERSCHIEDLICHEM Rohwert (21.2 / 21.4), die
           auf denselben Anzeigetext runden
    WHEN:  der Verlauf abgerufen wird
    THEN:  beide bilden EINEN Zeitbereich — die Rundung des bestehenden
           Formatierers IST die Kategorie

    Mutations-Gegenprobe: vergleicht die Implementierung den Rohwert statt des
    formatierten Textes, faellt genau dieser Test.
    """
    roh_a, roh_b = 21.2, 21.4
    assert roh_a != roh_b, "Vorbedingung: die Rohwerte muessen sich unterscheiden."
    assert TEMP_FMT(roh_a, with_emoji=True) == TEMP_FMT(roh_b, with_emoji=True), (
        "Vorbedingung: beide Rohwerte muessen auf denselben Text runden — "
        "sonst prueft dieser Test nicht, was er behauptet."
    )

    res = _res([roh_a, roh_b])
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "09:00")], (
        f"Gleicher Anzeigetext bei verschiedenem Rohwert muss EINEN Bereich "
        f"ergeben, erhalten {grenzen(body)}:\n{body}"
    )


# ---------------------------------------------------------------------------
# AC-5: eine fehlende Stunde BRICHT den Bereich
# ---------------------------------------------------------------------------

def test_ac5_fehlende_stunde_bricht_den_zeitbereich():
    """
    GIVEN: im Fenster fehlt eine Stunde ganz (kein Datenpunkt um 10:00), die
           umliegenden Punkte tragen denselben Wert
    WHEN:  der Verlauf abgerufen wird
    THEN:  der Bereich endet vor der Luecke und ein neuer beginnt danach —
           kein Bereich ueberbrueckt die fehlende Stunde

    Mutations-Gegenprobe: faellt die Lueckenpruefung weg, entsteht ein
    durchgehender Bereich 08:00–11:00 und dieser Test wird rot.
    """
    res = _res_versetzt([(0, 18.0), (1, 18.0), (3, 18.0)])
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "09:00"), ("11:00", None)], (
        f"Erwartet einen Bereich vor und eine Einzelstunde nach der Luecke, "
        f"erhalten {grenzen(body)}:\n{body}"
    )
    assert [len(g) for g in abdeckung(body, res)] == [2, 1]


# ---------------------------------------------------------------------------
# AC-6: fehlende Werte bilden einen eigenen, BENANNTEN Bereich
# ---------------------------------------------------------------------------

def test_ac6_fehlende_werte_bilden_eigenen_benannten_bereich():
    """
    GIVEN: zwei aufeinanderfolgende Punkte mit ``value=None``, danach ein
           Messwert
    WHEN:  der Verlauf abgerufen wird
    THEN:  die Luecke wird als eigener, benannter Bereich ausgeliefert und
           verschmilzt NIE mit dem Messwert (S1/AC-17 gilt weiter)
    """
    res = _res([None, None, 18.0])
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "09:00"), ("10:00", None)], (
        f"Erwartet eine Luecken-Zeile ueber beide None-Stunden und eine "
        f"getrennte Messwert-Zeile, erhalten {grenzen(body)}:\n{body}"
    )
    luecke, messwert = zeilen(body)
    assert luecke.group("text") == TEMP_FMT(None, with_emoji=True), (
        f"Die Luecke muss BENANNT bleiben, erhalten "
        f"{luecke.group('text')!r}:\n{body}"
    )
    assert messwert.group("text") == TEMP_FMT(18.0, with_emoji=True)


# ---------------------------------------------------------------------------
# AC-7: Abdeckungs-Zusicherung (loest telegram_tier3_drilldown.md AC-1 ab)
# ---------------------------------------------------------------------------

def test_ac7_jeder_datenpunkt_von_genau_einer_zeile_abgedeckt():
    """
    GIVEN: ein Fenster mit Wiederholungen, einer Datenluecke und fehlenden
           Werten
    WHEN:  der Verlauf abgerufen wird
    THEN:  jeder Zeitpunkt mit Datenpunkt ist von GENAU EINER Zeile abgedeckt,
           und keine Zeile deckt einen Zeitpunkt ohne Datenpunkt ab

    Diese Zusicherung ersetzt die alte Form-Regel "mindestens 6 Zeilen, je
    Uhrzeit eine" (``telegram_tier3_drilldown.md`` AC-1, PO-Entscheid #2185).
    Die zweite Zusicherung haelt fest, dass die Antwort dabei tatsaechlich
    verdichtet — ohne sie wuerde die reine Abdeckungspruefung auch von der
    alten Stunde-fuer-Stunde-Liste bestanden.
    """
    res = _res_versetzt([
        (0, 18.0), (1, 18.0), (2, 18.0),
        (3, 25.0),
        (5, 25.0), (6, 25.0),          # Luecke bei Stunde 4
        (7, None), (8, None),
        (9, 18.0),
    ])
    body = _formatiere(res)

    gruppen = abdeckung(body, res)
    assert sum(len(g) for g in gruppen) == len(res.points)
    assert len(zeilen(body)) < len(res.points), (
        f"Die Antwort verdichtet nicht: {len(zeilen(body))} Zeilen fuer "
        f"{len(res.points)} Datenpunkte:\n{body}"
    )


# ---------------------------------------------------------------------------
# AC-8: Kanalparitaet — der Emoji-Schalter aendert die Gruppierung nicht
# ---------------------------------------------------------------------------

def test_ac8_gruppengrenzen_sind_in_beiden_kanaelen_identisch():
    """
    GIVEN: dieselbe Datenlage, einmal mit ``with_emoji=True`` (Telegram),
           einmal mit ``with_emoji=False`` (E-Mail)
    WHEN:  beide Antworten erzeugt werden
    THEN:  die Gruppengrenzen sind identisch — der Emoji-Schalter aendert nur
           die Wortwahl INNERHALB einer Zeile, nie die Gruppierung
    """
    res = _res([
        ThunderLevel.NONE, ThunderLevel.NONE, ThunderLevel.NONE,
        ThunderLevel.MED, ThunderLevel.MED,
        ThunderLevel.HIGH,
    ])
    telegram = _formatiere(res, THUNDER_FMT, with_emoji=True)
    email = _formatiere(res, THUNDER_FMT, with_emoji=False)

    assert grenzen(telegram) == grenzen(email), (
        f"Gruppengrenzen laufen zwischen den Kanaelen auseinander:\n"
        f"telegram={grenzen(telegram)}\nemail={grenzen(email)}"
    )
    assert grenzen(telegram) == [
        ("08:00", "10:00"), ("11:00", "12:00"), ("13:00", None),
    ], f"Erwartete Wechselpunkte nicht getroffen:\n{telegram}"
    assert abdeckung(telegram, res) == abdeckung(email, res)
    assert telegram != email, (
        "Gegenprobe: die beiden Kanaele muessen sich im Zeilentext "
        "unterscheiden, sonst prueft der Vergleich nichts."
    )


# ---------------------------------------------------------------------------
# AC-9: die Verdichtung wirkt ueber BEIDE Aufrufer
# ---------------------------------------------------------------------------

def _konstanter_wind(i: int) -> dict:
    """Stundenpunkt mit ueber das ganze Fenster KONSTANTEM Wind."""
    return {
        "t2m_c": 10.0 + i,
        "wind10m_kmh": 24.0,
        "precip_1h_mm": 0.3,
        "thunder_level": ThunderLevel.MED,
    }


@pytest.fixture
def fix_konstant():
    return lege_trip_an("2185-beide-aufrufer", _konstanter_wind)


def test_ac9_legacy_token_verdichtet_zu_zeitbereichen(fix_konstant):
    """
    GIVEN: konstanter Wind ueber das ganze Antwortfenster
    WHEN:  der Verlauf ueber den Legacy-Token ``dd_wind_today``
           (``_handle_drilldown``) abgerufen wird
    THEN:  die Antwort traegt Bereichszeilen statt Einzelstunden
    """
    result = sende(fix_konstant, "### query: dd_wind_today")

    assert result.success, (
        f"dd_wind_today muss Werte liefern: {result.confirmation_body!r}"
    )
    bereiche = [g for g in grenzen(result.confirmation_body) if g[1]]
    assert bereiche, (
        f"Legacy-Aufrufer ``_handle_drilldown`` verdichtet nicht — nur "
        f"Einzelstunden:\n{result.confirmation_body}"
    )


def test_ac9_katalog_groesse_verdichtet_zu_zeitbereichen(fix_konstant):
    """
    GIVEN: dieselbe Datenlage
    WHEN:  der Verlauf ueber das getippte Katalog-Wort ``wind``
           (``_handle_metric_drilldown``) abgerufen wird
    THEN:  die Antwort traegt ebenfalls Bereichszeilen

    Mutations-Gegenprobe: wirkt die Gruppierung nur in EINEM der beiden
    Aufrufer, faellt genau einer dieser beiden Tests.
    """
    result = sende(fix_konstant, "wind")

    assert result.command == "metrik_wind", (
        f"'wind' muss ueber ``_handle_metric_drilldown`` laufen, erhalten "
        f"{result.command!r}"
    )
    assert result.success, (
        f"'wind' muss Werte liefern: {result.confirmation_body!r}"
    )
    bereiche = [g for g in grenzen(result.confirmation_body) if g[1]]
    assert bereiche, (
        f"Katalog-Aufrufer ``_handle_metric_drilldown`` verdichtet nicht — "
        f"nur Einzelstunden:\n{result.confirmation_body}"
    )


def test_ac9_beide_aufrufer_liefern_dieselben_gruppengrenzen(fix_konstant):
    """Dieselbe Datenlage, dieselbe Groesse — beide Wege muessen dieselbe
    Verdichtung liefern. Ohne diesen Vergleich koennte ein Weg gruppieren und
    der andere eine ANDERE Gruppierung liefern, ohne dass etwas rot wird."""
    legacy = sende(fix_konstant, "### query: dd_wind_today")
    katalog = sende(fix_konstant, "wind")

    assert grenzen(legacy.confirmation_body) == grenzen(katalog.confirmation_body), (
        f"Die beiden Aufrufer verdichten unterschiedlich:\n"
        f"legacy={grenzen(legacy.confirmation_body)}\n"
        f"katalog={grenzen(katalog.confirmation_body)}"
    )


# ---------------------------------------------------------------------------
# AC-10: die Vierspalten-Stundentabelle bleibt unangetastet
# ---------------------------------------------------------------------------

def test_ac10_stundentabelle_bleibt_stunde_fuer_stunde(fix_konstant):
    """
    GIVEN: ``dd_hours_today`` (die feste Vierspalten-Tabelle)
    WHEN:  sie abgerufen wird
    THEN:  sie bleibt eine Stunde-fuer-Stunde-Tabelle — diese Scheibe fasst
           sie NICHT an

    Regressionswaechter: muss vor UND nach der Verdichtung gruen sein.
    """
    result = sende(fix_konstant, "### query: dd_hours_today")

    assert result.success, (
        f"dd_hours_today muss Werte liefern: {result.confirmation_body!r}"
    )
    stundenzeilen = [
        z for z in result.confirmation_body.splitlines()
        if re.match(r"^\d{2}\s", z)
    ]
    assert len(stundenzeilen) >= 6, (
        f"Die Vierspalten-Tabelle muss je Stunde eine Zeile behalten, "
        f"gefunden {len(stundenzeilen)}:\n{result.confirmation_body}"
    )
    assert not [
        z for z in result.confirmation_body.splitlines()
        if re.search(r"\d{2}:\d{2}\s*[–—-]\s*\d{2}:\d{2}", z)
    ], (
        f"Die Vierspalten-Tabelle darf KEINE Zeitbereiche bilden:\n"
        f"{result.confirmation_body}"
    )


# ---------------------------------------------------------------------------
# AC-11: die Fortsetzung haengt an HOECHSTENS einer Stunde, nicht an GENAU
# ---------------------------------------------------------------------------

def test_ac11_halbstuendlicher_abstand_setzt_den_bereich_fort():
    """
    GIVEN: zwei Datenpunkte im Abstand von 30 Minuten mit identischem
           formatiertem Wert
    WHEN:  der Verlauf abgerufen wird
    THEN:  sie bilden EINEN Zeitbereich — die Fortsetzungsbedingung ist
           ``<= 1 h``, nicht ``== 1 h``

    Prueft ausschliesslich das Gruppierungsverhalten bei konstruiertem
    ``ts``-Abstand; sie sichert NICHT zu, dass ein Wetterdienst je ein
    feineres Raster liefert.

    Mutations-Gegenprobe: verschaerft man die Bedingung auf ``== 1 h``, bricht
    die Gruppe bei 30 Minuten faelschlich auf und dieser Test wird rot.
    """
    res = _res([18.0, 18.0], schritt=timedelta(minutes=30))
    body = _formatiere(res)

    assert grenzen(body) == [("08:00", "08:30")], (
        f"Zwei gleiche Werte im 30-Minuten-Abstand muessen EINEN Bereich "
        f"bilden, erhalten {grenzen(body)}:\n{body}"
    )


# ---------------------------------------------------------------------------
# Kopfzeile — Spec-Sektion "Implementation Details", Punkt 6
# ---------------------------------------------------------------------------

def test_kopfzeile_nennt_verlauf_statt_stuendlich():
    """Die Kopfzeile beschreibt die Antwort: sie nennt nicht mehr jede
    Stunde, also heisst sie ``— Verlauf`` statt ``— stuendlich``."""
    body = _formatiere(_res([18.0, 18.0]))
    kopf = body.splitlines()[0]

    assert kopf.endswith("— Verlauf"), (
        f"Erwartete Kopfzeile '... — Verlauf', erhalten {kopf!r}"
    )
