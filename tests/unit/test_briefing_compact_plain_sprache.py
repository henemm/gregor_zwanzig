"""Trip-Briefing ``compact`` und Klartext sprechen die Sprache des Nutzers (Issue #2665).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md (AC-1, AC-3, AC-6)

Kern-Schicht, kein Mock: echter ``TripReportFormatter.format_email`` auf dem
reichen Szenario (``tests/helpers/briefing_compact_plain_fixture.py``) und den
fuenf Golden-Szenarien; der Validator laeuft als echter Prozess gegen die
eingecheckten ``.eml``-Dateien aus ``build_mime_message``. Geprueft wird die
GERENDERTE Mail, nicht einzelne Bausteine -- faellt irgendwo ein
``lang=lang`` weg, steht dort wieder ein deutsches Wort.
"""
from __future__ import annotations

import email
import importlib.util
import re
from pathlib import Path

import pytest

from tests.helpers.briefing_compact_plain_fixture import ohne_spaetere_pakete, render_briefing
from tests.helpers.mail_lang_fixture import lade, validator_lauf

# Deutsche Signalwoerter (AC-1) -- jedes steht in mindestens einer deutschen
# Fassung des reichen Szenarios (Gegenprobe unten), damit die Liste nicht leer laeuft.
SIGNALWOERTER = [
    "Naechste Etappen", "Nächste Etappen", "Wetterlage", "Metriken-Ueberblick",
    "Metriken-Überblick", "Nacht am Ziel", "Ankunft", "Antwort-Kommandos", "Einheiten",
    "Spalten", "nicht abrufbar", "FEHLGESCHLAGEN", "ZURUeCKGEHALTEN", "ZURÜCKGEHALTEN",
    "Stille Stunden", "Tageslimit", "Versand fehlgeschlagen", "Ersatzquelle",
    "Ersatzmodell", "groebere", "gröbere", "Regen", "Regenradar", "Gewitter", "mittel",
    "bewoelkt", "bewölkt", "Boeen", "Böen", "WETTER-BRIEFING", "Vollversion", "Kompakt",
    "Etappen-Briefing", "verlaesslich", "verlässlich", "WECHSELHAFT", "Hagel", "Sonne",
    "gef.", "weitere", "Tage", "Vorhersage", "Wetter am Ziel", "WETTERDATEN",
    "Anbieter-Fehler", "Gewitter-Vorschau", "Ortsangabe", "Radar reicht", "letzter",
    "Temperatur", "Minimum", "Wetteränderung", "Amtliche", "unter deiner Schwelle",
    "Wiederholung", "Morgen", "leichter", "mäßiger", "möglich", "ab", "bis",
    "kein", "leicht", "hoch", "niedrig", "Blitzdichte",
]
WOCHENTAGE_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
GOLDEN_STEMS = ["gr20-summer-evening", "gr20-spring-morning", "gr221-mallorca-evening",
                "arlberg-winter-morning", "corsica-vigilance"]


def _deutsche_reste(text: str) -> list[str]:
    return [w for w in SIGNALWOERTER if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)]


def _golden(lang: str, email_format: str):
    pfad = Path(__file__).resolve().parents[1] / "golden" / "email" / "regenerate.py"
    spec = importlib.util.spec_from_file_location("golden_email_regenerate_2665", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod._scenarios(lang=lang, email_format=email_format))


VARIANTEN = [("compact", "ausblick"), ("compact", "zustand"),
             ("full", "ausblick"), ("full", "zustand")]


# --------------------------------------------------------------------------- #
# AC-1: englische Fassungen ohne deutsche Woerter
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("email_format,variante", VARIANTEN)
def test_ac1_englische_fassung_ohne_deutsche_woerter(email_format, variante):
    text = render_briefing("en", email_format=email_format, variante=variante).email_plain
    assert _deutsche_reste(ohne_spaetere_pakete(text)) == [], text


