"""Authentication-Results-Auswertung: Parser, Tokenizer und Annahmeregel.

Historie: #2143 (AC-5, erster Header zaehlt) — seit #2252 (SECURITY-FIX,
Spec ``docs/specs/modules/inbound_command_channels.md`` v1.7, Abschnitt 5a,
AC-8..AC-13, AC-16) gehaertet.

TESTVERTRAG fuer /50-implement (#2252, in TDD-RED festgelegt):

* ``InboundEmailReader._spf_dkim_pass(msg, expected_authserv_id, from_domain) -> bool``
  — dritter Parameter NEU: Domain der Adresse, ueber die der Nutzer gefunden
  wurde. Annahme nach Spec 5a Variante V3: (a) genau ein ``dmarc``-Segment,
  ``pass``, ``header.from == from_domain``; ODER (b) genau ein spf-Segment mit
  ``smtp.mailfrom``, ``pass``, Domain von ``smtp.mailfrom`` gleich/Subdomain von
  ``from_domain``; ODER (c) irgendein ``dkim=pass`` mit ``header.d``
  gleich/Subdomain von ``from_domain``. Quote-Sperre (irgendein ``"`` im ersten
  Header ⇒ False), Parse-Fehler ⇒ False, leere ``from_domain`` ⇒ False.
* ``InboundEmailReader._single_from_address(msg) -> bool`` (AC-14, siehe
  ``test_inbound_email_sender_authentication.py``).
* ``parse_authentication_results_segments(header_value)
  -> tuple[str | None, list[Segment]] | None`` (``None`` = Parse-Fehler).
  ``Segment`` hat ``.method``, ``.result`` (lowercase) und
  ``.props: dict[str, str]`` (Schluessel ``ptype.property`` lowercase, Wert
  ganz, Trennung am ERSTEN ``=``, quoted-string-Wert ohne umschliessende
  Quotes, Escapes aufgeloest). Kommentare werden vor dem Lesen entfernt.
  BEWUSST NICHT auf Modulebene importiert (sonst Collection-Error und die
  Regressionswachen dieser Datei laufen nicht) — Import in ``_segments()``.
* ``parse_authentication_results(header_value)`` bleibt Wrapper mit dem
  bisherigen Rueckgabetyp (AC-16): widerspruechliche Ergebnisse einer Methode
  ⇒ KEIN Eintrag (nie "das letzte gewinnt"), eindeutige wie bisher,
  Parse-Fehler ⇒ ``(None, {})``.

Messages werden als Raw-Bytes mit den woertlichen Faltungen gebaut (wie IMAP
sie liefert), nie ueber ``msg[...] = ...``. Keine Mocks.

Restrisiko (Adversary F005): ein UNGEQUOTETES ``;`` in einem Wert wie
``smtp.helo`` waere RFC-8601-konform ein neues Segment und wird bewusst nicht
abgefangen; der Schutz haengt an Stalwart, das ein EHLO mit ``;``/``"``/``(``
mit 550 ablehnt (Spec 5a, empirisch belegt).

Zusaetzlich prueft ``TestAuthorizeAppliesRules`` dieselben Angriffe ueber die
unveraenderte Signatur ``_authorize(sender, settings, msg)`` — dort scheitern
sie vor dem Fix per AssertionError (nicht nur per TypeError), und
``TestAuthorizeRegressionGuards`` haelt H1/H4/AC-5/None-authserv heute schon
gruen.
"""
from __future__ import annotations

import email

import pytest

