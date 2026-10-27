"""TDD RED -- #2422 S6, B1: "Gefuehlte Temperatur" (``wind_chill``) kommt als ``TF``
in SMS, Premium-SMS und Telegram-Kurzform an (PO-Entscheid V1, 30.09.).

SPEC: docs/specs/modules/fix_2422_s6_register_leeren.md (AC-1 bis AC-4)

Was der Nutzer erlebt (Fall KHW 403): die Gefuehlte Temperatur ist im SMS-Reiter
aktiv, fehlt aber in der ausgelieferten Kurzform. Token-Form (Klasse (b)
"Invers-Min", wie ``VS``/``FZ``): ``TF<Tiefstwert in ganzen Grad>@<Stunde>``,
Nullform ``TF-``, Datenluecke ``TF?``.

Kein ``Mock()``/``patch()``/``MagicMock``: Loader, Kaskade und Formatter laufen
echt, die einzige Naht ist der Transport-Aufzeichner
(``tests/helpers/transport_mitschrift.py``); Builder-Tests nutzen echte
``DailyForecast``-Werte. Noch nicht existierende Produkt-Symbole
(``DailyForecast.wind_chill_hourly``) werden INNERHALB der Testfunktion benutzt --
jede AC scheitert einzeln mit einer AssertionError statt die Datei beim Sammeln
lahmzulegen.

RED-Gruende (heute): ``wind_chill`` hat im Trip kein Kurzform-Token; ``DailyForecast``
kennt keine Stunden-Serie der gefuehlten Temperatur; ``TF`` fehlt in der
Kuerzungsreihenfolge; ``codes_text``/``KUERZEL`` entfernt ``TF`` im Trip-Kontext;
``/api/sms-symbols`` fuehrt ``wind_chill`` nicht.

GUARDS (heute gruen, muessen gruen bleiben):
``test_ac3_guard_abgewaehlte_kinder_liefern_kein_fl_fd_fn`` (Nutzer-Abwahl wird
nicht uebersteuert) und ``test_ac2_grammatik_minus_vor_zahl_auch_ohne_tf``.
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from tests.tdd._befehl_e2e_fixtures import (
    basis_settings,
    install_transport_fakes,
    lege_po_lage_nutzer_an,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)
from tests.tdd._einstellung_auslieferung_fixtures import (
    DAY,
    TZ,
    _local_to_utc,
    golden_dict,
    render_golden,
    render_trip_dict,
    segment,
)
from tests.tdd._sms_einfach_fixtures import token

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

pytestmark = pytest.mark.filterwarnings("ignore")


def _texte_a_b(monkeypatch) -> dict:
    """{sms, premium_sms, telegram_kurzform} aus den UNVERAENDERTEN Goldens."""
    mit_b, _ = render_golden(monkeypatch, "golden_b")
    mit_a, _ = render_golden(monkeypatch, "golden_a")
    kurz = [s for s in mit_a.sendungen("telegram") if s["parse_mode"] is None]
    assert kurz, "Vorbedingung: golden_a muss die Telegram-Kurzform senden"
    return {
        "sms": mit_b.sendungen("sms")[0]["body"],
        "premium_sms": mit_b.sendungen("premium_sms")[0]["body"],
        "telegram_kurzform": kurz[0]["body"],
    }


# ═══════════════════════════ AC-1 ═══════════════════════════════════════════


def test_ac1_tf_erscheint_genau_einmal_an_der_layout_position(monkeypatch):
    """AC-1: Given ``wind_chill`` aktiv im SMS-Layout (golden_a/golden_b, Position
    0 = erstes Token) und Stundenwerte der gefuehlten Temperatur im Tagesfenster
    (-3 Grad um 6 Uhr, sonst 13 -- Fixture ``_voller_datenpunkt``), When das
    Briefing als SMS, Premium-SMS und Telegram-Kurzform gesendet wird, Then steht
    in allen drei Texten GENAU EIN Token ``TF-3@6`` an der Layout-Position von
    ``wind_chill`` (vor ``W``), und der Text ist <= 160 Zeichen.

    Der Wert ist das Minimum der TAGESFENSTER-Stundenwerte (04-19 Uhr) mit seiner
    Stunde -- nicht das Gehzeit-Minimum (08-12 Uhr, dort 13): Mutation "Gehzeit-
    statt Tagesfenster" -> ``TF13@8``, rot."""
    for kanal, text in _texte_a_b(monkeypatch).items():
        rumpf = text.split(": ", 1)[1].split(" ")
        treffer = [t for t in rumpf if re.fullmatch(r"TF-?\d+@\d+", t)]
        assert treffer == ["TF-3@6"], (
            f"AC-1 ({kanal}): erwartet genau EIN Token 'TF-3@6', gefunden "
            f"{treffer}. Text: {text!r}"
        )
        assert rumpf[0] == "TF-3@6", (
            f"AC-1 ({kanal}): TF gehoert an die Layout-Position von wind_chill "
            f"(Position 0, vor W) -- Tokenfolge: {rumpf}"
        )
        assert len(text) <= 160, f"AC-1 ({kanal}): {len(text)} Zeichen > 160"


