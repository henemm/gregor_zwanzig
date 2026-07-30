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

SPEC: docs/specs/modules/fix_1404_validator_spaltennamen.md (AC-3, AC-4)
"""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

from output.renderers.email.compare_html import (
    CV2_METRICS, _fmt_metric, derive_row_labels,
)

# #1401 A2b: die Beschriftung steht nicht mehr in `CV2_METRICS`, sie wird aus
# dem zentralen Register abgeleitet. Der Pruefling wird deshalb gegen die
# Beschriftung gefahren, die der Renderer bei sichtbaren ALLEN Zeilen wirklich
# ausgibt (inkl. Kollisions-Zusatz "Temp max"/"Feels min").
CV2_ROWS = derive_row_labels(CV2_METRICS)

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "email_spec_validator.py"
)

# Die drei Zeilen ohne Zahlenwert: die Warn-Zeile (gestapelte Warn-Chips) und
# die zwei kategorialen Enum-Zeilen. Fuer sie ist "keine Pruefung" richtig --
# aber es muss ausgesprochen sein, nicht aus einem fehlenden Dict-Eintrag
# folgen (AC-4).
#
# #1420/AC-5: "Thdr"/"PType" sind die A2b-Gegenformen von "Gewitter"/
# "Niederschlagsart" -- separat benannt (_NEW_EXEMPT_LABELS_A2B), damit der
# Ursprung sichtbar bleibt, auch wenn EXEMPT_LABELS additiv waechst.
_NEW_EXEMPT_LABELS_A2B = {"Thdr", "PType"}
EXEMPT_LABELS = {"Amtliche Warnungen", "Gewitter", "Niederschlagsart"} | _NEW_EXEMPT_LABELS_A2B

NUMERIC_LABELS = [m["label"] for m in CV2_ROWS if m["label"] not in EXEMPT_LABELS]

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
    body = _overview_mail({"WDir": _fmt_metric(450, None, "°")})

    findings = validator.validate_plausibility(body)

    assert len(findings) == len(LOCATIONS), (
        f"Erwartet ein Befund je Ort ({len(LOCATIONS)}), bekommen: {findings}"
    )
    assert all("WDir" in f and "450" in f for f in findings), (
        f"Der Befund muss Zeile und Wert benennen: {findings}"
    )
    assert validator.validate_format(body) == [], (
        "'450 °' ist korrekt formatiert -- ein Format-Befund waere falsch"
    )


# ---------------------------------------------------------------------------
# AC-4 -- die drei nicht-numerischen Zeilen sind eine ausgesprochene Ausnahme
# ---------------------------------------------------------------------------


def test_ac4_exemption_set_is_declared_and_complete(validator):
    """AC-4 (Basis) + AC-5 (#1420): GIVEN `_OVERVIEW_METRIC_CHECKS`/
    `_OVERVIEW_NO_CHECK_LABELS` sind jetzt eine auf Alt+Neu erweiterte
    Uebergangs-Union / WHEN man geprueft und ausgenommen zusammenzaehlt / THEN
    ergibt sich exakt die erweiterte Soll-Menge: die 27 heutigen
    `CV2_METRICS`-Zeilen VEREINIGT mit den 24 A2b-Zielbeschriftungen
    (`ZIEL_LABELS_A2B`), ueberschneidungsfrei zwischen geprueft und
    ausgenommen. Die Gleichung bleibt exakt (nicht nur Teilmenge) -- ein
    Tippfehler, der NEBEN einem korrekten neuen Schluessel steht (z. B.
    "Gsut" neben "Gust"), muss auffallen (Spec: Implementation Details 4,
    "Der heikelste Punkt"). Vor #1420 (nur die alten 27 Zeilen) ist dieser
    Test rot, weil die rechte Seite (`all_labels | ZIEL_LABELS_A2B`) 24
    Labels enthaelt, die im heutigen Pruefer weder geprueft noch ausgenommen
    sind."""
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
    soll = all_labels | ZIEL_LABELS_A2B
    assert checked | exempt == soll, (
        f"Weder geprueft noch ausgenommen: {sorted(soll - checked - exempt)}; "
        f"unbekannte Beschriftung im Pruefer: {sorted((checked | exempt) - soll)}"
    )


@pytest.mark.parametrize(
    # #1420-Korrektur: NICHT ueber ganz EXEMPT_LABELS parametrisieren. Von den
    # 5 Ausnahme-Labels kommen heute nur die alten 3 in einer echten
    # `CV2_METRICS`-Zeile vor -- "Thdr"/"PType" existieren erst nach #1401
    # A2b im Renderer. Ein Parametrize-Fall fuer ein Label, das in keiner
    # Zeile von `_overview_mail()` steht, kann gar nicht greifen (der
    # `overrides`-Override in `_overview_mail()` findet nie eine passende
    # Zeile) und waere damit wirkungslos GRUEN, ohne etwas zu pruefen. Der
    # Schnitt mit den tatsaechlichen `CV2_METRICS`-Labels haelt den Test an
    # der echten Renderer-Ausgabe: heute die alten 3, nach A2b automatisch
    # "Thdr"/"PType" -- ohne dass dieser Test dafuer nochmal angefasst werden
    # muss.
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
# #1420 -- Uebergangs-Union der Uebersichtstabellen-Beschriftungen
#          (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7)
#
# #1401 Scheibe A2b stellt alle 26 Metrik-Zeilen der Uebersichtstabelle auf
# die englische Kurzform aus dem zentralen Namensregister um. Ohne
# Vorarbeit wuerden 24 der 24 Plausibilitaets-/Format-Pruefungen mit A2b
# sofort wieder lautlos in den stillen `continue`-Pfad zurueckfallen --
# dieselbe Luecke, die #1404 gerade erst fuer die Stundentabelle geschlossen
# hat, nur diesmal fuer die Uebersichtstabelle.
#
# SPEC: docs/specs/modules/fix_1420_validator_uebersichtslabels.md
# ===========================================================================

# Ziel-Beschriftung je Zeile (aus `fix_1401_a2_mailtabellen.md`,
# PO-freigegeben 2026-07-28, hier uebernommen aus
# `fix_1420_validator_uebersichtslabels.md`, "Ziel-Abbildung"). Regex/Bereich
# unveraendert vom jeweils alten Eintrag uebernommen -- die Werte hier sind
# NICHT die Zellwerte, sondern plausible, renderer-typisch formatierte
# Beispielwerte je NEUER Beschriftung (die Zeile existiert vor #1401 A2b in
# keiner echten Renderer-Ausgabe, s. Spec Implementation Details 5).
A2B_RENAMED_LABELS: dict[str, str] = {
    "Sun": "5.0 h",
    "Cloud": "30%",
    "UV": "4",
    "Rain": "3.4 mm",
    "Rain%": "80%",
    "Visib": "9.0 km",
    "SnowH": "12 cm",
    "NewSn": "5 cm",
    "Gust": "45 km/h",
    "0°Line": "3200 m",
    "WDir": "180 °",
    "Feels min": "-5°C",
    "Feels max": "19°C",
    "CldLow": "40%",
    "CldMid": "20%",
    "CldHi": "10%",
    "Humid": "65%",
    "Cond°": "8°C",
    "hPa": "1013 hPa",
    "SnowL": "1800 m",
}

# Kollisionsvarianten (Spec, "Der heikelste Punkt" 1.): A2b haengt den
# Auswertungs-Zusatz nur an, wenn zwei Zeilen mit demselben `col_label`
# gleichzeitig sichtbar sind. Ist nur eine Auswertung gewaehlt, heisst die
# Zeile "Temp" bzw. "Feels" -- ohne Zusatz.
COLLISION_LABELS: dict[str, str] = {"Temp": "21°C", "Feels": "19°C"}

# `ZIEL_LABELS_A2B` (Testkonstante, AC-5/Implementation Details 4): die 20
# Umbenennungen + 2 Kollisionsformen (22 Pruef-Labels) plus die 2 neuen
# Ausnahme-Labels "Thdr"/"PType" -- zusammen genau die 24 Labels, die mit
# #1420 neu in die Union von `_OVERVIEW_METRIC_CHECKS`/
# `_OVERVIEW_NO_CHECK_LABELS` wandern. Quelle: `fix_1401_a2_mailtabellen.md`.
ZIEL_LABELS_A2B: set[str] = (
    set(A2B_RENAMED_LABELS) | set(COLLISION_LABELS) | _NEW_EXEMPT_LABELS_A2B
)


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
# AC-1/AC-2 -- die 20 A2b-Kurzbeschriftungen werden schon vor A2b geprueft
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,plausible_value", sorted(A2B_RENAMED_LABELS.items()))
def test_ac1_ac2_a2b_renamed_label_is_actually_checked(validator, label, plausible_value):
    """AC-1: GIVEN eine Uebersichtstabellen-Zeile traegt eine der 20
    kuenftigen A2b-Kurzbeschriftungen mit einem renderer-typisch
    formatierten, plausiblen Wert / WHEN Plausibilitaets- und Format-Check
    laufen / THEN meldet der Pruefer keinen Befund -- die Pruefung wirkt
    bereits, bevor #1401 A2b selbst ausgeliefert ist.

    AC-2: GIVEN dieselbe Beschriftung traegt stattdessen einen kaputten Wert
    / WHEN dieselben Pruefungen laufen / THEN meldet der Pruefer einen
    Befund, der genau diese Zeile benennt -- keine der 20 neuen Zeilen faellt
    durch den stillen `continue`-Pfad, obwohl sie in der echten
    Renderer-Ausgabe heute noch gar nicht vorkommt."""
    good_body = _overview_mail_from_rows([(label, plausible_value)])
    assert validator.validate_plausibility(good_body) == [], (
        f"Plausibler Wert '{plausible_value}' fuer '{label}' darf keinen "
        f"Plausibilitaets-Befund erzeugen"
    )
    assert validator.validate_format(good_body) == [], (
        f"Plausibler Wert '{plausible_value}' fuer '{label}' darf keinen "
        f"Format-Befund erzeugen"
    )

    broken_body = _overview_mail_from_rows([(label, "kaputt")])
    findings = (
        validator.validate_plausibility(broken_body) + validator.validate_format(broken_body)
    )
    assert findings, (
        f"Zeile '{label}' laeuft ungeprueft durch: ein unbrauchbarer Zellwert "
        f"erzeugt keinen Befund"
    )
    assert all(label in f for f in findings), (
        f"Jeder Befund muss die betroffene Zeile '{label}' benennen: {findings}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- Kollisionsformen "Temp"/"Feels" ohne Auswertungs-Zusatz
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,plausible_value", sorted(COLLISION_LABELS.items()))
def test_ac3_collision_label_without_suffix_is_actually_checked(validator, label, plausible_value):
    """AC-3: GIVEN eine der beiden Kollisionsformen "Temp"/"Feels" (ohne
    Auswertungs-Zusatz), die A2b genau dann zeigt, wenn nur eine der beiden
    moeglichen Auswertungen gleichzeitig sichtbar ist / WHEN ein kaputter
    Wert in dieser Zeile steht / THEN meldet der Pruefer einen benannten
    Befund fuer genau diese Zeile. Ein plausibler Wert bleibt unbeanstandet."""
    good_body = _overview_mail_from_rows([(label, plausible_value)])
    assert validator.validate_plausibility(good_body) == []
    assert validator.validate_format(good_body) == []

    broken_body = _overview_mail_from_rows([(label, "kaputt")])
    findings = (
        validator.validate_plausibility(broken_body) + validator.validate_format(broken_body)
    )
    assert findings, f"Kollisionsform '{label}' laeuft ungeprueft durch"
    assert all(label in f for f in findings), (
        f"Jeder Befund muss die betroffene Zeile '{label}' benennen: {findings}"
    )


# ---------------------------------------------------------------------------
# AC-2 (Nachtrag, Adversary-Befund) -- unplausibler, aber KORREKT
# formatierter Wert je neuem Pruef-Eintrag
#
# `test_ac1_ac2_a2b_renamed_label_is_actually_checked` oben prueft den
# Fehlerfall nur mit dem Zellwert "kaputt" -- ein FORMATFEHLER, den der Regex
# abfaengt, BEVOR die Bereichspruefung ueberhaupt greift. Die Wertebereiche
# aller 22 neuen Eintraege (20 Umbenennungen + die 2 Kollisionsformen
# "Temp"/"Feels") sind damit unbewiesen: AC-2 verlangt "einen unplausiblen
# ODER falsch formatierten Wert" -- nur die zweite Haelfte war belegt.
# Vorbild fuer "formal korrekt, aber ausserhalb des Bereichs":
# `test_ac3_out_of_range_value_is_reported_per_location` ("Windrichtung" mit
# 450 Grad bei zulaessigen 0-360).
# ---------------------------------------------------------------------------

# Bewusst KEINE Ableitung aus `_OVERVIEW_METRIC_CHECKS` (auch nicht ueber eine
# andere Zeile desselben Dicts) -- eine Ableitung, die den Pruefling selbst
# befragt, macht den Nachweis strukturell wirkungslos: verfaelscht man die
# vom Pruefling hinterlegte Obergrenze, verschiebt sich der daraus berechnete
# Testwert automatisch mit, und der Test bleibt tautologisch gruen ("Zahl
# groesser als die (verfaelschte) Obergrenze" ist immer wahr). Belegt durch
# eine echte Gegenprobe: `_OVERVIEW_METRIC_CHECKS["Gust"]`-Bereich auf
# (0, 999999) gesetzt, Testlauf blieb 76/76 gruen.
#
# Die Werte hier sind deshalb WOERTLICH aus der Spec abgetippt
# (`fix_1420_validator_uebersichtslabels.md`, Tabellen "Ziel-Abbildung" und
# "Kollisionsvarianten") -- eine zweite, vom Code komplett unabhaengige
# Quelle. Jeder Wert ist knapp oberhalb der dort dokumentierten Obergrenze
# und erfuellt zugleich das dort dokumentierte Format-Regex.
_OUT_OF_RANGE_VALUES: dict[str, str] = {
    "Sun": "30.0 h",         # Spec: 0-24
    "Cloud": "150%",         # Spec: 0-100
    "UV": "20",              # Spec: 0-16
    "Rain": "350.0 mm",      # Spec: 0-300
    "Rain%": "150%",         # Spec: 0-100
    "Visib": "150.0 km",     # Spec: 0-100
    "SnowH": "1200 cm",      # Spec: 0-1000
    "NewSn": "350 cm",       # Spec: 0-300
    "Gust": "350 km/h",      # Spec: 0-300
    "0°Line": "6500 m",      # Spec: 0-6000
    "WDir": "400 °",         # Spec: 0-360
    "Feels min": "65°C",     # Spec: -50-50
    "Feels max": "70°C",     # Spec: -50-55
    "CldLow": "150%",        # Spec: 0-100
    "CldMid": "150%",        # Spec: 0-100
    "CldHi": "150%",         # Spec: 0-100
    "Humid": "150%",         # Spec: 0-100
    "Cond°": "50°C",         # Spec: -40-35
    "hPa": "1200 hPa",       # Spec: 500-1085
    "SnowL": "5500 m",       # Spec: 0-5000
    "Temp": "70°C",          # Spec-Kollisionsvariante: -40-55
    "Feels": "70°C",         # Spec-Kollisionsvariante: -50-55
}


@pytest.mark.parametrize(
    "label", sorted(set(A2B_RENAMED_LABELS) | set(COLLISION_LABELS))
)
def test_ac2_a2b_label_out_of_range_value_is_actually_checked(validator, label):
    """AC-2 (zweite Haelfte, Adversary-Befund): GIVEN eine der 22 neuen
    Pruef-Eintraege (20 Umbenennungen + Kollisionsformen "Temp"/"Feels")
    traegt einen Wert, der das Format-Regex ERFUELLT (kein Formatfehler),
    aber laut Spec AUSSERHALB des vorgesehenen Wertebereichs liegt / WHEN
    Plausibilitaets- und Format-Check laufen / THEN meldet
    `validate_plausibility()` einen Befund, der die Zeile benennt, und
    `validate_format()` bleibt still -- exakt das Muster von
    'Windrichtung'/450° oben, jetzt fuer jeden der 22 neuen Eintraege.

    Der Testwert stammt aus `_OUT_OF_RANGE_VALUES` (Spec-Abschrift), NICHT
    aus dem Pruefling -- sonst waere der Test gegen eine Verfaelschung der
    Bereichsgrenze blind (s. Kommentar dort)."""
    value = _OUT_OF_RANGE_VALUES[label]

    body = _overview_mail_from_rows([(label, value)])

    plausibility_findings = validator.validate_plausibility(body)
    assert plausibility_findings, (
        f"Wert '{value}' fuer '{label}' liegt laut Spec ausserhalb des "
        f"Wertebereichs, wird aber nicht gemeldet -- der Wertebereich ist "
        f"unbewiesen"
    )
    assert all(label in f for f in plausibility_findings), (
        f"Der Befund muss die betroffene Zeile '{label}' benennen: "
        f"{plausibility_findings}"
    )
    assert validator.validate_format(body) == [], (
        f"Wert '{value}' ist formal korrekt geschrieben -- ein Format-Befund "
        f"waere falsch: {validator.validate_format(body)}"
    )


def test_ac2_out_of_range_values_cover_exactly_the_22_new_check_entries(validator):
    """Erosionsschutz fuer `_OUT_OF_RANGE_VALUES` selbst: die hinterlegte
    Spec-Abschrift muss exakt die 22 neuen Pruef-Labels abdecken (20
    Umbenennungen + 2 Kollisionsformen) -- weder mehr (totes Label) noch
    weniger (ein neues Label liefe ungeprueft durch, ohne dass ein
    Parametrize-Fall das auffangen wuerde)."""
    expected = set(A2B_RENAMED_LABELS) | set(COLLISION_LABELS)
    assert set(_OUT_OF_RANGE_VALUES) == expected, (
        f"_OUT_OF_RANGE_VALUES weicht von den 22 neuen Pruef-Labels ab: "
        f"fehlt {expected - set(_OUT_OF_RANGE_VALUES)}, ueberzaehlig "
        f"{set(_OUT_OF_RANGE_VALUES) - expected}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- Uebergangs-Union traegt ein Pruefdatum ohne Verhaltenszweig
# ---------------------------------------------------------------------------


def test_ac6_transition_union_carries_a_review_date(validator):
    """AC-6: GIVEN die Uebergangs-Union der Uebersichtstabellen-
    Beschriftungen ist eine bewusst befristete Zwischenloesung (Muster
    `_HOUR_COLUMNS_V2`, #1404) / WHEN das Validator-Modul geladen wird /
    THEN traegt es ein maschinenlesbares Pruefdatum, das innerhalb der
    projektueblichen 90-Tage-Spanne ab `created` (2026-07-29) liegt und KEIN
    Verhalten umschaltet (Vorbild:
    `test_1404_ac5_transition_union_carries_a_review_date`)."""
    spec_created = date(2026, 7, 29)

    review = None
    for name in (
        "_OVERVIEW_METRIC_CHECKS_REVIEW_DATE", "_OVERVIEW_METRIC_CHECKS_EXPIRY",
        "_OVERVIEW_METRIC_CHECKS_PRUEFDATUM",
    ):
        review = getattr(validator, name, None)
        if review is not None:
            break
    assert review is not None, (
        "Der Pruefer nennt kein Pruefdatum fuer die Uebersichtstabellen-"
        "Uebergangs-Union (erwartet z. B. _OVERVIEW_METRIC_CHECKS_REVIEW_DATE) "
        "-- die Uebergangsregelung wuerde stillschweigend fuer immer gelten"
    )
    if isinstance(review, str):
        review = date.fromisoformat(review)
    assert isinstance(review, date), f"Pruefdatum muss ein Datum sein, ist: {review!r}"
    assert spec_created < review <= spec_created + timedelta(days=90), (
        f"Pruefdatum {review} liegt ausserhalb der projektueblichen 90-Tage-Spanne "
        f"ab {spec_created} (Regel-Budget)"
    )


# ---------------------------------------------------------------------------
# AC-7 -- echte Fremd-Beschriftung bleibt unbewertet (befristet, s. Known
# Limitations der Spec: faellt mit dem Folge-Ticket "unbekannte Beschriftung
# = lauter Befund" weg)
# ---------------------------------------------------------------------------


def test_ac7_unknown_label_outside_both_versions_stays_unevaluated(validator):
    """AC-7: GIVEN eine Uebersichtszeile traegt eine Beschriftung, die weder
    in der heutigen noch in der A2b-Zielfassung noch in der Ausnahme-Menge
    vorkommt (Tippfehler, z. B. "Mond") / WHEN Plausibilitaets- und
    Format-Check laufen / THEN bleibt diese Zeile unbewertet -- die Union
    veraendert den heutigen Status quo fuer echte Fremd-Beschriftungen nicht.

    Dieser Test ist bewusst ein Regressionsnachweis, kein Wirkungsnachweis:
    er darf schon VOR dieser Lieferung gruen sein (der stille `continue`-Pfad
    existiert unveraendert seit #1404) -- entscheidend ist, dass er es auch
    NACH der Erweiterung bleibt. Ausdruecklich befristet (Spec Known
    Limitations): faellt mit dem Folge-Ticket "unbekannte Beschriftung =
    lauter Befund" ersatzlos weg."""
    body = _overview_mail_from_rows([("Mond", "kaputt")])

    assert validator.validate_plausibility(body) == []
    assert validator.validate_format(body) == []
