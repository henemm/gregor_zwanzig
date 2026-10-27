"""TDD RED -- Mengenerhalt ueber die GERENDERTE Ausgabe (#1405 Scheibe S3).

SPEC: docs/specs/modules/feat_1405_s3_mengenerhalt.md (AC-1 .. AC-28)

Leitfrage (CLAUDE.md "Mutations-Gegenprobe"): Ist die Zusicherung dort geprueft,
wo sie WIRKT -- im Text, den der Empfaenger bekommt -- und nicht nur dort, wo der
Code steht? Jeder Test liest deshalb den GERENDERTEN Text (Mail-HTML/-Klartext,
Telegram, SMS, Premium-SMS-Sink) bzw. fuer die Trip-Tabelle die Entscheidung, die
die Spalten der Mail bestimmt. Kein Mock-Theater; Fakes nur an den Aussengrenzen
(Senken ``mail_sink``/``sms_sink``/``telegram_sink``/``premium_sms_sink``).

Festgelegte (noch nicht existierende) Schnittstelle der Spec, gegen die RED
geschrieben wird:
- ``compare_metric_ids.resolve_enabled_metrics_report(active)`` ->
  ``(resolved | None, unresolved: tuple[str, ...])``
- ``CompareRenderOptions.unresolved_by_channel: dict[str, int]``
- ``channel_layout.selection_gap_notice(count, *, scope)``  (scope ``"ort"`` /
  ``"vergleich"``)
- Schluesselwortparameter ``unresolved_count: int = 0`` an
  ``render_compare_sms`` (Spec Punkt 3) -- aus Gruenden der Gleichfoermigkeit
  derselbe Name an ``render_compare_telegram``, ``render_comparison_text``,
  ``render_compare_email`` und ``render_compare_html``.

RED heute (Fund): AC-1, -2, -4, -6, -10, -12, -13, -14(Teil), -15, -18, -19, -24, -25.
Heute GRUEN (Bestandsschutz, Rueckdreh-Gegenprobe in der Mutation AC-27):
AC-3, -5, -7, -8(ohne Unmappbares), -9, -11, -16, -17, -20 .. -23.
"""
from __future__ import annotations

import re

from tests.tdd.test_compare_render_options_resolver import _make_comparison_result

# Pfadregel #1409: alle Pruefling-Importe laufen ueber den Paketpfad ``src`` des
# Worktrees (conftest/pyproject), nie ueber einen festen Hauptrepo-Pfad.

#: Eine Renderer-Kennung ohne Zeilendefinition (Katalog kennt sie nicht).
OHNE_ZEILE = "zzz_ohne_zeile"
#: Gueltige Groesse, die in der Test-Fixture an KEINEM Ort einen Wert hat
#: (``_make_comparison_result`` fuellt snow_depth_cm nicht).
OHNE_WERT = "snow_depth_cm"

ORTE = ["Alpha", "Beta", "Gamma"]


def _result():
    return _make_comparison_result(ORTE)


# ---------------------------------------------------------------------------
# Auswertungs-Helfer (Nutzersicht: was steht im Text)
# ---------------------------------------------------------------------------

_HINWEIS_VERGLEICH = re.compile(r"\+(\d+) gewählte Wettergrößen ohne Wert in diesem Vergleich")
_HINWEIS_ORT = re.compile(r"\+(\d+) gewählte Wettergrößen ohne Wert an diesem Ort")


def _zahlen(muster: re.Pattern, text: str) -> list[int]:
    return [int(m) for m in muster.findall(text)]


def _sms_orte(sms: str) -> list[str]:
    """Ortsteile der SMS: ``Vergleich 08.07.: A ...; B ...; C ...``."""
    nach_kopf = sms.split(": ", 1)[1]
    return [t.strip() for t in nach_kopf.split("; ")]


def _fragezaehler(teil: str) -> int | None:
    m = re.search(r"(?:^|\s)\?(\d+)(?=\s|$)", teil)
    return int(m.group(1)) if m else None


def _telegram_ortsbloecke(text: str) -> dict[str, list[str]]:
    bloecke: dict[str, list[str]] = {}
    aktuell = None
    for zeile in text.splitlines():
        if zeile and not zeile.startswith(" ") and zeile in ORTE:
            aktuell = zeile
            bloecke[aktuell] = []
        elif aktuell and zeile.startswith("   "):
            bloecke[aktuell].append(zeile.strip())
    return bloecke


