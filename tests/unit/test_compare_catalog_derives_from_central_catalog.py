"""Drift-Guard zentraler Wetterkatalog <-> Compare-Metrik-Katalog (#1373, S2
Scheibe A).

SPEC: docs/specs/modules/feat_1373_s2_ein_katalog.md (AC-1, AC-2, AC-5)

Der Compare-Katalog bleibt eine kuratierte Tabelle -- er wird NICHT erzeugt
(PO-Entscheidung 2026-07-26: Labels/Wertebereiche sind redaktionell). Jeder der
26 Eintraege bekommt stattdessen `metric_id` + `aggregation`. Von den vier
bestehenden Drift-Sicherungen rund um den Compare-Katalog prueft heute keine
die Beziehung zu `src/app/metric_catalog.py` -- eine neue waehlbare zentrale
Groesse kann im Ortsvergleich verschwinden, ohne dass ein Test anschlaegt.

Vorbild: `tests/unit/test_compare_metric_catalog_consistency.py` --
Mengen-Vergleich statt harter Anzahl, plus Wirkungsnachweise, die den Guard
kuenstlich brechen. Kern-Schicht: kein Netz, kein Mock, kein Datei-I/O; es
werden nur Kopien manipuliert, nie die echten Katalog-Listen.
"""
from __future__ import annotations

import sys
from dataclasses import replace

from app.metric_catalog import MetricDefinition, get_all_metrics
from output.renderers.compare_metric_catalog import get_compare_metric_catalog

# ---------------------------------------------------------------------------
# Ausnahmeliste zu Pruefung (c) -- klein, benannt, DARF NUR SCHRUMPFEN.
# Schluessel = zentrale Katalog-Kennung, Wert = Issue + Begruendung.
# Ein NEUER Eintrag hier ist ein Befund, kein Schleichweg: er bedeutet, dass
# eine zentrale Groesse ihr Tages-Auswertungsfeld verloren hat.
#
# Seit #1391/#1392 (Katalog-Korrektur: alle vier Groessen tragen jetzt
# summary_fields) leer -- s. test_aggregation_check_exemptions_empty_after_
# 1391_1392_fix weiter unten.
# ---------------------------------------------------------------------------
AGGREGATION_CHECK_EXEMPTIONS: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Festnagelung fuer die Ausnahmen (F001): die Ausnahme betrifft AUSSCHLIESSLICH
# den Abgleich gegen `summary_fields`. Die `aggregation` muss weiterhin eine der
# zentralen `default_aggregations` sein -- und wo davon mehr als eine zur Wahl
# steht, ist die Wahl redaktionell und wird hier NAMENTLICH festgenagelt. Ohne
# das bliebe ein echter Bedeutungsfehler (min <-> max) von jedem Test unbemerkt.
#
# Seit #1391 leer (snowfall_limit traegt jetzt summary_fields={"min": ...},
# geht damit durch den strengeren summary_fields-Abgleich, keine Ausnahme
# mehr noetig).
# ---------------------------------------------------------------------------
PINNED_EXEMPT_AGGREGATIONS: dict[str, tuple[str, str]] = {}


def _central_selectable() -> dict[str, MetricDefinition]:
    """Alle im zentralen Katalog waehlbaren Groessen (24; `selectable=False`
    -- temperature_cold, confidence -- filtert `get_all_metrics()` bereits)."""
    return {m.id: m for m in get_all_metrics()}


def _compare_metric_ids(entries: list[dict] | None = None) -> set[str]:
    """Die zentralen Kennungen, auf die der Compare-Katalog verweist. Eintraege
    ohne `metric_id` zaehlen bewusst NICHT mit -- fehlt das Feld, ist die
    Beziehung nicht vorhanden und der Guard muss rot werden.

    `entries` ist ein Parameter (Default = echter Katalog), damit dieselbe
    Funktion gegen echte Daten UND gegen kuenstlich gebrochene Kopien laufen
    kann -- ein Wirkungsnachweis, der ihr Ergebnis nur einmal zieht und danach
    lokal weiterrechnet, wuerde eine Beschaedigung genau hier nicht bemerken."""
    if entries is None:
        entries = get_compare_metric_catalog()
    return {entry["metric_id"] for entry in entries if entry.get("metric_id")}


