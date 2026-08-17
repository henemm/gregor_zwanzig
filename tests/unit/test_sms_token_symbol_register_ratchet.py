"""Ratsche: SMS-Token-Kuerzel duerfen nicht vom Wetter-Register abdriften.

SPEC: docs/specs/modules/fix_1435_e3b_sms_kuerzel.md — AC-9.

Geprueft werden die vier Stellen, die im Trip-SMS-Pfad Symbole fuehren:

  * `output/tokens/builder.py`  — `PRIORITY`, `POSITIONAL`, `_wintersport()`
  * `output/tokens/render.py`   — `DROP_ORDER`
  * `output/adapters/trip_result.py` — `_wintersport_default_config()`
  * `output/renderers/sms_trip.py`   — `SMS_SYMBOL_BY_METRIC`

gegen `app.metric_catalog.get_sms_code()`.

Bauprinzipien (aus der Erfahrung zweier gruener Waechter in Etappe E3a, die
nie etwas geprueft hatten):

  1. **Kein Regex ueber Quelltext.** Alle Symbole werden ueber echten Import
     der Module bzw. echten Aufruf von `_wintersport()` ermittelt. Ein
     Regex, der nichts findet, ist immer gruen.
  2. **Keine handgepflegte Symbolliste.** Welche Wettergroessen im
     Wintersport-Block stecken, wird durch Abtasten der `DailyForecast`-
     Felder ermittelt; die Soll-Kuerzel kommen aus dem Register. Von Hand
     steht hier NUR die kommentierte Ausnahmeliste.
  3. **Nichtstun ist kein Bestehen.** Jeder Test behauptet seine eigene
     Trefferzahl (`> 0`); findet er nichts zu pruefen, schlaegt er fehl.
  4. **Der Pruefling muss aus DIESEM Arbeitsbaum stammen** (#1409) — sonst
     misst ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.

Regel-Budget (CLAUDE.md): Pruefdatum 2026-10-30.
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from app import metric_catalog as catalog_mod
from app.metric_catalog import (
    SMS_NULLFORM_METRIC_IDS, get_all_metrics, get_sms_code,
)
from output.adapters.trip_result import _wintersport_default_config
from output.renderers.sms_trip import (
    SMS_SYMBOL_BY_METRIC, build_extended_metric_specs,
)
from output.tokens import builder as builder_mod
from output.tokens.builder import (
    POSITIONAL, PRIORITY, _wintersport, build_token_line,
)
from output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
)
from output.tokens.render import DROP_ORDER

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Ausnahmen — ausdruecklich, begruendet, NICHT stillschweigend uebersprungen.
# Schluessel ist das DailyForecast-Feld (nicht das Symbol): so kann eine
# Umbenennung des Symbols die Ausnahme nicht versehentlich mitschleppen.
# ---------------------------------------------------------------------------
EXEMPT_FORECAST_FIELDS: dict[str, str] = {
    # 'AV' — Lawinenstufe. Das Register fuehrt dafuer ueberhaupt keine
    # Groesse (keine Katalog-Metrik), also gibt es kein Soll-Kuerzel.
    "avalanche_level": "AV: Lawinenstufe, kein Registereintrag",
    # Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    # fix_1887_e6a_sms_kuerzel_register.md): der vormalige 'WC'-Eintrag fuer
    # "wind_chill_c" entfaellt ERSATZLOS, nicht nur umformuliert -- 'WC'
    # verdoppelte nachweislich den Wert von 'FK' (identisches Feld, Fenster,
    # Aggregation) und wird von _wintersport() nach dieser Scheibe fuer
    # dieses Feld gar nicht mehr abgetastet. Ohne einen Eintrag hier bleibt
    # "wind_chill_c" (dp_field von "wind_chill", sms_code="TF") im
    # Register-Vergleich sichtbar: die Zelle zeigt weiterhin Stundenwerte
    # (col_key="felt"), nicht das entfallene SMS-Kuerzel.
}

# metric_id -> Begruendung. Ausnahmen der Register-Herrschaft ueber
# SMS_SYMBOL_BY_METRIC.
EXEMPT_METRIC_IDS: dict[str, str] = {
    # 'TH:' ist Grammatikform (Doppelpunkt trennt Gewitter-Stufe vom
    # Kuerzel); das Register kennt nur 'TH'. Ausdruecklich NICHT durch
    # #1435 E3b aufgehoben.
    "thunder": "TH: — Grammatikform mit Doppelpunkt (Register: TH)",
}

# Grammatik-Zusaetze, die ein Kuerzel tragen darf, ohne vom Register
# abzuweichen. '24+' markiert das 24-Stunden-Fenster beim Neuschnee, ':'
# trennt eine Stufenangabe ab. Beides ist Format, kein Registerfeld.
GRAMMAR_SUFFIXES = ("24+",)
GRAMMAR_TRAILING = (":",)


def _strip_grammar(symbol: str) -> str:
    out = symbol
    for suffix in GRAMMAR_SUFFIXES:
        if out.endswith(suffix):
            out = out[: -len(suffix)]
    for trailing in GRAMMAR_TRAILING:
        out = out.rstrip(trailing)
    return out


# ---------------------------------------------------------------------------
# Ableitung: DailyForecast-Feld -> tatsaechlich erzeugtes Symbol
# ---------------------------------------------------------------------------

def _probe_value(field: dataclasses.Field):
    """Probewert passend zum Feldtyp; None = Feld nicht abtastbar."""
    annotation = str(field.type)
    if "bool" in annotation:
        return None
    if "tuple" in annotation:
        return None
    if "int" in annotation and "float" not in annotation:
        return 3
    if "float" in annotation:
        return 1234.0
    return None


def _wintersport_symbol_by_field() -> dict[str, str]:
    """Fuer jedes DailyForecast-Feld: welches Symbol erzeugt `_wintersport()`?

    Rein verhaltensbasiert — pro Durchlauf wird GENAU EIN Feld gesetzt und
    beobachtet, welches Token entsteht. Kein Quelltext-Parsing, keine Liste.
    """
    mapping: dict[str, str] = {}
    for field in dataclasses.fields(DailyForecast):
        value = _probe_value(field)
        if value is None:
            continue
        day = DailyForecast(**{field.name: value})
        tokens = _wintersport(day, {}, "evening")
        if not tokens:
            continue
        assert len(tokens) == 1, (
            f"Feld {field.name!r} erzeugt mehr als ein Wintersport-Token: "
            f"{[t.symbol for t in tokens]!r} — die Ratsche kann Symbol und "
            "Groesse dann nicht mehr eindeutig zuordnen."
        )
        mapping[field.name] = tokens[0].symbol
    return mapping


def _register_metric_by_forecast_field() -> dict[str, object]:
    """DailyForecast-Feldname -> Registermetrik (ueber dp_field/summary_fields)."""
    out: dict[str, object] = {}
    for metric in get_all_metrics():
        names = {metric.dp_field} | set((metric.summary_fields or {}).values())
        for name in names:
            if name:
                out.setdefault(name, metric)
    return out


# ---------------------------------------------------------------------------
# Selbstpruefung der Ratsche
# ---------------------------------------------------------------------------

def test_ratchet_inspects_the_code_of_this_worktree():
    """#1409: der Pruefling muss aus DIESEM Arbeitsbaum kommen."""
    module_path = Path(builder_mod.__file__).resolve()
    assert str(module_path).startswith(str(REPO_ROOT)), (
        "Die Ratsche prueft nicht den Code dieses Arbeitsbaums, sondern "
        f"{module_path} (erwartet unterhalb {REPO_ROOT})."
    )


