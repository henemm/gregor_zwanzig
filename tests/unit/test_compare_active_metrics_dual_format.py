"""TDD RED — Kern-Tests zu `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`
(#1373, S2 Scheibe B): die Metrik-Auswahl eines Orts-Vergleichs
(`display_config.active_metrics`) wird kuenftig als Liste aus Groesse +
Auswertung gespeichert (`[{"metric_id": "temperature", "aggregation": "max"}]`),
das Altformat (Liste von Zeichenketten) wird DAUERHAFT weiter gelesen.

Deckt AC-1 bis AC-5 sowie AC-10 auf Kern-Ebene ab.

Erwartete, heute noch NICHT existierende Schnittstellen (darum ROT):

* `compare_metric_catalog.key_for(metric_id, aggregation) -> str | None`
  -- Umkehr-Index ueber COMPARE_METRIC_CATALOG (Spec, Implementation Details 1).
* `compare_metric_catalog.duplicate_metric_aggregation_pairs(entries=None)
  -> list[tuple[str, str]]` -- der Eindeutigkeits-Waechter aus AC-10 als
  aufrufbare, GETEILTE Funktion. Produktions-Waechter und Wirkungsnachweis
  muessen DIESELBE Funktion ausfuehren (Adversary-Befund F002 aus Scheibe A:
  eine im Test nachgebaute Kopie der Pruflogik beweist nichts).
* `compare_metric_ids.resolve_enabled_metrics()` loest PRO ELEMENT auf --
  Zeichenkette ODER `{"metric_id": ..., "aggregation": ...}` (Spec, Punkt 2).

Heutiger Zustand (nachgemessen 2026-07-26): ein Neuformat-Element laeuft in
`m not in FRONTEND_TO_RENDERER_METRIC_ID` und wirft
`TypeError: unhashable type: 'dict'` -- exakt das Restrisiko R2 der Spec. Die
Neuformat-Tests scheitern daher heute mit TypeError, nicht mit einem falschen
Ergebnis.

Kern-Schicht, deterministisch: kein Netz, kein Mock, kein `patch()`, kein
Datei-I/O. Erwartungswerte werden aus dem ECHTEN Katalog abgeleitet (nicht aus
`key_for()` selbst -- das waere zirkulaer) und zusaetzlich an den drei
Verifikationsankern der Spec namentlich festgenagelt.
"""
from __future__ import annotations

import logging

from output.renderers import compare_metric_catalog as catalog_module
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG,
    get_compare_metric_catalog,
)
from output.renderers.compare_metric_ids import (
    FRONTEND_TO_RENDERER_METRIC_ID,
    resolve_enabled_metrics,
)

# ---------------------------------------------------------------------------
# Zugriff auf die erwarteten neuen Schnittstellen. Bewusst per getattr INNERHALB
# der Tests, damit ein fehlendes Symbol jeden betroffenen Test einzeln und mit
# lesbarer Begruendung rot macht -- ein Import-Fehler auf Modulebene wuerde
# stattdessen die Collection der ganzen Datei (und laut #1196-Vorfall notfalls
# der ganzen Suite) reissen.
# ---------------------------------------------------------------------------


def _key_for():
    fn = getattr(catalog_module, "key_for", None)
    assert callable(fn), (
        "compare_metric_catalog.key_for(metric_id, aggregation) fehlt -- der "
        "Umkehr-Index aus Spec Implementation Details Punkt 1 ist noch nicht "
        "implementiert."
    )
    return fn


def _duplicate_pairs_fn():
    fn = getattr(catalog_module, "duplicate_metric_aggregation_pairs", None)
    assert callable(fn), (
        "compare_metric_catalog.duplicate_metric_aggregation_pairs(entries=None) "
        "fehlt -- AC-10 verlangt den Eindeutigkeits-Waechter als GETEILTE, "
        "aufrufbare Funktion (nicht als im Test nachgebaute Mengenarithmetik, "
        "Adversary-Befund F002 aus Scheibe A)."
    )
    return fn


