"""Trip-Briefing-Mail ``full`` spricht die Sprache des Nutzers (Issue #2664).

SPEC: docs/specs/modules/i18n_p2_briefing_mail_html_2664.md (AC-1, AC-3, AC-6)

Kern-Schicht, kein Mock: echter ``TripReportFormatter.format_email`` auf dem
reichen Szenario (``tests/helpers/briefing_html_sprache_fixture.py``) und den
fuenf Golden-Szenarien; der Validator laeuft als echter Prozess gegen die
eingecheckten ``.eml``-Dateien aus ``build_mime_message``.
"""
from __future__ import annotations

import email
import importlib.util
import re
from pathlib import Path

import pytest

from tests.helpers.briefing_html_sprache_fixture import (
    ohne_spaetere_pakete, render_reich, sichtbarer_text,
)
from tests.helpers.mail_lang_fixture import FIXTURE_DIR, lade, validator_lauf

# Deutsche Signalwoerter (AC-1) plus die uebrigen Beschriftungen aus html.py.
SIGNALWOERTER = [
    "Böen", "Nacht am Ziel", "Ausblick", "Aufstieg", "Einheiten", "Spalten",
    "kein Regen", "mittel", "Etappe", "Distanz", "Abstieg", "Max Höhe", "Segmente",
    "Wetterlage", "Ankunft", "gesendet", "Metriken", "Trip-Übersicht", "Zeitplan",
    "Gewitter", "Regen", "bewölkt", "Sonne", "Vollversion", "unkritisch", "Gefahr",
    "TAGESLAGE", "MORGEN-BRIEFING", "Temperatur", "Nullgradgrenze", "Tag",
    "Wetteränderungen", "WETTER-BRIEFING", "WANDERN", "WINTERSPORT", "verlässlich",
    "Doppelring", "Hagel", "WECHSELHAFT",
]
WOCHENTAGE_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _golden_szenarien(lang: str):
    pfad = Path(__file__).resolve().parents[1] / "golden" / "email" / "regenerate.py"
    spec = importlib.util.spec_from_file_location("golden_email_regenerate_2664", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod._scenarios(lang=lang))


def _deutsche_reste(text: str) -> list[str]:
    return [w for w in SIGNALWOERTER if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)]


# --------------------------------------------------------------------------- #
# AC-1: englische Mail ohne deutsche Woerter
# --------------------------------------------------------------------------- #
def test_ac1_englische_mail_hat_keine_deutschen_beschriftungen():
    text = ohne_spaetere_pakete(sichtbarer_text(render_reich("en").email_html))
    assert _deutsche_reste(text) == [], text


def test_ac1_legende_gewitterstufe_datum_und_fusszeile_englisch():
    text = sichtbarer_text(render_reich("en").email_html)
    assert "Gust = Wind gusts" in text
    assert "Thunderstorm medium from 11:00" in text
    assert "Stage 2 / 5" in text
    assert "Night at destination (1600m)" in text
    assert "Outlook · next 3 days" in text
    assert "Open trip overview →" in text and "Briefing schedule" in text
    assert "Stage briefing · full version" in text
    kopfdatum = re.search(r"\n(\w+) · \d\d\.\d\d\.\d{4} · \d\d:\d\d", text)
    assert kopfdatum and kopfdatum.group(1) in WOCHENTAGE_EN, text[:400]
    # Namen bleiben, wie der Nutzer sie vergeben hat.
    assert "Vizzavona → Capannelle" in text and "Corsica North" in text


# --------------------------------------------------------------------------- #
# Adversary F001-F004: jede Beschriftung in der GERENDERTEN Mail geprueft
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("profil,de,en", [
    (None, "WETTER-BRIEFING", "WEATHER BRIEFING"),
    ("WINTERSPORT", "WINTERSPORT · PISTE", "WINTER SPORTS · SLOPES"),
    ("WANDERN", "WANDERN", "HIKING"),
    ("SUMMER_TREKKING", "ALPINE TOUR", "ALPINE TREK"),
])
def test_f001_profil_eyebrow_in_nutzersprache(profil, de, en):
    from app.profile import ActivityProfile

    p = getattr(ActivityProfile, profil) if profil else None
    text_en = sichtbarer_text(render_reich("en", profile=p).email_html)
    text_de = sichtbarer_text(render_reich(profile=p).email_html)
    assert text_en.startswith(en + "\n"), text_en[:80]
    assert text_de.startswith(de + "\n"), text_de[:80]


