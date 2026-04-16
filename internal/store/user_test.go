package store

import (
	"os"
	"path/filepath"
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
