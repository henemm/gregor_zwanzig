"""Form-Waechter ueber SMS-Symbol-Grammatik-Klassen (#1703 Scheibe 6).

SPEC: docs/specs/modules/fix_1703_s6_form_waechter.md — AC-S6-1 … AC-S6-6.

Diese Datei iteriert — anders als die vorherigen Scheiben 1-5 — ueber
SYMBOLE/Grammatik-Klassen, nicht ueber Metrik-IDs (PO-Vorentscheidung
`docs/reference/metric_output_matrix.md` §7b: eigene Achse, weil
`SMS_MULTI_SYMBOLS_BY_METRIC` eine Metrik auf mehrere Kuerzel abbildet und
die 1:1-Hauptmatrix das nicht ausdruecken kann).

AC-S6-1 bis AC-S6-5 sind reine Charakterisierung des HEUTIGEN, korrekten
Zustands. AC-S6-6 ist der einzige TDD-RED-Test dieser Scheibe: er beweist
eine verifizierte, sicherheitsrelevante Byte-Kollision zwischen dem
Wind-Datenausfall-Marker ('W?', Symbol 'W' + Gap-Wert '?') und dem
dedizierten 'amtliche Warnungen nicht abrufbar'-Marker
(`UNAVAILABLE_SYMBOL`, heute ebenfalls 'W?'). Der Fix
(`UNAVAILABLE_SYMBOL` -> 'X?') erfolgt NICHT in dieser Testdatei, sondern
als Ein-Zeilen-Produktivcode-Edit in der Implementierungsphase danach.

Bauprinzipien (Vorbild: tests/unit/test_sms_token_symbol_register_ratchet.py,
Bindende Test-Architektur-Entscheidung der Spec, "Pruefort = Wirkort"):

  1. **Kein Regex ueber Quelltext, keine handgepflegte Symbolliste** ausser
     der ausdruecklich benannten und kommentierten Systemzeichen-
     Ausnahmeliste (`_SYSTEM_SYMBOLS` unten). Alle Mengen werden aus den
     echten Produktivkonstanten GERECHNET ("rechnen statt tippen").
  2. **Echter Import der Produktivmodule**, kein isolierter
     `Token(...)`-Konstruktoraufruf fuer AC-S6-5/AC-S6-6 — beide rendern
     ueber den ECHTEN `build_token_line()`-Pfad mit realen
     `NormalizedForecast`/`DailyForecast`-Objekten (Lehre aus Scheibe 3/4:
     isolierte Direktaufrufe umgehen den echten Choke-Point).
  3. **Vakuum-Schutz.** Jeder Vollstaendigkeits-Test behauptet seine eigene
     Mindest-Trefferzahl — ein leer gewordenes Register darf nicht
     versehentlich "vollstaendig" erscheinen.

Regel-Budget (CLAUDE.md): kein eigenes Pruefdatum — laeuft im bereits
etablierten tests/unit/-Kern wie jeder andere Kern-Test (s. Spec ADR).
"""
from __future__ import annotations

from pathlib import Path

from app.metric_catalog import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC
from output.tokens import builder as builder_mod
from output.tokens.builder import (
    POS_INDEX,
    POSITIONAL,
    PRIORITY,
    UNAVAILABLE_SYMBOL,
    _POSITION_SORTABLE_CATEGORIES,
    build_token_line,
)
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, LEVELLESS_HAZARDS, sms_symbol_for

REPO_ROOT = Path(__file__).resolve().parents[2]

# Systemzeichen ohne Katalog-Metrik (Debug/Lawine/Vigilance/Fire) — die
# EINZIGE handgepflegte Liste dieser Datei, benannt und begruendet
# (Implementation Details der Spec, Gleichungspaar 30 Katalog + 6 System = 36).
_SYSTEM_SYMBOLS = {"DBG", "AV", "HR:", "M:", "MAX", "Z:"}