def _expected_renderer_id(metric_id: str, aggregation: str) -> str:
    """Erwartungswert UNABHAENGIG von `key_for()` aus dem echten Katalog
    abgeleitet: (metric_id, aggregation) -> Katalog-`key` ->
    FRONTEND_TO_RENDERER_METRIC_ID. Wuerde der Test seine Erwartung ueber
    `key_for()` bilden, pruefte er die Funktion gegen sich selbst."""
    matches = [
        entry["key"]
        for entry in COMPARE_METRIC_CATALOG
        if entry.get("metric_id") == metric_id and entry.get("aggregation") == aggregation
    ]
    assert len(matches) == 1, (
        f"Der echte Katalog fuehrt fuer ({metric_id!r}, {aggregation!r}) nicht "
        f"genau einen Eintrag, sondern {matches!r} -- Erwartungswert nicht "
        f"bildbar (siehe AC-10)."
    )
    return FRONTEND_TO_RENDERER_METRIC_ID[matches[0]]


def _pair(metric_id: str, aggregation: str) -> dict:
    return {"metric_id": metric_id, "aggregation": aggregation}


# ===========================================================================
# AC-1 -- Die Verschmelzungsfalle: dieselbe Groesse in zwei Auswertungen
# ===========================================================================


def test_same_metric_in_two_aggregations_stays_two_rows():
    """AC-1 (wichtigster Test der Lieferung): Hoechst- UND Tiefsttemperatur
    tragen dieselbe `metric_id` ("temperature") und unterscheiden sich NUR in
    der `aggregation`. Jede Gruppierung/Deduplikation nach `metric_id` allein
    laesst sie zu einer Zeile verschmelzen -- der Nutzer verliert dann still
    eine seiner beiden Temperaturzeilen (Verifikationsanker der Spec: drei
    Produktions-Vergleiche haben genau diese Kombination).
    """
    selection = [_pair("temperature", "max"), _pair("temperature", "min")]

    resolved = resolve_enabled_metrics(selection)

    expected = [
        _expected_renderer_id("temperature", "max"),
        _expected_renderer_id("temperature", "min"),
    ]
    assert len(set(expected)) == 2, (
        f"Vorbedingung verletzt: Hoechst- und Tiefsttemperatur bilden im echten "
        f"Katalog nicht auf zwei verschiedene Renderer-Kennungen ab: {expected}"
    )
    # Am Verifikationsanker der Spec namentlich festgenagelt (nachgemessenes
    # heutiges Verhalten, nicht angenommen).
    assert expected == ["temp_max", "temp_min"], (
        f"Ableitung aus dem echten Katalog ergibt {expected} statt der "
        f"nachgemessenen heutigen Werte ['temp_max', 'temp_min']"
    )
    assert resolved == expected, (
        f"AC-1: die Auswahl (temperature/max, temperature/min) muss ZWEI "
        f"getrennte Zeilen in dieser Reihenfolge ergeben, nicht {resolved!r} -- "
        f"sonst verschmilzt eine der beiden Temperaturzeilen."
    )


def test_wind_chill_min_and_max_also_stay_two_rows():
    """AC-1, zweiter Zwilling: "Gefuehlte Temp. min"/"max" teilen die
    `metric_id` "wind_chill". Dieselbe Falle, anderer Anker."""
    resolved = resolve_enabled_metrics(
        [_pair("wind_chill", "min"), _pair("wind_chill", "max")]
    )

    expected = [
        _expected_renderer_id("wind_chill", "min"),
        _expected_renderer_id("wind_chill", "max"),
    ]
    assert expected == ["wind_chill_min", "wind_chill_max"]
    assert resolved == expected, (
        f"AC-1: gefuehlte Tiefst- und Hoechsttemperatur muessen zwei getrennte "
        f"Zeilen bleiben, nicht {resolved!r}"
    )


# ===========================================================================
# AC-2 -- Reihenfolge ist bedeutungstragend (#1335/#1359)
# ===========================================================================


