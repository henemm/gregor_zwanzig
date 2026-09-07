"""TDD RED — Issue #2134 (Epic #2133 S1): das Ad-hoc-Abrufvokabular kommt aus
dem Metrik-Katalog, nicht aus einer handgepflegten Kurzliste.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-1, AC-2, AC-3, AC-8, AC-18, AC-19, AC-20.

RED-Ursache: `_DRILLDOWN_METRICS` (trip_command_processor.py:287-291) kennt
genau drei Groessen (thunder/wind/precip); `_BARE_KEYWORD_MAP` (:87-103) kennt
kein einziges Katalog-Kuerzel. Ein getipptes `Visib`/`Humid`/`Thdr` faellt
deshalb heute in den Zweig "Unbekannter Befehl" (:396-405).

Mock-frei: echter Trip ueber `save_trip()`, echter Stunden-Snapshot ueber
`WeatherSnapshotService`, echter `TripCommandProcessor().process()`. Die
Mutations-Gegenprobe (AC-19) veraendert den Katalog ueber
`dataclasses.replace` + `monkeypatch` auf die Modul-Register — sie fasst KEINE
Datei an und braucht deshalb weder eine Sicherungskopie noch ein
`git checkout` (das laut CLAUDE.md ohnehin verboten ist).
"""
from __future__ import annotations

import re

import pytest

from tests.helpers.adhoc_metrik_fixtures import (
    ist_unbekannt,
    katalog_abrufwoerter,
    katalog_eintrag_ersetzt,
    lege_trip_an,
    metrik_abrufwoerter,
    normalisiere,
    sende,
    standard_felder,
    steuerbefehl_woerter,
    text_woerter,
)
# Issue #2185: die Wechselpunkt-Verdichtung fasst aufeinanderfolgende Stunden
# mit demselben Anzeigetext im Einzelgroessen-Verlauf (`_format_drilldown`)
# zu EINEM Zeitbereich zusammen — Zeilen- bzw. Treffer-Zahl sind dort kein
# brauchbarer Stellvertreter mehr fuer "mehrere Stunden". Ersatz: die
# Abdeckungs-Zusicherung aus feat_2185_verlauf_wechselpunkte.md AC-7.
from tests.helpers.verlauf_abdeckung import abgedeckte_stunden


# ===========================================================================
# AC-1 — bisher unmoegliche Groesse ueber ihr col_label abrufen
# ===========================================================================

def test_ac1_visib_liefert_stundenwerte_der_sichtweite_in_km():
    """AC-1 GIVEN der Katalog fuehrt `visibility` mit col_label `Visib` und
    display_unit km WHEN ein Nutzer per Telegram `Visib` sendet THEN enthaelt
    die Antwort Stundenwerte der Sichtweite mit der Einheit km."""
    fix = lege_trip_an(
        "ac1", lambda i: {**standard_felder(i), "visibility_m": 2000},
    )

    result = sende(fix, "Visib", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-1: `Visib` muss als Abrufwort der Sichtweite erkannt werden, "
        f"erhalten command={result.command!r} / "
        f"subject={result.confirmation_subject!r} / "
        f"body={result.confirmation_body!r}"
    )
    assert result.success is True, (
        f"AC-1: erwartet eine befuellte Antwort, erhalten success="
        f"{result.success} / body={result.confirmation_body!r}"
    )
    # Issue #2185: nach der Wechselpunkt-Verdichtung steht der Wert ggf. nur
    # EINMAL in der Antwort, deckt aber mehrere Stunden ab. Die Zusicherung
    # "mehrere Stunden zeigen diesen Wert" wird daher an der ABDECKUNG
    # gemessen (>=3 Stunden), nicht mehr an der Zeilen-/Treffer-Zahl.
    treffer = re.findall(r"\d+(?:[.,]\d+)?\s*km(?!/)", result.confirmation_body)
    assert len(treffer) >= 1, (
        f"AC-1: erwartet einen Stundenwert mit der Katalog-Einheit km, "
        f"gefunden {treffer!r} in:\n{result.confirmation_body}"
    )
    abgedeckt = abgedeckte_stunden(result.confirmation_body)
    assert len(abgedeckt) >= 3, (
        f"AC-1: erwartet mindestens 3 abgedeckte Stunden, gefunden "
        f"{abgedeckt!r} in:\n{result.confirmation_body}"
    )


# ===========================================================================
# AC-2 — Luftfeuchte ohne jeden Sonderlisten-Eintrag
# ===========================================================================

