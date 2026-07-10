package handler

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD GREEN — Issue #1219 Scheibe 1: UpdateProfileHandler setzt
// EmailVerifiedAt bei tatsächlicher email/mail_to-Änderung zurück.
// Spec: docs/specs/modules/fix_1219_email_verify.md (AC-5, AC-6).

// AC-5: eine tatsächliche Änderung von mail_to setzt email_verified_at zurück.
func TestUpdateProfileHandler_ResetsVerificationOnMailToChange_AC5(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "ivy")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"ivy","mail_to":"ivy-old@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s)
	body := `{"mail_to":"ivy-new@henemm.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "ivy"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if strings.Contains(string(data), "email_verified_at") {
		t.Errorf("AC-5: email_verified_at muss nach mail_to-Änderung entfernt sein, war: %s", data)
	}
	if !strings.Contains(string(data), "ivy-new@henemm.com") {
		t.Errorf("AC-5: neue mail_to muss persistiert sein, war: %s", data)
	}
}

// AC-5: eine tatsächliche Änderung von email setzt email_verified_at zurück.
func TestUpdateProfileHandler_ResetsVerificationOnEmailChange_AC5(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "jack")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"jack","email":"jack-old@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s)
	body := `{"email":"jack-new@henemm.com"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "jack"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if strings.Contains(string(data), "email_verified_at") {
		t.Errorf("AC-5: email_verified_at muss nach email-Änderung entfernt sein, war: %s", data)
	}
}

// AC-6: ein No-Op-Update (identischer mail_to-Wert) loest KEINEN Reset aus.
func TestUpdateProfileHandler_NoOpUpdateKeepsVerification_AC6(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "kim")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"kim","mail_to":"kim@henemm.com","email_verified_at":"2026-07-01T00:00:00Z"}`), 0644)

	h := UpdateProfileHandler(s)
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
