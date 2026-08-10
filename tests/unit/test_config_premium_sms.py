"""Premium-SMS: Rueckadresse kommt ausschliesslich aus ``user.json``.

Spec: docs/specs/modules/feat_1676_s2a_premium_sms_versand.md — AC-9 sowie die
beiden Traeger dieser Zusicherung (Feld-Deklaration, Profil-Uebernahme).

Prueforte:

- **AC-9** ist die ``Settings(...)``-Konstruktion selbst. Ein still akzeptierter
  ``GZ_``-Wert wuerde erst beim naechsten Versand sichtbar — dann ist die SMS
  schon draussen (und kostenpflichtig). Je Variable ein eigener Fall: ein
  Override von ``premium_sms_reply_at`` frischt die 30-Tage-Frist kuenstlich auf
  und gibt damit den Versand an eine langst veraltete Nummer frei; eine Sperre,
  die man mit einer Umgebungsvariable abschalten kann, ist keine.
- **Feld-Deklaration:** ``extra="ignore"`` (``config.py``) verschluckt
  undeklarierte Werte lautlos — ein nur in ``with_user_profile()`` ergaenztes
  Feld verschwindet also spurlos. Geprueft wird deshalb, dass ein uebergebener
  Wert am Objekt ANKOMMT, nicht bloss, dass irgendwo eine Zeile steht.
- **Profil-Uebernahme:** echte ``user.json`` in der (per conftest isolierten)
  Datenwurzel, gelesen ueber den einzigen Profil->Settings-Uebersetzer.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.loader import get_data_dir

LEARNED_REPLY_TO = "+4915799912345"
ENV_INJECTED_NUMBER = "+4915700000000"


def _write_profile(user_id: str, *, with_premium_fields: bool) -> datetime | None:
    """Schreibt ``user.json`` wie der einzige Schreiber (Go-Handler, S1) es tut."""
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    profile: dict = {"id": user_id, "tier": "premium"}
    stamp = None
    if with_premium_fields:
        stamp = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0)
        profile["premium_sms_reply_to"] = LEARNED_REPLY_TO
        profile["premium_sms_reply_at"] = stamp.isoformat().replace("+00:00", "Z")
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")
    return stamp


# ---------------------------------------------------------------------------
# AC-9: ENV-Sperre, je Variable ein Fall
# ---------------------------------------------------------------------------

def test_env_override_for_reply_to_is_rejected_loudly(monkeypatch) -> None:
    """AC-9: Given ``GZ_PREMIUM_SMS_REPLY_TO`` steht im Prozess-Environment /
    When ``Settings()`` konstruiert wird / Then schlaegt die Konstruktion laut
    fehl, statt den Wert stillschweigend zu uebernehmen."""
    monkeypatch.delenv("GZ_PREMIUM_SMS_REPLY_TO", raising=False)
    assert Settings() is not None, (
        "Gegenprobe: ohne die Umgebungsvariable muss Settings() normal bauen — "
        "sonst prueft dieser Test nur ein generell kaputtes Settings."
    )

    monkeypatch.setenv("GZ_PREMIUM_SMS_REPLY_TO", ENV_INJECTED_NUMBER)
    with pytest.raises(ValueError) as excinfo:
        Settings()

    message = str(excinfo.value)
    assert "GZ_PREMIUM_SMS_REPLY_TO" in message.upper(), (
        f"Die Fehlermeldung benennt die verbotene Variable nicht: {message!r}"
    )
    assert ENV_INJECTED_NUMBER not in message, (
        "Rufnummern gehoeren nicht unmaskiert in Fehlermeldungen "
        f"(Spec S1: nur maskiert protokollieren): {message!r}"
    )


def test_env_override_for_reply_at_is_rejected_loudly(monkeypatch) -> None:
    """AC-9: dasselbe fuer ``GZ_PREMIUM_SMS_REPLY_AT`` — ein aufgefrischter
    Zeitstempel wuerde die 30-Tage-Frist (AC-4) wirkungslos machen, bei formal
    korrekter Rufnummer."""
    monkeypatch.delenv("GZ_PREMIUM_SMS_REPLY_AT", raising=False)
    assert Settings() is not None, "Gegenprobe: ohne die Variable muss Settings() bauen"

    monkeypatch.setenv(
        "GZ_PREMIUM_SMS_REPLY_AT", datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(ValueError) as excinfo:
        Settings()

    assert "GZ_PREMIUM_SMS_REPLY_AT" in str(excinfo.value).upper(), (
        f"Die Fehlermeldung benennt die verbotene Variable nicht: {excinfo.value!r}"
    )


# ---------------------------------------------------------------------------
# Traeger 1: die Felder muessen deklariert sein, sonst frisst extra="ignore" sie
# ---------------------------------------------------------------------------

def test_declared_premium_sms_fields_survive_construction() -> None:
    """Given ``Settings`` wird mit gelernter Rueckadresse und Zeitstempel gebaut
    / When die Werte gelesen werden / Then stehen sie am Objekt — ein
    undeklariertes Feld waere von ``extra="ignore"`` lautlos verschluckt
    worden, und die Rueckadresse waere nie beim Versand angekommen."""
    stamp = datetime.now(timezone.utc).replace(microsecond=0)

    settings = Settings(premium_sms_reply_to=LEARNED_REPLY_TO, premium_sms_reply_at=stamp)

    assert settings.premium_sms_reply_to == LEARNED_REPLY_TO
    assert settings.premium_sms_reply_at == stamp
    assert Settings().premium_sms_reply_to in (None, ""), (
        "Ohne Profil darf keine Rueckadresse vorbelegt sein — fail-closed."
    )
    assert Settings().premium_sms_reply_at is None


# ---------------------------------------------------------------------------
# Traeger 2: with_user_profile() ist der einzige Weg an die gelernten Werte
# ---------------------------------------------------------------------------

def test_with_user_profile_takes_over_learned_reply_address() -> None:
    """Given ``user.json`` traegt die gelernte Rueckadresse und ihren
    Zeitstempel / When ``Settings().with_user_profile()`` laeuft / Then stehen
    beide Werte an den Settings — sonst kann kein Versandzweig sie sehen."""
    user_id = "tdd-1676-cfg-profile"
    stamp = _write_profile(user_id, with_premium_fields=True)

    settings = Settings().with_user_profile(user_id)

    assert settings.premium_sms_reply_to == LEARNED_REPLY_TO, (
        f"Gelernte Rueckadresse nicht uebernommen: {settings.premium_sms_reply_to!r}"
    )
    reply_at = settings.premium_sms_reply_at
    assert reply_at is not None, "Zeitstempel nicht uebernommen — die 30-Tage-Frist waere blind"
    if isinstance(reply_at, str):
        reply_at = datetime.fromisoformat(reply_at.replace("Z", "+00:00"))
    assert reply_at.tzinfo is not None, (
        f"Zeitstempel ohne Zeitzone ({reply_at!r}) — ein Vergleich mit 'jetzt' "
        "waere je nach Serverzeit um Stunden verschoben."
    )
    assert abs((reply_at - stamp).total_seconds()) < 2, (
        f"Zeitstempel weicht ab: {reply_at!r} != {stamp!r}"
    )


def test_no_second_readiness_question_for_premium_sms() -> None:
    """Adversary-Fund F003: Given jemand baut eine
    ``Settings.can_send_premium_sms()``-Bereitschaftsfrage (wieder) ein / When
    diese Datei laeuft / Then schlaegt sie fehl — die Sendebereitschaft des
    Premium-Kanals entscheidet allein der Kanal zur Sendezeit (Spec D3), und
    eine zweite, vorgeschaltete Frage wuerde die Fail-Closed-Pruefung dort
    abschirmen: sie liesse sich entfernen, ohne dass ein Test rot wird.

    Prueft die Zusicherung an ihrem Wirkort — am Objekt, das der Versandzweig
    benutzt, nicht am Dateitext (eine Kommentarzeile im Code waere kein
    Schutz). Die zwei EXISTIERENDEN Geschwister werden mitgeprueft: fiele die
    Namensfamilie ganz weg, waere dieser Test sonst still gegenstandslos.
    """
    settings = Settings(
        premium_sms_reply_to=LEARNED_REPLY_TO,
        premium_sms_reply_at=datetime.now(timezone.utc),
    )

    assert not hasattr(settings, "can_send_premium_sms"), (
        "`Settings.can_send_premium_sms()` ist wieder da. Entweder hat sie "
        "jetzt einen echten Wirkort — dann muss ein Test genau diesen Wirkort "
        "bewachen und dieser hier weichen — oder sie ist erneut toter Code, "
        "der Vertrauen in einen Schutz vortaeuscht, den nur "
        "`PremiumSmsOutput._resolve_recipient()` leistet."
    )
    assert callable(settings.can_send_sms) and callable(settings.can_send_telegram), (
        "Gegenprobe: die Bereitschaftsfragen der anderen Kanaele muessen "
        "existieren — sonst prueft dieser Test nur ein leeres Settings-Objekt."
    )
