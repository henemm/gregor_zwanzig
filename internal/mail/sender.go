// Package mail provides minimal SMTP dispatch for Go-side transactional mail
// (currently only password reset). Single helper, no interface — see spec
// docs/specs/modules/password_reset_mail.md.
package mail

import (
	"fmt"
	"log"
	"mime"
	"net/smtp"
	"strings"
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

// Send dispatches an e-mail over SMTP+STARTTLS using stdlib net/smtp.
// Blocks until completion or timeout (caller is responsible for goroutine
// and context cancellation). Returns nil on successful 250 OK from the relay.
func Send(cfg MailConfig, to string, msg Mail) error {
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
