"""Waechter (#2232, AC-11): `kuerzel_metric_id` darf keine Kennung sein, die der
Ortsvergleich selbst anbietet.

SPEC: docs/specs/modules/fix_2232_kuerzel_ein_modell_trip_vergleich.md

Warum es diesen Waechter braucht (Befund B1 der Rev.-1-Messung): die vier
Gehzeit-Groessen (`temperature_day_low/_high`, `wind_chill_day_low/_high`) sind
dem Trip vorbehalten (#1848 Scheibe C, PO-Entscheid 2026-08-19) -- sie fenstern
ueber die Gehzeit entlang der Route, der Ortsvergleich ueber ein konfiguriertes
Tagesfenster (04-19). Dieselbe Kennung auf beiden Seiten lieferte VERSCHIEDENE
Zahlen. `kuerzel_metric_id` traegt deshalb ausschliesslich das Kuerzel und die
Editor-Marke; sobald jemand es auf eine Kennung setzt, die der Vergleich als
`metric_id` selbst fuehrt, ist die Trennung aufgehoben und der Import scheitert.

Bauprinzip: Produktions-Zusicherung und Wirkungsnachweis rufen DIESELBE
Funktion auf -- eine im Test nachgebaute Kopie der Pruflogik bewiese nichts
(Adversary-Fund F002 aus #1373 Scheibe A). Der Modul-Import fuehrt
`assert_kuerzel_identity()` ohne Argument aus; der Test unten ruft genau diese
Funktion mit einer verfaelschten Katalogkopie und erwartet den
`AssertionError`. Bewusst OHNE Lesen des Produkt-Quelltextes: das waere ein
Dateiinhalt-Check (CLAUDE.md-Verbot, durchgesetzt von
`tests/tdd/test_765_backend_hygiene_compliance.py`).

Test-Politik (CLAUDE.md, Schicht "Kern"): deterministisch, kein Netz, kein Mock.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from output.renderers import compare_metric_catalog as katalog_mod
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG, assert_kuerzel_identity, get_compare_metric_catalog,
    kuerzel_identity_violations,
)

# Issue #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
_REPO = Path(__file__).resolve().parents[2]


def test_waechter_prueft_den_code_dieses_arbeitsbaums():
    """#1409: der Pruefling muss aus DIESEM Arbeitsbaum stammen."""
    pfad = Path(katalog_mod.__file__).resolve()
    assert str(pfad).startswith(str(_REPO)), (
        f"Der Waechter prueft {pfad} statt den Code unterhalb {_REPO}."
    )


def test_der_echte_katalog_verletzt_die_trennung_nicht():
    """AC-11 am Bestand: keine `kuerzel_metric_id` zeigt auf eine Kennung, die
    der Ortsvergleich selbst als `metric_id` anbietet."""
    assert kuerzel_identity_violations() == []


def test_der_waechter_hat_ueberhaupt_material():
    """Nichtstun ist kein Bestehen: es muss `kuerzel_metric_id`-Eintraege geben,
    sonst prueft dieser Waechter eine leere Menge."""
    getragen = [
        e["key"] for e in COMPARE_METRIC_CATALOG if e.get("kuerzel_metric_id")
    ]
    assert len(getragen) >= 4, (
        f"Nur {len(getragen)} Katalogzeilen tragen `kuerzel_metric_id` "
        f"({getragen!r}) -- erwartet mindestens die vier der Temperatur-Familie."
    )


def test_die_vier_kuerzel_kennungen_bleiben_ausserhalb_des_vergleichs_angebots():
    """Die Gehzeit-Exklusivitaet aus #1848 Scheibe C bleibt gewahrt: die vier
    Kennungen erscheinen als KUERZEL-Quelle, aber NIE als angebotene Groesse
    der Vergleichsantwort (dieselbe Zusicherung, die
    `test_gehzeit_metriken_bleiben_trip_exklusiv.py` von der anderen Seite
    fuehrt)."""
    angeboten = {e["metric_id"] for e in get_compare_metric_catalog()}
    kuerzel_ids = {
        e["kuerzel_metric_id"] for e in COMPARE_METRIC_CATALOG
        if e.get("kuerzel_metric_id")
    }
    ueberschneidung = sorted(angeboten & kuerzel_ids)
    assert not ueberschneidung, (
        f"Kennungen, die zugleich Kuerzel-Quelle UND angebotene "
        f"Vergleichsgroesse sind: {ueberschneidung}"
    )


def test_wirkungsnachweis_verfaelschter_eintrag_wird_namentlich_gemeldet():
    """Gegenprobe an einer KOPIE (der echte Katalog bleibt unberuehrt): eine
    `kuerzel_metric_id`, die der Vergleich selbst anbietet, wird mit Key UND
    Kennung im Text gemeldet -- ueber DIESELBE Funktion, die der Import ruft."""
    kopie = [dict(e) for e in COMPARE_METRIC_CATALOG]
    kopie[0] = {**kopie[0], "kuerzel_metric_id": kopie[0]["metric_id"]}

    befunde = kuerzel_identity_violations(entries=kopie)

    assert befunde, (
        "Die Gegenprobe bleibt still -- der Waechter faengt eine "
        "`kuerzel_metric_id` auf eine angebotene Kennung nicht."
    )
    text = " ".join(befunde)
    assert kopie[0]["key"] in text and kopie[0]["metric_id"] in text, (
        f"Die Meldung benennt Key und Kennung nicht: {befunde!r}"
    )


def test_wirkungsnachweis_unbekannte_kennung_wird_gemeldet():
    """Zweiter Zweig derselben Zusicherung: eine im Register unbekannte
    Kennung ist ebenfalls ein Befund (sonst zeigte die Marke ins Leere)."""
    kopie = [dict(e) for e in COMPARE_METRIC_CATALOG]
    kopie[0] = {**kopie[0], "kuerzel_metric_id": "gibt_es_nicht"}

    befunde = kuerzel_identity_violations(entries=kopie)

    assert befunde and "gibt_es_nicht" in " ".join(befunde), (
        f"Unbekannte Kennung wird nicht gemeldet: {befunde!r}"
    )


def test_die_import_zusicherung_bricht_bei_verletzung_ab():
    """AC-11 im Wortlaut: nicht nur die Befund-Liste, sondern die ZUSICHERUNG
    muss scheitern -- und zwar genau die, die der Modul-Import ausfuehrt
    (`assert_kuerzel_identity()`, aufgerufen am Ende von
    `compare_metric_catalog.py`). Der echte Katalog bleibt unberuehrt."""
    kopie = [dict(e) for e in COMPARE_METRIC_CATALOG]
    kopie[0] = {**kopie[0], "kuerzel_metric_id": kopie[0]["metric_id"]}

    with pytest.raises(AssertionError) as fehler:
        assert_kuerzel_identity(entries=kopie)
    assert kopie[0]["metric_id"] in str(fehler.value), (
        f"Der Import-Assert benennt die verletzende Kennung nicht: {fehler.value}"
    )

    # Positivkontrolle: dieselbe Zusicherung laeuft am ECHTEN Katalog durch --
    # sonst waere die Roete oben nur ein generell kaputter Aufrufpfad.
    assert_kuerzel_identity()
