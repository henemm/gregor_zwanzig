"""Nutzer- und Fremdtexte landen in Mail-HTML nur als Text (#2961, AC-3).

Trip-Name, Etappenname, Hinweistexte und Provider-Fehlertexte koennen
beliebige Zeichen enthalten. Im HTML-Teil muessen sie als Text erscheinen
(escaped, genau einmal), im Klartext-Teil unveraendert.
Echte Renderer-Aufrufe, keine Doubles.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from tests.tdd.test_issue_811_mode_matrix import _make_dc, _make_dp, _make_seg_data

NAME = '<img src=x onerror=1>'
ESC = "&lt;img src=x onerror=1&gt;"


def _briefing(trip_name: str, stage_name: str, *, trip_url: str | None = None):
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dp = _make_dp()
    dc = _make_dc(raw=False)
    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    tl = TokenLine(trip_name=trip_name, report_type="evening", stage_name=stage_name)
    return render_email(
        tl, segments=[_make_seg_data(dp=dp)], seg_tables=[[row]], display_config=dc,
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(), email_format="full",
        stage_name=stage_name, trip_url=trip_url,
    )


@pytest.mark.parametrize("stage_name", [NAME, f"Etappe 2: {NAME}"])
def test_briefing_html_zeigt_trip_und_etappennamen_als_text(stage_name):
    html, plain = _briefing(f"Tour {NAME}", stage_name)
    assert "<img" not in html
    assert ESC in html
    assert "&amp;lt;" not in html, "doppelt escaped"
    assert NAME in plain, "Klartext-Teil bleibt unveraendert"


def test_briefing_html_link_attribut_bleibt_attribut():
    html, _ = _briefing("Tour", "Etappe 1: A", trip_url='https://x.example/trips/a"onmouseover="1')
    assert '"onmouseover="' not in html
    assert "&quot;onmouseover=&quot;" in html


def test_servicefehler_mail_escaped_tripname_und_fehlertext():
    from services.notification_service import build_service_error_email_html

    html = build_service_error_email_html(
        trip_name=f"Tour {NAME}", report_type="morning",
        error_lines=f"  - Abschnitt 1: Provider sagt {NAME} & mehr",
    )
    assert "<img" not in html
    assert html.count(ESC) == 2
    assert "&amp; mehr" in html


def test_hinweis_im_briefing_html_wird_escaped():
    from services.notification_service import NotificationService

    out = NotificationService._inject_html_hint("<html><body><p>x</p></body></html>",
                                                f"Nachlieferung fuer {NAME}")
    assert "<img" not in out
    assert ESC in out
    assert out.startswith("<html><body><p>Nachlieferung")


@pytest.mark.parametrize("fall", ["abweichung_wind", "abweichung_mehrfach", "regen_einzel",
                                  "regen_buendel", "nachtrag", "regen_spaet"])
def test_alarm_mail_zeigt_namen_als_text(fall):
    import dataclasses

    from output.renderers.alert.render import render_email as render_alarm
    from tests.helpers import alarm_fixture

    msg = alarm_fixture.nachricht(fall, "de")
    felder = ("location_label", "segment_label", "source_label")
    events = tuple(
        dataclasses.replace(e, **{k: NAME for k in felder if hasattr(e, k)}) for e in msg.events
    )
    msg = dataclasses.replace(msg, trip_short=f"T {NAME}", location_label=NAME, events=events)
    html, plain = render_alarm(msg)
    assert "<img" not in html
    assert NAME in plain


def test_ortsvergleich_mail_zeigt_orts_und_abo_namen_als_text():
    import dataclasses

    from app.profile import ActivityProfile
    from output.renderers.email.compare_html import render_compare_html
    from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN
    from tests.tdd.test_issue_1105_compare_snow_metric import _make_snow_result

    result = _make_snow_result()
    for lr in result.locations:
        lr.location = dataclasses.replace(lr.location, name=f"{lr.location.name} {NAME}")
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, preset=PRESET_ALLGEMEIN,
                               preset_name=f"Abo {NAME}", warnings=[f"Hinweis {NAME}"])
    assert "<img" not in html
    assert ESC in html
