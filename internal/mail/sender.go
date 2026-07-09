// Package mail provides minimal SMTP dispatch for Go-side transactional mail
// (currently only password reset). Single helper, no interface — see spec
// docs/specs/modules/password_reset_mail.md.
package mail

import (
	"fmt"
	"log"
	"mime"
	"net/mail"
	"net/smtp"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"
)

// encodeMailHeader serialisiert einen Header-Wert RFC-2047-konform als
// Quoted-Printable Encoded-Word (=?utf-8?q?...?=) bei Non-ASCII-Input.
// ASCII-only-Eingaben gibt mime.QEncoding.Encode bitidentisch zurück.
func encodeMailHeader(s string) string {
	return mime.QEncoding.Encode("UTF-8", s)
}

// MailConfig captures the SMTP credentials and sender identity for one dispatch.
// Build it per-request from internal/config.Config (Resend vs. Google branch).
type MailConfig struct {
	Host string
	Port int
	User string
	Pass string
	From string
}

// Mail represents a multipart/alternative outgoing message.
type Mail struct {
	Subject   string
	PlainBody string
	HTMLBody  string
}

// IsTestUser detects test-user accounts whose mail MUST NOT be sent through
// Resend (spam reputation guard). Substring match for "test" or "tdd",
// case-insensitive. Mirrors src/app/config.py::_is_test_user.
func IsTestUser(userID string) bool {
	id := strings.ToLower(userID)
	return strings.Contains(id, "test") || strings.Contains(id, "tdd")
}

// resendBlocked enforces the Resend default-deny (Issue #1122): Resend is
// gesperrt, außer der Prozess trägt das explizite Token GZ_RESEND_ALLOWED=1
// (nur Prod-Systemd-Units). Testprozesse (go test) sind AUCH MIT Token gesperrt.
func resendBlocked(host string) error {
	if !strings.Contains(strings.ToLower(host), "resend") {
		return nil
	}
	if testing.Testing() {
		return fmt.Errorf(
			"mail.Send: Resend-Host %q unter go test gesperrt (#1122) — "+
				"Test-Mails gehen über Stalwart; GZ_RESEND_ALLOWED gilt hier nicht", host)
	}
	if os.Getenv("GZ_RESEND_ALLOWED") != "1" {
		return fmt.Errorf(
			"mail.Send: Resend-Host %q ohne GZ_RESEND_ALLOWED=1 gesperrt (#1122) — "+
				"Token setzen nur die Prod-Units (henemm-infra)", host)
	}
	return nil
}

// testMailboxes lists GZ test mailboxes that must never receive mail via
// Resend, regardless of any process-level signal (Issue #1147).
var testMailboxes = map[string]bool{
	"gregor-test@henemm.com":    true,
	"gregor-staging@henemm.com": true,
}

// Fix-Loop 4 (F005): rohes, PARSER-UNABHÄNGIGES Fangnetz (Symmetrie zu
// src/output/channels/email.py::_raw_contains_test_mailbox). Statt jeden
// Zerlege-/Normalisierungs-Trick einzeln zu stopfen, scannt dieser Layer
// den rohen, UNGEPARSTEN `to`-String direkt nach den Test-Postfach-
// Literalen (plus-tolerant) — immun gegen jede künftige Zerlege-Umgehung,
// weil er nichts zerlegt.
var (
	controlCharsRe   = regexp.MustCompile(`[\r\n\v\f\x00]`)
	testMailboxRawRe = regexp.MustCompile(`(?i)(?:gregor-test|gregor-staging)(?:\+[^@]*)?@henemm\.com`)
)

// rawContainsTestMailbox strippt zuerst Steuerzeichen (\r \n \v \f \x00) aus
// dem rohen `to`-String — Steuerzeichen in einer Adresse sind nie legitim,
// werden aber genutzt, um Trennzeichen-/Quote-Parser zu verwirren (F005: ein
// eingebetteter CRLF im Anzeigenamen). Nach dem Strippen wird der rohe
// (NICHT zerlegte) String direkt gegen die Test-Postfach-Literale gescannt.
// Diese Reihenfolge — erst strippen, dann scannen — ist bewusst gewählt: ein
// legitimer Empfänger mit kaputtem Anzeigenamen (z.B.
// `"Weird\r\nName" <real@example.com>`) enthält nach dem Strippen kein
// Test-Postfach-Literal und bleibt unblockiert (AC-4-Regressionsschutz).
func rawContainsTestMailbox(raw string) bool {
	stripped := controlCharsRe.ReplaceAllString(raw, "")
	return testMailboxRawRe.MatchString(stripped)
}

// normalizedAddrForGuard strips the "Name <addr>" form and, for
// Issue #1147 Fix-Loop 1 (F001), cuts the local part at the first "+" so
// plus-addressed variants (gregor-test+foo@henemm.com) still match
// testMailboxes.
func normalizedAddrForGuard(addr string) string {
	lower := strings.ToLower(strings.TrimSpace(addr))
	if parsed, err := mail.ParseAddress(addr); err == nil {
		lower = strings.ToLower(parsed.Address)
	}
	local, domain, found := strings.Cut(lower, "@")
	if found {
		if plusIdx := strings.Index(local, "+"); plusIdx >= 0 {
			local = local[:plusIdx]
		}
		lower = local + "@" + domain
	}
	return lower
}