def _katalog_union() -> set[str]:
    """Alle Symbole, die eine waehlbare Metrik im SMS-Kanal traegt — GERECHNET
    aus den beiden Katalog-Registern, keine getippte Liste."""
    return set(SMS_SYMBOL_BY_METRIC.values()) | {
        sym for tpl in SMS_MULTI_SYMBOLS_BY_METRIC.values() for sym in tpl
    }


# ---------------------------------------------------------------------------
# Selbstpruefung (#1409: Pruefling muss aus diesem Arbeitsbaum stammen)
# ---------------------------------------------------------------------------


def test_ratchet_inspects_the_code_of_this_worktree():
    module_path = Path(builder_mod.__file__).resolve()
    assert str(module_path).startswith(str(REPO_ROOT)), (
        "Dieser Waechter prueft nicht den Code dieses Arbeitsbaums, sondern "
        f"{module_path} (erwartet unterhalb {REPO_ROOT})."
    )


# ---------------------------------------------------------------------------
# AC-S6-1: bidirektionale Vollstaendigkeit PRIORITY <-> POSITIONAL
# ---------------------------------------------------------------------------


def test_ac_s6_1_priority_positional_bidirectional_completeness():
    """Jedes Symbol, das eine Prioritaet ODER eine Position braucht, hat
    beides — in beide Richtungen keine Waise."""
    needs_priority_or_position = set(PRIORITY.keys()) | {UNAVAILABLE_SYMBOL}
    positional_symbols = {symbol for symbol, _category in POSITIONAL}

    # Vakuum-Schutz: ein leer gewordenes Register darf nicht "vollstaendig" wirken.
    assert len(needs_priority_or_position) >= 30, (
        f"Nur {len(needs_priority_or_position)} Symbole brauchen Prioritaet/"
        "Position — das Register scheint fast leer, der Waechter wuerde "
        "nichts pruefen."
    )
    assert len(positional_symbols) >= 30, (
        f"POSITIONAL fuehrt nur {len(positional_symbols)} eindeutige Symbole "
        "— zu wenig, der Waechter wuerde nichts pruefen."
    )

    missing_in_positional = needs_priority_or_position - positional_symbols
    assert not missing_in_positional, (
        f"Symbole {sorted(missing_in_positional)!r} brauchen eine Prioritaet "
        "(PRIORITY-Schluessel oder UNAVAILABLE_SYMBOL), haben aber KEINEN "
        "POSITIONAL-Eintrag — eine Kuerzung koennte sie nie einordnen."
    )

    orphan_positions = positional_symbols - needs_priority_or_position
    assert not orphan_positions, (
        f"Symbole {sorted(orphan_positions)!r} stehen in POSITIONAL, sind "
        "aber weder PRIORITY-Schluessel noch UNAVAILABLE_SYMBOL — eine "
        "unerklaerte Position ohne Prioritaet."
    )


# ---------------------------------------------------------------------------
# AC-S6-2: TH:-Doppeleintrag ist bewusst, Sortier-Kategorie schuetzt davor
# ---------------------------------------------------------------------------


def test_ac_s6_2_th_double_entry_is_deliberate_and_protected():
    """'TH:' erscheint zweimal in POSITIONAL (forecast + vigilance) — beide
    Tupel sind eigenstaendige POS_INDEX-Schluessel; 'vigilance' ist NICHT
    sortierbar."""
    th_entries = [(symbol, category) for symbol, category in POSITIONAL if symbol == "TH:"]
    assert set(th_entries) == {("TH:", "forecast"), ("TH:", "vigilance")}, (
        f"'TH:' sollte GENAU zweimal in POSITIONAL stehen (forecast + "
        f"vigilance), gefunden: {th_entries!r}"
    )

    assert ("TH:", "forecast") in POS_INDEX, "POS_INDEX fehlt ('TH:', 'forecast')."
    assert ("TH:", "vigilance") in POS_INDEX, "POS_INDEX fehlt ('TH:', 'vigilance')."
    assert POS_INDEX[("TH:", "forecast")] != POS_INDEX[("TH:", "vigilance")], (
        "Beide 'TH:'-Tupel muessen unterschiedliche POS_INDEX-Positionen "
        "haben — sonst waeren sie im Dict nicht unterscheidbar."
    )

    assert "vigilance" not in _POSITION_SORTABLE_CATEGORIES, (
        "_POSITION_SORTABLE_CATEGORIES darf 'vigilance' NICHT enthalten — "
        "sonst koennte eine MetricSpec.position-Sortierung den toten "
        "Vigilance-Pfad erreichen (Adversary-Hinweis Issue #1677)."
    )
    assert _POSITION_SORTABLE_CATEGORIES == {"forecast", "wintersport"}, (
        f"_POSITION_SORTABLE_CATEGORIES ist {_POSITION_SORTABLE_CATEGORIES!r} "
        "— erwartet genau {'forecast', 'wintersport'}."
    )