# ===========================================================================
# A. Ortsvergleich -- E-Mail (HTML und Klartext)
# ===========================================================================


def test_ac1_html_hinweis_fuer_groesse_ohne_zeilendefinition():
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(_result(), enabled_metrics=["temp_max", OHNE_ZEILE, "wind_max"])

    assert _zahlen(_HINWEIS_VERGLEICH, html) == [1], (
        "Unter der Uebersichtstabelle muss stehen, wie viele gewaehlte Groessen "
        f"nicht gezeigt werden konnten (+1). Gefunden: {_zahlen(_HINWEIS_VERGLEICH, html)}"
    )
    # Die uebrigen Groessen behalten ihre Zeile in der gewaehlten Reihenfolge.
    assert html.index("Temperatur") < html.index("Wind")


def test_ac2_html_unmappbarer_schluessel_zaehlt_in_der_hinweiszahl():
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(
        _result(), enabled_metrics=["temp_max", "wind_max"], unresolved_count=1,
    )
    assert _zahlen(_HINWEIS_VERGLEICH, html) == [1]

    html2 = render_compare_html(
        _result(), enabled_metrics=["temp_max", OHNE_ZEILE], unresolved_count=2,
    )
    assert _zahlen(_HINWEIS_VERGLEICH, html2) == [3], (
        "Zahl = nicht darstellbare Groessen INSGESAMT (ohne Zeile + unmappbar)"
    )


def test_ac3_html_ohne_luecke_kein_hinweis_und_zeilen_unveraendert():
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(_result(), enabled_metrics=["temp_max", "wind_max"])
    assert "ohne Wert in diesem Vergleich" not in html
    assert "ohne Wert" not in html.replace("ohne Wert an", "")
    assert html.index("Temperatur") < html.index("Wind")


def test_ac4_klartext_hat_denselben_hinweis_mit_derselben_zahl():
    from output.renderers.comparison import render_comparison_text

    text = render_comparison_text(
        _result(), enabled_metrics=["temp_max", OHNE_ZEILE], unresolved_count=1,
    )
    assert _zahlen(_HINWEIS_VERGLEICH, text) == [2]


def test_ac4_mail_beide_fassungen_tragen_dieselbe_zahl():
    from output.renderers.comparison import render_compare_email

    html, text = render_compare_email(
        _result(), enabled_metrics=["temp_max", OHNE_ZEILE], unresolved_count=1,
    )
    assert _zahlen(_HINWEIS_VERGLEICH, html) == _zahlen(_HINWEIS_VERGLEICH, text) == [2]


def test_ac5_klartext_ohne_luecke_kein_hinweis():
    from output.renderers.comparison import render_comparison_text

    text = render_comparison_text(_result(), enabled_metrics=["temp_max", "wind_max"])
    assert "ohne Wert" not in text


# ===========================================================================
# B. Ortsvergleich -- Telegram
# ===========================================================================


def test_ac6_telegram_zaehlt_wertlose_groesse_und_unmappbaren_schluessel():
    from output.renderers.comparison import render_compare_telegram

    text = render_compare_telegram(
        _result(), enabled_metrics=["temp_max", "wind_max", OHNE_WERT],
        preset_name="P", unresolved_count=1,
    )
    bloecke = _telegram_ortsbloecke(text)
    assert set(bloecke) == set(ORTE)
    for ort, zeilen in bloecke.items():
        zahlen = _zahlen(_HINWEIS_ORT, " ".join(zeilen))
        assert zahlen == [2], (
            f"{ort}: N muss die Groesse ohne Wert UND den unmappbaren Schluessel "
            f"enthalten (2), gefunden {zahlen}"
        )


def test_ac7_telegram_ohne_luecke_kein_ohne_wert_hinweis():
    from output.renderers.comparison import render_compare_telegram

    text = render_compare_telegram(
        _result(), enabled_metrics=["temp_max", "wind_max"], preset_name="P",
    )
    assert "ohne Wert" not in text


