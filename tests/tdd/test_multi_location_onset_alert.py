"""TDD RED — Issue #1041 Slice 1a: Mehrort-fähiger Onset-Alarm-Renderer &
Bündel-Nachricht (E-Mail-Kanal).

Macht den Onset-Alarm-Renderpfad (Radar „Regen fängt gleich an") mehrort-fähig,
ohne die produktive Trip-Radar-Ausgabe zu verändern. Alle Tests laufen gegen
echte `NowcastResult`-Fixtures, den echten Renderer und den echten Dispatch-Kern
(`mail_sink`-DI-Seam statt SMTP) — keine Mocks (CLAUDE.md).

SPEC: docs/specs/modules/issue_1041_multi_location_onset_alert.md (Slice 1a/3)
"""
from __future__ import annotations

import uuid
from datetime import timezone

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def _freeze_deployed_commit(monkeypatch):
    """Issue #1241: Die Herkunfts-Fußzeile (Zeile 2) trägt den Commit-Hash aus
    `helpers._DEPLOYED_COMMIT`. Für die Byte-Gleichheits-Golden unten auf einen
    festen Platzhalter einfrieren, sonst brechen die Fixtures nach jedem Commit
    (analog tests/golden/email/conftest.py). Der Renderer liest das Attribut zur
    Laufzeit über `src.output.renderers.email.helpers` — genau dieses Modulobjekt
    wird gepatcht."""
    from src.output.renderers.email import helpers as helpers_mod

    monkeypatch.setattr(helpers_mod, "_DEPLOYED_COMMIT", "gitrev0")

# ---------------------------------------------------------------------------
# Vorher/Nachher-Snapshot des heutigen Single-Onset-Fixtures (AC-2/AC-3).
# Ermittelt durch einmaligen Render-Lauf gegen den Stand VOR dieser Scheibe
# (siehe Spec „Regressions-Invariante"). Bit-identisch einzufrieren.
# ---------------------------------------------------------------------------
EXPECTED_SUBJECT = '[GR20-Test] km 5–18 · Regen in 12 Min'
EXPECTED_PLAIN = (
    'Regen in 12 Min\n\nRadar-Nowcast\n\nWo & wann: km 5–18 · ab 14:35\n'
    'Intensität: leichter Regen\nQuelle: Radar (DWD)\n\n'
    'Stand: heute 14:23\n'
    'Cooldown: Du erhältst diese Warnung höchstens einmal in 2 Stunden.'
    # Issue #1241: geteilte Herkunfts-Fußzeile (radar-alert), Commit eingefroren.
    '\n\nRegen-/Gewitter-Alarm · alert/render.py · gitrev0'
)
EXPECTED_HTML = (
    '<html><body style="font-family:\'Inter Tight\', -apple-system, BlinkMacSystemFont, '
    '\'Segoe UI\', Roboto, sans-serif;color:#1a1a18;">'
    '<div style="display:inline-block;padding:4px 12px;border-radius:12px;'
    'background:#c45a2a1f;color:#c45a2a;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;margin-bottom:12px;">'
    'Radar-Nowcast</div>'
    '<h1 style="margin:0 0 12px;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;color:#1a1a18;">'
    'Regen in 12 Min</h1>'
    '<div style="border-bottom:1px solid #d8d5c9;">'
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="">'
    '<tr><td align="left" style="padding:8px 0;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;color:#5c5a52;">Wo &amp; wann</td>'
    '<td align="right" style="padding:8px 0;font-family:\'JetBrains Mono\', ui-monospace, '
    '\'SF Mono\', Menlo, Consolas, monospace;color:#1a1a18;">km 5–18 · ab 14:35</td>'
    '</tr></table>'
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
    'style="border-top:1px solid #d8d5c9;">'
    '<tr><td align="left" style="padding:8px 0;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;color:#5c5a52;">Intensität</td>'
    '<td align="right" style="padding:8px 0;font-family:\'JetBrains Mono\', ui-monospace, '
    '\'SF Mono\', Menlo, Consolas, monospace;color:#1a1a18;">leichter Regen</td>'
    '</tr></table>'
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
    'style="border-top:1px solid #d8d5c9;">'
    '<tr><td align="left" style="padding:8px 0;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;color:#5c5a52;">Quelle</td>'
    '<td align="right" style="padding:8px 0;font-family:\'JetBrains Mono\', ui-monospace, '
    '\'SF Mono\', Menlo, Consolas, monospace;color:#1a1a18;">Radar (DWD)</td>'
    '</tr></table></div>'
    '<div style="border-left:4px solid #c45a2a;padding:8px 12px;margin-top:12px;'
    'font-family:\'Inter Tight\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, '
    'sans-serif;color:#5c5a52;">Cooldown: Du erhältst diese Warnung höchstens einmal in '
    '2 Stunden.</div>'
    '<p style="color:#5c5a52;margin-top:16px;font-family:\'Inter Tight\', -apple-system, '
    'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
    'Stand: heute 14:23</p>'
    # Issue #1241: geteilte Herkunfts-Fußzeile (radar-alert), Commit eingefroren.
    '<div style="font-family:\'JetBrains Mono\', ui-monospace, \'SF Mono\', Menlo, '
    'Consolas, monospace;font-size:10px;color:#9a978d;padding:10px 24px 14px;'
    'line-height:1.5;"><div>Regen-/Gewitter-Alarm</div>'
    '<div style="color:#b5b1a6;">alert/render.py · gitrev0</div></div>'
    '</body></html>'
)
EXPECTED_TELEGRAM = (
    '<b>GR20-Test · km 5–18 · Regen in 12 Min</b>\n14:35 · leichter Regen · Radar (DWD)'
)
EXPECTED_SMS = 'GR20-Test km5-18: R!12'


