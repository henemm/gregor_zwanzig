package handler

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
)

// Wirkort-Test der SMTP-Weiche im ForgotPasswordHandler (Issue #2152, AC-6;
// Adversary Fix-Loop 1, Finding F001). Geprüft wird die vom Handler GEWÄHLTE
// Primär-Konfiguration an der Versand-Naht sendResetMailFn (auth.go) — nicht
// ein Log-Wortlaut. Beide SMTP-Konfigurationen sind gesetzt und klar
// unterscheidbar, damit ausschließlich die Weiche entscheidet und kein
// "not configured"-Abbruch das Ergebnis erzeugt. Kein Mock: echter Handler,
// echter Store, echte Platte; nur der SMTP-Dial ist an der Naht ersetzt.

const (
	resetProdHost = "smtp.resend.com"
	resetTestHost = "smtp.gmail.com"
)

// forgotPasswordPrimaryHost fährt einen echten Reset-Request für userID und
// liefert den Host der Primär-Konfiguration zurück, die der Handler an den
// Versand übergeben hat.
func forgotPasswordPrimaryHost(t *testing.T, userID string, isTestUser bool) string {
	t.Helper()
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{
		ID: userID, PasswordHash: string(hash),
		Email: userID + "@example.com", IsTestUser: isTestUser,
	}); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	// Nach Empfänger filtern: nachlaufende Versand-Goroutinen anderer
	// ForgotPassword-Tests laufen ebenfalls durch diese Naht und dürfen den
	// beobachteten Wert nicht überschreiben.
	wantTo := userID + "@example.com"
	hosts := make(chan string, 4)
	orig := sendResetMailFn
	sendResetMailFn = func(primaryCfg, fallbackCfg mail.MailConfig, to string, msg mail.Mail) error {
		if to == wantTo {
			hosts <- primaryCfg.Host
		}
		return nil
	}
	// Die Naht wird erst in der Versand-Goroutine gelesen — Rücksetzen darf
	// deshalb NICHT per defer vor dem Aufruf greifen (sonst echter Dial).
	restore := func() { sendResetMailFn = orig }

	cfg := config.Config{
		PublicHost: "https://example.com",
		SMTPHost:   resetProdHost, SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
		GoogleSMTPHost: resetTestHost, GoogleSMTPPort: 587,
		GoogleSMTPUser: "gz-test@gmail.com", GoogleSMTPPass: "gp",
	}
	body, _ := json.Marshal(map[string]string{"username": userID})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	ForgotPasswordHandler(s, bcrypt.MinCost, cfg)(rec, req)
	if rec.Code != 200 {
		restore()
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}

	select {
	case host := <-hosts:
		restore()
		return host
	case <-time.After(2 * time.Second):
		restore()
		t.Fatalf("Versand-Naht sendResetMailFn wurde binnen 2s nicht aufgerufen (user %q)", userID)
		return ""
	}
}

// AC-6: „protester" trägt „test" im Namen, aber KEIN is_test_user-Flag — der
// Reset-Versand muss über die Produktiv-/Resend-Konfiguration laufen.
func TestForgotPassword_UnflaggedTestishName_UsesResendConfig_AC6(t *testing.T) {
	if host := forgotPasswordPrimaryHost(t, "protester", false); host != resetProdHost {
		t.Errorf("AC-6: %q ohne is_test_user-Flag muss über die Produktiv-/Resend-Konfiguration "+
			"versenden (%q), gewählter Host war %q", "protester", resetProdHost, host)
	}
}

// AC-6 (Gegenprobe): neutral benanntes Konto MIT is_test_user-Flag — der
// Reset-Versand muss über die Test-/Gmail-Konfiguration laufen.
func TestForgotPassword_FlaggedNeutralName_UsesGoogleSMTPConfig_AC6(t *testing.T) {
	if host := forgotPasswordPrimaryHost(t, "mitarbeiter42", true); host != resetTestHost {
		t.Errorf("AC-6: %q mit is_test_user-Flag muss über die Test-/Gmail-Konfiguration "+
			"versenden (%q), gewählter Host war %q", "mitarbeiter42", resetTestHost, host)
	}
}
