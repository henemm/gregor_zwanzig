"""Compare-Mail-Pruefer: freie Spaltenreihenfolge der Stundentabelle (#1381).

Der Pflicht-Pruefer des Ortsvergleichs-Mailpfads
(`.claude/hooks/email_spec_validator.py`) weist eine inhaltlich korrekte Mail
zurueck, sobald die Spalten der Stundentabelle nicht in der intern kodierten
Kanon-Reihenfolge stehen. Diese Reihenfolge ist seit #1359 frei einstellbar --
der Pruefer kennt diese Freiheit nicht (Fundstelle: Projektion auf
`_HOUR_COLUMNS_V2` in `validate_structure()`).

Geprueft wird die reine Parse-Funktion `validate_structure(body,
hourly_enabled=...)` gegen versionierte HTML-Fixtures: deterministisch, ohne
Netz, ohne IMAP, ohne Postfach. Der Pruefling selbst wird ECHT geladen und
ausgefuehrt (kein Mock, kein Patch).

Die Fixtures bilden genau die Markup-Merkmale nach, an denen der Pruefer die
Strukturen erkennt -- Vorbild ist der echte Renderer
`src/output/renderers/email/compare_html.py`:

* Uebersichtstabelle: Kopfzeile "Metrik" + Ortsnamen, erste Datenzeile
  "Amtliche Warnungen" (`_render_overview_table`, `CV2_METRICS[0]`) --
  darueber findet `extract_table_rows()`/`extract_locations()` die Tabelle.
* Je Ort ein Kopf `>ORT</span> <span ...>Name</span>`
  (`_render_location_section`) und darunter eine Tabelle, deren Kopfzeile mit
  "Zeit" beginnt (`_render_hour_table`) -- darueber findet
  `_find_location_hour_table()` die Stundentabelle.

Die Spaltenfolge ist je Test frei setzbar; das ist der Punkt des Fixes.
"""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"

# Der real belegte Fall aus #1361 (Staging-Preset cp-21e198c1b74020dd, 3 Orte):
# dieselben zehn Spalten wie der Kanon, nur "UV" ans Ende sortiert.
ORDER_1361 = [
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "Gew.", "Regen-W.", "Sicht", "UV",
]

# Beispiel-Zellwerte je Spalten-Label, exakt in den Formaten, die die
# `fmt`-Funktionen von HOUR_METRICS erzeugen (_fmt_deg/_fmt_kmh/_fmt_rain/...).
_HOUR_CELL_VALUES = {
    "Temp": "21°", "Gef.": "19°", "Wind": "10", "Böen": "18", "Regen": "·",
    "UV": "4", "Gew.": "—", "Regen-W.": "15%", "Sicht": "9.0",
}


