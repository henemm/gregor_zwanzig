"""Zwei Nutzer, zwei Sprachen, ein Prozess (Issue #2664, AC-5 -- Renderer-/Versandteil).

SPEC: docs/specs/modules/i18n_p2_briefing_mail_html_2664.md

Nutzer A hat ``language: "en"`` in seinem ``user.json``, Nutzer B kein Feld.
Fuer beide laeuft nacheinander (in beiden Reihenfolgen) der echte Weg
Sprachaufloesung (``resolve_user_lang``) -> Renderer
(``TripReportFormatter.format_email``) -> Mailversand (``EmailOutput.send``
mit den Settings DIESES Nutzers). Ersetzt wird ausschliesslich der SMTP-Rand
``EmailOutput._dial_and_send`` (Muster ``test_briefing_recipient_logging.py``);
Zugangsdaten sind Dummy-Werte.

Die Durchreichung im Versanddienst ``NotificationService.send_trip_report``
folgt mit P9a (#2671) -- dieser Test belegt, dass Renderer und Versand keinen
Sprachzustand zwischen Nutzern teilen.
"""
from __future__ import annotations

import email
import json

import pytest

from tests.helpers.briefing_html_sprache_fixture import render_reich, sichtbarer_text

DUMMY_ENV = {
    "GZ_SMTP_HOST": "mail.henemm.com", "GZ_SMTP_PORT": "587",
    "GZ_SMTP_USER": "tdd-2664", "GZ_SMTP_PASS": "tdd-2664-kein-echtes-passwort",
    "GZ_TEST_SMTP_HOST": "mail.henemm.com", "GZ_TEST_SMTP_USER": "tdd-2664",
    "GZ_TEST_SMTP_PASS": "tdd-2664-kein-echtes-passwort",
}
NUTZER = {
    "tdd-2664-anna": ({"language": "en"}, "anna-2664@henemm.com", "Anna Hut Trail"),
    "tdd-2664-bernd": ({}, "bernd-2664@henemm.com", "Bernds Hüttentour"),
}


@pytest.fixture
def smtp_rand(monkeypatch) -> list:
    for key, value in DUMMY_ENV.items():
        monkeypatch.setenv(key, value)
    gesendet: list = []

    def _steckdose(self, host, port, user, password, recipients, msg,
                   from_addr, deadline_at, message_ids=None):
        gesendet.append((list(recipients), email.message_from_bytes(msg.as_bytes())))

    monkeypatch.setattr("output.channels.email.EmailOutput._dial_and_send", _steckdose)
    return gesendet


def _profil_anlegen(user_id: str) -> None:
    from app.loader import get_data_dir

    extra, mail_to, _ = NUTZER[user_id]
    pfad = get_data_dir(user_id) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"mail_to": mail_to, "is_test_user": True, **extra}))


def _briefing_versenden(user_id: str) -> None:
    from app.config import Settings
    from i18n import resolve_user_lang
    from output.channels.email import EmailOutput

    lang = resolve_user_lang(user_id)
    report = render_reich(lang, trip_name=NUTZER[user_id][2])
    EmailOutput(Settings().with_user_profile(user_id)).send(
        subject=report.email_subject, body=report.email_html,
        plain_text_body=report.email_plain, mail_type="trip-briefing",
        mail_format="full", lang=lang,
    )


def _html_teil(msg) -> str:
    for teil in msg.walk():
        if teil.get_content_type() == "text/html":
            return teil.get_payload(decode=True).decode("utf-8")
    raise AssertionError("kein HTML-Teil")


@pytest.mark.parametrize("reihenfolge", [("tdd-2664-anna", "tdd-2664-bernd"),
                                         ("tdd-2664-bernd", "tdd-2664-anna")],
                         ids=["A_dann_B", "B_dann_A"])
def test_ac5_jeder_nutzer_bekommt_seine_sprache(smtp_rand, reihenfolge):
    for uid in NUTZER:
        _profil_anlegen(uid)
    for uid in reihenfolge:
        _briefing_versenden(uid)

    # Die Herkunftssperre (#1476) lenkt Testlaeufe auf das Testpostfach um --
    # die Zuordnung laeuft deshalb ueber die Versandreihenfolge.
    assert len(smtp_rand) == 2
    je_nutzer = {uid: msg for uid, (_, msg) in zip(reihenfolge, smtp_rand)}
    anna = je_nutzer["tdd-2664-anna"]
    bernd = je_nutzer["tdd-2664-bernd"]

    assert anna["X-GZ-Lang"] == "en"
    text_a = sichtbarer_text(_html_teil(anna))
    assert "Night at destination" in text_a and "Nacht am Ziel" not in text_a
    assert "Anna Hut Trail" in text_a and "Bernds Hüttentour" not in text_a

    assert bernd["X-GZ-Lang"] == "de"
    text_b = sichtbarer_text(_html_teil(bernd))
    assert "Nacht am Ziel" in text_b and "Night at destination" not in text_b
    assert "Bernds Hüttentour" in text_b and "Anna Hut Trail" not in text_b