def test_ratchet_actually_has_material_to_check():
    """Nichtstun ist kein Bestehen: die Ratsche behauptet ihre Trefferzahl."""
    probed = _wintersport_symbol_by_field()
    register = _register_metric_by_forecast_field()
    positional_ws = [s for s, cat in POSITIONAL if cat == "wintersport"]

    assert len(probed) >= 3, (
        "Die Ratsche hat weniger als 3 Wintersport-Token gefunden — sie "
        f"prueft praktisch nichts. Gefunden: {probed!r}"
    )
    assert len(positional_ws) >= 3, (
        f"POSITIONAL fuehrt keinen Wintersport-Block mehr: {POSITIONAL!r}"
    )
    assert len(PRIORITY) > 0 and len(DROP_ORDER) > 0, (
        "PRIORITY/DROP_ORDER sind leer — nichts zu pruefen."
    )
    assert len(SMS_SYMBOL_BY_METRIC) > 0, "SMS_SYMBOL_BY_METRIC ist leer."
    assert len(register) > 0, "Das Register liefert keine Feldzuordnung."

    checkable = [
        f for f in probed
        if f not in EXEMPT_FORECAST_FIELDS and f in register
    ]
    assert len(checkable) >= 3, (
        "Nach Abzug der Ausnahmen bleiben weniger als 3 pruefbare Groessen "
        f"uebrig — die Ratsche waere zahnlos. Pruefbar: {checkable!r}, "
        f"abgetastet: {probed!r}, Ausnahmen: {sorted(EXEMPT_FORECAST_FIELDS)!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 Kern: Symbole der Token-Erzeugung gegen das Register
# ---------------------------------------------------------------------------

def test_wintersport_token_symbols_match_register():
    """Jedes im Wintersport-Block erzeugte Kuerzel entspricht dem Register."""
    probed = _wintersport_symbol_by_field()
    register = _register_metric_by_forecast_field()

    deviations: list[str] = []
    checked = 0
    for field_name, symbol in sorted(probed.items()):
        if field_name in EXEMPT_FORECAST_FIELDS:
            continue
        metric = register.get(field_name)
        if metric is None:
            deviations.append(
                f"  - Feld {field_name!r} (Kuerzel {symbol!r}): keine "
                "Registergroesse gefunden und keine dokumentierte Ausnahme "
                f"in EXEMPT_FORECAST_FIELDS ({sorted(EXEMPT_FORECAST_FIELDS)!r})"
            )
            continue
        expected = get_sms_code(metric.id)
        checked += 1
        if _strip_grammar(symbol) != expected:
            deviations.append(
                f"  - {metric.label_de} ({metric.id}): gefunden {symbol!r}, "
                f"erwartet {expected!r}"
                + (f" (+ Grammatik-Suffix '24+' -> {expected}24+)"
                   if symbol.endswith("24+") else "")
            )

    assert checked >= 3, (
        f"Nur {checked} Groessen geprueft — zu wenig, die Ratsche misst nichts."
    )
    assert not deviations, (
        f"SMS-Kuerzel weichen vom Wetter-Register ab ({checked} Groessen "
        "geprueft, siehe docs/specs/modules/fix_1435_e3b_sms_kuerzel.md):\n"
        + "\n".join(deviations)
    )


def test_sms_symbol_by_metric_matches_register():
    """`SMS_SYMBOL_BY_METRIC` (Quelle fuer Schwellwerte #624 und Abwahl #944)
    darf nicht vom Register abweichen."""
    deviations: list[str] = []
    checked = 0
    labels = {m.id: m.label_de for m in get_all_metrics()}

    for metric_id, symbol in sorted(SMS_SYMBOL_BY_METRIC.items()):
        if metric_id in EXEMPT_METRIC_IDS:
            continue
        expected = get_sms_code(metric_id)
        if not expected:
            deviations.append(
                f"  - {metric_id!r} (Kuerzel {symbol!r}): das Register kennt "
                "diese Groesse nicht bzw. fuehrt keinen sms_code"
            )
            continue
        checked += 1
        if _strip_grammar(symbol) != expected:
            deviations.append(
                f"  - {labels.get(metric_id, metric_id)} ({metric_id}): "
                f"gefunden {symbol!r}, erwartet {expected!r}"
            )

    assert checked >= 4, (
        f"Nur {checked} Zuordnungen geprueft — zu wenig. "
        f"SMS_SYMBOL_BY_METRIC={SMS_SYMBOL_BY_METRIC!r}"
    )
    assert not deviations, (
        f"SMS_SYMBOL_BY_METRIC weicht vom Wetter-Register ab ({checked} "
        "Zuordnungen geprueft):\n" + "\n".join(deviations)
    )


# ---------------------------------------------------------------------------
# AC-9: die drei Tabellen muessen GEMEINSAM ziehen
# ---------------------------------------------------------------------------

def test_all_symbol_tables_carry_the_same_wintersport_symbols():
    """Aendert eine der drei Tabellen ein Kuerzel ohne die anderen, faellt es
    hier auf — genau das Risiko einer unvollstaendigen Umbenennung."""
    probed = set(_wintersport_symbol_by_field().values())
    positional_ws = {s for s, cat in POSITIONAL if cat == "wintersport"}
    default_cfg = {s.symbol for s in _wintersport_default_config()}

    assert probed, "Kein einziges Wintersport-Token abgetastet."

    assert probed == positional_ws, (
        "POSITIONAL und die tatsaechlich erzeugten Token stimmen nicht "
        f"ueberein.\n  erzeugt:    {sorted(probed)!r}\n"
        f"  POSITIONAL: {sorted(positional_ws)!r}\n"
        f"  nur erzeugt: {sorted(probed - positional_ws)!r}\n"
        f"  nur POSITIONAL: {sorted(positional_ws - probed)!r}"
    )

    missing_priority = sorted(probed - set(PRIORITY))
    assert not missing_priority, (
        f"Kuerzel {missing_priority!r} fehlen in PRIORITY — "
        "`PRIORITY[sym]` (builder.py) laeuft dann in einen KeyError und die "
        "SMS-Erzeugung stuerzt ab."
    )

    missing_drop = sorted(probed - set(DROP_ORDER))
    assert not missing_drop, (
        f"Kuerzel {missing_drop!r} fehlen in DROP_ORDER (render.py) — sie "
        "wuerden bei zu langer SMS nie gekuerzt."
    )

    missing_default = sorted(probed - default_cfg)
    assert not missing_default, (
        f"Kuerzel {missing_default!r} fehlen in "
        "_wintersport_default_config() (trip_result.py) — der CLI-Pfad "
        f"liefert dann {sorted(default_cfg)!r}."
    )


# ---------------------------------------------------------------------------
# Issue #1824 / Adversary-Fix-Loop F001: dieselbe Zusicherung fuer den Block
# der 14 erweiterten Metriken (#1660 B).
# ---------------------------------------------------------------------------

def _extended_block_symbols() -> set[str]:
    """Die Kuerzel, die ``build_token_line()`` fuer die 14 erweiterten
    Metriken TATSAECHLICH erzeugt — abgetastet, nicht getippt (Bauprinzip 2
    dieser Datei). Genau diese Zeichenketten legt der Renderer zur Laufzeit
    den drei Tabellen vor.
    """
    day = DailyForecast(
        humidity_hourly=(HourlyValue(14, 88),),
        dewpoint_hourly=(HourlyValue(9, 7),),
        cape_hourly=(HourlyValue(16, 1200),),
        uv_hourly=(HourlyValue(13, 8),),
        cloud_total_hourly=(HourlyValue(12, 80),),
        cloud_low_hourly=(HourlyValue(10, 40),),
        cloud_mid_hourly=(HourlyValue(11, 55),),
        cloud_high_hourly=(HourlyValue(9, 20),),
        visibility_hourly=(HourlyValue(11, 600),),
        freezing_level_hourly=(HourlyValue(12, 2400),),
        wind_direction_sector="NW",
        precip_type_dominant="S",
        sunshine_hours=6.4,
        pressure_avg_hpa=1013.4,
    )
    line = build_token_line(
        NormalizedForecast(days=(day,)),
        build_extended_metric_specs(set(SMS_NULLFORM_METRIC_IDS)),
        report_type="evening", stage_name="E1",
    )
    erwartet = {SMS_SYMBOL_BY_METRIC[mid] for mid in SMS_NULLFORM_METRIC_IDS}
    return {t.symbol for t in line.tokens} & erwartet


def test_extended_metric_tables_carry_the_symbol_the_builder_emits():
    """Issue #1824 (B) verschob den Grammatik-Doppelpunkt der Kuerzel
    ``WD``/``PT`` ins Symbol. Die drei Tabellen fuehren das Symbol als
    LITERAL und mussten mitgezogen werden.

    Warum diese Zusicherung strukturell ist und nicht am Verhalten haengt:
    fuer ``DROP_ORDER`` und ``POSITIONAL`` gibt es Verhaltens-Waechter
    (``tests/tdd/test_sms_letter_value_separator.py``, Kuerzung bzw.
    Reihenfolge der fertigen Zeile). Fuer ``PRIORITY`` gibt es keinen: der
    einzige Leser von ``Token.priority`` ist der Last-Resort-Schritt in
    ``render.py::_truncate()``, und dorthin gelangen die 14 Kuerzel nie,
    weil ``DROP_ORDER`` sie vorher entfernt. Gemessen (2026-08-14): mit
    absichtlich verfaelschtem ``PRIORITY``-Schluessel sind die gerenderten
    Zeilen ueber 175 Zeichenbudgets hinweg BYTEGLEICH. Der Eintrag ist
    zweite Verteidigungslinie — sichtbar wird sein Fehlen erst, wenn auch
    ``DROP_ORDER`` bricht. Genau dafuer steht dieser Waechter.
    """
    emitted = _extended_block_symbols()

    assert len(emitted) >= 10, (
        "Weniger als 10 der 14 erweiterten Kuerzel abgetastet — der Waechter "
        f"prueft praktisch nichts. Gefunden: {sorted(emitted)!r}"
    )

    for tabelle, inhalt, folge in (
        ("PRIORITY (builder.py)", set(PRIORITY),
         "`PRIORITY.get(sym, 5)` faellt still auf den Standardwert zurueck — "
         "die Kuerzung raeumt dann in der falschen Rangfolge ab"),
        ("POSITIONAL (builder.py)", {s for s, _cat in POSITIONAL},
         "`POS_INDEX.get(...)` greift den Fallback 99 — das Kuerzel rutscht "
         "ans Zeilenende, hinter die System-Bloecke"),
        ("DROP_ORDER (render.py)", set(DROP_ORDER),
         "`_drop_first()` findet das Token nie — es faellt unter "
         "Kuerzungsdruck NIE mehr an seiner Stelle"),
    ):
        fehlend = sorted(emitted - inhalt)
        assert not fehlend, (
            f"Der Builder erzeugt {fehlend!r}, aber {tabelle} kennt diese "
            f"Zeichenkette nicht. Folge: {folge}.\n"
            f"  erzeugt: {sorted(emitted)!r}"
        )


@pytest.mark.parametrize("legacy_symbol", ["SN", "SN24+", "SFL", "WC"])
def test_legacy_snow_symbols_are_absent_from_all_tables(legacy_symbol: str):
    """#1435 E3b: die drei Alt-Kuerzel duerfen in keiner Metrik-Tabelle mehr
    stehen. ('SN' bleibt ausschliesslich die amtliche Schneewarnung in
    `hazard_symbols.py` — eine andere Tabelle, hier nicht geprueft.)

    Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    fix_1887_e6a_sms_kuerzel_register.md, AC-4): 'WC' verdoppelte
    nachweislich 'FK' (identisches Feld, Fenster, Aggregation) und entfaellt
    ERSATZLOS — kein Ersatzkuerzel wie bei SN/SN24+/SFL (die durch SD/NS24+/
    SL abgeloest wurden)."""
    positional_symbols = {s for s, _cat in POSITIONAL}
    default_cfg = {s.symbol for s in _wintersport_default_config()}

    found_in = []
    if legacy_symbol in PRIORITY:
        found_in.append("builder.PRIORITY")
    if legacy_symbol in positional_symbols:
        found_in.append("builder.POSITIONAL")
    if legacy_symbol in DROP_ORDER:
        found_in.append("render.DROP_ORDER")
    if legacy_symbol in default_cfg:
        found_in.append("trip_result._wintersport_default_config")
    if legacy_symbol in set(SMS_SYMBOL_BY_METRIC.values()):
        found_in.append("sms_trip.SMS_SYMBOL_BY_METRIC")

    assert not found_in, (
        f"Alt-Kuerzel {legacy_symbol!r} steht noch in: {found_in!r}. "
        "Erwartet werden die Registerwerte SD (Schneehoehe), NS24+ "
        "(Neuschnee), SL (Schneefallgrenze)."
    )


# ---------------------------------------------------------------------------
# Fuenfte Pruefstelle — Issue #1856 (#1435 Etappe E7), AC-1/AC-7.
# SPEC: docs/specs/modules/fix_1856_e7_metrik_listen_waechter.md
#
# Kein Kuerzel bezeichnet zwei VERSCHIEDENE Groessen. Zwei Ausgabewege, zwei
# getrennte Pruefungen, nie gemischt: die Trip-SMS liest
# SMS_SYMBOL_BY_METRIC/SMS_MULTI_SYMBOLS_BY_METRIC, Vergleichs- und Alarm-SMS
# lesen `get_sms_code()` direkt (comparison.py:647, alert/render.py:93).
#
# Die vier Pruefstellen oberhalb bleiben unveraendert (AC-7) — auch ihre
# Import-Zeilen. Der Kollisions-Kern wird deshalb LOKAL importiert: er lebt in
# `tests/helpers/metrik_listen_scan.py`, damit er gegen erfundene Eingaben
# pruefbar ist (dritte Funktion unten); ein Modul-Import wuerde diese Datei
# bei jedem Fehler dort komplett unauffuehrbar machen.
#
# NICHT geprueft wird Gleichheit zwischen den Wegen: die drei Abweichungen
# (temperature K/D, wind_chill FK/FD/WC, temperature_night N) sind
# PO-Entscheide (#1415/#1450/#1484), eine Gleichheitspruefung waere nach dem
# ersten Lauf taub. Gueltigkeit faellt ueber AC-2/AC-4 an.
# ---------------------------------------------------------------------------

def _kuerzel_trip_sms_weg() -> dict[str, str]:
    """Metrik-Kennung -> das Kuerzel, das die Trip-Kurzform sendet.

    Gruppiert nach KENNUNG, nicht nach Kuerzel-Wert: 'TH:' steht sowohl in
    SMS_SYMBOL_BY_METRIC als auch in SMS_MULTI_SYMBOLS_BY_METRIC, beide Male
    fuer dieselbe Groesse `thunder` (dedupliziert auch von /api/sms-symbols,
    s. tests/tdd/test_sms_snow_symbols.py). Wer nach Wert gruppiert, meldet
    beim ersten Lauf eine Kollision, die keine ist.
    """
    from app.metric_catalog import (
        _METRICS, _kurzform_kuerzel, SMS_MULTI_SYMBOLS_BY_METRIC,
    )
    codes = {m.id: m.sms_code for m in _METRICS}
    ids = set(SMS_SYMBOL_BY_METRIC) | set(SMS_MULTI_SYMBOLS_BY_METRIC)
    kuerzel = {mid: _kurzform_kuerzel(mid, codes[mid]) for mid in ids}
    return {mid: k for mid, k in kuerzel.items() if k}


def test_trip_sms_kuerzel_bezeichnen_je_genau_eine_groesse():
    """AC-1(b), Trip-SMS-Weg."""
    from tests.helpers.metrik_listen_scan import finde_kuerzel_kollisionen

    kuerzel = _kuerzel_trip_sms_weg()
    assert len(kuerzel) >= 20, (
        f"Nur {len(kuerzel)} Kuerzel geprueft — zu wenig, die Pruefung misst "
        f"nichts. Gemessen zum Stand der Spec: 26. {kuerzel!r}"
    )
    assert kuerzel.get("thunder") == "TH", (
        "Fuer `thunder` steht nicht genau ein Kuerzel — vermutlich wurde nach "
        f"Kuerzel-Wert statt nach Metrik-Kennung gruppiert: {kuerzel!r}"
    )

    kollisionen = finde_kuerzel_kollisionen(kuerzel)
    assert kollisionen == [], (
        "Ein Kuerzel der Trip-Kurzform bezeichnet zwei verschiedene "
        "Wettergroessen:\n" + "\n".join(kollisionen)
    )


def test_register_kuerzel_bezeichnen_je_genau_eine_groesse():
    """AC-1(b), Register-Weg (Vergleichs-SMS, Alarm-SMS)."""
    from app.metric_catalog import _METRICS
    from tests.helpers.metrik_listen_scan import finde_kuerzel_kollisionen

    kuerzel = {m.id: m.sms_code for m in _METRICS if m.sms_code}
    assert len(kuerzel) >= 25, (
        f"Nur {len(kuerzel)} Register-Kuerzel geprueft — zu wenig. Gemessen "
        f"zum Stand der Spec: 27 von 28 Groessen ({kuerzel!r})"
    )

    kollisionen = finde_kuerzel_kollisionen(kuerzel)
    assert kollisionen == [], (
        "Ein Register-Kuerzel (`sms_code`) bezeichnet zwei verschiedene "
        "Wettergroessen:\n" + "\n".join(kollisionen)
    )


def test_kollisionspruefung_beisst_zu_und_ueberspringt_leere_kuerzel():
    """Wirksamkeitsnachweis fuer AC-1: beide Pruefungen oben sind heute gruen
    (0 Kollisionen) — ohne diesen Fall belegten sie nur, dass sie durchlaufen.

    Zugleich der gemessene zweite Fallstrick: `confidence` fuehrt einen LEEREN
    `sms_code` (selectable=False, PO-Entscheid #710). Leere Kuerzel duerfen
    nicht gruppiert werden, sonst meldet der Waechter zwei Luecken als
    Doppelvergabe, sobald eine zweite kuerzellose Groesse hinzukommt.
    """
    from tests.helpers.metrik_listen_scan import finde_kuerzel_kollisionen

    befunde = finde_kuerzel_kollisionen({
        "erfundene_groesse_a": "XY",
        "erfundene_groesse_b": "XY",
        "erfundene_groesse_c": "YZ",
        "ohne_kuerzel_eins": "",
        "ohne_kuerzel_zwei": "",
    })
    text = "\n".join(befunde)

    assert len(befunde) == 1, (
        f"Erwartet genau eine gemeldete Doppelvergabe, bekommen: {befunde!r}"
    )
    for kennung in ("erfundene_groesse_a", "erfundene_groesse_b"):
        assert kennung in text, (
            f"Die Doppelvergabe von 'XY' nennt {kennung!r} nicht: {text!r}"
        )
    for unbeteiligt in ("erfundene_groesse_c", "ohne_kuerzel_eins",
                        "ohne_kuerzel_zwei"):
        assert unbeteiligt not in text, (
            f"{unbeteiligt!r} ist keine Kollision, wird aber gemeldet: {text!r}"
        )


# ---------------------------------------------------------------------------
# Fix #1887 E6 Scheibe A — AC-1, AC-4, AC-9.
# SPEC: docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md
#
# Sechs Groessen, deren Trip-SMS-Kuerzel bisher NUR in der handgetippten
# SMS_MULTI_SYMBOLS_BY_METRIC stand, bekommen ein Register-Feld
# `sms_multi_symbols`; die Tabelle wird zur reinen Ableitung. 'WC'
# (wind_chill) entfaellt ersatzlos (PO-Entscheid, verdoppelt nachweislich
# 'FK').
# ---------------------------------------------------------------------------

# AC-9: von Hand getippt -- darf NICHT aus SMS_MULTI_SYMBOLS_BY_METRIC oder
# MetricDefinition.sms_multi_symbols selbst berechnet werden, sonst ist die
# Zusicherung eine Tautologie (Mutations-Gegenprobe Punkt 1).
#
# Fix #1926 (PO-Konsistenzentscheid 2026-08-17): temperature_day_low K->L,
# wind_chill_day_low FK->FL (Kollisionsvermeidung, kein Sprach-Thema --
# ADR-0042 Klasse 1 bleibt von Sprachfragen ausgenommen).
_AC9_ERWARTUNG: dict[str, str] = {
    "temperature_day_low": "L",
    "temperature_day_high": "D",
    "temperature_night": "N",
    "wind_chill_day_low": "FL",
    "wind_chill_day_high": "FD",
    "wind_chill_night": "FN",
}


def test_sms_multi_symbols_feld_traegt_die_getippte_ac9_erwartungstabelle():
    """AC-9: vertauscht das Register eine Zuordnung, wird dieser Waechter rot
    und nennt die betroffene Groesse beim Namen (Mutations-Gegenprobe Punkt
    1)."""
    from app.metric_catalog import _METRICS_BY_ID

    abweichungen = []
    for metric_id, erwartetes_kuerzel in _AC9_ERWARTUNG.items():
        metrik = _METRICS_BY_ID.get(metric_id)
        assert metrik is not None, (
            f"Register kennt {metric_id!r} nicht (mehr) — Testvoraussetzung "
            "verletzt."
        )
        tatsaechlich = getattr(metrik, "sms_multi_symbols", ())
        if tatsaechlich != (erwartetes_kuerzel,):
            abweichungen.append(
                f"  - {metric_id}: erwartet {(erwartetes_kuerzel,)!r}, "
                f"gefunden {tatsaechlich!r}"
            )

    assert not abweichungen, (
        "MetricDefinition.sms_multi_symbols weicht von der getippten "
        "AC-9-Erwartungstabelle ab:\n" + "\n".join(abweichungen)
    )


def test_sms_multi_symbols_by_metric_ableitung_stimmt_mit_ac9_erwartung_ueberein():
    """AC-1, ergaenzender Wertevergleich: die ABGELEITETE Tabelle
    SMS_MULTI_SYMBOLS_BY_METRIC muss dieselben sechs Werte fuehren wie die
    getippte AC-9-Tabelle -- unabhaengig davon, ob die Ableitung ueberhaupt
    schon existiert."""
    from app.metric_catalog import SMS_MULTI_SYMBOLS_BY_METRIC

    abweichungen = []
    for metric_id, erwartetes_kuerzel in _AC9_ERWARTUNG.items():
        gefunden = SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id)
        if gefunden != (erwartetes_kuerzel,):
            abweichungen.append(
                f"  - {metric_id}: erwartet {(erwartetes_kuerzel,)!r}, "
                f"SMS_MULTI_SYMBOLS_BY_METRIC liefert {gefunden!r}"
            )
    assert not abweichungen, (
        "SMS_MULTI_SYMBOLS_BY_METRIC weicht von der getippten "
        "AC-9-Erwartungstabelle ab:\n" + "\n".join(abweichungen)
    )

    assert "wind_chill" not in SMS_MULTI_SYMBOLS_BY_METRIC, (
        "'wind_chill' fuehrt weiterhin einen Eintrag in "
        "SMS_MULTI_SYMBOLS_BY_METRIC — 'WC' sollte ersatzlos entfallen "
        f"(PO-Entscheid): {SMS_MULTI_SYMBOLS_BY_METRIC.get('wind_chill')!r}"
    )


