package mail

import (
	"strings"
	"testing"
)

// TDD GREEN — Issue #1219 Scheibe 2a-i: Versand des E-Mail-Bestätigungslinks.
// Spec: docs/specs/modules/fix_1219_verify_flow_2a.md (AC-3, AC-4, AC-5).
//
// Co-located Ersatz für den temporären externen RED-Test
// (internal/mail/tests/verify_send_red_test.go) — siehe Spec "Source".

func verifySendTestMail() Mail {
	return Mail{
		Subject:   "Bestätige deine E-Mail-Adresse für Gregor 20",
		PlainBody: "verify",
		HTMLBody:  "<p>verify</p>",
	}
}

// AC-3: eine reservierte RFC-2606-Test-Domain wird VOR jedem SMTP-Connect
// abgewiesen, unabhängig von der (hier bewusst nicht relevanten) Allowlist.
func TestSendVerificationMail_ReservedTestDomainBlocked(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_dummy", From: "gregor_zwanzig@henemm.com"}
	for _, domain := range []string{"example.com", "foo.test", "foo.invalid", "foo.localhost", "foo.example"} {
		err := SendVerificationMail(cfg, "attacker@"+domain, verifySendTestMail())
		if err == nil {
			t.Errorf("AC-3: reservierte Domain %q muss VOR jedem SMTP-Connect abgelehnt werden", domain)
		}
	}
}

// AC-5: mehr als ein Empfänger (Komma oder Semikolon) wird abgewiesen —
// genau eine Adresse liefert nil.
func TestRecipientBlockedForVerification_SingleRecipientOnly(t *testing.T) {
	host := "smtp.resend.com"
	if err := recipientBlockedForVerification(host, "a@x.de,b@x.de"); err == nil {
		t.Error("AC-5: Komma-getrennte Mehrfach-Empfänger müssen abgelehnt werden")
	}
	if err := recipientBlockedForVerification(host, "a@x.de; b@x.de"); err == nil {
		t.Error("AC-5: Semikolon-getrennte Mehrfach-Empfänger müssen abgelehnt werden")
	}
	if err := recipientBlockedForVerification(host, "a@x.de"); err != nil {
		t.Errorf("AC-5: genau ein Empfänger muss erlaubt sein, war: %v", err)
	}
}

// AC-4: das rohe Test-Postfach-Literal (auch plus-adressiert) wird vom
// Fangnetz geblockt — der Sonderpfad hat kein eigenes Fangnetz, sondern
// nutzt rawContainsTestMailbox unverändert.
func TestRecipientBlockedForVerification_TestMailboxFangnetz(t *testing.T) {
	host := "smtp.resend.com"
	if err := recipientBlockedForVerification(host, "gregor-test+x@henemm.com"); err == nil {
		t.Error("AC-4: gregor-test+x@henemm.com muss vom Fangnetz geblockt werden")
	}
}

// AC-4: SendVerificationMail unter go test gegen einen Resend-Host ist
// unabhängig vom Empfänger gesperrt — resendBlocked (#1122) greift genauso
// wie beim Hauptpfad.
func TestSendVerificationMail_ResendBlockedUnderGoTest(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_dummy", From: "gregor_zwanzig@henemm.com"}
	err := SendVerificationMail(cfg, "neu@henemm.com", verifySendTestMail())
	if err == nil {
		t.Fatal("AC-4: SendVerificationMail muss unter go test gegen einen Resend-Host gesperrt sein (#1122)")
	}
	if !strings.Contains(err.Error(), "1122") {
		t.Errorf("AC-4: Fehler muss Issue #1122 nennen, war: %v", err)
	}
}

// Sanity: kein Allowlist-Aufruf im Sonderpfad — eine gültige, NICHT
// registrierte Adresse mit Nicht-Resend-Host darf recipientBlockedForVerification
// passieren (der Guard prüft ausschließlich Fangnetz/Ein-Empfänger/Reserved-Domain).
func TestRecipientBlockedForVerification_NoAllowlistLookup(t *testing.T) {
	if err := recipientBlockedForVerification("smtp.example-relay.internal", "brand-new@henemm.com"); err != nil {
		t.Errorf("recipientBlockedForVerification darf keine Allowlist prüfen, war Fehler: %v", err)
	}
}

