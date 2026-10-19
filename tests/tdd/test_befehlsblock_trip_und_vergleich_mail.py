"""Befehlsblock "Antwort-Kommandos" in Trip- UND Ortsvergleichs-Mail (#2420).

SPEC: docs/specs/modules/feat_2420_befehle_anzeigen.md AC-8, AC-10, AC-11, AC-12.

Kern-Schicht, deterministisch: echte Renderer (``TripReportFormatter.format_email``,
``render_compare_html``, ``render_comparison_text``), keine Mocks. Geprueft wird
der Text der gerenderten Mail, nicht eine Quelltextdatei.

Pendant-Regel (AC-12): ein einziger Baustein
(``output.renderers.email.command_block``: ``render_commands_plain(kind)`` /
``render_commands_html(kind)``) speist alle vier Ausgaben. Der Beweis ist
VERHALTEN: wird ``_COMMAND_SPECS`` zur Laufzeit veraendert, aendern sich alle
vier Mails gleichzeitig. ``command_block`` selbst wird dabei nicht angefasst.

Die Erwartungen sind harte Literale (15 / 4 Zeilen, Wortlisten), nicht aus dem
Produkt abgeleitet -- sonst wuerde ein fehlender Befehl aus der Erwartung
verschwinden statt den Test rot zu machen.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.helpers.adhoc_metrik_fixtures import segmente, standard_felder

TZ = ZoneInfo("Europe/Vienna")
_JETZT = datetime.now(tz=timezone.utc)
TARGET_DATE = date(2026, 7, 20)

KOPF_PLAIN = "── Antwort-Kommandos ──"
HINWEIS = "Antworte auf diese E-Mail mit einem Schlüsselwort."

#: Die 15 Zeilen der Trip-Mail in der Reihenfolge von ``_COMMAND_SPECS``
#: (harte Liste; AC-8). Nur Befehlsform, nicht die Beschreibung.
TRIP_ZEILEN = (
    "HEUTE", "MORGEN", "JETZT", "GEWITTER", "STRECKE [km]", "RUHETAG [N]",
    "STATUS", "PAUSE [2d / 12h]", "SKIP", "STOP", "WEITER", "HILFE", "KUERZEL",
    "STARTDATUM JJJJ-MM-TT", "REPORT [morning / evening]",
)
VERGLEICH_ZEILEN = ("PAUSE", "WEITER", "HILFE", "KUERZEL")
NUR_TRIP_WOERTER = (
    "STARTDATUM", "REPORT", "HEUTE", "MORGEN", "JETZT", "GEWITTER", "STRECKE",
    "RUHETAG", "STATUS", "SKIP", "STOP",
)


# ---------------------------------------------------------------------------
# Echte Mails erzeugen
# ---------------------------------------------------------------------------

def _trip_mail():
    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter

    return TripReportFormatter().format_email(
        segmente(_JETZT, standard_felder), "Befehlsblock Trip", "evening",
        display_config=build_default_display_config(),
        stage_name="Etappe 1", tz=TZ,
    )


def _loc(name: str):
    from app.models import ForecastDataPoint, ThunderLevel
    from app.user import LocationResult, SavedLocation

    punkte = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 20, h, 0, tzinfo=timezone.utc),
            t2m_c=10.0 + h, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.2,
            pop_pct=30, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
            visibility_m=20000,
        )
        for h in (2, 8, 14, 20)
    ]
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.0, lon=11.0,
                               elevation_m=500, timezone="Europe/Vienna"),
        score=50, hourly_data=punkte, outlook_hourly_data=[],
    )


def _compare_result():
    from app.user import ComparisonResult

    return ComparisonResult(
        locations=[_loc("Innsbruck"), _loc("Frejus")], time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )


def _compare_html() -> str:
    from output.renderers.email.compare_html import render_compare_html

    return render_compare_html(
        _compare_result(), preset_name="Mein Vergleich", preset_schedule="daily",
    )


def _compare_text() -> str:
    from output.renderers.comparison import render_comparison_text

    return render_comparison_text(_compare_result())


# ---------------------------------------------------------------------------
# Block aus der Mail herausschneiden
# ---------------------------------------------------------------------------

def _entmarkup(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _html_block(html: str) -> str:
    """Entmarkuptes "Antwort-Kommandos"-Segment: ab dem Eyebrow bis zum
    Hinweis "Antworte auf diese E-Mail ..." (einschliesslich)."""
    start = html.find("Antwort-Kommandos")
    assert start != -1, "HTML-Mail ohne Block 'Antwort-Kommandos'"
    ende = html.find(HINWEIS, start)
    assert ende != -1, "Block 'Antwort-Kommandos' ohne Hinweis 'Antworte auf diese E-Mail ...'"
    return _entmarkup(html[start:ende + len(HINWEIS)])


def _plain_block(text: str) -> list[str]:
    """Befehlszeilen unter ``── Antwort-Kommandos ──`` bis zur ersten Leerzeile
    bzw. Trennzeile ``---``."""
    zeilen = text.splitlines()
    start = next((i for i, z in enumerate(zeilen) if KOPF_PLAIN in z), None)
    assert start is not None, f"Klartext-Mail ohne Block {KOPF_PLAIN!r}"
    block: list[str] = []
    for zeile in zeilen[start + 1:]:
        if not zeile.strip() or zeile.strip() == "---":
            break
        block.append(zeile)
    return block


def _formen(zeilen: list[str]) -> list[str]:
    """Befehlsform je Plain-Zeile ("  HEUTE   – Wetter ..." -> "HEUTE")."""
    return [z.split(" – ")[0].strip() for z in zeilen]


def _woerter(text: str) -> set[str]:
    return set(re.findall(r"\b[A-ZÄÖÜ]{3,}\b", text))


# ---------------------------------------------------------------------------
# AC-8: Trip-Mail, 15 Zeilen, HTML und Klartext
# ---------------------------------------------------------------------------

def test_ac8_trip_klartext_fuehrt_fuenfzehn_befehle_in_quellreihenfolge():
    block = _plain_block(_trip_mail().email_plain)
    assert _formen(block) == list(TRIP_ZEILEN), _formen(block)
    stop = next(z for z in block if z.strip().startswith("STOP"))
    assert "ABBRUCH" in stop, stop
    assert not [z for z in _formen(block) if z.split(" ")[0] in ("ABBRUCH", "COLUMNS")]


def test_ac8_trip_html_fuehrt_fuenfzehn_befehle_in_quellreihenfolge():
    text = _html_block(_trip_mail().email_html)
    positionen = []
    for form in TRIP_ZEILEN:
        pos = text.find(form)
        assert pos != -1, f"HTML-Block ohne {form!r}: {text!r}"
        positionen.append(pos)
    assert positionen == sorted(positionen), "HTML-Block weicht von der Reihenfolge in _COMMAND_SPECS ab"
    assert "ABBRUCH" in text
    assert "ABBRUCH [" not in text and " COLUMNS" not in text


def test_ac8_trip_html_und_klartext_tragen_dieselbe_befehlsmenge():
    mail = _trip_mail()
    assert _woerter(" ".join(_plain_block(mail.email_plain))) == _woerter(_html_block(mail.email_html))


# ---------------------------------------------------------------------------
# AC-10: Ortsvergleich HTML
# ---------------------------------------------------------------------------

def test_ac10_vergleich_html_hat_genau_die_vier_befehle():
    text = _html_block(_compare_html())
    woerter = _woerter(text)
    for form in VERGLEICH_ZEILEN:
        assert form in text, f"Vergleichs-Block ohne {form!r}: {text!r}"
    for verboten in NUR_TRIP_WOERTER:
        assert verboten not in woerter, f"Vergleichs-Block fuehrt Trip-Befehl {verboten!r}: {text!r}"
    # PAUSE ohne Dauer (Vergleiche pausieren unbefristet, AC-29 #2417).
    assert "2d" not in text and "12h" not in text, text
    assert HINWEIS in text


def test_ac10_vergleich_html_block_steht_zwischen_abo_hinweis_und_app_fusszeile():
    html = _compare_html()
    abo = html.find("Dieses Abo")
    block = html.find("Antwort-Kommandos")
    fuss = html.find("Vergleich in App")
    assert -1 not in (abo, block, fuss), (abo, block, fuss)
    assert abo < block < fuss, f"Reihenfolge Abo={abo} Block={block} App-Fuss={fuss}"


def test_ac10_vergleichs_block_entspricht_der_hilfe_antwort():
    """Gegenprobe: dieselbe Zeilenmenge wie ``_show_help_for_kind('vergleich')``."""
    from services.trip_command_processor import TripCommandProcessor, command_rows

    hilfe = TripCommandProcessor()._show_help_for_kind("vergleich").confirmation_body
    aus_hilfe = {
        tuple(t.strip() for t in z.split(" – ", 1))
        for z in hilfe.splitlines() if " – " in z
    }
    assert aus_hilfe == set(command_rows("vergleich"))
    assert [b for b, _ in command_rows("vergleich")] == list(VERGLEICH_ZEILEN)
    text = _html_block(_compare_html())
    for befehl, beschreibung in aus_hilfe:
        assert befehl in text and beschreibung in text, (befehl, beschreibung)


# ---------------------------------------------------------------------------
# AC-11: Ortsvergleich Klartext
# ---------------------------------------------------------------------------

def test_ac11_vergleich_klartext_hat_denselben_block_vor_der_fusszeile():
    text = _compare_text()
    block = _plain_block(text)
    assert _formen(block) == list(VERGLEICH_ZEILEN), _formen(block)
    assert text.find(KOPF_PLAIN) < text.rfind("---"), "Block steht nicht VOR der Fusszeile '---'"
    assert text.rstrip().endswith("Gregor Zwanzig")


def test_ac11_klartext_und_html_des_vergleichs_tragen_dieselben_zeilen():
    from services.trip_command_processor import command_rows

    plain = _plain_block(_compare_text())
    html = _html_block(_compare_html())
    for befehl, beschreibung in command_rows("vergleich"):
        assert any(z.strip().startswith(befehl) and z.rstrip().endswith(beschreibung) for z in plain), (
            befehl, plain,
        )
        assert befehl in html and beschreibung in html


# ---------------------------------------------------------------------------
# AC-12: EIN Baustein -- Laufzeit-Mutation von _COMMAND_SPECS
# ---------------------------------------------------------------------------

def test_ac12_baustein_liefert_trip_und_vergleichs_block():
    from output.renderers.email import command_block

    plain_trip = command_block.render_commands_plain("route")
    plain_vgl = command_block.render_commands_plain("vergleich")
    assert KOPF_PLAIN in plain_trip and KOPF_PLAIN in plain_vgl
    assert len([z for z in plain_trip.splitlines() if z.startswith("  ")]) == 15
    assert len([z for z in plain_vgl.splitlines() if z.startswith("  ")]) == 4
    html_trip = _entmarkup(command_block.render_commands_html("route"))
    html_vgl = _entmarkup(command_block.render_commands_html("vergleich"))
    assert "STARTDATUM JJJJ-MM-TT" in html_trip and "REPORT [morning / evening]" in html_trip
    assert "STARTDATUM" not in html_vgl and "REPORT" not in html_vgl


def test_ac12_aenderung_an_command_specs_aendert_trip_und_vergleich_gleichzeitig(monkeypatch):
    """GIVEN ``_COMMAND_SPECS`` wird zur Laufzeit veraendert (ein Befehl fuer
    BEIDE Mail-Arten kommt hinzu, WEITER faellt weg, SKIP faellt weg) WHEN alle
    vier Mails (Trip HTML/Klartext, Vergleich HTML/Klartext) neu entstehen THEN
    zeigen ALLE vier den neuen Befehl und keine das entfernte WEITER."""
    from services import trip_command_processor as tcp

    probe = tcp._Befehl(
        "zzzprobe", "zzzprobe", "", "Probebefehl Zweitausendvierhundertzwanzig",
        "probe", tcp._BEIDE_KINDS,
    )
    mutiert = tuple(
        s for s in tcp._COMMAND_SPECS if s.wort not in ("weiter", "skip")
    ) + (probe,)
    monkeypatch.setattr(tcp, "_COMMAND_SPECS", mutiert)

    mail = _trip_mail()
    ausgaben = {
        "trip-klartext": " ".join(_plain_block(mail.email_plain)),
        "trip-html": _html_block(mail.email_html),
        "vergleich-klartext": " ".join(_plain_block(_compare_text())),
        "vergleich-html": _html_block(_compare_html()),
    }
    for name, text in ausgaben.items():
        assert "ZZZPROBE" in text, f"{name}: neuer Befehl fehlt -> eigene Kopie der Liste: {text!r}"
        assert "Probebefehl Zweitausendvierhundertzwanzig" in text, name
        assert "WEITER" not in _woerter(text), f"{name}: entfernter Befehl WEITER steht noch drin"
    for name in ("trip-klartext", "trip-html"):
        assert "SKIP" not in _woerter(ausgaben[name]), f"{name}: entferntes SKIP steht noch drin"


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac12_baustein_folgt_der_quelle_je_kind(monkeypatch, kind):
    from output.renderers.email import command_block
    from services import trip_command_processor as tcp

    ohne_hilfe = tuple(s for s in tcp._COMMAND_SPECS if s.wort != "hilfe")
    monkeypatch.setattr(tcp, "_COMMAND_SPECS", ohne_hilfe)

    assert "HILFE" not in _woerter(command_block.render_commands_plain(kind))
    assert "HILFE" not in _woerter(_entmarkup(command_block.render_commands_html(kind)))
