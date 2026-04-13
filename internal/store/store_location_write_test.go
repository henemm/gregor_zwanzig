package store

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestSaveLocationAndLoad(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	elev := 1200
	loc := model.Location{
		ID: "save-test", Name: "Save Test", Lat: 47.0, Lon: 11.0, ElevationM: &elev,
	}

	if err := s.SaveLocation(loc); err != nil {
		t.Fatalf("SaveLocation failed: %v", err)
	}

	loaded, err := s.LoadLocation("save-test")
	if err != nil {
		t.Fatalf("LoadLocation failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected location, got nil")
	}
	if loaded.Name != "Save Test" {
		t.Errorf("expected name 'Save Test', got %s", loaded.Name)
	}
}

func TestDeleteLocation(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	loc := model.Location{ID: "del-test", Name: "Delete Me", Lat: 47.0, Lon: 11.0}
	s.SaveLocation(loc)

	if err := s.DeleteLocation("del-test"); err != nil {
		t.Fatalf("DeleteLocation failed: %v", err)
	}

	loaded, _ := s.LoadLocation("del-test")
	if loaded != nil {
		t.Error("expected nil after delete")
	}
}

func TestDeleteLocationNotFound(t *testing.T) {
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)

	s := New(tmpDir, "test")
	err := s.DeleteLocation("nonexistent")
	if err != nil {
		t.Errorf("expected no error for nonexistent location, got %v", err)
	}
}

func TestLoadLocation(t *testing.T) {
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)
	os.WriteFile(filepath.Join(locDir, "my-loc.json"), []byte(`{"id":"my-loc","name":"My Loc","lat":47.5,"lon":11.5}`), 0644)

	s := New(tmpDir, "test")
	loc, err := s.LoadLocation("my-loc")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if loc == nil {
		t.Fatal("expected location, got nil")
	}
	if loc.ID != "my-loc" {
		t.Errorf("expected id 'my-loc', got %s", loc.ID)
	}
}

func TestLoadLocationNotFound(t *testing.T) {
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)

	s := New(tmpDir, "test")
	loc, err := s.LoadLocation("ghost")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if loc != nil {
		t.Errorf("expected nil, got %+v", loc)
	}
}