// Adversary Fix-Loop F001, Runde 1 (#1219): der alte
// len(splitRecipientField(to))==1-Check ließ Roh-`to`-Strings mit einem
// versteckten zweiten "@"-Token durch, solange sie Whitespace-getrennt
// waren (splitRecipientField's ParseAddress-Fallback via strings.Fields) —
// der UNBEREINIGTE Roh-`to` (inkl. Garbage-Präfix/-Suffix, Steuerzeichen)
// ging dabei unverändert an dialAndSend/smtp.SendMail.
//
// Fix-Loop F001, Runde 2: die Steuerzeichen-Blacklist + splitRecipientField-
// basierte Prüfung war Symptom-Ebene. recipientBlockedForVerification nutzt
// jetzt ECHTES Parsen (mail.ParseAddress + Unicode-Whitespace-Scan +
// Adress-Gleichheits-Check) — dieser Test deckt beide Runden ab. Reiner
// Rand-Whitespace bleibt weiterhin erlaubt (Trim-Toleranz), eine einzelne
// syntaktisch gültige Adresse mit ungewöhnlichem Local-Part ebenfalls
// (Semantik-Klarstellung Runde 2: kein Leck, genau EIN Empfänger).
func TestRecipientBlockedForVerification_F001_RawGarbageBlocked(t *testing.T) {
	host := "smtp.resend.com"
	blocked := []string{
		"not-an-email\na@x.de",
		"a@x.de\nnot-an-email",
		"not-an-email\ta@x.de",
		"a@x.de\rnot-an-email",
		"prefix-garbage a@x.de",
		"a@x.de suffix-garbage",
		"<script>a@x.de</script>",
		`"X" <a@x.de>`,
		"<a@x.de>",
		"a@x.de" + " " + "b@y.de", // Unicode-Zeilentrenner statt Leerzeichen
		"a" + " " + "@x.de",       // NBSP statt Leerzeichen
	}
	for _, to := range blocked {
		if err := recipientBlockedForVerification(host, to); err == nil {
			t.Errorf("F001: %q muss blockiert werden", to)
		}
	}

	allowed := []string{
		" a@x.de ",
		"a@x.de",
		"garbage-prefix-a@x.de", // gültige Einzeladresse mit ungewöhnlichem Local-Part — kein Leck
	}
	for _, to := range allowed {
		if err := recipientBlockedForVerification(host, to); err != nil {
			t.Errorf("F001: %q muss weiterhin erlaubt sein (genau eine saubere Adresse), war: %v", to, err)
		}
	}
}

// Adversary Fix-Loop F001b (#1219): der Zeichen-Scan aus Runde 2
// (unicode.IsControl || unicode.IsSpace) erfasst NICHT die Kategorie Cf
// ("Format") — unsichtbare Zeichen wie ZWSP U+200B, ZWNJ/ZWJ U+200C/U+200D,
// BOM U+FEFF, Word-Joiner U+2060, Soft-Hyphen U+00AD. mail.ParseAddress
// akzeptiert sie klaglos als atext, sodass ein unsichtbar getrennter
// Garbage-Präfix (z.B. "not-an-email" + ZWSP + "a@x.de") die Ein-Empfänger-
// Prüfung umgangen hätte. Explizite Rune-Escapes statt Copy-Paste der
// unsichtbaren Zeichen, damit der Test selbst lesbar bleibt.
func TestRecipientBlockedForVerification_F001b_InvisibleFormatCharsBlocked(t *testing.T) {
	host := "smtp.resend.com"
	blocked := []string{
		"not-an-email" + "\u200b" + "a@x.de", // ZWSP
		"a" + "\ufeff" + "@x.de",             // BOM
		"a" + "\u00ad" + "@x.de",             // Soft-Hyphen
		"a" + "\u2060" + "@x.de",             // Word-Joiner
		"a" + "\u200c" + "@x.de",             // ZWNJ
		"a" + "\u200d" + "@x.de",             // ZWJ
	}
	for _, to := range blocked {
		if err := recipientBlockedForVerification(host, to); err == nil {
			t.Errorf("F001b: %q (unsichtbares Format-Zeichen) muss blockiert werden", to)
		}
	}

	// Bestehende Erlaubt-Fälle müssen unverändert grün bleiben.
	allowed := []string{"a@x.de", " a@x.de ", "garbage-prefix-a@x.de"}
	for _, to := range allowed {
		if err := recipientBlockedForVerification(host, to); err != nil {
			t.Errorf("F001b: %q muss weiterhin erlaubt sein, war: %v", to, err)
		}
	}
}

// Adversary Fix-Loop F001 Defense-in-Depth: SendVerificationMail bekommt den
// bereinigten (getrimmten) `to`-Wert für dialAndSend — hier indirekt über
// den Reserved-Domain-Guard geprüft: Rand-Whitespace um eine reservierte
// Domain darf den Guard nicht umgehen.
func TestSendVerificationMail_F001_WhitespaceDoesNotBypassReservedDomainGuard(t *testing.T) {
	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "re_dummy", From: "gregor_zwanzig@henemm.com"}
	err := SendVerificationMail(cfg, " attacker@example.com ", verifySendTestMail())
	if err == nil {
		t.Error("F001: Rand-Whitespace um eine reservierte Domain darf den Guard nicht umgehen")
	}
}

// Adversary Fix-Loop F002 (#1219, LOW→mitnehmen, PO „reservierte Domains
// IMMER"): isReservedTestDomain blockte example.com nur exakt, nicht
// Subdomains davon. sub.example.com muss jetzt ebenfalls reserviert sein;
// myexample.com (KEINE echte Subdomain, nur ähnlicher Name) bleibt erlaubt.
func TestIsReservedTestDomain_F002_SubdomainOfExampleBlocked(t *testing.T) {
	if !isReservedTestDomain("user@sub.example.com") {
		t.Error("F002: user@sub.example.com muss als reservierte Subdomain blockiert werden")
	}
	if !isReservedTestDomain("user@deep.sub.example.net") {
		t.Error("F002: user@deep.sub.example.net muss als reservierte Subdomain blockiert werden")
	}
	if isReservedTestDomain("user@myexample.com") {
		t.Error("F002: user@myexample.com ist KEINE Subdomain von example.com und darf nicht blockiert werden")
	}
}
