"""TDD RED -- #2422 S6, B2: "Roh"/"Einfach" je Metrik wirkt in SMS, Premium-SMS und
Telegram-Kurzform (PO-Entscheid: ASCII-Stufenform, Spec-Vorschlag mit den ACs
freizugeben).

SPEC: docs/specs/modules/fix_2422_s6_register_leeren.md (AC-5 bis AC-11)

Erwartete Form: Roh = Zahl (``CT70@4``), Einfach = GSM-7-Stufe mit Doppelpunkt im
Kuerzel (``CT:SCT@4``; Konvention #1824 B). Wolken: ``CLR FEW SCT BKN OVC``
(Baender von ``metric_format.cloud_emoji``); ``thunder``/``wind_direction``/``sunshine`` und die
Ampel-Groessen haben in der SMS EINE Form (Roh == Einfach, byte-gleich).

#2422 S6b (PO-Entscheid 2026-10-01, SPEC
docs/specs/modules/fix_2422_s6b_cape_aus_roh_einfach.md): ``cape`` ist im Katalog
``selectable=False`` (#1585) und faellt in der Kaskade aus JEDEM Kanal-Layout --
sein Roh/Einfach-Modus konnte nie wirken (Staging-Befund S6, Verdict BROKEN).
``cape`` ist deshalb aus ``SMS_FORMAT_MODE_METRIC_IDS`` gestrichen; AC-6, der
CAPE-Teil von AC-7 und der cape-Teil von AC-8 sind abgeloest. Die Zusicherung
steht jetzt an der Wirkstelle (Invariante "jede Id der Konstante ist waehlbar",
Endpoint-Gleichheit, ``STUFEN_FN``-Drift, Bestands-Trip mit ``cape``).
Zudem stehen ``cloud_mid``/``cloud_high`` in keinem Golden-SMS-Layout -- der
Vakuum-Schutz laeuft ueber in-Test-Varianten der Goldens (``_sms_einfach_fixtures``),
die Golden-Dateien bleiben unveraendert.

RED-Gruende (heute): ``format_mode`` erreicht den Builder nicht (B2); es gibt keine
GSM-7-Einfach-Stufe; ``SMS_FORMAT_MODE_METRIC_IDS`` und ``sms_format_capable``
existieren nicht.

GUARDS (heute gruen, muessen gruen bleiben): Roh/Einfach-Texte der Groessen
OHNE SMS-Form sind byte-gleich; Gewitter-Stufenform ``TH:`` = E-Mail-Band;
Orakel-Konstantenpfad; Fixture-CAPE >= 300.

Keine Mocks: Builder mit echten ``DailyForecast``-Werten, Produkt-Durchlaeufe ueber
echten Loader/Kaskade/Formatter mit dem Transport-Aufzeichner als einziger Naht.
"""
from __future__ import annotations


import pytest

from tests.tdd._gsm7_charset import assert_gsm7_clean
from tests.tdd._einstellung_auslieferung_fixtures import (
    TZ,
    _voller_datenpunkt,
    night_weather,
    render_golden,
    render_trip_dict,
    segment,
)
from tests.tdd._sms_einfach_fixtures import (
    AMPEL_REIHENFOLGE,
    AMPEL_ZU_STUFE,
    SPEC_OHNE_SMS_FORM,
    SPEC_SMS_FORMAT_IDS,
    WOLKEN,
    WOLKEN_SYMBOL,
    sms_texte,
    spec,
    stufe_aus_email_band,
    token,
    tokens_von,
    variante,
    zeile,
)

pytestmark = pytest.mark.filterwarnings("ignore")

#: Die elf Groessen, die ueber Layout/Kaskade einen Kanaltext erreichen
#: (``cape`` ist ``selectable=False`` und fehlt -- siehe Modul-Docstring).
PRODUKT_ERREICHBAR = WOLKEN + SPEC_OHNE_SMS_FORM
_TOKEN_JE_GROESSE = {
    "cloud_total": "CT", "cloud_low": "CL", "cloud_mid": "CM", "cloud_high": "CH",
    "thunder": "TH:", "wind_direction": "WD:", "sunshine": "SU", "wind": "W",
    "gust": "G", "rain_probability": "PR", "precipitation": "R",
}


def _hv(stunde: int, wert: float):
    from output.tokens.dto import HourlyValue

    return HourlyValue(stunde, float(wert))


# ═══════════════════════════ AC-5: Wolken ═══════════════════════════════════

_CLOUD_FELD = {
    "CT": "cloud_total_hourly", "CL": "cloud_low_hourly",
    "CM": "cloud_mid_hourly", "CH": "cloud_high_hourly",
}
_CLOUD_ID = {"CT": "cloud_total", "CL": "cloud_low", "CM": "cloud_mid", "CH": "cloud_high"}


