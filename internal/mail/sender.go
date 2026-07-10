// Package mail provides minimal SMTP dispatch for Go-side transactional mail
// (currently only password reset). Single helper, no interface — see spec
// docs/specs/modules/password_reset_mail.md.
package mail

import (
	"encoding/json"
	"fmt"
	"log"
	"mime"
	"net/mail"
	"net/smtp"
	"os"
	"path/filepath"
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
// Resend. Historisch (Issue #1147) als Denylist genutzt; seit Issue #1219
// funktional durch loadResendAllowlist() ABGELÖST — beide Adressen gehören
// zu keinem echten Nutzerprofil und werden daher automatisch NICHT in die
// Allowlist aufgenommen. Konstante bleibt zu Dokumentationszwecken erhalten.
var testMailboxes = map[string]bool{
	"gregor-test@henemm.com":    true,
	"gregor-staging@henemm.com": true,
}

// resendAllowlistProfile ist eine minimale Projektion eines user.json-
// Profils — nur die für die Resend-Empfänger-Allowlist relevanten Felder
// (Issue #1219). EmailVerifiedAt (Issue #1219 Scheibe 1) ist das
// Eignungskriterium: nur Profile mit gesetztem Zeitstempel sind
// allowlist-fähig.
type resendAllowlistProfile struct {
	MailTo          string `json:"mail_to"`
	Email           string `json:"email"`
	EmailVerifiedAt string `json:"email_verified_at"`
}

var (
	reservedTestDomains = map[string]bool{
		"example.com": true,
		"example.net": true,
		"example.org": true,
	}
	reservedTestTLDs = []string{".test", ".invalid", ".localhost", ".example"}
	reservedBareTLDs = map[string]bool{
		"test":      true,
		"invalid":   true,
		"localhost": true,
		"example":   true,
	}
)

// isReservedTestDomain prüft, ob die Domain einer Adresse RFC-2606-reserviert
// ist (Issue #1219 Scheibe 1, AC-4) — Symmetrie zu Python
// _is_reserved_test_domain(). Reservierte Domains werden IMMER geblockt,
// unabhängig vom Verifikationsstatus des Profils.
//
// Adversary F002/F003: ein Trailing-Dot-FQDN (example.com., example.com..)
// wird vor dem Vergleich gekürzt — TrimRight statt TrimSuffix, damit ALLE
// trailing Dots entfernt werden (1:1-Parität zu Python rstrip(".")), sonst
// rutscht der Suffix-Check bei mehrfachem Trailing-Dot fälschlich durch.
// Eine BARE-TLD ohne Subdomain-Label (user@localhost, user@test) wird
// zusätzlich per EXAKTEM Vergleich erkannt — NICHT als Substring/Suffix,
// damit legitime Domains wie mytest.de/example.company nicht fälschlich
// gesperrt werden.
func isReservedTestDomain(addr string) bool {
	normalized := normalizedAddrForGuard(addr)
	_, domain, found := strings.Cut(normalized, "@")
	domain = strings.TrimRight(domain, ".")
	if !found || domain == "" {
		return false
	}
	if reservedTestDomains[domain] || reservedBareTLDs[domain] {
		return true
	}
	for _, tld := range reservedTestTLDs {
		if strings.HasSuffix(domain, tld) {
			return true
		}
	}
	return false
}

// resendAllowlistDataDir löst das Datenverzeichnis für loadResendAllowlist
// auf und respektiert dabei die bestehende GZ_DATA_DIR-Konvention (Issue
// #1219) — fällt sonst auf den Projekt-Default "data" zurück.
func resendAllowlistDataDir() string {
	if v := os.Getenv("GZ_DATA_DIR"); v != "" {
		return v
	}
	return "data"
}

// loadResendAllowlist sammelt normalisierte mail_to-/email-Adressen aller
// VERIFIZIERTEN Nutzerprofile unter dataDir/users/<id>/user.json (Issue
// #1219 Scheibe 1). Symmetrisches Pendant zu
// src/output/channels/email.py::_load_resend_allowlist. Eignungskriterium
// ist das gesetzte Profilfeld EmailVerifiedAt — Profile ohne (leeres/
// fehlendes) email_verified_at werden konservativ ausgeschlossen, im
// Zweifel NICHT in die Allowlist aufnehmen. Reservierte Test-Domains (siehe
// isReservedTestDomain) werden zusätzlich ausgeschlossen, auch bei
// gesetztem EmailVerifiedAt (AC-4). Plus-Adressierung wird auf
// Allowlist-Einträgen NICHT gekappt (echte Nutzeradressen werden 1:1
// verglichen, nur lowercase/trim via mail.ParseAddress).
//
// Fail-soft: ein fehlendes dataDir/users-Verzeichnis liefert eine leere
// Allowlist; eine fehlende/kaputte user.json überspringt nur das betroffene
// Profil — nie ein Crash des Sendepfads.
func loadResendAllowlist(dataDir string) map[string]bool {
	allowed := make(map[string]bool)
	usersRoot := filepath.Join(dataDir, "users")
	entries, err := os.ReadDir(usersRoot)
	if err != nil {
		return allowed
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		userID := e.Name()
		data, err := os.ReadFile(filepath.Join(usersRoot, userID, "user.json"))
		if err != nil {
			continue
		}
		var profile resendAllowlistProfile
		if err := json.Unmarshal(data, &profile); err != nil {
			continue
		}
		if profile.EmailVerifiedAt == "" {
			continue
		}
		for _, raw := range []string{profile.MailTo, profile.Email} {
			if raw == "" {
				continue
			}
			addr := raw
			if parsed, perr := mail.ParseAddress(raw); perr == nil {
				addr = parsed.Address
			}
			addr = strings.ToLower(strings.TrimSpace(addr))
			if addr == "" || isReservedTestDomain(addr) {
				continue
			}
			allowed[addr] = true
		}
	}
	return allowed
}

// maskAddrForLog reduziert eine Adresse auf die Domain für Log-/
// Fehlermeldungen (Issue #1219 AC-6) — verhindert, dass eine volle
// Empfängeradresse im Klartext geloggt bzw. in einer Fehlermeldung
// ausgegeben wird.
func maskAddrForLog(raw string) string {
	addr := raw
	if parsed, err := mail.ParseAddress(raw); err == nil {
		addr = parsed.Address
	}
	if idx := strings.Index(addr, "@"); idx >= 0 {
		return "***@" + strings.ToLower(addr[idx+1:])
	}
	return "***"
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

// recipientBlocked enforces the recipient-side Resend invariant. Seit Issue
// #1219 eine POSITIVE Allowlist statt der #1147-Denylist: ein Resend-Host
// darf nur an echte, angelegte (Nicht-Test-)Nutzerprofile zustellen. Dritte
// Guard-Linie, ergänzt resendBlocked (#1122) — wird VOR resendBlocked
// geprüft, damit sie auch unter go test greift, wo resendBlocked ohnehin
// jeden Resend-Host blockiert. gregor-test@/gregor-staging@henemm.com
// gehören zu keinem echten Profil und bleiben so automatisch blockiert
// (Regressionsschutz für die abgelöste #1147-Denylist).
// Fix-Loop 1 (F002a) + Fix-Loop 2 (F003): `to` wird an der Trennzeichen-
// KLASSE Komma/Semikolon gesplittet (mit Whitespace-Fallback für Fragmente,
// die mail.ParseAddress nicht parsen kann).
func recipientBlocked(host, to string) error {
	if !strings.Contains(strings.ToLower(host), "resend") {
		return nil
	}
	// Fix-Loop 4 (F005): roher Substring-Scan bleibt ZUSÄTZLICH aktiv (kein
	// Ersatz für die Allowlist-Prüfung) — greift unabhängig davon, ob
	// splitRecipientField den Empfänger korrekt zerlegt.
	if rawContainsTestMailbox(to) {
		log.Printf(
			"mail.Send: Resend-Allowlist-Guard (Fangnetz) blockiert Empfänger bei Host %q (#1147/#1219)",
			host)
		return fmt.Errorf(
			"mail.Send: Test-Postfach in Empfänger-Rohstring bei Resend-Host %q blockiert (#1147/#1219) — "+
				"Test-Postfächer dürfen nie über Resend versendet werden", host)
	}

	allowlist := loadResendAllowlist(resendAllowlistDataDir())
	parts := splitRecipientField(to)
	var blocked []string
	for _, part := range parts {
		normalized := normalizedAddrForGuard(part)
		if !allowlist[normalized] || isReservedTestDomain(normalized) {
			blocked = append(blocked, maskAddrForLog(part))
		}
	}
	if len(parts) == 0 || len(blocked) > 0 {
		log.Printf(
			"mail.Send: Resend-Allowlist-Guard blockiert %d Empfänger bei Host %q, "+
				"kein echtes Nutzerprofil gefunden (#1147/#1219): %v",
			len(blocked), host, blocked)
		return fmt.Errorf(
			"mail.Send: Empfänger nicht in der Resend-Allowlist bei Host %q blockiert (#1147/#1219) — "+
				"nur mail_to/email echter, angelegter (Nicht-Test-)Nutzerprofile dürfen über Resend erreicht werden",
			host)
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