def _central_metrics_without_compare_entry(
    entries: list[dict], central: dict[str, MetricDefinition]
) -> list[str]:
    """Pruefung (a) als aufrufbare Funktion: welche waehlbaren zentralen
    Groessen erreicht der Compare-Katalog NICHT (sortiert, leer = in Ordnung).
    Herausgezogen, damit Produktions-Guard (echte Daten) und Wirkungsnachweis
    (reduzierte Kopie) DIESELBE Logik ausfuehren -- inklusive
    `_compare_metric_ids()`."""
    return sorted(set(central) - _compare_metric_ids(entries))


def _aggregation_violations(
    entries: list[dict], central: dict[str, MetricDefinition]
) -> list[str]:
    """Pruefung (c) als reine Funktion; Rueckgabe sind lesbare Befunde (leer =
    in Ordnung). Herausgezogen, damit derselbe Ausdruck gegen echte Daten
    (Guard) UND gegen kuenstlich gebrochene Kopien (Wirkungsnachweis) laufen
    kann. Zwei Strengegrade:

    * zentrale Groesse traegt `summary_fields` und ist nicht ausgenommen ->
      `aggregation` MUSS eine davon sein;
    * ausgenommen -> `aggregation` muss immerhin eine der zentralen
      `default_aggregations` sein, und wo eine Festnagelung existiert, genau
      die (s. PINNED_EXEMPT_AGGREGATIONS). Die Ausnahme stellt also NUR den
      `summary_fields`-Abgleich still, nie die Plausibilitaet der Auswertung.

    F003: die Nachsicht haengt AUSSCHLIESSLICH an der Mitgliedschaft in
    AGGREGATION_CHECK_EXEMPTIONS, nicht am strukturellen Merkmal "traegt keine
    `summary_fields`". Sonst bekaeme jede kuenftig neu aufgenommene zentrale
    Groesse ohne Auswertungsfelder die Nachsicht automatisch -- ohne
    Listeneintrag und ohne Festnagelungspflicht. Die Liste ist das einzige
    Tor."""
    findings: list[str] = []
    for entry in entries:
        key = entry.get("key")
        metric_id = entry.get("metric_id")
        metric = central.get(metric_id) if metric_id else None
        if metric is None:
            continue
        aggregation = entry.get("aggregation")
        if metric.summary_fields and metric_id not in AGGREGATION_CHECK_EXEMPTIONS:
            if aggregation not in metric.summary_fields:
                findings.append(
                    f"{key!r}: aggregation={aggregation!r} ist keine "
                    f"Auswertung von {metric_id!r} "
                    f"(zentral: {sorted(metric.summary_fields)})"
                )
            continue
        if metric_id not in AGGREGATION_CHECK_EXEMPTIONS:
            findings.append(
                f"{key!r}: zentrale Groesse {metric_id!r} traegt keine "
                f"`summary_fields` und steht NICHT in "
                f"AGGREGATION_CHECK_EXEMPTIONS -- entweder `summary_fields` "
                f"fuer {metric_id!r} im zentralen Katalog "
                f"(src/app/metric_catalog.py) ergaenzen, oder {metric_id!r} "
                f"mit Issue-Verweis und Begruendung in die Ausnahmeliste "
                f"aufnehmen. Ohne ausdrueckliche Erklaerung gibt es keine "
                f"Nachsicht (F003)."
            )
            continue
        if aggregation not in metric.default_aggregations:
            findings.append(
                f"{key!r}: aggregation={aggregation!r} ist keine der zentral "
                f"vorgesehenen Auswertungen von {metric_id!r} "
                f"(default_aggregations: {sorted(metric.default_aggregations)})"
            )
            continue
        pinned = PINNED_EXEMPT_AGGREGATIONS.get(metric_id)
        if pinned and aggregation != pinned[0]:
            findings.append(
                f"{key!r}: aggregation={aggregation!r}, festgenagelt ist "
                f"{pinned[0]!r} -- {pinned[1]}"
            )
    return findings


# ---------------------------------------------------------------------------
# AC-2: Bestandsschutz -- die zwei Aufspaltungen bleiben vier eigene Eintraege
# ---------------------------------------------------------------------------


