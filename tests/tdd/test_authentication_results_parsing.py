"""TDD RED — Authentication-Results-Header-Parsing (#2143, AC-5).

`parse_authentication_results()` und `InboundEmailReader._spf_dkim_pass()`
existieren noch nicht — der Import schlaegt fehl (Modul-Ebene, bewusst: ALLE
Tests dieser Datei haengen an derselben neuen Funktion, ein Collection-Error
ist hier ein eindeutiges RED-Artefakt statt einer Ueberraschung pro Test).

Vertrag (RED-Phase legt ihn fest, #50-implement baut GEGEN diese Signatur):

    def parse_authentication_results(header_value: str) -> tuple[str | None, dict[str, str]]:
        '''RFC-8601: liefert (authserv-id, {method: result, ...}).'''

Nur der ERSTE Authentication-Results-Header zaehlt (Stalwart prependt) —
das ist Aufgabe von `InboundEmailReader._spf_dkim_pass(msg, expected_authserv_id)`,
NICHT des reinen Parsers: der Parser bekommt bereits einen einzelnen
Header-Wert (String) uebergeben, `_spf_dkim_pass` ist dafuer verantwortlich,
`msg.get(...)` (nicht `get_all(...)`) zu benutzen.

SPEC: docs/specs/modules/inbound_command_channels.md v1.5, §5, AC-5.
"""
from __future__ import annotations

import email

from services.inbound_email_reader import (  # RED: existiert noch nicht
    InboundEmailReader,
    parse_authentication_results,
)
from tests.fixtures.authentication_results_fixtures import (
    AR_FAIL,
    AR_FOREIGN_AUTHSERV,
    AR_PASS,
    AR_SPF_DMARC_ALIGNMENT,
    AR_SPF_ONLY,
    TEST_AUTHSERV_ID,
)


class TestParseAuthenticationResults:
    """Reines Parsing: authserv-id + method=result-Paare aus dem Header-Wert."""

    def test_extracts_authserv_id_and_pass_results(self):
        authserv_id, results = parse_authentication_results(AR_PASS)
        assert authserv_id == TEST_AUTHSERV_ID
        assert results.get("spf") == "pass"
        assert results.get("dkim") == "pass"
        assert results.get("dmarc") == "pass"

    def test_extracts_fail_results(self):
        authserv_id, results = parse_authentication_results(AR_FAIL)
        assert authserv_id == TEST_AUTHSERV_ID
        assert results.get("spf") == "fail"
        assert results.get("dkim") == "fail"

    def test_foreign_authserv_id_is_returned_verbatim(self):
        """Der Parser selbst bewertet authserv-id nicht — nur Extraktion."""
        authserv_id, results = parse_authentication_results(AR_FOREIGN_AUTHSERV)
        assert authserv_id == "mx.example-other-provider.net"
        assert results.get("spf") == "pass"


def _msg_with_auth_headers(*header_values: str) -> email.message.Message:
    """Baut eine Message mit N Authentication-Results-Headern IN DIESER Reihenfolge."""
    lines = ["From: sender@example.com", "To: recipient@example.com", "Subject: [Trip] status"]
    for value in header_values:
        lines.append(f"Authentication-Results: {value}")
    lines.append("")
    lines.append("status")
    raw = "\r\n".join(lines).encode("utf-8")
    return email.message_from_bytes(raw)


class TestSpfDkimPass:
    """`_spf_dkim_pass()`: nur der ERSTE Authentication-Results-Header zaehlt (AC-5)."""

    def setup_method(self):
        self.reader = InboundEmailReader()

    def test_pass_with_matching_authserv_id_is_accepted(self):
        msg = _msg_with_auth_headers(AR_PASS)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is True

    def test_fail_is_rejected(self):
        msg = _msg_with_auth_headers(AR_FAIL)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is False

    def test_missing_header_is_rejected(self):
        msg = _msg_with_auth_headers()
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is False

    def test_foreign_authserv_id_is_rejected_even_if_pass(self):
        msg = _msg_with_auth_headers(AR_FOREIGN_AUTHSERV)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is False

    def test_spf_pass_without_dkim_or_dmarc_alignment_is_rejected(self):
        msg = _msg_with_auth_headers(AR_SPF_ONLY)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is False

    def test_dmarc_pass_counts_as_dkim_alignment_substitute(self):
        msg = _msg_with_auth_headers(AR_SPF_DMARC_ALIGNMENT)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is True

    def test_second_forged_header_is_ignored_ac5(self):
        """AC-5 Adversary: Stalwart prependt — erster Header (fail) zaehlt,
        ein zweiter, vom Angreifer angehaengter Header mit pass wird NICHT
        ausgewertet."""
        msg = _msg_with_auth_headers(AR_FAIL, AR_PASS)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID) is False, (
            "#2143 AC-5: zweiter gefaelschter Authentication-Results-Header "
            "mit pass wurde ausgewertet statt ignoriert (msg.get() statt "
            "get_all() erwartet)"
        )

    def test_none_expected_authserv_id_rejects_even_with_empty_authserv_header(self):
        """F002 (Adversary #2143): expected_authserv_id=None darf NICHT
        stillschweigend die authserv-id-Pruefung uebergehen -- ein Header mit
        leerem authserv-id-Segment wuerde sonst None == None matchen."""
        msg = _msg_with_auth_headers("; spf=pass; dkim=pass")
        assert self.reader._spf_dkim_pass(msg, None) is False
