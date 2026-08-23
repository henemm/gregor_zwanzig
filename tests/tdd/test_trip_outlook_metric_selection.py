"""TDD RED — #1720 S1: waehlbare Spalten der 3-Tages-Vorschau (Renderpfad).

SPEC: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
KONTEXT: docs/context/feat-1720-vorschau-metriken.md

Hier: AC-1, AC-4, AC-5, AC-8, AC-9, AC-10, AC-11, AC-14 (Renderer-Ebene),
AC-16 und die Mutations-Gegenproben 1, 2, 3, 4, 6, 7, 9, 10.
AC-2/AC-3/AC-14 (ganze Kette)/AC-15 -> ``test_trip_outlook_dispatch_mail.py``;
AC-12 -> ``test_trip_outlook_metrics_persistence.py``; AC-6/AC-7/AC-13 ->
``frontend/e2e/trip-outlook-metric-selection.staging.spec.ts``.

🔴 Prueforts-Regel: jeder Test treibt ``render_email()`` -- den echten
Aufrufpfad inkl. ``html.py:1357``/``plain.py:338``. Der staerkste vorhandene
Waechter (``test_trip_outlook_parity.py:96,117``) ruft die Renderer DIREKT
auf und bleibt gruen, gleichgueltig ob die neue Verdrahtung stimmt.

🔴 Grenze dieser Datei (fuer den Adversary): die Ausblick-Zeilen baut der
TEST -- mit derselben Auswahl, mit der gerendert wird. Ein Auseinanderlaufen
von Zeilenbau (``build_outlook_row``, Scheduler) und Spaltenbau (Renderer)
kann sie strukturell nicht sehen; dafuer gibt es den Ketten-Test.

RED-Erwartung: AC-1-Legende sagt heute "N Nacht-Tief"; alle uebrigen Tests
scheitern, weil ``UnifiedWeatherDisplayConfig`` kein ``outlook_metrics`` hat.

Kern-Schicht, deterministisch. Kein Mock-Framework, kein Netz.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from tests.helpers.trip_outlook_selection import (  # noqa: E402
    OUTLOOK_EYEBROW, REFERENCE_LEGEND, REFERENCE_PLAIN, REFERENCE_TABLE,
    display_config, html_outlook_body_rows, html_outlook_headers,
    html_outlook_legend, html_outlook_table, outlook_rows, plain_outlook_block,
    render_trip_mail,
)

# Auswahl-Bausteine: reine Kennungen (#1848 A2, vorher Paare aus #1373).
NIEDERSCHLAG = "precipitation"
BOEEN = "gust"
TEMPERATUR = "temperature"
GEWITTER = "thunder"
SCHNEEHOEHE = "snow_depth"
CONFIDENCE = "confidence"
# #2098 AC-13: ACC ist seit der Behebung eine fest angehaengte Zusatzspalte
# HINTER der Auswahl -- ausserhalb des Metrik-Systems, damit ADR-0005/#710
# (Confidence nicht waehlbar) unberuehrt bleibt.
_ACC = "ACC"

# Die EINE dokumentierte Abweichung zwischen Aufzeichnung und Sollstand
# (AC-8 / Implementation Details 5): `temp_lo` ist `summary.temp_min_c`, das
# Tages-Minimum IM WANDERFENSTER -- nicht das naechtliche Tief.
LEGENDE_ALT = "N Nacht-Tief"
LEGENDE_NEU = "N Tagestief"


def _dc_altpfad():
    """Die Vorbedingung des AC-1-Bestandsschutzes: ein Trip, der den FESTEN
    Sieben-Spalten-Ausblick zeigt.

    ⚠️ #1848 A3 (PO-Freigabe 2026-08-21): bis dahin genuegte dafuer ein
    fehlendes ``outlook_metrics`` -- "nie eingestellt" hiess "sieben feste
    Spalten". Seither heisst es "nichts abgewaehlt", und der Ausblick erbt
    die Grundauswahl (Spec "Known Limitations": "Die Ausblick-Tabelle wird
    fuer bestehende Touren breiter"). Der feste Zweig bleibt fuer Touren ganz
    OHNE Grundauswahl in Kraft (ADR-0050 D4) -- genau dort bewacht die
    Aufzeichnung weiter, was sie immer bewacht hat: dass "Feld fehlt" nicht
    mit "bewusst geleert" verwechselt wird und der Block nicht still
    verschwindet.

    Die Referenzdateien werden deshalb NICHT nachgezogen. Sie bleiben Byte
    fuer Byte gueltig -- nur die Vorbedingung ist jetzt ausgesprochen statt
    stillschweigend."""
    return display_config(leere_grundauswahl=True)


# ══════════════════════════ AC-1 — Bestandsschutz ════════════════════════════

def test_ac1_bestandstrip_html_ausblick_bleibt_byte_identisch():
    """AC-1 (HTML): Given ein Trip ohne gesetzte Vorschau-Auswahl / When die
    Mail ueber ``render_email()`` erzeugt wird / Then ist die Ausblick-Tabelle
    byte-identisch zur VOR dieser Lieferung aufgezeichneten Referenz.

    Faengt Mutation 1 (``resolve_outlook_metrics(...) or []``): der Ausblick
    waere fuer 100 % der heutigen Trips still leer.
    """
    html, _ = render_trip_mail(_dc_altpfad(), outlook_rows())
    tabelle = html_outlook_table(html)

    assert tabelle is not None, (
        "Ohne gesetzte Auswahl wurde ueberhaupt keine Ausblick-Tabelle "
        "gerendert -- genau das passiert, wenn 'Feld fehlt' (None) und "
        "'bewusst geleert' ([]) verwechselt werden (AC-1)."
    )
    # Ausnahme #1801 (2026-08-14, PO-freigegeben): die Referenz WURDE hier
    # bewusst nachgezogen -- Grund ist NICHT ein unbeachteter Rotstand,
    # sondern die #1801-Warnstufen-Palette (Ampel-Flaechenfarben). Nachgemessen
    # per Hex-Maskierung (`#[0-9a-fA-F]{6}` -> Platzhalter) in Ist vs.
    # aufgezeichneter Referenz: gleiche Laenge (8717 Zeichen), gleiche Anzahl
    # Farbwerte (86), nach Maskierung ZEICHENGLEICH -- es weichen ausschliesslich
    # drei Flaechenfarben ab (`#fbeeb8`->`#fdf4cd` gelb, `#fad6b8`->`#fbe3cc`
    # orange, `#f6c5bf`->`#f7d3e2` rot), keine Struktur-/Text-/Zahlenaenderung.
    # Der Satz "Die Referenz wird NICHT nachgezogen" bleibt die Regel fuer
    # INHALTLICHE Aenderungen (Mutation 1: stiller Totalausfall der Vorschau);
    # diese eine, gemessene, PO-freigegebene Palettenaenderung ist die einzige
    # dokumentierte Gegenausnahme dazu.
    assert tabelle == REFERENCE_TABLE.read_text(encoding="utf-8"), (
        f"Die HTML-Ausblick-Tabelle weicht von der Aufzeichnung ab "
        f"({REFERENCE_TABLE}). Die Referenz wird NICHT nachgezogen -- rot "
        "heisst, die Trip-Mail hat sich fuer alle Bestandsnutzer geaendert."
    )


def test_ac1_bestandstrip_legende_bleibt_bis_auf_die_ac8_korrektur_identisch():
    """AC-1 (Legende) + AC-8: die Legendenzeile ist byte-identisch zur
    Aufzeichnung, bis auf GENAU EINE dokumentierte Ersetzung
    ``N Nacht-Tief`` -> ``N Tagestief``.

    Ganzzeilen-Vergleich statt Teilstring-Suche: so faellt auch auf, wenn bei
    der Korrektur ein anderes Zeichen mitwandert.
    """
    html, _ = render_trip_mail(_dc_altpfad(), outlook_rows())
    legende = html_outlook_legend(html)

    assert legende is not None, (
        "Der Bestandstrip zeigt keine Legende mehr. Sie darf ausschliesslich "
        "bei AKTIVER Auswahl entfallen (AC-9), nicht im Altbestand."
    )
    aufgezeichnet = REFERENCE_LEGEND.read_text(encoding="utf-8")
    assert LEGENDE_ALT in aufgezeichnet, (
        "Vorbedingung: die Aufzeichnung muss den ALTEN Wortlaut tragen, sonst "
        "prueft dieser Test die Korrektur gegen sich selbst."
    )
    erwartet = aufgezeichnet.replace(LEGENDE_ALT, LEGENDE_NEU)
    assert legende == erwartet, (
        f"Erlaubt ist genau EINE Aenderung: {LEGENDE_ALT!r} -> {LEGENDE_NEU!r} "
        f"(AC-8).\nErwartet: {erwartet!r}\nErhalten: {legende!r}"
    )


def test_ac1_bestandstrip_klartext_ausblick_bleibt_byte_identisch():
    """AC-1 (Klartext): byte-identisch zur Aufzeichnung -- inkl. Ueberschrift,
    26-Zeichen-Namensfeld und Notizzeile.

    Der Klartext-Zweig (``plain.py:309/338``) hat eine EIGENE Bedingung; ein
    Fehler dort faellt im HTML nicht auf.
    """
    _, plain = render_trip_mail(_dc_altpfad(), outlook_rows())
    block = plain_outlook_block(plain)

    assert block is not None, "Der Klartext-Ausblick fehlt vollstaendig (AC-1)."
    erwartet = REFERENCE_PLAIN.read_text(encoding="utf-8")
    assert block == erwartet, (
        f"Klartext-Ausblick weicht von der Aufzeichnung ab "
        f"({REFERENCE_PLAIN}).\nErwartet:\n{erwartet}\nErhalten:\n{block}"
    )


# ═══════════════════ AC-4 — bewusst geleerte Auswahl ═════════════════════════

def test_ac4_leere_auswahl_laesst_den_ganzen_block_entfallen():
    """AC-4: Given ``outlook_metrics = []`` / When die Mail erzeugt wird /
    Then entfaellt der GESAMTE Vorschau-Block in HTML UND Klartext -- weder
    Ueberschrift noch Tabelle, nicht bloss eine leere Tabelle mit
    Wochentag-Spalte.

    Mutation 6: ohne die neue Bedingung ``_outlook_metrics != []`` rendert
    ``render_outlook_table(rows, metrics=[])`` eine Tabelle mit nur der
    Tag-Spalte (outlook.py:148-172).
    """
    dc = display_config(outlook_metrics=[])
    html, plain = render_trip_mail(dc, outlook_rows(metrics=[]))

    assert OUTLOOK_EYEBROW not in html, (
        f"Ueberschrift {OUTLOOK_EYEBROW!r} steht weiterhin in der Mail (AC-4)."
    )
    assert html_outlook_table(html) is None, (
        "Es wird weiterhin eine Ausblick-Tabelle gerendert (vermutlich mit nur "
        "der Wochentag-Spalte) -- genau der Fall, den AC-4 ausschliesst."
    )
    assert plain_outlook_block(plain) is None, (
        "Der Klartext zeigt weiterhin einen Ausblick-Block -- die Bedingung in "
        "plain.py:309 braucht dieselbe Erweiterung wie html.py (AC-4)."
    )


# ══════════════════════ AC-5 — Auswahlreihenfolge ════════════════════════════

def test_ac5_spalten_erscheinen_in_auswahlreihenfolge_im_html():
    """AC-5: Given drei Groessen in bewusst unsortierter Reihenfolge (erst
    Gewitter, dann Temperatur, dann Niederschlag) / When die Mail erzeugt wird
    / Then erscheinen genau diese Spalten in genau dieser Reihenfolge.

    Mutation 4 (Auswahl ueber ein ``set`` statt eine geordnete Liste).
    """
    auswahl = [GEWITTER, TEMPERATUR, NIEDERSCHLAG]
    html, _ = render_trip_mail(display_config(outlook_metrics=auswahl),
                               outlook_rows(metrics=auswahl))

    assert html_outlook_headers(html) == [
        "Tag", "Gewitter", "Temperatur", "Niederschlag", _ACC,
    ], (
        f"Kopfzeile {html_outlook_headers(html)!r} folgt nicht der "
        "Auswahlreihenfolge. Katalog-Reihenfolge waere ['Niederschlag', "
        "'Temperatur', 'Gewitter'], alphabetisch ['Gewitter', 'Niederschlag', "
        "'Temperatur'] -- beide waeren falsch (AC-5)."
    )


def test_ac5_zellwerte_stehen_unter_der_richtigen_spalte():
    """AC-5 (Zuordnung): jede Zelle traegt den Wert IHRER Spalte.

    Ohne diese Pruefung waere ein Spaltenversatz unsichtbar -- die Kopfzeile
    allein sagt nichts ueber die Zahlen darunter.
    """
    auswahl = [GEWITTER, TEMPERATUR, NIEDERSCHLAG]
    html, _ = render_trip_mail(display_config(outlook_metrics=auswahl),
                               outlook_rows(metrics=auswahl))
    zeilen = html_outlook_body_rows(html)

    assert len(zeilen) == 3, f"Erwartet drei Ausblick-Zeilen: {zeilen!r}"
    assert [z[0] for z in zeilen] == ["Mo", "Di", "Mi"], zeilen
    # #1848 A2: die Kennung 'temperature' zeigt Tief UND Hoch in EINER Zelle.
    # Die Zusicherung ist unveraendert -- drei paarweise verschiedene Werte,
    # jeder unter SEINER Spalte; ein Spaltenversatz faellt genauso auf wie
    # vorher, die Zelle traegt jetzt nur beide Tagesenden statt nur des Hochs.
    assert [z[2] for z in zeilen] == ["9/21", "11/19", "6/24"], (
        f"Temperatur-Spalte: {[z[2] for z in zeilen]!r} statt der "
        "Tages-Spannen 9/21, 11/19, 6/24 -- Spaltenversatz (AC-5)."
    )
    assert [z[3] for z in zeilen] == ["2.5 mm", "0.0 mm", "7.1 mm"], (
        f"Niederschlag-Spalte: {[z[3] for z in zeilen]!r} statt der "
        "Tagessummen der drei Fixture-Tage (AC-5)."
    )


def test_ac5_klartext_zeigt_dieselben_groessen_in_derselben_reihenfolge():
    """AC-5/AC-3 auf Renderer-Ebene: der Klartext-Ausblick nennt dieselben
    Groessen in derselben Reihenfolge wie das HTML.

    Mutation 2: wird ``metrics=`` nur an ``render_outlook_table`` uebergeben,
    bleibt der Klartext bei den festen Tokens.
    """
    auswahl = [GEWITTER, TEMPERATUR, NIEDERSCHLAG]
    _, plain = render_trip_mail(display_config(outlook_metrics=auswahl),
                                outlook_rows(metrics=auswahl))
    block = plain_outlook_block(plain)

    assert block is not None, "Kein Klartext-Ausblick trotz aktiver Auswahl."
    zeile = block.splitlines()[1]
    positionen = [zeile.find(l) for l in ("Gewitter", "Temperatur", "Niederschlag")]
    assert all(p >= 0 for p in positionen), (
        f"Klartext nennt die gewaehlten Groessen nicht mit ihren deutschen "
        f"Katalog-Bezeichnungen. Zeile: {zeile!r} (AC-3/AC-5)"
    )
    assert positionen == sorted(positionen), (
        f"Klartext-Reihenfolge weicht von der Auswahl ab: {zeile!r} (AC-5)"
    )


# ══════════════════════════ AC-8 / AC-9 — Legende ════════════════════════════

def test_ac8_legende_nennt_spalte_n_nicht_mehr_als_nachtwert():
    """AC-8: Given ein Trip ohne Auswahl / When der HTML-Teil betrachtet wird /
    Then bezeichnet die Legende die Spalte "N" als Tageswert, nicht als
    "Nacht-Tief" -- die Zahl ist das Tages-Minimum im Wanderfenster.
    """
    html, _ = render_trip_mail(_dc_altpfad(), outlook_rows())
    legende = html_outlook_legend(html)

    assert legende is not None, "Legende fehlt im Altbestand (AC-1/AC-8)."
    assert "Nacht" not in legende, (
        "Die Legende behauptet weiterhin einen Nachtwert fuer 'N'. Gemessen "
        "ist das Tages-Minimum im Wanderfenster (Default 08:00 bis letzte "
        f"Wegpunkt-Ankunft); Nachtdaten fliessen hier nicht ein: {legende!r}"
    )
    assert LEGENDE_NEU in legende, (
        f"Erwartet {LEGENDE_NEU!r} in der Legende, erhalten: {legende!r}"
    )


def test_ac9_aktive_auswahl_zeigt_keine_abkuerzungs_legende_mehr():
    """AC-9: Given ein Trip MIT aktiver Auswahl / When der HTML-Teil betrachtet
    wird / Then erscheint die alte Abkuerzungs-Legende NICHT mehr -- die
    Spaltenkoepfe sind bereits ausgeschriebene deutsche Bezeichnungen.

    Mutation 7: wird die Legende unabhaengig von der Auswahl gebaut, erklaert
    sie Spalten, die gar nicht gezeigt werden (z.B. "R Regen mm").
    """
    auswahl = [BOEEN, NIEDERSCHLAG]
    html, _ = render_trip_mail(display_config(outlook_metrics=auswahl),
                               outlook_rows(metrics=auswahl))

    assert html_outlook_headers(html) == ["Tag", "Böen", "Niederschlag", _ACC], (
        f"Vorbedingung von AC-9: {html_outlook_headers(html)!r}"
    )
    assert html_outlook_legend(html) is None, (
        "Bei aktiver Auswahl steht weiterhin die Abkuerzungs-Legende in der "
        "Mail. Sie beschreibt AUSSCHLIESSLICH die sieben festen Spalten und "
        "passt nicht zur gezeigten Spaltenmenge (AC-9)."
    )


# ═══════════════ AC-10 / AC-11 — Katalog-Quelle und confidence ═══════════════

def test_ac10_pickerkatalog_bietet_keine_vorhersage_genauigkeit_an():
    """AC-10 (a): die Katalogantwort, aus der sich die Auswahl speist
    (``GET /api/compare/metrics``), enthaelt keinen ``confidence``-Eintrag --
    PO-Entscheid #710.

    Mutation 3: laedt der Picker den ungefilterten Registry-Katalog, wird
    ``confidence`` waehlbar.
    """
    from api.routers.compare import get_compare_metrics

    angeboten = get_compare_metrics()["metrics"]
    assert angeboten, "Leerer Picker-Katalog -- der Test bewachte nichts."
    assert "confidence" not in {e["metric_id"] for e in angeboten}, (
        "Der Katalog bietet 'confidence' (die ACC-Spalte) als waehlbare "
        "Groesse an -- PO-Entscheid #710: nie pro Spalte waehlbar (AC-10)."
    )


def test_ac10_manipulierte_confidence_auswahl_wird_beim_rendern_verworfen(caplog):
    """AC-10 (b): Given ein manipulierter Speicher-Aufruf legt
    ``metric_id: "confidence"`` neben eine gueltige Groesse / When gerendert
    wird / Then erscheint dafuer keine Spalte, die uebrige Auswahl bleibt, und
    die Verwerfung wird protokolliert.

    Geprueft wird die WIRKUNG, nicht die Implementierung -- gleichgueltig ob
    das ``selectable``-Gate (#1585) oder der Resolver den Eintrag faellt.
    """
    auswahl = [CONFIDENCE, NIEDERSCHLAG]
    with caplog.at_level(logging.WARNING):
        html, plain = render_trip_mail(display_config(outlook_metrics=auswahl),
                                       outlook_rows(metrics=auswahl))

    # #2098: ACC steht seit der Behebung als fest angehaengte Zusatzspalte
    # hinter der Auswahl (ausserhalb des Metrik-Systems, #710 unberuehrt).
    # Massstab ist deshalb der Renderlauf OHNE den manipulierten Eintrag --
    # abgeleitet statt im Test abgeschrieben: der manipulierte Eintrag darf
    # die Kopfzeile ueberhaupt nicht veraendern.
    kopf = html_outlook_headers(html)
    ohne_manipulation = html_outlook_headers(
        render_trip_mail(display_config(outlook_metrics=[NIEDERSCHLAG]),
                         outlook_rows(metrics=[NIEDERSCHLAG]))[0]
    )
    assert kopf == ohne_manipulation, (
        f"Der manipulierte 'confidence'-Eintrag hat eine Spalte erzeugt: "
        f"{kopf!r} statt {ohne_manipulation!r}. Er muss beim Rendern "
        "serverseitig verworfen werden (AC-10)."
    )
    from app.metric_catalog import get_metric
    confidence_label = get_metric(CONFIDENCE).label_de
    assert confidence_label not in kopf, (
        f"Die Kopfzeile traegt die Katalog-Beschriftung von 'confidence' "
        f"({confidence_label!r}) -- der Eintrag ist als waehlbare Spalte "
        f"durchgeschlagen: {kopf!r} (AC-10/#710)."
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Prognose" not in block, (
        f"Der Klartext nennt die verworfene Groesse: {block!r}"
    )
    assert any("confidence" in r.message.lower() or "confidence" in str(r.args).lower()
               for r in caplog.records), (
        "Die Verwerfung wurde nicht protokolliert -- sie muss sichtbar sein, "
        "nicht still (AC-10, compare_outlook_metric_ids.py:70-74)."
    )


def test_ac11_jede_angebotene_groesse_erscheint_auch_als_spalte():
    """AC-11: Given der Picker bietet die Groessen aus
    ``get_compare_metric_catalog()`` an und der Trip hat sie alle in der
    Grundauswahl / When alle gewaehlt und gerendert werden / Then erscheint
    jede als Spalte -- keine Differenz in beide Richtungen.

    Das Soll wird aus dem Katalog GERECHNET (``tests/helpers/outlook_columns``),
    nicht aus ``outlook_columns()`` uebernommen -- sonst waeren Massstab und
    Prueflig dieselbe Funktion.
    """
    from tests.helpers.outlook_columns import (
        OUTLOOK_SOLL_MINDESTGROESSE, compare_outlook_soll_spalten,
    )

    soll = compare_outlook_soll_spalten()
    assert len(soll) >= OUTLOOK_SOLL_MINDESTGROESSE, (
        f"Nur {len(soll)} Soll-Spalten -- Vakuum-Schutz: ein Waechter ueber "
        "einer geschrumpften Menge ist immer gruen."
    )
    # #1848 A1: min+max derselben Groesse ergeben EINEN Soll-Eintrag mit
    # ZWEI Paaren (``paare``) -- die AUSWAHL (was der Picker an den
    # Renderer schickt) bleibt die FLACHE Paar-Menge, nur die Zahl der
    # daraus entstehenden SPALTEN (``soll``) sinkt.
    auswahl = [p for e in soll for p in e["paare"]]
    dc = display_config(enabled_ids={e["metric_id"] for e in soll},
                        outlook_metrics=auswahl)
    kopf = html_outlook_headers(render_trip_mail(dc, outlook_rows(metrics=auswahl))[0])

    # RED-Korrektur (#1720 S1, GREEN-Phase): Massstab ist ``ueberschrift``,
    # nicht ``label``. Der Helfer RECHNET genau dafuer beide Felder aus
    # (outlook_columns.py:63-71): bei mehrfach vorkommendem Namen haengt die
    # Auswertung an ("Temperatur Maximum") -- PO-Vorgabe 2026-07-27, keine
    # zwei gleich beschrifteten Spalten. Gegen ``label`` verglichen forderte
    # der Test dreimal "Temperatur" und damit das Gegenteil der Vorgabe.
    # #2098: die fest angehaengte ACC-Zusatzspalte steht HINTER der Auswahl
    # und stammt nicht aus dem Picker-Katalog (#710) -- sie gehoert deshalb
    # zur Erwartung, nicht zum Soll aus dem Katalog.
    assert kopf[1:] == [e["ueberschrift"] for e in soll] + [_ACC], (
        "Gerenderte Spalten weichen von den im Picker angebotenen Groessen ab. "
        f"Fehlend: {[e['ueberschrift'] for e in soll if e['ueberschrift'] not in kopf]!r} "
        f"(AC-11)"
    )


# ═══════ AC-14 / AC-16 — Schnitt gegen die Grundauswahl (Renderer-Ebene) ═════

def test_ac14_nicht_grundausgewaehlte_groesse_erscheint_in_keinem_teil():
    """AC-14 (Renderer-Ebene): Given "Schneehoehe" ist in der Grundauswahl
    NICHT aktiv, landet aber ueber einen manipulierten Speicher-Aufruf in der
    Vorschau-Auswahl / When gerendert wird / Then erscheint dafuer weder im
    HTML- noch im Klartext-Teil eine Spalte.

    Mutation 8 (die wichtigste): ein Schnitt nur im Frontend zeigt dem Nutzer
    das richtige Verhalten, waehrend die Mail es nicht einhaelt.
    """
    dc = display_config(enabled_ids={"precipitation"},
                        outlook_metrics=[NIEDERSCHLAG, SCHNEEHOEHE])
    # Zeilen wie ein korrekt schneidender Scheduler sie baut (s. Dateikopf).
    html, plain = render_trip_mail(dc, outlook_rows(metrics=[NIEDERSCHLAG]))

    assert html_outlook_headers(html) == ["Tag", "Niederschlag", _ACC], (
        f"Kopfzeile {html_outlook_headers(html)!r}: eine Groesse ausserhalb "
        "der Grundauswahl erscheint. Die Vorschau darf nur abwaehlen, nie "
        "hinzufuegen (AC-14)."
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Schneehöhe" not in block, (
        f"Der Klartext-Zweig (plain.py:338) schneidet nicht:\n{block}\n(AC-14)"
    )


def test_ac14_abend_abwahl_schneidet_die_vorschau_ebenfalls():
    """Mutation 9 (Quelle des Schnitts): Given "Böen" ist global aktiv, aber
    fuer den Abendbericht abgewaehlt (``evening_enabled=False``, ADR-0050
    Regel 3) / When die Abend-Mail gerendert wird / Then erscheint keine
    Böen-Spalte.

    Wer gegen rohe ``enabled``-Flags statt gegen
    ``get_metrics_for_report_type(report_type)`` schneidet, wird hier rot --
    und verliert zugleich das ``selectable``-Gate (#1585) im Schnitt (D2).
    """
    dc = display_config(enabled_ids={"precipitation", "gust"},
                        report_overrides={"gust": {"evening_enabled": False}},
                        outlook_metrics=[NIEDERSCHLAG, BOEEN])
    html, _ = render_trip_mail(dc, outlook_rows(metrics=[NIEDERSCHLAG]),
                               report_type="evening")

    assert "Böen" not in html_outlook_headers(html), (
        f"Kopfzeile {html_outlook_headers(html)!r}: eine fuer den Abendbericht "
        "abgewaehlte Groesse erscheint in der Abend-Vorschau."
    )


def test_ac16_leere_grundauswahl_schneidet_die_vorschau_nicht():
    """AC-16: Given ``display_config.metrics == []`` (Altbestand ohne
    Grundauswahl) / When eine Vorschau-Auswahl gesetzt ist / Then wird sie
    vollstaendig gezeigt und NICHT gegen eine leere Menge geschnitten.

    Mutation 10, der naheliegendste Fehler beim Nachbilden von
    ``_clip_to_global_maximum()`` (Regel D4, models.py:913-914).
    """
    auswahl = [NIEDERSCHLAG, BOEEN, SCHNEEHOEHE]
    dc = display_config(leere_grundauswahl=True, outlook_metrics=auswahl)
    html, plain = render_trip_mail(dc, outlook_rows(metrics=auswahl))

    assert html_outlook_headers(html) == [
        "Tag", "Niederschlag", "Böen", "Schneehöhe", _ACC,
    ], (
        f"Kopfzeile {html_outlook_headers(html)!r}: bei leerer Grundauswahl "
        "wurde geschnitten. D4: kein Maximum definiert -> nicht schneiden, "
        "sonst Totalausfall fuer jeden Altbestand (AC-16)."
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Schneehöhe" in block, (
        f"Auch der Klartext muss alle drei Groessen zeigen:\n{block}\n(AC-16)"
    )