@pytest.mark.parametrize("symbol", ["CT", "CL", "CM", "CH"])
def test_ac5_wolken_bandgrenzen_roh_und_einfach(symbol):
    """AC-5: Given eine Wolken-Metrik mit Spitzenwert ``v`` % um 4 Uhr, When
    ``format_mode`` Roh ist, Then ``<SYM><v>@4``; When Einfach, Then
    ``<SYM>:<STUFE>@4`` mit ``CLR`` (<=10), ``FEW`` (<=30), ``SCT`` (<=70), ``BKN``
    (<=90), ``OVC`` (>90) -- die Stufe ABGELEITET aus den Baendern der
    E-Mail-Klassifikation ``cloud_emoji`` (nicht hart kopiert). Geprueft wird JEDER
    ganzzahlige Wert 1..100 (faengt die Grenzen 10/11, 30/31, 70/71, 90/91 und
    jede Verschiebung um 1, Mutation 5).

    Mutationen: ``format_mode`` nicht durchreichen -> Einfach-Text bleibt Zahl
    (rot); Emoji-``friendly_label`` statt Stufe -> rot."""
    feld = _CLOUD_FELD[symbol]
    falsch: list[str] = []
    for v in range(1, 101):
        roh = zeile({feld: (_hv(4, v),)}, [spec(symbol, "raw", _CLOUD_ID[symbol])])
        einfach = zeile({feld: (_hv(4, v),)}, [spec(symbol, "symbol", _CLOUD_ID[symbol])])
        soll_roh, soll_einfach = f"{symbol}{v}@4", f"{symbol}:{stufe_aus_email_band(v)}@4"
        if soll_roh not in tokens_von(roh):
            falsch.append(f"v={v} roh: {soll_roh!r} fehlt in {roh!r}")
        if soll_einfach not in tokens_von(einfach):
            falsch.append(f"v={v} einfach: {soll_einfach!r} fehlt in {einfach!r}")
    assert not falsch, "AC-5: " + "; ".join(falsch[:6]) + (
        f" ... ({len(falsch)} Abweichungen)" if len(falsch) > 6 else ""
    )


def test_ac5_wolken_nullform_ohne_sample_bleibt_minus_in_beiden_modi():
    """AC-5: Ein 0-%-Wert erzeugt wie in der Roh-Form kein Sample und ergibt ``-``
    (Bestandsverhalten, ``> 0``-Filter) -- in BEIDEN Modi dasselbe Token."""
    roh = zeile({"cloud_total_hourly": ()}, [spec("CT", "raw", "cloud_total")])
    einfach = zeile({"cloud_total_hourly": ()}, [spec("CT", "symbol", "cloud_total")])
    assert "CT-" in tokens_von(roh), roh
    assert tokens_von(einfach) == tokens_von(roh), (
        f"AC-5: Nullform muss in beiden Modi gleich sein: roh={roh!r}, einfach={einfach!r}"
    )


def test_ac5_wolken_erst_und_spitzenwert_als_stufen():
    """AC-5: Mit Schwelle (Erst-/Spitzenwert) gilt ``Stufe@h(Stufe@h)``:
    75 % um 4 Uhr, Spitze 95 % um 9 Uhr -> Roh ``CT75@4(95@9)``, Einfach
    ``CT:BKN@4(OVC@9)`` (Worst-Case-Beispiel der Spec). Gleiche Stufe an
    verschiedenen Stunden kollabiert NICHT (``CT:SCT@4(SCT@9)``); die Schwelle
    selbst arbeitet weiter auf den ZAHLEN."""
    serie = (_hv(4, 75), _hv(9, 95))
    roh = zeile({"cloud_total_hourly": serie}, [spec("CT", "raw", "cloud_total", threshold=50.0)])
    einfach = zeile({"cloud_total_hourly": serie}, [spec("CT", "symbol", "cloud_total", threshold=50.0)])
    assert "CT75@4(95@9)" in tokens_von(roh), roh
    assert "CT:BKN@4(OVC@9)" in tokens_von(einfach), (
        f"AC-5: erwartet 'CT:BKN@4(OVC@9)', erhalten {einfach!r}"
    )
    gleich = (_hv(4, 60), _hv(9, 70))
    einfach2 = zeile({"cloud_total_hourly": gleich},
                     [spec("CT", "symbol", "cloud_total", threshold=50.0)])
    assert "CT:SCT@4(SCT@9)" in tokens_von(einfach2), einfach2
    # Schwelle arbeitet auf Zahlen: Erstwert erst ab 62 % -> Stunde 9 ist der Erstwert.
    schwelle = zeile({"cloud_total_hourly": gleich},
                     [spec("CT", "symbol", "cloud_total", threshold=65.0)])
    assert "CT:SCT@9" in tokens_von(schwelle), schwelle


def test_ac5_orakel_liest_roh_als_raw_und_einfach_als_friendly():
    """AC-5: das Orakel erkennt ``CT70@4`` als "raw" und ``CT:SCT@4`` als
    "friendly" (Grammatik-Erweiterung um ``:``-Stufenwerte). Reiner Parser-Test
    (heute gruen, Guard der Orakel-Erweiterung)."""
    from tests.helpers.einstellung_auslieferung_orakel import parse_sms_artig

    _, roh = parse_sms_artig("E1: CT70@4 CL40@4")
    _, einfach = parse_sms_artig("E1: CT:SCT@4 CL:BKN@4(OVC@9)")
    assert roh["cloud_total"] == "raw" and roh["cloud_low"] == "raw"
    assert einfach["cloud_total"] == "friendly" and einfach["cloud_low"] == "friendly"


# ═══════════════════════════ AC-5/AC-10: Produktpfad ═════════════════════════