def test_temperature_and_wind_chill_stay_four_distinct_entries():
    """AC-2: "Temperatur max"/"min" und "Gefuehlte Temp. max"/"min" bleiben vier
    eigenstaendige Eintraege mit unterschiedlichem `key` und unterscheidbarem
    Label -- sonst verliert der Nutzer die Wahl zwischen Hoechst- und
    Tiefstwert. Bestandsverhalten, heute schon gruen."""
    by_key = {entry["key"]: entry for entry in get_compare_metric_catalog()}

    expected_keys = ("temp_max_c", "temp_min_c", "wind_chill_max_c", "wind_chill_min_c")
    missing = [k for k in expected_keys if k not in by_key]
    assert not missing, (
        f"Compare-Katalog fuehrt diese einzeln waehlbaren Eintraege nicht "
        f"(mehr): {missing} -- die Aufspaltung Hoechst-/Tiefstwert ist "
        f"verloren gegangen."
    )
    assert len({by_key[k]["key"] for k in expected_keys}) == 4

    labels = [by_key[k]["label"] for k in expected_keys]
    assert len(set(labels)) == 4, (
        f"Die vier Eintraege tragen nicht vier unterscheidbare Labels: {labels}"
    )


# ---------------------------------------------------------------------------
# AC-1: Drift-Guard in drei Richtungen
# ---------------------------------------------------------------------------


def test_every_selectable_central_metric_has_a_compare_entry():
    """AC-1 (a): JEDE waehlbare zentrale Groesse hat mindestens einen
    Compare-Eintrag mit passendem `metric_id` -- hier faellt kuenftig eine neue
    zentrale Groesse auf, die den Vergleich nicht erreicht. Mengen-Vergleich,
    keine hartkodierte Anzahl. Bewusst "mindestens einen": weniger exponierte
    Auswertungen als `default_aggregations` sind gewollte UI-Kuration."""
    missing = _central_metrics_without_compare_entry(
        get_compare_metric_catalog(), _central_selectable()
    )
    assert not missing, (
        f"Waehlbare zentrale Katalog-Groessen ohne Compare-Eintrag (im "
        f"Ortsvergleich nicht waehlbar, ohne dass es jemand merkt): {missing}"
    )


def test_every_compare_entry_points_to_an_existing_central_metric():
    """AC-1 (b): JEDER Compare-Eintrag traegt ein `metric_id`, das zentral
    existiert -- keine verwaisten Zeilen nach einer zentralen Umbenennung.
    """
    entries = get_compare_metric_catalog()

    without_metric_id = [e["key"] for e in entries if not e.get("metric_id")]
    assert not without_metric_id, (
        f"Compare-Eintraege ohne `metric_id` (keine Beziehung zum zentralen "
        f"Katalog nachweisbar): {sorted(without_metric_id)}"
    )

    central_ids = set(_central_selectable())
    orphaned = sorted(
        (e["key"], e["metric_id"]) for e in entries if e["metric_id"] not in central_ids
    )
    assert not orphaned, (
        f"Compare-Eintraege verweisen auf zentrale Groessen, die es nicht "
        f"(mehr) gibt: {orphaned}"
    )


def test_compare_aggregation_is_one_of_the_central_summary_fields():
    """AC-1 (c): wo die zentrale Groesse `summary_fields` traegt, ist die
    `aggregation` des Compare-Eintrags eine davon -- der Vergleich zeigt also
    nachweislich dieselbe Auswertung, die der zentrale Katalog kennt.
    Ausnahmen ausschliesslich aus AGGREGATION_CHECK_EXEMPTIONS.
    """
    central = _central_selectable()
    entries = get_compare_metric_catalog()

    # Ohne `aggregation` ist die Pruefung gar nicht durchfuehrbar -- das ist
    # ein Befund, kein Grund zum stillen Ueberspringen. Gilt fuer ALLE 26
    # Eintraege; die Ausnahmeliste betrifft nur den Abgleich mit
    # `summary_fields`, nicht das Vorhandensein der Angabe.
    without_aggregation = sorted(e["key"] for e in entries if not e.get("aggregation"))
    assert not without_aggregation, (
        f"Compare-Eintraege ohne `aggregation` (Auswertung nicht mit dem "
        f"zentralen Katalog abgleichbar): {without_aggregation}"
    )

    findings = _aggregation_violations(entries, central)
    assert not findings, (
        "Compare-Eintraege nennen eine Auswertung, die der zentrale Katalog "
        "fuer diese Groesse nicht kennt:\n" + "\n".join(findings)
    )


# ---------------------------------------------------------------------------
# Ausnahmeliste: darf nur schrumpfen -- und wird durch #1391/#1392 leer
# ---------------------------------------------------------------------------


