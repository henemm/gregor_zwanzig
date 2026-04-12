package store

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadTripsFromRealData(t *testing.T) {
	repoRoot := filepath.Join("..", "..")
	s := New(filepath.Join(repoRoot, "data"), "default")

	trips, err := s.LoadTrips()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(trips) == 0 {
		t.Fatal("expected at least 1 trip from data/users/default/trips/")
	}

	trip := trips[0]
	if trip.ID == "" {
		t.Error("expected trip to have an ID")
	}
	if trip.Name == "" {
		t.Error("expected trip to have a name")
	}
	if len(trip.Stages) == 0 {
		t.Error("expected trip to have at least 1 stage")
	}

	stage := trip.Stages[0]
	if stage.ID == "" {
		t.Error("expected stage to have an ID")
	}
	if stage.Date == "" {
		t.Error("expected stage to have a date")
	}
	if len(stage.Waypoints) == 0 {
		t.Error("expected stage to have at least 1 waypoint")
	}

	wp := stage.Waypoints[0]
	if wp.Lat == 0 && wp.Lon == 0 {
		t.Error("expected waypoint to have coordinates")
	}
}

func TestLoadTripsEmptyDir(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	os.MkdirAll(tripDir, 0755)

	s := New(tmpDir, "test")
	trips, err := s.LoadTrips()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(trips) != 0 {
		t.Errorf("expected empty slice, got %d trips", len(trips))
	}
}

func TestLoadTripsBadJSON(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	os.MkdirAll(tripDir, 0755)

	os.WriteFile(filepath.Join(tripDir, "good.json"), []byte(`{
		"id": "good", "name": "Good Trip",
		"stages": [{"id":"S1","name":"Stage 1","date":"2026-04-13","waypoints":[
			{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}
		]}]
	}`), 0644)
	os.WriteFile(filepath.Join(tripDir, "bad.json"), []byte(`{broken`), 0644)

	s := New(tmpDir, "test")
	trips, err := s.LoadTrips()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(trips) != 1 {
		t.Fatalf("expected 1 trip (bad skipped), got %d", len(trips))
	}
	if trips[0].ID != "good" {
		t.Errorf("expected id 'good', got %s", trips[0].ID)
	}
}

func TestLoadTripByID(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	os.MkdirAll(tripDir, 0755)

	os.WriteFile(filepath.Join(tripDir, "my-trip.json"), []byte(`{
		"id": "my-trip", "name": "My Trip",
		"stages": [{"id":"S1","name":"Day 1","date":"2026-05-01","waypoints":[
			{"id":"W1","name":"Hut","lat":47.0,"lon":11.0,"elevation_m":1200}
		]}]
	}`), 0644)

	s := New(tmpDir, "test")
	trip, err := s.LoadTrip("my-trip")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if trip == nil {
		t.Fatal("expected trip, got nil")
	}
	if trip.ID != "my-trip" {
		t.Errorf("expected id 'my-trip', got %s", trip.ID)
	}
	if trip.Name != "My Trip" {
		t.Errorf("expected name 'My Trip', got %s", trip.Name)
	}
}

func TestLoadTripNotFound(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	os.MkdirAll(tripDir, 0755)

	s := New(tmpDir, "test")
	trip, err := s.LoadTrip("nonexistent")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if trip != nil {
		t.Errorf("expected nil for nonexistent trip, got %+v", trip)
	}
}
