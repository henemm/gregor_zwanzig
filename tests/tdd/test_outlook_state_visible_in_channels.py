"""Fix #1486 (TDD RED) — der Ausblick-Zustand wird auf ALLEN Wegen sichtbar.

Spec: docs/specs/modules/fix_1486_outlook_silent_exit.md (AC-1..AC-6, AC-8)
Kontext: docs/context/fix-1486-outlook-silent-exit.md

Diese Datei prueft die AUSGABE-Seite: was der Empfaenger in HTML-Mail,
Klartext-Mail, Compact-Mail und Telegram liest, wenn der Ausblick entfaellt.
Die Erzeugungs-Seite (Zustand + Protokoll) prueft
``tests/tdd/test_outlook_state_named_not_silent.py``.

Geprueft wird am echten gemeinsamen Render-Punkt ``TripReportFormatter.
format_email()`` — genau der, den BEIDE Wege benutzen (Versand ueber
``notification_service.py:292``, Vorschau ueber ``preview_service.
_render_email``). Kein Zwischenformat, keine Mocks: echte
``SegmentWeatherData``/``Trip``-Objekte aus dem Bestands-Baukasten
``tests/tdd/test_preview_thunder_matches_sent.py`` (dort ausdruecklich als
geteilte Bausteine gefuehrt), kein Netz.

RED heute: ``format_email()`` kennt ``outlook_state`` nicht (TypeError) und der
Block entfaellt in allen vier Kanaelen kommentarlos.
AUSNAHME: AC-6 (Vorschau bleibt zeichengleich) und der Bestands-Teil von AC-8
(Ausblick im Morgen-Briefing) beschreiben Verhalten, das schon heute gilt und
NICHT brechen darf — sie sind absichtlich gruen.
"""
from __future__ import annotations

import re

from zoneinfo import ZoneInfo

from tests.tdd.test_preview_thunder_matches_sent import (
    _current_stage_segments,
    _trend_rows,
    _trip_with_thunder,
    build_thunder_scenario,
    preview_report,
    send_report,
)

_UTC = ZoneInfo("UTC")

TEXT_NO_STAGES = "Keine weiteren Etappen — kein Ausblick."
TEXT_BEYOND = "Nächste Etappe liegt zu weit voraus (max. {n} Tage)."
TEXT_UNAVAILABLE = "Vorhersage derzeit nicht abrufbar."


def _state(name):
    from output.renderers.email.outlook_state_hint import OutlookState

    return getattr(OutlookState, name)


def _render(report_type="evening", email_format="full", *, trend=None,
            state=None, horizon_days=None):
    """Ein echtes Briefing rendern (alle vier Kanaele in EINEM Aufruf)."""
    from app.models import TripReportConfig
    from output.renderers.trip_report import TripReportFormatter
    from services.report_config_resolver import resolve_report_render_options

    trip = _trip_with_thunder()
    rc = TripReportConfig(
        trip_id=trip.id,
        email_format=email_format,
        multi_day_trend_reports=[report_type],
    )
    extra = {}
    if state is not None:
        extra["outlook_state"] = _state(state)
        extra["outlook_horizon_days"] = horizon_days
    return TripReportFormatter().format_email(
        segments=_current_stage_segments(),
        trip_name=trip.name,
        report_type=report_type,
        display_config=trip.display_config,
        stage_name="Heute",
        stage_stats=None,
        tz=_UTC,
        profile=trip.aggregation.profile,
        stability_result=None,
        report_config=rc,
        render_options=resolve_report_render_options(
            rc, trip.display_config, report_type,
        ),
        multi_day_trend=trend,
        **extra,
    )


def _telegram_text(report):
    return "\n".join(report.telegram_bubbles)


# ---------------------------------------------------------------------------
# AC-5 — alle VIER Ausgabewege nennen die Stoerung (Klasse C)
# ---------------------------------------------------------------------------

def test_ac5_html_mail_shows_unavailable_hint():
    """AC-5 (HTML): Danger-Box mit dem Stoerungs-Satz."""
    from output.renderers.email.design_tokens import G_DANGER

    rep = _render(state="UNAVAILABLE")
    assert TEXT_UNAVAILABLE in rep.email_html, (
        "Die HTML-Mail zeigt bei gestoertem Ausblick weiterhin eine unerklaerte "
        "Leerstelle statt des Hinweises."
    )
    assert G_DANGER in rep.email_html, (
        "Der Stoerungs-Hinweis braucht Danger-Optik (Vorbild unavailable_hint.py)."
    )