# ---------------------------------------------------------------------------
# AC-S6-3: Katalog-Vollstaendigkeit — 30 eindeutige Katalog-Symbole
# ---------------------------------------------------------------------------


def test_ac_s6_3_catalog_union_is_complete_subset_of_priority():
    """Die Vereinigung aus SMS_SYMBOL_BY_METRIC und
    SMS_MULTI_SYMBOLS_BY_METRIC (30 eindeutige Symbole, 'TH:' ueberlappt by
    design) ist vollstaendig in PRIORITY vertreten."""
    katalog_union = _katalog_union()

    # Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    # fix_1887_e6a_sms_kuerzel_register.md): 30 -> 29. 'WC' entfaellt
    # ERSATZLOS (verdoppelte nachweislich 'FK') -- ein Multi-Wert weniger:
    # 22 Single + 8 Multi - 1 Ueberschneidung 'TH:' = 29.
    assert len(katalog_union) == 29, (
        f"Katalog-Union hat {len(katalog_union)} eindeutige Symbole, "
        f"erwartet 29 (22 Single + 8 Multi - 1 Ueberschneidung 'TH:'): "
        f"{sorted(katalog_union)!r}"
    )

    missing = katalog_union - set(PRIORITY.keys())
    assert not missing, (
        f"Katalog-Symbole {sorted(missing)!r} fehlen in PRIORITY — ein "
        "waehlbares Metrik-Kuerzel faellt beim Kuerzen fälschlich als "
        "'Waise' durch."
    )


# ---------------------------------------------------------------------------
# AC-S6-4: geschlossene Systemzeichen-Ausnahmeliste
# ---------------------------------------------------------------------------


def test_ac_s6_4_system_exception_list_is_closed_and_disjoint():
    """PRIORITY.keys() minus (Katalog-Union ∪ Systemzeichen-Ausnahmeliste)
    ist leer — jedes Symbol ist entweder katalogrueckfuehrbar oder auf der
    benannten Ausnahmeliste, keine dritte, unerklaerte Kategorie."""
    katalog_union = _katalog_union()

    assert len(_SYSTEM_SYMBOLS) == 6, (
        f"Die Systemzeichen-Ausnahmeliste hat {len(_SYSTEM_SYMBOLS)} "
        f"Eintraege, erwartet 6: {sorted(_SYSTEM_SYMBOLS)!r}"
    )

    unexplained = set(PRIORITY.keys()) - (katalog_union | _SYSTEM_SYMBOLS)
    assert not unexplained, (
        f"PRIORITY-Symbole {sorted(unexplained)!r} sind weder ueber den "
        "Katalog noch ueber die Systemzeichen-Ausnahmeliste erklaerbar — "
        "eine dritte, unbenannte Kategorie ist entstanden."
    )

    assert _SYSTEM_SYMBOLS.isdisjoint(katalog_union), (
        f"Ueberschneidung zwischen Systemzeichen-Ausnahmeliste und "
        f"Katalog-Union: {sorted(_SYSTEM_SYMBOLS & katalog_union)!r} — "
        "die Ausnahmeliste waere dann keine echte Ausnahme mehr."
    )

    assert set(PRIORITY.keys()) == (katalog_union | _SYSTEM_SYMBOLS), (
        "PRIORITY.keys() sollte exakt der Vereinigung aus Katalog-Union "
        f"(30) und Systemzeichen-Ausnahmeliste (6) entsprechen: "
        f"PRIORITY hat {len(PRIORITY)} Schluessel."
    )