# Die sechs Groessen, fuer die AC-1 ein hartkodiertes Kuerzel in der
# Dict-DEFINITION verbietet -- 'wind_chill' zaehlt bewusst NICHT dazu, weil
# es nach dieser Scheibe ueberhaupt keinen sms_multi_symbols-Eintrag mehr hat.
_AC1_SECHS_GROESSEN = frozenset(_AC9_ERWARTUNG)


def test_sms_multi_symbols_by_metric_ist_ableitung_kein_literal_fuer_die_sechs_groessen():
    """AC-1: an der Zuweisung von SMS_MULTI_SYMBOLS_BY_METRIC darf fuer die
    sechs betroffenen Groessen kein Dict-Literal mit getippten Kuerzeln mehr
    stehen -- die Tabelle muss aus dem Register (MetricDefinition.
    sms_multi_symbols) abgeleitet werden (Muster SMS_SYMBOL_BY_METRIC seit
    E3b). Kein Regex ueber Quelltext -- echter AST, analog zu
    tests/helpers/metrik_listen_scan.py::_seiten()."""
    quelle = Path(catalog_mod.__file__).resolve().read_text(encoding="utf-8")
    baum = ast.parse(quelle, filename=catalog_mod.__file__)

    zuweisung = None
    for knoten in ast.walk(baum):
        if (isinstance(knoten, ast.Assign)
                and any(isinstance(t, ast.Name)
                        and t.id == "SMS_MULTI_SYMBOLS_BY_METRIC"
                        for t in knoten.targets)):
            zuweisung = knoten
            break
        # Die Zuweisung traegt eine Typannotation (`dict[str, tuple[str, ...]]`)
        # -- das ist ast.AnnAssign, nicht ast.Assign.
        if (isinstance(knoten, ast.AnnAssign)
                and isinstance(knoten.target, ast.Name)
                and knoten.target.id == "SMS_MULTI_SYMBOLS_BY_METRIC"
                and knoten.value is not None):
            zuweisung = knoten
            break
    assert zuweisung is not None, (
        "Testvoraussetzung verletzt: keine Zuweisung an "
        "SMS_MULTI_SYMBOLS_BY_METRIC gefunden — wurde der Name geaendert?"
    )

    def _ist_literale_zeichenkette(wert: ast.expr) -> bool:
        return isinstance(wert, ast.Constant) and isinstance(wert.value, str)

    def _ist_literales_tupel(wert: ast.expr) -> bool:
        return (isinstance(wert, ast.Tuple)
                and bool(wert.elts)
                and all(_ist_literale_zeichenkette(e) for e in wert.elts))

    literale_treffer = []
    for teilbaum in ast.walk(zuweisung.value):
        if not isinstance(teilbaum, ast.Dict):
            continue
        for schluessel, wert in zip(teilbaum.keys, teilbaum.values):
            if not (isinstance(schluessel, ast.Constant)
                    and schluessel.value in _AC1_SECHS_GROESSEN):
                continue
            if _ist_literale_zeichenkette(wert) or _ist_literales_tupel(wert):
                literale_treffer.append(schluessel.value)

    assert not literale_treffer, (
        "SMS_MULTI_SYMBOLS_BY_METRIC traegt fuer diese Groessen noch ein "
        f"getipptes Kuerzel statt einer Ableitung aus dem Register: "
        f"{sorted(literale_treffer)!r}. Nach Implementation Details Punkt 1 "
        "der Spec muss die Tabelle eine Comprehension ueber "
        "MetricDefinition.sms_multi_symbols sein (Muster SMS_SYMBOL_BY_METRIC "
        "seit E3b)."
    )


