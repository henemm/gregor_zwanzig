"""Pflicht-Pruefer kennt genau EINE Namensform je Tabelle (Issue #1453, AC-6).

Seit #1404/#1420 fuehrt `.claude/hooks/email_spec_validator.py` eine
**Uebergangs-Union**: an zwei Stellen gelten alte UND neue Beschriftungen
gleichzeitig als gueltig, damit waehrend der Umbenennung keine inhaltlich
korrekte Mail hart abgelehnt wird. Diese Lieferung beendet die Uebergangszeit
in beide Richtungen zugleich:

* **Uebersichtstabelle** -- gueltig ist ab jetzt allein der ausgeschriebene
  deutsche Registername. Die englischen A2b-Kurzformen (``Gust``, ``Cond°``,
  ``hPa``, …) UND die alten abgekuerzten deutschen Formen (``Temp max``,
  ``Sonne``, ``Taupunkt Ø``, …) fallen heraus.
* **Stundentabelle** -- gueltig ist allein die aus dem Register abgeleitete
  englische Kurzform. Die sechs handgetippten Alt-Literale (``Gef.``,
  ``Böen``, ``Regen``, ``Gew.``, ``Regen-W.``, ``Sicht``) fallen heraus; die
  zwei umbenannten Spalten ``Dew``/``Press`` ziehen ueber die bestehende
  Ableitung automatisch nach.

Der Nachweis laeuft ausdruecklich in BEIDE Richtungen: der Pruefer nimmt die
neue Form an (und prueft sie wirklich, statt sie still zu ueberspringen) UND
er kennt die alte Form nicht mehr. Ein Test, der nur die Annahme prueft,
liesse eine weiterhin offene Uebergangs-Union durchgehen -- genau den Zustand,
den diese Lieferung beendet.

Geprueft werden die reinen Parse-Funktionen gegen versionierte HTML-Fixtures:
deterministisch, ohne Netz, ohne IMAP, ohne Postfach. Der Pruefling selbst
wird ECHT geladen und ausgefuehrt (kein Mock, kein `patch()`). Pfadregel
#1409: der Pruefling wird relativ zur eigenen Testdatei aufgeloest.

Die exakte Mengengleichung ("geprueft + ausgenommen = genau die Zeilen, die
der Renderer erzeugt") lebt weiterhin in
``test_compare_mail_overview_plausibility_coverage.py`` -- hier steht der
Verhaltensnachweis, dort die Vollstaendigkeit.

SPEC: docs/specs/modules/fix_1453_namensformen.md (AC-6)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "email_spec_validator.py"
)

LOCATIONS = ("Andermatt", "Kufstein", "Lienz")

# Die sechs Uebersichtszeilen, deren deutscher Registername am staerksten von
# dem abweicht, was der Pruefer bis heute fuehrt ("Temp max", "Sonne",
# "Wolken", "Taupunkt Ø", "Luftdruck Ø" bzw. die englische A2b-Gegenform).
# Werte in renderer-typischer Schreibweise.
NEUE_FORM: dict[str, str] = {
    "Temperatur Maximum": "21°C",
    "Sonnenstunden": "5.0 h",
    "Bewölkung": "30%",
    "Taupunkt": "8°C",
    "Luftdruck": "1013 hPa",
    "Gewitterenergie (CAPE)": "1200 J/kg",
}

# Alte Formen, die nach dem Rueckbau KEINE gueltige Uebersichtsbeschriftung
# mehr sind -- links die englischen A2b-Kurzformen, rechts die alten,
# abgekuerzten deutschen Formen der Uebergangs-Union.
ALTE_UEBERSICHTSFORMEN = [
    "Sun", "Cloud", "UV", "Rain", "Rain%", "Visib", "SnowH", "NewSn", "Gust",
    "0°Line", "WDir", "Feels min", "Feels max", "CldLow", "CldMid", "CldHi",
    "Humid", "Cond°", "hPa", "SnowL", "Temp", "Feels", "Thdr", "PType",
    "Temp max", "Temp min", "Sonne", "Wolken", "UV max", "Sicht min",
    "Gefühlte Temp. min", "Gefühlte Temp. max", "Wolken tief", "Wolken mittel",
    "Wolken hoch", "Luftfeuchtigkeit Ø", "Taupunkt Ø", "Luftdruck Ø",
    # Zwei alte deutsche Schluessel, deren Registername anders lautet:
    # "Regen" -> "Niederschlag", "CAPE" -> "Gewitterenergie (CAPE)". (Als
    # STUNDENspalte bleiben "Rain"/"CAPE" selbstverstaendlich gueltig -- dieser
    # Test sieht ausschliesslich in die Uebersichts-Mengen.)
    "Regen", "CAPE",
]

# Die sechs handgetippten Alt-Literale der Stundentabelle (Uebergangs-Union
# #1404). Nach dem Rueckbau sind sie unbekannte Spalten.
ALTE_STUNDENSPALTEN = ["Gef.", "Böen", "Regen", "Gew.", "Regen-W.", "Sicht"]


@pytest.fixture(scope="module")
def validator():
    spec = importlib.util.spec_from_file_location("esv1453", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:  # pragma: no cover - Ladefehler
        pytest.fail(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture-Erzeuger (Markup analog compare_html.py, Inline-Styles gekuerzt --
# Vorbild test_compare_mail_validator_column_order.py)
# ---------------------------------------------------------------------------


def _overview_table(rows: list[tuple[str, str]]) -> str:
    """Uebersichtstabelle; erste Datenzeile ist immer die Warn-Zeile, ueber die
    `extract_table_rows()` die Tabelle findet."""
    head = "".join(f"<th>{n}</th>" for n in ("Metrik",) + LOCATIONS)
    body = ""
    for label, value in [("Amtliche Warnungen", "—")] + rows:
        cells = f"<td>{label}</td>" + f"<td>{value}</td>" * len(LOCATIONS)
        body += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _hour_table(columns: list[str]) -> str:
    ths = "".join(f"<th>{c}</th>" for c in columns)
    rows = ""
    for hour in ("09", "10"):
        rows += "<tr>" + "".join(
            f'<td>{hour if c == "Zeit" else "—"}</td>' for c in columns
        ) + "</tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{rows}</tbody></table>"


def _location_section(name: str, columns: list[str]) -> str:
    header = (
        f'<div><span style="letter-spacing:0.1em;">ORT</span> '
        f'<span style="font-weight:600;">{name}</span></div>'
    )
    return f"<div>{header}{_hour_table(columns)}</div>"


def compare_mail(
    overview: list[tuple[str, str]] | None = None,
    columns: list[str] | None = None,
) -> str:
    overview = overview if overview is not None else [("Temperatur Maximum", "21°C")]
    columns = columns or ["Zeit", "Temp", "Wind", "Gust"]
    sections = "".join(_location_section(n, columns) for n in LOCATIONS)
    return (
        "<html><body><div><h1>Orts-Vergleich</h1>"
        f"{_overview_table(overview)}{sections}</div></body></html>"
    )


# ===========================================================================
# AC-6, Richtung 1 -- die NEUE Form wird angenommen UND wirklich geprueft
# ===========================================================================


@pytest.mark.parametrize("label,plausibel", sorted(NEUE_FORM.items()))
def test_written_out_german_overview_label_is_accepted_and_actually_checked(
    validator, label, plausibel
):
    """AC-6: GIVEN eine Uebersichtszeile traegt den ausgeschriebenen deutschen
    Registernamen mit einem renderer-typisch formatierten, plausiblen Wert /
    WHEN Plausibilitaets- und Format-Check laufen / THEN meldet der Pruefer
    nichts. UND: traegt dieselbe Zeile einen unbrauchbaren Wert, meldet er
    einen Befund, der die Zeile benennt.

    Die zweite Haelfte ist der eigentliche Punkt -- ohne sie waere auch ein
    Pruefer "gruen", der die neue Beschriftung schlicht nicht kennt und still
    ueberspringt (`continue`-Pfad).
    """
    gut = compare_mail(overview=[(label, plausibel)])
    assert validator.validate_plausibility(gut) == [], (
        f"Plausibler Wert '{plausibel}' fuer '{label}' darf keinen Befund erzeugen"
    )
    assert validator.validate_format(gut) == [], (
        f"Plausibler Wert '{plausibel}' fuer '{label}' darf keinen Befund erzeugen"
    )

    kaputt = compare_mail(overview=[(label, "kaputt")])
    findings = (
        validator.validate_plausibility(kaputt) + validator.validate_format(kaputt)
    )
    assert findings, (
        f"Zeile '{label}' laeuft ungeprueft durch: ein unbrauchbarer Zellwert "
        f"erzeugt keinen Befund -- der Pruefer kennt die neue Form nicht"
    )
    assert all(label in f for f in findings), (
        f"Jeder Befund muss die betroffene Zeile '{label}' benennen: {findings}"
    )


def test_renamed_hour_columns_dew_and_press_are_accepted(validator):
    """AC-6: GIVEN eine Stundentabelle zeigt die beiden umbenannten Spalten
    "Dew"/"Press" / WHEN der Struktur-Check laeuft / THEN nimmt der Pruefer
    die Mail an. Die Spaltenliste ist seit #1406 B aus dem Register
    abgeleitet -- die Umbenennung muss dort ohne eigenen Eingriff ankommen."""
    body = compare_mail(columns=["Zeit", "Temp", "Dew", "Press"])

    assert validator.validate_structure(body, hourly_enabled=True) == [], (
        "Die umbenannten Spalten werden abgelehnt: "
        f"{validator.validate_structure(body, hourly_enabled=True)}"
    )


# ===========================================================================
# AC-6, Richtung 2 -- die ALTE Form gilt nicht mehr
# ===========================================================================


def test_old_overview_label_forms_are_no_longer_a_known_form(validator):
    """AC-6 (Gegenrichtung, Uebersicht): GIVEN die Uebergangs-Union ist
    zurueckgebaut / WHEN man nachsieht, welche Uebersichtsbeschriftungen der
    Pruefer ueberhaupt kennt / THEN ist keine der alten Formen mehr darunter --
    weder die englischen A2b-Kurzformen noch die alten abgekuerzten deutschen.

    Warum strukturell und nicht ueber einen Mail-Lauf: eine unbekannte
    Uebersichtsbeschriftung laesst der Pruefer heute bewusst unbewertet
    (stiller `continue`-Pfad, #1420 Known Limitations) -- ein Mail-Lauf mit
    alter Form kann deshalb gar keinen Befund erzeugen. Beobachtbar ist die
    Gegenrichtung an der bekannten Menge selbst.
    """
    bekannt = set(validator._OVERVIEW_METRIC_CHECKS) | set(
        validator._OVERVIEW_NO_CHECK_LABELS
    )

    uebrig = sorted(bekannt & set(ALTE_UEBERSICHTSFORMEN))
    assert not uebrig, (
        "Der Pruefer fuehrt weiterhin alte Uebersichtsbeschriftungen -- die "
        f"Uebergangs-Union ist nicht zurueckgebaut: {uebrig}"
    )


@pytest.mark.parametrize("alt", ALTE_STUNDENSPALTEN)
def test_old_hour_column_label_is_rejected_and_named(validator, alt):
    """AC-6 (Gegenrichtung, Stundentabelle): GIVEN eine Mail zeigt eine der
    sechs Alt-Beschriftungen als Stundenspalte / WHEN der Struktur-Check
    laeuft / THEN lehnt der Pruefer sie ab und benennt die Spalte.

    Hier ist die Ablehnung echt beobachtbar: `validate_structure()` fuehrt
    fuer Stundenspalten eine geschlossene Allowlist."""
    body = compare_mail(columns=["Zeit", "Temp", alt])

    errors = validator.validate_structure(body, hourly_enabled=True)

    assert errors, f"Alt-Spalte '{alt}' wird weiterhin angenommen"
    assert any(alt in e for e in errors), (
        f"Der Befund muss die Alt-Spalte '{alt}' benennen: {errors}"
    )


def test_invented_hour_column_is_still_rejected_and_named(validator):
    """[REGRESSIONSSCHUTZ] Der Rueckbau darf die Allowlist nicht stumpf
    machen: eine erfundene Spalte wird weiterhin abgelehnt und benannt.
    Heute gruen -- muss gruen bleiben."""
    body = compare_mail(columns=["Zeit", "Temp", "Mondphase"])

    errors = validator.validate_structure(body, hourly_enabled=True)

    assert errors and any("Mondphase" in e for e in errors), (
        f"Erfundene Spalte wird nicht mehr benannt abgelehnt: {errors}"
    )
