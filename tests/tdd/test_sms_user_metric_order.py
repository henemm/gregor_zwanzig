"""TDD RED: Issue #1677 -- die im SMS-Kanal-Tab gezogene Metrik-Reihenfolge
muss in der zugestellten Trip-Kurzform (SMS/Telegram-Kurzform) wirken.

SPEC: docs/specs/modules/fix_1677_sms_reihenfolge.md (AC-1..AC-11).

Wirkort-Prinzip (CLAUDE.md "Pruefort = Wirkort", Muster
tests/tdd/test_sms_extended_null_forms.py): fast alle Tests hier fahren den
ECHTEN Produktionspfad ``TripReportFormatter().format_email() -> report.
sms_text`` -- keine an Ort und Stelle konstruierten ``MetricSpec``-Objekte.

Ausnahme AC-4: Vigilance-Daten (``provider="meteofrance"``,
``vigilance_hr_level``/``vigilance_th_level``) erreichen den Trip-SMS-Pfad
strukturell NICHT -- ``SMSTripFormatter._build_normalized_forecast()`` setzt
weder ``provider`` noch die Vigilance-Felder (Grep-Beleg 2026-08-10: nur
Direktaufrufe in ``tests/unit/test_token_builder.py``,
``tests/golden/test_sms_golden.py``, ``tests/unit/test_renderers_sms.py``
bauen echte Vigilance-Fixtures). Der Wirkort der NEUEN Sortierung ist ohnehin
``output/tokens/builder.py::build_token_line`` (Implementation Details
Punkt 4 der Spec) -- AC-4 faehrt deshalb genau diese Ebene direkt.

AC-Zuordnung (Kopf-Kommentar UND Rueckmeldung):
- AC-1: test_ac1_sms_channel_layout_order_wins_over_default            -> RED
- AC-2: test_ac2_default_order_byte_identical_without_sms_layout       -> GRUEN (Charakterisierung, Bestand)
- AC-3: test_ac3_per_report_layout_overrides_per_channel_layout        -> RED
- AC-4: test_ac4_vigilance_block_stays_behind_forecast_and_fused       -> RED (TypeError: MetricSpec.position fehlt)
- AC-5: test_ac5_position_applies_per_metric_anchor_not_per_symbol     -> RED
- AC-6: test_ac6_drop_order_ignores_display_position_...               -> RED
- AC-7: test_ac7_wintersport_metric_can_precede_forecast_metric_...    -> RED
- AC-8: siehe Kopf-Kommentar unten (kein neuer Testcode -- Bestand deckt ab)
- AC-9: test_ac9_cascade_source_helper_matches_validator_...           -> RED (AttributeError: cascade_source_for_channel fehlt)
- AC-10: test_ac10_two_permutations_same_metric_set_different_order    -> RED
- AC-11: test_ac11_sms_and_telegram_kurzform_share_one_token_line      -> RED

AC-8 (Compare-Kurzform-Regression): ``tests/unit/test_compare_metric_order.py
::TestAC10SmsFollowsUserOrder`` deckt ``render_compare_sms`` bereits mit
einem Ordnungs-Assert ab (``test_sms_shows_all_four_metrics_of_order_a``,
``test_sms_selection_flips_with_reversed_order``) -- kein neuer Testcode
noetig (Spec: "NUR falls dort keiner existiert"). Alert-SMS
(``alert/render.py``) hat keine Nutzer-Reihenfolge (Known Limitation 5 der
Spec, Alarme sind dringlichkeitssortiert) -- kein Test noetig, da kein Code
dort geaendert wird.

Keine Mocks, kein Netz -- reine Datenmodell-Objekte + Renderer-Aufrufe
(CLAUDE.md Test-Politik, Schicht "Kern").
"""
from __future__ import annotations

import dataclasses
import re

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers.trip_report import TripReportFormatter
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
from output.tokens.builder import build_token_line
from api.routers.validator import _determine_cascade_source

from tests.tdd import _min_temp_felt_fixtures as F