def test_new_format_selection_keeps_the_users_order():
    """AC-2: die gespeicherte Reihenfolge ist die Nutzer-Reihenfolge, keine
    Menge. Die Eingabe ist bewusst NICHT alphabetisch sortiert -- ein `set()`
    oder eine Sortierung an falscher Stelle faellt hier auf."""
    selection = [
        _pair("wind", "max"),
        _pair("temperature", "min"),
        _pair("snow_depth", "max"),
        _pair("precipitation", "sum"),
    ]

    resolved = resolve_enabled_metrics(selection)

    expected = [_expected_renderer_id(p["metric_id"], p["aggregation"]) for p in selection]
    assert expected != sorted(expected), (
        f"Vorbedingung verletzt: die Erwartung {expected} ist zufaellig bereits "
        f"alphabetisch -- der Reihenfolge-Nachweis waere wertlos."
    )
    assert resolved == expected, (
        f"AC-2: die aufgeloeste Liste muss positionsgetreu der Eingabe folgen.\n"
        f"erwartet: {expected}\ntatsaechlich: {resolved}"
    )


def test_duplicate_pair_in_selection_deduplicates_order_preserving():
    """AC-2, Bestandsverhalten: der Dedup-Schluessel bleibt die Renderer-
    Kennung (`dict.fromkeys`, reihenfolge-erhaltend). Dasselbe Paar zweimal --
    und dieselbe Groesse einmal alt, einmal neu geschrieben -- ergibt eine
    Zeile, die erste Position gewinnt."""
    resolved = resolve_enabled_metrics(
        [
            _pair("temperature", "max"),
            _pair("wind", "max"),
            _pair("temperature", "max"),
            "temp_max_c",
        ]
    )

    expected = [
        _expected_renderer_id("temperature", "max"),
        _expected_renderer_id("wind", "max"),
    ]
    assert resolved == expected, (
        f"AC-2: Mehrfachnennung derselben Groesse+Auswertung (auch gemischt "
        f"ueber beide Speicherformate) muss reihenfolge-erhaltend auf eine "
        f"Zeile zusammenfallen: {resolved!r} != {expected!r}"
    )


# ===========================================================================
# AC-3 -- Leere Auswahl: Verhalten bleibt UNVERAENDERT (#1191)
# ===========================================================================


def test_empty_selection_returns_empty_list():
    """Issue #1366: die bewusst leere Auswahl liefert `[]`, nicht mehr `None`
    (= "leer heisst leer" statt "leer heisst alle"). Die Dual-Format-
    Normalisierung (`_to_key`) davor bleibt unveraendert, nur der Rueckgabewert
    aendert sich."""
    assert resolve_enabled_metrics([]) == [], (
        "Issue #1366: leere Auswahl muss [] ergeben (bewusst leer), nicht None"
    )


def test_non_list_input_stays_defensive_and_never_raises():
    """AC-3 (defensiver Teil, Bestandsverhalten): `None` und Nicht-Listen
    ergeben `None` -- kein TypeError, kein Iterieren ueber String-Zeichen oder
    Dict-Schluessel. Muss auch nach dem Formatwechsel gelten, weil der neue
    Aufloeser pro Element entscheidet."""
    for bad in (None, {}, {"temp_max_c": True}, "temp_max_c", 0, 5, ()):
        assert resolve_enabled_metrics(bad) is None, (
            f"AC-3: Nicht-Listen-Eingabe {bad!r} muss defensiv None ergeben"
        )


def test_selection_with_only_unresolvable_entries_returns_empty_list():
    """Issue #1366 (AC-2): bildet die Auswahl komplett auf nichts Aufloesbares
    ab, ist das Ergebnis `[]` (keine Zeile), nicht `None` (= alle) -- fuer
    Neuformat-Eintraege genauso wie fuer Zeichenketten."""
    assert resolve_enabled_metrics([_pair("gibtsnicht", "max")]) == [], (
        "Eine Auswahl nur aus unbekannten Groesse-Auswertung-Paaren muss [] "
        "ergeben (wie bei nur unbekannten Zeichenketten)"
    )
    assert resolve_enabled_metrics(["gibtsnicht_auch_nicht"]) == []