def test_ac1_signalwortliste_trifft_die_deutsche_fassung():
    """Gegenprobe: jedes Signalwort kommt in einer deutschen Fassung vor."""
    deutsch = "\n".join(
        render_briefing("de", email_format=f, variante=v).email_plain for f, v in VARIANTEN
    ) + "\n" + render_briefing("de", email_format="full").email_html
    fehlend = [w for w in SIGNALWOERTER if w not in _deutsche_reste(deutsch)]
    assert fehlend == []


@pytest.mark.parametrize("variante", ["ausblick", "zustand"])
def test_ac1_kompakt_bleibt_ascii_und_kuerzel_bleiben(variante):
    text = render_briefing("en", email_format="compact", variante=variante).email_plain
    assert text.isascii(), [z for z in text.split("\n") if not z.isascii()]
    if variante == "ausblick":
        # Spaltenkoepfe (col_label) unveraendert -- nie uebersetzt (ADR-0042).
        assert re.search(r"Temp .* Gust .* Rain .* Thdr ", text), text


def test_ac1_kompakt_englisch_inhalt_ausblick():
    text = render_briefing("en", email_format="compact").email_plain
    for erwartet in (
        "WEATHER BRIEFING", "Corsica North - Evening Report", "== Metrics overview ==",
        "Weather pattern: CHANGEABLE - The pattern is in transition.",
        "Next stages", "Thdr Tmedium@13 (high @15)",
        "!! Official warnings are currently unavailable - please check yourself.",
        "FAILED - something went wrong", "HELD BACK - as you set it up",
        "Delivery failed", "Quiet hours", "... and 2 more",
        "Thunderstorm data from a backup source (coarser resolution)",
        "Some weather values from backup model: DWD Europa (Wind gusts)",
        "Stage briefing - compact - openmeteo",
    ):
        assert erwartet in text, (erwartet, text)


def test_ac1_kompakt_gewitterzelle_und_acc_englisch():
    """Reines "light" ohne T-Praefix, Aggregat-Rueckfall in Nutzersprache."""
    text = render_briefing("en", email_format="compact").email_plain
    zeilen = {z.split()[0]: z for z in text.split("\n") if "Thdr" in z}
    assert "Thdr light@12 " in zeilen["So"], zeilen
    assert "Thdr Thigh " in zeilen["Mo"] and "Thdr light " in zeilen["Di"], zeilen


def test_ac1_klartext_ausblick_englisch_gewitter_hagel_herkunft_acc():
    text = render_briefing("en", email_format="full").email_plain
    zeilen = {z.split()[0]: z for z in text.split("\n") if "Thdr" in z and "ACC" in z}
    assert "Thdr light@12 · Lightning density · Hail: yes" in zeilen["So"], zeilen
    assert "ACC low" in zeilen["So"] and "ACC very low" in zeilen["Mo"], zeilen
    assert "Thdr ⚡high " in zeilen["Mo"] and "Thdr light " in zeilen["Di"], zeilen


def test_ac1_vollmail_html_hinweise_englisch():
    html = render_briefing("en", email_format="full").email_html
    for erwartet in ("Official warnings currently unavailable",
                     "FAILED — something went wrong", "HELD BACK — as you set it up",
                     "Rain radar · E-Mail, Premium-SMS · Delivery failed", "… and 2 more",
                     "light @12 · Lightning density · Hail: yes"):
        assert erwartet in html, erwartet
    for deutsch in ("Amtliche Warnungen aktuell", "FEHLGESCHLAGEN", "Versand fehlgeschlagen",
                    "Blitzdichte", "Hagel: ja"):
        assert deutsch not in html, deutsch
    zustand = render_briefing("en", email_format="full", variante="zustand").email_html
    assert "Next stage is too far ahead (max. 1 day)." in zustand
    assert "Nächste Etappe liegt" not in zustand


def test_ac1_kompakt_unbekannte_stabilitaet_englisch():
    """Nur die Kompaktform kennt einen Rueckfall fuer unbekannte Labels."""
    en = render_briefing("en", email_format="compact", stabilitaet="UNBEKANNT").email_plain
    de = render_briefing("de", email_format="compact", stabilitaet="UNBEKANNT").email_plain
    assert "Weather pattern: UNBEKANNT" in en and "Wetterlage: UNBEKANNT" not in en
    assert "Wetterlage: UNBEKANNT" in de


