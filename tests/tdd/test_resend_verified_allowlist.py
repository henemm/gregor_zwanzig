"""TDD RED — Fix #1219 Scheibe 1: Resend-Allowlist auf E-Mail-Verifikation
umstellen.

Spec: docs/specs/modules/fix_1219_email_verify.md (AC-1..AC-4, AC-7 Python-Teil)

Hintergrund: Die heutige #1219-Allowlist (live) entscheidet "echtes
Nutzerprofil, das ueber Resend erreicht werden darf?" allein anhand der
Namens-Heuristik `is_test_user_id()` (Substring "test"/"tdd" im Konto-Namen).
Ein Konto mit neutralem Namen wie `e2e-758` entkommt dieser Heuristik -- die
zugehoerige Adresse `e2e-758@example.com` gilt heute faelschlich als "echt"
und wird ueber Resend zugestellt (der urspruengliche Bug-Fall).

Dieser Fix ersetzt die Namens-Heuristik als Eignungskriterium durch das neue,
explizite Profilfeld `email_verified_at`: nur Profile mit gesetztem
Verifikations-Zeitstempel sind allowlist-faehig. Zusaetzlich werden
RFC-2606-reservierte Test-Domains (example.com/.net/.org, .test, .invalid,
.localhost, .example) als dauerhaftes Sicherheitsnetz IMMER geblockt --
unabhaengig vom Verifikationsstatus.

Solange `_load_resend_allowlist()` weiterhin `is_test_user_id()` statt
`profile.get("email_verified_at")` prueft und `_is_reserved_test_domain()`
noch nicht existiert, sind AC-1/AC-2/AC-4 aus dem RICHTIGEN Grund rot:
- AC-1/AC-2: `e2e-758` enthaelt kein "test"/"tdd" -> `is_test_user_id()`
  liefert False -> das Profil landet trotz fehlendem `email_verified_at`
  in der Allowlist (Bug reproduziert).
- AC-4: ein verifiziertes Profil mit reservierter Domain wird von der
  heutigen Logik NICHT zusaetzlich geblockt (keine Domain-Pruefung vorhanden).
AC-3 (Regressionsschutz) darf bereits gruen sein: ein Profil ohne "test"/
"tdd" im Namen landet nach heutiger Logik ohnehin in der Allowlist.

Daten-Isolation (PFLICHT): niemals die echten `data/users/` anfassen.
- Reine Loader-Tests rufen `_load_resend_allowlist()` direkt mit einem
  `tmp_path`-`data_dir` auf -- kein Netzwerk, keine Beruehrung des echten
  Datenbestands.
- Guard-Level-Tests (voller `send()`-Pfad) nutzen den autouse-isolierten
  `_DATA_ROOT` (Issue #1133, `tests/conftest.py`), den der Guard ueber
  `app.loader.get_data_root()` aufloest (Prioritaet `_DATA_ROOT` >
  `GZ_DATA_DIR` > Default "data").

Fuer die BLOCKIERT-Faelle wird -- analog zu
`tests/tdd/test_resend_recipient_allowlist.py` -- ein echter Resend-Host mit
bewusst UNGUELTIGEN Zugangsdaten verwendet: greift der Guard nicht, laeuft
`send()` bis zum echten SMTP-Dial und scheitert dort mit
`SMTPAuthenticationError` statt der erwarteten `OutputConfigError` --
deterministisch rot, ohne echten Mailversand oder Resend-Kontingent-Verbrauch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from output.channels import email as email_module  # noqa: E402
from output.channels.base import OutputConfigError  # noqa: E402
from output.channels.email import EmailOutput  # noqa: E402


def _write_user_profile(users_root: Path, user_id: str, **fields) -> None:
    """Legt ein Fixture-`user.json` unter `users_root/<user_id>/user.json` an."""
    profile_dir = users_root / user_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "user.json").write_text(json.dumps(fields), encoding="utf-8")


def _resend_bypass_settings(*, host: str = "smtp.resend.com", mail_to: str = "user@example.com") -> Settings:
    """Resend-Settings, die den #1122-Konstruktor-Validator via model_copy()
    umgehen -- Vorbild: tests/tdd/test_resend_recipient_allowlist.py.
    is_test_mode bleibt False, env bleibt "production" (Default)."""
    base = Settings(
        smtp_host="mail.henemm.com",  # unkritischer Platzhalter fuer den __init__-Validator
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_1219_verify_test_invalid_key",
        mail_to=mail_to,
        mail_from="bot@henemm.com",
        _env_file=None,
    )
    return base.model_copy(update={"smtp_host": host, "is_test_mode": False})


def _make_output(*, host: str = "smtp.resend.com") -> EmailOutput:
    s = _resend_bypass_settings(host=host)
    assert "resend" in (s.smtp_host or "").lower(), (
        "Testaufbau defekt: Settings muss einen Resend-Host halten"
    )
    assert s.is_test_mode is False, (
        "Testaufbau defekt: is_test_mode muss False sein (kein Prozess-Test-Signal)"
    )
    return EmailOutput(s)


def _send_and_capture(output: EmailOutput, to: list[str]) -> Exception | None:
    try:
        output.send("GZ #1219 Scheibe-1 RED-Test", "Testkoerper", to=to)
    except Exception as exc:  # noqa: BLE001 - Ausgang wird bewusst weitergereicht
        return exc
    return None


# ---------------------------------------------------------------------------
# AC-1: neutral benanntes Profil OHNE email_verified_at wird blockiert
# (der urspruengliche Bug-Fall: e2e-758@example.com)
# ---------------------------------------------------------------------------


class TestAC1UnverifiedNeutralProfileBlocked:
    def test_loader_excludes_unverified_profile_without_verified_at(self, tmp_path):
        """AC-1 (Loader-Ebene): GIVEN ein Fixture-Profil `e2e-758` (Name
        OHNE "test"/"tdd", entkommt also der alten Namens-Heuristik) mit
        `mail_to=e2e-758@example.com` und KEINEM gesetzten
        `email_verified_at` / WHEN `_load_resend_allowlist()` aufgerufen
        wird / THEN taucht die Adresse NICHT in der Allowlist auf."""
        _write_user_profile(
            tmp_path / "users", "e2e-758", mail_to="e2e-758@example.com"
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "e2e-758@example.com" not in allowlist, (
            "AC-1 (RED erwartet): _load_resend_allowlist() prueft noch die "
            "alte Namens-Heuristik (is_test_user_id) statt "
            "email_verified_at -- ein neutral benanntes, unverifiziertes "
            f"Profil landet faelschlich in der Allowlist: {allowlist}"
        )

    def test_resend_send_to_unverified_neutral_profile_blocked(self):
        """AC-1 (voller Sendepfad): GIVEN dasselbe Fixture-Profil im
        autouse-isolierten `_DATA_ROOT` / WHEN send() gegen einen
        Resend-Host mit exakt dieser Adresse aufgerufen wird / THEN wirft
        send() eine OutputConfigError VOR dem SMTP-Dial."""
        from app import loader as app_loader

        _write_user_profile(
            app_loader.get_data_root() / "users",
            "e2e-758",
            mail_to="e2e-758@example.com",
        )
        output = _make_output()
        exc = _send_and_capture(output, to=["e2e-758@example.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-1 (RED erwartet): send() haette blockieren muessen, weil "
            "das Profil kein email_verified_at hat -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )


# ---------------------------------------------------------------------------
# AC-2: dasselbe unverifizierte Profil mit NICHT reservierter Domain wird
# ALLEIN wegen fehlendem email_verified_at blockiert (isoliert vom
# reservierten-Domain-Kriterium)
# ---------------------------------------------------------------------------


class TestAC2UnverifiedNonReservedDomainBlocked:
    def test_loader_excludes_unverified_profile_with_real_domain(self, tmp_path):
        """AC-2 (Loader-Ebene): GIVEN ein Fixture-Profil mit
        `mail_to=e2e-758@gmail.com` (nicht reservierte Domain) und KEINEM
        gesetzten `email_verified_at` / WHEN `_load_resend_allowlist()`
        aufgerufen wird / THEN taucht die Adresse NICHT in der Allowlist
        auf -- der Ausschluss darf ausschliesslich am fehlenden
        email_verified_at liegen, nicht an der Domain."""
        _write_user_profile(
            tmp_path / "users", "e2e-758-gmail", mail_to="e2e-758@gmail.com"
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "e2e-758@gmail.com" not in allowlist, (
            "AC-2 (RED erwartet): ein unverifiziertes Profil mit "
            "NICHT-reservierter Domain muss trotzdem ausgeschlossen bleiben "
            f"-- allein wegen fehlendem email_verified_at: {allowlist}"
        )

    def test_resend_send_to_unverified_real_domain_blocked(self):
        """AC-2 (voller Sendepfad): GIVEN dasselbe unverifizierte Profil mit
        nicht reservierter Domain / WHEN send() gegen einen Resend-Host
        aufgerufen wird / THEN wirft send() eine OutputConfigError."""
        from app import loader as app_loader

        _write_user_profile(
            app_loader.get_data_root() / "users",
            "e2e-758-gmail",
            mail_to="e2e-758@gmail.com",
        )
        output = _make_output()
        exc = _send_and_capture(output, to=["e2e-758@gmail.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-2 (RED erwartet): send() haette blockieren muessen (kein "
            "email_verified_at, unabhaengig von der Domain) -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )


# ---------------------------------------------------------------------------
# AC-3 (Regressionsschutz): verifiziertes Profil mit echter Domain bleibt
# erlaubt -- darf bereits GRUEN sein (heutige Logik laesst ein Nicht-Test-
# benanntes Profil ohnehin durch)
# ---------------------------------------------------------------------------


class TestAC3VerifiedRealDomainAllowed:
    def test_loader_includes_verified_profile_with_real_domain(self, tmp_path):
        """AC-3 (Loader-Ebene, Regressionsschutz): GIVEN ein Fixture-Profil
        mit gesetztem `email_verified_at` und `mail_to=real@gmail.com`
        (echte, nicht reservierte Domain) / WHEN `_load_resend_allowlist()`
        aufgerufen wird / THEN IST die Adresse in der Allowlist -- Vorbild
        fuer henning/steffi nach der Migration."""
        _write_user_profile(
            tmp_path / "users",
            "real-user",
            mail_to="real@gmail.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "real@gmail.com" in allowlist, (
            "AC-3: ein verifiziertes Profil mit echter Domain muss in der "
            f"Allowlist landen: {allowlist}"
        )

    def test_resend_send_to_verified_real_domain_allowed(self):
        """AC-3 (voller Sendepfad, Regressionsschutz): GIVEN dasselbe
        verifizierte Profil / WHEN send() gegen einen Resend-Host mit
        exakt dieser Adresse aufgerufen wird / THEN wirft send() KEINE
        Allowlist-Guard-OutputConfigError (der Aufruf darf bis zum echten
        SMTP-Dial durchlaufen und dort mit ungueltigen Zugangsdaten
        scheitern -- das beweist, dass der Guard NICHT blockiert hat)."""
        from app import loader as app_loader

        _write_user_profile(
            app_loader.get_data_root() / "users",
            "real-user",
            mail_to="real@gmail.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        output = _make_output()
        exc = _send_and_capture(output, to=["real@gmail.com"])
        assert not (
            isinstance(exc, OutputConfigError) and "allowlist" in str(exc).lower()
        ), (
            "AC-3: ein verifiziertes Profil mit echter Domain darf NICHT "
            f"durch den Allowlist-Guard blockiert werden -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )


# ---------------------------------------------------------------------------
# AC-4: verifiziertes Profil mit RESERVIERTER Test-Domain wird IMMER
# blockiert, unabhaengig vom Verifikationsstatus
# ---------------------------------------------------------------------------


class TestAC4ReservedDomainAlwaysBlocked:
    def test_reserved_test_domain_helper_missing_or_detects_example_com(self):
        """AC-4 (Helper-Ebene): `_is_reserved_test_domain()` existiert noch
        nicht -- der Test schlaegt mit AttributeError fehl, solange die
        Funktion fehlt. Sobald sie existiert, muss sie `example.com`
        erkennen."""
        assert email_module._is_reserved_test_domain("foo@example.com") is True

    @pytest.mark.parametrize(
        "idx,addr",
        [
            (0, "foo@example.com"),
            (1, "foo@example.net"),
            (2, "foo@example.org"),
            (3, "foo@x.test"),
            (4, "foo@x.invalid"),
            (5, "foo@x.localhost"),
            (6, "foo@x.example"),
        ],
    )
    def test_loader_excludes_verified_profile_on_reserved_domain(self, tmp_path, idx, addr):
        """AC-4 (Loader-Ebene): GIVEN ein Fixture-Profil mit gesetztem
        `email_verified_at`, dessen `mail_to` aber auf einer reservierten
        Test-Domain liegt / WHEN `_load_resend_allowlist()` aufgerufen wird
        / THEN taucht die Adresse NICHT in der Allowlist auf -- die
        Verifikation allein genuegt nicht, wenn die Domain reserviert ist.

        Verzeichnisname bewusst OHNE die Silbe "test"/"tdd" (rein
        durchnummeriert, `idx`-basiert) -- sonst wuerde die ALTE
        Namens-Heuristik (`is_test_user_id`) den Fall aus dem FALSCHEN
        Grund ausschliessen (z.B. bei `addr="foo@x.test"" waere ein
        Verzeichnisname wie "reserved-x-test" selbst schon ein
        Namens-Treffer) und den Test faelschlich gruen machen, bevor die
        eigentliche Domain-Pruefung ueberhaupt existiert."""
        _write_user_profile(
            tmp_path / "users",
            f"reserved-domain-fixture-{idx}",
            mail_to=addr,
            email_verified_at="2026-07-10T12:00:00Z",
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert addr not in allowlist, (
            f"AC-4 (RED erwartet): reservierte Test-Domain {addr!r} darf "
            f"trotz gesetztem email_verified_at nicht in der Allowlist "
            f"landen: {allowlist}"
        )

    def test_resend_send_to_verified_reserved_domain_blocked(self):
        """AC-4 (voller Sendepfad): GIVEN ein verifiziertes Profil mit
        `mail_to=foo@example.com` / WHEN send() gegen einen Resend-Host mit
        exakt dieser Adresse aufgerufen wird / THEN wirft send() eine
        OutputConfigError -- der reservierte-Domain-Guard blockiert
        UNABHAENGIG vom Verifikationsstatus."""
        from app import loader as app_loader

        _write_user_profile(
            app_loader.get_data_root() / "users",
            "reserved-example-com",
            mail_to="foo@example.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        output = _make_output()
        exc = _send_and_capture(output, to=["foo@example.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-4 (RED erwartet): send() haette trotz gesetztem "
            "email_verified_at blockieren muessen, weil die Domain "
            f"reserviert ist -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )


# ---------------------------------------------------------------------------
# AC-7 (Python-Seite): Verdikt-Konsistenz der drei Kernfaelle -- reine
# Dokumentation der erwarteten Guard-Ergebnisse innerhalb von Python
# (Go-Vergleich folgt erst in Phase 6/Go-Testfaltung, hier nur die
# Python-Haelfte der drei Faelle als Tabelle).
# ---------------------------------------------------------------------------


class TestAC7PythonVerdictsForThreeCoreCases:
    @pytest.mark.parametrize(
        "mail_to,verified_at,expect_allowed",
        [
            ("case-unverified@example.com", None, False),  # unverifiziert
            ("case-real@gmail.com", "2026-07-10T12:00:00Z", True),  # verifiziert + echte Domain
            ("case-reserved@example.com", "2026-07-10T12:00:00Z", False),  # verifiziert + reservierte Domain
        ],
    )
    def test_loader_verdict_matrix(self, tmp_path, mail_to, verified_at, expect_allowed):
        """AC-7 (Python-Haelfte): die drei Kernfaelle aus AC-1/AC-3/AC-4
        muessen konsistent im Loader landen -- Grundlage fuer den spaeteren
        Go/Python-Verdikt-Vergleich."""
        fields = {"mail_to": mail_to}
        if verified_at:
            fields["email_verified_at"] = verified_at
        _write_user_profile(
            tmp_path / "users", f"case-{abs(hash(mail_to)) % 10000}", **fields
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        is_allowed = mail_to in allowlist
        assert is_allowed == expect_allowed, (
            f"AC-7: Verdikt fuer {mail_to!r} (verified_at={verified_at!r}) "
            f"sollte allowed={expect_allowed} sein, war aber {is_allowed} "
            f"(Allowlist: {allowlist})"
        )


# ---------------------------------------------------------------------------
# Adversary Runde 1 -- F001: kaputtes (nicht-Objekt) user.json darf den
# Allowlist-Loader NICHT crashen (fail-soft), gueltige Profile bleiben
# geladen.
# ---------------------------------------------------------------------------


class TestF001BrokenNonObjectProfileIsFailSoft:
    @pytest.mark.parametrize("broken_content", ["[]", "null"])
    def test_loader_skips_non_object_profile_without_crash(self, tmp_path, broken_content):
        """F001: GIVEN ein user.json mit gueltigem JSON, das aber kein
        Objekt ist (`[]`/`null`) / WHEN _load_resend_allowlist() aufgerufen
        wird / THEN wird das kaputte Profil still uebersprungen (kein
        AttributeError), ein daneben liegendes gueltiges, verifiziertes
        Profil wird trotzdem geladen."""
        users_root = tmp_path / "users"
        broken_dir = users_root / "broken-profile"
        broken_dir.mkdir(parents=True, exist_ok=True)
        (broken_dir / "user.json").write_text(broken_content, encoding="utf-8")
        _write_user_profile(
            users_root,
            "healthy-profile",
            mail_to="healthy@gmail.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )

        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))

        assert "healthy@gmail.com" in allowlist, (
            f"F001: ein kaputtes Profil ({broken_content!r}) darf das "
            f"Laden anderer gueltiger Profile nicht verhindern: {allowlist}"
        )


# ---------------------------------------------------------------------------
# Adversary Runde 1 -- F002: Reserved-Domain-Bypass ueber Bare-TLD ohne
# Subdomain-Label und Trailing-Dot-FQDN.
# ---------------------------------------------------------------------------


class TestF002ReservedDomainBypassEdgeCases:
    @pytest.mark.parametrize(
        "addr",
        [
            "user@localhost",
            "user@test",
            "user@invalid",
            "user@example",
            "user@example.com.",
        ],
    )
    def test_reserved_domain_edge_cases_detected(self, addr):
        """F002: Bare-TLDs ohne Subdomain-Label und ein Trailing-Dot-FQDN
        muessen als reserviert erkannt werden."""
        assert email_module._is_reserved_test_domain(addr) is True, (
            f"F002: {addr!r} haette als reservierte Test-Domain erkannt "
            "werden muessen"
        )

    @pytest.mark.parametrize("addr", ["x@mytest.de", "x@example.company"])
    def test_legitimate_domains_not_falsely_blocked(self, addr):
        """F002-Gegentest: legitime Domains, die eine reservierte TLD nur
        als Substring enthalten, duerfen NICHT faelschlich gesperrt werden."""
        assert email_module._is_reserved_test_domain(addr) is False, (
            f"F002: {addr!r} ist eine legitime Domain und darf nicht als "
            "reserviert erkannt werden"
        )