from app.config import Settings
from services.inbound_email_reader import (
    InboundEmailReader,
    parse_authentication_results,
)
from tests.fixtures.authentication_results_fixtures import (
    AR_DKIM_CONTRADICTORY_FAIL_FIRST,
    AR_DKIM_CONTRADICTORY_PASS_FIRST,
    AR_DKIM_PASS_NO_D,
    AR_DKIM_TWICE_SAME,
    AR_DMARC_PASS_NO_FROM,
    AR_DUPLICATE_MAILFROM_ALIGNED_FIRST,
    AR_DUPLICATE_MAILFROM_FOREIGN_FIRST,
    AR_FAIL,
    AR_FOREIGN_AUTHSERV,
    AR_FOREIGN_DOMAIN_ALIGNED,
    AR_H1_NORMAL,
    AR_H1_SPF_SWAPPED,
    AR_H2_INJECTION,
    AR_H2B_ALIGNED_INJECTION,
    AR_H3_ESCAPED_QUOTE,
    AR_H4_RESEND,
    AR_HARMLESS_QUOTE_IN_COMMENT,
    AR_MAILFROM_FAIL_HELO_PASS,
    AR_MAILFROM_LAST_AT_ALIGNED,
    AR_MAILFROM_LAST_AT_FOREIGN,
    AR_ONLY_UNALIGNED_DKIM,
    AR_PARENT_DOMAIN_ONLY,
    AR_PASS,
    AR_SEMICOLON_IN_COMMENT,
    AR_SPF_DMARC_ALIGNMENT,
    AR_SPF_ONLY,
    AR_SPF_PASS_EMPTY_MAILFROM,
    AR_SPF_PASS_NO_SCOPE,
    AR_SUBDOMAIN_ALIGNED,
    AR_SUFFIX_LOOKALIKE,
    AR_TWO_DMARC,
    AR_TWO_MAILFROM_BOTH_PASS,
    AR_UNBALANCED_PAREN,
    AR_UNBALANCED_QUOTE,
    AR_UNCLOSED_PAREN,
    H1_SEGMENT_COUNT,
    H2B_INJECTED_MAILFROM,
    H2_INJECTED_MAILFROM,
    H2_SEGMENT_COUNT,
    H3_INJECTED_MAILFROM,
    H3_SEGMENT_COUNT,
    H4_SEGMENT_COUNT,
    PROD_AUTHSERV_ID,
    TEST_AUTHSERV_ID,
)