def test_ac1_orakel_sieht_wind_chill_in_allen_drei_kanaelen_ohne_register(monkeypatch):
    """AC-1: die Orakel-Dimension "erscheint" ist fuer ``wind_chill`` in ``sms``/
    ``premium_sms``/``telegram_kurzform`` gruen OHNE Register-Eintrag (der
    B1-Eintrag ist entfernt). Die Orakel-Parser lesen ``TF`` ueber das Register
    (``SMS_SYMBOL_BY_METRIC``) -- fehlt dort der Eintrag, ist das Token fuer den
    Parser unsichtbar."""
    from tests.helpers.einstellung_auslieferung_orakel import parse_sms_artig

    for kanal, text in _texte_a_b(monkeypatch).items():
        ids, modi = parse_sms_artig(text)
        assert "wind_chill" in ids, (
            f"AC-1 ({kanal}): wind_chill fehlt im geparsten Text {text!r} -- ids={ids}"
        )
        assert modi["wind_chill"] == "raw"


def test_ac1_produzent_fuellt_serie_aus_dem_tagesfenster_ohne_positiv_filter():
    """AC-1 (Produzent): ``DailyForecast.wind_chill_hourly`` wird in
    ``_segments_to_normalized_forecast`` aus DERSELBEN Tagesfenster-Zeitreihe
    gefuellt wie Regen/Wind/CAPE (``build_day_window_points``, Stunde -> Wert),
    OHNE ``> 0``-Filter: negative gefuehlte Temperaturen sind gueltig.

    Zwei Etappen teilen die Grenz-Stunde 10 (Werte -5 bzw. 4). Die Serie traegt
    je Stunde GENAU die Werte der Fenster-Punktliste (dort bereits je Stunde
    dedupliziert) -- und zwar ALLE, auch die negative Stunde 10.

    Hinweis zu Mutation 6 (Dedup ohne Tiefstwert): ``build_day_window_points``
    liefert je Stunde bereits EINEN Punkt (Erst-Treffer), ``_dedup_by_hour_min``
    sieht im Produzenten nie ein Duplikat -- die Mutation ist aequivalent und
    kann durch keinen Test gefangen werden (siehe Bericht)."""
    from output.renderers.day_window import build_day_window_points
    from output.renderers.sms_trip import _segments_to_normalized_forecast
    from output.tokens.dto import HourlyValue
    from utils.timezone import local_hour

    seg_a = _segment_mit_wind_chill(start_h=8, end_h=10, werte={10: -5.0, 9: 2.0})
    seg_b = _segment_mit_wind_chill(start_h=10, end_h=12, werte={10: 4.0})
    fc = _segments_to_normalized_forecast([seg_a, seg_b], tz=TZ, night_weather=None)
    serie = getattr(fc.days[0], "wind_chill_hourly", None)
    assert serie is not None, (
        "AC-1: DailyForecast traegt keine Stunden-Serie 'wind_chill_hourly' der "
        "gefuehlten Temperatur -- ohne sie kann TF nicht entstehen."
    )
    fenster = build_day_window_points([seg_a, seg_b], None, tz=TZ, start_hour=4, end_hour=19)
    erwartet = tuple(sorted(
        HourlyValue(local_hour(dp.ts, TZ), float(dp.wind_chill_c))
        for dp in fenster if dp.wind_chill_c is not None
    ))
    assert tuple(sorted(serie, key=lambda s: s.hour)) == erwartet, (
        f"AC-1: die Serie muss die Tagesfenster-Stundenwerte tragen (auch "
        f"negative). erwartet={erwartet}, erhalten={tuple(serie)}"
    )
    assert any(s.value < 0 for s in serie), "Testaufbau: es muss ein negativer Wert dabei sein"


