package store

// TDD RED: Issue #425 — Google OAuth Login
// Spec: docs/specs/modules/google_oauth_login.md
//
// Tests for FindUserByOAuthSub — muss FEHLSCHLAGEN bis implementiert.
// Ausführung: cd <repo> && go test ./internal/store/... -run TestFindUserByOAuthSub -v

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-3: Bestehender OAuth-User wird per FindUserByOAuthSub gefunden.
func TestFindUserByOAuthSubFound(t *testing.T) {
	// GIVEN: User mit OAuthProvider="google" und OAuthSub="sub-123" existiert
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:            "g-aabbccdd",
		OAuthProvider: "google",
		OAuthSub:      "sub-123",
		Email:         "tester@gmail.com",
		CreatedAt:     time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: FindUserByOAuthSub mit passendem Provider+Sub
	found, err := s.FindUserByOAuthSub("google", "sub-123")

	// THEN: User wird zurückgegeben
	if err != nil {
		t.Fatalf("FindUserByOAuthSub error: %v", err)
	}
	if found == nil {
		t.Fatal("expected user, got nil")
	}
	if found.ID != "g-aabbccdd" {
		t.Errorf("expected ID 'g-aabbccdd', got '%s'", found.ID)
	}
	if found.OAuthSub != "sub-123" {
		t.Errorf("expected OAuthSub 'sub-123', got '%s'", found.OAuthSub)
	}
}

// AC-2: Kein User für neuen OAuth-Sub → nil zurück (kein Fehler).
func TestFindUserByOAuthSubNotFound(t *testing.T) {
	// GIVEN: Leerer Store
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	// WHEN: FindUserByOAuthSub ohne passenden Eintrag
	found, err := s.FindUserByOAuthSub("google", "sub-does-not-exist")

	// THEN: nil, nil (kein Fehler — neuer User wird angelegt)
	if err != nil {
		t.Fatalf("expected nil error, got: %v", err)
	}
	if found != nil {
		t.Errorf("expected nil user, got: %v", found)
	}
}

// AC-3: Falscher Provider oder falscher Sub → nicht gefunden.
func TestFindUserByOAuthSubWrongProvider(t *testing.T) {
	// GIVEN: Google-User existiert
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:            "g-11223344",
		OAuthProvider: "google",
		OAuthSub:      "sub-xyz",
		CreatedAt:     time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: Suche mit "apple" als Provider
	found, err := s.FindUserByOAuthSub("apple", "sub-xyz")

	// THEN: nil (falscher Provider)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found != nil {
		t.Errorf("expected nil (wrong provider), got: %v", found)
	}
}

// Sicherstellen: OAuthProvider und OAuthSub werden korrekt persistiert (Roundtrip).
func TestOAuthFieldsRoundtrip(t *testing.T) {
	// GIVEN: User mit OAuth-Feldern
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:            "g-deadbeef",
		OAuthProvider: "google",
		OAuthSub:      "persistent-sub-42",
		Email:         "roundtrip@example.com",
		CreatedAt:     time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: User laden
	loaded, err := s.LoadUser("g-deadbeef")

	// THEN: Felder unverändert
	if err != nil {
		t.Fatalf("LoadUser: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected loaded user, got nil")
	}
	if loaded.OAuthProvider != "google" {
		t.Errorf("OAuthProvider: expected 'google', got '%s'", loaded.OAuthProvider)
	}
	if loaded.OAuthSub != "persistent-sub-42" {
		t.Errorf("OAuthSub: expected 'persistent-sub-42', got '%s'", loaded.OAuthSub)
	}
}

// Sicherstellen: Passwort-User ohne OAuth-Felder bleibt nach SaveUser unverändert (keine omitempty-Regression).
func TestPasswordUserHasNoOAuthFields(t *testing.T) {
	// GIVEN: Klassischer Passwort-User
	tmpDir := t.TempDir()

	// Datei direkt schreiben (wie Prod-Daten vor #425)
	dir := filepath.Join(tmpDir, "users", "alice")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	raw := []byte(`{"id":"alice","password_hash":"$2a$10$hash","created_at":"2026-05-01T00:00:00Z"}`)
	if err := os.WriteFile(filepath.Join(dir, "user.json"), raw, 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	s := New(tmpDir, "alice")

	// WHEN: User laden, speichern (z.B. durch UpdateProfile)
	user, err := s.LoadUser("alice")
	if err != nil || user == nil {
		t.Fatalf("LoadUser: %v, %v", err, user)
	}
	if err := s.SaveUser(*user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// THEN: OAuth-Felder sind NICHT in JSON (omitempty)
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	var m map[string]interface{}
	json.Unmarshal(data, &m)
	if _, ok := m["oauth_provider"]; ok {
		t.Error("oauth_provider should not appear in user.json for password user (omitempty)")
	}
	if _, ok := m["oauth_sub"]; ok {
		t.Error("oauth_sub should not appear in user.json for password user (omitempty)")
	}
}
