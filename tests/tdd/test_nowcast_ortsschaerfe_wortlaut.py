"""TDD RED — Issue #2051 S3: Wortlaut der Guete-Zeile — "unscharf", niemals
"extrapoliert".

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-8.

Fachlicher Kern (E2/E3): die GeoSphere-INCA-Quelle extrapoliert das GESAMTE
abgerufene Fenster -- es gibt keinen gemessenen Teil, von dem sich ein
"ab hier extrapoliert" sinnvoll abgrenzen liesse. Das Wort "extrapoliert"
waere deshalb sachlich falsch: es suggeriert eine Grenze in den Daten, die
es nicht gibt. Der PO-Vorschlag "davon ab 14:40 extrapoliert" wurde deshalb
zu "Ortsangabe ab HH:MM unscharf" praezisiert.

RED heute: keine Renderer-Stelle kennt die Guete-Suffixe -- das Wort
"unscharf" fehlt ersatzlos.

Mock-frei: echte `NowcastResult`/`OnsetEvent`-Objekte durch die echten
Projektions- und Renderfunktionen. Die Uhr steht per `freeze_time`.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_subject, render_telegram
from services.radar_service import NowcastResult

_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Projektion und Renderer werden RELATIV ZU
    DIESER Testdatei aufgeloest."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (project_module, render_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


@freeze_time(_FROZEN_UTC)
def test_ac8_guete_zeile_sagt_unscharf_niemals_extrapoliert():
    """AC-8 GIVEN einen Fall mit gesetzter Guete-Zeile (Beginn 75 Minuten in
    der Zukunft, jenseits der 60-Minuten-Grenze -- Aufbau wie AC-4)
    WHEN der gerenderte Text auf sein Vokabular geprueft wird
    THEN enthaelt er das Wort "unscharf", NIEMALS das Wort "extrapoliert" --
    letzteres suggeriert faelschlich einen gemessenen Teil, den die
    INCA-Quelle nicht liefert (E2/E3).

    RED heute: die Guete-Zeile fehlt komplett -- weder "unscharf" noch
    "extrapoliert" stehen im Text, die Positivkontrolle ("unscharf" IST da)
    schlaegt fehl."""
    nc = NowcastResult(
        onset_minutes=75, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False, event_end_minutes=30,
    )
    msg = to_multi_location_onset_alert_message(
        [("Sillian", nc)], tz=_TZ, stand_at="17:55",
    )
    _html, plain = render_email(msg)
    betreff = render_subject(msg)
    telegram = render_telegram(msg)

    for name, text in (("email", plain), ("betreff", betreff), ("telegram", telegram)):
        assert "unscharf" in text, (
            f"RED: das Wort 'unscharf' fehlt in {name}: {text!r}"
        )
        assert "extrapoliert" not in text, (
            f"Das Wort 'extrapoliert' darf NIEMALS im Text stehen (E2/E3), "
            f"gefunden in {name}: {text!r}"
        )