def test_ac1_klartext_wetteraenderungen_ueberschrift():
    from app.models import ChangeSeverity, WeatherChange

    change = WeatherChange(metric="temp_max_c", old_value=18.0, new_value=25.0, delta=7.0,
                           threshold=5.0, severity=ChangeSeverity.MODERATE,
                           direction="increase", segment_id="1")
    en = render_briefing("en", email_format="full", changes=[change]).email_plain
    de = render_briefing("de", email_format="full", changes=[change]).email_plain
    assert "━━ Weather changes ━━" in en and "Wetteränderungen" not in en
    assert "━━ Wetteränderungen ━━" in de


def test_ac1_klartext_tabelle_englisch_signale_breite_und_leer():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from app.metric_catalog import build_default_display_config
    from app.models import ForecastDataPoint, ThunderLevel
    from output.renderers.email.helpers import dp_to_row
    from output.renderers.email.plain import _render_text_table

    dc = build_default_display_config()
    dp = ForecastDataPoint(ts=datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc), t2m_c=9.0,
                           thunder_level=ThunderLevel.LOW)
    row = dp_to_row(dp, dc, tz=ZoneInfo("UTC"))
    row["_thunder_signals"] = ["blitzdichte"]
    tabelle = _render_text_table([row], friendly_keys=set(), lang="en")
    kopf, trenner, zeile = tabelle.split("\n")
    zelle = "light · Lightning density"
    assert zelle in zeile and "Blitzdichte" not in tabelle, tabelle
    # Spaltenbreite aus dem ENGLISCHEN Text: Trennstrich exakt Zelle + 1.
    spalte = kopf.split().index("Thdr")
    assert len(trenner.split()[spalte]) == len(zelle) + 1, tabelle
    assert _render_text_table([], friendly_keys=set(), lang="en") == "  (no data)"
    assert _render_text_table([], friendly_keys=set()) == "  (keine Daten)"