def test_aggregation_check_exemptions_empty_after_1391_1392_fix():
    """AC-4 (#1391/#1392, rot vor Fix): sobald ``metric_catalog.py``
    ``summary_fields`` fuer die Schneefallgrenze und die drei
    Bewoelkungsstufen traegt, braucht keine der vier ausgenommenen Groessen
    mehr die Nachsicht aus ``AGGREGATION_CHECK_EXEMPTIONS`` -- die Liste wird
    leer. Heute (vor dem Fix) enthaelt sie noch alle vier Eintraege."""
    assert AGGREGATION_CHECK_EXEMPTIONS == {}, (
        "AGGREGATION_CHECK_EXEMPTIONS soll nach #1391/#1392 leer sein, "
        f"enthaelt aber noch: {sorted(AGGREGATION_CHECK_EXEMPTIONS)}"
    )


def test_aggregation_exemptions_only_shrink():
    """Die Ausnahmeliste ist eine Uebergangsloesung fuer #1391/#1392 und darf
    nur kleiner werden. Sobald eine ausgenommene Groesse `summary_fields`
    traegt, schlaegt dieser Test fehl -- Aufforderung, den Eintrag zu
    ENTFERNEN, statt die Ausnahme zur Dauereinrichtung werden zu lassen.
    """
    central = _central_selectable()

    stale = sorted(mid for mid in AGGREGATION_CHECK_EXEMPTIONS if mid not in central)
    assert not stale, (
        f"Ausnahmen fuer zentral nicht (mehr) waehlbare Groessen: {stale} -- "
        f"Eintraege aus AGGREGATION_CHECK_EXEMPTIONS entfernen."
    )

    fixed = sorted(
        mid for mid in AGGREGATION_CHECK_EXEMPTIONS if central[mid].summary_fields
    )
    assert not fixed, (
        f"Diese Groessen tragen inzwischen `summary_fields` und brauchen keine "
        f"Ausnahme mehr: {fixed} -- aus AGGREGATION_CHECK_EXEMPTIONS entfernen "
        f"(die Liste darf nur schrumpfen). Begruendungen: "
        + "; ".join(f"{mid}: {AGGREGATION_CHECK_EXEMPTIONS[mid]}" for mid in fixed)
    )


def test_every_exempt_metric_with_an_editorial_choice_is_pinned():
    """F001: eine Ausnahme darf nur den `summary_fields`-Abgleich stilllegen.
    Laesst die zentrale Groesse mehr als eine Auswertung zu (z. B.
    `snowfall_limit`: min/max), ist die Wahl redaktionell und MUSS in
    PINNED_EXEMPT_AGGREGATIONS festgenagelt sein -- sonst bliebe ein
    Bedeutungsfehler unbemerkt. Umgekehrt darf dort nichts stehen, was nicht
    ausgenommen ist (dann greift der strengere summary_fields-Abgleich).
    """
    central = _central_selectable()

    needs_pin = sorted(
        mid
        for mid in AGGREGATION_CHECK_EXEMPTIONS
        if len(central[mid].default_aggregations) > 1
    )
    assert needs_pin == sorted(PINNED_EXEMPT_AGGREGATIONS), (
        f"Festnagelung unvollstaendig oder ueberfluessig: ausgenommene "
        f"Groessen mit mehreren zentralen Auswertungen = {needs_pin}, "
        f"festgenagelt = {sorted(PINNED_EXEMPT_AGGREGATIONS)}"
    )

    for metric_id, (value, _reason) in PINNED_EXEMPT_AGGREGATIONS.items():
        assert value in central[metric_id].default_aggregations, (
            f"Festgenagelte Auswertung {value!r} fuer {metric_id!r} ist zentral "
            f"nicht vorgesehen ({central[metric_id].default_aggregations})"
        )

    # Und der echte Katalog haelt sich daran -- namentlich, nicht nur generisch.
    # Fallstrick (#1391/#1392): sobald die Ausnahme fuer 'snowfall_limit'
    # entfernt wird (Zielzustand), verschwindet der Eintrag auch aus
    # PINNED_EXEMPT_AGGREGATIONS -- ein harter Index wuerde dann bei einem
    # tatsaechlichen Fehlschlag mit KeyError abstuerzen statt die Assertion
    # sauber zu melden. Deshalb `.get()` mit Fallback-Text.
    by_metric_id = {
        e.get("metric_id"): e.get("aggregation") for e in get_compare_metric_catalog()
    }
    _snowfall_pin = PINNED_EXEMPT_AGGREGATIONS.get("snowfall_limit")
    _snowfall_reason = _snowfall_pin[1] if _snowfall_pin else (
        "_compute_snowfall_limit() (src/services/weather_metrics.py) rechnet "
        "das MINIMUM -- 'max' waere ein Bedeutungsfehler."
    )
    assert by_metric_id.get("snowfall_limit") == "min", (
        "Die Schneefallgrenze im Ortsvergleich zeigt "
        f"{by_metric_id.get('snowfall_limit')!r} statt 'min' -- {_snowfall_reason}"
    )