// splitRecipientField zerlegt ein Empfänger-Feld an der TRENNZEICHEN-KLASSE
// Komma UND Semikolon (Fix-Loop 2, Issue #1147, Finding F003) — ein
// Frontend-Freitextfeld splittet selbst nur an Komma, ein Element mit
// eingebettetem Semikolon würde also unverändert bei Send() ankommen.
//
// Scheitert mail.ParseAddress an einem Teil (z.B. zwei nur durch Leerzeichen
// statt Komma/Semikolon getrennte Adressen in einem Fragment), wird
// zusätzlich an Whitespace roh gesplittet — aber NUR für Teil-Fragmente, die
// selbst ein "@" enthalten, damit `"Name" <addr>`-Formen (die
// mail.ParseAddress weiterhin korrekt auflöst) nicht zerrissen werden.
func splitRecipientField(to string) []string {
	var out []string
	for _, part := range strings.FieldsFunc(to, func(r rune) bool { return r == ',' || r == ';' }) {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if _, err := mail.ParseAddress(part); err == nil {
			out = append(out, part)
			continue
		}
		var withAt []string
		for _, field := range strings.Fields(part) {
			if strings.Contains(field, "@") {
				withAt = append(withAt, field)
			}
		}
		if len(withAt) > 0 {
			out = append(out, withAt...)
		} else {
			out = append(out, part)
		}
	}
	return out
}

// recipientBlocked enforces the recipient-side Resend invariant (Issue
// #1147): a Resend host must never deliver to a GZ test mailbox, regardless
// of user/env/token signals. Third guard line, complements resendBlocked
// (#1122) — checked BEFORE resendBlocked so it fires even under go test,
// where resendBlocked already blocks every Resend host unconditionally.
// Fix-Loop 1 (F002a) + Fix-Loop 2 (F003): `to` is split on the comma/
// semicolon separator CLASS (with a whitespace fallback for fragments
// mail.ParseAddress can't parse) so neither an embedded-comma nor an
// embedded-semicolon string (e.g. from a mail_to config field or a
// frontend free-text field that only splits on commas) can smuggle a test
// mailbox past the guard.
func recipientBlocked(host, to string) error {
	if !strings.Contains(strings.ToLower(host), "resend") {
		return nil
	}
	// Fix-Loop 4 (F005): roher Substring-Scan zuerst — greift zusätzlich zur
	// Parser-Union unten, unabhängig davon, ob splitRecipientField den
	// Empfänger korrekt zerlegt.
	if rawContainsTestMailbox(to) {
		return fmt.Errorf(
			"mail.Send: Test-Postfach in Empfänger-Rohstring %q bei Resend-Host %q blockiert (#1147) — "+
				"Test-Postfächer dürfen nie über Resend versendet werden", to, host)
	}
	for _, part := range splitRecipientField(to) {
		if testMailboxes[normalizedAddrForGuard(part)] {
			return fmt.Errorf(
				"mail.Send: Test-Postfach %q bei Resend-Host %q blockiert (#1147) — "+
					"Test-Postfächer dürfen nie über Resend versendet werden", to, host)
		}
	}
	return nil
}

// Send dispatches an e-mail over SMTP+STARTTLS using stdlib net/smtp.
// Blocks until completion or timeout (caller is responsible for goroutine
// and context cancellation). Returns nil on successful 250 OK from the relay.
func Send(cfg MailConfig, to string, msg Mail) error {
	if err := recipientBlocked(cfg.Host, to); err != nil {
		return err
	}
	if err := resendBlocked(cfg.Host); err != nil {
		return err
	}
	if cfg.Host == "" || cfg.User == "" || cfg.Pass == "" {
		return fmt.Errorf("mail.Send: incomplete SMTP config (host/user/pass)")
	}
	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	auth := smtp.PlainAuth("", cfg.User, cfg.Pass, cfg.Host)

	from := cfg.From
	if from == "" {
		from = cfg.User
	}

	boundary := fmt.Sprintf("gz-boundary-%d", time.Now().UnixNano())
	headers := []string{
		fmt.Sprintf("From: %s", from),
		fmt.Sprintf("To: %s", to),
		fmt.Sprintf("Subject: %s", encodeMailHeader(msg.Subject)),
		"MIME-Version: 1.0",
		fmt.Sprintf("Content-Type: multipart/alternative; boundary=\"%s\"", boundary),
	}
	body := []string{
		strings.Join(headers, "\r\n"),
		"",
		"--" + boundary,
		"Content-Type: text/plain; charset=UTF-8",
		"",
		msg.PlainBody,
		"",
		"--" + boundary,
		"Content-Type: text/html; charset=UTF-8",
		"",
		msg.HTMLBody,
		"",
		"--" + boundary + "--",
		"",
	}
	payload := []byte(strings.Join(body, "\r\n"))

	// smtp.SendMail negotiates STARTTLS automatically; ServerName for TLS
	// verification is derived from cfg.Host internally.
	if err := smtp.SendMail(addr, auth, from, []string{to}, payload); err != nil {
		return fmt.Errorf("mail.Send: %w", err)
	}
	return nil
}

// SendWithFallback versucht zuerst primaryCfg, dann bei Netzwerk-/Temp-Fehlern
// fallbackCfg. Auth-Fehler (535 im Fehler-String) → sofortiger Abbruch, kein Fallback.
// Erfolgreicher Fallback loggt: [SMTP-FALLBACK] sent via fallback SMTP
func SendWithFallback(primaryCfg, fallbackCfg MailConfig, to string, msg Mail) error {
	err := Send(primaryCfg, to, msg)
	if err == nil {
		return nil
	}
	// Auth-Fehler sind permanent — kein Fallback
	if strings.Contains(err.Error(), "535") {
		return err
	}
	if fallbackCfg.Host == "" {
		return err
	}
	log.Printf("[SMTP-FALLBACK] Primary failed: %v — trying fallback SMTP", err)
	if fbErr := Send(fallbackCfg, to, msg); fbErr != nil {
		return fmt.Errorf("primary: %w; fallback: %v", err, fbErr)
	}
	log.Printf("[SMTP-FALLBACK] sent via fallback SMTP")
	return nil
}
