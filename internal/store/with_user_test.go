package store

import (
	"os"
	"path/filepath"
	"testing"
)

// TDD RED: Tests for Store.WithUser() — must FAIL until implemented.

func TestWithUserReturnsNewStoreWithDifferentUserID(t *testing.T) {
	// GIVEN: A store initialized with "default"
	s := New("/tmp/test", "default")

	// WHEN: WithUser is called with "alice"
	scoped := s.WithUser("alice")

	// THEN: New store has UserID "alice", original unchanged
	if scoped.UserID != "alice" {
		t.Errorf("expected UserID 'alice', got '%s'", scoped.UserID)
	}
	if s.UserID != "default" {
		t.Errorf("original store should still be 'default', got '%s'", s.UserID)
	}
}

func TestWithUserEmptyStringIsNoop(t *testing.T) {
	// GIVEN: A store with UserID "default"
	s := New("/tmp/test", "default")

	// WHEN: WithUser is called with empty string
	scoped := s.WithUser("")

	// THEN: Returns same store, UserID unchanged
	if scoped.UserID != "default" {
		t.Errorf("expected UserID 'default' for empty input, got '%s'", scoped.UserID)
	}
}

func TestWithUserPreservesDataDir(t *testing.T) {
	// GIVEN: A store with specific DataDir
	s := New("/data/gregor", "default")

	// WHEN: WithUser is called
	scoped := s.WithUser("bob")

	// THEN: DataDir is preserved
	if scoped.DataDir != "/data/gregor" {
		t.Errorf("expected DataDir '/data/gregor', got '%s'", scoped.DataDir)
	}
}

func TestWithUserIsolatesFilePaths(t *testing.T) {
	// GIVEN: A store and two users
	tmpDir := t.TempDir()
	base := New(tmpDir, "default")

	// Create data for user "alice"
	aliceStore := base.WithUser("alice")
	aliceDir := filepath.Join(tmpDir, "users", "alice", "locations")
	os.MkdirAll(aliceDir, 0755)
	os.WriteFile(filepath.Join(aliceDir, "loc1.json"),
		[]byte(`{"id":"loc1","name":"Alice Location","lat":47.0,"lon":11.0}`), 0644)

	// Create data for user "bob" (different location)
	bobStore := base.WithUser("bob")
	bobDir := filepath.Join(tmpDir, "users", "bob", "locations")
	os.MkdirAll(bobDir, 0755)
	os.WriteFile(filepath.Join(bobDir, "loc2.json"),
		[]byte(`{"id":"loc2","name":"Bob Location","lat":48.0,"lon":12.0}`), 0644)

	// WHEN: Each user loads their locations
	aliceLocs, err := aliceStore.LoadLocations()
	if err != nil {
		t.Fatalf("alice load error: %v", err)
	}
	bobLocs, err := bobStore.LoadLocations()
	if err != nil {
		t.Fatalf("bob load error: %v", err)
	}

	// THEN: Each user sees only their own data
	if len(aliceLocs) != 1 {
		t.Fatalf("alice: expected 1 location, got %d", len(aliceLocs))
	}
	if aliceLocs[0].Name != "Alice Location" {
		t.Errorf("alice: expected 'Alice Location', got '%s'", aliceLocs[0].Name)
	}

	if len(bobLocs) != 1 {
		t.Fatalf("bob: expected 1 location, got %d", len(bobLocs))
	}
	if bobLocs[0].Name != "Bob Location" {
		t.Errorf("bob: expected 'Bob Location', got '%s'", bobLocs[0].Name)
	}
}
