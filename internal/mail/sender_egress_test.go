// SMTP-Linie des Egress-Waechters (Issue #1337, Scheibe "Go-Prozess", AC-7).
// Spec: docs/specs/modules/egress_guard_go.md.
//
// net/smtp laeuft nicht ueber http.DefaultTransport — der Waechter greift hier
// ueber egress.SMTPAllowed als erste Pruefung in dialAndSend. Beweis ohne Netz:
// der Versand bricht mit dem Egress-Fehler ab, bevor smtp.SendMail eine
// Verbindung aufbauen kann. Die bestehenden Linien resendBlocked (#1122) und
// recipientBlocked (#1147/#1219) bleiben unberuehrt.
package mail

import (
	"errors"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/egress"
)

func stagingEgress(t *testing.T) {
	t.Helper()
	if !egress.Install(&config.Config{Env: "staging"}) {
		t.Fatal("egress.Install() haette in Staging installieren muessen")
	}
	t.Cleanup(egress.Uninstall)
}

func TestSMTPHostBlockedInStaging(t *testing.T) {
	// AC-7: undeklarierter SMTP-Host in Staging -> Abbruch vor dem Verbindungsaufbau.
	stagingEgress(t)

	cfg := MailConfig{
		Host: "smtp.undeclared-relay.invalid",
		Port: 587,
		User: "user",
		Pass: "pass",
		From: "gregor_zwanzig@henemm.com",
	}
	err := Send(cfg, "someone@henemm.com", Mail{Subject: "x", PlainBody: "y", HTMLBody: "<p>y</p>"})

	if !errors.Is(err, egress.ErrEgressBlocked) {
		t.Fatalf("erwartet ErrEgressBlocked, bekommen: %v", err)
	}
}

func TestSMTPDeclaredHostPassesEgressLine(t *testing.T) {
	// Gegenprobe: der deklarierte Test-Host mail.henemm.com wird von der
	// Egress-Linie durchgelassen — ein Fehler kommt dann erst vom Dial.
	stagingEgress(t)

	if err := egress.SMTPAllowed("mail.henemm.com"); err != nil {
		t.Fatalf("mail.henemm.com ist TestAccess und haette durchgehen muessen: %v", err)
	}
}

func TestSMTPAllowedIsNoOpWithoutGuard(t *testing.T) {
	// Prod: Waechter nicht installiert -> SMTPAllowed ist immer nil.
	if err := egress.SMTPAllowed("smtp.resend.com"); err != nil {
		t.Fatalf("ohne installierten Waechter muss SMTPAllowed nil liefern: %v", err)
	}
}

func TestExistingGuardsStillApply(t *testing.T) {
	// AC-7 (zweiter Teil): resendBlocked und recipientBlocked liefern auch mit
	// installiertem Egress-Waechter unveraendert ihre eigenen Fehler — die
	// Egress-Linie tritt zusaetzlich davor, ersetzt nichts.
	stagingEgress(t)

	if err := resendBlocked("smtp.resend.com"); err == nil {
		t.Fatal("resendBlocked haette den Resend-Host sperren muessen (#1122)")
	}
	if err := recipientBlocked("smtp.resend.com", "gregor-test@henemm.com"); err == nil {
		t.Fatal("recipientBlocked haette das Test-Postfach sperren muessen (#1147/#1219)")
	}

	cfg := MailConfig{Host: "smtp.resend.com", Port: 587, User: "resend", Pass: "key"}
	err := Send(cfg, "nobody@example.org", Mail{Subject: "x"})
	if err == nil {
		t.Fatal("Send an Resend-Host haette blockiert werden muessen")
	}
	if errors.Is(err, egress.ErrEgressBlocked) {
		t.Fatalf("Egress-Linie hat die bestehende Guard-Linie verdraengt: %v", err)
	}
	if !strings.Contains(err.Error(), "#1147/#1219") && !strings.Contains(err.Error(), "#1122") {
		t.Fatalf("unerwarteter Fehler statt bestehender Guard-Meldung: %v", err)
	}
}