def test_ac8_telegram_mengenerhalt_je_ort():
    from output.renderers.comparison import render_compare_telegram

    gewaehlt = ["temp_max", "wind_max", "cloud_avg", OHNE_WERT]
    text = render_compare_telegram(
        _result(), enabled_metrics=gewaehlt, preset_name="P", unresolved_count=1,
    )
    for ort, zeilen in _telegram_ortsbloecke(text).items():
        zellen = [z for z in zeilen if " · " in z or re.match(r"^\S.*\d", z)][0].split(" · ")
        ohne_wert = sum(_zahlen(_HINWEIS_ORT, " ".join(zeilen)))
        platz = sum(int(n) for n in re.findall(r"\+(\d+) weitere", " ".join(zeilen)))
        assert len(zellen) + platz + ohne_wert == len(gewaehlt) + 1, (
            f"{ort}: sichtbar {len(zellen)} + Platzmangel {platz} + ohne Wert "
            f"{ohne_wert} != gewaehlt {len(gewaehlt)} + unmappbar 1"
        )


def test_ac9_kurzform_telegram_traegt_den_sms_text_mit_zaehler(tmp_path, monkeypatch):
    """Kurzform = ``_telegram_text = _sms_text`` -- im Versand gemessen (siehe AC-13)."""
    text, kanaele = _versand_mit_unmappbarem(tmp_path, monkeypatch, stil="kurzform")
    assert kanaele["telegram"] == kanaele["sms"], "Kurzform muss den SMS-Text senden"
    assert _fragezaehler(_sms_orte(kanaele["telegram"])[0]) == 1


# ===========================================================================
# C. Ortsvergleich -- SMS und Premium-SMS
# ===========================================================================


def test_ac10_sms_zaehler_nur_an_orten_mit_luecke():
    from output.renderers.comparison import render_compare_sms

    sms = render_compare_sms(_result(), enabled_metrics=["temp_max", "wind_max", OHNE_WERT])
    teile = _sms_orte(sms)
    assert len(teile) == 3
    for teil in teile:
        assert _fragezaehler(teil) == 1, f"Zaehler ?1 fehlt im Ortsteil: {teil!r}"
        assert teil.rstrip().endswith("?1") or "?1 !" in teil, teil


def test_ac11_sms_normalfall_ist_zeichen_fuer_zeichen_unveraendert():
    from output.renderers.comparison import render_compare_sms

    sms = render_compare_sms(_result(), enabled_metrics=["temp_max", "wind_max"])
    assert sms == (
        "Vergleich 08.07.: Alpha D 20C W 10 km/h; Beta D 21C W 10 km/h; "
        "Gamma D 22C W 10 km/h"
    ), "Normalfall darf sich nicht veraendern (kein ?, kein zusaetzliches Leerzeichen)"
    assert "?" not in sms


def test_ac12_sms_sichtbar_plus_verdraengt_plus_fehlend_ergibt_gewaehlt():
    from output.renderers.comparison import render_compare_sms

    gewaehlt = ["temp_max", "wind_max", "cloud_avg", "sunny_hours", OHNE_WERT]
    sms = render_compare_sms(_result(), enabled_metrics=gewaehlt)
    for teil in _sms_orte(sms):
        fehlend = _fragezaehler(teil) or 0
        verdraengt = sum(int(n) for n in re.findall(r"\+(\d+)(?!\s*Orte)(?:\s|$)", teil))
        sichtbar = len(re.findall(r"\b[A-Z]{1,3}\s+\d", teil))
        assert fehlend >= 1, f"?N fehlt: {teil!r}"
        assert sichtbar + verdraengt + fehlend == len(gewaehlt), (
            f"{teil!r}: sichtbar {sichtbar} + verdraengt {verdraengt} + fehlend "
            f"{fehlend} != gewaehlt {len(gewaehlt)}"
        )


def test_ac13_premium_sms_bekommt_denselben_text_wie_sms_inklusive_zaehler(tmp_path, monkeypatch):
    _text, kanaele = _versand_mit_unmappbarem(tmp_path, monkeypatch)
    assert kanaele["premium_sms"] == kanaele["sms"], "kein Kanal darf eine aeltere Fassung bekommen"
    for teil in _sms_orte(kanaele["premium_sms"]):
        assert _fragezaehler(teil) == 1, f"Premium-SMS ohne ?1: {teil!r}"