def test_ac5_plain_mail_shows_unavailable_hint():
    """AC-5 (Klartext): Satz mit Warn-Symbol."""
    rep = _render(state="UNAVAILABLE")
    hint_lines = [ln for ln in rep.email_plain.splitlines() if TEXT_UNAVAILABLE in ln]
    assert hint_lines, (
        f"Die Klartext-Mail nennt den Ausblick-Ausfall nicht:\n{rep.email_plain}"
    )
    assert any("⚠️" in ln for ln in hint_lines), (
        f"Der Stoerungs-Hinweis braucht das Warn-Symbol, war: {hint_lines}"
    )


def test_ac5_compact_mail_shows_unavailable_hint():
    """AC-5 (Compact): ASCII-Fassung mit "!!"-Praefix."""
    rep = _render(email_format="compact", state="UNAVAILABLE")
    assert f"!! {TEXT_UNAVAILABLE}" in rep.email_plain, (
        f"Die Compact-Mail nennt den Ausblick-Ausfall nicht:\n{rep.email_plain}"
    )


def test_ac5_telegram_shows_unavailable_hint():
    """AC-5 (Telegram, narrow.py): der oft vergessene vierte Weg."""
    rep = _render(state="UNAVAILABLE")
    assert TEXT_UNAVAILABLE in _telegram_text(rep), (
        "Telegram laesst die Ausblick-Bubble bei Stoerung kommentarlos weg:\n"
        f"{_telegram_text(rep)}"
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 — die beiden ruhigen Zustaende, sichtbar aber ohne Alarm-Ton
# ---------------------------------------------------------------------------

def test_ac1_no_stages_text_is_visible_and_calm():
    """AC-1: Tourabschluss wird benannt — ohne Warn-/Danger-Optik."""
    from output.renderers.email.design_tokens import G_BOX_DANGER_BG, G_DANGER
    from output.renderers.email.outlook_state_hint import (
        render_outlook_state_html, render_outlook_state_plain,
    )

    rep = _render(state="NO_STAGES")
    assert TEXT_NO_STAGES in rep.email_plain, (
        f"Der Tourabschluss bleibt unerklaert:\n{rep.email_plain}"
    )
    assert TEXT_NO_STAGES in rep.email_html

    plain = render_outlook_state_plain(_state("NO_STAGES"))
    assert "⚠️" not in plain and "!!" not in plain, (
        f"Ein normaler Tourabschluss ist keine Warnung, war: {plain!r}"
    )
    html = render_outlook_state_html(_state("NO_STAGES"))
    assert G_DANGER not in html and G_BOX_DANGER_BG not in html, (
        "Ein normaler Tourabschluss darf nicht wie eine Stoerung aussehen."
    )


def test_ac2_beyond_horizon_text_names_the_real_horizon():
    """AC-2: der Text nennt den ECHTEN, konfigurierten Horizont."""
    from providers.openmeteo import OPENMETEO_MAX_FORECAST_DAYS

    n = OPENMETEO_MAX_FORECAST_DAYS
    rep = _render(state="BEYOND_HORIZON", horizon_days=n)
    assert TEXT_BEYOND.format(n=n) in rep.email_plain, (
        f"Erwartet: {TEXT_BEYOND.format(n=n)!r}\nMail war:\n{rep.email_plain}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Unterscheidbarkeit (Kern des Issues)
# ---------------------------------------------------------------------------

def test_ac4_the_three_states_are_pairwise_distinguishable():
    """AC-4: die drei Zustaende sind fuer den Empfaenger paarweise
    unterscheidbar — sowohl als Baustein-Text als auch in der fertigen Mail."""
    from output.renderers.email.outlook_state_hint import render_outlook_state_plain

    texts = [
        render_outlook_state_plain(_state("NO_STAGES")),
        render_outlook_state_plain(_state("BEYOND_HORIZON"), 15),
        render_outlook_state_plain(_state("UNAVAILABLE")),
    ]
    assert all(t.strip() for t in texts), f"Kein Zustand darf leer bleiben: {texts}"
    assert len(set(texts)) == 3, (
        f"Die drei Zustaende duerfen nicht dieselbe Phrase zeigen: {texts}"
    )

    mails = [
        _render(state="NO_STAGES").email_plain,
        _render(state="BEYOND_HORIZON", horizon_days=15).email_plain,
        _render(state="UNAVAILABLE").email_plain,
    ]
    assert len(set(mails)) == 3, (
        "Die drei Zustaende erzeugen identische Mails — genau der Befund aus "
        "#1486 ('fuer den Empfaenger sehen alle fuenf identisch aus')."
    )


def test_ac1_ac2_ac3_logging_contract_of_the_shared_building_block():
    """AC-1/2/3: nur die beiden Stoerfaelle sind protokollwuerdig."""
    from output.renderers.email.outlook_state_hint import outlook_state_should_warn

    assert outlook_state_should_warn(_state("NO_STAGES")) is False
    assert outlook_state_should_warn(_state("BEYOND_HORIZON")) is True
    assert outlook_state_should_warn(_state("UNAVAILABLE")) is True


# ---------------------------------------------------------------------------
# AC-6 — Vorschau bleibt zeichengleich (ADR-0025/#1297) — GRUEN, Bestandsschutz
# ---------------------------------------------------------------------------

_SENT_LABEL = re.compile(r"gesendet [A-Za-z]{2} · \d{2}:\d{2}")


def test_ac6_preview_stays_byte_identical_to_the_sent_report():
    """AC-6: derselbe Trend ergibt in Vorschau und Versand dieselben Bytes.

    Einzige Ausnahme im HTML: das minutengenaue "gesendet"-Label (#623 AC-5),
    das beide Aufrufe naturgemaess unterschiedlich stempeln koennen.
    """
    ctx = build_thunder_scenario()
    sent, preview = send_report(*ctx), preview_report(*ctx)

    assert preview.email_plain == sent.email_plain
    assert preview.sms_text == sent.sms_text
    assert preview.telegram_bubbles == sent.telegram_bubbles
    assert _SENT_LABEL.sub("", preview.email_html) == _SENT_LABEL.sub("", sent.email_html)


def test_ac6_preview_seam_accepts_every_outlook_parameter_of_the_render():
    """AC-6: die Vorschau-Naht muss JEDEN ausblick-bezogenen Parameter des
    Renders durchreichen koennen — sonst divergiert sie wieder strukturell
    (#1297). Heute gruen (beide kennen ``multi_day_trend``); nach dem Fix rot,
    falls ``outlook_state`` nur in den Versandpfad eingebaut wird.
    """
    import inspect

    from output.renderers.trip_report import TripReportFormatter
    from services.preview_service import PreviewService

    def _outlook_params(func):
        return {
            name for name in inspect.signature(func).parameters
            if "outlook" in name or "trend" in name
        }

    render_params = _outlook_params(TripReportFormatter.format_email)
    preview_params = _outlook_params(PreviewService._render_email)
    assert render_params <= preview_params, (
        "Die Vorschau-Naht kennt diese Ausblick-Parameter des Renders nicht: "
        f"{sorted(render_params - preview_params)}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Morgen-Briefing (Testluecke aus #1388)
# ---------------------------------------------------------------------------

def test_ac8_morning_briefing_shows_the_outlook_like_the_evening_one():
    """AC-8: mit ``multi_day_trend_reports=["morning"]`` zeigt das
    Morgen-Briefing denselben Ausblick-Block wie das Abend-Briefing.
    Bestandsverhalten — bisher ungetestet (#1388), ab jetzt bewacht."""
    trend = _trend_rows()
    morning = _render("morning", trend=trend)
    evening = _render("evening", trend=trend)

    for rep, label in ((morning, "Morgen"), (evening, "Abend")):
        assert "Nächste Etappen" in rep.email_plain, (
            f"{label}-Briefing zeigt keinen Ausblick-Block:\n{rep.email_plain}"
        )
        assert "Folgeetappe" in rep.email_plain, (
            f"{label}-Briefing zeigt den Ausblick ohne Etappen-Inhalt."
        )
        assert "Ausblick · nächste 3 Tage" in rep.email_html
        assert "Ausblick" in _telegram_text(rep)


def test_ac8_morning_briefing_names_the_outlook_state_too():
    """AC-8 + AC-5: faellt der Ausblick im MORGEN-Briefing aus, bekommt der
    Empfaenger dort denselben Hinweis wie abends."""
    rep = _render("morning", state="UNAVAILABLE")
    assert TEXT_UNAVAILABLE in rep.email_plain, (
        f"Morgen-Briefing verschweigt den Ausblick-Ausfall:\n{rep.email_plain}"
    )
