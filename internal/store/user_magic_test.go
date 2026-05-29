package store

// TDD RED: Issue #449 — Magic Link / OTP Login per E-Mail
// Spec: docs/specs/modules/issue_449_magic_link.md
//
// Tests für FindUserByEmail — muss FEHLSCHLAGEN bis implementiert.
// Ausführung: cd <repo> && go test ./internal/store/... -run TestFindUserByEmail -v

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-3: Bestehender User mit E-Mail-Feld wird gefunden.
func TestFindUserByEmailFound(t *testing.T) {
	// GIVEN: User mit gesetzter E-Mail-Adresse existiert
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:        "alice",
		Email:     "alice@example.com",
		CreatedAt: time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: FindUserByEmail mit passender Adresse
	found, err := s.FindUserByEmail("alice@example.com")

	// THEN: User wird zurückgegeben
	if err != nil {
		t.Fatalf("FindUserByEmail error: %v", err)
	}
	if found == nil {
		t.Fatal("expected user, got nil")
	}
	if found.ID != "alice" {
		t.Errorf("expected ID 'alice', got '%s'", found.ID)
	}
	if found.Email != "alice@example.com" {
		t.Errorf("expected Email 'alice@example.com', got '%s'", found.Email)
	}
}

// AC-2: Kein User mit dieser E-Mail → nil zurück (kein Fehler — neuer User wird angelegt).
func TestFindUserByEmailNotFound(t *testing.T) {
	// GIVEN: Leerer Store
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	// WHEN: FindUserByEmail ohne passenden Eintrag
	found, err := s.FindUserByEmail("nobody@example.com")

	// THEN: nil, nil (kein Fehler)
	if err != nil {
		t.Fatalf("expected nil error, got: %v", err)
	}
	if found != nil {
		t.Errorf("expected nil user, got: %+v", found)
	}
}

// Sicherstellen: Case-insensitive Suche — E-Mail in Großbuchstaben trifft lowercase-User.
func TestFindUserByEmailCaseInsensitive(t *testing.T) {
	// GIVEN: User mit kleingeschriebener E-Mail
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:        "bob",
		Email:     "bob@example.com",
		CreatedAt: time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: Suche mit Großbuchstaben
	found, err := s.FindUserByEmail("BOB@EXAMPLE.COM")

	// THEN: User wird trotzdem gefunden (case-insensitive)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found == nil {
		t.Fatal("expected user for case-insensitive match, got nil")
	}
	if found.ID != "bob" {
		t.Errorf("expected ID 'bob', got '%s'", found.ID)
	}
}

// Sicherstellen: User ohne E-Mail-Feld wird nicht fälschlich gefunden.
func TestFindUserByEmailSkipsUserWithoutEmail(t *testing.T) {
	// GIVEN: User ohne E-Mail-Feld
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	user := model.User{
		ID:        "no-email-user",
		Email:     "", // kein E-Mail-Feld gesetzt
		CreatedAt: time.Now(),
	}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// WHEN: Suche mit leerer E-Mail → soll nie treffen
	found, err := s.FindUserByEmail("")

	// THEN: nil (leere E-Mail ist kein gültiger Suchschlüssel)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found != nil {
		t.Errorf("empty email search must return nil, got: %+v", found)
	}
}