def test_sms_symbols_endpoint_fuehrt_wind_chill_nicht_mehr():
    """AC-4: /api/sms-symbols serialisiert SMS_MULTI_SYMBOLS_BY_METRIC
    generisch (kein eigener Code-Pfad, s. Spec) — nach dem Wegfall von 'WC'
    verschwindet 'wind_chill' vollstaendig aus der Metrik-Liste statt mit
    leerem sms_symbols-Eintrag zu erscheinen (AC-4, Spec Punkt 7)."""
    from api.routers.config import get_sms_symbols

    antwort = get_sms_symbols()
    metrik_ids = {eintrag["metric_id"] for eintrag in antwort["metrics"]}
    alle_symbole = {
        symbol for eintrag in antwort["metrics"] for symbol in eintrag["sms_symbols"]
    }

    assert "wind_chill" not in metrik_ids, (
        "'wind_chill' erscheint weiterhin in /api/sms-symbols, obwohl 'WC' "
        f"ersatzlos entfallen ist: {sorted(metrik_ids)!r}"
    )
    assert "WC" not in alle_symbole, (
        f"Kuerzel 'WC' erscheint weiterhin in /api/sms-symbols: "
        f"{antwort['metrics']!r}"
    )


# ---------------------------------------------------------------------------
# Fix #1926 (PO-Freigabe 2026-08-17) -- AC-1: col_label MUSS englisch sein
# (ADR-0042 Klasse 2). Sechs nach dem ADR-Beschluss (2026-08-02) eingefuehrte
# col_label-Werte verletzten die Regel.
# SPEC: docs/specs/modules/fix_1926_metrik_kuerzel_englisch.md
# ---------------------------------------------------------------------------