def test_ac14_sms_laenge_gsm7_und_zaehler_wird_nie_verdraengt():
    from output.renderers.channel_layout import CHANNEL_LIMITS
    from output.renderers.comparison import render_compare_sms

    viele = ["temp_max", "wind_max", "cloud_avg", "sunny_hours", "precip_sum",
             "pop_max", "uv_max", "temp_min", "gust_max", OHNE_WERT]
    sms = render_compare_sms(_result(), enabled_metrics=viele)
    assert len(sms) <= CHANNEL_LIMITS["sms"]["max_chars"] == 153
    assert all(ord(c) < 128 for c in sms), f"nicht-GSM-7-sicher: {sms!r}"
    for teil in _sms_orte(sms):
        if teil.endswith("n/a") or re.search(r"\+\d+ Orte", teil):
            continue
        assert _fragezaehler(teil) is not None, f"Zaehler verdraengt: {teil!r}"


def test_ac14_zaehler_ist_fester_teil_des_budgets():
    """Adversary F001: der Zaehler ``?N`` muss in der Kuerzungsschleife
    mitgerechnet sein -- sonst ragt der Ortsteil um `` ?N`` ueber sein Budget,
    und die SMS verliert Ort bzw. Zaehler an die Notkuerzung. Die Ortsnamen-
    Laenge wird durchgefahren, damit jede Restluecke im Budget einmal knapp
    ist (ein fester Name traefe die kritische Laenge nur zufaellig)."""
    from output.renderers.comparison import render_compare_sms

    gewaehlt = ["temp_max", "wind_max", "cloud_avg", "sunny_hours", "precip_sum",
                "pop_max", "uv_max", OHNE_WERT]
    for laenge in range(20, 130):
        name = "N" * laenge
        sms = render_compare_sms(_make_comparison_result([name]), enabled_metrics=gewaehlt)
        assert len(sms) <= 153, sms
        teile = _sms_orte(sms)
        assert len(teile) == 1 and teile[0].startswith(name + " "), (
            f"Ort fiel der Notkuerzung zum Opfer (Name {laenge}): {sms!r}"
        )
        teil = teile[0]
        assert _fragezaehler(teil) == 1, f"Zaehler fehlt (Name {laenge}): {teil!r}"
        verdraengt = sum(int(n) for n in re.findall(r"(?:^|\s)\+(\d+)(?=\s|$)", teil))
        sichtbar = len(re.findall(r"\s[A-Z]{1,3}\s+\d", teil))
        assert sichtbar + verdraengt + 1 == len(gewaehlt), teil


def test_ac12_reihenfolge_platzmangel_vor_fehlend_exakt():
    """Adversary F005: Wire-Vertrag sms_format.md §5b -- ``+N`` (verdraengt)
    steht VOR ``?N`` (fehlend), Zeichen fuer Zeichen."""
    from output.renderers.comparison import render_compare_sms

    name = "N" * 90
    gewaehlt = ["temp_max", "wind_max", "cloud_avg", "sunny_hours", "precip_sum",
                "pop_max", "uv_max", OHNE_WERT]
    sms = render_compare_sms(_make_comparison_result([name]), enabled_metrics=gewaehlt)
    assert sms == f"Vergleich 08.07.: {name} D 20C W 10 km/h CT 30% SU 5.0h +3 ?1", sms


def _sms_ueber_echten_eingang(display_config: dict):
    from output.renderers.comparison import render_compare_sms
    from services.report_config_resolver import resolve_compare_render_options

    opts = resolve_compare_render_options({"id": "p-kanal", "display_config": display_config})
    sms = render_compare_sms(
        _result(), enabled_metrics=opts.enabled_metrics_by_channel["sms"],
        unresolved_count=opts.unresolved_by_channel.get("sms", 0),
    )
    return opts, sms


def test_ac15_kanal_und_grundauswahl_mit_demselben_unmappbaren_zaehlen_einmal():
    """Adversary F004a: derselbe unmappbare Schluessel in Grundauswahl UND
    Kanal-Auswahl ist EINE Luecke, nicht zwei."""
    opts, sms = _sms_ueber_echten_eingang({
        "active_metrics": ["temp_max_c", "wind_max_kmh", "gibt_es_nicht_xyz"],
        "channel_active_metrics": {"sms": ["temp_max_c", "gibt_es_nicht_xyz"]},
    })
    assert opts.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}
    assert [_fragezaehler(t) for t in _sms_orte(sms)] == [1, 1, 1], sms


