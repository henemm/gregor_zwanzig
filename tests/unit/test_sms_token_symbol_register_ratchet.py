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

import dataclasses
from pathlib import Path

import pytest

from app.metric_catalog import get_all_metrics, get_sms_code
from output.adapters.trip_result import _wintersport_default_config
from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC
from output.tokens import builder as builder_mod
from output.tokens.builder import POSITIONAL, PRIORITY, _wintersport
from output.tokens.dto import DailyForecast
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
    # 'WC' — gefuehlte Temperatur. Eine Groesse (Register: 'TF') traegt im
    # SMS-Format DREI Kuerzel (WC/FK/FD, Tageskennzahl/Tiefst/Hoechst) und
    # ist damit strukturell nicht aus einem einzelnen sms_code-Feld
    # ableitbar. Bewusster Sonderfall, s. Known Limitations. Fix #1660
    # Scheibe A: 'FN' (Nacht) ist zur eigenen Groesse "wind_chill_night"
    # gewandert (vorher vier Kuerzel).
    "wind_chill_c": "WC: drei Kuerzel fuer eine Groesse (Register: TF)",
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


@pytest.mark.parametrize("legacy_symbol", ["SN", "SN24+", "SFL"])
def test_legacy_snow_symbols_are_absent_from_all_tables(legacy_symbol: str):
    """#1435 E3b: die drei Alt-Kuerzel duerfen in keiner Metrik-Tabelle mehr
    stehen. ('SN' bleibt ausschliesslich die amtliche Schneewarnung in
    `hazard_symbols.py` — eine andere Tabelle, hier nicht geprueft.)"""
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
