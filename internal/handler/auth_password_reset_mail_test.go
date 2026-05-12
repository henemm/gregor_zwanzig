package handler

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Handler-Tests fuer No-Enumeration (AC-3) und SMTP-not-configured (AC-6).
// These tests will FAIL to compile until ForgotPasswordHandler accepts a config.Config
// parameter. Compile error: "too many arguments in call to ForgotPasswordHandler".

func TestForgotPassword_NoEmailAddress_LogsWarning(t *testing.T) {
	s := newTestStore(t)

	// User with NO email and NO mail_to
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	user := model.User{ID: "alice", PasswordHash: string(hash)}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	cfg := config.Config{
		SMTPHost:   "smtp.example.com",
		SMTPPort:   587,
		SMTPUser:   "u",
		SMTPPass:   "p",
		PublicHost: "https://example.com",
	}
	handler := ForgotPasswordHandler(s, bcrypt.MinCost, cfg)

	body, _ := json.Marshal(map[string]string{"username": "alice"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	handler(rec, req)

	if rec.Code != 200 {
		t.Errorf("AC-3: expected 200 (no-enumeration), got %d", rec.Code)
	}
	if !strings.Contains(logBuf.String(), "no email address for user alice") {
		t.Errorf("AC-3: expected warning log 'no email address for user alice', got: %s", logBuf.String())
	}
}

// TestForgotPassword_EmailFallbackWhenMailToEmpty covers AC-2: when User.MailTo
// is empty but User.Email is set, the handler MUST use Email as recipient
// (no "no email address" warning, no early return). The SMTP call itself is
// allowed to fail in the background goroutine — we point at a closed port so
// Send returns quickly, but the handler has already returned 200.
func TestForgotPassword_EmailFallbackWhenMailToEmpty(t *testing.T) {
	s := newTestStore(t)

	// User with NO mail_to but Email set
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	user := model.User{
		ID:           "alice",
		PasswordHash: string(hash),
		Email:        "alice@example.com",
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	// Complete SMTP config but pointing at a closed local port — Send fails
	// quickly in the goroutine, handler still answers 200 synchronously.
	cfg := config.Config{
		SMTPHost:   "127.0.0.1",
		SMTPPort:   1, // closed port — Send fails immediately
		SMTPUser:   "u",
		SMTPPass:   "p",
		PublicHost: "https://example.com",
	}
	handler := ForgotPasswordHandler(s, bcrypt.MinCost, cfg)

	body, _ := json.Marshal(map[string]string{"username": "alice"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	handler(rec, req)

	if rec.Code != 200 {
		t.Errorf("AC-2: expected 200, got %d", rec.Code)
	}
	if strings.Contains(logBuf.String(), "no email address") {
		t.Errorf("AC-2: must NOT log 'no email address' when Email fallback applies. Log: %s", logBuf.String())
	}
	if strings.Contains(logBuf.String(), "SMTP not configured") {
		t.Errorf("AC-2: must NOT log 'SMTP not configured' — SMTP is configured. Log: %s", logBuf.String())
	}
}

func TestForgotPassword_SMTPNotConfigured_LogsWarning(t *testing.T) {
	s := newTestStore(t)

	// User WITH email address, but SMTP not configured in cfg
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	user := model.User{ID: "alice", PasswordHash: string(hash), Email: "alice@example.com"}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser failed: %v", err)
	}

	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	cfg := config.Config{
		// SMTPHost intentionally empty (AC-6)
		PublicHost: "https://example.com",
	}
	handler := ForgotPasswordHandler(s, bcrypt.MinCost, cfg)

	body, _ := json.Marshal(map[string]string{"username": "alice"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	handler(rec, req)

	if rec.Code != 200 {
		t.Errorf("AC-6: expected 200 (no-enumeration), got %d", rec.Code)
	}
	if !strings.Contains(logBuf.String(), "SMTP not configured") {
		t.Errorf("AC-6: expected warning 'SMTP not configured', got: %s", logBuf.String())
	}
}