def test_ac15_nur_kanal_eigener_unmappbarer_zaehlt_nur_in_diesem_kanal():
    """Adversary F004b: ein unmappbarer Schluessel NUR in der SMS-Auswahl
    zaehlt in der SMS (``?1``), nicht in Mail/Telegram."""
    opts, sms = _sms_ueber_echten_eingang({
        "active_metrics": ["temp_max_c", "wind_max_kmh"],
        "channel_active_metrics": {"sms": ["temp_max_c", "gibt_es_nicht_abc"]},
    })
    assert opts.unresolved_by_channel == {"email": 0, "telegram": 0, "sms": 1}
    assert [_fragezaehler(t) for t in _sms_orte(sms)] == [1, 1, 1], sms


def test_ac15_unmappbarer_schluessel_erhoeht_den_zaehler_an_jedem_ort():
    from output.renderers.comparison import render_compare_sms

    sms = render_compare_sms(
        _result(), enabled_metrics=["temp_max", "wind_max"], unresolved_count=1,
    )
    zaehler = [_fragezaehler(t) for t in _sms_orte(sms)]
    assert zaehler == [1, 1, 1], zaehler


# ===========================================================================
# D. Abgrenzungen
# ===========================================================================


def test_ac16_nicht_waehlbare_groesse_taucht_in_keinem_kanal_auf(caplog):
    from output.renderers.compare_metric_ids import resolve_enabled_metrics_report

    resolved, unresolved = resolve_enabled_metrics_report(["temp_max_c", "confidence_pct"])
    assert resolved == ["temp_max"]
    assert unresolved == (), "confidence_pct (selectable=False) darf nie gezaehlt werden (#710)"


def test_ac16_report_trennt_unmappbar_von_nicht_waehlbar():
    from output.renderers.compare_metric_ids import resolve_enabled_metrics_report

    resolved, unresolved = resolve_enabled_metrics_report(
        ["temp_max_c", "confidence_pct", "gibt_es_nicht_xyz"],
    )
    assert resolved == ["temp_max"]
    assert unresolved == ("gibt_es_nicht_xyz",)


def test_ac16_namensform_einer_waehlbaren_groesse_bleibt_meldepflichtig():
    """``t2m_c`` traegt die nicht waehlbare ``temperature_cold`` UND die waehlbare
    ``temperature`` -- ohne Compare-Zuordnung ist es eine echte Luecke (Art a),
    keine still verschluckte nicht-waehlbare Groesse (Art b)."""
    from services.report_config_resolver import resolve_compare_render_options

    opts = resolve_compare_render_options(
        {"id": "p-t2m", "display_config": {"active_metrics": ["temp_max_c", "t2m_c"]}},
    )
    assert opts.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}


def test_ac17_kanal_abgewaehlte_groesse_ist_keine_luecke():
    from services.report_config_resolver import resolve_compare_render_options

    preset = {"id": "p17", "display_config": {
        "active_metrics": ["temp_max_c", "wind_max_kmh"],
        "channel_active_metrics": {"sms": ["temp_max_c"]},
    }}
    opts = resolve_compare_render_options(preset)
    assert opts.enabled_metrics_by_channel["sms"] == ["temp_max"]
    assert opts.unresolved_by_channel.get("sms", 0) == 0
    assert opts.unresolved_by_channel.get("email", 0) == 0


def test_ac18_vorschau_und_versand_tragen_denselben_zaehler(tmp_path, monkeypatch):
    """Beide Aufrufseiten lesen ``opts.unresolved_by_channel`` -- die Zahl muss je
    Kanal aus der EINEN Aufloesung stammen (Versand wird gemessen, Vorschau ueber
    den Quelltext-freien Beleg: dieselbe Optionsinstanz liefert die Zahlen)."""
    from services.report_config_resolver import resolve_compare_render_options

    opts = resolve_compare_render_options(_preset_mit_unmappbarem())
    assert opts.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}
    _text, kanaele = _versand_mit_unmappbarem(tmp_path, monkeypatch)
    assert _fragezaehler(_sms_orte(kanaele["sms"])[0]) == opts.unresolved_by_channel["sms"]