def _segment_mit_wind_chill(*, start_h: int, end_h: int, werte: dict):
    """Ein echtes ``SegmentWeatherData`` (Fixture ``segment()``) mit anderer
    Zeitspanne; die Stunde ``h`` der Zeitreihe traegt ``werte[h]`` als gefuehlte
    Temperatur (sonst 13)."""
    basis = segment()
    neue_daten = []
    for dp in basis.timeseries.data:
        h = dp.ts.astimezone(TZ).hour
        neue_daten.append(dataclasses.replace(dp, wind_chill_c=werte.get(h, 13.0)))
    ts = dataclasses.replace(basis.timeseries, data=neue_daten)
    seg = dataclasses.replace(
        basis.segment,
        start_time=_local_to_utc(DAY, start_h), end_time=_local_to_utc(DAY, end_h),
    )
    return dataclasses.replace(basis, segment=seg, timeseries=ts)


# ═══════════════════════════ AC-2 ═══════════════════════════════════════════


def _zeile(forecast_kwargs: dict, specs, *, max_length: int = 160) -> str:
    """Echter Token-Builder + Renderer mit echten ``DailyForecast``-Werten.
    Ein fehlendes Produkt-Feld scheitert als AssertionError (kein TypeError)."""
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, NormalizedForecast
    from output.tokens.render import render_line

    try:
        tag = DailyForecast(**forecast_kwargs)
    except TypeError as exc:
        pytest.fail(f"AC-2: DailyForecast kennt das Feld noch nicht: {exc}")
    line = build_token_line(
        NormalizedForecast(days=(tag,)), specs, report_type="evening", stage_name="E1",
    )
    return render_line(line, max_length)


def _tokens(text: str) -> list[str]:
    return text.split(": ", 1)[1].split(" ")


def test_ac2_nullform_und_luecke():
    """AC-2 (a)/(b): aktive ``wind_chill`` ohne Stundenwerte -> ``TF-``; mit
    Datenluecke im Fenster -> ``TF?`` (``_gap_or``, #1483). Beide sind vom
    Wert ``TF-3@6`` per ``fullmatch`` eindeutig unterscheidbar."""
    from output.tokens.dto import MetricSpec

    spec = [MetricSpec(symbol="TF", enabled=True)]
    null = _zeile({"wind_chill_hourly": ()}, spec)
    assert "TF-" in _tokens(null), f"AC-2 (a): Nullform 'TF-' fehlt: {null!r}"
    luecke = _zeile({"wind_chill_hourly": (), "has_data_gap": True}, spec)
    assert "TF?" in _tokens(luecke), f"AC-2 (b): Luecken-Form 'TF?' fehlt: {luecke!r}"