def test_ac5_produktpfad_wolken_roh_und_einfach_in_allen_drei_kanaelen(monkeypatch):
    """AC-5 (Produktpfad, Mutation 1): gespeichertes Trip-JSON mit allen vier
    Wolken-Metriken im SMS-Layout, je Metrik ``use_friendly_format`` -> echter
    Loader/Kaskade/Formatter -> SMS, Premium-SMS und Telegram-Kurzform. Werte der
    Fixture: CT 70, CL 40, CM 30, CH 20 %. Roh = Zahlen, Einfach = Stufen aus den
    E-Mail-Baendern."""
    werte = {"cloud_total": 70, "cloud_low": 40, "cloud_mid": 30, "cloud_high": 20}
    roh_texte = sms_texte(monkeypatch, standard="raw")
    einfach_texte = sms_texte(monkeypatch, standard="einfach")
    for kanal in ("sms", "premium_sms", "telegram_kurzform"):
        for mid, pct in werte.items():
            sym = WOLKEN_SYMBOL[mid]
            assert token(roh_texte[kanal], sym) == f"{sym}{pct}@4", (
                f"AC-5 ({kanal}, roh): {sym} erwartet {sym}{pct}@4 in {roh_texte[kanal]!r}"
            )
            assert token(einfach_texte[kanal], sym) == f"{sym}:{stufe_aus_email_band(pct)}@4", (
                f"AC-5 ({kanal}, einfach): {sym} erwartet "
                f"{sym}:{stufe_aus_email_band(pct)}@4 in {einfach_texte[kanal]!r}"
            )


def test_ac5_modus_ist_je_metrik_nicht_kanalweit(monkeypatch):
    """AC-5: die Wahl gilt PRO Metrik -- CT Einfach, CL Roh im selben Text."""
    texte = sms_texte(monkeypatch, {"cloud_total": "einfach", "cloud_low": "raw",
                                    "cloud_mid": "einfach", "cloud_high": "raw"})
    for kanal, text in texte.items():
        assert token(text, "CT") == "CT:SCT@4", f"({kanal}) {text!r}"
        assert token(text, "CL") == "CL40@4", f"({kanal}) {text!r}"
        assert token(text, "CM") == "CM:FEW@4", f"({kanal}) {text!r}"
        assert token(text, "CH") == "CH20@4", f"({kanal}) {text!r}"


def test_ac10_bestandsnutzer_katalog_default_einfach_raw_bleibt_zahl(monkeypatch):
    """AC-10 (PO-Freigabe): Trip-JSON OHNE ``format_mode``/``use_friendly_format``
    (Katalog-Default ``symbol``) zeigt die Wolke kuenftig als Stufe
    (``CT:SCT@4``); ein ausdrueckliches ``format_mode: "raw"`` bleibt die Zahl
    (``CT70@4``). Fuer ``thunder``/``wind_direction``/``sunshine``/Ampel-Groessen
    aendert sich nichts (siehe Guard ``test_ac8_groessen_ohne_sms_form_...``)."""
    from tests.tdd._sms_einfach_fixtures import variante as _v

    mit_d, _ = render_trip_dict(monkeypatch, _v("golden_b", {"cloud_total": "default"}),
                                name="s6-default")
    mit_r, _ = render_trip_dict(monkeypatch, _v("golden_b", {"cloud_total": "raw_explizit"}),
                                name="s6-raw")
    for kanal in ("sms", "premium_sms"):
        assert token(mit_d.sendungen(kanal)[0]["body"], "CT") == "CT:SCT@4", (
            f"AC-10 ({kanal}): Katalog-Default muss als Stufe erscheinen: "
            f"{mit_d.sendungen(kanal)[0]['body']!r}"
        )
        assert token(mit_r.sendungen(kanal)[0]["body"], "CT") == "CT70@4", (
            f"AC-10 ({kanal}): ausdruecklich Roh bleibt die Zahl: "
            f"{mit_r.sendungen(kanal)[0]['body']!r}"
        )


# ═════════════ S6b: CAPE raus, Zusicherung an der Wirkstelle ═══════════════
# SPEC: docs/specs/modules/fix_2422_s6b_cape_aus_roh_einfach.md (AC-1 bis AC-4).
# Loest AC-6, den CAPE-Teil von AC-7 und den cape-Teil von AC-8 aus S6 ab.


def test_s6b_ac1_jede_roh_einfach_groesse_ist_waehlbar():
    """S6b AC-1 (Invariante): jede Id in ``SMS_FORMAT_MODE_METRIC_IDS`` ist im
    echten Katalog ``selectable=True`` UND besteht ``models._is_selectable`` --
    sonst filtert die Kanal-Kaskade sie aus jedem Layout und ihr Roh/Einfach-Modus
    kann nie wirken (Staging-Befund S6: ``cape``).

    Mutation: ``"cape"`` zurueck in die Konstante -> rot."""
    from app.metric_catalog import SMS_FORMAT_MODE_METRIC_IDS, get_metric
    from app.models import _is_selectable

    nicht_waehlbar = sorted(
        mid for mid in SMS_FORMAT_MODE_METRIC_IDS
        if not (get_metric(mid).selectable and _is_selectable(mid))
    )
    assert not nicht_waehlbar, (
        f"S6b AC-1: nicht waehlbare Groessen in SMS_FORMAT_MODE_METRIC_IDS: "
        f"{nicht_waehlbar} -- ihr Roh/Einfach-Modus erreicht nie einen Kanaltext"
    )