# ---------------------------------------------------------------------------
# AC-S6-5: Format-Invariante — '!'-Praefix exklusiv fuer official_alert
# ---------------------------------------------------------------------------


def _build_full_coverage_forecast() -> tuple[NormalizedForecast, list[MetricSpec]]:
    """Ein NormalizedForecast/DailyForecast-Paar mit allen wählbaren
    Grammatik-Klassen aktiv (forecast/wintersport/fire/debug), OHNE
    Wind-/Warn-Ausfall (das ist AC-S6-6). Vigilance bleibt strukturell tot
    (Known Limitation 1 der Spec, provider='open-meteo')."""
    today = DailyForecast(
        night_temp_min_c=5.0, temp_min_c=8.0, temp_max_c=18.0,
        night_wind_chill_min_c=3.0, wind_chill_min_c=6.0, wind_chill_max_c=15.0,
        rain_hourly=(HourlyValue(6, 0.5),), pop_hourly=(HourlyValue(11, 40.0),),
        wind_hourly=(HourlyValue(11, 18.0),), gust_hourly=(HourlyValue(11, 25.0),),
        thunder_hourly=(HourlyValue(16, 2),),
        humidity_hourly=(HourlyValue(12, 55.0),), dewpoint_hourly=(HourlyValue(12, 8.0),),
        cape_hourly=(HourlyValue(15, 300.0),), uv_hourly=(HourlyValue(13, 5.0),),
        cloud_total_hourly=(HourlyValue(12, 60.0),), cloud_low_hourly=(HourlyValue(12, 40.0),),
        cloud_mid_hourly=(HourlyValue(12, 20.0),), cloud_high_hourly=(HourlyValue(12, 10.0),),
        visibility_hourly=(HourlyValue(12, 20000.0),),
        freezing_level_hourly=(HourlyValue(12, 2500.0),),
        wind_direction_sector="NW", precip_type_dominant="R",
        sunshine_hours=6.5, pressure_avg_hpa=1013.0,
        snow_depth_cm=120.0, snow_new_24h_cm=10.0, snowfall_limit_m=1600.0,
        avalanche_level=2, wind_chill_c=-5.0, has_data_gap=False,
    )
    tomorrow = DailyForecast(thunder_hourly=(HourlyValue(14, 3),))
    forecast = NormalizedForecast(
        days=(today, tomorrow), provider="open-meteo", country="FR",
        fire_zones_high=("208",), fire_zones_max=("209",), fire_massifs=("3",),
        debug_provider="MET", debug_confidence="MED",
        official_alerts_unavailable=False,
    )
    config = [
        MetricSpec(symbol=sym, enabled=True)
        for sym in (
            "N", "K", "D", "FN", "FK", "FD", "R", "PR", "W", "G", "TH:", "TH+:",
            "HU", "DP", "WD", "CP", "PT", "CT", "CL", "CM", "CH", "VS", "SU",
            "UV", "HP", "NL", "SD", "NS24+", "SL", "AV",
            # Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' entfaellt ERSATZLOS
            # (verdoppelte nachweislich 'FK') -- kein MetricSpec mehr hier.
        )
    ]
    return forecast, config