# Von Hand getippt -- Mutations-Gegenprobe analog _AC9_ERWARTUNG oben (darf
# NICHT aus MetricDefinition.col_label selbst berechnet werden).
_AC1_COL_LABEL_ERWARTUNG: dict[str, str] = {
    "temperature_night": "Night",
    "temperature_day_low": "DayMin",
    "temperature_day_high": "DayMax",
    "wind_chill_night": "NightF",
    "wind_chill_day_low": "DayMinF",
    "wind_chill_day_high": "DayMaxF",
}


def test_col_label_der_sechs_temperaturgroessen_ist_englisch():
    """AC-1: getippte Erwartungstabelle fuer die sechs Groessen, deren
    col_label nach dem ADR-0042-Beschluss deutsch eingefuehrt wurde."""
    from app.metric_catalog import _METRICS_BY_ID

    abweichungen = []
    for metric_id, erwartet in _AC1_COL_LABEL_ERWARTUNG.items():
        metrik = _METRICS_BY_ID.get(metric_id)
        assert metrik is not None, (
            f"Register kennt {metric_id!r} nicht (mehr) — Testvoraussetzung "
            "verletzt."
        )
        if metrik.col_label != erwartet:
            abweichungen.append(
                f"  - {metric_id}: erwartet {erwartet!r}, gefunden "
                f"{metrik.col_label!r}"
            )
    assert not abweichungen, (
        "col_label weicht von der englischen ADR-0042-Erwartung ab:\n"
        + "\n".join(abweichungen)
    )


