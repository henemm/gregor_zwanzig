package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED: Tests for User store methods — must FAIL until implemented.

func TestSaveUserCreatesFile(t *testing.T) {
	// GIVEN: Empty store
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// WHEN: Saving a user
	user := model.User{ID: "alice", PasswordHash: "$2a$10$fakehash"}
	err := s.SaveUser(user)

	// THEN: user.json exists in data/users/alice/
	if err != nil {
		t.Fatalf("SaveUser error: %v", err)
	}
	path := filepath.Join(tmpDir, "users", "alice", "user.json")
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Error("user.json should exist after SaveUser")
	}
}

func TestLoadUserReturnsUser(t *testing.T) {
	// GIVEN: A saved user
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	dir := filepath.Join(tmpDir, "users", "testuser")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"testuser","password_hash":"$2a$10$hash","created_at":"2026-04-15T00:00:00Z"}`), 0644)

	// WHEN: Loading the user
	user, err := s.LoadUser("testuser")

	// THEN: User is returned with correct fields
	if err != nil {
		t.Fatalf("LoadUser error: %v", err)
	}
	if user == nil {
		t.Fatal("expected user, got nil")
	}
	if user.ID != "testuser" {
		t.Errorf("expected ID 'testuser', got '%s'", user.ID)
	}
	if user.PasswordHash != "$2a$10$hash" {
		t.Errorf("expected hash, got '%s'", user.PasswordHash)
	}
}

func TestLoadUserNotFoundReturnsNil(t *testing.T) {
	// GIVEN: No users
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// WHEN: Loading non-existent user
	user, err := s.LoadUser("nobody")

	// THEN: nil, nil (no error)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if user != nil {
		t.Error("expected nil user for non-existent user")
	}
}

func TestUserExistsTrue(t *testing.T) {
	// GIVEN: A saved user
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	dir := filepath.Join(tmpDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{}`), 0644)

	// THEN: UserExists returns true
	if !s.UserExists("alice") {
		t.Error("expected UserExists to return true")
	}
}

func TestUserExistsFalse(t *testing.T) {
	// GIVEN: No users
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// THEN: UserExists returns false
	if s.UserExists("ghost") {
		t.Error("expected UserExists to return false")
	}
}

// ---------------------------------------------------------------------------
// TDD RED — Issue #2152, AC-7 (FindUserByTelegramChatID) + AC-8 (Persistenz-
// Roundtrip). Spec: docs/specs/modules/testkonto_profilfeld.md
//
// Bewusst KEIN neues Symbol referenziert (kein u.IsTestUser): Profile werden
// als Roh-JSON angelegt und nach dem Roundtrip als map[string]any gegengelesen.
// Das RED ist damit eine Assertion, kein Compile-Fehler — der heutige Verlust
// des Feldes durch SaveUser (Replace-Semantik, BUG-DATALOSS-GR221) wird auf
// Dateiebene sichtbar. GREEN: model.User.IsTestUser (json:"is_test_user,
// omitempty") und FindUserByTelegramChatID prueft model.IsTestAccount(u) am
// bereits geladenen Profil statt model.IsTestUserID(id).
// ---------------------------------------------------------------------------

func writeRawUserJSON(t *testing.T, dataDir, id, body string) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", id)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(body), 0644); err != nil {
		t.Fatalf("write user.json: %v", err)
	}
}

func readRawUserJSON(t *testing.T, dataDir, id string) map[string]any {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(dataDir, "users", id, "user.json"))
	if err != nil {
		t.Fatalf("read user.json: %v", err)
	}
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal user.json: %v", err)
	}
	return m
}