def test_f002_hagel_legende_unter_der_tabelle_englisch():
    html_en = render_reich("en").email_html
    html_de = render_reich().email_html
    assert "* Double ring on thunderstorm = hail possible" in sichtbarer_text(html_en)
    assert "* Doppelring bei Gewitter = Hagel möglich" in sichtbarer_text(html_de)
    assert "Hail: yes" in sichtbarer_text(html_en)  # Gewitter-Pille


def test_f002_hagel_im_roh_modus_als_textzusatz_englisch():
    from app.metric_catalog import build_default_display_config

    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.format_mode, mc.use_friendly_format = "raw", False
    zellen = re.findall(r'data-label="Thdr">(.*?)</td>', render_reich("en", dc=dc).email_html)
    assert "medium · Hail: yes" in zellen, zellen


def test_f003_verlaesslichkeits_hinweis_in_der_gerenderten_mail():
    text_en = sichtbarer_text(render_reich("en").email_html)
    text_de = sichtbarer_text(render_reich().email_html)
    assert "From Thursday the forecast is less reliable." in text_en
    assert "Ab Donnerstag ist die Vorhersage weniger verlässlich." in text_de


@pytest.mark.parametrize("ausblick", [True, False], ids=["im_ausblick", "ohne_ausblick"])
def test_f004_stabilitaetswort_in_der_gerenderten_mail(ausblick):
    text_en = sichtbarer_text(render_reich("en", ausblick=ausblick).email_html)
    text_de = sichtbarer_text(render_reich(ausblick=ausblick).email_html)
    assert "Weather pattern: CHANGEABLE — The pattern is in transition." in text_en
    assert "WECHSELHAFT" not in text_en
    assert "Wetterlage: WECHSELHAFT — Die Lage ist im Übergang." in text_de


def test_ac1_html_element_traegt_englische_sprache():
    assert '<html lang="en">' in render_reich("en").email_html
    assert "<html>\n" in render_reich("de").email_html


@pytest.mark.parametrize("nr", range(5))
def test_ac1_golden_szenarien_englisch_ohne_signalwoerter(nr):
    stem, report = _golden_szenarien("en")[nr]
    text = ohne_spaetere_pakete(sichtbarer_text(report.email_html))
    # Amtliche Warnung (P6 #2668) bleibt bis zu ihrem Paket deutsch.
    text = re.sub(r"Official warning\n.*?(?=DAY SUMMARY)", "", text, flags=re.S)
    text = re.sub(r"Amtliche Warnung\n.*?(?=DAY SUMMARY)", "", text, flags=re.S)
    assert _deutsche_reste(text) == [], (stem, text)


def test_ac1_deutsch_ohne_lang_gleich_lang_de():
    assert render_reich().email_html == render_reich("de").email_html


# --------------------------------------------------------------------------- #
# AC-3: Validator gegen deutsche und englische .eml
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,lang", [("briefing_full_de.eml", "de"),
                                       ("briefing_full_en.eml", "en")])