# ---------------------------------------------------------------------------
# Wirkungsnachweise: der Guard muss kuenstlich brechbar sein
# ---------------------------------------------------------------------------


def test_compare_metric_ids_helper_reads_exactly_the_metric_id_field():
    """F002: die gemeinsam genutzte Hilfsfunktion braucht eine EIGENE
    Zusicherung -- sie ist der Nenner von Pruefung (a) und (b). Wird sie leer,
    zu gross oder eingabeblind (z. B. durch einen kuenftigen Refactor, der ein
    Zwischenergebnis zwischenspeichert), muss hier etwas rot werden.
    """
    assert _compare_metric_ids([]) == set(), "leere Eingabe liefert nicht leer"
    handmade = [
        {"key": "a", "metric_id": "temperature"},
        {"key": "b", "metric_id": "wind"},
        {"key": "c", "metric_id": "wind"},  # Duplikat zaehlt einmal
        {"key": "d"},  # kein Feld -> keine Beziehung
        {"key": "e", "metric_id": ""},  # leeres Feld -> keine Beziehung
    ]
    assert _compare_metric_ids(handmade) == {"temperature", "wind"}, (
        f"Hilfsfunktion liest das Feld nicht wie erwartet: "
        f"{sorted(_compare_metric_ids(handmade))}"
    )

    # Gegen die echten Daten: nicht leer, benannte Anker vorhanden, und die
    # Funktion REAGIERT auf ihre Eingabe (sonst ist sie eingabeblind).
    real = _compare_metric_ids()
    assert {"temperature", "wind", "precipitation"} <= real, (
        f"Hilfsfunktion findet Grund-Groessen nicht im echten Katalog: {sorted(real)}"
    )
    reduced_entries = [
        e for e in get_compare_metric_catalog() if e.get("metric_id") != "wind"
    ]
    assert _compare_metric_ids(reduced_entries) == real - {"wind"}, (
        "Hilfsfunktion ignoriert ihre Eingabe -- sie liefert fuer eine um 'wind' "
        "reduzierte Kopie dasselbe wie fuer den vollen Katalog."
    )


def test_guard_actually_fails_when_a_central_metric_has_no_compare_entry():
    """Wirkungsnachweis zu (a), Muster test_compare_metric_catalog_consistency
    .py::test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row:
    DIESELBE Pruef-Funktion wie der Produktions-Guard
    (`_central_metrics_without_compare_entry`, inkl. `_compare_metric_ids()`)
    laeuft gegen eine kuenstlich um eine Groesse reduzierte KOPIE der
    Compare-Eintraege -- keine im Test nachgebaute Mengenarithmetik (F002).
    Der Befund muss die entfernte Groesse NAMENTLICH nennen (AC-1)."""
    central = _central_selectable()
    entries = get_compare_metric_catalog()

    assert not _central_metrics_without_compare_entry(entries, central), (
        "Vorbedingung verletzt: zentraler und Compare-Katalog sind bereits "
        f"inkonsistent ({_central_metrics_without_compare_entry(entries, central)})."
    )

    removed_id = sorted(central)[0]
    reduced_entries = [e for e in entries if e.get("metric_id") != removed_id]
    assert len(reduced_entries) < len(entries), (
        f"Vorbedingung verletzt: kein Compare-Eintrag zu '{removed_id}' entfernt."
    )

    missing = _central_metrics_without_compare_entry(reduced_entries, central)
    assert missing == [removed_id], (
        f"Guard erkennt die kuenstlich entfernte Groesse '{removed_id}' nicht "
        f"als fehlend: missing={missing}"
    )
    # AC-1 verlangt, dass der Fehlertext die fehlende Groesse BENENNT --
    # derselbe Meldungsaufbau wie im Guard oben.
    message = f"Waehlbare zentrale Katalog-Groessen ohne Compare-Eintrag: {missing}"
    assert removed_id in message, (
        f"Fehlertext des Guards nennt die fehlende Groesse nicht: {message}"
    )