def _load_validator():
    """Laedt den echten Pruefer als isoliertes Modul (Muster aus
    tests/tdd/test_issue_1150_compare_validator_hourly.py::_load_validator)."""
    spec = importlib.util.spec_from_file_location("esv1381", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        pytest.fail(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture-Erzeuger -- Markup analog compare_html.py (Inline-Styles gekuerzt,
# Struktur 1:1: thead/tbody, th/td, ORT-Kopf, "Zeit" als erste Kopfzelle)
# ---------------------------------------------------------------------------


def _hour_table(columns: list[str]) -> str:
    """Stundentabelle eines Ortes (_render_hour_table): Kopfzeile aus
    `columns`, zwei Datenzeilen (09/10, Stundenformat ohne Minuten, #1237)."""
    ths = "".join(
        f'<th style="text-align:{"left" if c == "Zeit" else "center"};padding:6px 4px;'
        f'font-size:11px;color:#1a1a18;font-weight:600;'
        f'border-right:1px solid #f0ece1;">{c}</th>'
        for c in columns
    )
    header = f'<tr style="background:#f6f4ee;border-bottom:1px solid #e6e1d3;">{ths}</tr>'
    rows = ""
    for hour in ("09", "10"):
        tds = "".join(
            f'<td style="text-align:{"left" if c == "Zeit" else "center"};padding:8px 4px;'
            f'font-size:13px;background:transparent;color:#1a1a18;font-weight:500;'
            f'border-right:1px solid #f0ece1;">'
            f'{hour if c == "Zeit" else _HOUR_CELL_VALUES.get(c, "—")}</td>'
            for c in columns
        )
        rows += f'<tr style="border-bottom:1px solid #f0ece1;">{tds}</tr>'
    return (
        f'<div style="overflow-x:auto;margin-top:12px;border:1px solid #e6e1d3;">'
        f'<table cellspacing="0" cellpadding="0" style="width:100%;'
        f'border-collapse:collapse;margin-top:12px;font-size:12px;">'
        f'<thead>{header}</thead><tbody>{rows}</tbody></table></div>'
    )


def _location_section(name: str, columns: list[str]) -> str:
    """Ort-Kopf + Stundentabelle (_render_location_section). Der Kopf traegt
    das Marker-Markup `>ORT</span> <span ...>Name</span>`, ueber das
    `_find_location_hour_table()` den Ort findet."""
    header = (
        f'<div style="padding-bottom:8px;border-bottom:2px solid #1a1a18;">'
        f'<span style="font-size:11px;font-weight:600;color:#b45309;'
        f'letter-spacing:0.1em;">ORT</span> '
        f'<span style="font-size:15px;font-weight:600;color:#1a1a18;">{name}</span>'
        f'</div>'
    )
    return f'<div style="padding:14px 24px 0;">{header}{_hour_table(columns)}</div>'


def _overview_table(names: list[str]) -> str:
    """Uebersichtstabelle (_render_overview_table): Kopfzeile "Metrik" +
    Ortsspalten, danach die immer erste Warn-Zeile und numerische Zeilen in den
    Formaten von CV2_METRICS."""
    header_cells = ['<th style="text-align:left;padding:9px 5px;">Metrik</th>']
    header_cells += [
        f'<th style="text-align:center;padding:9px 5px;font-weight:600;">{n}</th>'
        for n in names
    ]
    header = (
        f'<tr style="background:#f6f4ee;border-bottom:1px solid #e6e1d3;">'
        f'{"".join(header_cells)}</tr>'
    )
    body_rows = ""
    for label, value in (
        ("Amtliche Warnungen", "—"), ("Temp max", "21°C"), ("Wind", "10 km/h"),
        ("Sonne", "5.0 h"), ("Wolken", "30%"), ("UV max", "4"),
    ):
        cells = f'<td style="text-align:left;padding:8px 5px;">{label}</td>'
        cells += "".join(
            f'<td style="text-align:center;padding:8px 5px;">{value}</td>' for _ in names
        )
        body_rows += f'<tr style="border-bottom:1px solid #f0ece1;">{cells}</tr>'
    return (
        f'<div style="overflow-x:auto;margin-top:12px;border:1px solid #e6e1d3;">'
        f'<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;">'
        f'<thead>{header}</thead><tbody>{body_rows}</tbody></table></div>'
    )


def compare_mail(locations: list[tuple[str, list[str]]]) -> str:
    """Vollstaendiger Vergleichs-Mail-Body: Uebersichtstabelle ueber alle Orte
    plus je Ort eine Sektion mit der uebergebenen Spaltenfolge."""
    names = [name for name, _cols in locations]
    sections = "".join(_location_section(name, cols) for name, cols in locations)
    return (
        '<html><body style="background:#f6f4ee;">'
        '<div style="padding:24px;"><h1 style="font-size:20px;">Orts-Vergleich</h1>'
        '<p style="font-size:12px;">Mittwoch, 8. Juli 2026 · Zeitfenster 09-16 Uhr</p>'
        f'{_overview_table(names)}{sections}'
        '<p style="font-size:11px;color:#6b6b63;">Einheiten: Temp °C · Wind km/h · '
        'Regen mm · Sicht km</p></div></body></html>'
    )


# ---------------------------------------------------------------------------
# AC-1 -- umsortierte, bekannte Spalten sind gueltig
# ---------------------------------------------------------------------------


def test_ac1_reordered_known_columns_are_accepted():
    """AC-1: GIVEN eine Vergleichs-Mail, deren Stundentabellen ausschliesslich
    bekannte Spalten tragen, aber in der seit #1359 einstellbaren, vom Kanon
    abweichenden Reihenfolge (real belegter Fall aus #1361: UV ans Ende
    sortiert) / WHEN der Struktur-Check laeuft / THEN meldet der Pruefer keinen
    Strukturfehler -- eine inhaltlich korrekte Mail darf nicht abgelehnt
    werden."""
    mod = _load_validator()
    body = compare_mail([
        ("Innsbruck", ORDER_1361), ("Kufstein", ORDER_1361), ("Lienz", ORDER_1361),
    ])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert errors == [], (
        "Eine korrekte Mail mit frei sortierten, bekannten Spalten muss "
        f"angenommen werden. Der Pruefer meldet: {errors}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- unbekannte Spalte bleibt ein Fehler
# ---------------------------------------------------------------------------


def test_ac2_unknown_column_is_rejected_and_named():
    """AC-2: GIVEN eine Stundentabelle mit einer Spalte, die nicht zur
    bekannten Wertspalten-Liste gehoert ("Mond") / WHEN der Struktur-Check
    laeuft / THEN meldet der Pruefer genau einen Fehler, dessen Text die
    unbekannte Spalte benennt -- die Reihenfolge-Lockerung darf keine
    Fremdspalten durchlassen."""
    mod = _load_validator()
    body = compare_mail([
        ("Ort A", ["Zeit", "Temp", "Wind", "Böen"]),
        ("Ort B", ["Zeit", "Temp", "Mond", "Wind", "Böen"]),
        ("Ort C", ["Zeit", "Temp", "Wind", "Böen"]),
    ])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert len(errors) == 1, (
        f"Erwartet genau ein Befund (die unbekannte Spalte bei 'Ort B'), "
        f"bekommen: {errors}"
    )
    assert "Mond" in errors[0], f"Fehler muss die Spalte 'Mond' benennen: {errors[0]}"
    assert "Ort B" in errors[0], f"Fehler muss den Ort benennen: {errors[0]}"

    # Erosionsschutz: traegt JEDER Ort dieselbe Fremdspalte, kann die
    # Cross-Location-Regel nicht mehr aushelfen (alle Kopfzeilen sind
    # identisch). Nur eine eigenstaendige Unbekannte-Spalte-Pruefung faengt
    # diesen Fall -- ohne sie waere die Mail nach dem Umbau still gueltig.
    all_bad = ["Zeit", "Temp", "Mond", "Wind", "Böen"]
    errors_all = mod.validate_structure(
        compare_mail([("Ort A", all_bad), ("Ort B", all_bad), ("Ort C", all_bad)]),
        hourly_enabled=True,
    )
    assert errors_all, (
        "Eine mail-weit einheitliche Fremdspalte MUSS abgelehnt werden -- sonst "
        "ist die Spalten-Allowlist wirkungslos"
    )
    assert all("Mond" in e for e in errors_all), (
        f"Jeder Befund muss die unbekannte Spalte benennen: {errors_all}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- doppelte Spalte bleibt ein Fehler
# ---------------------------------------------------------------------------


def test_ac3_duplicate_column_is_rejected_and_named():
    """AC-3: GIVEN eine Stundentabelle, in der dieselbe Spalte zweimal steht
    ("Wind") / WHEN der Struktur-Check laeuft / THEN meldet der Pruefer einen
    Fehler, der die doppelte Spalte benennt.

    Hinweis zur Beweiskraft: Heute besteht dieser Test nur als NEBENEFFEKT --
    die Projektion auf die Kanon-Reihenfolge dedupliziert, wodurch die
    Kopfzeile ungleich der Projektion wird und der Reihenfolge-Fehler greift;
    die Meldung nennt die Spalte nur, weil sie die ganze Kopfzeile abdruckt.
    Faellt die Reihenfolge-Projektion (Kern dieses Fixes) ersatzlos weg,
    verschwindet die Ablehnung. Nach dem Umbau muss die Ablehnung durch eine
    AUSDRUECKLICHE Duplikat-Pruefung erfolgen -- dieser Test muss dabei gruen
    bleiben.

    Deshalb traegt hier JEDER Ort dieselbe doppelte Spalte: so kann weder die
    Cross-Location-Regel (alle Kopfzeilen identisch) noch die
    Mindestspalten-Regel den Fall auffangen -- nur eine echte
    Duplikat-Pruefung."""
    mod = _load_validator()
    dup = ["Zeit", "Temp", "Wind", "Böen", "Wind"]
    body = compare_mail([("Ort A", dup), ("Ort B", dup), ("Ort C", dup)])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert errors, (
        "Eine doppelte Spalte MUSS abgelehnt werden -- auch wenn alle Orte "
        "dieselbe Kopfzeile tragen"
    )
    assert all("Wind" in e for e in errors), (
        f"Jeder Befund muss die doppelte Spalte 'Wind' benennen: {errors}"
    )
    assert any("Ort A" in e for e in errors), (
        f"Der Befund muss den betroffenen Ort benennen: {errors}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- Mindestspalten-Regel bleibt scharf
# ---------------------------------------------------------------------------


def test_ac4_minimum_columns_rule_still_rejects():
    """AC-4: GIVEN Stundentabellen ohne jede Wertspalte (nur "Zeit") bzw. ohne
    "Zeit" als erste Spalte / WHEN der Struktur-Check laeuft / THEN wird
    weiterhin ein Fehler gemeldet -- die Reihenfolge-Lockerung darf die
    Mindestspalten-Regel nicht mit aufweichen (Bestandsverhalten)."""
    mod = _load_validator()

    only_time = compare_mail([
        ("Ort A", ["Zeit", "Temp", "Wind"]),
        ("Ort B", ["Zeit"]),
        ("Ort C", ["Zeit", "Temp", "Wind"]),
    ])
    errors_only_time = mod.validate_structure(only_time, hourly_enabled=True)
    assert any("Ort B" in e for e in errors_only_time), (
        f"Eine Stundentabelle ohne jede Wertspalte MUSS abgelehnt werden: "
        f"{errors_only_time}"
    )
    assert any("Mindestspalten" in e for e in errors_only_time), (
        f"Erwartet wird die Mindestspalten-Regel: {errors_only_time}"
    )

    # Zweite Haelfte des Given: erste Spalte heisst nicht "Zeit". Der Pruefer
    # erkennt eine Stundentabelle ueber genau dieses Merkmal (#1150, Fix-Runde
    # 2) -- die Tabelle gilt dann als gar nicht vorhanden. Auch dieser Weg
    # fuehrt zur Ablehnung; entscheidend fuer AC-4 ist, dass sie erfolgt.
    no_time = compare_mail([
        ("Ort A", ["Zeit", "Temp", "Wind"]),
        ("Ort B", ["Temp", "Wind"]),
        ("Ort C", ["Zeit", "Temp", "Wind"]),
    ])
    errors_no_time = mod.validate_structure(no_time, hourly_enabled=True)
    assert any("Ort B" in e for e in errors_no_time), (
        f"Eine Stundentabelle ohne fuehrende 'Zeit'-Spalte MUSS abgelehnt "
        f"werden: {errors_no_time}"
    )


# ---------------------------------------------------------------------------
# AC-5 -- abweichende Spaltenmenge zwischen Orten bleibt ein Fehler
# ---------------------------------------------------------------------------


def test_ac5_differing_column_set_across_locations_is_rejected():
    """AC-5: GIVEN zwei Orte derselben Mail mit unterschiedlicher
    Spaltenmenge (Ort B hat eine Spalte weniger als Ort A) / WHEN der
    Struktur-Check laeuft / THEN wird ein Fehler gemeldet, der den
    abweichenden Ort benennt -- mail-weit gilt genau eine Konfiguration."""
    mod = _load_validator()
    full = ["Zeit", "Temp", "Wind", "Böen", "Regen"]
    body = compare_mail([
        ("Ort A", full), ("Ort B", ["Zeit", "Temp", "Wind", "Böen"]), ("Ort C", full),
    ])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert len(errors) == 1, (
        f"Erwartet genau ein Befund (Ort B weicht ab), bekommen: {errors}"
    )
    assert "Ort B" in errors[0], (
        f"Der Befund muss den abweichenden Ort 'Ort B' benennen: {errors[0]}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- gleiche Menge, andere Reihenfolge zwischen Orten bleibt ein Fehler
# ---------------------------------------------------------------------------


def test_ac6_differing_column_order_across_locations_is_rejected():
    """AC-6: GIVEN zwei Orte derselben Mail mit derselben Spaltenmenge, aber
    unterschiedlicher Reihenfolge / WHEN der Struktur-Check laeuft / THEN wird
    ein Fehler gemeldet, der den abweichenden Ort benennt -- eine Mail traegt
    genau eine Spalten-Konfiguration, auch nach der Reihenfolge-Lockerung.

    Hinweis: Heute greift dabei noch die Kanon-Reihenfolge-Pruefung, nach dem
    Umbau die Cross-Location-Regel. Beide Male muss dieselbe Mail abgelehnt
    werden und dieselbe Ortsangabe tragen."""
    mod = _load_validator()
    body = compare_mail([
        ("Ort A", ["Zeit", "Temp", "Wind"]),
        ("Ort B", ["Zeit", "Wind", "Temp"]),
        ("Ort C", ["Zeit", "Temp", "Wind"]),
    ])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert len(errors) == 1, (
        f"Erwartet genau ein Befund (Ort B weicht in der Reihenfolge ab), "
        f"bekommen: {errors}"
    )
    assert "Ort B" in errors[0], (
        f"Der Befund muss den abweichenden Ort 'Ort B' benennen: {errors[0]}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- mail-weit einheitliche, aber nicht-kanonische Reihenfolge ist gueltig
# ---------------------------------------------------------------------------


def test_ac7_uniform_non_canonical_order_across_locations_is_accepted():
    """AC-7: GIVEN drei Orte derselben Mail mit identischer Spaltenmenge in
    identischer, aber vom alten Kanon abweichender Reihenfolge / WHEN der
    Struktur-Check laeuft / THEN meldet der Pruefer keinen
    Cross-Location-Fehler (und ueberhaupt keinen Fehler) -- die mail-weite
    Konsistenz ist erfuellt, die Kanon-Reihenfolge ist kein Massstab mehr."""
    mod = _load_validator()
    order = ["Zeit", "Sicht", "Regen-W.", "Temp", "Wind"]
    body = compare_mail([("Ort A", order), ("Ort B", order), ("Ort C", order)])

    errors = mod.validate_structure(body, hourly_enabled=True)

    assert errors == [], (
        "Drei Orte mit identischer, frei sortierter Spaltenfolge sind mail-weit "
        f"konsistent und muessen angenommen werden. Pruefer meldet: {errors}"
    )


# ===========================================================================
# #1404 -- Uebergangs-Union der Spaltenbeschriftungen (AC-1, AC-2, AC-5)
#
# #1401 Scheibe A2b leitet die Spaltenueberschriften aus dem zentralen
# Namensregister ab; 6 der 9 Wertspalten heissen danach anders. Der Pruefer
# kennt sie woertlich und wuerde die dann korrekte Mail hart ablehnen (Exit 1
# ueber das Renderer-Commit-Gate #811) -- A2b koennte seinen eigenen Commit
# nicht abschliessen. Bis A2b geliefert ist, muessen BEIDE Fassungen
# durchgehen; danach faellt die alte Haelfte wieder raus (AC-5).
#
# SPEC: docs/specs/modules/fix_1404_validator_spaltennamen.md
# ===========================================================================

# Zielfassung nach #1401 A2b (dort "Ziel-Beschriftung Stundentabelle",
# kanonische Reihenfolge). Gegenueber heute geaendert: Gef.->Feels,
# Böen->Gust, Regen->Rain, Gew.->Thdr, Regen-W.->Rain%, Sicht->Visib.
ORDER_A2B = [
    "Zeit", "Temp", "Feels", "Wind", "Gust", "Rain", "UV", "Thdr", "Rain%", "Visib",
]

# Heutige Fassung (kanonische Reihenfolge, `_HOUR_COLUMNS_V2`).
ORDER_TODAY = [
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.", "Regen-W.", "Sicht",
]

# Spec-Datum der Uebergangsregelung + projektuebliche 90-Tage-Spanne
# (Regel-Budget, Vorbild `nebenbefund_gate.py:21`).
SPEC_CREATED = date(2026, 7, 28)


def _uniform_mail(columns: list[str]) -> str:
    return compare_mail([("Ort A", columns), ("Ort B", columns), ("Ort C", columns)])


def test_1404_ac1_both_column_namings_are_accepted():
    """AC-1: GIVEN eine Vergleichs-Mail zeigt ihre Stundentabellen entweder in
    der heutigen oder in der kuenftigen A2b-Beschriftung (oder mail-weit
    einheitlich gemischt) / WHEN der Struktur-Check laeuft / THEN meldet der
    Pruefer keinen Fehler wegen unbekannter Spalten.

    Solange die Umbenennung laeuft, sind beide Fassungen inhaltlich korrekt --
    der Pruefer darf keine davon abweisen, sonst blockiert er die Lieferung,
    die er absichern soll."""
    mod = _load_validator()

    errors_new = mod.validate_structure(_uniform_mail(ORDER_A2B), hourly_enabled=True)
    assert errors_new == [], (
        "Die kuenftige A2b-Spaltenfassung muss angenommen werden, sonst kann "
        f"#1401 A2b nicht committen. Pruefer meldet: {errors_new}"
    )

    errors_old = mod.validate_structure(_uniform_mail(ORDER_TODAY), hourly_enabled=True)
    assert errors_old == [], (
        f"Die heutige Spaltenfassung muss weiterhin angenommen werden: {errors_old}"
    )

    mixed = ["Zeit", "Temp", "Gef.", "Wind", "Gust", "Rain"]
    errors_mixed = mod.validate_structure(_uniform_mail(mixed), hourly_enabled=True)
    assert errors_mixed == [], (
        f"Mail-weit einheitliche Mischung aus beiden Fassungen: {errors_mixed}"
    )


def test_1404_ac2_unknown_column_is_still_rejected_and_named():
    """AC-2: GIVEN eine Stundentabellen-Spalte, die weder zur heutigen noch zur
    kuenftigen Beschriftung gehoert ("Mond") / WHEN der Struktur-Check laeuft /
    THEN meldet der Pruefer weiterhin einen Fehler, der die Spalte benennt --
    die Uebergangsfassung ist eine erweiterte Pruefung, keine Durchreiche.

    Bestandsschutz-Nachweis, heute schon gruen: die Erweiterung der Allowlist
    darf die Allowlist nicht wirkungslos machen. Die Befunde werden bewusst auf
    "Mond" eingegrenzt -- ob die uebrigen, KNOWN Spalten der Mischung
    durchgehen, ist Gegenstand von AC-1 und heute noch offen."""
    mod = _load_validator()
    old_mix = ["Zeit", "Temp", "Gef.", "Wind", "Böen"]

    body = compare_mail([
        ("Ort A", old_mix),
        ("Ort B", ["Zeit", "Temp", "Gef.", "Mond", "Wind", "Böen"]),
        ("Ort C", old_mix),
    ])
    errors = mod.validate_structure(body, hourly_enabled=True)
    assert len(errors) == 1, (
        f"Erwartet genau ein Befund (die unbekannte Spalte bei 'Ort B'): {errors}"
    )
    assert "Mond" in errors[0] and "Ort B" in errors[0], (
        f"Der Befund muss Spalte und Ort benennen: {errors[0]}"
    )

    # Mischung aus alter und neuer Beschriftung (Spec-Fassung von AC-2): die
    # Fremdspalte bleibt EIN benannter Befund am richtigen Ort.
    mixed = ["Zeit", "Temp", "Gef.", "Wind", "Gust"]
    mixed_errors = mod.validate_structure(
        compare_mail([
            ("Ort A", mixed),
            ("Ort B", ["Zeit", "Temp", "Gef.", "Mond", "Wind", "Gust"]),
            ("Ort C", mixed),
        ]),
        hourly_enabled=True,
    )
    mond_errors = [e for e in mixed_errors if "Mond" in e]
    assert len(mond_errors) == 1 and "Ort B" in mond_errors[0], (
        f"Erwartet genau einen Mond-Befund bei 'Ort B': {mixed_errors}"
    )

    # Erosionsschutz: traegt JEDER Ort dieselbe Fremdspalte, kann die
    # Cross-Location-Regel nicht aushelfen -- nur die Allowlist selbst.
    all_bad = ["Zeit", "Temp", "Mond", "Wind", "Böen"]
    errors_all = mod.validate_structure(_uniform_mail(all_bad), hourly_enabled=True)
    assert errors_all and all("Mond" in e for e in errors_all), (
        f"Eine mail-weit einheitliche Fremdspalte MUSS abgelehnt werden: {errors_all}"
    )


def test_1404_ac5_transition_union_carries_a_review_date():
    """AC-5: GIVEN die Spalten-Union aus alter und neuer Beschriftung ist eine
    bewusst befristete Zwischenloesung / WHEN das Pruefer-Modul geladen wird /
    THEN traegt es ein maschinenlesbares Datum, bis zu dem entschieden sein
    muss, ob die alten Beschriftungen wieder herausfallen.

    Das Datum ist nur ein Erinnerungs-Marker fuer eine menschliche Review -- es
    darf KEIN Verhalten umschalten (anders als `nebenbefund_gate.py`): ein
    Pruefer, der sich am Stichtag selbst verengt, wuerde eine dann korrekte
    Mail wieder ablehnen, falls sich A2b verzoegert. Dieser Test verlangt
    deshalb ausdruecklich keine Selbstabschaltung."""
    mod = _load_validator()

    review = None
    for name in (
        "_HOUR_COLUMNS_V2_REVIEW_DATE", "_HOUR_COLUMNS_V2_EXPIRY",
        "_HOUR_COLUMNS_V2_PRUEFDATUM",
    ):
        review = getattr(mod, name, None)
        if review is not None:
            break
    assert review is not None, (
        "Der Pruefer nennt kein Pruefdatum fuer die Spalten-Uebergangs-Union "
        "(erwartet z. B. _HOUR_COLUMNS_V2_REVIEW_DATE) -- die Uebergangsregelung "
        "wuerde stillschweigend fuer immer gelten"
    )
    if isinstance(review, str):
        review = date.fromisoformat(review)
    assert isinstance(review, date), f"Pruefdatum muss ein Datum sein, ist: {review!r}"
    assert SPEC_CREATED < review <= SPEC_CREATED + timedelta(days=90), (
        f"Pruefdatum {review} liegt ausserhalb der projektueblichen 90-Tage-Spanne "
        f"ab {SPEC_CREATED} (Regel-Budget)"
    )