# Negativliste statt Positivliste (Spec Known Limitations): eine
# Positivliste bekannter englischer Fachbegriffe braeuchte laufende Pflege
# pro neuem Wort; die Negativliste trifft nur die vier tatsaechlich
# aufgetretenen deutschen Wortbestandteile und laesst Fachbegriffe wie
# CAPE/UV unbehelligt (keines der Fragmente kommt darin vor, gemessen
# gegen alle 32 heutigen col_label-Werte).
_GERMAN_COL_LABEL_FRAGMENTS = ("nacht", "tag", "grenze", "grad")


def test_col_label_traegt_keine_deutschen_wortbestandteile():
    """AC-1, generische Ratsche (Spec Test Plan Punkt 1): verhindert, dass
    ein KUENFTIGER Katalog-Eintrag erneut ein deutsches col_label
    einfuehrt."""
    from app.metric_catalog import _METRICS

    treffer = []
    for m in _METRICS:
        label = (m.col_label or "").lower()
        for fragment in _GERMAN_COL_LABEL_FRAGMENTS:
            if fragment in label:
                treffer.append(
                    f"  - {m.id}: col_label={m.col_label!r} enthaelt "
                    f"deutschen Wortbestandteil {fragment!r}"
                )
    assert not treffer, (
        "col_label verletzt ADR-0042 Klasse 2 (muss englisch sein, "
        "<=6 Zeichen):\n" + "\n".join(treffer)
    )