def test_ac_s6_5_no_non_alert_token_render_starts_with_bang():
    """Ueber den echten build_token_line()-Pfad: KEIN Token ausserhalb der
    Kategorie 'official_alert' rendert mit fuehrendem '!' — der Marker
    bleibt exklusiv dem amtlichen Warnblock vorbehalten."""
    forecast, config = _build_full_coverage_forecast()
    line = build_token_line(
        forecast, config, report_type="evening", stage_name="Etappe1",
    )
    non_alert_tokens = [t for t in line.tokens if t.category != "official_alert"]

    assert len(non_alert_tokens) >= 25, (
        f"Nur {len(non_alert_tokens)} Nicht-official_alert-Token gerendert "
        "— die Fixture deckt zu wenige Grammatik-Klassen ab, der Waechter "
        "wuerde praktisch nichts pruefen."
    )

    violations = [t for t in non_alert_tokens if t.render().startswith("!")]
    assert not violations, (
        "Folgende Nicht-official_alert-Token rendern mit fuehrendem '!': "
        f"{[(t.symbol, t.category, t.render()) for t in violations]!r} — "
        "der '!'-Block-Marker ist damit nicht mehr exklusiv dem amtlichen "
        "Warnblock vorbehalten."
    )


def test_ac_s6_5_access_ban_bare_never_collides_with_forecast_cloud_low():
    """Stichprobe: 'access_ban' (der EINZIGE levellose Hazard) rendert bar
    'CL' ohne Suffix; forecast-'CL' (Wolken tief) rendert NIE bar — beide
    Renderformen sind bytegenau verschieden."""
    assert LEVELLESS_HAZARDS == frozenset({"access_ban"}), (
        f"LEVELLESS_HAZARDS ist {LEVELLESS_HAZARDS!r} — erwartet genau "
        "{'access_ban'} (einziger levelloser Hazard)."
    )
    access_ban_symbol = sms_symbol_for("access_ban")
    assert access_ban_symbol == HAZARD_SMS_SYMBOLS["access_ban"], (
        "sms_symbol_for('access_ban') weicht vom Katalog HAZARD_SMS_SYMBOLS ab."
    )

    forecast_ab = NormalizedForecast(
        days=(DailyForecast(),),
        official_alerts=((access_ban_symbol, "", None),),
    )
    line_ab = build_token_line(
        forecast_ab, [], report_type="evening", stage_name="EtappeAB",
    )
    ab_tokens = [
        t for t in line_ab.tokens
        if t.symbol == access_ban_symbol and t.category == "official_alert"
    ]
    assert len(ab_tokens) == 1, (
        f"Erwartet genau EIN official_alert-Token fuer 'access_ban', "
        f"gefunden: {ab_tokens!r}"
    )
    bare_render = ab_tokens[0].render()
    assert bare_render == access_ban_symbol, (
        f"'access_ban' MUSS bar (ohne Suffix) rendern — erwartet "
        f"{access_ban_symbol!r}, war {bare_render!r}."
    )

    forecast_cl = NormalizedForecast(
        days=(DailyForecast(cloud_low_hourly=(HourlyValue(12, 40.0),)),),
    )
    line_cl = build_token_line(
        forecast_cl, [MetricSpec(symbol="CL", enabled=True)],
        report_type="evening", stage_name="EtappeCL",
    )
    cl_forecast_tokens = [
        t for t in line_cl.tokens if t.symbol == "CL" and t.category == "forecast"
    ]
    assert len(cl_forecast_tokens) == 1, (
        f"Erwartet genau EIN forecast-Token fuer 'CL', gefunden: "
        f"{cl_forecast_tokens!r}"
    )
    forecast_render = cl_forecast_tokens[0].render()
    assert forecast_render != access_ban_symbol, (
        f"forecast-'CL' rendert bar ({forecast_render!r}) — das wuerde mit "
        f"'access_ban' ({access_ban_symbol!r}) kollidieren. forecast-'CL' "
        "MUSS immer einen Zahl/'-'/'?'-Suffix tragen."
    )
    assert bare_render != forecast_render, (
        f"Die beiden Renderformen von 'CL' duerfen sich NIE decken: "
        f"access_ban={bare_render!r}, forecast={forecast_render!r}"
    )