def _fresh_user(prefix: str) -> str:
    return f"tdd-1041-{prefix}-{uuid.uuid4().hex[:6]}"


def _test_settings() -> Settings:
    """Settings mit vollständiger (aber ungültiger) SMTP-Konfig — reicht für
    `can_send_email()`, echter Netzwerk-Call wird durch `mail_sink` ersetzt
    (Vorbild test_issue_1088_official_alert_triggers.py TestAC7SmsWithoutParity)."""
    return Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
    )


def _line_for(body: str, needle: str) -> str | None:
    """Erste Zeile im Text-Body, die `needle` enthält (oder None)."""
    for line in body.splitlines():
        if needle in line:
            return line
    return None


def _build_single_onset_message():
    """Baut das bestehende Single-Onset-Fixture (heutiger Trip-Radar-Pfad).

    RED: `OnsetEvent` kennt `location_label` noch nicht -> TypeError beim
    Konstruktor-Aufruf.
    """
    from output.renderers.alert.model import AlertMessage, OnsetEvent

    onset = OnsetEvent(
        onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="Radar (DWD)", location_label=None,
    )
    return AlertMessage(
        trip_short="GR20-Test", stand_at="14:23", events=(onset,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )


# ===========================================================================
# AC-1: Bündel-E-Mail listet alle Orte
# ===========================================================================


def test_bundled_email_lists_all_locations():
    """AC-1: zwei Orts-Fixtures (Onset ≤ 20 Min) → EIN Versand über
    `send_multi_location_radar_alert`, Body listet BEIDE Orte mit eigenem
    Namen und eigener Onset-Angabe (nicht nur der erste Ort).

    RED: `NotificationService.send_multi_location_radar_alert` existiert
    noch nicht -> AttributeError.
    """
    from services.notification_service import NotificationService
    from services.radar_service import NowcastResult

    nc_zermatt = NowcastResult(
        onset_minutes=8, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )
    nc_chamonix = NowcastResult(
        onset_minutes=15, intensity_label="mäßiger Regen", source="AROME-FR",
        is_convective=False,
    )

    settings = _test_settings()
    service = NotificationService(settings, _fresh_user("ac1"))

    mail_calls: list[tuple[str, str]] = []
    result = service.send_multi_location_radar_alert(
        [("Zermatt", nc_zermatt), ("Chamonix", nc_chamonix)],
        {"email"},
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )

    assert len(mail_calls) == 1, (
        f"Erwartet genau EINE gebündelte Mail, erhalten: {len(mail_calls)}"
    )
    _, body = mail_calls[0]

    line_zermatt = _line_for(body, "Zermatt")
    assert line_zermatt is not None, f"Ort 'Zermatt' fehlt im Body: {body!r}"
    assert "8" in line_zermatt, f"Onset-Angabe für Zermatt fehlt: {line_zermatt!r}"

    line_chamonix = _line_for(body, "Chamonix")
    assert line_chamonix is not None, f"Ort 'Chamonix' fehlt im Body: {body!r}"
    assert "15" in line_chamonix, f"Onset-Angabe für Chamonix fehlt: {line_chamonix!r}"

    assert result.sent is True
    assert "email" in result.sent_channels


# ===========================================================================
# AC-2: Single-Onset E-Mail (Subject + Body) byte-identisch
# ===========================================================================


def test_single_onset_email_and_subject_byte_identical():
    """AC-2: Single-Onset-Fixture (location_label=None) rendert Subject +
    E-Mail-Body byte-identisch zum eingefrorenen Vorher-Stand.

    RED: `OnsetEvent(..., location_label=None)` -> TypeError, weil das Feld
    noch nicht existiert.
    """
    from output.renderers.alert.render import render_email, render_subject

    msg = _build_single_onset_message()

    subject = render_subject(msg)
    html, plain = render_email(msg)

    assert subject == EXPECTED_SUBJECT
    assert plain == EXPECTED_PLAIN
    assert html == EXPECTED_HTML


# ===========================================================================
# AC-3: Single-Onset Telegram + SMS unverändert
# ===========================================================================


def test_single_onset_telegram_sms_byte_identical():
    """AC-3: dasselbe Single-Onset-Fixture rendert Telegram + SMS
    byte-identisch — diese Renderer werden in dieser Scheibe nicht angefasst.

    RED: `OnsetEvent(..., location_label=None)` -> TypeError, weil das Feld
    noch nicht existiert.
    """
    from output.renderers.alert.render import render_sms, render_telegram

    msg = _build_single_onset_message()

    telegram = render_telegram(msg)
    sms = render_sms(msg)

    assert telegram == EXPECTED_TELEGRAM
    assert sms == EXPECTED_SMS


# ===========================================================================
# AC-4: konvektiver Ort trägt unterscheidbares Label in der Bündel-Mail
# ===========================================================================


def test_bundle_labels_convective_location_distinctly():
    """AC-4: Bündel-Mail mit einem konvektiven Ort (is_convective=True) und
    einem normalen Regen-Ort — je Ort korrektes, unterschiedliches Label
    (Gewitter/Hagel vs. Regen).

    RED: `to_multi_location_onset_alert_message` existiert noch nicht ->
    ImportError.
    """
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_email
    from services.radar_service import NowcastResult

    nc_conv = NowcastResult(
        onset_minutes=6, intensity_label="Gewitter mit Hagel", source="radar",
        is_convective=True,
    )
    nc_rain = NowcastResult(
        onset_minutes=18, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )

    msg = to_multi_location_onset_alert_message(
        [("Sturmdorf", nc_conv), ("Nieselhausen", nc_rain)],
        tz=timezone.utc, stand_at="14:23",
    )
    _html, plain = render_email(msg)

    line_conv = _line_for(plain, "Sturmdorf")
    line_rain = _line_for(plain, "Nieselhausen")

    assert line_conv is not None, f"Ort 'Sturmdorf' fehlt im Body: {plain!r}"
    assert line_rain is not None, f"Ort 'Nieselhausen' fehlt im Body: {plain!r}"
    assert "Gewitter" in line_conv, (
        f"Konvektiver Ort trägt kein Gewitter/Hagel-Label: {line_conv!r}"
    )
    assert "Regen" in line_rain, f"Regen-Ort trägt kein Regen-Label: {line_rain!r}"
    assert line_conv != line_rain, "Beide Orts-Zeilen dürfen nicht identisch sein"


# ===========================================================================
# AC-5: Bündel-Nachricht mit EINER Gruppe fällt auf Single-Onset-Layout zurück
# ===========================================================================


def test_single_group_falls_back_to_single_onset_layout():
    """AC-5: `to_multi_location_onset_alert_message` mit EINER Gruppe →
    gerenderte E-Mail entspricht dem Ein-Ort-Onset-Layout (kein
    Sammel-Betreff, kein Listen-Layout).

    RED: `to_multi_location_onset_alert_message` existiert noch nicht ->
    ImportError.
    """
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_email, render_subject
    from services.radar_service import NowcastResult

    nc_solo = NowcastResult(
        onset_minutes=10, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )

    msg = to_multi_location_onset_alert_message(
        [("Solo Ort", nc_solo)], tz=timezone.utc, stand_at="14:23",
    )

    assert len(msg.events) == 1, "Eine Gruppe muss genau EIN OnsetEvent erzeugen"
    assert msg.events[0].location_label is None, (
        "Bei genau einer Gruppe muss location_label None bleiben "
        "(fällt auf den Single-Onset-Pfad zurück)"
    )

    subject = render_subject(msg)
    _html, plain = render_email(msg)

    import re
    assert not re.search(r"\d+\s*Orte", subject), (
        f"Kein Sammel-Betreff bei genau einem Ort erwartet: {subject!r}"
    )
    assert "Orte" not in plain, (
        f"Kein Listen-Layout/Sammel-Formulierung bei genau einem Ort erwartet: {plain!r}"
    )
    # Single-Onset-Struktur: genau EIN Datenblock ("Wo & wann" erscheint nur einmal).
    assert plain.count("Wo & wann") == 1, (
        f"Erwartet genau EINE 'Wo & wann'-Zeile (Single-Layout): {plain!r}"
    )


# ===========================================================================
# Fix-Loop (#1041, Adversary-Nebenbefunde F001/F002/F003)
# ===========================================================================


def test_bundle_footer_shows_distinct_sources():
    """F003: Bündel mit zwei Orten UNTERSCHIEDLICHER Quelle → die gerenderte
    E-Mail-Fußzeile nennt BEIDE Quell-Labels (nicht die feste "Radar (DWD)"-
    Fußzeile). Zwei Orte GLEICHER Quelle → nur ein Quell-Label."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_email
    from services.radar_service import NowcastResult

    nc_radar = NowcastResult(
        onset_minutes=8, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )
    nc_arome = NowcastResult(
        onset_minutes=15, intensity_label="mäßiger Regen", source="AROME-FR",
        is_convective=False,
    )

    msg_mixed = to_multi_location_onset_alert_message(
        [("Zermatt", nc_radar), ("Chamonix", nc_arome)],
        tz=timezone.utc, stand_at="14:23",
    )
    _html, plain_mixed = render_email(msg_mixed)
    footer_mixed = _line_for(plain_mixed, "Stand: heute")
    assert footer_mixed is not None
    assert "radar" in footer_mixed, f"Erste Quelle fehlt in Fußzeile: {footer_mixed!r}"
    assert "AROME-FR" in footer_mixed, f"Zweite Quelle fehlt in Fußzeile: {footer_mixed!r}"
    assert footer_mixed != "Stand: heute 14:23 · Quelle: Radar (DWD)", (
        "Fußzeile darf nicht mehr fest auf 'Radar (DWD)' stehen"
    )

    nc_radar_2 = NowcastResult(
        onset_minutes=12, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )
    msg_same = to_multi_location_onset_alert_message(
        [("Zermatt", nc_radar), ("Nieselhausen", nc_radar_2)],
        tz=timezone.utc, stand_at="14:23",
    )
    _html2, plain_same = render_email(msg_same)
    footer_same = _line_for(plain_same, "Stand: heute")
    assert footer_same == "Stand: heute 14:23 · Quelle: radar", (
        f"Bei nur einer distinct Quelle darf sie nur EINMAL erscheinen: {footer_same!r}"
    )


def test_empty_groups_raises_valueerror():
    """F001: leere `groups`-Liste → definierter `ValueError`, keine
    `IndexError` (Absturz-Härtung für Slice 1b)."""
    import pytest

    from output.renderers.alert.project import to_multi_location_onset_alert_message

    with pytest.raises(ValueError):
        to_multi_location_onset_alert_message([], tz=timezone.utc, stand_at="14:23")


def test_none_onset_entries_filtered_or_raise():
    """F002: `NowcastResult.onset_minutes=None` gehört nicht in einen
    Radar-Alarm-Bündel. Gemischtes Bündel (zwei gültige Orte + ein
    None-Ort) → die Mail listet nur die gültigen Orte, der None-Ort fehlt.
    Bündel NUR aus None-Onset → `ValueError`."""
    import pytest

    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_email
    from services.radar_service import NowcastResult

    nc_valid_1 = NowcastResult(
        onset_minutes=10, intensity_label="leichter Regen", source="radar",
        is_convective=False,
    )
    nc_valid_2 = NowcastResult(
        onset_minutes=20, intensity_label="mäßiger Regen", source="radar",
        is_convective=False,
    )
    nc_none = NowcastResult(
        onset_minutes=None, intensity_label="kein Niederschlag", source="radar",
        is_convective=False,
    )

    msg = to_multi_location_onset_alert_message(
        [("Gueltigdorf", nc_valid_1), ("Leerdorf", nc_none), ("Zweitdorf", nc_valid_2)],
        tz=timezone.utc, stand_at="14:23",
    )
    assert len(msg.events) == 2, "None-Onset-Ort darf nicht als Event landen"
    _html, plain = render_email(msg)
    assert "Gueltigdorf" in plain
    assert "Zweitdorf" in plain
    assert "Leerdorf" not in plain

    with pytest.raises(ValueError):
        to_multi_location_onset_alert_message(
            [("Nur-Leerdorf", nc_none)], tz=timezone.utc, stand_at="14:23",
        )