def test_ac1_kompakt_fester_ausblick_zweig_englisch():
    """Altbestand ohne Ausblick-Spalten (``outlook_metrics=None``)."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.compact import render_compact
    from tests.helpers.briefing_compact_plain_fixture import trend_reich
    from tests.helpers.briefing_html_sprache_fixture import TZ, _segment

    text = render_compact(
        segments=[_segment()], dc=build_default_display_config(), multi_day_trend=trend_reich(),
        outlook_metrics=None, stability_result=None, tz=TZ, report_type="evening",
        trip_name="Corsica North", stage_name=None, stage_stats=None, lang="en",
    )
    zeilen = {z.split()[0]: z for z in text.split("\n") if z[:2] in ("Fr", "So", "Mo", "Di")}
    assert zeilen["Fr"].endswith("Tmedium@13 (high @15)"), zeilen
    assert zeilen["So"].endswith(" light@12") and zeilen["Mo"].endswith(" Thigh"), zeilen
    assert zeilen["Di"].endswith(" light"), zeilen


def test_ac1_kompakt_englisch_inhalt_zustand():
    text = render_briefing("en", email_format="compact", variante="zustand").email_plain
    assert "Next stages\nNext stage is too far ahead (max. 1 day)." in text, text


def test_ac1_klartext_englisch_inhalt():
    text = render_briefing("en", email_format="full").email_plain
    for erwartet in (
        "WEATHER BRIEFING", "━━ Metrics overview ━━",
        "Weather pattern: CHANGEABLE — The pattern is in transition.",
        "Night at destination (1600m)", "Arrival ", "→ next morning 06:00",
        "Next stages", "⚠️ Official warnings are currently unavailable — please check yourself.",
        "⚠️ Heavy rain from about ", "(in ~30 min), last rain around ",
        "── Reply commands ──", "Units: ", "Columns: ", "Stage briefing · full version",
        "Some weather values from backup model: DWD Europa (Wind gusts)",
    ):
        assert erwartet in text, (erwartet, text)
    # Tagesueberblick (Zusammenfassung) und Stundentabelle: Gewitterstufe englisch.
    assert "Thunderstorm possible" in text or "⚡ possible" in text, text


def test_ac1_klartext_zustand_englisch():
    text = render_briefing("en", email_format="full", variante="zustand").email_plain
    for erwartet in (
        "━━ Next stages ━━\nNext stage is too far ahead (max. 1 day).",
        "━━ Thunderstorm preview ━━", "━━ Segment 2: WEATHER DATA UNAVAILABLE ━━",
        "Provider error after 5 attempts", "Weather at destination: ",
    ):
        assert erwartet in text, (erwartet, text)


@pytest.mark.parametrize("email_format", ["compact", "full"])
def test_ac1_golden_szenarien_englisch(email_format):
    for stem, report in _golden("en", email_format).items():
        text = ohne_spaetere_pakete(report.email_plain)
        assert _deutsche_reste(text) == [], (stem, text)
        if email_format == "compact":
            assert report.email_plain.isascii(), stem


# --------------------------------------------------------------------------- #
# AC-6: Antwort-Kommandos, beide Arten, beide Sprachen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac6_befehlsblock_englisch(kind):
    from output.renderers.email.command_block import render_commands_html, render_commands_plain
    from services.trip_command_processor import command_rows

    plain = render_commands_plain(kind, lang="en")
    assert plain.split("\n")[0] == "── Reply commands ──"
    # Befehlsteil aus command_rows(kind, lang) -- seit P10 (#2673) englisch.
    assert plain.split("\n")[1:] == [
        f"  {c:<20} – {b}" for c, b in command_rows(kind, lang="en")]
    assert plain.split("\n")[1:] != render_commands_plain(kind).split("\n")[1:]
    assert len(plain.split("\n")) == len(command_rows(kind)) + 1
    html = render_commands_html(kind, lang="en")
    assert "Reply commands</span>" in html
    assert "Reply to this email with a keyword.</div>" in html
    assert "Antwort" not in html and "Schlüsselwort" not in html


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac6_befehlsblock_deutsch_wortgleich(kind):
    from output.renderers.email.command_block import render_commands_html, render_commands_plain

    assert render_commands_plain(kind, lang="de") == render_commands_plain(kind)
    assert render_commands_plain(kind).split("\n")[0] == "── Antwort-Kommandos ──"
    html = render_commands_html(kind)
    assert render_commands_html(kind, lang="de") == html
    assert "Antwort-Kommandos</span>" in html
    assert "Antworte auf diese E-Mail mit einem Schlüsselwort.</div>" in html


def test_ac6_englische_vollmail_traegt_englischen_befehlsblock():
    report = render_briefing("en", email_format="full")
    assert "Reply to this email with a keyword." in report.email_html
    assert "── Reply commands ──" in report.email_plain


# --------------------------------------------------------------------------- #
# AC-3: Validator gegen echte .eml beider Sprachen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", [
    "briefing_compact_de.eml",
    "briefing_compact_en.eml",
])
def test_ac3_validator_besteht_kompakt_mail(tmp_path, name):
    lauf, _ = validator_lauf(tmp_path, "briefing_mail_validator", lade(name))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_ac3_englische_kompakt_mail_traegt_kopf_und_englischen_inhalt():
    msg = email.message_from_bytes(lade("briefing_compact_en.eml"))
    assert msg["X-GZ-Lang"] == "en"
    assert msg["X-GZ-Format"] == "compact"
    text = msg.get_payload(decode=True).decode("ascii")
    assert "== Metrics overview ==" in text and "Next stages" in text
    assert _deutsche_reste(text) == [], text


def test_ac3_englische_eml_stammt_aus_dem_heutigen_renderer():
    """Die eingecheckte englische Fixture ist der heutige Renderer-Stand
    (bis auf die Uhrzeit der Fusszeile)."""
    from tests.helpers.mail_lang_fixture import briefing_mail

    def _ohne_uhr(b: bytes) -> str:
        return re.sub(r"Generated: [^\n]+", "Generated: X", b.decode("ascii"))

    assert _ohne_uhr(briefing_mail("compact", lang="en")) == _ohne_uhr(lade("briefing_compact_en.eml"))