# ===========================================================================
# AC-4 -- Altformat wird DAUERHAFT weiter gelesen, bitgleich zu heute
# ===========================================================================


def test_legacy_string_selection_resolves_exactly_as_today():
    """AC-4: eine reine Zeichenketten-Auswahl (Vergleich vor der Umstellung
    angelegt, nie neu gespeichert) liefert genau dasselbe wie heute. Belegt
    gegen die echte heutige Tabelle UND gegen die nachgemessenen Werte der drei
    Verifikationsanker der Spec."""
    legacy = ["temp_max_c", "temp_min_c", "wind_chill_min_c"]

    resolved = resolve_enabled_metrics(legacy)

    assert resolved == [FRONTEND_TO_RENDERER_METRIC_ID[k] for k in legacy], (
        f"AC-4: Altformat muss ueber die unveraenderte Tabelle aufgeloest "
        f"werden: {resolved!r}"
    )
    assert resolved == ["temp_max", "temp_min", "wind_chill_min"], (
        f"AC-4: nachgemessenes heutiges Ergebnis (2026-07-26) war "
        f"['temp_max', 'temp_min', 'wind_chill_min'], jetzt {resolved!r}"
    )


def test_every_legacy_key_still_resolves_after_the_format_switch():
    """AC-4, Vollabdeckung: JEDER der heute gueltigen Auswahl-Schluessel muss
    nach der Umstellung weiterhin aufloesen -- kein Schluessel darf durch die
    neue Pro-Element-Verzweigung durchfallen. Mengen-Vergleich, keine
    hartkodierte Anzahl."""
    legacy_keys = [entry["key"] for entry in get_compare_metric_catalog()]

    resolved = resolve_enabled_metrics(legacy_keys)

    expected = [FRONTEND_TO_RENDERER_METRIC_ID[k] for k in legacy_keys]
    assert resolved == expected, (
        f"AC-4: nicht alle Altformat-Schluessel loesen unveraendert auf.\n"
        f"fehlend: {sorted(set(expected) - set(resolved or []))}"
    )


def test_new_format_reaches_the_same_rows_as_the_legacy_format():
    """AC-4/AC-8-Vorbedingung im Kern: dieselbe Auswahl, einmal alt und einmal
    neu geschrieben, muss auf DIESELBEN Zeilen in DERSELBEN Reihenfolge
    fuehren. Das ist die eigentliche Zusicherung der Lieferung ("dieselbe
    Auswahl ergibt dieselbe Mail") -- ueber alle 26 Katalog-Eintraege."""
    entries = get_compare_metric_catalog()
    legacy = [entry["key"] for entry in entries]
    modern = [_pair(entry["metric_id"], entry["aggregation"]) for entry in entries]

    assert resolve_enabled_metrics(modern) == resolve_enabled_metrics(legacy), (
        "Alt- und Neuformat derselben Auswahl fuehren zu unterschiedlichen "
        "Zeilen -- die Umstellung waere nutzersichtbar."
    )


# ===========================================================================
# AC-5 -- Mischliste (Restrisiko R1: stehengebliebene Browser-Sitzung)
# ===========================================================================


def test_mixed_legacy_and_new_format_entries_all_resolve():
    """AC-5: eine Auswahl mit Zeichenkette UND Objekt im selben Array (real
    erreichbar durch eine stehengebliebene Browser-Sitzung, Restrisiko R1)
    darf nicht abbrechen -- alle gueltigen Elemente erscheinen, in Eingabe-
    Reihenfolge."""
    selection = ["temp_max_c", _pair("temperature", "min")]

    resolved = resolve_enabled_metrics(selection)

    expected = [
        FRONTEND_TO_RENDERER_METRIC_ID["temp_max_c"],
        _expected_renderer_id("temperature", "min"),
    ]
    assert resolved == expected, (
        f"AC-5: Mischliste muss vollstaendig und reihenfolge-erhaltend "
        f"aufgeloest werden: {resolved!r} != {expected!r}"
    )