def test_ac2_humid_liefert_stundenwerte_ueber_den_kanal_eingang():
    """AC-2 GIVEN `humidity` (col_label `Humid`) hat in keiner Sonderliste des
    Abrufpfads einen Eintrag WHEN ein Nutzer `Humid` sendet THEN enthaelt die
    Antwort die Stundenwerte der Luftfeuchtigkeit — geprueft ueber
    `TripCommandProcessor.process()`, NICHT ueber einen Direktaufruf der
    Ableitungsfunktion."""
    fix = lege_trip_an(
        "ac2", lambda i: {**standard_felder(i), "humidity_pct": 55},
    )

    result = sende(fix, "Humid", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-2: `Humid` muss als Abrufwort der Luftfeuchte erkannt werden, "
        f"erhalten command={result.command!r} / "
        f"body={result.confirmation_body!r}"
    )
    # Issue #2185: Wechselpunkt-Verdichtung — siehe Kommentar bei AC-1 oben.
    treffer = re.findall(r"\b55\s*%", result.confirmation_body)
    assert len(treffer) >= 1, (
        f"AC-2: erwartet den Stundenwert '55 %', gefunden {treffer!r} "
        f"in:\n{result.confirmation_body}"
    )
    abgedeckt = abgedeckte_stunden(result.confirmation_body)
    assert len(abgedeckt) >= 3, (
        f"AC-2: erwartet mindestens 3 abgedeckte Stunden, gefunden "
        f"{abgedeckt!r} in:\n{result.confirmation_body}"
    )


def test_ac2_humid_folgt_dem_katalog_statt_einer_sonderliste(monkeypatch):
    """AC-2 (Ableitungsnachweis) GIVEN das col_label der Luftfeuchte wird
    testweise von `Humid` auf `Feuchte` geaendert WHEN ein Nutzer danach beide
    Woerter sendet THEN wird `Humid` NICHT mehr erkannt und `Feuchte` WIRD
    erkannt.

    Das ist die Spec-Aussage "`humidity` hat in keiner Sonderliste des
    Abrufpfads einen Eintrag" am VERHALTEN belegt: stuende das Wort irgendwo
    namentlich in einer Erlaubt-Liste, ueberlebte es die Katalog-Aenderung.
    Beide Richtungen sind Pflicht (Bauart wie AC-19) — nur das Verschwinden zu
    pruefen liesse eine Umsetzung durchgehen, die das Wort gar nicht kennt.
    """
    fix = lege_trip_an(
        "ac2b", lambda i: {**standard_felder(i), "humidity_pct": 55},
    )

    # Positivkontrolle: mit dem Katalogwert `Humid` muss der Abruf gehen.
    vorher = sende(fix, "Humid", channel="telegram")
    assert not ist_unbekannt(vorher), (
        f"AC-2 Vorbedingung: `Humid` wird gar nicht erkannt — die Gegenprobe "
        f"kann keinen Unterschied zeigen. body={vorher.confirmation_body!r}"
    )

    with katalog_eintrag_ersetzt(monkeypatch, "humidity", col_label="Feuchte"):
        altes_wort = sende(fix, "Humid", channel="telegram")
        neues_wort = sende(fix, "Feuchte", channel="telegram")

    assert ist_unbekannt(altes_wort), (
        f"AC-2: nach der Katalog-Aenderung darf `Humid` NICHT mehr erkannt "
        f"werden — die Luftfeuchte ist offenbar per Sonderliste "
        f"freigeschaltet statt abgeleitet. "
        f"body={altes_wort.confirmation_body!r}"
    )
    assert not ist_unbekannt(neues_wort), (
        f"AC-2: das neue Katalog-Kuerzel `Feuchte` muss erkannt werden, "
        f"erhalten body={neues_wort.confirmation_body!r}"
    )


# ===========================================================================
# AC-3 — selectable=false bleibt unerreichbar
# ===========================================================================

@pytest.mark.parametrize("wort", ["Conf", "TmpMin", "CAPE", "confidence", "cape"])
def test_ac3_nicht_waehlbare_groessen_liefern_keine_metrik_antwort(wort):
    """AC-3 GIVEN `confidence`/`temperature_cold`/`cape` sind selectable=false
    WHEN eines ihrer Woerter gesendet wird THEN antwortet das System mit
    "unbekannter Befehl"/Hilfe-Verweis statt mit einem Wert.

    HINWEIS: dieser Test ist im RED-Stand bereits GRUEN (heute ist jedes Wort
    unbekannt). Er ist der Waechter dagegen, dass die Umsetzung ueber die
    interne `_METRICS`-Liste statt ueber `get_all_metrics()` iteriert — dann
    wuerde er rot.
    """
    fix = lege_trip_an("ac3")

    result = sende(fix, wort, channel="telegram")

    assert ist_unbekannt(result), (
        f"AC-3: {wort!r} gehoert zu einer selectable=false-Groesse und darf "
        f"keine Metrik-Antwort erzeugen, erhalten success={result.success} / "
        f"command={result.command!r} / body={result.confirmation_body!r}"
    )


