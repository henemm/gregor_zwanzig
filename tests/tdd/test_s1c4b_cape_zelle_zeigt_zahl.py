"""Issue #2792 S1c-4b Fix-Loop (/60-validate) — CAPE-Zelle zeigt die Zahl.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md, AC-6 und §5
„CAPE (P1): keine eigene Farbe (``_ampel_dot_severity("cape")`` entfällt)".

Defekt (in /60 gemessen): seit CAPE keine Ampel-Schwellen mehr hat, liefert
``severity_for("cape", …)`` ``None``; der Einfach-HTML-Zweig in ``fmt_val``
fragte trotzdem den Ampel-Punkt ab und gab für JEDEN CAPE-Wert „–" aus —
sieht aus wie „keine Daten". Soll: die nackte Zahl, ohne Punkt, ohne
Ampel-Hintergrund, in jeder Vorlage.

Geprüft wird dort, wo die Zelle entsteht und wirkt:
  1. Alarm-Mail (``alert.render.render_email`` → ``_hours_html`` →
     ``row_parts`` → ``format_cell`` → ``fmt_val``), CAPE-Ereignis mit
     CAPE in den E-Mail-Indikatoren (Einfach-Modus).
  2. Stundentabelle der Trip-Mail (``html._render_html_table``) mit
     CAPE-Spalte und CAPE in ``indicator_keys`` (Einfach-Modus).

Kern-Schicht: echte Domänenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.ampel import AMPEL_TEMPLATES, resolve_ampel

VORLAGEN = sorted(AMPEL_TEMPLATES)


def _ampel(vorlage: str) -> dict:
    return resolve_ampel({"display_config": {"preset_name": vorlage}})


def _hat_punkt(markup: str) -> bool:
    return "border-radius:50%" in markup


# ---------------------------------------------------------------------------
# 1. Alarm-Mail mit CAPE-Ereignis
# ---------------------------------------------------------------------------

def _cape_alarm(ampel: dict, *, modes: dict | None):
    from output.renderers.alert.model import AlertEvent, AlertHourRow, AlertMessage
    event = AlertEvent(
        metric_id="cape", value_from=300.0, value_to=1600.0, threshold=500.0,
        cmp="über", occurred_at="14:00", km_from=0.0, km_to=4.0,
        hours=(AlertHourRow("14:00", None, 1600.0),),
    )
    kwargs = {}
    if modes is not None:
        kwargs["format_modes"] = {"email": modes}
    return AlertMessage(
        trip_short="Cape", stand_at="06:00", events=(event,),
        indicator_keys={"email": frozenset({"cape"})}, ampel=ampel, **kwargs,
    )


def _zeile_mit_zeit(html: str, zeit: str):
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if tds and tds[0].get_text(strip=True) == zeit:
            return tds
    return None


@pytest.mark.parametrize("vorlage", VORLAGEN)
@pytest.mark.parametrize("modes", [None, {"cape": "simplified"}],
                         ids=["indikator", "einfach"])
def test_alarm_mail_cape_zelle_zeigt_zahl_ohne_punkt(vorlage, modes):
    from output.renderers.alert.render import render_email
    html, _plain = render_email(_cape_alarm(_ampel(vorlage), modes=modes))
    tds = _zeile_mit_zeit(html, "14:00")
    assert tds is not None, "Stundenzeile 14:00 fehlt in der Alarm-Mail"
    zellen = [str(td) for td in tds[1:]]
    texte = [td.get_text(strip=True) for td in tds[1:]]
    assert any("1600" in t for t in texte), (
        f"CAPE-Zelle zeigt nicht die Zahl 1600 (Vorlage {vorlage}): {texte!r}"
    )
    assert not any(t == "–" for t in texte), (
        f"CAPE-Zelle zeigt „–“ statt der Zahl (Vorlage {vorlage}): {texte!r}"
    )
    assert not any(_hat_punkt(z) for z in zellen), (
        f"CAPE-Zelle trägt einen Ampel-Punkt (Vorlage {vorlage}): {zellen!r}"
    )


# ---------------------------------------------------------------------------
# 2. Stundentabelle der Trip-Mail mit CAPE-Spalte (Einfach-Modus)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage", VORLAGEN)
def test_trip_stundentabelle_cape_zelle_zeigt_zahl_ohne_farbe(vorlage):
    from output.renderers.email.html import _render_html_table
    rows = [{"time": "14", "temp": 22.0, "cape": 1600.0}]
    html = _render_html_table(
        rows, friendly_keys={"cape"}, indicator_keys={"cape"},
        ampel=_ampel(vorlage),
    )
    soup = BeautifulSoup(html, "html.parser")
    zelle = soup.find("td", attrs={"data-label": "CAPE"})
    assert zelle is not None, f"CAPE-Zelle fehlt: {html!r}"
    text = zelle.get_text(strip=True)
    assert "1600" in text, f"CAPE-Zelle zeigt {text!r} statt 1600 (Vorlage {vorlage})"
    assert not _hat_punkt(str(zelle)), (
        f"CAPE-Zelle trägt einen Ampel-Punkt (Vorlage {vorlage}): {zelle}"
    )
    style = zelle.get("style") or ""
    assert "background" not in style, (
        f"CAPE-Zelle trägt einen Ampel-Hintergrund (Vorlage {vorlage}): {style!r}"
    )


def test_cape_ist_keine_ampel_faehige_indikator_metrik():
    """``build_html_indicator_keys`` nimmt CAPE nicht mehr auf — sonst
    behandelt die Trip-Tabelle die CAPE-Spalte als Ampel-Zelle."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.helpers import build_html_indicator_keys
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = True
        mc.use_friendly_format = True
    assert "cape" not in build_html_indicator_keys(dc)