def test_s6b_ac2_endpoint_sms_format_capable_genau_die_konstante_und_die_wolken():
    """S6b AC-2 (Wirkstelle Endpoint): ``GET /api/metrics`` meldet
    ``sms_format_capable=true`` fuer GENAU die Ids der Konstante -- ohne
    Schnittmenge mit der Antwort: eine Id der Konstante, die der Endpoint nicht
    fuehrt (nicht waehlbar), ist eine Abweichung. Und die Menge sind genau die vier
    Wolken-Groessen (wortgleich aus der Spec).

    Mutation: ``"cape"`` zurueck in die Konstante -> rot (Konstante != Endpoint)."""
    import app.metric_catalog as katalog
    from api.routers.config import get_metrics

    eintraege = [m for gruppe in get_metrics().values() for m in gruppe]
    wahr = {m["id"] for m in eintraege if m.get("sms_format_capable") is True}
    assert wahr == {"cloud_total", "cloud_low", "cloud_mid", "cloud_high"}, (
        f"S6b AC-2: sms_format_capable=true fuer {sorted(wahr)}"
    )
    assert wahr == set(katalog.SMS_FORMAT_MODE_METRIC_IDS), (
        f"S6b AC-2: Konstante {sorted(katalog.SMS_FORMAT_MODE_METRIC_IDS)} verspricht "
        f"mehr, als der Endpoint anbietet ({sorted(wahr)})"
    )


def test_s6b_ac3_stufen_fn_spiegelt_die_konstante_ohne_cp():
    """S6b AC-3 (Drift): die Kuerzel von ``STUFEN_FN`` sind genau die SMS-Kuerzel
    der Ids in ``SMS_FORMAT_MODE_METRIC_IDS`` (``CT``/``CL``/``CM``/``CH``); fuer
    ``CP`` gibt es keine Stufenabbildung -- eine spaetere Freischaltung von
    ``cape`` erbt keine ungeprueften Baender.

    Mutation: ``STUFEN_FN["CP"]`` wieder einfuegen -> rot."""
    from app.metric_catalog import SMS_FORMAT_MODE_METRIC_IDS, SMS_SYMBOL_BY_METRIC
    from output.tokens.metrics import STUFEN_FN

    soll = {SMS_SYMBOL_BY_METRIC[mid] for mid in SMS_FORMAT_MODE_METRIC_IDS}
    assert "CP" not in STUFEN_FN, "S6b AC-3: STUFEN_FN fuehrt noch eine CAPE-Stufe"
    assert set(STUFEN_FN) == soll == {"CT", "CL", "CM", "CH"}, (
        f"S6b AC-3: STUFEN_FN={sorted(STUFEN_FN)}, Kuerzel der Konstante={sorted(soll)}"
    )


def _mit_cape(golden: str, modus: str | None) -> dict:
    """Golden-Variante (alles Roh); bei ``modus`` zusaetzlich ein Bestands-Eintrag
    ``cape`` im SMS-Layout und im globalen Maximum, mit ``format_mode`` UND
    ``use_friendly_format`` (Altbestand aus S6)."""
    d = variante(golden)
    if modus is None:
        return d
    dc = d["display_config"]
    dc["channel_layouts"]["sms"].append({
        "metric_id": "cape", "enabled": True, "bucket": "primary", "order": 99,
        "format_mode": modus, "use_friendly_format": modus == "symbol",
    })
    dc["metrics"].append({"metric_id": "cape", "enabled": True, "order": 99})
    return d


def _drei_texte(monkeypatch, modus: str | None) -> dict:
    mit_b, _ = render_trip_dict(monkeypatch, _mit_cape("golden_b", modus), name="s6b-b")
    mit_a, _ = render_trip_dict(monkeypatch, _mit_cape("golden_a", modus), name="s6b-a")
    kurz = [s for s in mit_a.sendungen("telegram") if s["parse_mode"] is None]
    assert kurz, "Vorbedingung: golden_a muss die Telegram-Kurzform senden"
    return {
        "sms": mit_b.sendungen("sms")[0]["body"],
        "premium_sms": mit_b.sendungen("premium_sms")[0]["body"],
        "telegram_kurzform": kurz[0]["body"],
    }


@pytest.mark.parametrize("modus", ["raw", "symbol"])
def test_s6b_ac4_bestandstrip_mit_cape_format_mode_bleibt_byte_gleich(monkeypatch, modus):
    """S6b AC-4 (GUARD, Produktpfad): ein Bestands-Trip mit gespeichertem
    ``cape``-Eintrag inklusive ``format_mode`` im SMS-Layout laeuft ohne Fehler
    durch Loader/Kaskade/Formatter; SMS, Premium-SMS und Telegram-Kurzform tragen
    kein ``CP``-Token und sind BYTE-GLEICH zum selben Trip ohne ``cape``-Eintrag
    (``cape`` bleibt wie seit #1585 ausgefiltert). Vakuum-Schutz: die Fixture
    liefert CAPE >= 300 J/kg, ein durchgerutschtes ``CP`` waere also sichtbar."""
    dp = _voller_datenpunkt(20, 6)
    assert dp.cape_jkg is not None and dp.cape_jkg >= 300.0, "Testaufbau: CAPE fehlt"
    ohne = _drei_texte(monkeypatch, None)
    mit = _drei_texte(monkeypatch, modus)
    for kanal in ohne:
        assert token(mit[kanal], "CP") is None, f"S6b AC-4 ({kanal}): CP im Text {mit[kanal]!r}"
        assert mit[kanal] == ohne[kanal], (
            f"S6b AC-4 ({kanal}, cape={modus}): Bestandseintrag veraendert den Text.\n"
            f"ohne={ohne[kanal]!r}\nmit ={mit[kanal]!r}"
        )


