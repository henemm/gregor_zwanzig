package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
	"golang.org/x/crypto/bcrypt"
)

// TDD RED: Tests for ChangePasswordHandler — must FAIL until implemented.

func setupUserWithPassword(t *testing.T, s *store.Store, userID, password string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt error: %v", err)
	}
	s.ProvisionUserDirs(userID)
	s.SaveUser(model.User{ID: userID, PasswordHash: string(hash)})
}

func TestChangePasswordHandler_Success(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	setupUserWithPassword(t, s, "alice", "oldpass123")

	body, _ := json.Marshal(map[string]string{
		"old_password": "oldpass123",
		"new_password": "newpass456",
	})
	req := httptest.NewRequest(http.MethodPut, "/api/auth/password", bytes.NewReader(body))
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()

	ChangePasswordHandler(s, bcrypt.MinCost)(w, req)

	if w.Code != 200 {
		t.Fatalf("Expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify new password works
	user, _ := s.LoadUser("alice")
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte("newpass456")); err != nil {
		t.Fatal("New password should be valid after change")
	}
}

func TestChangePasswordHandler_WrongOldPassword(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	setupUserWithPassword(t, s, "alice", "oldpass123")

	body, _ := json.Marshal(map[string]string{
		"old_password": "wrongpass",
		"new_password": "newpass456",
	})
	req := httptest.NewRequest(http.MethodPut, "/api/auth/password", bytes.NewReader(body))
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()

	ChangePasswordHandler(s, bcrypt.MinCost)(w, req)

	if w.Code != 403 {
		t.Fatalf("Expected 403, got %d: %s", w.Code, w.Body.String())
	}
}

func TestChangePasswordHandler_NewPasswordTooShort(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	setupUserWithPassword(t, s, "alice", "oldpass123")

	body, _ := json.Marshal(map[string]string{
		"old_password": "oldpass123",
		"new_password": "short",
	})
	req := httptest.NewRequest(http.MethodPut, "/api/auth/password", bytes.NewReader(body))
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()

	ChangePasswordHandler(s, bcrypt.MinCost)(w, req)

	if w.Code != 400 {
		t.Fatalf("Expected 400, got %d: %s", w.Code, w.Body.String())
	}
}