@pytest.mark.parametrize(
    "werte, erwartet",
    [
        (((6, -3.0), (9, 8.0)), "TF-3@6"),   # negativer Tiefstwert
        (((6, 3.0), (9, 8.0)), "TF3@6"),     # positiver Tiefstwert
        (((7, 1.4), (9, -0.4)), "TF0@9"),    # ganze Grad gerundet, Stunde des Minimums
    ],
)
def test_ac2_wert_ist_tiefstwert_mit_stunde(werte, erwartet):
    """AC-2: Klasse (b) Invers-Min -- ``TF<Tiefstwert ganz>@<Stunde>``, ohne
    Schwelle immer sichtbar, ohne ``> 0``-Filter."""
    from output.tokens.dto import HourlyValue, MetricSpec

    serie = tuple(HourlyValue(h, v) for h, v in werte)
    text = _zeile({"wind_chill_hourly": serie}, [MetricSpec(symbol="TF", enabled=True)])
    assert erwartet in _tokens(text), f"AC-2: erwartet {erwartet!r} in {text!r}"


def test_ac2_orakel_unterscheidet_nullform_und_negativen_wert():
    """AC-2: ``TF-`` (Nullform) und ``TF-3@6`` (negativer Wert) werden vom
    Orakel-Parser unterschieden: die Grammatik bekommt das optionale Minus vor
    Zahlen. Nullform = kein Modus ablesbar, ``-3@6`` = Zahl (raw)."""
    from tests.helpers.einstellung_auslieferung_orakel import _sms_treffer, parse_sms_artig

    treffer = _sms_treffer("E1: TF- TF-3@6")
    werte = [wert for _, mid, wert in treffer if mid == "wind_chill"]
    assert werte == ["-", "-3@6"], (
        f"AC-2: der Parser muss 'TF-' und 'TF-3@6' getrennt lesen (erwartet "
        f"['-', '-3@6'] fuer wind_chill), erhalten {treffer}"
    )
    _, modi = parse_sms_artig("E1: TF-3@6")
    assert modi.get("wind_chill") == "raw"
    _, modi_null = parse_sms_artig("E1: TF-")
    assert modi_null.get("wind_chill") is None


def test_ac2_grammatik_minus_vor_zahl_auch_ohne_tf():
    """AC-2 (GUARD, unabhaengig vom Register): ``FL-3`` (negativer Einzelwert
    OHNE Stunde) und ``FL-`` (Nullform) parst die erweiterte Grammatik
    unterschiedlich. Heute gruen (das Minus steht bereits im Orakel), bewacht die
    Grammatik gegen ein zurueckgedrehtes optionales Minus."""
    from tests.helpers.einstellung_auslieferung_orakel import _sms_treffer

    werte = [w for _, mid, w in _sms_treffer("E1: FL-3 FD-") if mid.startswith("wind_chill_day")]
    assert werte == ["-3", "-"], f"Grammatik: {werte}"


