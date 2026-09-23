package handler

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD GREEN — Issue #1219 Scheibe 1: ein verifiziertes Konto darf nicht
// nachtraeglich auf eine ungepruefte Adresse umgebogen werden.
// Spec: docs/specs/modules/fix_1219_email_verify.md (AC-5, AC-6).
//
// Issue #2147 Scheibe B2 (docs/specs/modules/adresswechsel_nach_bestaetigung.md,
// AC-1) hat die Umsetzung dieser Zusicherung geaendert: statt die Verifikation
// zurueckzusetzen (Aussperr-Falle), bleibt die alte, bestaetigte Adresse
// wirksam und die neue wartet als ausstehende Aenderung auf den
// Bestaetigungslink. Die Zusicherung "ungepruefte Adresse wird nie als
// bestaetigt wirksam" bleibt geprueft.

// AC-5: eine tatsächliche Änderung von mail_to macht die neue Adresse NICHT
// bestaetigt wirksam — sie steht nur als ausstehend im Profil.
func TestUpdateProfileHandler_MailToChangeOfVerifiedAccountStaysPending_AC5(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "ivy")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"ivy","mail_to":"ivy-old@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)
	body := `{"mail_to":"ivy-new@henemm.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "ivy"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, "ivy")
	if u.MailTo != "ivy-old@henemm.com" {
		t.Errorf("AC-5/B2: die ungepruefte neue Adresse darf nicht wirksam werden, mail_to ist %q", u.MailTo)
	}
	if u.EmailVerifiedAt == nil {
		t.Errorf("AC-5/B2: die Bestaetigung der alten Adresse muss erhalten bleiben")
	}
	if u.PendingContactAddress != "ivy-new@henemm.com" || u.PendingContactField != "mail_to" {
		t.Errorf("AC-5/B2: neue mail_to muss als ausstehend persistiert sein, pending=%q field=%q",
			u.PendingContactAddress, u.PendingContactField)
	}
}

// AC-5: eine tatsächliche Änderung von email (hier die wirksame Adresse, kein
// mail_to) macht die neue Adresse NICHT bestaetigt wirksam.
func TestUpdateProfileHandler_EmailChangeOfVerifiedAccountStaysPending_AC5(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "jack")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"jack","email":"jack-old@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)
	body := `{"email":"jack-new@henemm.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "jack"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, "jack")
	if u.Email != "jack-old@henemm.com" || u.EmailVerifiedAt == nil {
		t.Errorf("AC-5/B2: ungepruefte email darf nicht bestaetigt wirksam werden, email=%q verified=%v",
			u.Email, u.EmailVerifiedAt)
	}
	if u.PendingContactAddress != "jack-new@henemm.com" || u.PendingContactField != "email" {
		t.Errorf("AC-5/B2: neue email muss als ausstehend persistiert sein, pending=%q field=%q",
			u.PendingContactAddress, u.PendingContactField)
	}
}

// AC-6: ein No-Op-Update (identischer mail_to-Wert) loest KEINEN Reset aus.
func TestUpdateProfileHandler_NoOpUpdateKeepsVerification_AC6(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "kim")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"kim","mail_to":"kim@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)
	body := `{"mail_to":"kim@henemm.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "kim"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if !strings.Contains(string(data), "2026-07-01T00:00:00Z") {
		t.Errorf("AC-6: No-Op-Update (identischer mail_to) darf email_verified_at NICHT zurücksetzen, war: %s", data)
	}
}