def test_s6b_ac4_vorschau_kennt_keine_cape_einfachform():
    """S6b AC-4 (Vorschau, Builder-Naht ``build_sms_fidelity_specs``): auch ein
    ``format_by_metric`` mit ``cape: "symbol"`` (Altbestand) erzeugt keine
    CAPE-Stufe ``CP:`` -- cape hat keine Roh/Einfach-Form mehr, Roh und Einfach
    rendern denselben Text.

    Hinweis: Steht ``cape`` in ``metric_ids``, zeigt die Editor-Vorschau ``CP<n>``
    als Zahl -- unveraendertes Vor-S6-Verhalten; der Editor bietet ``cape`` nicht
    an (``/api/metrics`` filtert ``selectable=False``)."""
    from output.renderers.sms_trip import _segments_to_normalized_forecast
    from output.tokens.builder import build_token_line
    from output.tokens.render import render_line
    from services.validator_render_service import build_sms_fidelity_specs

    forecast = _segments_to_normalized_forecast(
        [segment()], tz=TZ, night_weather=night_weather(),
    )

    def vorschau(fm: str) -> str:
        specs = build_sms_fidelity_specs(["cloud_total", "cape"], format_by_metric={"cape": fm})
        return render_line(
            build_token_line(forecast, specs, report_type="evening", stage_name="E1"), 160,
        )

    einfach, roh = vorschau("symbol"), vorschau("raw")
    assert "CP:" not in einfach, f"S6b AC-4: Vorschau zeigt eine CAPE-Stufe: {einfach!r}"
    assert einfach == roh, f"S6b AC-4: cape Roh/Einfach unterscheiden sich: {roh!r} vs {einfach!r}"


# ═══════════════════════════ AC-7: Kanalgleichheit ══════════════════════════


@pytest.mark.parametrize("stufe_name", ["LOW", "MED", "HIGH"])
def test_ac7_guard_gewitter_stufe_entspricht_thunder_ampel_band(stufe_name):
    """AC-7 (GUARD, heute gruen): ``TH:`` ist bereits die Stufenform der
    E-Mail-Klassifikation ``thunder_ampel_band`` -- ``L``/``M``/``H`` aus dem Band,
    nicht hart kopiert. Bewacht, dass die B2-Umstellung ``TH:`` nicht veraendert
    (Gewitter hat in der SMS EINE Form)."""
    from app.models import ThunderLevel
    from output.metric_format import thunder_ampel_band, thunder_label_value
    from output.tokens.dto import MetricSpec

    level = ThunderLevel[stufe_name]
    band = thunder_ampel_band(level)
    erwartet = f"TH:{AMPEL_ZU_STUFE[band]}@4"
    text = zeile(
        {"thunder_hourly": (_hv(4, thunder_label_value(level)),)},
        [MetricSpec(symbol="TH:", enabled=True)],
    )
    assert erwartet in tokens_von(text), f"AC-7: erwartet {erwartet!r} in {text!r}"
    assert band in AMPEL_REIHENFOLGE


def test_ac7_wolken_produktpfad_sms_stufe_gleich_email_emoji_band(monkeypatch):
    """AC-7 (Produktpfad): dieselbe Stunde, dieselben Rohwerte (CT 70 %, CL 40 %).
    Die E-Mail (Einfach) zeigt das Emoji-Band von ``cloud_emoji``; die SMS (Einfach)
    die Stufe aus DEMSELBEN Band. Erwartung aus den Quellfunktionen abgeleitet."""
    from output.metric_format import cloud_emoji
    from tests.helpers.einstellung_auslieferung_orakel import roh_wert_der_metrik

    d = variante("golden_b", {"cloud_total": "einfach", "cloud_low": "einfach"})
    for m in d["display_config"]["channel_layouts"]["email"]:
        if m["metric_id"] in ("cloud_total", "cloud_low"):
            m["use_friendly_format"] = True
    mit, _ = render_trip_dict(monkeypatch, d, name="s6-ac7")
    for mid, pct in (("cloud_total", 70), ("cloud_low", 40)):
        zelle = roh_wert_der_metrik(mit, "email_plain", mid)
        assert zelle == cloud_emoji(float(pct)), (
            f"Testaufbau: E-Mail-Zelle {mid} = {zelle!r}, erwartet {cloud_emoji(float(pct))!r}"
        )
        sym = WOLKEN_SYMBOL[mid]
        assert token(mit.sendungen("sms")[0]["body"], sym) == (
            f"{sym}:{stufe_aus_email_band(pct)}@4"
        ), f"AC-7: SMS-Stufe weicht vom E-Mail-Band ab: {mit.sendungen('sms')[0]['body']!r}"


# ═══════════════════════════ AC-8: eine Quelle ══════════════════════════════