# ---------------------------------------------------------------------------
# AC-S6-6 (RED): UNAVAILABLE_SYMBOL kollidiert heute bytegleich mit dem
# Wind-Gap-Marker. Dieser Test MUSS beim Erstlauf fehlschlagen.
# ---------------------------------------------------------------------------


def test_ac_s6_6_unavailable_marker_must_never_collide_with_wind_gap_marker():
    """(a) Wind-Datenausfall OHNE amtlichen Warnungs-Ausfall und (b) amtlicher
    Warnungs-Ausfall OHNE Wind-Datenausfall MUESSEN ueber den echten
    build_token_line()-Pfad verschiedene Marker-Strings liefern.

    HEUTE (vor dem Fix in builder.py:74): beide rendern 'W?' -> ROT.
    NACH dem Fix (UNAVAILABLE_SYMBOL = 'X?'): (a) bleibt 'W?', (b) wird
    'X?' -> GRUEN.
    """
    # Szenario (a): Wind-Datenausfall, keine echte Windmessung im Fenster.
    today_a = DailyForecast(wind_hourly=(), has_data_gap=True)
    forecast_a = NormalizedForecast(days=(today_a,), official_alerts_unavailable=False)
    line_a = build_token_line(
        forecast_a, [MetricSpec(symbol="W", enabled=True)],
        report_type="evening", stage_name="EtappeWindGap",
    )
    wind_gap_tokens = [
        t for t in line_a.tokens if t.symbol == "W" and t.category == "forecast"
    ]
    assert len(wind_gap_tokens) == 1, (
        f"Erwartet genau EIN Wind-forecast-Token, gefunden: {wind_gap_tokens!r}"
    )
    wind_gap_marker = wind_gap_tokens[0].render()

    # Szenario (b): amtlicher Warnungs-Ausfall, keine Wind-Datenluecke.
    today_b = DailyForecast(has_data_gap=False)
    forecast_b = NormalizedForecast(days=(today_b,), official_alerts_unavailable=True)
    line_b = build_token_line(
        forecast_b, [], report_type="evening", stage_name="EtappeWarnAusfall",
    )
    unavailable_tokens = [t for t in line_b.tokens if t.category == "unavailable"]
    assert len(unavailable_tokens) == 1, (
        f"Erwartet genau EIN 'unavailable'-Token, gefunden: {unavailable_tokens!r}"
    )
    unavailable_marker = unavailable_tokens[0].render()

    # Regressionsschutz: der Fix darf den Wind-Token selbst nicht veraendern.
    assert wind_gap_marker == "W?", (
        f"Szenario (a) (Wind-Datenausfall) sollte unveraendert 'W?' rendern, "
        f"war {wind_gap_marker!r} — der Fix an UNAVAILABLE_SYMBOL darf den "
        "Wind-Token selbst nicht beruehren."
    )
    # Regressionsschutz: der Marker bleibt weiterhin ausserhalb des
    # '!'-Warnblocks (Anschluss an feat_1349_sms_unavailable.md AC-3).
    assert "!" not in unavailable_marker, (
        f"Szenario (b)s Marker darf NICHT als amtliche Warnung erscheinen "
        f"('!'-Praefix), war {unavailable_marker!r}."
    )

    # DER FIX (AC-S6-6): beide Marker-Strings duerfen NIEMALS bytegleich sein.
    # HEUTE (UNAVAILABLE_SYMBOL noch 'W?'): dieser Assert schlaegt fehl (RED).
    assert wind_gap_marker != unavailable_marker, (
        "AC-S6-6: 'Wind-Datenausfall' und 'amtliche Warnungen nicht "
        f"abrufbar' rendern BEIDE {wind_gap_marker!r} — bytegleiche "
        "Kollision zwischen zwei fachlich verschiedenen Zustaenden "
        "(UNAVAILABLE_SYMBOL, builder.py:74, ist noch nicht auf 'X?' "
        "gefixt). Fix: UNAVAILABLE_SYMBOL von 'W?' auf 'X?' aendern."
    )
