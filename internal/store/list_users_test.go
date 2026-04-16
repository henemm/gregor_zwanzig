package store

import (
	"os"
	"path/filepath"
	"sort"
	"testing"
)

// TDD RED: Tests for ListUserIDs — must FAIL until implemented.

func TestListUserIDs_ReturnsRegisteredUsers(t *testing.T) {
	// GIVEN: Store with two users that have user.json
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	for _, id := range []string{"alice", "bob"} {
		dir := filepath.Join(tmpDir, "users", id)
		os.MkdirAll(dir, 0755)
		os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"`+id+`"}`), 0644)
	}

	// WHEN: Listing user IDs
	ids, err := s.ListUserIDs()

	// THEN: Returns both users
	if err != nil {
		t.Fatalf("ListUserIDs error: %v", err)
	}
	sort.Strings(ids)
	if len(ids) != 2 || ids[0] != "alice" || ids[1] != "bob" {
		t.Fatalf("Expected [alice bob], got %v", ids)
	}
}

func TestListUserIDs_IgnoresDirsWithoutUserJSON(t *testing.T) {
	// GIVEN: Users dir with one valid and one invalid directory
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// alice has user.json
	aliceDir := filepath.Join(tmpDir, "users", "alice")
	os.MkdirAll(aliceDir, 0755)
	os.WriteFile(filepath.Join(aliceDir, "user.json"), []byte(`{"id":"alice"}`), 0644)

	// orphan has no user.json
	os.MkdirAll(filepath.Join(tmpDir, "users", "orphan"), 0755)

	// WHEN: Listing user IDs
	ids, err := s.ListUserIDs()

	// THEN: Only alice returned
	if err != nil {
		t.Fatalf("ListUserIDs error: %v", err)
	}
	if len(ids) != 1 || ids[0] != "alice" {
		t.Fatalf("Expected [alice], got %v", ids)
	}
}

func TestListUserIDs_EmptyUsersDir(t *testing.T) {
	// GIVEN: Empty users directory
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")
	os.MkdirAll(filepath.Join(tmpDir, "users"), 0755)

	// WHEN: Listing user IDs
	ids, err := s.ListUserIDs()

	// THEN: Empty slice, no error
	if err != nil {
		t.Fatalf("ListUserIDs error: %v", err)
	}
	if len(ids) != 0 {
		t.Fatalf("Expected empty slice, got %v", ids)
	}
}

func TestListUserIDs_NoUsersDir(t *testing.T) {
	// GIVEN: No users directory at all
	tmpDir := t.TempDir()
	s := New(tmpDir, "default")

	// WHEN: Listing user IDs
	ids, err := s.ListUserIDs()

	// THEN: Empty slice, no error
	if err != nil {
		t.Fatalf("ListUserIDs error: %v", err)
	}
	if len(ids) != 0 {
		t.Fatalf("Expected empty slice, got %v", ids)
	}
}
