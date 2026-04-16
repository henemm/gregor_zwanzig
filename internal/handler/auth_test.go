package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/crypto/bcrypt"
)

// TDD RED: Tests for auth handlers — must FAIL until implemented.

func TestRegisterHandlerSuccess(t *testing.T) {
	// GIVEN: Empty store
	s := newTestStore(t)

	h := RegisterHandler(s, bcrypt.MinCost)

	// WHEN: Registering a new user
	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 201 with user ID
	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "alice" {
		t.Errorf("expected id 'alice', got '%s'", resp["id"])
	}

	// AND: user.json exists
	userFile := filepath.Join(s.DataDir, "users", "alice", "user.json")
	if _, err := os.Stat(userFile); os.IsNotExist(err) {
		t.Error("user.json should be created")
	}
}

func TestRegisterHandlerDuplicateUser(t *testing.T) {
	// GIVEN: User already exists
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"alice"}`), 0644)

	h := RegisterHandler(s, bcrypt.MinCost)

	// WHEN: Registering same username
	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 409 Conflict
	if w.Code != 409 {
		t.Fatalf("expected 409, got %d: %s", w.Code, w.Body.String())
	}
}

func TestRegisterHandlerShortUsername(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost)

	body := `{"username":"ab","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for short username, got %d", w.Code)
	}
}

func TestRegisterHandlerShortPassword(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost)

	body := `{"username":"alice","password":"short"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for short password, got %d", w.Code)
	}
}

func TestLoginHandlerSuccess(t *testing.T) {
	// GIVEN: A registered user with bcrypt hash
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`","created_at":"2026-04-15T00:00:00Z"}`), 0644)

	secret := "test-secret-32-chars-long-enough"
	h := LoginHandler(s, secret)

	// WHEN: Logging in with correct credentials
	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 with session cookie
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Check session cookie is set
	cookies := w.Result().Cookies()
	var sessionCookie *http.Cookie
	for _, c := range cookies {
		if c.Name == "gz_session" {
			sessionCookie = c
			break
		}
	}
	if sessionCookie == nil {
		t.Fatal("expected gz_session cookie to be set")
	}
	if !sessionCookie.HttpOnly {
		t.Error("cookie should be HttpOnly")
	}
	if sessionCookie.MaxAge != 86400 {
		t.Errorf("expected MaxAge 86400, got %d", sessionCookie.MaxAge)
	}

	// Check cookie starts with username
	if !strings.HasPrefix(sessionCookie.Value, "alice.") {
		t.Errorf("session cookie should start with 'alice.', got '%s'", sessionCookie.Value[:20])
	}
}

func TestLoginHandlerWrongPassword(t *testing.T) {
	// GIVEN: A registered user
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`"}`), 0644)

	h := LoginHandler(s, "secret")

	// WHEN: Wrong password
	body := `{"username":"alice","password":"falsch!!!"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 401
	if w.Code != 401 {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}

func TestLoginHandlerUserNotFound(t *testing.T) {
	s := newTestStore(t)
	h := LoginHandler(s, "secret")

	body := `{"username":"nobody","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 401 {
		t.Fatalf("expected 401 for unknown user, got %d", w.Code)
	}
}

func TestLoginHandlerMalformedJSON(t *testing.T) {
	s := newTestStore(t)
	h := LoginHandler(s, "secret")

	body := `{not valid json`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for bad JSON, got %d", w.Code)
	}
}
