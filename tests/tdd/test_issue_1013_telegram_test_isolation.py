"""
Issue #1013 — Telegram-Test-Isolation (Fixture-Guard, Lookup-Vorrang, zentrale
Test-User-Erkennung).

Root Cause: `ensure_test_user_with_active_trip()` schrieb ungeschützt CWD-relativ
in `data/` und der Chat-ID-/E-Mail-Lookup nahm den ersten `iterdir()`-Treffer —
der PO erhielt dadurch Test-Briefings über den Prod-Bot.

KEINE Mocks (Projektregel) — echtes Dateisystem (tmp_path) bzw. echte Settings-
Umgebung (monkeypatch.setenv/delenv).

Spec: docs/specs/modules/issue_1013_telegram_test_isolation.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.tdd._telegram_live_fixture import ensure_test_user_with_active_trip

# AC-6 (#2226): strukturell relativ zu DIESER Testdatei aufgeloest, NICHT
# ueber app.loader/get_data_root() (dessen _DATA_ROOT zeigt zur Testzeit
# selbst auf eine isolierte Wegwerf-Wurzel).
#
# WICHTIG (Adversary-Vorabpruefung, #2226): die untenstehende Zusatzassertion
# gegen _REPO_DATA_USERS_ROOT ist in test_fixture_guard_raises_outside_
# staging_and_creates_no_prod_dir NICHT "strikt staerker" als die bestehende
# tmp_path-Assertion -- sie ist dort zahnlos. Der Test macht
# monkeypatch.chdir(tmp_path); data_dir="data" resolved damit zu
# tmp_path/data, der GZ_ENV-Guard in ensure_test_user_with_active_trip()
# wirft VOR jedem Schreibzugriff. Der echte Baum wird von diesem Test also
# per Konstruktion nie erreicht, egal ob der Guard oder die zugrundeliegende
# Fixture spaeter regressieren -- pytest.raises(RuntimeError) faengt jede
# Guard-Regression zuerst, und eine Fixture-Regression (Schreibzugriff zeigt
# wieder auf den echten Baum statt auf data_dir) bleibt fuer DIESEN Test
# unsichtbar (empirisch mit einer Mutations-Gegenprobe verifiziert: Aufruf-
# Ziel in ensure_test_user_with_active_trip() testweise auf einen
# repo-root-abgeleiteten Pfad umgebogen -- dieser Test blieb gruen, weil er
# wegen des fruehen RuntimeError nie bis zum Schreibzugriff kommt; zwei
# ANDERE Tests in dieser Datei, die den Guard legitim passieren, wurden
# durch dieselbe Mutation rot).
#
# Die Assertion bleibt trotzdem als Verteidigung in der Tiefe stehen (sie
# kostet nichts und deckt ab, falls dieser Test je ohne chdir liefe), aber
# die eigentliche Deckung fuer "ein Schreibzugriff ausserhalb von
# app.loader landet im echten Baum" liefert der session-weite Waechter aus
# AC-5 (tests/tdd/test_data_root_isolation_scopes.py), nicht diese Zeile.
_REPO_DATA_USERS_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


def _write_user(data_dir: Path, user_id: str, chat_id: str = "", mail_to: str = "") -> None:
    user_dir = data_dir / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    profile = {"id": user_id, "telegram_chat_id": chat_id, "mail_to": mail_to}
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1: Fixture-Guard verhindert Prod-Schreibzugriff außerhalb Staging
# ---------------------------------------------------------------------------


def test_fixture_guard_raises_outside_staging_and_creates_no_prod_dir(tmp_path, monkeypatch):
    """GIVEN GZ_ENV != staging (z.B. Prod)
    WHEN ensure_test_user_with_active_trip(chat_id, data_dir="data") aufgerufen wird
    THEN wirft die Fixture RuntimeError und legt KEIN data/users/tg-live-e2e/ an."""
    monkeypatch.setenv("GZ_ENV", "production")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError):
        ensure_test_user_with_active_trip(chat_id="123456", data_dir="data")

    assert not (tmp_path / "data" / "users" / "tg-live-e2e").exists()
    # AC-6 (#2226): Verteidigung in der Tiefe -- dieser Test erreicht den
    # echten Baum wegen monkeypatch.chdir(tmp_path) + fruehem Guard-Raise
    # per Konstruktion nie (s. Moduldocstring oben). Die eigentliche
    # Deckung fuer CWD-relative/hartkodierte Schreibzugriffe in den echten
    # Baum liefert der session-weite Waechter aus AC-5.
    assert not (_REPO_DATA_USERS_ROOT / "tg-live-e2e").exists(), (
        f"Fixture-Guard hat trotz RuntimeError eine Spur unter dem ECHTEN "
        f"{_REPO_DATA_USERS_ROOT} hinterlassen."
    )


def test_fixture_guard_allows_explicit_tmp_path(tmp_path, monkeypatch):
    """GIVEN GZ_ENV != staging
    WHEN die Fixture mit explizitem data_dir=tmp_path aufgerufen wird
    THEN läuft sie unverändert durch (Guard betrifft nur data_dir="data")."""
    monkeypatch.setenv("GZ_ENV", "production")

    user_id = ensure_test_user_with_active_trip(chat_id="123456", data_dir=str(tmp_path))

    assert user_id == "tg-live-e2e"
    assert (tmp_path / "users" / "tg-live-e2e" / "user.json").exists()


# ---------------------------------------------------------------------------
# AC-2: Fixture bleibt in Staging erlaubt (kein Regress)
# ---------------------------------------------------------------------------


def test_fixture_allowed_in_staging_creates_test_user(tmp_path, monkeypatch):
    """GIVEN GZ_ENV=staging
    WHEN die Fixture mit data_dir="data" läuft
    THEN legt sie den Test-User wie bisher an (telegram_chat_id gesetzt)."""
    monkeypatch.setenv("GZ_ENV", "staging")
    monkeypatch.chdir(tmp_path)

    user_id = ensure_test_user_with_active_trip(chat_id="654321", data_dir="data")

    assert user_id == "tg-live-e2e"
    user_file = tmp_path / "data" / "users" / "tg-live-e2e" / "user.json"
    assert user_file.exists()
    profile = json.loads(user_file.read_text(encoding="utf-8"))
    assert profile["telegram_chat_id"] == "654321"


# ---------------------------------------------------------------------------
# AC-3: Lookup bevorzugt echten User vor Test-User bei Kollision
# ---------------------------------------------------------------------------


def test_lookup_by_telegram_chat_id_prefers_real_user_over_test_user(tmp_path):
    """GIVEN echter User (henning) und mehrere Test-User mit identischer chat_id
    WHEN lookup_user_by_telegram_chat_id(chat_id) aufgerufen wird
    THEN wird deterministisch die echte User-ID zurückgegeben."""
    from app.loader import lookup_user_by_telegram_chat_id

    chat_id = "999888"
    _write_user(tmp_path, "tg-live-e2e", chat_id=chat_id)
    _write_user(tmp_path, "test_aaa", chat_id=chat_id)
    _write_user(tmp_path, "tdd-zzz", chat_id=chat_id)
    _write_user(tmp_path, "henning", chat_id=chat_id)

    result = lookup_user_by_telegram_chat_id(chat_id, data_dir=str(tmp_path))

    assert result == "henning"


def test_lookup_by_email_prefers_real_user_over_test_user(tmp_path):
    """GIVEN echter User (henning) und mehrere Test-User mit identischer mail_to
    WHEN lookup_user_by_email(email) aufgerufen wird
    THEN wird deterministisch die echte User-ID zurückgegeben."""
    from app.loader import lookup_user_by_email

    email = "henning@henemm.com"
    _write_user(tmp_path, "tg-live-e2e", mail_to=email)
    _write_user(tmp_path, "test_aaa", mail_to=email)
    _write_user(tmp_path, "tdd-zzz", mail_to=email)
    _write_user(tmp_path, "henning", mail_to=email)

    result = lookup_user_by_email(email, data_dir=str(tmp_path))

    assert result == "henning"


# ---------------------------------------------------------------------------
# AC-4: Zentrales Test-User-Prädikat
# ---------------------------------------------------------------------------


def test_central_test_user_predicate_classifies_known_ids_correctly():
    """GIVEN test_xyz, tdd-123, tg-live-e2e sowie henning, steffi, admin, default
    WHEN das zentrale Prädikat is_test_user_id() angewendet wird
    THEN klassifiziert es Test-User als True und echte User als False."""
    from app.config import is_test_user_id

    assert is_test_user_id("test_xyz") is True
    assert is_test_user_id("tdd-123") is True
    assert is_test_user_id("tg-live-e2e") is True
    assert is_test_user_id("henning") is False
    assert is_test_user_id("steffi") is False
    assert is_test_user_id("admin") is False
    assert is_test_user_id("default") is False


def test_central_test_user_predicate_is_case_insensitive_for_fixture_id():
    """Adversary-Finding F002 (Issue #1265 Fix-Loop 1): der Fixed-ID-Zweig
    verglich vor dem Fix gegen die UN-lowercased Originalvariable — eine
    Groß-Schreibvariante der Fixture-ID (TG-LIVE-E2E) wurde fälschlich als
    echter User behandelt. GIVEN die Groß-Schreibvariante WHEN
    is_test_user_id() prüft THEN True — wie die Kleinschreibung."""
    from app.config import is_test_user_id

    assert is_test_user_id("TG-LIVE-E2E") is True
    assert is_test_user_id("Tg-Live-E2e") is True


def test_is_test_user_delegates_to_central_predicate():
    """GIVEN dieselben User-IDs (inkl. design_tdd)
    WHEN Settings()._is_test_user(uid) und is_test_user_id(uid) verglichen werden
    THEN liefern beide identische Ergebnisse (Delegation, keine Logik-Duplizierung)."""
    from app.config import Settings, is_test_user_id

    settings = Settings()
    ids = [
        "test_xyz", "tdd-123", "tg-live-e2e",
        "henning", "steffi", "admin", "default", "design_tdd",
    ]

    for uid in ids:
        assert settings._is_test_user(uid) == is_test_user_id(uid), uid


# ---------------------------------------------------------------------------
# Adversary-Fix F001: Fixture-Guard darf nicht per Pfad-Schreibweise umgangen werden
# ---------------------------------------------------------------------------


def test_fixture_guard_not_bypassed_by_path_spelling(tmp_path, monkeypatch):
    """GIVEN GZ_ENV != staging
    WHEN ensure_test_user_with_active_trip() mit "./data", "data/" oder dem
        absoluten CWD-data-Pfad aufgerufen wird
    THEN wirft die Fixture jeweils RuntimeError und legt KEIN Verzeichnis an
        (String-Vergleich "data_dir == 'data'" würde diese Schreibweisen durchlassen)."""
    monkeypatch.setenv("GZ_ENV", "production")
    monkeypatch.chdir(tmp_path)

    variants = ["./data", "data/", str(tmp_path / "data")]
    for variant in variants:
        with pytest.raises(RuntimeError):
            ensure_test_user_with_active_trip(chat_id="123456", data_dir=variant)
        assert not (tmp_path / "data" / "users" / "tg-live-e2e").exists(), variant


# ---------------------------------------------------------------------------
# Adversary-Fix F002: Profil-Flag is_test_user gewinnt gegen neutralen Namen
# ---------------------------------------------------------------------------


def test_lookup_prefers_real_user_over_profile_flagged_test_user(tmp_path):
    """GIVEN ein Test-User mit neutralem Namen ("e2e-fixture-runner") aber
        is_test_user=True im Profil, und ein echter User (henning) mit
        identischer chat_id
    WHEN lookup_user_by_telegram_chat_id(chat_id) aufgerufen wird
    THEN wird die echte User-ID (henning) zurückgegeben — die Namens-Heuristik
        allein würde "e2e-fixture-runner" fälschlich als real einstufen."""
    from app.loader import lookup_user_by_telegram_chat_id

    chat_id = "777666"
    user_dir = tmp_path / "users" / "e2e-fixture-runner"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(
        json.dumps({
            "id": "e2e-fixture-runner",
            "telegram_chat_id": chat_id,
            "mail_to": "",
            "is_test_user": True,
        }),
        encoding="utf-8",
    )
    _write_user(tmp_path, "henning", chat_id=chat_id)

    result = lookup_user_by_telegram_chat_id(chat_id, data_dir=str(tmp_path))

    assert result == "henning"
