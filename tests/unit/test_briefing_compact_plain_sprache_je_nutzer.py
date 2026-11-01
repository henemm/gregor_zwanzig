"""Zwei Nutzer, zwei Sprachen, Kompakt-Format, ein Prozess (Issue #2665, AC-7).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Nutzer A hat ``language: "en"`` in seinem ``user.json``, Nutzer B kein Feld;
beide haben ``email_format: "compact"``. Fuer beide laeuft nacheinander (in
beiden Reihenfolgen) der echte Weg Sprachaufloesung (``resolve_user_lang``)
-> Renderer (``TripReportFormatter.format_email``, Kompakt) -> Mailversand
(``EmailOutput.send`` mit den Settings DIESES Nutzers). Ersetzt wird
ausschliesslich der SMTP-Rand ``EmailOutput._dial_and_send`` (Muster
``test_briefing_mail_sprache_je_nutzer.py``).

Abweichung von der Spec (bewusst, s. PR): die Durchreichung in
``NotificationService.send_trip_report`` gehoert zu P9a (#2671) -- dieser
Test belegt, dass Renderer und Versand keinen Sprachzustand zwischen Nutzern
teilen, nicht die Verdrahtung im Versanddienst.
"""
from __future__ import annotations

import email
import json

import pytest

from tests.helpers.briefing_compact_plain_fixture import render_briefing

DUMMY_ENV = {
    "GZ_SMTP_HOST": "mail.henemm.com", "GZ_SMTP_PORT": "587",
    "GZ_SMTP_USER": "tdd-2665", "GZ_SMTP_PASS": "tdd-2665-kein-echtes-passwort",
    "GZ_TEST_SMTP_HOST": "mail.henemm.com", "GZ_TEST_SMTP_USER": "tdd-2665",
    "GZ_TEST_SMTP_PASS": "tdd-2665-kein-echtes-passwort",
}
NUTZER = {
    "tdd-2665-anna": ({"language": "en"}, "anna-2665@henemm.com", "Anna Hut Trail"),
    "tdd-2665-bernd": ({}, "bernd-2665@henemm.com", "Bernds Huettentour"),
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
    report = render_briefing(lang, email_format="compact", trip_name=NUTZER[user_id][2])
    EmailOutput(Settings().with_user_profile(user_id)).send(
        subject=report.email_subject, body=report.email_plain, html=False,
        mail_type="trip-briefing", mail_format="compact", lang=lang,
    )


@pytest.mark.parametrize("reihenfolge", [("tdd-2665-anna", "tdd-2665-bernd"),
                                         ("tdd-2665-bernd", "tdd-2665-anna")],
                         ids=["A_dann_B", "B_dann_A"])
def test_ac7_jeder_nutzer_bekommt_seine_sprache_im_kompaktformat(smtp_rand, reihenfolge):
    for uid in NUTZER:
        _profil_anlegen(uid)
    for uid in reihenfolge:
        _briefing_versenden(uid)

    assert len(smtp_rand) == 2
    je_nutzer = {uid: msg for uid, (_, msg) in zip(reihenfolge, smtp_rand)}
    anna, bernd = je_nutzer["tdd-2665-anna"], je_nutzer["tdd-2665-bernd"]

    assert anna["X-GZ-Lang"] == "en" and anna["X-GZ-Format"] == "compact"
    text_a = anna.get_payload(decode=True).decode("ascii")
    assert "== Metrics overview ==" in text_a and "Next stages" in text_a
    assert "Metriken-Ueberblick" not in text_a and "Naechste Etappen" not in text_a
    assert "Anna Hut Trail" in text_a and "Bernds Huettentour" not in text_a

    assert bernd["X-GZ-Lang"] == "de" and bernd["X-GZ-Format"] == "compact"
    text_b = bernd.get_payload(decode=True).decode("ascii")
    assert "== Metriken-Ueberblick ==" in text_b and "Naechste Etappen" in text_b
    assert "Metrics overview" not in text_b and "Next stages" not in text_b
    assert "Bernds Huettentour" in text_b and "Anna Hut Trail" not in text_b