def test_ac3_vokabular_enthaelt_keine_nicht_waehlbare_groesse():
    """AC-3 (strukturell) GIVEN `metric_command_words()` speist sich aus
    `get_all_metrics()` WHEN das Vokabular gebildet wird THEN zeigt kein
    Eintrag auf `confidence`, `temperature_cold` oder `cape`."""
    vokabular = metrik_abrufwoerter()

    verboten = {"confidence", "temperature_cold", "cape"}
    getroffen = {w: m for w, m in vokabular.items() if m in verboten}

    assert not getroffen, (
        f"AC-3: das Abrufvokabular fuehrt nicht-waehlbare Groessen: "
        f"{getroffen!r} — die Ableitung laeuft nicht ueber get_all_metrics()."
    )


# ===========================================================================
# AC-8 — Hilfe nennt jede der 29 waehlbaren Groessen
# ===========================================================================

def test_ac8_hilfe_nennt_ein_abrufwort_je_katalog_groesse():
    """AC-8 GIVEN der Katalog fuehrt die waehlbaren Groessen WHEN der Nutzer
    `Hilfe` per Telegram sendet THEN enthaelt die Antwort fuer JEDE Groesse
    ein Abrufwort — strukturell gegen `get_all_metrics()` geprueft, nicht
    gegen eine im Test eingetippte Liste."""
    fix = lege_trip_an("ac8", mit_snapshot=False)

    result = sende(fix, "Hilfe", channel="telegram")
    gefunden = text_woerter(result.confirmation_body)

    erwartet = katalog_abrufwoerter()
    assert erwartet, "Testaufbau kaputt: get_all_metrics() liefert nichts."
    fehlend = {w: mid for w, mid in erwartet.items() if w not in gefunden}

    assert not fehlend, (
        f"AC-8: {len(fehlend)} von {len(erwartet)} Katalog-Groessen fehlen in "
        f"der Hilfe (normalisiertes Wort -> metric.id): {fehlend!r}\n"
        f"Hilfe-Text war:\n{result.confirmation_body}"
    )


# ===========================================================================
# AC-18 — Kollisionsfreiheit des Vokabulars
# ===========================================================================

def test_ac18_katalog_labels_sind_nach_normalisierung_kollisionsfrei():
    """AC-18 (Katalog-Waechter) GIVEN die normalisierten `col_label`-Woerter
    WHEN sie gebildet werden THEN bildet keine zweite Groesse auf dasselbe
    Wort ab — Regressionsfall `Rain`/`Rain%`.

    HINWEIS: im RED-Stand bereits GRUEN. Der Waechter schlaegt an, sobald eine
    neue Groesse ein kollidierendes Kuerzel bekommt.
    """
    from app.metric_catalog import get_all_metrics

    nach_wort: dict[str, list[str]] = {}
    for m in get_all_metrics():
        nach_wort.setdefault(normalisiere(m.col_label), []).append(m.id)
    kollisionen = {w: ids for w, ids in nach_wort.items() if len(ids) > 1}

    assert not kollisionen, (
        f"AC-18: normalisierte col_label-Kollision: {kollisionen!r}"
    )
    assert normalisiere("Rain") == "rain" and normalisiere("Rain%") == "rainpct", (
        f"AC-18: die %-Regel trennt Rain/Rain% nicht — "
        f"{normalisiere('Rain')!r} vs. {normalisiere('Rain%')!r}"
    )


def test_ac18_metric_command_words_ist_kollisionsfrei_und_vollstaendig():
    """AC-18 GIVEN `metric_command_words()` WHEN es gebildet wird THEN traegt
    es jede waehlbare Groesse genau einmal (kein Eintrag geht durch eine
    Kollision still verloren)."""
    vokabular = metrik_abrufwoerter()
    erwartet = katalog_abrufwoerter()

    fehlend = {w: mid for w, mid in erwartet.items() if w not in vokabular}
    assert not fehlend, (
        f"AC-18: diese Katalog-Woerter fehlen im Vokabular: {fehlend!r}"
    )
    ids = [vokabular[w] for w in erwartet]
    assert len(set(ids)) == len(erwartet), (
        f"AC-18: {len(erwartet)} Woerter zeigen auf nur {len(set(ids))} "
        f"verschiedene Groessen — eine Kollision hat Eintraege verschluckt."
    )


# ===========================================================================
# AC-19 — Mutations-Gegenprobe: das Abrufwort ist ABGELEITET
# ===========================================================================

