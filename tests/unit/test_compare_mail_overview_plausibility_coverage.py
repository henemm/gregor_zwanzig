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
from pathlib import Path

import pytest

from output.renderers.email.compare_html import CV2_METRICS, _fmt_metric

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "email_spec_validator.py"
)

# Die drei Zeilen ohne Zahlenwert: die Warn-Zeile (gestapelte Warn-Chips) und
# die zwei kategorialen Enum-Zeilen. Fuer sie ist "keine Pruefung" richtig --
# aber es muss ausgesprochen sein, nicht aus einem fehlenden Dict-Eintrag
# folgen (AC-4).
EXEMPT_LABELS = {"Amtliche Warnungen", "Gewitter", "Niederschlagsart"}

NUMERIC_LABELS = [m["label"] for m in CV2_METRICS if m["label"] not in EXEMPT_LABELS]

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
    for m in CV2_METRICS:
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
    """AC-4: GIVEN die Uebersichtstabelle hat 27 Zeilen / WHEN man geprueft und
    ausgenommen zusammenzaehlt / THEN ergibt sich exakt die Gesamtzahl: 24
    geprueft + 3 ausgesprochen ausgenommen, ueberschneidungsfrei. Rechnerisch
    gegen `CV2_METRICS` gefuehrt, damit eine kuenftig hinzugefuegte Zeile hier
    auffaellt, statt lautlos in den `continue`-Pfad zu rutschen (#1296/#1324)."""
    exempt = getattr(validator, "_OVERVIEW_NO_CHECK_LABELS", None)
    assert exempt is not None, (
        "Der Pruefer nennt keine ausgesprochene Ausnahme-Menge "
        "(_OVERVIEW_NO_CHECK_LABELS) -- die drei nicht-numerischen Zeilen "
        "bleiben nur zufaellig unbewertet"
    )
    exempt = set(exempt)
    checked = set(validator._OVERVIEW_METRIC_CHECKS)
    all_labels = {m["label"] for m in CV2_METRICS}

    assert exempt == EXEMPT_LABELS, f"Erwartete Ausnahme-Zeilen: {EXEMPT_LABELS}"
    assert checked.isdisjoint(exempt), (
        f"Eine Zeile kann nicht geprueft UND ausgenommen sein: {checked & exempt}"
    )
    assert checked | exempt == all_labels, (
        f"Weder geprueft noch ausgenommen: {sorted(all_labels - checked - exempt)}; "
        f"unbekannte Beschriftung im Pruefer: {sorted((checked | exempt) - all_labels)}"
    )
    assert len(checked) == len(NUMERIC_LABELS) and len(checked) + len(exempt) == len(CV2_METRICS)


@pytest.mark.parametrize("label", sorted(EXEMPT_LABELS))
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