def test_mixed_list_with_junk_keeps_the_valid_entries():
    """AC-5 (Haerte): unbekanntes Paar, Objekt ohne `aggregation`, Objekt ohne
    `metric_id` und ein voellig fremder Typ stehen zwischen gueltigen
    Eintraegen. Erwartung: die gueltigen Eintraege erscheinen, der Rest wird
    verworfen (wie heute nicht mappbare Zeichenketten), kein Absturz."""
    selection = [
        "temp_max_c",
        _pair("gibtsnicht", "max"),
        {"metric_id": "temperature"},  # Auswertung fehlt -> nicht aufloesbar
        {"aggregation": "min"},  # Groesse fehlt -> nicht aufloesbar
        None,
        42,
        ["verschachtelt"],
        _pair("wind", "max"),
    ]

    resolved = resolve_enabled_metrics(selection)

    expected = [
        FRONTEND_TO_RENDERER_METRIC_ID["temp_max_c"],
        _expected_renderer_id("wind", "max"),
    ]
    assert resolved == expected, (
        f"AC-5: unbekannte/kaputte Elemente muessen verworfen werden, ohne die "
        f"gueltigen mitzunehmen: {resolved!r} != {expected!r}"
    )


def test_unresolvable_new_format_entry_is_logged_not_silently_dropped(caplog):
    """AC-5/#1285-#1296-Guard: ein unbekanntes Groesse-Auswertung-Paar wird
    wie eine nicht mappbare Zeichenkette mit einem sichtbaren Warning
    verworfen -- stille Verwerfung ist genau der Bug-Typ, der sich hier nicht
    wiederholen darf."""
    with caplog.at_level(logging.WARNING):
        resolve_enabled_metrics(["temp_max_c", _pair("gibtsnicht", "max")])

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        "Ein unaufloesbares Groesse-Auswertung-Paar wurde kommentarlos "
        "verworfen -- kein Log-Warning erzeugt (vgl. #1285/#1296)."
    )
    assert any("gibtsnicht" in r.getMessage() for r in warnings), (
        f"Kein Warning nennt das verworfene Paar: "
        f"{[r.getMessage() for r in warnings]}"
    )


# ===========================================================================
# key_for() -- der Umkehr-Index selbst
# ===========================================================================


def test_key_for_resolves_every_catalog_entry_back_to_its_key():
    """Umkehr-Index (Spec Punkt 1): fuer JEDEN Katalog-Eintrag gilt
    key_for(metric_id, aggregation) == key. Kein Eintrag darf unerreichbar
    sein -- ein unerreichbarer Eintrag ist eine Metrik, die nach der Migration
    nicht mehr geschrieben/gelesen werden kann."""
    key_for = _key_for()

    unreachable = [
        entry["key"]
        for entry in COMPARE_METRIC_CATALOG
        if key_for(entry["metric_id"], entry["aggregation"]) != entry["key"]
    ]
    assert not unreachable, (
        f"Diese Katalog-Eintraege sind ueber (metric_id, aggregation) nicht "
        f"erreichbar: {sorted(unreachable)}"
    )


def test_key_for_returns_none_for_unknown_or_incomplete_pairs():
    """Umkehr-Index: unbekannte oder unvollstaendige Paare ergeben `None`
    (Signal "nicht aufloesbar"), kein KeyError und keine Ausnahme -- darauf
    beruht der Verwerfungspfad aus AC-5."""
    key_for = _key_for()

    assert key_for("gibtsnicht", "max") is None
    assert key_for("temperature", "gibtsnicht") is None
    assert key_for("temperature", None) is None
    assert key_for(None, "max") is None
    assert key_for("", "") is None


def test_key_for_distinguishes_aggregations_of_the_same_metric():
    """Umkehr-Index, Kern der Verschmelzungsfalle: dieselbe `metric_id` mit
    verschiedener `aggregation` MUSS auf verschiedene Schluessel fuehren."""
    key_for = _key_for()

    assert key_for("temperature", "max") == "temp_max_c"
    assert key_for("temperature", "min") == "temp_min_c"
    assert key_for("wind_chill", "min") == "wind_chill_min_c"
    assert key_for("wind_chill", "max") == "wind_chill_max_c"


