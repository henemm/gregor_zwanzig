"""TDD RED — Issue #2152, AC-2 / AC-4: ``Settings.with_user_profile()`` waehlt die
Kanal-Credentials ueber das Profilfeld ``is_test_user``, nicht ueber die
Namens-Heuristik.

Spec: docs/specs/modules/testkonto_profilfeld.md

RED-Stand (vor GREEN):
- AC-2 (protester ohne Flag → Prod-SMTP) ist ROT: ``is_test_user_id("protester")``
  matcht heute den Substring "test" → ``for_testing()`` → Test-Host.
- AC-4 (mitarbeiter42 mit Flag → Test-SMTP) ist ROT: ``is_test_user_id`` liest
  das Profil heute unter dem literalen Default ``data_dir="data"`` statt unter
  der konfigurierten Datenwurzel (``get_data_root()``, tests/conftest.py #1133)
  — das Flag unter der isolierten Wurzel wird nie gesehen.

Profile werden ueber ``get_data_dir(user_id)`` geschrieben (Muster
tests/unit/test_with_user_profile_no_global_fallback.py) — greift automatisch
die ``_DATA_ROOT``-Isolation. ``Settings`` wird mit expliziten kwargs und
``_env_file=None`` gebaut; der Prod-Host ist ein Sentinel (``smtp.prod.invalid``),
damit ein Wert aus der lokalen ``.env`` nichts beweisen kann. Kein ``data_dir``
an ``with_user_profile`` — ``Settings._is_test_user`` ist ``@staticmethod`` und
kann die konfigurierte Wurzel nur ueber ``is_test_user_id`` selbst erreichen.
"""
from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.loader import get_data_dir

PROD_SMTP_HOST = "smtp.prod.invalid"
TEST_SMTP_HOST = "stalwart.test.invalid"


def _write_profile(user_id: str, profile: dict) -> None:
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


@pytest.fixture
def prod_settings(monkeypatch) -> Settings:
    """Produktions-Settings mit Sentinel-Hosts, ohne ``.env``-Einfluss."""
    for var in ("GZ_ENV", "GZ_SMTP_HOST", "GZ_TEST_SMTP_HOST", "GZ_DATA_DIR"):
        monkeypatch.delenv(var, raising=False)
    return Settings(
        env="production",
        smtp_host=PROD_SMTP_HOST,
        smtp_user="resend",
        smtp_pass="re_x",
        test_smtp_host=TEST_SMTP_HOST,
        test_smtp_user="gregor-test",
        test_smtp_pass="pw",
        _env_file=None,
    )


def test_protester_ohne_flag_bekommt_prod_credentials_ac2(prod_settings):
    """AC-2 GIVEN Profil "protester" ohne ``is_test_user`` / WHEN
    ``with_user_profile("protester")`` / THEN Prod-SMTP, ``is_test_mode`` False."""
    _write_profile("protester", {"id": "protester", "mail_to": "protester@example.com"})

    s = prod_settings.with_user_profile("protester")

    assert s.is_test_mode is False, (
        "BUG #2152: protester (kein Flag) wurde als Testkonto geroutet — "
        "Namens-Heuristik statt Profilfeld"
    )
    assert s.smtp_host == PROD_SMTP_HOST, s.smtp_host
    assert s.mail_to == "protester@example.com"


def test_mitarbeiter42_mit_flag_bekommt_test_credentials_ac4(prod_settings):
    """AC-4 GIVEN Profil "mitarbeiter42" mit ``is_test_user: true`` unter der
    konfigurierten Datenwurzel / WHEN ``with_user_profile("mitarbeiter42")`` /
    THEN Stalwart-Test-Credentials, ``is_test_mode`` True."""
    _write_profile(
        "mitarbeiter42",
        {"id": "mitarbeiter42", "mail_to": "m42@example.com", "is_test_user": True},
    )

    s = prod_settings.with_user_profile("mitarbeiter42")

    assert s.is_test_mode is True, (
        "BUG #2152: mitarbeiter42 (is_test_user=true) wurde NICHT als Testkonto "
        "geroutet — das Flag unter der konfigurierten Datenwurzel wird nicht gelesen"
    )
    assert s.smtp_host == TEST_SMTP_HOST, s.smtp_host
    assert s.smtp_user == "gregor-test"


def test_tdd_name_ohne_flag_bekommt_prod_credentials_ac2(prod_settings):
    """AC-2 (zweite Heuristik-Silbe) GIVEN Profil "mattdd" ohne Flag / THEN
    Prod-SMTP — auch der "tdd"-Substring entscheidet nicht mehr."""
    _write_profile("mattdd", {"id": "mattdd", "mail_to": "mattdd@example.com"})

    s = prod_settings.with_user_profile("mattdd")

    assert s.is_test_mode is False
    assert s.smtp_host == PROD_SMTP_HOST


def test_settings_is_test_user_liest_konfigurierte_wurzel(prod_settings):
    """``Settings._is_test_user`` (Wrapper der Weiche ``force_test``) sieht das
    Flag unter der konfigurierten Datenwurzel — ohne Namens-Heuristik."""
    _write_profile("mitarbeiter42", {"id": "mitarbeiter42", "is_test_user": True})
    _write_profile("protester", {"id": "protester"})

    assert Settings._is_test_user("mitarbeiter42") is True
    assert Settings._is_test_user("protester") is False
