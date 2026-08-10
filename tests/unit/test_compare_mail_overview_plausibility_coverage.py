"""Stille Pruefluecke der Vergleichs-Mail-Uebersichtstabelle (#1404, AC-3/AC-4).

Der Pflicht-Pruefer des Ortsvergleichs-Mailpfads
(`.claude/hooks/email_spec_validator.py`) kennt in `_OVERVIEW_METRIC_CHECKS`
heute 5 von 27 Zeilen-Beschriftungen. Fuer jede nicht gelistete Zeile springt
`validate_plausibility()`/`validate_format()` per `continue` weiter -- ohne
Fehler, ohne Log. 19 numerisch pruefbare Zeilen laufen dadurch ungeprueft
durch, und die drei Zeilen OHNE Zahlenwert bleiben nur zufaellig unbewertet
(kein Eintrag), nicht als ausgesprochene Entscheidung.

Geprueft wird deshalb WIRKUNG, nicht Bestueckung: eine Zeile gilt erst als
geprueft, wenn ein kaputter Zellwert in ihr auch einen benannten Befund
erzeugt (Muster: `test_compare_metric_catalog_consistency.py::
test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`).

Die Zellwerte der Fixture sind NICHT getippt: sie entstehen durch Aufruf der
ECHTEN Renderer-Formatierer aus `compare_html.py` (`_fmt_metric` bzw. die
zeilen-eigene `fmt`-Funktion), in der Dispatch-Reihenfolge von
`_render_overview_row`. Damit belegt der Gutfall-Test zugleich, dass die
Format-Regex des Pruefers zu dem passt, was der Renderer wirklich ausgibt.

Kern-Schicht: deterministisch, kein Netz, kein IMAP, keine Mocks/`patch()` --
der Pruefling wird echt geladen und ausgefuehrt.

#1453: die Uebergangs-Union aus #1420 (alte deutsche UND englische
A2b-Beschriftungen gleichzeitig gueltig) ist zurueckgebaut -- gueltig ist
allein der ausgeschriebene deutsche Registername. Weil `CV2_ROWS` unten der
ECHTEN Renderer-Ableitung folgt, ziehen die Pruefungen dieser Datei
automatisch auf die neue Form um; festgenagelt wird sie von der exakten
Mengengleichung in `test_ac4_exemption_set_is_declared_and_complete`.

SPEC: docs/specs/modules/fix_1404_validator_spaltennamen.md (AC-3, AC-4)
      docs/specs/modules/fix_1453_namensformen.md (AC-6, Rueckbau)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from output.renderers.email.compare_html import _fmt_metric, _visible_metrics

# #1401 A2b: die Beschriftung steht nicht mehr in `CV2_METRICS`, sie wird aus
# dem zentralen Register abgeleitet. Der Pruefling wird deshalb gegen die
# Beschriftung gefahren, die der Renderer bei ALLEN sichtbaren Zeilen wirklich
# ausgibt (inkl. Auswertungs-Zusatz bei zwei Auswertungen derselben Groesse).
#
# #1453: bewusst ueber die Zeilenquelle der UEBERSICHTSTABELLE
# (`_visible_metrics(None)` = kein Filter, alle Zeilen) statt ueber die
# allgemeine Beschriftungs-Ableitung. Uebersicht (deutsch) und Stundentabelle
# (englisch) tragen seit dieser Lieferung verschiedene Formen -- wer hier die
# allgemeine Ableitung befragt, prueft womoeglich die Form der anderen Tabelle.
CV2_ROWS = _visible_metrics(None)

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "email_spec_validator.py"
)

# Die drei Zeilen ohne Zahlenwert: die Warn-Zeile (gestapelte Warn-Chips) und
# die zwei kategorialen Enum-Zeilen. Fuer sie ist "keine Pruefung" richtig --
# aber es muss ausgesprochen sein, nicht aus einem fehlenden Dict-Eintrag
# folgen (AC-4).
#
# #1453: die Uebergangs-Union ist zurueckgebaut -- die Uebersichtstabelle
# fuehrt genau EINE Namensform (den ausgeschriebenen deutschen Registernamen).
# Die zwei A2b-Gegenformen "Thdr"/"PType" sind damit entfallen; ausgenommen
# bleiben die Warn-Zeile und die zwei kategorialen Enum-Zeilen, deren
# Registername woertlich "Gewitter"/"Niederschlagsart" lautet.
EXEMPT_LABELS = {"Amtliche Warnungen", "Gewitter", "Niederschlagsart"}

NUMERIC_LABELS = [m["label"] for m in CV2_ROWS if m["label"] not in EXEMPT_LABELS]

# Zwei Groessen fuehren zwei waehlbare Auswertungen (Temperatur, Gefuehlte
# Temperatur). `CV2_ROWS` zeigt sie beide gleichzeitig -- dann traegt jede
# Zeile die Auswertungs-Ergaenzung. Waehlt der Nutzer nur EINE Auswertung,
# steht dort der blanke Name; auch der ist eine gueltige Zeilenbeschriftung
# und muss dem Pruefer bekannt sein. Woertlich getippt (Registernamen der
# beiden Groessen), nicht aus dem Pruefling abgeleitet.
KOLLISIONSFREIE_FORMEN = {"Temperatur", "Gefühlte Temperatur"}

# Plausible Rohwerte je Zeilen-Key -- Eingang der echten Formatierer, nicht
# deren Ergebnis (das leitet `_cell_text()` ab).
RAW_VALUES: dict[str, object] = {
    "temp_max": 21.0, "wind_max": 10.0, "precip_sum": 3.4, "pop_max": 80,
    "thunder_max": "MED", "sunny_hours": 5.0, "cloud_avg": 30, "uv_max": 4,
    "visibility_min": 9000, "snow_depth_cm": 12, "snow_new_cm": 5,
    "temp_min": -3, "gust_max": 45, "cape_max": 1200, "freezing_level": 3200,
    "wind_direction_avg": 180, "wind_chill_min": -5, "wind_chill_max": 19,
    "cloud_low_avg": 40, "cloud_mid_avg": 20, "cloud_high_avg": 10,
    "humidity_avg": 65, "dewpoint_avg": 8, "pressure_avg": 1013,
    "precip_type": "RAIN", "snowfall_limit": 1800,
}

LOCATIONS = ("Andermatt", "Kufstein", "Lienz")


@pytest.fixture(scope="module")
def validator():
    """Der echte Pruefer als isoliertes Modul (Muster aus
    `test_compare_mail_validator_column_order.py::_load_validator`)."""
    spec = importlib.util.spec_from_file_location("esv1404", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:  # pragma: no cover - Ladefehler
        pytest.fail(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell_text(m: dict) -> str:
    """Zellinhalt exakt wie `_render_overview_row` (compare_html.py:501):
    zeilen-eigene `fmt`-Funktion, sonst `_fmt_metric(value, decimals, unit)`."""
    if m.get("kind") == "warn":
        return "—"
    raw = RAW_VALUES[m["key"]]
    fmt_fn = m.get("fmt")
    return fmt_fn(raw) if fmt_fn else _fmt_metric(raw, m.get("decimals"), m.get("unit", ""))


def _overview_mail(overrides: dict[str, str] | None = None) -> str:
    """Minimaler Mail-Body mit der Uebersichtstabelle (alle 27 Zeilen von
    `CV2_METRICS`, drei Orte); `overrides` ersetzt den Zellwert einer Zeile.
    Der Pruefer findet die Tabelle allein ueber ihre erste Datenzeile
    "Amtliche Warnungen" (`extract_table_rows`, #1108) -- ORT-Sektionen und
    Stundentabellen braucht er fuer Plausibilitaet/Format nicht."""
    overrides = overrides or {}
    head = "".join(f"<th>{n}</th>" for n in ("Metrik",) + LOCATIONS)
    rows = ""
    for m in CV2_ROWS:
        value = overrides.get(m["label"], _cell_text(m))
        cells = f"<td>{m['label']}</td>" + f"<td>{value}</td>" * len(LOCATIONS)
        rows += f"<tr>{cells}</tr>"
    return (
        "<html><body><div><table><thead><tr>" + head + "</tr></thead>"
        "<tbody>" + rows + "</tbody></table></div></body></html>"
    )


# ---------------------------------------------------------------------------
# Gutfall -- belegt zugleich die Format-Herleitung aus dem Renderer
# ---------------------------------------------------------------------------


def test_renderer_conform_overview_produces_no_findings(validator):
    """GIVEN eine Uebersichtstabelle, deren Zellwerte von den ECHTEN
    Renderer-Formatierern stammen / WHEN Plausibilitaets- und Format-Check
    laufen / THEN meldet der Pruefer nichts. Heute gruen (nur 5 Zeilen
    geprueft) und nach der Erweiterung auf 24 Zeilen ebenso -- genau das ist
    der Nachweis, dass die neuen Format-Regex zu der Ausgabe passen, die der
    Renderer wirklich erzeugt (z. B. "180 °" mit Leerzeichen, "21°C" ohne)."""
    body = _overview_mail()

    assert validator.validate_plausibility(body) == []
    assert validator.validate_format(body) == []


# ---------------------------------------------------------------------------
# AC-3 -- jede numerische Zeile wird wirklich geprueft
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", NUMERIC_LABELS)
def test_ac3_every_numeric_row_is_actually_checked(validator, label):
    """AC-3: GIVEN eine der 24 numerisch pruefbaren Uebersichtszeilen traegt
    einen unbrauchbaren Zellwert / WHEN Plausibilitaets- und Format-Check
    laufen / THEN meldet der Pruefer einen Befund, der genau diese Zeile
    benennt. Vor dieser Lieferung erzeugen 19 der 24 Zeilen keinen Befund --
    sie stehen nicht in `_OVERVIEW_METRIC_CHECKS` und fallen in den stillen
    `continue`-Pfad."""
    body = _overview_mail({label: "kaputt"})

    findings = validator.validate_plausibility(body) + validator.validate_format(body)

    assert findings, (
        f"Zeile '{label}' laeuft ungeprueft durch: ein unbrauchbarer Zellwert "
        f"erzeugt keinen Befund"
    )
    assert all(label in f for f in findings), (
        f"Jeder Befund muss die betroffene Zeile '{label}' benennen: {findings}"
    )


def test_ac3_out_of_range_value_is_reported_per_location(validator):
    """AC-3 (benanntes Beispiel der Spec): GIVEN "Windrichtung" zeigt 450 °,
    also ausserhalb 0-360, in korrektem Format / WHEN der
    Plausibilitaets-Check laeuft / THEN meldet der Pruefer den Wert je Ort --
    und der Format-Check bleibt still, weil nur der Wert unplausibel ist, nicht
    seine Schreibweise."""
    body = _overview_mail({"Windrichtung": _fmt_metric(450, None, "°")})

    findings = validator.validate_plausibility(body)

    assert len(findings) == len(LOCATIONS), (
        f"Erwartet ein Befund je Ort ({len(LOCATIONS)}), bekommen: {findings}"
    )
    assert all("Windrichtung" in f and "450" in f for f in findings), (
        f"Der Befund muss Zeile und Wert benennen: {findings}"
    )
    assert validator.validate_format(body) == [], (
        "'450 °' ist korrekt formatiert -- ein Format-Befund waere falsch"
    )


# ---------------------------------------------------------------------------
# AC-4 -- die drei nicht-numerischen Zeilen sind eine ausgesprochene Ausnahme
# ---------------------------------------------------------------------------


def test_ac4_exemption_set_is_declared_and_complete(validator):
    """AC-4 (Basis) + #1453/AC-6 (Rueckbau): GIVEN die Uebergangs-Union ist
    beendet / WHEN man geprueft und ausgenommen zusammenzaehlt / THEN ergibt
    sich EXAKT die Menge der Beschriftungen, die der Renderer heute erzeugt --
    ueberschneidungsfrei zwischen geprueft und ausgenommen, keine
    zusaetzliche Zweitform.

    Die Gleichung ist bewusst exakt (nicht nur Teilmenge) und traegt damit
    beide Richtungen von #1453/AC-6: die neue Form MUSS drin sein, jede alte
    Form (englische A2b-Kurzform wie "Gust", alte abgekuerzte deutsche Form
    wie "Temp max"/"Sonne") darf NICHT mehr drin sein. Ein Tippfehler, der
    NEBEN einem korrekten Schluessel steht, faellt genauso auf.

    Vorgeschichte: dieser Test war seit #1420 vorbestehend rot -- der Pruefer
    fuehrte die Uebergangs-Union aus alten deutschen UND englischen
    A2b-Formen, der Renderer lieferte nur die englische. #1453 loest genau
    diesen Widerspruch auf; der Test nagelt jetzt den Zielzustand fest."""
    exempt = getattr(validator, "_OVERVIEW_NO_CHECK_LABELS", None)
    assert exempt is not None, (
        "Der Pruefer nennt keine ausgesprochene Ausnahme-Menge "
        "(_OVERVIEW_NO_CHECK_LABELS) -- die drei nicht-numerischen Zeilen "
        "bleiben nur zufaellig unbewertet"
    )
    exempt = set(exempt)
    checked = set(validator._OVERVIEW_METRIC_CHECKS)
    all_labels = {m["label"] for m in CV2_ROWS}

    assert exempt == EXEMPT_LABELS, f"Erwartete Ausnahme-Zeilen: {EXEMPT_LABELS}"
    assert checked.isdisjoint(exempt), (
        f"Eine Zeile kann nicht geprueft UND ausgenommen sein: {checked & exempt}"
    )
    soll = all_labels | KOLLISIONSFREIE_FORMEN
    assert checked | exempt == soll, (
        f"Weder geprueft noch ausgenommen: {sorted(soll - checked - exempt)}; "
        f"Zweitform/unbekannte Beschriftung im Pruefer: "
        f"{sorted((checked | exempt) - soll)}"
    )


@pytest.mark.parametrize(
    # NICHT ueber ganz EXEMPT_LABELS parametrisieren: ein Parametrize-Fall fuer
    # ein Label, das in keiner Zeile von `_overview_mail()` steht, kann gar
    # nicht greifen (der `overrides`-Override findet nie eine passende Zeile)
    # und waere wirkungslos GRUEN. Der Schnitt mit den tatsaechlichen
    # Renderer-Labels haelt den Test an der echten Ausgabe.
    "label", sorted(EXEMPT_LABELS & {m["label"] for m in CV2_ROWS})
)
def test_ac4_exempt_rows_stay_unevaluated(validator, label):
    """AC-4: GIVEN eine der drei nicht-numerischen Zeilen traegt einen Wert,
    der keinem Zahlenformat entspricht / WHEN Plausibilitaets- und
    Format-Check laufen / THEN bleibt sie unbewertet. Erosionsschutz in die
    andere Richtung: wuerde die Warn-Zeile versehentlich mit in
    `_OVERVIEW_METRIC_CHECKS` wandern, meldete JEDE Vergleichsmail einen
    Fehler."""
    body = _overview_mail({label: "kaputt"})

    assert validator.validate_plausibility(body) == []
    assert validator.validate_format(body) == []


# ===========================================================================
# #1453 -- die Uebersichtstabelle fuehrt GENAU EINE Namensform
#          (ausgeschriebener deutscher Registername), AC-6
#
# #1420 hatte hier eine befristete Uebergangs-Union gepflegt: alte deutsche
# UND kuenftige englische A2b-Kurzformen galten gleichzeitig, damit waehrend
# der Umbenennung keine inhaltlich korrekte Mail hart abgelehnt wird. Mit
# #1453 ist die Uebergangszeit beendet -- gueltig ist allein der
# ausgeschriebene deutsche Name aus dem Register, bei zwei gleichzeitig
# sichtbaren Auswertungen derselben Groesse mit deutscher Ergaenzung
# ("Temperatur Maximum"). Die Union-Konstanten (A2B_RENAMED_LABELS,
# COLLISION_LABELS, ZIEL_LABELS_A2B) und die daran haengenden Testfaelle sind
# damit ersatzlos entfallen; die exakte Mengengleichung oben
# (test_ac4_exemption_set_is_declared_and_complete) traegt beide Richtungen.
#
# Was bleibt: der Adversary-gehaertete Bereichsnachweis. "kaputt" faengt nur
# das Format-Regex -- ohne einen formal KORREKT geschriebenen Wert ausserhalb
# des zulaessigen Bereichs waere jeder Wertebereich unbewiesen.
#
# SPEC: docs/specs/modules/fix_1453_namensformen.md (AC-6)
# ===========================================================================


def _overview_mail_from_rows(rows: list[tuple[str, str]]) -> str:
    """Baut eine Uebersichtstabelle direkt aus frei uebergebenen
    (Label, Zellwert)-Paaren, OHNE ueber `CV2_METRICS` zu enumerieren (Spec
    Implementation Details 5). Noetig, weil die A2b-Zielbeschriftungen und
    die Kollisionsformen vor #1401 A2b in keiner echten Renderer-Ausgabe
    vorkommen. Dasselbe Markup-Skelett wie `_overview_mail()`; die erste
    Datenzeile ist immer die Warn-Zeile ("Amtliche Warnungen"), darueber
    findet der Pruefer die Tabelle (`extract_table_rows`, #1108)."""
    head = "".join(f"<th>{n}</th>" for n in ("Metrik",) + LOCATIONS)
    all_rows = [("Amtliche Warnungen", "—")] + list(rows)
    body_rows = ""
    for label, value in all_rows:
        cells = f"<td>{label}</td>" + f"<td>{value}</td>" * len(LOCATIONS)
        body_rows += f"<tr>{cells}</tr>"
    return (
        "<html><body><div><table><thead><tr>" + head + "</tr></thead>"
        "<tbody>" + body_rows + "</tbody></table></div></body></html>"
    )



# ---------------------------------------------------------------------------
# Bereichsnachweis je numerischer Zeile: formal korrekt geschrieben, aber
# ausserhalb des zulaessigen Bereichs (Adversary-Muster aus #1420)
# ---------------------------------------------------------------------------

# Bewusst KEINE Ableitung aus `_OVERVIEW_METRIC_CHECKS` -- eine Ableitung, die
# den Pruefling selbst befragt, macht den Nachweis strukturell wirkungslos:
# verfaelscht man die hinterlegte Obergrenze, verschiebt sich der daraus
# berechnete Testwert mit, und der Test bleibt tautologisch gruen. Die Werte
# sind deshalb woertlich getippt, je knapp oberhalb der Obergrenze, die der
# Pruefer fuer diese Groesse fuehrt (uebernommen aus dem jeweils alten
# Eintrag, #1404/#1420) -- und jeder Wert erfuellt das Format-Regex.
_OUT_OF_RANGE_VALUES: dict[str, str] = {
    "Temperatur Maximum": "70°C",           # Bereich -40..55
    "Temperatur Minimum": "70°C",           # Bereich -40..55
    "Wind": "350 km/h",                     # Bereich 0..250
    "Niederschlag": "350.0 mm",             # Bereich 0..300
    "Regenwahrscheinlichkeit": "150%",      # Bereich 0..100
    "Sonnenstunden": "30.0 h",              # Bereich 0..24
    "Bewölkung": "150%",                    # Bereich 0..100
    "UV-Index": "20",                       # Bereich 0..16
    "Sichtweite": "150.0 km",               # Bereich 0..100
    "Schneehöhe": "1200 cm",                # Bereich 0..1000
    "Neuschnee": "350 cm",                  # Bereich 0..300
    "Böen": "350 km/h",                     # Bereich 0..300
    # Issue #1585: "Gewitterenergie (CAPE)" entfallen -- die Zeile wird nicht
    # mehr gerendert, also gibt es dafuer auch keinen Plausibilitaetsbereich.
    "Nullgradgrenze": "6500 m",             # Bereich 0..6000
    "Windrichtung": "400 °",                # Bereich 0..360
    "Gefühlte Temperatur Minimum": "65°C",  # Bereich -50..50
    "Gefühlte Temperatur Maximum": "70°C",  # Bereich -50..55
    "Tiefe Wolken": "150%",                 # Bereich 0..100
    "Mittelhohe Wolken": "150%",            # Bereich 0..100
    "Hohe Wolken": "150%",                  # Bereich 0..100
    "Luftfeuchtigkeit": "150%",             # Bereich 0..100
    "Taupunkt": "50°C",                     # Bereich -40..35
    "Luftdruck": "1200 hPa",                # Bereich 500..1085
    "Schneefallgrenze": "5500 m",           # Bereich 0..5000
}


@pytest.mark.parametrize("label,value", sorted(_OUT_OF_RANGE_VALUES.items()))
def test_out_of_range_value_is_reported_for_every_numeric_row(validator, label, value):
    """GIVEN eine Uebersichtszeile traegt unter ihrem ausgeschriebenen
    deutschen Namen einen Wert, der das Format-Regex ERFUELLT, aber ausserhalb
    des vorgesehenen Wertebereichs liegt / WHEN Plausibilitaets- und
    Format-Check laufen / THEN meldet `validate_plausibility()` einen Befund,
    der die Zeile benennt, und `validate_format()` bleibt still.

    Deckt zugleich AC-6 (Richtung "neue Form wird wirklich geprueft"): kennt
    der Pruefer die Beschriftung nicht, faellt sie in den stillen
    `continue`-Pfad und dieser Test ist rot."""
    body = _overview_mail_from_rows([(label, value)])

    findings = validator.validate_plausibility(body)

    assert findings, (
        f"Wert '{value}' fuer '{label}' liegt ausserhalb des Wertebereichs, "
        f"wird aber nicht gemeldet -- der Wertebereich ist unbewiesen"
    )
    assert all(label in f for f in findings), (
        f"Der Befund muss die betroffene Zeile '{label}' benennen: {findings}"
    )
    assert validator.validate_format(body) == [], (
        f"Wert '{value}' ist formal korrekt geschrieben -- ein Format-Befund "
        f"waere falsch: {validator.validate_format(body)}"
    )


def test_out_of_range_values_cover_exactly_the_numeric_rows(validator):
    """Erosionsschutz fuer `_OUT_OF_RANGE_VALUES` selbst: die getippte Tabelle
    muss exakt die numerisch pruefbaren Zeilen abdecken, die der Renderer
    erzeugt -- weder mehr (totes Label) noch weniger (eine Zeile liefe ohne
    Bereichsnachweis durch, ohne dass ein Parametrize-Fall das auffinge)."""
    assert set(_OUT_OF_RANGE_VALUES) == set(NUMERIC_LABELS), (
        f"fehlt: {sorted(set(NUMERIC_LABELS) - set(_OUT_OF_RANGE_VALUES))}, "
        f"ueberzaehlig: {sorted(set(_OUT_OF_RANGE_VALUES) - set(NUMERIC_LABELS))}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- echte Fremd-Beschriftung bleibt unbewertet (befristet, s. Known
# Limitations der Spec: faellt mit dem Folge-Ticket "unbekannte Beschriftung
# = lauter Befund" weg)
# ---------------------------------------------------------------------------


def test_ac7_unknown_label_stays_unevaluated(validator):
    """AC-7: GIVEN eine Uebersichtszeile traegt eine Beschriftung, die weder
    zur gueltigen Namensform noch zur Ausnahme-Menge gehoert (Tippfehler,
    z. B. "Mond") / WHEN Plausibilitaets- und Format-Check laufen / THEN
    bleibt diese Zeile unbewertet.

    Regressionsnachweis, kein Wirkungsnachweis: gruen vor UND nach dieser
    Lieferung (der stille `continue`-Pfad existiert unveraendert seit #1404).

    WICHTIG fuer #1453/AC-6: genau deshalb kann die Gegenrichtung "alte
    Uebersichtsform wird ABGELEHNT" verhaltensseitig nicht nachgewiesen
    werden -- eine unbekannte Uebersichtsbeschriftung wird stillschweigend
    uebersprungen, nicht gemeldet. Nachweisbar ist sie nur an der bekannten
    Menge selbst (s. `test_ac4_exemption_set_is_declared_and_complete` und
    `test_compare_validator_single_name_form.py`). Ausdruecklich befristet
    (Known Limitations #1420): faellt mit dem Folge-Ticket "unbekannte
    Beschriftung = lauter Befund" ersatzlos weg."""
    body = _overview_mail_from_rows([("Mond", "kaputt")])

    assert validator.validate_plausibility(body) == []
    assert validator.validate_format(body) == []