def test_ac2_kuerzung_tf_faellt_als_erstes_der_komfort_angaben():
    """AC-2 (c) / Mutation 4: Beim Kuerzen (160-Zeichen-Budget) faellt ``TF`` als
    ERSTES der Komfort-Zusatzangaben -- VOR ``FN``/``FL``/``FD`` und vor ``PR``.
    Reihenfolge ``("TF", "FN", "FL", "FD")`` (``tokens/render.py``).

    Die Zeile wird so gebaut, dass pro Schritt genau EIN Token zu viel ist
    (Budget = Laenge - 1): erst faellt TF, dann FN, dann FD (der Bereich
    ``FD-3/10`` traegt das FD-Symbol) -- und PR/W/G/TH bleiben jeweils stehen."""
    from output.tokens.dto import HourlyValue, MetricSpec

    felder = {
        "wind_chill_hourly": (HourlyValue(6, -3.0), HourlyValue(9, 4.0)),
        "night_wind_chill_min_c": -2.0,
        "wind_chill_min_c": -3.0, "wind_chill_max_c": 10.0,
        "pop_hourly": (HourlyValue(4, 60.0),),
        "wind_hourly": (HourlyValue(4, 20.0),),
        "gust_hourly": (HourlyValue(4, 45.0),),
    }
    specs = [MetricSpec(symbol=s, enabled=True) for s in ("TF", "FN", "FL", "FD", "PR", "W", "G")]
    voll = _zeile(felder, specs, max_length=10_000)
    toks = _tokens(voll)
    assert "TF-3@6" in toks and "FN-2" in toks, f"Testaufbau: {voll!r}"
    assert any(t.startswith("FD") for t in toks) and any(t.startswith("PR") for t in toks)

    def _sym(text: str) -> set[str]:
        return {re.match(r"[A-Z]+", t).group(0) for t in _tokens(text)}

    schritt1 = _zeile(felder, specs, max_length=len(voll) - 1)
    assert "TF" not in _sym(schritt1), f"AC-2 (c): TF muss ZUERST fallen: {schritt1!r}"
    assert {"FN", "FD", "PR", "W", "G"} <= _sym(schritt1), (
        f"AC-2 (c): FN/FD/PR/W/G muessen beim ersten Kuerzungsschritt stehen bleiben: {schritt1!r}"
    )
    schritt2 = _zeile(felder, specs, max_length=len(schritt1) - 1)
    assert "FN" not in _sym(schritt2) and {"FD", "PR", "W", "G"} <= _sym(schritt2), (
        f"AC-2 (c): nach TF faellt FN: {schritt2!r}"
    )
    schritt3 = _zeile(felder, specs, max_length=len(schritt2) - 1)
    assert "FD" not in _sym(schritt3) and {"PR", "W", "G"} <= _sym(schritt3), (
        f"AC-2 (c): danach faellt FD, PR bleibt: {schritt3!r}"
    )


# ═══════════════════════════ AC-3 ═══════════════════════════════════════════


def _variante_beide_aktiv() -> dict:
    """golden_b mit Eltern-Metrik ``wind_chill`` UND Kind ``wind_chill_day_low``
    (FL) ausdruecklich aktiv -- im SMS-Layout und im globalen Maximum (Kaskade:
    Kanal <= global). ``day_high``/``night`` bleiben ausdruecklich abgewaehlt."""
    d = golden_dict("golden_b")
    dc = d["display_config"]
    for liste in (dc["channel_layouts"]["sms"], dc["metrics"]):
        for m in liste:
            if m["metric_id"] == "wind_chill_day_low":
                m["enabled"] = True
                m["bucket"] = "primary"
                m["order"] = 9
    return d


def test_ac3_eltern_und_kind_aktiv_beide_token_keines_unterdrueckt(monkeypatch):
    """AC-3: Given Eltern-Metrik ``wind_chill`` UND Kind ``wind_chill_day_low``
    aktiv, When das Briefing gesendet wird, Then erscheinen BEIDE Token --
    ``TF-3@6`` (Tagesfenster 04-19, mit Uhrzeit) und ``FL13`` (Gehzeit-Fenster
    08-12) -- keines wird unterdrueckt. Die Fixture liefert verschiedene Tiefst-
    werte fuer die zwei Fenster (-3 um 6 Uhr, sonst 13), damit TF != FL messbar
    ist."""
    mit, _ = render_trip_dict(monkeypatch, _variante_beide_aktiv(), name="golden_b-tf-fl")
    for kanal in ("sms", "premium_sms"):
        text = mit.sendungen(kanal)[0]["body"]
        assert token(text, "TF") == "TF-3@6", f"AC-3 ({kanal}): TF fehlt/falsch in {text!r}"
        assert token(text, "FL") == "FL13", f"AC-3 ({kanal}): FL fehlt/falsch in {text!r}"


def test_ac3_nur_eltern_metrik_nur_tf_ohne_kinder_token(monkeypatch):
    """AC-3: sind die drei Kinder ausdruecklich abgewaehlt (Goldens a/b: ``enabled:
    false``) und nur die Eltern-Metrik aktiv, erscheint NUR ``TF`` -- und zwar in
    allen drei SMS-artigen Kanaelen."""
    for kanal, text in _texte_a_b(monkeypatch).items():
        assert token(text, "TF") == "TF-3@6", f"AC-3 ({kanal}): TF fehlt in {text!r}"


