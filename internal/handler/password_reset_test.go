package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED: Tests for password reset — must FAIL until implemented.

func TestForgotPasswordReturns200ForExistingUser(t *testing.T) {
	s := newTestStore(t)
	// Create user
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`"}`), 0644)

	h := ForgotPasswordHandler(s, bcrypt.MinCost)

	body := `{"username":"alice"}`
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Token file should be created
	tokenFile := filepath.Join(dir, "password_reset.json")
	if _, err := os.Stat(tokenFile); os.IsNotExist(err) {
		t.Error("password_reset.json should be created")
	}
}

func TestForgotPasswordReturns200ForNonExistentUser(t *testing.T) {
	s := newTestStore(t)
	h := ForgotPasswordHandler(s, bcrypt.MinCost)

	// Non-existent user — should still return 200 (no user enumeration)
	body := `{"username":"nobody"}`
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 even for non-existent user, got %d", w.Code)
	}
}

func TestResetPasswordSuccess(t *testing.T) {
	s := newTestStore(t)
	// Create user
	oldHash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "bob")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"bob","password_hash":"`+string(oldHash)+`"}`), 0644)

	// Create valid reset token
	token := "abc123testtoken"
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte(token), bcrypt.MinCost)
	resetToken := model.PasswordResetToken{
		TokenHash: string(tokenHash),
		ExpiresAt: time.Now().Add(30 * time.Minute),
	}
	tokenData, _ := json.Marshal(resetToken)
	os.WriteFile(filepath.Join(dir, "password_reset.json"), tokenData, 0644)

	h := ResetPasswordHandler(s, bcrypt.MinCost)

	body := `{"username":"bob","token":"abc123testtoken","new_password":"newpass123"}`
	req := httptest.NewRequest("POST", "/api/auth/reset-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Token file should be deleted
	tokenFile := filepath.Join(dir, "password_reset.json")
	if _, err := os.Stat(tokenFile); !os.IsNotExist(err) {
		t.Error("password_reset.json should be deleted after successful reset")
	}

	// New password should work
	userData, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	var user model.User
	json.Unmarshal(userData, &user)
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte("newpass123")); err != nil {
		t.Error("new password should be set correctly")
	}
}

func TestResetPasswordExpiredToken(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "charlie")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"charlie","password_hash":"x"}`), 0644)

	// Expired token
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("expired"), bcrypt.MinCost)
	resetToken := model.PasswordResetToken{
		TokenHash: string(tokenHash),
		ExpiresAt: time.Now().Add(-1 * time.Hour), // expired
	}
	tokenData, _ := json.Marshal(resetToken)
	os.WriteFile(filepath.Join(dir, "password_reset.json"), tokenData, 0644)

	h := ResetPasswordHandler(s, bcrypt.MinCost)

	body := `{"username":"charlie","token":"expired","new_password":"newpass123"}`
	req := httptest.NewRequest("POST", "/api/auth/reset-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for expired token, got %d", w.Code)
	}
}

func TestResetPasswordWrongToken(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "dave")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"dave","password_hash":"x"}`), 0644)

	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("correct"), bcrypt.MinCost)
	resetToken := model.PasswordResetToken{
		TokenHash: string(tokenHash),
		ExpiresAt: time.Now().Add(30 * time.Minute),
	}
	tokenData, _ := json.Marshal(resetToken)
	os.WriteFile(filepath.Join(dir, "password_reset.json"), tokenData, 0644)

	h := ResetPasswordHandler(s, bcrypt.MinCost)

	body := `{"username":"dave","token":"WRONG","new_password":"newpass123"}`
	req := httptest.NewRequest("POST", "/api/auth/reset-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for wrong token, got %d", w.Code)
	}
}

func TestResetPasswordShortPassword(t *testing.T) {
	s := newTestStore(t)
	h := ResetPasswordHandler(s, bcrypt.MinCost)

	body := `{"username":"x","token":"x","new_password":"short"}`
	req := httptest.NewRequest("POST", "/api/auth/reset-password", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for short password, got %d", w.Code)
	}
}