PARSE_ERROR_HEADERS = [
    pytest.param(AR_UNBALANCED_QUOTE, id="unbalancierte-quote"),
    pytest.param(AR_UNBALANCED_PAREN, id="ueberzaehlige-klammer"),
    pytest.param(AR_UNCLOSED_PAREN, id="offene-klammer"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_msg(*auth_values: str, from_lines: tuple[str, ...] = ("From: user@henemm.com",)) -> email.message.Message:
    """Raw-Bytes wie IMAP sie liefert: Header-Werte inkl. woertlicher
    ``\\r\\n\\t``-Faltungen, N Authentication-Results-Header in DIESER Reihenfolge."""
    lines = list(from_lines) + ["To: cmd@henemm.com", "Subject: [Trip] status"]
    for value in auth_values:
        lines.append(f"Authentication-Results: {value}")
    lines.append("")
    lines.append("status")
    return email.message_from_bytes("\r\n".join(lines).encode("utf-8"))


def _segments(header_value: str):
    # Import bewusst HIER (siehe Modul-Docstring): vor dem Fix ImportError
    # nur in den Tests, die die neue Funktion brauchen.
    from services.inbound_email_reader import parse_authentication_results_segments

    return parse_authentication_results_segments(header_value)


def _by_method(segments, method: str) -> list:
    return [s for s in segments if s.method == method]


# ---------------------------------------------------------------------------
# Wrapper parse_authentication_results (bestehend + AC-16)
# ---------------------------------------------------------------------------

class TestParseAuthenticationResults:
    """Wrapper: authserv-id + {method: result} — Rueckgabetyp unveraendert."""

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

    def test_ac16_same_result_in_several_segments_is_kept(self):
        """AC-16: mehrere Segmente GLEICHEN Ergebnisses ⇒ dieses Ergebnis."""
        _, results = parse_authentication_results(AR_DKIM_TWICE_SAME)
        assert results.get("dkim") == "pass"
        assert results.get("spf") == "pass"

    @pytest.mark.parametrize("header", [
        pytest.param(AR_DKIM_CONTRADICTORY_PASS_FIRST, id="pass-dann-fail"),
        pytest.param(AR_DKIM_CONTRADICTORY_FAIL_FIRST, id="fail-dann-pass"),
    ])
    def test_ac16_contradictory_results_yield_no_entry(self, header):
        """AC-16: widerspruechliche Ergebnisse einer Methode ⇒ KEIN Eintrag,
        weder "letztes gewinnt" noch "erstes gewinnt"; eindeutige Methoden
        bleiben erhalten."""
        authserv_id, results = parse_authentication_results(header)
        assert authserv_id == TEST_AUTHSERV_ID
        assert "dkim" not in results, (
            f"#2252 AC-16: widerspruechliches dkim lieferte {results.get('dkim')!r}"
        )
        assert results.get("spf") == "pass"

    def test_ac16_h1_contradictory_spf_has_no_entry(self):
        """H1 traegt spf=permerror (helo) UND spf=pass (mailfrom) — der Wrapper
        trifft keine Annahme-Entscheidung, ``spf`` fehlt; dmarc bleibt."""
        authserv_id, results = parse_authentication_results(AR_H1_NORMAL)
        assert authserv_id == PROD_AUTHSERV_ID
        assert "spf" not in results, f"#2252 AC-16: spf={results.get('spf')!r}"
        assert results.get("dmarc") == "pass"
        assert results.get("iprev") == "pass"

    def test_wrapper_h2_has_no_injected_dkim(self):
        """H2: das im quoted-string eingeschleuste ``dkim=pass`` ist kein Segment."""
        _, results = parse_authentication_results(AR_H2_INJECTION)
        assert "dkim" not in results, f"#2252: eingeschleustes dkim={results.get('dkim')!r}"
        assert results.get("dmarc") == "fail"

    @pytest.mark.parametrize("header", PARSE_ERROR_HEADERS)
    def test_ac16_parse_error_returns_none_and_empty(self, header):
        assert parse_authentication_results(header) == (None, {}), (
            "#2252 AC-16: Parse-Fehler muss (None, {}) liefern"
        )


# ---------------------------------------------------------------------------
# Segment-Funktion / Tokenizer (AC-8, AC-9, Mutationsfestigkeit H1–H4)
# ---------------------------------------------------------------------------

class TestSegmentTokenizer:

    def test_h1_segments(self):
        parsed = _segments(AR_H1_NORMAL)
        assert parsed is not None
        authserv_id, segs = parsed
        assert authserv_id == PROD_AUTHSERV_ID
        assert len(segs) == H1_SEGMENT_COUNT
        assert [s.method for s in segs] == ["spf", "spf", "iprev", "dmarc"]
        helo, mailfrom = _by_method(segs, "spf")
        assert helo.result == "permerror"
        assert helo.props == {"smtp.helo": "[127.0.1.1]"}
        assert mailfrom.result == "pass"
        # Kommentar entfernt: nur die echte Property bleibt.
        assert mailfrom.props == {"smtp.mailfrom": "probe2252-b5877b3d@henemm.com"}
        (dmarc,) = _by_method(segs, "dmarc")
        assert dmarc.result == "pass"
        assert dmarc.props.get("header.from") == "henemm.com"
        assert dmarc.props.get("policy.dmarc") == "quarantine"

    @pytest.mark.parametrize("header,count,injected", [
        pytest.param(AR_H2_INJECTION, H2_SEGMENT_COUNT, H2_INJECTED_MAILFROM, id="H2"),
        pytest.param(AR_H3_ESCAPED_QUOTE, H3_SEGMENT_COUNT, H3_INJECTED_MAILFROM, id="H3"),
        pytest.param(AR_H2B_ALIGNED_INJECTION, H2_SEGMENT_COUNT, H2B_INJECTED_MAILFROM, id="H2b"),
    ])
    def test_injection_stays_inside_quoted_string(self, header, count, injected):
        """H2/H3: ``;`` im quoted-string trennt NICHT; das eingeschleuste
        ``dkim=pass``/``spf=pass`` ist KEIN eigenes Segment; ``smtp.mailfrom``
        des spf=none-Segments ist der GANZE quoted-string-Inhalt (Escapes
        aufgeloest)."""
        parsed = _segments(header)
        assert parsed is not None
        authserv_id, segs = parsed
        assert authserv_id == PROD_AUTHSERV_ID
        assert len(segs) == count, [(s.method, s.result) for s in segs]
        assert not _by_method(segs, "dkim"), "#2252: eingeschleustes dkim=pass wurde Segment"
        spf = _by_method(segs, "spf")
        assert [s.result for s in spf] == ["permerror", "none"]
        assert spf[1].props.get("smtp.mailfrom") == injected
        assert all(s.result != "pass" for s in spf)

    def test_h4_segments(self):
        parsed = _segments(AR_H4_RESEND)
        assert parsed is not None
        _, segs = parsed
        assert len(segs) == H4_SEGMENT_COUNT
        dkims = _by_method(segs, "dkim")
        assert [d.props.get("header.d") for d in dkims] == ["henemm.com", "amazonses.com"]
        assert dkims[0].props.get("header.b") == "a7IkBGaV"
        assert dkims[0].props.get("header.s") == "resend"
        spf = _by_method(segs, "spf")
        assert [s.result for s in spf] == ["none", "pass"]
        assert spf[1].props.get("smtp.mailfrom", "").endswith("@send.henemm.com")

    def test_ac9_semicolon_in_comment_and_equals_in_value(self):
        """AC-9: ``;`` im Kommentar trennt nicht; ``header.b=M/C96LSA==`` bleibt
        ganz (Trennung am ERSTEN ``=``)."""
        parsed = _segments(AR_SEMICOLON_IN_COMMENT)
        assert parsed is not None
        _, segs = parsed
        assert [s.method for s in segs] == ["spf", "dkim", "dmarc"]
        (spf,) = _by_method(segs, "spf")
        assert spf.result == "pass"
        assert spf.props == {"smtp.mailfrom": "u@henemm.com"}
        (dkim,) = _by_method(segs, "dkim")
        assert dkim.props.get("header.b") == "M/C96LSA=="

    def test_method_result_and_property_names_lowercase(self):
        parsed = _segments(f"{TEST_AUTHSERV_ID}; SPF=PASS SMTP.MailFrom=u@henemm.com")
        assert parsed is not None
        _, segs = parsed
        assert len(segs) == 1
        assert segs[0].method == "spf"
        assert segs[0].result == "pass"
        assert "smtp.mailfrom" in segs[0].props

    def test_segment_without_method_result_is_ignored(self):
        parsed = _segments(f"{TEST_AUTHSERV_ID}; none")
        assert parsed is not None
        authserv_id, segs = parsed
        assert authserv_id == TEST_AUTHSERV_ID
        assert segs == []

    @pytest.mark.parametrize("header", PARSE_ERROR_HEADERS)
    def test_ac8_unbalanced_is_parse_error(self, header):
        assert _segments(header) is None, "#2252 AC-8: unbalanciert muss Parse-Fehler (None) sein"


# ---------------------------------------------------------------------------
# _spf_dkim_pass(msg, authserv_id, from_domain) — Regeln (3-Parameter-Vertrag)
# ---------------------------------------------------------------------------

class TestSpfDkimPass:
    """Nur der ERSTE Authentication-Results-Header zaehlt (AC-5); Annahme nach
    Spec 5a V3 mit Domain-Ausrichtung zu ``from_domain``."""

    def setup_method(self):
        self.reader = InboundEmailReader()

    def _check(self, header, from_domain="henemm.com", authserv=TEST_AUTHSERV_ID):
        return self.reader._spf_dkim_pass(_raw_msg(header), authserv, from_domain)

    # --- bestehende Faelle (#2143), auf from_domain="henemm.com" angepasst ---

    def test_pass_with_matching_authserv_id_is_accepted(self):
        assert self._check(AR_PASS) is True

    def test_fail_is_rejected(self):
        assert self._check(AR_FAIL) is False

    def test_missing_header_is_rejected(self):
        msg = _raw_msg()
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID, "henemm.com") is False

    def test_foreign_authserv_id_is_rejected_even_if_pass(self):
        assert self._check(AR_FOREIGN_AUTHSERV) is False

    def test_spf_pass_aligned_mailfrom_alone_is_accepted_v3(self):
        """Vormals ``test_spf_pass_without_dkim_or_dmarc_alignment_is_rejected``:
        unter Spec 5a Variante V3, Regel (b) genuegt ein ausgerichtetes
        ``spf=pass`` (smtp.mailfrom @henemm.com) zur From-Domain henemm.com."""
        assert self._check(AR_SPF_ONLY, from_domain="henemm.com") is True

    def test_spf_pass_alone_for_foreign_from_domain_is_rejected(self):
        """Gegenstueck: derselbe Header, aber From-Domain ``opfer.example`` ⇒
        nichts ist ausgerichtet ⇒ abgelehnt."""
        assert self._check(AR_SPF_ONLY, from_domain="opfer.example") is False

    def test_dmarc_pass_counts_as_dkim_alignment_substitute(self):
        assert self._check(AR_SPF_DMARC_ALIGNMENT) is True

    def test_second_forged_header_is_ignored_ac5(self):
        msg = _raw_msg(AR_FAIL, AR_PASS)
        assert self.reader._spf_dkim_pass(msg, TEST_AUTHSERV_ID, "henemm.com") is False, (
            "#2143 AC-5: zweiter gefaelschter Header wurde ausgewertet"
        )

    def test_none_expected_authserv_id_rejects_even_with_empty_authserv_header(self):
        """F002 (#2143), unveraendert: leere authserv-id darf nicht None == None matchen."""
        msg = _raw_msg("; spf=pass; dkim=pass")
        assert self.reader._spf_dkim_pass(msg, None, "henemm.com") is False

    def test_none_expected_authserv_id_rejects_aligned_header(self):
        """Wie oben, aber der Header waere sonst ausgerichtet gueltig — nur die
        None-Pruefung lehnt ab (Mutationsfestigkeit)."""
        msg = _raw_msg("; spf=pass smtp.mailfrom=u@henemm.com; dmarc=pass header.from=henemm.com")
        assert self.reader._spf_dkim_pass(msg, None, "henemm.com") is False

    def test_empty_from_domain_is_rejected(self):
        assert self._check(AR_PASS, from_domain="") is False

    def test_header_domain_case_and_trailing_dot_are_normalised(self):
        header = (f"{TEST_AUTHSERV_ID}; spf=fail smtp.mailfrom=u@henemm.com; "
                  "dkim=none header.d=henemm.com; dmarc=pass header.from=HenEmm.Com.")
        assert self._check(header) is True

    # --- AC-10 SPF-Scope ---

    def test_ac10_h1_is_accepted(self):
        assert self._check(AR_H1_NORMAL, authserv=PROD_AUTHSERV_ID) is True

    def test_ac10_h1_with_swapped_spf_segments_is_accepted(self):
        assert self._check(AR_H1_SPF_SWAPPED, authserv=PROD_AUTHSERV_ID) is True

    def test_ac10_mailfrom_fail_with_helo_pass_is_rejected(self):
        assert self._check(AR_MAILFROM_FAIL_HELO_PASS) is False

    # --- AC-7 Injektion ---

    @pytest.mark.parametrize("header", [
        pytest.param(AR_H2_INJECTION, id="H2"),
        pytest.param(AR_H3_ESCAPED_QUOTE, id="H3"),
    ])
    def test_ac7_injection_is_rejected(self, header):
        assert self._check(header, authserv=PROD_AUTHSERV_ID) is False

    # --- AC-8 Quote-Sperre / Parse-Fehler ---

    @pytest.mark.parametrize("header", PARSE_ERROR_HEADERS + [
        pytest.param(AR_HARMLESS_QUOTE_IN_COMMENT, id="harmloses-quote-im-kommentar"),
    ])
    def test_ac8_quote_or_unbalanced_is_rejected(self, header):
        assert self._check(header) is False

    # --- AC-9 ---

    def test_ac9_semicolon_in_comment_keeps_mailfrom_aligned(self):
        """Nur spf (Regel b) ist ausgerichtet; Annahme haengt allein an der
        korrekten Kommentar-Behandlung."""
        assert self._check(AR_SEMICOLON_IN_COMMENT) is True

    # --- AC-11 Mehrdeutigkeit / fehlender Scope ---

    @pytest.mark.parametrize("header", [
        pytest.param(AR_TWO_MAILFROM_BOTH_PASS, id="zwei-mailfrom"),
        pytest.param(AR_SPF_PASS_NO_SCOPE, id="spf-ohne-scope"),
        pytest.param(AR_DKIM_PASS_NO_D, id="dkim-ohne-d"),
        pytest.param(AR_DMARC_PASS_NO_FROM, id="dmarc-ohne-from"),
        pytest.param(AR_TWO_DMARC, id="zwei-dmarc"),
    ])
    def test_ac11_ambiguous_or_scopeless_does_not_count(self, header):
        assert self._check(header) is False

    def test_ac11_valid_authserv_spf_pass_without_scope_is_rejected(self):
        """AC-11 eigener Fall: gueltige authserv-id, ``spf=pass`` ohne Scope,
        sonst gar nichts."""
        assert self._check(f"{TEST_AUTHSERV_ID}; spf=pass") is False

    # --- AC-12 Domain-Ausrichtung ---

    def test_ac12_foreign_domain_aligned_is_rejected(self):
        assert self._check(AR_FOREIGN_DOMAIN_ALIGNED, from_domain="opfer.example") is False

    def test_ac12_parent_domain_does_not_cover_subdomain_from(self):
        assert self._check(AR_PARENT_DOMAIN_ONLY, from_domain="sub.opfer.example") is False

    def test_ac12_suffix_lookalike_is_not_a_subdomain(self):
        assert self._check(AR_SUFFIX_LOOKALIKE, from_domain="opfer.example") is False

    def test_subdomain_of_from_domain_is_aligned(self):
        assert self._check(AR_SUBDOMAIN_ALIGNED, from_domain="opfer.example") is True

    # --- AC-13 ---

    def test_ac13_h4_resend_is_accepted(self):
        assert self._check(AR_H4_RESEND, authserv=PROD_AUTHSERV_ID) is True

    def test_ac13_only_unaligned_dkim_is_rejected(self):
        assert self._check(AR_ONLY_UNALIGNED_DKIM) is False

    # --- Adversary-Nachtrag F001..F004 ---

    def test_f001_aligned_injection_is_rejected(self):
        """H2b: eingeschleuste Nutzlast ist zu henemm.com ausgerichtet — nur
        Quote-Sperre/Quote-Handling verhindern hier die Annahme."""
        assert self._check(AR_H2B_ALIGNED_INJECTION, authserv=PROD_AUTHSERV_ID) is False

    @pytest.mark.parametrize("header", [
        pytest.param(AR_DUPLICATE_MAILFROM_ALIGNED_FIRST, id="ausgerichtet-zuerst"),
        pytest.param(AR_DUPLICATE_MAILFROM_FOREIGN_FIRST, id="fremd-zuerst"),
    ])
    def test_f002_duplicate_property_makes_header_unreadable(self, header):
        assert _segments(header) is None, "F002: doppelter Schluessel muss Parse-Fehler sein"
        assert self._check(header) is False

    def test_f003_empty_from_domain_with_empty_mailfrom_is_rejected(self):
        """Leere from_domain + leerer smtp.mailfrom: ohne die Leer-Pruefung
        waere "" zu "" ausgerichtet."""
        assert self._check(AR_SPF_PASS_EMPTY_MAILFROM, from_domain="") is False

    def test_f004_mailfrom_domain_after_last_at_is_aligned(self):
        assert self._check(AR_MAILFROM_LAST_AT_ALIGNED) is True

    def test_f004_mailfrom_domain_after_last_at_is_foreign(self):
        assert self._check(AR_MAILFROM_LAST_AT_FOREIGN) is False


# ---------------------------------------------------------------------------
# Dieselben Regeln ueber die UNVERAENDERTE Signatur _authorize(sender, settings, msg)
# ---------------------------------------------------------------------------

def _settings(mail_to: str, authserv: str | None) -> Settings:
    # mail_from explizit != Absender (Loop-Guard), unabhaengig von einer lokalen .env.
    return Settings(
        mail_to=mail_to,
        mail_from="system@example.invalid",
        email_verified_at="2026-01-01T00:00:00Z",
        mail_server_hostname=authserv,
    )


def _authorize(sender: str, header_values: tuple[str, ...], authserv: str | None) -> bool:
    msg = _raw_msg(*header_values, from_lines=(f"From: {sender}",))
    return InboundEmailReader()._authorize(sender, _settings(sender, authserv), msg)


class TestAuthorizeAppliesRules:
    """Angriffe/Grenzfaelle ueber ``_authorize`` — vor dem Fix AssertionError."""

    @pytest.mark.parametrize("sender,header,authserv", [
        pytest.param("nutzer@henemm.com", AR_H2_INJECTION, PROD_AUTHSERV_ID, id="AC7-H2"),
        pytest.param("nutzer@henemm.com", AR_H3_ESCAPED_QUOTE, PROD_AUTHSERV_ID, id="AC7-H3"),
        pytest.param("nutzer@henemm.com", AR_H2B_ALIGNED_INJECTION, PROD_AUTHSERV_ID, id="F001-H2b"),
        pytest.param("nutzer@henemm.com", AR_DUPLICATE_MAILFROM_ALIGNED_FIRST, TEST_AUTHSERV_ID,
                     id="F002-doppelter-schluessel"),
        pytest.param("nutzer@henemm.com", AR_HARMLESS_QUOTE_IN_COMMENT, TEST_AUTHSERV_ID, id="AC8-quote-kommentar"),
        pytest.param("nutzer@henemm.com", AR_UNBALANCED_QUOTE, TEST_AUTHSERV_ID, id="AC8-quote-offen"),
        pytest.param("nutzer@henemm.com", AR_UNBALANCED_PAREN, TEST_AUTHSERV_ID, id="AC8-klammer-zu"),
        pytest.param("nutzer@henemm.com", AR_UNCLOSED_PAREN, TEST_AUTHSERV_ID, id="AC8-klammer-offen"),
        pytest.param("nutzer@henemm.com", AR_MAILFROM_FAIL_HELO_PASS, TEST_AUTHSERV_ID, id="AC10-helo-pass"),
        pytest.param("nutzer@henemm.com", AR_TWO_MAILFROM_BOTH_PASS, TEST_AUTHSERV_ID, id="AC11-zwei-mailfrom"),
        pytest.param("nutzer@henemm.com", AR_SPF_PASS_NO_SCOPE, TEST_AUTHSERV_ID, id="AC11-ohne-scope"),
        pytest.param("nutzer@henemm.com", AR_DKIM_PASS_NO_D, TEST_AUTHSERV_ID, id="AC11-dkim-ohne-d"),
        pytest.param("nutzer@henemm.com", AR_DMARC_PASS_NO_FROM, TEST_AUTHSERV_ID, id="AC11-dmarc-ohne-from"),
        pytest.param("nutzer@henemm.com", AR_TWO_DMARC, TEST_AUTHSERV_ID, id="AC11-zwei-dmarc"),
        pytest.param("x@opfer.example", AR_FOREIGN_DOMAIN_ALIGNED, TEST_AUTHSERV_ID, id="AC12-luecke2"),
        pytest.param("x@sub.opfer.example", AR_PARENT_DOMAIN_ONLY, TEST_AUTHSERV_ID, id="AC12-gegenrichtung"),
        pytest.param("x@opfer.example", AR_SUFFIX_LOOKALIKE, TEST_AUTHSERV_ID, id="AC12-suffix-falle"),
        pytest.param("nutzer@henemm.com", AR_ONLY_UNALIGNED_DKIM, TEST_AUTHSERV_ID, id="AC13-nur-amazonses"),
    ])
    def test_rejected(self, sender, header, authserv):
        assert _authorize(sender, (header,), authserv) is False, (
            f"#2252: Header wurde fuer {sender!r} akzeptiert"
        )

    def test_ac10_h1_swapped_spf_is_accepted(self):
        assert _authorize("nutzer@henemm.com", (AR_H1_SPF_SWAPPED,), PROD_AUTHSERV_ID) is True

    def test_ac9_semicolon_in_comment_is_accepted(self):
        assert _authorize("u@henemm.com", (AR_SEMICOLON_IN_COMMENT,), TEST_AUTHSERV_ID) is True

    def test_spf_only_aligned_is_accepted_v3(self):
        assert _authorize("nutzer@henemm.com", (AR_SPF_ONLY,), TEST_AUTHSERV_ID) is True

    def test_f004_mailfrom_domain_after_last_at_is_accepted(self):
        assert _authorize("nutzer@henemm.com", (AR_MAILFROM_LAST_AT_ALIGNED,), TEST_AUTHSERV_ID) is True


class TestAuthorizeRegressionGuards:
    """Heute schon GRUEN und nach dem Fix weiter gruen (Regressionswache)."""

    def test_h1_is_accepted(self):
        assert _authorize("nutzer@henemm.com", (AR_H1_NORMAL,), PROD_AUTHSERV_ID) is True

    def test_h4_resend_is_accepted(self):
        assert _authorize("gregor_zwanzig@henemm.com", (AR_H4_RESEND,), PROD_AUTHSERV_ID) is True

    def test_ac5_second_forged_header_is_ignored(self):
        assert _authorize("nutzer@henemm.com", (AR_FAIL, AR_PASS), TEST_AUTHSERV_ID) is False

    def test_none_authserv_rejects_aligned_header(self):
        header = "; spf=pass smtp.mailfrom=u@henemm.com; dmarc=pass header.from=henemm.com"
        assert _authorize("nutzer@henemm.com", (header,), None) is False

    def test_subdomain_aligned_is_accepted(self):
        assert _authorize("x@opfer.example", (AR_SUBDOMAIN_ALIGNED,), TEST_AUTHSERV_ID) is True

    def test_ar_pass_is_accepted(self):
        assert _authorize("nutzer@henemm.com", (AR_PASS,), TEST_AUTHSERV_ID) is True