// TestFindUserByTelegramChatID_ProtesterOhneFlagWirdGefunden_AC7 — Konto mit
// "test" im Namen, aber ohne Flag, ist ein echter Nutzer und wird per Chat-ID
// gefunden.
func TestFindUserByTelegramChatID_ProtesterOhneFlagWirdGefunden_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	writeRawUserJSON(t, tmpDir, "protester",
		`{"id":"protester","telegram_chat_id":"555111","mail_to":"protester@example.com"}`)

	u, err := s.FindUserByTelegramChatID("555111")
	if err != nil {
		t.Fatalf("FindUserByTelegramChatID: %v", err)
	}
	if u == nil || u.ID != "protester" {
		t.Fatalf("AC-7: protester (ohne Flag) muss per Chat-ID gefunden werden, got %+v", u)
	}
}

// TestFindUserByTelegramChatID_FlaggedNeutralNameWirdUebersprungen_AC7 —
// Gegenprobe: neutraler Name mit is_test_user=true wird uebersprungen, der
// echte Nutzer mit derselben Chat-ID gewinnt.
func TestFindUserByTelegramChatID_FlaggedNeutralNameWirdUebersprungen_AC7(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	writeRawUserJSON(t, tmpDir, "mitarbeiter42",
		`{"id":"mitarbeiter42","telegram_chat_id":"777666","is_test_user":true}`)

	u, err := s.FindUserByTelegramChatID("777666")
	if err != nil {
		t.Fatalf("FindUserByTelegramChatID: %v", err)
	}
	if u != nil {
		t.Fatalf("AC-7: mitarbeiter42 (is_test_user=true) darf NICHT gefunden werden, got %+v", u)
	}
}

// TestSaveUserLoadUser_RoundtripErhaeltIsTestUserUndNachbarfelder_AC8 —
// user.json mit is_test_user:true und Nachbarfeldern → LoadUser → SaveUser →
// Datei gegenlesen: Flag UND alle uebrigen Felder unveraendert.
func TestSaveUserLoadUser_RoundtripErhaeltIsTestUserUndNachbarfelder_AC8(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	writeRawUserJSON(t, tmpDir, "mitarbeiter42", `{
		"id":"mitarbeiter42",
		"email":"m42@example.com",
		"mail_to":"m42-briefing@example.com",
		"sms_to":"+491700000042",
		"telegram_chat_id":"424242",
		"display_name":"M 42",
		"tier":"basic",
		"created_at":"2026-09-17T10:00:00Z",
		"email_verified_at":"2026-09-17T11:00:00Z",
		"passkey_prompt_dismissed":true,
		"is_test_user":true
	}`)
	before := readRawUserJSON(t, tmpDir, "mitarbeiter42")

	u, err := s.LoadUser("mitarbeiter42")
	if err != nil || u == nil {
		t.Fatalf("LoadUser: %v / %+v", err, u)
	}
	if err := s.SaveUser(*u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	after := readRawUserJSON(t, tmpDir, "mitarbeiter42")

	if after["is_test_user"] != true {
		t.Errorf("AC-8: is_test_user ging beim LoadUser/SaveUser-Roundtrip verloren "+
			"(Replace-Semantik, BUG-DATALOSS-GR221): after=%v", after["is_test_user"])
	}
	for key, want := range before {
		if got, ok := after[key]; !ok || !reflect.DeepEqual(got, want) {
			t.Errorf("AC-8: Feld %q veraendert: before=%v after=%v (ok=%v)", key, want, got, ok)
		}
	}
	for key := range after {
		if _, ok := before[key]; !ok {
			t.Errorf("AC-8: Roundtrip fuegte unerwartetes Feld %q hinzu: %v", key, after[key])
		}
	}
}

// TestSaveUser_OhneFlagSchreibtKeinIsTestUser_AC8 — bei fehlendem Flag darf der
// Schluessel nicht als "false" auftauchen (omitempty), Bestandsdaten bleiben
// wie sie sind.
func TestSaveUser_OhneFlagSchreibtKeinIsTestUser_AC8(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	if err := s.SaveUser(model.User{ID: "henning", Email: "h@example.com"}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	after := readRawUserJSON(t, tmpDir, "henning")
	if v, ok := after["is_test_user"]; ok {
		t.Errorf("AC-8: ohne Flag darf is_test_user nicht geschrieben werden, got %v", v)
	}
}