def test_ac3_warn_in_der_auswahl_ist_keine_luecke():
    """Adversary F003: die Warn-Zeile ist immer sichtbar -- ``warn`` in der
    Auswahl darf weder im HTML noch im Klartext als fehlend gezaehlt werden."""
    from output.renderers.comparison import render_compare_email

    html, text = render_compare_email(_result(), enabled_metrics=["warn", "temp_max"])
    assert "ohne Wert in diesem Vergleich" not in html
    assert "ohne Wert in diesem Vergleich" not in text


def _vorschau(uid: str, preset_id: str) -> tuple[dict, str]:
    from services.compare_preview_service import ComparePreviewService
    from tests.tdd._compare_kette_fixtures import TARGET_DATE

    svc = ComparePreviewService()
    kanaele = svc.render_all_channels(preset_id, user_id=uid, target_date=TARGET_DATE)
    ctx = svc._prepare(preset_id, user_id=uid, target_date=TARGET_DATE)
    _html, plain = svc._render_email(ctx)
    return kanaele, plain


def test_ac18_wirkort_mail_und_telegram_versand_gleich_vorschau(tmp_path, monkeypatch):
    """Adversary F002: unmappbarer Schluessel in ``active_metrics`` -> der
    ZUGESTELLTE Mail-Text (HTML + Klartext, am Transport-Aufzeichner) und das
    zugestellte Telegram (rich) tragen die Zahl; die Vorschau zeigt dieselbe."""
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    mit = aufzeichner_installieren(monkeypatch)
    uid, preset_id = _versand_mit_unmappbarem(tmp_path, monkeypatch, ohne_senken=True)
    mail = mit.sendungen("email")[0]
    telegram = mit.sendungen("telegram")[0]["body"]
    assert _zahlen(_HINWEIS_VERGLEICH, mail["body"]) == [1], "HTML-Versand ohne Hinweis"
    assert _zahlen(_HINWEIS_VERGLEICH, mail["plain_text_body"]) == [1], "Klartext-Versand ohne Hinweis"
    assert _zahlen(_HINWEIS_ORT, telegram) == [1, 1], f"Telegram-Versand: {telegram!r}"

    vorschau, plain = _vorschau(uid, preset_id)
    assert _zahlen(_HINWEIS_VERGLEICH, vorschau["email_html"]) == [1], "HTML-Vorschau luegt"
    assert _zahlen(_HINWEIS_VERGLEICH, plain) == [1], "Klartext-Vorschau luegt"
    assert _zahlen(_HINWEIS_ORT, vorschau["telegram"]) == [1, 1], "Telegram-Vorschau luegt"
    assert [_fragezaehler(t) for t in _sms_orte(vorschau["sms"])] == [1, 1], "SMS-Vorschau luegt"


def test_ac19_ein_baustein_ein_wortlaut():
    from output.renderers.channel_layout import selection_gap_notice

    assert selection_gap_notice(0, scope="ort") == ""
    assert selection_gap_notice(2, scope="ort") == "… +2 gewählte Wettergrößen ohne Wert an diesem Ort"
    assert selection_gap_notice(3, scope="vergleich") == (
        "… +3 gewählte Wettergrößen ohne Wert in diesem Vergleich"
    )


# ===========================================================================
# E. Trip -- Charakterisierung
# ===========================================================================


def _trip_segment_ohne(feld_punkt: str | None = None, feld_agg: str | None = None):
    from tests.helpers import trip_outlook_selection as h

    seg = h._segment_weather()
    if feld_punkt:
        for p in seg.timeseries.data:
            setattr(p, feld_punkt, None)
    if feld_agg:
        setattr(seg.aggregated, feld_agg, None)
    return seg