def test_ac8_konstante_ist_die_spec_menge():
    """AC-8: ``app.metric_catalog.SMS_FORMAT_MODE_METRIC_IDS`` (Muster
    ``SMS_NULLFORM_METRIC_IDS``) = {cloud_total, cloud_low, cloud_mid, cloud_high}
    (S6b: ``cape`` gestrichen). Gegen die WORTGLEICHE Spec-Menge, nicht gegen eine aus dem Produkt
    gelesene."""
    import app.metric_catalog as katalog

    konstante = getattr(katalog, "SMS_FORMAT_MODE_METRIC_IDS", None)
    assert konstante is not None, (
        "AC-8: app.metric_catalog fuehrt keine Konstante SMS_FORMAT_MODE_METRIC_IDS "
        "-- die EINE Quelle fuer SMS-Builder, Editor und Orakel fehlt."
    )
    assert frozenset(konstante) == frozenset(SPEC_SMS_FORMAT_IDS), (
        f"AC-8: {sorted(konstante)} statt {sorted(SPEC_SMS_FORMAT_IDS)}"
    )


def test_ac8_endpoint_feld_sms_format_capable_liest_die_konstante():
    """AC-8 (Drift Katalog-Konstante <-> Endpoint): ``GET /api/metrics`` traegt je
    Metrik ``sms_format_capable`` (bool) == ``id in SMS_FORMAT_MODE_METRIC_IDS``.
    Die Antwort fuehrt nur waehlbare Groessen -- ``cape`` (``selectable=False``)
    fehlt dort; wahr ist das Feld also fuer die vier Wolken-Groessen."""
    import app.metric_catalog as katalog
    from api.routers.config import get_metrics

    konstante = frozenset(getattr(katalog, "SMS_FORMAT_MODE_METRIC_IDS", ()))
    eintraege = [m for gruppe in get_metrics().values() for m in gruppe]
    assert eintraege, "Testaufbau: /api/metrics liefert nichts"
    fehlend = [m["id"] for m in eintraege if "sms_format_capable" not in m]
    assert not fehlend, (
        f"AC-8: /api/metrics fuehrt das Feld 'sms_format_capable' nicht ({len(fehlend)} "
        f"Metriken, z.B. {fehlend[:3]})"
    )
    wahr = {m["id"] for m in eintraege if m["sms_format_capable"] is True}
    assert wahr == (konstante & {m["id"] for m in eintraege}), (
        f"AC-8: sms_format_capable weicht von der Konstante ab: wahr={sorted(wahr)}, "
        f"Konstante={sorted(konstante)}"
    )
    assert wahr == set(WOLKEN), f"AC-8: erwartet die vier Wolken-Groessen, erhalten {sorted(wahr)}"
    assert all(isinstance(m["sms_format_capable"], bool) for m in eintraege)


def _text_fuer(monkeypatch, mid: str, modus: str) -> str:
    """SMS-Text (golden_b) mit NUR ``mid`` im Modus ``modus``, alle anderen Roh."""
    mit, _ = render_trip_dict(monkeypatch, variante("golden_b", {mid: modus}), name="s6-paar")
    return mit.sendungen("sms")[0]["body"]


@pytest.mark.parametrize("mid", WOLKEN)
def test_ac8_groesse_in_der_konstante_roh_und_einfach_text_verschieden(monkeypatch, mid):
    """AC-8 (Produkttest, Haelfte 1): Groesse IN der Konstante -> Roh- und
    Einfach-Text unterscheiden sich, und zwar genau am Token dieser Groesse.
    Parametrisiert ueber die WORTGLEICHE Spec-Menge."""
    roh, einfach = _text_fuer(monkeypatch, mid, "raw"), _text_fuer(monkeypatch, mid, "einfach")
    assert roh != einfach, f"AC-8: {mid} hat in der SMS keine Einfachform: {roh!r}"
    sym = WOLKEN_SYMBOL[mid]
    assert token(roh, sym) != token(einfach, sym)
    rest_roh = [t for t in tokens_von(roh) if not t.startswith(sym)]
    rest_einfach = [t for t in tokens_von(einfach) if not t.startswith(sym)]
    assert rest_roh == rest_einfach, "AC-8: ein anderes Token als das der Groesse hat sich geaendert"


def test_ac8_guard_groessen_ohne_sms_form_roh_und_einfach_byte_gleich(monkeypatch):
    """AC-8 (Produkttest, Haelfte 2, GUARD heute gruen): fuer ``thunder``,
    ``wind_direction``, ``sunshine``, ``wind``, ``gust``, ``rain_probability``,
    ``precipitation`` sind Roh- und Einfach-Text in SMS, Premium-SMS und
    Telegram-Kurzform BYTE-GLEICH -- sie haben in der SMS eine Form. Faengt eine
    stille Aufweichung (``format_mode`` fuer ALLE Metriken durchgereicht: Gewitter
    zeigte dann das Emoji-Label). Jede Groesse muss im Text vorkommen (kein
    Vakuum)."""
    modi_roh = {m: "raw" for m in SPEC_OHNE_SMS_FORM}
    modi_einfach = {m: "einfach" for m in SPEC_OHNE_SMS_FORM}
    roh = sms_texte(monkeypatch, modi_roh)
    einfach = sms_texte(monkeypatch, modi_einfach)
    for kanal in roh:
        assert roh[kanal] == einfach[kanal], (
            f"AC-8 ({kanal}): Groessen OHNE SMS-Form duerfen Roh/Einfach nicht "
            f"unterscheiden.\nroh={roh[kanal]!r}\neinfach={einfach[kanal]!r}"
        )
        for mid in SPEC_OHNE_SMS_FORM:
            assert token(roh[kanal], _TOKEN_JE_GROESSE[mid].rstrip(":")) is not None or (
                _TOKEN_JE_GROESSE[mid] in roh[kanal]
            ), f"AC-8 ({kanal}): {mid} fehlt im Text (Vakuum): {roh[kanal]!r}"