def test_aggregation_guard_actually_fails_on_a_wrong_aggregation(monkeypatch):
    """Wirkungsnachweis zu (c): dieselbe Pruef-Funktion laeuft gegen
    kuenstliche Eintraege (Kopien, keine Produktivdaten):
      * korrekte Auswertung -> kein Befund,
      * erfundene Auswertung -> Befund, der Key und Auswertung nennt,
      * ausgenommene Groesse mit zentral vorgesehener Auswertung -> kein
        Befund (die Ausnahme wirkt gezielt auf den summary_fields-Abgleich),
      * ausgenommene Groesse mit erfundener Auswertung -> Befund (die Ausnahme
        stellt NICHT die ganze Pruefung still, F001).

    Fallstrick (#1391/#1392, aus dem Kontext-Dokument): die Ausnahme-Wirkung
    darf NICHT ueber eine Schleife ueber die ECHTE
    ``AGGREGATION_CHECK_EXEMPTIONS`` gepruegft werden -- die wird durch die
    Lieferung zu #1391/#1392 leer, eine solche Schleife liefe dann als
    stiller No-Op durch (0 Iterationen, keine Assertion greift). Stattdessen
    wird hier ein KUENSTLICH EINGESETZTER Ausnahme-Eintrag verwendet
    (Attribut-Rebind via ``monkeypatch``, kein Mock) -- unabhaengig davon, ob
    die reale Liste gerade vier Eintraege oder keinen enthaelt.
    """
    central = _central_selectable()

    assert not _aggregation_violations(
        [{"key": "kunst_ok", "metric_id": "temperature", "aggregation": "max"}], central
    ), "Pruefung (c) meldet eine korrekte Auswertung faelschlich als Befund"

    findings = _aggregation_violations(
        [{"key": "kunst_falsch", "metric_id": "temperature", "aggregation": "erfunden"}],
        central,
    )
    assert len(findings) == 1, (
        f"Pruefung (c) schlaegt bei erfundener Auswertung nicht an: {findings}"
    )
    assert "kunst_falsch" in findings[0] and "erfunden" in findings[0], (
        f"Befund nennt Eintrag und Auswertung nicht: {findings[0]}"
    )

    # Kuenstliche zentrale Groesse mit >1 Auswertungen, OHNE summary_fields --
    # strukturell wie 'snowfall_limit' heute, aber unter eigenem Namen und
    # damit unabhaengig davon, ob 'snowfall_limit' selbst noch ausgenommen ist.
    ghost = replace(central["snowfall_limit"], id="ghost_exempt_1391_1392", summary_fields={})
    central_with_ghost = {**central, ghost.id: ghost}
    assert not ghost.summary_fields and len(ghost.default_aggregations) > 1, (
        "Vorbedingung verletzt: die kuenstliche Groesse ist nicht der Ausnahme-Fall."
    )
    monkeypatch.setattr(
        sys.modules[__name__],
        "AGGREGATION_CHECK_EXEMPTIONS",
        {ghost.id: "test-only kuenstliche Ausnahme"},
    )

    good = ghost.default_aggregations[0]
    assert not _aggregation_violations(
        [{"key": "kunst_ausnahme", "metric_id": ghost.id, "aggregation": good}],
        central_with_ghost,
    ), f"Kuenstliche Ausnahme fuer {ghost.id!r} greift nicht"

    bogus = _aggregation_violations(
        [{"key": "kunst_ausnahme_falsch", "metric_id": ghost.id, "aggregation": "erfunden"}],
        central_with_ghost,
    )
    assert len(bogus) == 1 and "kunst_ausnahme_falsch" in bogus[0], (
        f"Kuenstliche Ausnahme fuer {ghost.id!r} stellt die Plausibilitaet "
        f"der Auswertung komplett still (F001): {bogus}"
    )