def test_ac20_trip_mail_behaelt_die_spalte_und_zeigt_strich_statt_zu_verschwinden():
    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers import trip_outlook_selection as h

    seg = _trip_segment_ohne("wind10m_kmh")
    with h.utc_process_tz():
        report = TripReportFormatter().format_email(
            segments=[seg], trip_name="T", report_type="evening",
            display_config=h.display_config(), tz=h.TZ,
            multi_day_trend=h.outlook_rows(), stage_name="E3",
        )
    kopf = re.search(r"Time\s+Temp.*", report.email_plain).group(0)
    assert "Wind" in kopf, "Spalte Wind darf nicht verschwinden"
    zeile = [z for z in report.email_plain.splitlines() if re.match(r"\s+1[0-6]\s", z)][0]
    assert "–" in zeile, f"fehlender Wert muss als Strich erscheinen: {zeile!r}"
    assert "Wind" in report.email_html


def test_ac21_trip_telegram_zeigt_strich_fuer_groesse_ohne_wert():
    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers import trip_outlook_selection as h

    seg = _trip_segment_ohne("wind10m_kmh", "wind_max_kmh")
    with h.utc_process_tz():
        report = TripReportFormatter().format_email(
            segments=[seg], trip_name="T", report_type="evening",
            display_config=h.display_config(), tz=h.TZ,
            multi_day_trend=h.outlook_rows(), stage_name="E3",
        )
    uebersicht = report.telegram_bubbles[1]
    assert re.search(r"^W\s+–", uebersicht, re.M), (
        f"Zeile 'W' darf nicht verschwinden, sondern '–' tragen: {uebersicht!r}"
    )


def test_ac22_trip_sms_token_fehlt_nicht_sondern_traegt_null_oder_luecken_form():
    from output.renderers.sms_trip import SMSTripFormatter

    seg = _trip_segment_ohne("wind10m_kmh", "wind_max_kmh")
    sms = SMSTripFormatter().format_sms([seg], stage_name="E1")
    token = [t for t in sms.split() if t.startswith("W") and not t.startswith(("WD", "WC"))]
    assert token and token[0] in ("W-", "W?"), (
        f"Token W muss in Null- ('-') oder Lueckenform ('?') vorhanden sein: {sms!r}"
    )


def _dc_mit_horizonten(**horizonte):
    from tests.helpers import trip_outlook_selection as h

    dc = h.display_config(enabled_ids={"temperature", "wind"})
    for mc in dc.metrics:
        if mc.metric_id in horizonte:
            mc.horizons = horizonte[mc.metric_id]
    return dc


def test_ac23_abgewaehlter_horizont_ist_nutzerentscheidung_nicht_verlust():
    from app.metric_catalog import get_metric
    from output.renderers.email.html import _allowed_col_keys_for_horizon

    dc = _dc_mit_horizonten(
        wind={"today": True, "tomorrow": False, "day_after": True},
        temperature={"today": True, "tomorrow": True, "day_after": True},
    )
    wind = get_metric("wind").col_key
    temp = get_metric("temperature").col_key
    assert wind in _allowed_col_keys_for_horizon(dc, "today")
    morgen = _allowed_col_keys_for_horizon(dc, "tomorrow")
    assert wind not in morgen and temp in morgen


def test_ac24_alle_abgewaehlt_heisst_keine_wertespalten_nicht_alle():
    from output.renderers.email.html import _allowed_col_keys_for_horizon

    dc = _dc_mit_horizonten(
        wind={"today": False, "tomorrow": True, "day_after": True},
        temperature={"today": False, "tomorrow": True, "day_after": True},
    )
    erlaubt = _allowed_col_keys_for_horizon(dc, "today")
    assert erlaubt == set(), (
        "Alle aktivierten Groessen fuer 'today' abgewaehlt => KEINE Wertespalten "
        f"(leere Menge), nicht None='alle'. Ist: {erlaubt!r}"
    )


def test_ac24_trip_ohne_gespeicherte_metrik_konfiguration_zeigt_standardspalten():
    from output.renderers.email.html import _allowed_col_keys_for_horizon
    from tests.helpers import trip_outlook_selection as h

    dc = h.display_config(leere_grundauswahl=True)
    assert _allowed_col_keys_for_horizon(dc, "today") is None
    assert _allowed_col_keys_for_horizon(dc, None) is None


# ===========================================================================
# F. Mandantentrennung, Anti-Gaming, Doku
# ===========================================================================


def _preset_mit_unmappbarem() -> dict:
    return {"id": "p-luecke", "display_config": {
        "active_metrics": ["temp_max_c", "wind_max_kmh", "gibt_es_nicht_xyz"],
    }}