# ---------------------------------------------------------------------------
# Fix #1926 -- AC-5: tote compact_label-Literale (cape/snowfall_limit/
# freezing_level) muessen mit dem zur Laufzeit tatsaechlich abgeleiteten
# Wert uebereinstimmen (kein abweichendes Quelltext-Literal mehr).
# ---------------------------------------------------------------------------

def test_compact_label_quelltext_literal_folgt_der_ableitung_bei_toten_kuerzeln():
    """AC-5: cape/snowfall_limit/freezing_level fuehren zur LAUFZEIT bereits
    das abgeleitete Kuerzel (compact_label wird durch die
    List-Comprehension am Ende von metric_catalog.py ueberschrieben, s.
    _kurzform_kuerzel()) -- das QUELLTEXT-Literal darf davon nicht mehr
    abweichen (reine Lesbarkeit, kein funktionaler Effekt). Echter AST-Zugriff
    auf die MetricDefinition(...)-Aufrufe, kein Regex."""
    from app.metric_catalog import _kurzform_kuerzel

    ziel_ids = ("cape", "snowfall_limit", "freezing_level")
    quelle = Path(catalog_mod.__file__).resolve().read_text(encoding="utf-8")
    baum = ast.parse(quelle, filename=catalog_mod.__file__)

    literale: dict[str, tuple[str, str]] = {}
    for knoten in ast.walk(baum):
        if not (isinstance(knoten, ast.Call)
                and isinstance(knoten.func, ast.Name)
                and knoten.func.id == "MetricDefinition"):
            continue
        kwargs = {kw.arg: kw.value for kw in knoten.keywords if kw.arg}
        id_node = kwargs.get("id")
        if not (isinstance(id_node, ast.Constant) and id_node.value in ziel_ids):
            continue
        cl_node = kwargs.get("compact_label")
        sc_node = kwargs.get("sms_code")
        assert (isinstance(cl_node, ast.Constant)
                and isinstance(sc_node, ast.Constant)), (
            f"{id_node.value!r}: compact_label/sms_code sind keine "
            "literalen Konstanten im Quelltext — Testvoraussetzung verletzt."
        )
        literale[id_node.value] = (cl_node.value, sc_node.value)

    assert set(literale) == set(ziel_ids), (
        f"Nicht alle Ziel-Groessen im Quelltext gefunden: {sorted(literale)!r} "
        f"statt {sorted(ziel_ids)!r} — wurden Namen/Struktur geaendert?"
    )

    abweichungen = []
    for metric_id, (cl_literal, sms_code) in literale.items():
        abgeleitet = _kurzform_kuerzel(metric_id, sms_code)
        if cl_literal != abgeleitet:
            abweichungen.append(
                f"  - {metric_id}: Quelltext-Literal compact_label={cl_literal!r}, "
                f"zur Laufzeit abgeleitet wird aber {abgeleitet!r} (aus "
                f"sms_code={sms_code!r}) — totes, abweichendes Literal."
            )
    assert not abweichungen, (
        "compact_label-Quelltext-Literal weicht vom zur Laufzeit tatsaechlich "
        "abgeleiteten Wert ab (AC-5):\n" + "\n".join(abweichungen)
    )