def test_undeclared_metric_without_summary_fields_gets_no_leniency():
    """F003-Wirkungsnachweis: eine kuenstliche zentrale Groesse ohne
    `summary_fields`, die NICHT in AGGREGATION_CHECK_EXEMPTIONS steht, darf die
    Nachsicht der vier erklaerten Ausnahmen nicht automatisch erben -- sonst
    rutscht eine kuenftige Katalog-Erweiterung mit falscher Auswertung stumm
    durch (genau die Fehlerklasse, die dieser Guard schliessen soll). Vorher
    blieb dieser Fall in JEDEM Test gruen."""
    central = _central_selectable()
    # Strukturell wie `snowfall_limit` (kein `summary_fields`, zwei zentrale
    # Auswertungen) -- aber unter neuem Namen und damit NICHT erklaert.
    # `summary_fields={}` explizit ueberschrieben: seit #1391 traegt
    # `snowfall_limit` selbst `summary_fields` -- der Geist bleibt damit
    # unabhaengig davon, welchen Zustand die reale Groesse gerade hat.
    ghost = replace(
        central["snowfall_limit"], id="ghost_two_agg", label_de="Geist", summary_fields={},
    )
    assert not ghost.summary_fields and len(ghost.default_aggregations) > 1, (
        "Vorbedingung verletzt: die kuenstliche Groesse ist nicht der F003-Fall."
    )
    assert ghost.id not in AGGREGATION_CHECK_EXEMPTIONS, (
        "Vorbedingung verletzt: die kuenstliche Groesse ist erklaert."
    )
    central = {**central, ghost.id: ghost}

    findings = _aggregation_violations(
        [{"key": "ghost_max_m", "metric_id": ghost.id, "aggregation": "max"}], central
    )
    assert len(findings) == 1, (
        f"Nicht erklaerte Groesse ohne `summary_fields` bekommt weiterhin "
        f"stille Nachsicht: {findings}"
    )
    assert ghost.id in findings[0] and "AGGREGATION_CHECK_EXEMPTIONS" in findings[0], (
        f"Befund benennt Groesse und Abhilfe nicht: {findings[0]}"
    )

    # Gegenprobe: mit derselben Mechanik bleiben die vier ERKLAERTEN Ausnahmen
    # nachsichtig -- die Verschaerfung trifft nur den undeklarierten Fall.
    for exempt_id in AGGREGATION_CHECK_EXEMPTIONS:
        pinned = PINNED_EXEMPT_AGGREGATIONS.get(exempt_id)
        good = pinned[0] if pinned else central[exempt_id].default_aggregations[0]
        assert not _aggregation_violations(
            [{"key": "kunst_erklaert", "metric_id": exempt_id, "aggregation": good}],
            central,
        ), f"Erklaerte Ausnahme {exempt_id!r} verliert ihre Nachsicht."


def test_aggregation_guard_catches_a_flipped_snowfall_limit_on_real_data():
    """Wirkungsnachweis zu F001 am konkreten Fall: eine KOPIE des echten
    Katalogs, in der die Schneefallgrenze von 'min' auf 'max' kippt (beide
    zentral erlaubt, aber 'max' ist ein Bedeutungsfehler -- s.
    weather_metrics.py:848-858), muss von derselben Pruef-Funktion gefangen
    werden, die der Produktions-Guard benutzt. Vorher blieb dieser Fall in
    JEDEM Test gruen."""
    central = _central_selectable()
    flipped = [
        {**e, "aggregation": "max"} if e.get("metric_id") == "snowfall_limit" else e
        for e in get_compare_metric_catalog()
    ]
    assert any(
        e.get("metric_id") == "snowfall_limit" and e.get("aggregation") == "max"
        for e in flipped
    ), "Vorbedingung verletzt: Sabotage-Kopie enthaelt die Schneefallgrenze nicht."

    findings = _aggregation_violations(flipped, central)
    assert len(findings) == 1, (
        f"Gekippte Schneefallgrenze ('max' statt 'min') wird nicht gefangen: {findings}"
    )
    assert "snowfall_limit_m" in findings[0] and "'min'" in findings[0], (
        f"Befund nennt Eintrag und festgenagelte Auswertung nicht: {findings[0]}"
    )
    # Gegenprobe: der unveraenderte echte Katalog erzeugt keinen Befund.
    real_findings = _aggregation_violations(get_compare_metric_catalog(), central)
    assert not real_findings, (
        "Gegenprobe: der echte Katalog erzeugt selbst Befunde:\n"
        + "\n".join(real_findings)
    )