def test_ac19_abrufwort_folgt_dem_katalog_in_beide_richtungen(monkeypatch):
    """AC-19 GIVEN das col_label der Sichtweite wird testweise von `Visib` auf
    `Sichtw` geaendert WHEN ein Nutzer danach beide Woerter sendet THEN wird
    `Visib` NICHT mehr erkannt und `Sichtw` WIRD erkannt.

    Beide Richtungen sind Pflicht: nur das Verschwinden zu pruefen liesse eine
    Umsetzung durchgehen, die das Wort gar nicht kennt.
    """
    fix = lege_trip_an(
        "ac19", lambda i: {**standard_felder(i), "visibility_m": 2000},
    )

    # Vorbedingung: mit dem Katalogwert `Visib` muss der Abruf funktionieren.
    vorher = sende(fix, "Visib", channel="telegram")
    assert not ist_unbekannt(vorher), (
        f"AC-19 Vorbedingung: `Visib` wird gar nicht erkannt — die Gegenprobe "
        f"kann keinen Unterschied zeigen. body={vorher.confirmation_body!r}"
    )

    with katalog_eintrag_ersetzt(monkeypatch, "visibility", col_label="Sichtw"):
        altes_wort = sende(fix, "Visib", channel="telegram")
        neues_wort = sende(fix, "Sichtw", channel="telegram")

    assert ist_unbekannt(altes_wort), (
        f"AC-19: nach der Katalog-Aenderung darf `Visib` NICHT mehr erkannt "
        f"werden — das Abrufwort ist offenbar danebengeschrieben statt "
        f"abgeleitet. body={altes_wort.confirmation_body!r}"
    )
    assert not ist_unbekannt(neues_wort), (
        f"AC-19: das neue Katalog-Kuerzel `Sichtw` muss erkannt werden, "
        f"erhalten body={neues_wort.confirmation_body!r}"
    )


# ===========================================================================
# AC-20 — Steuerbefehl und Metrikwort kollidieren nicht
# ===========================================================================

def test_ac20_gewitter_und_thdr_liefern_zwei_verschiedene_antworten():
    """AC-20 GIVEN `gewitter` ist Steuerbefehl (-> heute_gewitter) und `Thdr`
    das Abrufwort derselben Wettergroesse WHEN beide gesendet werden THEN
    liefert `gewitter` die Tagesaussage und `Thdr` den Stundenverlauf."""
    fix = lege_trip_an("ac20")

    tages = sende(fix, "gewitter", channel="telegram")
    stunden = sende(fix, "Thdr", channel="telegram")

    assert tages.command == "heute_gewitter" and tages.success, (
        f"AC-20: `gewitter` muss weiter die Gewitter-Tagesaussage liefern, "
        f"erhalten command={tages.command!r} / success={tages.success} / "
        f"body={tages.confirmation_body!r}"
    )
    assert not ist_unbekannt(stunden), (
        f"AC-20: `Thdr` muss als Abrufwort der Gewitterstufe erkannt werden, "
        f"erhalten command={stunden.command!r} / "
        f"body={stunden.confirmation_body!r}"
    )
    # Issue #2185: `Thdr` laeuft ueber denselben verdichtenden
    # Einzelgroessen-Formatierer (`_format_drilldown`) wie AC-1/AC-2 oben —
    # anders als die Vierspalten-Stundentabelle `dd_hours_*`, die nicht
    # verdichtet (AC-10) und deshalb unangetastet bleibt. Zeilenzahl ist hier
    # kein brauchbarer Stellvertreter mehr; ersetzt durch die
    # Abdeckungs-Zusicherung aus feat_2185_verlauf_wechselpunkte.md AC-7.
    abgedeckt = abgedeckte_stunden(stunden.confirmation_body)
    assert len(abgedeckt) >= 6, (
        f"AC-20: `Thdr` muss einen Stundenverlauf liefern, gefunden "
        f"{len(abgedeckt)} abgedeckte Stunden in:\n{stunden.confirmation_body}"
    )
    assert stunden.confirmation_body != tages.confirmation_body, (
        "AC-20: Tagesaussage und Stundenverlauf sind dieselbe Antwort — der "
        "Steuerbefehl wurde vom Metrikwort verdraengt (oder umgekehrt)."
    )


def test_ac20_steuerbefehle_und_metrikwoerter_sind_disjunkt():
    """AC-20 (Waechter) GIVEN beide Vokabulare WHEN sie gebildet werden THEN
    ist ihre Schnittmenge leer — kein Steuerbefehl wird von einem Metrikwort
    verdraengt."""
    steuer = steuerbefehl_woerter()
    metrik = set(metrik_abrufwoerter())

    schnitt = steuer & metrik
    assert not schnitt, (
        f"AC-20: Steuerbefehle und Metrik-Abrufwoerter ueberschneiden sich in "
        f"{sorted(schnitt)!r} — welcher Zweig greift, entscheidet dann die "
        f"Reihenfolge im Code statt der Fachlichkeit."
    )