def test_ac3_guard_abgewaehlte_kinder_liefern_kein_fl_fd_fn(monkeypatch):
    """AC-3 (GUARD, heute gruen): die ausdrueckliche Abwahl der Kinder wird vom
    Produkt nicht uebersteuert -- kein ``FL``/``FD``/``FN`` in den Texten, auch
    nicht nach der Einfuehrung von ``TF`` (``loader._DERIVED_METRIC_RULES``: ein
    explizites ``false`` schlaegt die Ableitung; Alternative B1-alt verworfen)."""
    for kanal, text in _texte_a_b(monkeypatch).items():
        for kind in ("FL", "FD", "FN"):
            assert token(text, kind) is None, (
                f"AC-3 ({kanal}): {kind} darf bei abgewaehlten Kindern nicht "
                f"erscheinen: {text!r}"
            )


# ═══════════════════════════ AC-4 ═══════════════════════════════════════════


def _codes_treffer(text: str):
    return re.search(r"(?<![A-Za-z+])TF (gefühlt|feels like)", text)


def test_ac4_kuerzel_und_codes_nennen_tf_im_trip_ueber_den_echten_eingang(monkeypatch, user_ids):
    """AC-4: ``KUERZEL``/``CODES`` als eingehende Nachricht durch den ECHTEN
    Kanal-Eingang (Premium-SMS-Reader = englisch; Telegram-Reader = deutsch),
    Trip-Kontext (kein aufgeloester Ortsvergleich): die Antwort nennt ``TF`` mit
    Bedeutung. Loest #2454 AC-6 ("TF entfaellt im Trip") ab. Nicht nur
    ``codes_text()`` direkt."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    vorher = len(recorder.premium_sms_out)
    sende_premium_sms(settings, recorder, nutzer, "codes")
    en = "".join(e["text"] for e in recorder.premium_sms_out[vorher:]
                 if e["to"] == nutzer.premium_sms_reply_to)
    assert en, "Vorbedingung: auf 'codes' per Premium-SMS wurde nichts geantwortet."
    assert _codes_treffer(en), f"AC-4: die CODES-Antwort (en) nennt TF nicht:\n{en}"

    vorher_tg = len(recorder.telegram_inhalte(nutzer.telegram_chat_id))
    sende_telegram_text(settings, nutzer, "kuerzel")
    neu = recorder.telegram_inhalte(nutzer.telegram_chat_id)[vorher_tg:]
    de = "\n".join(e["payload"].get("text", "") for e in neu)
    assert de, "Vorbedingung: auf 'kuerzel' per Telegram wurde nichts geantwortet."
    assert _codes_treffer(de), f"AC-4: die KUERZEL-Antwort (de) nennt TF nicht:\n{de}"


def test_ac4_editor_kuerzelmarken_fuehren_wind_chill_mit_tf():
    """AC-4: ``GET /api/sms-symbols`` (Editor-Kuerzelmarken) fuehrt ``wind_chill``
    mit ``TF`` -- und ``TF`` bezeichnet dort keine zweite Groesse."""
    from api.routers.config import get_sms_symbols

    antwort = get_sms_symbols()
    je_metrik = {e["metric_id"]: e["sms_symbols"] for e in antwort["metrics"]}
    assert je_metrik.get("wind_chill") == ["TF"], (
        f"AC-4: /api/sms-symbols muss wind_chill mit ['TF'] fuehren, hat "
        f"{je_metrik.get('wind_chill')!r}"
    )
    andere = [m for m, syms in je_metrik.items() if "TF" in syms and m != "wind_chill"]
    assert andere == [], f"AC-4: TF bezeichnet weitere Groessen: {andere}"
    # die Tages-Kuerzel der Kinder bleiben unveraendert
    assert je_metrik["wind_chill_day_low"] == ["FL"]
    assert je_metrik["wind_chill_day_high"] == ["FD"]
    assert je_metrik["wind_chill_night"] == ["FN"]