@pytest.mark.parametrize("mid", PRODUKT_ERREICHBAR)
def test_ac8_konstante_und_verhalten_stimmen_je_groesse_ueberein(monkeypatch, mid):
    """AC-8: Konstante und Verhalten sind EINE Aussage: fuer jede der elf
    produkterreichbaren Groessen gilt ``(Roh != Einfach) == (id in Konstante)`` --
    die Konstante wird zur LAUFZEIT aus dem Produkt gelesen. Faengt beide
    Richtungen: eine Groesse in der Konstante ohne gebaute Einfachform (z.B.
    ``sunshine`` aufgenommen, nichts gebaut) UND eine gebaute Einfachform ohne
    Konstanten-Eintrag."""
    import app.metric_catalog as katalog

    konstante = getattr(katalog, "SMS_FORMAT_MODE_METRIC_IDS", None)
    assert konstante is not None, "AC-8: SMS_FORMAT_MODE_METRIC_IDS fehlt im Katalog"
    roh, einfach = _text_fuer(monkeypatch, mid, "raw"), _text_fuer(monkeypatch, mid, "einfach")
    assert (roh != einfach) == (mid in konstante), (
        f"AC-8: {mid}: in der Konstante={mid in konstante}, aber "
        f"Roh{'!=' if roh != einfach else '=='}Einfach.\nroh={roh!r}\neinfach={einfach!r}"
    )


def test_ac8_orakel_liest_die_produktkonstante_keine_eigene_liste(monkeypatch):
    """AC-8: ``hat_roh_einfach_dimension(metric_id, kanal)`` prueft in ``sms``/
    ``premium_sms``/``telegram_kurzform`` genau die Groessen der PRODUKT-Konstante
    -- zur Aufrufzeit gelesen. Beweis: eine umgesetzte Konstante aendert das
    Orakel sichtbar (Mutation: eigene Test-Liste -> rot). E-Mail/Telegram rich
    bleiben bei ``has_friendly_format``."""
    import app.metric_catalog as katalog
    from tests.helpers.einstellung_auslieferung_orakel import hat_roh_einfach_dimension

    monkeypatch.setattr(katalog, "SMS_FORMAT_MODE_METRIC_IDS", frozenset({"sunshine"}),
                        raising=False)
    for kanal in ("sms", "premium_sms", "telegram_kurzform"):
        assert hat_roh_einfach_dimension("sunshine", kanal) is True
        assert hat_roh_einfach_dimension("cloud_total", kanal) is False
    for kanal in ("email_html", "telegram_rich"):
        assert hat_roh_einfach_dimension("cloud_total", kanal) is True
        assert hat_roh_einfach_dimension("wind", kanal) is False
    assert hat_roh_einfach_dimension("cloud_total") is True  # Altaufruf ohne Kanal (AC-11 S1)


def test_ac8_orakel_prueft_echte_konstante_in_den_sms_kanaelen():
    """AC-8: gegen die ECHTE Produktkonstante prueft das Orakel in den drei
    SMS-artigen Kanaelen die Wolken-Groessen (nicht ``sunshine``/``thunder``)."""
    from tests.helpers.einstellung_auslieferung_orakel import hat_roh_einfach_dimension

    for kanal in ("sms", "premium_sms", "telegram_kurzform"):
        for mid in WOLKEN:
            assert hat_roh_einfach_dimension(mid, kanal), (
                f"AC-8: {mid} muss im Kanal {kanal!r} eine Roh/Einfach-Dimension "
                f"haben (Produktkonstante fehlt oder unvollstaendig)"
            )
        for mid in ("thunder", "sunshine", "wind_direction", "wind"):
            assert not hat_roh_einfach_dimension(mid, kanal)


def test_ac8_vakuum_schutz_jede_produkterreichbare_groesse_hat_einen_geprueften_modus(monkeypatch):
    """AC-8 (Vakuum-Schutz): fuer jede Groesse der Konstante, die einen
    Kanaltext erreichen kann (die vier Wolken-Groessen), liest das Orakel in der
    Roh-Variante "raw" und in der Einfach-Variante "friendly" -- nie ``None``
    (ungeprueft). Varianten der Goldens, weil ``cloud_mid``/``cloud_high`` in
    keinem Golden-SMS-Layout stehen."""
    from tests.helpers.einstellung_auslieferung_orakel import parse_sms_artig

    roh = sms_texte(monkeypatch, standard="raw")
    einfach = sms_texte(monkeypatch, standard="einfach")
    for kanal in roh:
        _, modi_roh = parse_sms_artig(roh[kanal])
        _, modi_einfach = parse_sms_artig(einfach[kanal])
        for mid in WOLKEN:
            assert modi_roh.get(mid) == "raw", f"({kanal}) {mid} roh: {modi_roh.get(mid)!r}"
            assert modi_einfach.get(mid) == "friendly", (
                f"({kanal}) {mid} einfach: {modi_einfach.get(mid)!r} -- Text {einfach[kanal]!r}"
            )


# ═══════════════════════════ AC-9: GSM-7 und Laenge ═════════════════════════

#: Golden-SMS nach S6 (AC-1 + AC-9): ``TF`` neu (+7), Wolken als Stufe (+2) --
#: 55 -> 64 Zeichen.
GOLDEN_SMS_NACH_S6 = "E1: TF-3@6 W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT:SCT@4 SU16"