def test_ac3_validator_besteht_beide_sprachen(tmp_path, name, lang):
    eml = lade(name)
    assert email.message_from_bytes(eml)["X-GZ-Lang"] == lang
    lauf, _ = validator_lauf(tmp_path, "briefing_mail_validator", eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def _html_teil(eml: bytes) -> str:
    for teil in email.message_from_bytes(eml).walk():
        if teil.get_content_type() == "text/html":
            return teil.get_payload(decode=True).decode("utf-8")
    raise AssertionError("kein HTML-Teil")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac3_fixture_ist_echte_renderer_ausgabe(lang):
    """Der HTML-Teil der eingecheckten .eml entsteht byte-gleich aus dem
    Renderer (der Klartext-Teil traegt einen 'Generated:'-Zeitstempel)."""
    from tests.helpers.mail_lang_fixture import briefing_mail

    frisch = briefing_mail("full", lang=lang)
    eingecheckt = (FIXTURE_DIR / f"briefing_full_{lang}.eml").read_bytes()
    assert _html_teil(frisch) == _html_teil(eingecheckt)
    assert email.message_from_bytes(frisch)["X-GZ-Lang"] == lang


# --------------------------------------------------------------------------- #
# AC-6: geteilte Bausteine -- ohne lang deutsch, mit lang="en" englisch
# --------------------------------------------------------------------------- #
def test_ac6_einheiten_und_spalten_legende():
    from output.renderers.email.helpers import format_column_legend, format_units_legend

    paare = [("Temp", "°C"), ("Gust", "km/h")]
    assert format_units_legend(paare) == "Einheiten: Temp °C · Gust km/h"
    assert format_units_legend(paare, lang="en") == "Units: Temp °C · Gust km/h"
    spalten = [("Gust", "Böen")]
    assert format_column_legend(spalten) == "Spalten: Gust = Böen"
    assert format_column_legend([("Gust", "Wind gusts")], lang="en") == "Columns: Gust = Wind gusts"


def test_ac6_spalten_legende_loest_kuerzel_in_nutzersprache_auf():
    from output.renderers.email.helpers import build_column_legend

    zeilen = [{"time": "08", "gust": 40.0}]
    assert build_column_legend(zeilen) == "Spalten: Gust = Böen"
    assert build_column_legend(zeilen, lang="en") == "Columns: Gust = Wind gusts"


def test_ac6_herkunfts_fusszeile():
    from output.renderers.email.helpers import build_origin_footer

    assert build_origin_footer("compare", source="x").line1 == "Ortsvergleich"
    assert build_origin_footer("compare", source="x", lang="en").line1 == "Location comparison"
    assert build_origin_footer("official-alert", source="x", lang="en").line1 == "Official warning"
    assert build_origin_footer("deviation-alert", source="x", lang="en").line1 == "Deviation alert"


def test_ac6_gewitter_stufenwort_und_hagel():
    from app.thunder_scale import format_hail_note
    from output.renderers.email.helpers import format_trend_tokens

    stufe = {"thunder": "MED"}
    assert format_trend_tokens(stufe)["thunder_word"] == "mittel"
    assert format_trend_tokens(stufe, lang="en")["thunder_word"] == "medium"
    assert format_trend_tokens(stufe, lang="en")["thunder_plain"] == "⚡medium"
    assert format_hail_note(True) == "Hagel: ja"
    assert format_hail_note(True, lang="en") == "Hail: yes"
    assert format_hail_note(None, lang="en") is None


def test_ac6_trend_token_stufenwort_folgt_sprache():
    from output.renderers.email.helpers import format_trend_tokens
    from output.tokens.dto import HourlyValue

    stufe = {"thunder": "HIGH", "hourly_thunder": (HourlyValue(13, 2.0), HourlyValue(15, 3.0))}
    assert format_trend_tokens(stufe)["thunder_token"] == format_trend_tokens(stufe, lang="de")["thunder_token"]
    assert "mittel" in format_trend_tokens(stufe)["thunder_token"]
    assert "medium" in format_trend_tokens(stufe, lang="en")["thunder_token"]


def test_ac1_verlaesslichkeits_hinweis_mit_wochentag_in_nutzersprache():
    from datetime import datetime, timezone

    from app.models import ForecastDataPoint
    from output.renderers.email.helpers import build_confidence_hint
    from tests.helpers.briefing_html_sprache_fixture import TZ, _segment

    seg = _segment()
    for dp in seg.timeseries.data:  # nur die eine unsichere Stunde am Freitag
        dp.confidence_pct = None
    seg.timeseries.data.append(ForecastDataPoint(
        ts=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc), t2m_c=8.0, confidence_pct=40,
    ))
    jetzt = datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc)
    assert build_confidence_hint([seg], now=jetzt, tz=TZ) == (
        "Ab Freitag ist die Vorhersage weniger verlässlich.")
    assert build_confidence_hint([seg], now=jetzt, tz=TZ, lang="en") == (
        "From Friday the forecast is less reliable.")


def test_ac1_englischer_etappenname_wird_zerlegt():
    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers.briefing_html_sprache_fixture import TZ, _segment

    html = TripReportFormatter().format_email(
        [_segment()], "Corsica North", "evening", stage_name="Stage 4: Col → Refuge",
        stage_total=7, tz=TZ, lang="en",
    ).email_html
    assert "Stage 4 / 7" in html and ">Col → Refuge</h1>" in html


def test_ac6_modulkonstante_bleibt_deutsch():
    from output.renderers.email.helpers import _THUNDER_MAP

    assert _THUNDER_MAP["MED"]["word"] == "mittel"