# ---------------------------------------------------------------------------
# Fix #1926 -- AC-8 (RED-Phase-Korrektur 2026-08-17, PO-Entscheid): die
# Schichtgrenze `output/tokens/builder.py` <-> `app/metric_catalog.py` bleibt
# architektonisch bestehen (Entkopplungsfrage ausgegliedert nach #1934).
# `builder.py` (`PRIORITY`/`POSITIONAL`/`build_token_line()`, Zeilen
# ~60/96/325-330/378/426) fuehrt fuer die sechs Temperatur-Positionaltoken
# (N/K/D/FN/FK/FD) und fuer die Invers-Min-Groesse VS/NL BEWUSST eigene,
# vom Register unabhaengige Literale (#1435 E3b) -- dieselbe Kategorie
# Handarbeit, die 'WC' (Fix #1887 E6) bereits entfernt und 'FN' (#1660 A)
# bereits eingefuehrt hat. Diese Tabelle macht die drei fuer #1926
# betroffenen Faelle explizit, statt sie stillschweigend unbewacht zu
# lassen -- vorher gab es dafuer KEINE Ratsche: `_wintersport()`
# (oben, `test_wintersport_token_symbols_match_register`) deckt nur
# SD/NS24+/SL/AV ab, nicht die Positional-/Invers-Min-Bloecke.
# alt/neu je Groesse -- 'alt' ist der Wert, den builder.py HEUTE noch
# hartkodiert; 'neu' der Zielwert nach der (GREEN-)Handnachfuehrung.
_AC8_BUILDER_LITERALE_ERWARTUNG: dict[str, tuple[str, str]] = {
    "temperature_day_low": ("K", "L"),
    "wind_chill_day_low": ("FK", "FL"),
    "freezing_level": ("NL", "FZ"),
}


def test_builder_positionaltoken_literale_noch_nicht_auf_fix_1926_nachgezogen():
    """AC-8: `build_token_line()`s TATSAECHLICH erzeugter Token-Text fuer
    temperature_day_low/wind_chill_day_low/freezing_level muss die NEUEN
    Kuerzel (L/FL/FZ) tragen -- rot, solange builder.py noch die alten
    Literale (K/FK/NL) fuehrt (GREEN-Arbeit, s. Spec AC-8 Implementation
    Details). 'D'/'FD' werden bewusst explizit ABGEWAEHLT: ohne Gegenwert
    wuerden K/D bzw. FK/FD sonst zum Bereichs-Token verschmelzen (Issue
    #1824 A) und das gesuchte Einzelsymbol waere nicht mehr isoliert
    pruefbar. Das ist reine Test-Isolation -- 'D'/'FD' sind unveraendert
    'D'/'FD' und bleiben von #1926 unberuehrt, deshalb duerfen sie hier als
    Gating-Schluessel stehen (kein Widerspruch zur RED-Phase-Regel bei
    _TEMPERATURE_OFF/_TEMPERATURE_ON in test_sms_unknown_on_missing_data.py).
    """
    day = DailyForecast(
        temp_min_c=13.0,
        wind_chill_min_c=-22.0,
        freezing_level_hourly=(HourlyValue(12, 2400.0),),
    )
    line = build_token_line(
        NormalizedForecast(days=(day,)),
        [MetricSpec(symbol="D", enabled=False), MetricSpec(symbol="FD", enabled=False)],
        report_type="evening", stage_name="E1",
    )
    symbole = {t.symbol for t in line.tokens}

    abweichungen = []
    for metric_id, (alt, neu) in _AC8_BUILDER_LITERALE_ERWARTUNG.items():
        if neu not in symbole:
            gefunden = alt if alt in symbole else "(kein Token erzeugt)"
            abweichungen.append(
                f"  - {metric_id}: erwartet Token-Symbol {neu!r}, "
                f"builder.py erzeugt weiterhin {gefunden!r}"
            )
    assert not abweichungen, (
        "builder.py fuehrt fuer diese Groessen noch die ALTEN, vom Register "
        "unabhaengigen Literale (AC-8, #1926 GREEN-Arbeit, NICHT #1934):\n"
        + "\n".join(abweichungen)
        + f"\n  erzeugte Token-Symbole insgesamt: {sorted(symbole)!r}"
    )