def test_ac9_golden_sms_text_und_laenge_nach_s6(monkeypatch):
    """AC-9: die Golden-SMS ``E1: W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT70@4
    SU16`` (55 Zeichen) wird durch Einfach-Stufe und ``TF`` zu
    ``E1: TF-3@6 W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT:SCT@4 SU16`` --
    64 Zeichen, in SMS, Premium-SMS und Telegram-Kurzform. HANDGESCHRIEBENE
    Soll-Werte (nicht aus dem aktuellen Output eingefroren). Die unveraenderten
    Goldens tragen ``cloud_total`` mit ``use_friendly_format: true``."""
    assert len(GOLDEN_SMS_NACH_S6) == 64
    mit_b, _ = render_golden(monkeypatch, "golden_b")
    mit_a, _ = render_golden(monkeypatch, "golden_a")
    kurz = [s for s in mit_a.sendungen("telegram") if s["parse_mode"] is None][0]["body"]
    for kanal, text in (
        ("sms", mit_b.sendungen("sms")[0]["body"]),
        ("premium_sms", mit_b.sendungen("premium_sms")[0]["body"]),
        ("telegram_kurzform", kurz),
    ):
        assert text == GOLDEN_SMS_NACH_S6, (
            f"AC-9 ({kanal}): erwartet {GOLDEN_SMS_NACH_S6!r} (64 Zeichen), "
            f"erhalten {text!r} ({len(text)} Zeichen)"
        )


@pytest.mark.parametrize("standard", ["raw", "einfach"])
def test_ac9_gsm7_und_laenge_jede_roh_einfach_kombination(monkeypatch, standard):
    """AC-9: jede Roh/Einfach-Kombination der Golden-Layouts besteht GSM-7 (kein
    Emoji, keine Umlaute im Token) und bleibt <= 160 Zeichen -- in allen drei
    SMS-artigen Kanaelen. Vakuum-Schutz: in der Einfach-Variante steht ``CT:`` im
    Text (sonst prueft der Wächter nur Zahlen)."""
    for kanal, text in sms_texte(monkeypatch, standard=standard).items():
        assert_gsm7_clean(text, f"{kanal} ({standard})")
        assert len(text) <= 160, f"AC-9 ({kanal}, {standard}): {len(text)} Zeichen"
        if standard == "einfach":
            assert "CT:" in text and "CL:" in text, (
                f"AC-9 ({kanal}): die Einfach-Variante traegt keine Stufen-Token "
                f"(Vakuum): {text!r}"
            )


# ═══════════════════════════ AC-11: Vorschau ════════════════════════════════


def test_ac11_vorschau_und_versand_tragen_dieselben_wolken_token(monkeypatch):
    """AC-11: Editor-Vorschau (``validator_render_service.build_sms_fidelity_specs``)
    und echter Versand rendern denselben Trip mit denselben Roh/Einfach-
    Einstellungen -- die Wolken-Token sind zeichengleich (CT/CM Einfach, CL/CH
    Roh). Dieselbe Prognose fuer beide Wege (Produzent ``_segments_to_normalized_
    forecast`` ueber die Fixture-Segmente).

    Erwartete Signatur (analog ``build_extended_metric_specs(format_by_metric=None)``
    aus der Spec): ``build_sms_fidelity_specs(metric_ids, format_by_metric=None)``
    mit ``{metric_id: "raw"|"symbol"}``. Waehlt /50 einen anderen Namen, ist diese
    EINE Stelle anzupassen."""
    from output.renderers.sms_trip import _segments_to_normalized_forecast
    from output.tokens.builder import build_token_line
    from output.tokens.render import render_line
    from services.validator_render_service import build_sms_fidelity_specs

    modi = {"cloud_total": "einfach", "cloud_low": "raw", "cloud_mid": "einfach",
            "cloud_high": "raw"}
    real = sms_texte(monkeypatch, modi)["sms"]
    forecast = _segments_to_normalized_forecast(
        [segment()], tz=TZ, night_weather=night_weather(),
    )
    ids = list(variante("golden_b")["display_config"]["channel_layouts"]["sms"])
    aktive = [m["metric_id"] for m in ids if m.get("enabled")]
    formate = {"cloud_total": "symbol", "cloud_low": "raw", "cloud_mid": "symbol",
              "cloud_high": "raw"}
    try:
        specs = build_sms_fidelity_specs(aktive, format_by_metric=formate)
    except TypeError as exc:
        pytest.fail(
            "AC-11: build_sms_fidelity_specs kennt die Roh/Einfach-Wahl noch nicht "
            f"(erwartet Schluesselwort 'format_by_metric'): {exc}"
        )
    vorschau = render_line(
        build_token_line(forecast, specs, report_type="evening", stage_name="E1"), 160,
    )
    for sym in ("CT", "CL", "CM", "CH"):
        assert token(vorschau, sym) == token(real, sym) and token(real, sym) is not None, (
            f"AC-11: {sym} weicht ab -- Vorschau {token(vorschau, sym)!r} vs Versand "
            f"{token(real, sym)!r}.\nVorschau: {vorschau!r}\nVersand:  {real!r}"
        )
    assert token(real, "CT").startswith("CT:"), "AC-11: Vakuum -- Versand ohne Stufe"
