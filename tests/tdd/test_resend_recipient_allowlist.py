"""TDD RED — Fix #1219: positive Empfaenger-Allowlist fuer Resend-Versand.

Spec: docs/specs/modules/fix_1219_resend_allowlist.md (AC-1..AC-7)
Analyse: docs/context/fix-1219-resend-allowlist.md

Hintergrund: Der heutige Empfaenger-Guard (`email.py:313`, Issue #1147) ist
eine 2-Adressen-DENYLIST (`TEST_MAILBOXES`) -- jede Adresse, die nicht exakt
`gregor-test@henemm.com`/`gregor-staging@henemm.com` ist, wird ueber Resend
zugestellt, ohne zu pruefen, ob dahinter ein echtes, angelegtes Nutzerkonto
steckt. Dieser Fix ersetzt die Denylist durch eine echte ALLOWLIST: nur
`mail_to`/`email`-Adressen echter (Nicht-Test-)Nutzerprofile unter
`data/users/<id>/user.json` duerfen ueber Resend erreicht werden.

Die zentrale, noch nicht existierende Funktion ist
`_load_resend_allowlist(data_dir="data") -> frozenset[str]` in
`src/output/channels/email.py`. Solange sie fehlt, sind alle Tests, die sie
direkt aufrufen, aus dem RICHTIGEN Grund rot (AttributeError: Modul hat kein
Attribut `_load_resend_allowlist`).

Daten-Isolation (PFLICHT): niemals die echten `data/users/` anfassen.
- Fuer reine Loader-Tests (AC-2/AC-3/AC-5) wird `_load_resend_allowlist`
  direkt mit einem `tmp_path`-`data_dir` aufgerufen -- kein Netzwerk, keine
  Beruehrung des echten Datenbestands.
- Fuer Tests, die den vollen `send()`-Guard-Pfad pruefen (AC-1/AC-3/AC-4/
  AC-6/AC-7), braucht es KEINEN expliziten Isolations-Aufbau mehr: der Guard
  loest sein `data_dir` seit der Adversary-F002-Nachbesserung ueber
  `app.loader.get_data_root()` auf (Prioritaet `_DATA_ROOT` > `GZ_DATA_DIR`
  > Default "data"), NICHT ueber einen direkten `GZ_DATA_DIR`-/CWD-Read.
  Die autouse-Fixture `_isolate_data_root` (Issue #1133, `tests/conftest.py`)
  setzt `_DATA_ROOT` bereits fuer JEDEN Test auf ein frisches, leeres
  `tmp_path_factory`-Verzeichnis -- ein Test ohne eigenes Fixture-Profil
  sieht dort automatisch KEIN Profil. Tests, die ein SPEZIFISCHES
  Fixture-Profil brauchen (z.B. AC-3s voller Sendepfad), schreiben es direkt
  in `app.loader.get_data_root()` (den von der autouse-Fixture bereits
  gesetzten isolierten Pfad) statt in einen eigenen `tmp_path`/`GZ_DATA_DIR`,
  der sonst von `_DATA_ROOT` ignoriert wuerde.

Fuer den ERLAUBT-Fall (AC-2) findet KEIN echter SMTP-Dial statt -- getestet
wird ausschliesslich die Guard-Entscheidung (`_load_resend_allowlist`-
Mitgliedschaft), nicht die tatsaechliche Zustellung. Fuer die BLOCKIERT-Faelle
(AC-1/AC-3/AC-4/AC-6/AC-7) wird -- analog zu
`tests/tdd/test_issue_1147_resend_recipient_invariant.py` -- ein echter
Resend-Host mit bewusst UNGUELTIGEN Zugangsdaten verwendet: greift der Guard
nicht, laeuft `send()` bis zum echten SMTP-Dial und scheitert dort schnell
(~1s) mit `SMTPAuthenticationError` statt der erwarteten `OutputConfigError`
-- deterministisch rot, ohne echten Mailversand oder Resend-Kontingent-
Verbrauch.
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
    """Legt ein Fixture-`user.json` unter `users_root/<user_id>/user.json` an.

    `users_root` ist bewusst als Parameter zu uebergeben (statt hartkodiert)
    -- je nach Testfall ist das entweder `tmp_path / "users"` (fuer direkte
    Loader-Aufrufe mit `data_dir=tmp_path`) oder `tmp_path / "data" / "users"`
    (fuer `send()`-Pfad-Tests nach `monkeypatch.chdir(tmp_path)`, wo der
    Default `data_dir="data"` relativ zum neuen CWD aufgeloest wird).
    """
    profile_dir = users_root / user_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "user.json").write_text(json.dumps(fields), encoding="utf-8")


def _resend_bypass_settings(*, host: str = "smtp.resend.com", mail_to: str = "user@example.com") -> Settings:
    """Resend-Settings, die den #1122-Konstruktor-Validator via model_copy()
    umgehen -- Vorbild: tests/tdd/test_issue_1147_resend_recipient_invariant.py.
    is_test_mode bleibt False, env bleibt "production" (Default)."""
    base = Settings(
        smtp_host="mail.henemm.com",  # unkritischer Platzhalter fuer den __init__-Validator
        smtp_port=587,
        smtp_user="resend",
        smtp_pass="re_1219_test_invalid_key",
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
        output.send("GZ #1219 RED-Test", "Testkoerper", to=to)
    except Exception as exc:  # noqa: BLE001 - Ausgang wird bewusst weitergereicht
        return exc
    return None


# ---------------------------------------------------------------------------
# AC-1: Fremdadresse (kein Nutzerprofil) wird ueber Resend blockiert
# ---------------------------------------------------------------------------


class TestAC1UnknownAddressBlocked:
    def test_resend_send_to_unknown_address_blocked(self):
        """AC-1: GIVEN Resend-Host + Empfaenger, der zu keinem Nutzerprofil
        gehoert / WHEN send() aufgerufen wird / THEN wirft send() eine
        OutputConfigError VOR dem SMTP-Dial.

        Isolation: der Guard loest sein `data_dir` ueber
        `app.loader.get_data_root()` auf, das die autouse-`_DATA_ROOT`-
        Isolation (Issue #1133/#1219 Adversary F002) honoriert -- kein
        expliziter `tmp_path`/`chdir`-Aufbau noetig, es existiert dort
        ohnehin kein Fixture-Profil."""
        output = _make_output()
        exc = _send_and_capture(output, to=["unbekannt@example.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-1 (RED erwartet): send() haette eine OutputConfigError werfen "
            "muessen, BEVOR der SMTP-Dial passiert -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}. Die "
            "Allowlist-Pruefung (_load_resend_allowlist) existiert noch nicht "
            "-- die heutige Denylist laesst jede Nicht-Test-Postfach-Adresse "
            "bis zum echten Dial durch."
        )


# ---------------------------------------------------------------------------
# AC-2: echter mail_to eines angelegten (Nicht-Test-)Nutzerprofils -> erlaubt
# ---------------------------------------------------------------------------


class TestAC2RealUserMailToAllowed:
    def test_allowlist_contains_real_user_mail_to(self, tmp_path):
        """AC-2: GIVEN ein Fixture-Nutzerprofil mit `mail_to` / WHEN
        `_load_resend_allowlist()` gegen dessen `data_dir` aufgerufen wird /
        THEN enthaelt die zurueckgegebene Allowlist die `mail_to`-Adresse --
        die Guard-Entscheidung selbst wird geprueft, kein echter
        Resend-Connect noetig."""
        _write_user_profile(
            tmp_path / "users",
            "henning",
            mail_to="henning@henemm.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "henning@henemm.com" in allowlist, (
            "AC-2: _load_resend_allowlist() liefert das echte mail_to eines "
            "verifizierten Nutzerprofils nicht (Issue #1219 Scheibe 1: "
            "Eignungskriterium ist jetzt email_verified_at)."
        )


# ---------------------------------------------------------------------------
# AC-3: Adresse eines Test-Nutzerprofils bleibt blockiert
# ---------------------------------------------------------------------------


class TestAC3TestUserAddressBlocked:
    def test_allowlist_excludes_test_user_profile(self, tmp_path):
        """AC-3 (Loader-Ebene): GIVEN ein Test-User-Verzeichnis
        (`tdd-1219-fixture`, matcht `is_test_user_id()` per Substring
        "tdd") mit gesetztem `mail_to` / WHEN `_load_resend_allowlist()`
        aufgerufen wird / THEN taucht die Adresse NICHT in der Allowlist
        auf -- obwohl sie formal in einem user.json steht."""
        _write_user_profile(
            tmp_path / "users", "tdd-1219-fixture", mail_to="tdd-1219-fixture@example.com"
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "tdd-1219-fixture@example.com" not in allowlist, (
            "AC-3 (RED erwartet): Test-User-Profile duerfen NICHT in der "
            "Allowlist landen, selbst wenn mail_to gesetzt ist -- "
            "_load_resend_allowlist() existiert noch nicht."
        )

    def test_resend_send_to_test_user_mail_to_blocked(self):
        """AC-3 (voller Sendepfad): GIVEN dasselbe Fixture-Test-Profil,
        diesmal im autouse-isolierten `_DATA_ROOT` (Issue #1133/#1219
        Adversary F002 -- der Guard loest sein `data_dir` ueber
        `app.loader.get_data_root()` auf, NICHT ueber CWD/`GZ_DATA_DIR`
        direkt) / WHEN send() mit exakt dieser Adresse gegen einen
        Resend-Host aufgerufen wird / THEN wirft send() OutputConfigError --
        der Guard blockiert trotz vorhandenem user.json, weil das Profil
        als Test-Nutzer erkannt wird."""
        from app import loader as app_loader

        _write_user_profile(
            app_loader.get_data_root() / "users",
            "tdd-1219-fixture",
            mail_to="tdd-1219-fixture@example.com",
        )
        output = _make_output()
        exc = _send_and_capture(output, to=["tdd-1219-fixture@example.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-3 (RED erwartet): send() haette trotz vorhandenem "
            "Test-User-user.json blockieren muessen -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )

    def test_allowlist_excludes_neutral_named_profile_with_test_user_flag(
        self, tmp_path
    ):
        """F001-Gegentest (Adversary Runde 1, Issue #1219 -- Symmetrie zu
        Go): GIVEN ein NEUTRAL benanntes Nutzerverzeichnis (kein "test"/"tdd"
        im Namen) mit explizitem Profil-Flag `is_test_user: true` / WHEN
        `_load_resend_allowlist()` aufgerufen wird / THEN taucht die Adresse
        NICHT in der Allowlist auf. Python's `is_test_user_id()`
        (config.py:30-50) prueft dieses Flag bereits seit Issue #1013 -- der
        Go-Loader hatte hier vor der F001-Nachbesserung eine Luecke, Python
        war stets korrekt. Dieser Test belegt/schuetzt das."""
        _write_user_profile(
            tmp_path / "users",
            "neutral-profile-name",
            mail_to="neutral@example.com",
            is_test_user=True,
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "neutral@example.com" not in allowlist, (
            "F001-Gegentest: ein Profil mit is_test_user:true darf NICHT in "
            f"der Allowlist landen, selbst bei neutralem Verzeichnisnamen: {allowlist}"
        )

    def test_allowlist_excludes_tg_live_e2e_fixture_id(self, tmp_path):
        """F001b-Gegentest (Adversary Runde 1, Issue #1219 -- Symmetrie zu
        Go): GIVEN die feste Fixture-ID `tg-live-e2e` (kein "test"/"tdd" im
        Namen) mit gesetztem `mail_to` / WHEN `_load_resend_allowlist()`
        aufgerufen wird / THEN taucht die Adresse NICHT in der Allowlist
        auf."""
        _write_user_profile(
            tmp_path / "users", "tg-live-e2e", mail_to="tg-live-e2e@example.com"
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "tg-live-e2e@example.com" not in allowlist, (
            f"F001b-Gegentest: die Fixture-ID tg-live-e2e darf NICHT in der "
            f"Allowlist landen: {allowlist}"
        )


# ---------------------------------------------------------------------------
# AC-4: Stalwart-Host bleibt unberuehrt (Guard greift nur bei Resend)
# ---------------------------------------------------------------------------


class TestAC4StalwartHostGuardBlocksExternal:
    """Issue #1235 (dokumentierte, begründete Verhaltensänderung):

    Dieser Test hieß bis Issue #1235 `TestAC4StalwartHostGuardInactive` und
    behauptete, der Allowlist-Guard duerfe bei einem Stalwart-Host NICHT
    greifen -- das war eine bewusste #1219-Design-Entscheidung, weil damals
    angenommen wurde, ein Stalwart-Versand bleibe lokal und sei damit
    ungefaehrlich. Diese Annahme ist durch henemm-infra#114 widerlegt:
    Stalwart relayt tatsaechlich extern an Resend, wodurch externe
    Fake-Empfaenger (u.a. genau die hier verwendete
    `unbekannt@example.com`-Fixture) an die Aussenwelt geleakt wurden
    (86 Mails/48h, MQ 48151). Issue #1235 fuehrt dafuer einen eigenen,
    strengeren Nicht-Resend-Guard ein (nur lokale @henemm.com-Empfaenger
    erlaubt, kein Allowlist-Bypass) -- der bisherige AC-4-Test wird daher
    invertiert: derselbe externe Empfaenger, der frueher unblockiert durch-
    laufen musste, MUSS jetzt geblockt werden. Spec:
    docs/specs/modules/issue_1235_stalwart_recipient_guard.md AC-5.
    """

    def test_stalwart_host_blocks_external_recipient(self):
        """AC-4 (invertiert, s. Issue #1235): GIVEN ein Stalwart-Host
        (`mail.henemm.com`) mit einer externen, nicht-lokalen Adresse
        ausserhalb jeder Allowlist / WHEN send() aufgerufen wird / THEN
        blockt der NEUE #1235-Lokal-Guard mit OutputConfigError -- der
        Resend-spezifische #1219-Allowlist-Guard bleibt dabei unbeteiligt
        (Fehlermeldung referenziert #1235, nicht 'allowlist')."""
        s = Settings(
            smtp_host="mail.henemm.com",
            smtp_port=587,
            smtp_user="doesnotexist-1219",
            smtp_pass="wrong-password-1219",
            mail_to="unbekannt@example.com",
            mail_from="bot@henemm.com",
            _env_file=None,
        )
        output = EmailOutput(s)
        exc = _send_and_capture(output, to=["unbekannt@example.com"])
        assert isinstance(exc, OutputConfigError), (
            "AC-4 (invertiert, #1235): der neue Lokal-Guard muss bei einem "
            f"Stalwart-Host einen externen Empfänger blocken, bekam: "
            f"{type(exc).__name__}: {exc}"
        )
        assert "allowlist" not in str(exc).lower(), (
            "AC-4 (invertiert, #1235): der Block muss vom neuen "
            "#1235-Lokal-Guard kommen, nicht vom #1219-Resend-Allowlist-"
            f"Guard: {exc}"
        )


# ---------------------------------------------------------------------------
# AC-5: Whitespace-/Casing-Normalisierung zwischen Empfaenger und Allowlist
# ---------------------------------------------------------------------------


class TestAC5NormalizationMatchesAllowlist:
    def test_messy_stored_mail_to_is_normalized_in_allowlist(self, tmp_path):
        """AC-5a: GIVEN ein Fixture-Profil, dessen `mail_to` selbst
        Whitespace/Grossschreibung enthaelt (" Henning@HENEMM.com ") / WHEN
        `_load_resend_allowlist()` aufgerufen wird / THEN enthaelt die
        Allowlist die normalisierte Form `henning@henemm.com`."""
        _write_user_profile(
            tmp_path / "users",
            "henning",
            mail_to=" Henning@HENEMM.com ",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        assert "henning@henemm.com" in allowlist, (
            "AC-5a: _load_resend_allowlist() normalisiert gespeicherte "
            "mail_to-Werte eines verifizierten Profils nicht."
        )

    def test_normalized_recipient_matches_clean_allowlist_entry(self, tmp_path):
        """AC-5b: GIVEN ein Fixture-Profil mit sauberem `mail_to`
        (`henning@henemm.com`) / WHEN ein abweichend geschriebener Empfaenger
        (" Henning@HENEMM.com ") ueber die bestehende Guard-Normalisierung
        (`_normalize_addr_for_guard`, #1147) normalisiert und gegen die
        Allowlist geprueft wird / THEN matcht die normalisierte Form den
        Allowlist-Eintrag -- identische Normalisierungspipeline auf beiden
        Seiten."""
        _write_user_profile(
            tmp_path / "users",
            "henning",
            mail_to="henning@henemm.com",
            email_verified_at="2026-07-10T12:00:00Z",
        )
        allowlist = email_module._load_resend_allowlist(data_dir=str(tmp_path))
        normalized_recipient = email_module._normalize_addr_for_guard(" Henning@HENEMM.com ")
        assert normalized_recipient in allowlist, (
            "AC-5b: der normalisierte Empfaenger matcht nicht gegen die "
            "Allowlist eines verifizierten Profils."
        )


# ---------------------------------------------------------------------------
# AC-6: Blockade-Log ohne Klartext-Empfaengeradresse
# ---------------------------------------------------------------------------


class TestAC6BlockLogNoPlaintextAddress:
    def test_block_is_logged_without_leaking_raw_address(self, caplog):
        """AC-6: GIVEN ein durch die Allowlist abgewiesener Sendeversuch /
        WHEN der Guard blockiert / THEN (a) wirft send() eine
        OutputConfigError, (b) weder die Exception noch ein Log-Eintrag
        enthalten die volle Rohadresse im Klartext, (c) es existiert ein
        Log-Eintrag, der die Blockade dokumentiert."""
        output = _make_output()
        raw_address = "geheime-testadresse@example.com"

        with caplog.at_level("WARNING"):
            exc = _send_and_capture(output, to=[raw_address])

        assert isinstance(exc, OutputConfigError), (
            "AC-6 (RED erwartet): Guard muss OutputConfigError werfen, bevor "
            f"der SMTP-Dial passiert -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )
        assert raw_address not in str(exc), (
            "AC-6: Exception-Text darf die volle Empfaengeradresse nicht im "
            f"Klartext enthalten: {exc}"
        )
        log_text = "\n".join(r.getMessage() for r in caplog.records)
        assert raw_address not in log_text, (
            "AC-6: Log-Ausgabe darf die volle Empfaengeradresse nicht im "
            f"Klartext enthalten: {log_text!r}"
        )
        assert any(
            "blockiert" in r.getMessage().lower() or "blocked" in r.getMessage().lower()
            for r in caplog.records
        ), (
            "AC-6 (RED erwartet): es muss ein Log-Eintrag existieren, der die "
            "Blockade dokumentiert -- der heutige Guard loggt bei Blockade "
            "nichts (nur die Exception-Message)."
        )


# ---------------------------------------------------------------------------
# AC-7: Abgeloeste 2-Adressen-Denylist bleibt via Allowlist blockiert
# ---------------------------------------------------------------------------


class TestAC7LegacyDenylistAddressesStillBlocked:
    @pytest.mark.parametrize("addr", ["gregor-test@henemm.com", "gregor-staging@henemm.com"])
    def test_legacy_test_mailbox_still_blocked_after_allowlist_rewrite(self, addr):
        """AC-7: GIVEN die beiden bisherigen Denylist-Adressen / WHEN send()
        gegen einen Resend-Host mit genau dieser Adresse aufgerufen wird /
        THEN bleibt die Zustellung blockiert -- die Adressen gehoeren zu
        keinem echten Nutzerprofil und tauchen daher auch in der neuen
        Allowlist nicht auf (Regressionsschutz fuer die abgeloeste
        Denylist)."""
        output = _make_output()
        exc = _send_and_capture(output, to=[addr])
        assert isinstance(exc, OutputConfigError), (
            f"AC-7: {addr!r} muss weiterhin blockiert werden (Regressionsschutz "
            f"fuer die abgeloeste Denylist) -- stattdessen: "
            f"{type(exc).__name__ if exc else None}: {exc}."
        )
