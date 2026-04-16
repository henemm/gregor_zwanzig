package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD RED: Tests for profile endpoints — must FAIL until implemented.

func TestGetProfileHandler(t *testing.T) {
	// GIVEN: A registered user with channel settings
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`","mail_to":"alice@example.com","signal_phone":"+43123","telegram_chat_id":"999"}`), 0644)

	h := GetProfileHandler(s)

	// WHEN: Alice requests her profile
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "alice")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 with profile (NO password_hash)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp["id"] != "alice" {
		t.Errorf("expected id 'alice', got '%v'", resp["id"])
	}
	if resp["mail_to"] != "alice@example.com" {
		t.Errorf("expected mail_to, got '%v'", resp["mail_to"])
	}
	if resp["signal_phone"] != "+43123" {
		t.Errorf("expected signal_phone, got '%v'", resp["signal_phone"])
	}
	if resp["telegram_chat_id"] != "999" {
		t.Errorf("expected telegram_chat_id, got '%v'", resp["telegram_chat_id"])
	}
	if _, hasHash := resp["password_hash"]; hasHash {
		t.Error("password_hash must NOT be in profile response")
	}
}

func TestGetProfileHandlerNotFound(t *testing.T) {
	s := newTestStore(t)
	h := GetProfileHandler(s)

	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "nobody")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestUpdateProfileHandler(t *testing.T) {
	// GIVEN: Existing user
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "bob")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"bob","password_hash":"`+string(hash)+`"}`), 0644)

	h := UpdateProfileHandler(s)

	// WHEN: Bob updates his channel settings
	body := `{"mail_to":"bob@example.com","telegram_chat_id":"42"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	ctx := middleware.ContextWithUserID(req.Context(), "bob")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 with updated profile
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp["mail_to"] != "bob@example.com" {
		t.Errorf("expected mail_to 'bob@example.com', got '%v'", resp["mail_to"])
	}
	if resp["telegram_chat_id"] != "42" {
		t.Errorf("expected telegram_chat_id '42', got '%v'", resp["telegram_chat_id"])
	}
	// password_hash must not leak
	if _, hasHash := resp["password_hash"]; hasHash {
		t.Error("password_hash must NOT be in response")
	}
}

func TestUpdateProfilePreservesPasswordHash(t *testing.T) {
	// GIVEN: User with known password
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	originalHash := string(hash)
	dir := filepath.Join(s.DataDir, "users", "charlie")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"charlie","password_hash":"`+originalHash+`"}`), 0644)

	h := UpdateProfileHandler(s)

	// WHEN: Charlie updates profile (even trying to set password_hash)
	body := `{"mail_to":"c@example.com","password_hash":"HACKED"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	ctx := middleware.ContextWithUserID(req.Context(), "charlie")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// THEN: password_hash on disk is unchanged
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if !strings.Contains(string(data), originalHash) {
		t.Error("password_hash should be preserved, not overwritten")
	}
	if strings.Contains(string(data), "HACKED") {
		t.Error("password_hash should NOT be overwritable via profile update")
	}
}

func TestRegisterCreatesUserDirs(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost)

	body := `{"username":"newuser","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// THEN: User directories are created
	base := filepath.Join(s.DataDir, "users", "newuser")
	for _, sub := range []string{"locations", "trips", "gpx", "weather_snapshots"} {
		path := filepath.Join(base, sub)
		info, err := os.Stat(path)
		if err != nil {
			t.Errorf("expected directory %s to exist: %v", sub, err)
		} else if !info.IsDir() {
			t.Errorf("expected %s to be a directory", sub)
		}
	}
}