# ---------------------------------------------------------------------------
# Fixtures/Helfer
# ---------------------------------------------------------------------------


def _sms_layout_dc(
    order: list[str], *, per_report_evening: list[str] | None = None,
) -> UnifiedWeatherDisplayConfig:
    """UnifiedWeatherDisplayConfig mit globaler Metrikliste (Katalog-Default-
    Reihenfolge) UND ``per_channel_layouts['sms']`` in der Nutzer-Reihenfolge
    ``order``. ``per_report_evening`` setzt zusaetzlich die hoechste
    Kaskadenebene (#434) nur fuer 'evening' (AC-3)."""
    global_metrics = [MetricConfig(metric_id=m, enabled=True) for m in order]
    sms_layout = [
        MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
        for i, m in enumerate(order)
    ]
    kwargs: dict = dict(
        trip_id="i1677", metrics=global_metrics,
        per_channel_layouts={"sms": sms_layout},
    )
    if per_report_evening is not None:
        kwargs["per_report_layouts"] = {"evening": {"sms": [
            MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
            for i, m in enumerate(per_report_evening)
        ]}}
    return UnifiedWeatherDisplayConfig(**kwargs)


def _render_sms(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening") -> str:
    report = TripReportFormatter().format_email(
        [F.segment()], trip_name="Issue1677", report_type=report_type,
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    return report.sms_text


# sms_format.md §5: Wert-Grammatik ist NICHT nur eine nackte Zahl -- der
# Threshold+Peak-Block ("{val}@{h}({peak}@{h})", §5 "Threshold == Max-
# Optimierung"), die Prozent-Schreibweise (§5 "Wahrscheinlichkeit (%)") UND
# die Stufen-Label-Werte L/M/H (§3, TH:/TH+: sind is_level, builder.py
# LEVELS = {0:'-',1:'L',2:'M',3:'H'}) sind Pflichtbestandteile des Formats.
# Die urspruengliche Grammatik hier kannte weder '@' noch '(' ')' noch '%'
# noch die Stufen-Buchstaben -- fand dadurch KEINEN der Kern-Vorhersage-Token
# (R/PR/W/G/TH:), die ueber render_threshold_peak_value() ausnahmslos mit
# Default-Schwellwert (builder.py DEFAULTS) gerendert werden und deshalb
# strukturell den Peak-Block tragen (Testfehler gegen sms_format.md §5,
# nicht gegen die Spec dieser Scheibe -- Erwartung unveraendert, nur die
# Symbol-Erkennung repariert). Die Buchstaben sind bewusst ENG gefasst (nur
# unmittelbar vor '@'/Ende/Klammer-Ende) -- ein Praefix-Kollisionstest
# ('L' nach Symbol 'N' fuer den Token 'NL-') bestaetigt, dass 'N' weiterhin
# NICHT faelschlich in 'NL-' matcht.
_VALUE_GRAMMAR = re.compile(
    r"(?:(?:\d+(?:\.\d+)?%?|[LMH])(?:@\d+(?:\((?:\d+(?:\.\d+)?%?|[LMH])@\d+\))?)?|-|\?)$"
)


def _token_index(sms: str, symbol: str) -> int:
    """Index des Tokens mit exakt diesem Symbol (fullmatch auf Symbol+Wert,
    schliesst Praefix-Verwechslungen strukturell aus, Muster F.sms_token_value)."""
    body = sms.split(": ", 1)[1] if ": " in sms else sms
    pattern = re.compile(rf"{re.escape(symbol)}(?:{_VALUE_GRAMMAR.pattern})")
    for i, tok in enumerate(body.split(" ")):
        if pattern.fullmatch(tok):
            return i
    raise AssertionError(f"Symbol {symbol!r} nicht gefunden in SMS: {sms!r}")


def _present(sms: str, symbol: str) -> bool:
    """Bool-Wrapper um ``_token_index()`` (Symbol-Praesenz, unabhaengig vom
    konkreten Wert-Format). AC-10 braucht eine Praesenz-Pruefung ueber die
    volle Peak-Grammatik (s. ``_VALUE_GRAMMAR``) -- der geteilte Fixture-
    Helfer ``F.sms_token_value()`` (``tests/tdd/_min_temp_felt_fixtures.py``)
    ist bewusst auf reine Temperatur-Token ohne Peak-Block eingegrenzt (dort
    NICHT geaendert, um dessen Praefix-Kollisionsschutz fuer andere Tests
    nicht zu verwaessern) -- deshalb hier ein lokaler, auf die volle Grammatik
    passender Wrapper statt einer Aufweichung der geteilten Fixture."""
    try:
        _token_index(sms, symbol)
        return True
    except AssertionError:
        return False


def _exact_token_index(sms: str, literal: str) -> int:
    """Index eines Tokens, der EXAKT dem literalen String entspricht (fuer
    wertlose System-Marker wie 'W?', deren Symbol bereits den vollen Text
    traegt)."""
    body = sms.split(": ", 1)[1] if ": " in sms else sms
    for i, tok in enumerate(body.split(" ")):
        if tok == literal:
            return i
    raise AssertionError(f"Token {literal!r} nicht gefunden in SMS: {sms!r}")


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


def test_ac1_sms_channel_layout_order_wins_over_default():
    """SMS-Kanal-Layout [gust, wind, precipitation] -> G vor W vor R, NICHT
    die Default-Reihenfolge R vor W vor G (POSITIONAL)."""
    dc = _sms_layout_dc(["gust", "wind", "precipitation"])
    sms = _render_sms(dc)
    i_g, i_w, i_r = _token_index(sms, "G"), _token_index(sms, "W"), _token_index(sms, "R")
    assert i_g < i_w < i_r, (
        f"Erwartete Reihenfolge G < W < R (SMS-Kanal-Layout), aber Indizes "
        f"G={i_g} W={i_w} R={i_r}. SMS: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- GRUEN (Bestand-Charakterisierung, dokumentierte Ausnahme)
# ---------------------------------------------------------------------------


def test_ac2_default_order_byte_identical_without_sms_layout():
    """Ohne SMS-Kanal-Layout (nur globale Auswahl) bleibt die Reihenfolge
    exakt die heutige POSITIONAL-Reihenfolge -- fuer morning UND evening.
    Referenzstring am 2026-08-10 empirisch vom UNVERAENDERTEN Code
    abgenommen (uv run python3 -c "..." gegen HEAD 21da0d50) und eingefroren.
    Diese Ausnahme ist bewusst GRUEN: der Test beweist Byte-Identitaet des
    Ist-Zustands, nicht das neue Verhalten."""
    dc = F.dc("gust", "wind", "precipitation")
    expected = "E7: R0.5@5(8.4@11) W12@4(45@10) G22@4(70@10)"
    assert _render_sms(dc, "evening") == expected, "Abend-SMS weicht vom eingefrorenen Referenzstring ab"
    assert _render_sms(dc, "morning") == expected, "Morgen-SMS weicht vom eingefrorenen Referenzstring ab"


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


def test_ac3_per_report_layout_overrides_per_channel_layout():
    """per_report_layouts['evening']['sms'] (Ebene 1) schlaegt
    per_channel_layouts['sms'] (Ebene 2); fuer 'morning' (kein per_report-
    Eintrag) greift per_channel_layouts als Fallback."""
    dc = _sms_layout_dc(
        ["wind", "precipitation", "gust"],           # Ebene 2 (A)
        per_report_evening=["gust", "wind", "precipitation"],  # Ebene 1 (B), nur evening
    )
    evening = _render_sms(dc, "evening")
    morning = _render_sms(dc, "morning")

    assert _token_index(evening, "G") < _token_index(evening, "W") < _token_index(evening, "R"), (
        f"Abend muss Reihenfolge B (per_report: G,W,R) folgen: {evening!r}"
    )
    assert _token_index(morning, "W") < _token_index(morning, "R") < _token_index(morning, "G"), (
        f"Morgen muss auf Reihenfolge A (per_channel: W,R,G) zurueckfallen: {morning!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- builder.py-Ebene (Begruendung s. Modul-Docstring)
# ---------------------------------------------------------------------------


def test_ac4_vigilance_block_stays_behind_forecast_and_fused():
    """Vorhersage-Gewitter (TH:, category='forecast') an Nutzer-Position 0
    steht VOR dem Vigilance-Block, waehrend HR:/TH: (category='vigilance')
    unveraendert fusioniert bleiben -- die Symbol-Kollision (beide Kategorien
    teilen sich das Zeichen 'TH:') darf die Vigilance-Adjazenz nicht brechen
    (Implementation Details Punkt 4 + Adversary-Hinweis 2).

    RED heute: ``MetricSpec`` kennt noch kein ``position``-Feld (dto.py) ->
    TypeError. Das IST der RED-Beleg fuer diese Scheibe."""
    today = DailyForecast(
        temp_min_c=3.0, temp_max_c=12.0, night_temp_min_c=3.0,
        wind_hourly=(HourlyValue(10, 25.0),),
        thunder_hourly=(HourlyValue(11, 2.0),),
    )
    forecast = NormalizedForecast(
        days=(today,), provider="meteofrance", country="FR",
        vigilance_hr_level="M", vigilance_hr_hour=14,
        vigilance_th_level="H", vigilance_th_hour=17,
    )
    specs = [
        MetricSpec(symbol="TH:", enabled=True, position=0),  # type: ignore[call-arg]
    ]
    line = build_token_line(forecast, specs, report_type="evening", stage_name="E7")
    body = line.render(160).split(": ", 1)[1]

    i_th_forecast = body.index("TH:M@11")
    i_w = body.index("W25@10")
    i_vigi = body.index("HR:M@14TH:H@17")
    assert i_th_forecast < i_w < i_vigi, (
        f"Erwartet: Vorhersage-TH: (Position 0) vor W vor dem fusionierten "
        f"Vigilance-Block: {body!r}"
    )


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


def test_ac5_position_applies_per_metric_anchor_not_per_symbol():
    """wind_chill (FK/FD) an Position 0, temperature (K/D) an Position 1 ->
    FK/FD-Paar VOR K/D-Paar, interne Paar-Reihenfolge bleibt (FK<FD, K<D)."""
    dc = _sms_layout_dc(["wind_chill", "temperature"])
    sms = _render_sms(dc)
    i_fk, i_fd = _token_index(sms, "FK"), _token_index(sms, "FD")
    i_k, i_d = _token_index(sms, "K"), _token_index(sms, "D")
    assert i_fk < i_k and i_fd < i_k, (
        f"Gefuehltes Paar (Nutzer-Position 0) muss vor dem gemessenen Paar "
        f"(Position 1) stehen: {sms!r}"
    )
    assert i_fk < i_fd, f"Interne Reihenfolge FK vor FD muss erhalten bleiben: {sms!r}"
    assert i_k < i_d, f"Interne Reihenfolge K vor D muss erhalten bleiben: {sms!r}"


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


def test_ac6_drop_order_ignores_display_position():
    """Der Taupunkt (DP) an Nutzer-Position 0 faellt bei Ueberlaenge trotzdem
    VOR den sicherheitsrelevanten Vorhersage-Token weg (fruehe DROP_ORDER-
    Position, unveraendert) -- Anzeige-Position != Ueberlebensrang.

    Issue #1585: Traeger-Groesse von "cape" auf "dewpoint" gewechselt. CAPE ist
    zentral nicht mehr waehlbar und erscheint im SMS-Pfad gar nicht mehr -- die
    Gegenprobe "ohne Kuerzungsdruck bleibt das Token stehen" waere sonst aus
    dem falschen Grund rot. DP steht in DROP_ORDER (render.py) auf Index 2 und
    damit VOR dem frueheren CP (Index 4): faellt CP unter diesem Druck, faellt
    DP erst recht. Der Pruefgegenstand ist unveraendert. Die ueberlebenden
    Kern-Token behalten dabei die vom Nutzer gesetzte Reihenfolge (G vor W
    vor R, NICHT Default R/W/G) -- das macht die Zusicherung erst
    RED-faehig, sonst waere sie schon heute (ohne jede Aenderung) erfuellt."""
    order = [
        "dewpoint", "gust", "wind", "precipitation", "rain_probability", "thunder",
        "snow_depth", "snowfall_limit", "fresh_snow",
        "temperature", "temperature_night", "wind_chill", "wind_chill_night",
        "humidity", "wind_direction", "precip_type", "cloud_total",
        "cloud_low", "cloud_mid", "cloud_high", "visibility", "sunshine",
        "uv_index", "pressure", "freezing_level",
    ]
    dc_full = _sms_layout_dc(order)
    # Testfehler gegen die eigene AC-6-Praemisse ("Fixture, das eine
    # Zeilenlaenge >160 Zeichen erzwingt"): F.segment() pur (ohne
    # Wintersport-Aggregate) erreichte hoechstens 157 Zeichen -- der Drop
    # wurde nie ausgeloest, die Kern-Zusicherung (CP faellt VOR den
    # ueberlebenden Kern-Token) blieb ungeprueft. Muster wie
    # test_ac7_...: reale Schneedaten via dataclasses.replace (dieselbe
    # Datenquelle, die _segments_to_normalized_forecast fuer SD/SL/NS24+
    # aggregiert) heben die Zeile ueber die Schwelle.
    seg = F.segment()
    agg = dataclasses.replace(
        seg.aggregated, snow_depth_cm=25.0, snowfall_limit_m=1800.0, snow_new_sum_cm=5.0,
    )
    seg = dataclasses.replace(seg, aggregated=agg)
    report = TripReportFormatter().format_email(
        [seg], trip_name="Issue1677", report_type="evening",
        night_weather=F.night_weather(), display_config=dc_full,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    sms_full = report.sms_text
    assert len(sms_full) <= 160
    assert F.sms_token_value(sms_full, "DP") is None, (
        f"DP muss bei Ueberlaenge weichen (fruehe DROP_ORDER-Position), "
        f"unabhaengig von Position 0: {sms_full!r}"
    )
    i_g, i_w, i_r = _token_index(sms_full, "G"), _token_index(sms_full, "W"), _token_index(sms_full, "R")
    assert i_g < i_w < i_r, (
        f"Ueberlebende Kern-Token muessen die Nutzer-Reihenfolge G<W<R "
        f"behalten, nicht die Default-Reihenfolge: {sms_full!r}"
    )

    # Gegenprobe: ohne Kuerzungsdruck bleibt DP stehen (DP ist generell
    # wirksam verdrahtet, nicht grundsaetzlich unterdrueckt).
    dc_small = _sms_layout_dc(["dewpoint", "gust"])
    sms_small = _render_sms(dc_small)
    assert F.sms_token_value(sms_small, "DP") is not None, (
        f"Ohne Kuerzungsdruck muss DP (Position 0) stehen: {sms_small!r}"
    )


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------


def test_ac7_wintersport_metric_can_precede_forecast_metric_but_stays_before_system_blocks():
    """Wintersport-Metrik (snow_depth, Nutzer-Position 0) vor
    Vorhersage-Metrik (gust, Position 2) -- beide bleiben trotzdem vor dem
    nicht-sortierbaren System-Block (hier: 'X?', amtliche-Warnungen-nicht-
    abrufbar-Marker)."""
    order = ["snow_depth", "snowfall_limit", "gust"]
    dc = _sms_layout_dc(order)
    seg = F.segment()
    agg = dataclasses.replace(seg.aggregated, snow_depth_cm=25.0, snowfall_limit_m=1700.0)
    seg = dataclasses.replace(seg, aggregated=agg, official_alerts_unavailable=True)

    report = TripReportFormatter().format_email(
        [seg], trip_name="Issue1677", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    sms = report.sms_text
    i_sd = _token_index(sms, "SD")
    i_g = _token_index(sms, "G")
    i_marker = _exact_token_index(sms, "X?")
    assert i_sd < i_g, (
        f"SD (Wintersport, Nutzer-Position 0) muss vor G (Vorhersage, "
        f"Position 2) stehen: {sms!r}"
    )
    assert i_g < i_marker, (
        f"Systemblock 'X?' muss auch bei umsortierten Fachtoken dahinter "
        f"bleiben: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-9
# ---------------------------------------------------------------------------


def test_ac9_cascade_source_helper_matches_validator_and_couples_to_order_effect():
    """``UnifiedWeatherDisplayConfig.cascade_source_for_channel()`` (models.py,
    noch nicht existent -> AttributeError = RED) muss dieselbe Antwort geben
    wie der Validator-Spiegel ``_determine_cascade_source`` UND diese
    Antwort muss mit der tatsaechlichen Reihenfolge-Wirkung gekoppelt sein
    (Adversary-Hinweis 4: kein Test, der nur EINEN der beiden Pfade prueft)."""
    dc_layout = _sms_layout_dc(["gust", "wind", "precipitation"])
    dc_global = F.dc("gust", "wind", "precipitation")

    for dc, expected_order_effect in ((dc_layout, True), (dc_global, False)):
        validator_source = _determine_cascade_source(dc, "sms", "evening")
        model_source = dc.cascade_source_for_channel("sms", "evening")  # type: ignore[attr-defined]
        assert model_source == validator_source, (
            f"models.py-Helfer und Validator-Spiegel laufen auseinander: "
            f"{model_source!r} != {validator_source!r}"
        )
        sms = _render_sms(dc)
        order_matches_user = (
            _token_index(sms, "G") < _token_index(sms, "W") < _token_index(sms, "R")
        )
        assert order_matches_user == expected_order_effect, (
            f"Kopplung von Meldung ({model_source!r}) und Wirkung gebrochen: "
            f"order_matches_user={order_matches_user}, erwartet="
            f"{expected_order_effect}. SMS: {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-10
# ---------------------------------------------------------------------------


def test_ac10_two_permutations_same_metric_set_different_order():
    """Zwei disjunkte Permutationen derselben Metrik-MENGE -> dieselbe
    Symbol-Menge, aber zwei nachweisbar verschiedene Reihenfolgen."""
    # Issue #1585: "cape" -> "dewpoint" (CAPE ist zentral nicht mehr waehlbar
    # und erscheint im SMS-Pfad nicht mehr). Der Pruefgegenstand -- dieselbe
    # Metrik-MENGE in zwei Reihenfolgen ergibt zwei Token-Folgen -- ist
    # unveraendert.
    metric_ids = ["gust", "wind", "precipitation", "dewpoint", "humidity"]
    symbols = ["G", "W", "R", "DP", "HU"]
    order_a = metric_ids
    order_b = list(reversed(metric_ids))

    sms_a = _render_sms(_sms_layout_dc(order_a))
    sms_b = _render_sms(_sms_layout_dc(order_b))

    present_a = {s for s in symbols if _present(sms_a, s)}
    present_b = {s for s in symbols if _present(sms_b, s)}
    assert present_a == present_b == set(symbols), (
        f"Beide Permutationen muessen dieselbe Symbol-Menge zeigen: "
        f"A={present_a} B={present_b}\nA={sms_a!r}\nB={sms_b!r}"
    )

    appearance_a = sorted(symbols, key=lambda s: _token_index(sms_a, s))
    appearance_b = sorted(symbols, key=lambda s: _token_index(sms_b, s))
    assert appearance_a == ["G", "W", "R", "DP", "HU"], f"Reihenfolge A falsch: {sms_a!r}"
    assert appearance_b == ["HU", "DP", "R", "W", "G"], f"Reihenfolge B falsch: {sms_b!r}"
    assert appearance_a != appearance_b, (
        f"Dieselbe Menge in zwei Reihenfolgen muss zwei verschiedene "
        f"Token-Folgen ergeben, ergab aber beide Male {appearance_a}."
    )


# ---------------------------------------------------------------------------
# AC-11
# ---------------------------------------------------------------------------


def test_ac11_sms_and_telegram_kurzform_share_one_token_line():
    """SMS und Telegram-Kurzform sind KEIN zweiter Renderer-/Sortier-Pfad,
    sondern EIN Objekt: ``services/notification_service.py`` uebergibt
    ``body=report.sms_text or report.email_plain`` fuer BEIDE Kanaele
    unveraendert (Zeilen 364/381, Grep-Beleg 2026-08-10 -- begruendeter
    Verweis statt zweitem Testaufruf, #1660 B dokumentiert dasselbe Muster).
    Der Beleg hier ist die konkrete Nutzer-Reihenfolge auf GENAU diesem
    Objekt, ueber alle drei #1660-B-Grammatikklassen hinweg (a: humidity,
    b: visibility, c: wind_direction)."""
    order = ["wind_direction", "visibility", "humidity"]  # Klasse c, b, a
    dc = _sms_layout_dc(order)
    sms = _render_sms(dc)
    i_wd, i_vs, i_hu = _token_index(sms, "WD"), _token_index(sms, "VS"), _token_index(sms, "HU")
    assert i_wd < i_vs < i_hu, (
        f"Nutzer-Reihenfolge WD < VS < HU muss auf report.sms_text gelten, "
        f"dem Objekt, das notification_service.py fuer SMS UND "
        f"Telegram-Kurzform sendet: {sms!r}"
    )


# ---------------------------------------------------------------------------
# Fix-Loop (Adversary BROKEN-Verdict, 2026-08-10): F001 + F002
# ---------------------------------------------------------------------------


def test_fixloop_f001_threshold_and_position_combine():
    """Adversary Fix-Loop F001 (CRITICAL): eine Metrik mit KONFIGURIERTEM
    ``sms_threshold`` (Issue #624) UND SMS-Kanal-Position (#1677) darf ihre
    Position nicht verlieren.

    Root Cause vor dem Fix: ``sms_trip.py::format_sms()`` baut zuerst aus
    ``thresholds`` (Zeilen ~725-746) eine threshold-tragende ``MetricSpec``
    ohne ``position`` und belegt damit das Symbol in ``config``. Der
    anschliessende ``disabled_specs``-Merge (Zeilen ~753-755,
    ``config.extend(s for s in disabled_specs if s.symbol not in
    existing_syms)``) verwirft die positionstragende Spec aus
    ``disabled_specs`` daraufhin STILL, weil das Symbol schon "existiert" --
    die Nutzer-Reihenfolge verpufft genau dann, wenn beide Features
    kombiniert werden. Repro des Adversary: gust auf Position 0 OHNE
    Schwelle wirkt (G vor W vor R), MIT ``sms_threshold=15.0`` auf gust
    faellt G wieder an die Default-Position."""
    global_metrics = [
        MetricConfig(metric_id="gust", enabled=True, sms_threshold=15.0),
        MetricConfig(metric_id="wind", enabled=True),
        MetricConfig(metric_id="precipitation", enabled=True),
    ]
    sms_layout = [
        MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
        for i, m in enumerate(["gust", "wind", "precipitation"])
    ]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="i1677fixloopf001", metrics=global_metrics,
        per_channel_layouts={"sms": sms_layout},
    )
    sms = _render_sms(dc)
    i_g, i_w, i_r = _token_index(sms, "G"), _token_index(sms, "W"), _token_index(sms, "R")
    assert i_g < i_w < i_r, (
        f"SMS-Kanal-Position (gust zuerst) muss auch bei konfiguriertem "
        f"Schwellwert (sms_threshold=15.0 auf gust) wirken -- G vor W vor "
        f"R erwartet, unabhaengig vom Schwellwert-Merge: {sms!r}"
    )


def test_fixloop_f002_last_resort_priority_ignores_display_position():
    """Adversary Fix-Loop F002 (MEDIUM): der Last-Resort-Kuerzungszweig
    (``render.py`` Zeilen ~100-114, sortiert Kern-Vorhersage-Token
    ausschliesslich nach dem sicherheitsbasierten ``Token.priority``) darf
    NIEMALS von der Nutzer-Anzeigeposition (``MetricSpec.position``)
    beeinflusst werden (DEC-6/sms_format.md §6). Kein bisheriger Test
    erreicht diesen Zweig fuer KERN-Vorhersage-Token (R/W/G/TH:) mit
    gleichzeitig aktiver Nutzer-Position -- die AC-6-Kuerzungs-Tests bleiben
    im DROP_ORDER-Zweig stecken (DROP_ORDER fasst R/W/G/TH: nie an), und
    keiner davon nutzt einen so kleinen ``max_length``, dass ueberhaupt das
    Last-Resort-Kernstueck aktiv wird.

    Direkter ``build_token_line()`` + ``render(N)``-Aufruf (Muster des
    AC-4-Tests oben, s. Modul-Docstring): ``TripReportFormatter``/
    ``SMSTripFormatter`` haerten ``max_length=160`` fest
    (``trip_report.py`` Zeile ~394 ``format_sms(..., max_length=160, ...)``)
    -- ohne einen extrem kleinen, direkt an ``TokenLine.render()``
    uebergebenen ``max_length`` wird der Last-Resort-Zweig fuer Kern-Token
    strukturell NIE erreicht (DROP_ORDER/PR/K-D-N-Drops reichen bei jeder
    ueber den Produktivpfad erreichbaren SMS-Laenge aus).

    Gewitter (``TH:``) traegt Nutzer-Position 0 (die "beste" Anzeigeposition)
    UND die hoechste ``PRIORITY`` (10) -- unmutiert ueberlebt es das
    Last-Resort-Kuerzen als letztes Kern-Token trotz Position 0 (die
    Position darf die Ueberlebens-Reihenfolge nicht steuern). Bei der
    Mutation "Token.priority aus spec.position ableiten" wuerde ``TH:``
    (Position 0 = niedrigster Wert) stattdessen als ERSTES Kern-Token
    entfernt -- exakt die DEC-6-Verletzung, die dieser Test fangen muss."""
    today = DailyForecast(
        rain_hourly=(HourlyValue(5, 3.0),),
        wind_hourly=(HourlyValue(4, 12.0),),
        gust_hourly=(HourlyValue(4, 22.0),),
        thunder_hourly=(HourlyValue(11, 2.0),),
    )
    forecast = NormalizedForecast(days=(today,))
    specs = [
        MetricSpec(symbol="TH:", position=0),
        MetricSpec(symbol="W", position=1),
        MetricSpec(symbol="G", position=2),
        MetricSpec(symbol="R", position=3),
    ]
    line = build_token_line(forecast, specs, report_type="evening", stage_name="E7")
    rendered = line.render(25)
    assert _present(rendered, "TH:"), (
        f"Gewitter (hoechste PRIORITY=10, unabhaengig von Anzeigeposition 0) "
        f"muss den Last-Resort-Zweig als Kern-Token ueberleben: {rendered!r}"
    )
    assert _present(rendered, "W"), f"W (PRIORITY 8) muss ueberleben: {rendered!r}"
    assert _present(rendered, "G"), f"G (PRIORITY 8) muss ueberleben: {rendered!r}"
    assert not _present(rendered, "R"), (
        f"R (niedrigste PRIORITY=7 unter den vier Kern-Token) muss als "
        f"ERSTES Kern-Token weichen, trotz Nutzer-Position 3 (letzte "
        f"Anzeigeposition) -- Anzeige-Position != Ueberlebensrang: {rendered!r}"
    )