# ===========================================================================
# AC-10 -- Eindeutigkeits-Waechter MIT Wirkungsnachweis
# ===========================================================================


def test_all_catalog_metric_aggregation_pairs_are_unique():
    """AC-10 (Produktions-Waechter): jedes (metric_id, aggregation)-Paar im
    Vergleichs-Katalog kommt genau einmal vor. Waeren zwei Zeilen paargleich,
    kollidierten sie im Neuformat unbemerkt auf denselben Auswahl-Eintrag --
    eine der beiden Metriken waere nicht mehr speicherbar. Mengen-Vergleich
    ohne hartkodierte Anzahl."""
    duplicate_pairs = _duplicate_pairs_fn()

    duplicates = duplicate_pairs()
    assert not duplicates, (
        f"Der Vergleichs-Katalog fuehrt mehrfach dasselbe Groesse-Auswertung-"
        f"Paar: {duplicates} -- im Neuformat nicht unterscheidbar."
    )

    pairs = [(e["metric_id"], e["aggregation"]) for e in COMPARE_METRIC_CATALOG]
    assert len(pairs) == len(set(pairs)) == len(COMPARE_METRIC_CATALOG), (
        f"Anzahl Paare ({len(pairs)}) weicht von der Anzahl eindeutiger Paare "
        f"({len(set(pairs))}) bzw. der Katalog-Groesse "
        f"({len(COMPARE_METRIC_CATALOG)}) ab."
    )


def test_pair_uniqueness_guard_actually_fires_on_a_duplicated_pair():
    """AC-10 Wirkungsnachweis: DIESELBE geteilte Pruef-Funktion, die der
    Produktions-Waechter oben benutzt, laeuft gegen eine KOPIE des echten
    Katalogs, in der ein Paar dupliziert ist -- und muss dann tatsaechlich
    anschlagen und das Paar benennen. Ausdruecklich KEINE im Test nachgebaute
    Mengenarithmetik (Adversary-Befund F002 aus Scheibe A: das waere ein
    zirkulaerer Nachweis)."""
    duplicate_pairs = _duplicate_pairs_fn()

    real_entries = get_compare_metric_catalog()
    assert not duplicate_pairs(real_entries), (
        "Vorbedingung verletzt: der echte Katalog enthaelt bereits ein "
        "doppeltes Paar -- der Wirkungsnachweis waere nicht aussagekraeftig."
    )

    victim = next(e for e in real_entries if e["metric_id"] == "wind")
    sabotaged = [*real_entries, {**victim, "key": "kunst_dublette"}]

    found = duplicate_pairs(sabotaged)
    assert found, (
        "Der Eindeutigkeits-Waechter schlaegt bei einem kuenstlich duplizierten "
        "Paar NICHT an -- er ist wirkungslos."
    )
    expected_pair = (victim["metric_id"], victim["aggregation"])
    assert expected_pair in [tuple(p) for p in found], (
        f"Der Befund nennt das duplizierte Paar {expected_pair} nicht: {found}"
    )


def test_pair_uniqueness_guard_reacts_to_its_input():
    """AC-10 Wirkungsnachweis, Teil 2: die Pruef-Funktion darf ihr Ergebnis
    nicht zwischenspeichern oder eingabeblind sein -- sonst wuerde sie eine
    Beschaedigung genau dann nicht bemerken, wenn sie mit anderen Daten
    aufgerufen wird (F002)."""
    duplicate_pairs = _duplicate_pairs_fn()

    assert duplicate_pairs([]) == [] or duplicate_pairs([]) == list(), (
        "Leere Eingabe muss einen leeren Befund ergeben"
    )
    handmade = [
        {"key": "a", "metric_id": "temperature", "aggregation": "max"},
        {"key": "b", "metric_id": "temperature", "aggregation": "min"},
        {"key": "c", "metric_id": "temperature", "aggregation": "max"},
    ]
    found = [tuple(p) for p in duplicate_pairs(handmade)]
    assert found == [("temperature", "max")], (
        f"Pruef-Funktion liest ihre Eingabe nicht wie erwartet: {found}"
    )