def test_ac25_zwei_aufloesungen_tragen_keinen_zustand_ueber():
    from services.report_config_resolver import resolve_compare_render_options

    erster = resolve_compare_render_options(_preset_mit_unmappbarem())
    zweiter = resolve_compare_render_options(
        {"id": "p-sauber", "display_config": {"active_metrics": ["temp_max_c"]}},
    )
    assert erster.unresolved_by_channel == {"email": 1, "telegram": 1, "sms": 1}
    assert zweiter.unresolved_by_channel.get("email", 0) == 0
    assert zweiter.unresolved_by_channel.get("sms", 0) == 0
    assert zweiter.unresolved_by_channel is not erster.unresolved_by_channel


def test_ac26_wire_vertrag_beschreibt_den_zaehler():  # doc-compliance-test
    from pathlib import Path

    doku = (Path(__file__).resolve().parents[1] / "docs/reference/sms_format.md").read_text()
    assert "| 2.37 |" in doku and "?N" in doku  # v2.36 ist durch #1737 belegt


# ---------------------------------------------------------------------------
# Versand-Messung (Wirkort): Preset mit unmappbarer Kennung durch die ECHTE
# Kette ``send_one_compare_preset`` -> NotificationService -> Senken.
# ---------------------------------------------------------------------------


def _premium_erreichbar_machen(uid: str) -> None:
    """Profil wie im Premium-SMS-Versandtest (#2275): bestaetigte Nummer und
    frisch gelernte Rueckadresse -- sonst sperrt der Kanal und Premium-SMS
    erreicht den Sink gar nicht."""
    import json
    from datetime import datetime, timezone

    from app.loader import get_data_dir

    pfad = get_data_dir(uid) / "user.json"
    profil = json.loads(pfad.read_text())
    nummer = profil.get("sms_to") or "+490000000000"
    profil.update({
        "sms_to": nummer, "sms_verified_number": nummer,
        "premium_sms_reply_to": "4915799912345",
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    })
    pfad.write_text(json.dumps(profil))


def _versand_mit_unmappbarem(tmp_path, monkeypatch, *, stil: str = "rich",
                             ohne_senken: bool = False):
    """``ohne_senken=True``: Versand laeuft bis zum (vorher installierten)
    Transport-Aufzeichner -- Rueckgabe ``(uid, preset_id)`` fuer die Vorschau."""
    from tests.tdd._compare_kette_fixtures import (
        TARGET_DATE, briefing_senden, engine_naht, fixture_dict, nutzer_anlegen,
        orte_anlegen, preset_ablegen, settings_fuer, transport_einrichten,
    )

    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    uid = nutzer_anlegen()
    _premium_erreichbar_machen(uid)
    roh = fixture_dict("basis")
    roh["id"] = "vgl-s3-luecke"
    roh["send_telegram"] = True
    roh["send_sms"] = True
    roh["send_premium_sms"] = True
    roh["alert_channels"] = ["email", "premium_sms"]  # sonst gilt das Flag als Alarm-Absicht
    roh["display_config"] = {
        **roh.get("display_config", {}),
        "active_metrics": [
            {"metric_id": "temperature", "aggregation": "max"},
            {"metric_id": "wind", "aggregation": "max"},
            {"metric_id": "gibt_es_nicht_xyz", "aggregation": "max"},
        ],
        "telegram_style": stil,
    }
    orte_anlegen(uid)
    preset_ablegen(uid, roh)

    if ohne_senken:
        briefing_senden(uid, roh["id"], settings_fuer(uid), target_date=TARGET_DATE)
        return uid, roh["id"]

    kanaele: dict[str, str] = {}
    briefing_senden(
        uid, roh["id"], settings_fuer(uid), target_date=TARGET_DATE,
        mail_sink=lambda **kw: kanaele.__setitem__("email", kw.get("body", "")),
        sms_sink=lambda t: kanaele.__setitem__("sms", t),
        telegram_sink=lambda t: kanaele.__setitem__("telegram", t),
        premium_sms_sink=lambda t: kanaele.__setitem__("premium_sms", t),
    )
    return kanaele.get("email", ""), kanaele
