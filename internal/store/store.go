package store

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

type Store struct {
	DataDir string
	UserID  string
}

func New(dataDir, userID string) *Store {
	return &Store{DataDir: dataDir, UserID: userID}
}

func (s *Store) LocationsDir() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "locations")
}

func (s *Store) LoadLocations() ([]model.Location, error) {
	dir := s.LocationsDir()

	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return []model.Location{}, nil
		}
		return []model.Location{}, nil
	}

	var locations []model.Location
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			log.Printf("skip %s: read error: %v", entry.Name(), err)
			continue
		}

		var loc model.Location
		if err := json.Unmarshal(data, &loc); err != nil {
			log.Printf("skip %s: json error: %v", entry.Name(), err)
			continue
		}

		locations = append(locations, loc)
	}

	sort.Slice(locations, func(i, j int) bool {
		return locations[i].Name < locations[j].Name
	})

	if locations == nil {
		locations = []model.Location{}
	}

	return locations, nil
}

func (s *Store) TripsDir() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "trips")
}

func (s *Store) LoadTrips() ([]model.Trip, error) {
	dir := s.TripsDir()

	entries, err := os.ReadDir(dir)
	if err != nil {
		return []model.Trip{}, nil
	}

	var trips []model.Trip
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			log.Printf("skip %s: read error: %v", entry.Name(), err)
			continue
		}

		var trip model.Trip
		if err := json.Unmarshal(data, &trip); err != nil {
			log.Printf("skip %s: json error: %v", entry.Name(), err)
			continue
		}

		trips = append(trips, trip)
	}

	sort.Slice(trips, func(i, j int) bool {
		return trips[i].Name < trips[j].Name
	})

	if trips == nil {
		trips = []model.Trip{}
	}

	return trips, nil
}

func (s *Store) LoadTrip(id string) (*model.Trip, error) {
	path := filepath.Join(s.TripsDir(), id+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var trip model.Trip
	if err := json.Unmarshal(data, &trip); err != nil {
		return nil, err
	}

	return &trip, nil
}

func (s *Store) SaveTrip(trip model.Trip) error {
	dir := s.TripsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(trip, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(dir, trip.ID+".json"), data, 0644)
}

func (s *Store) DeleteTrip(id string) error {
	path := filepath.Join(s.TripsDir(), id+".json")
	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

func (s *Store) LoadLocation(id string) (*model.Location, error) {
	path := filepath.Join(s.LocationsDir(), id+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var loc model.Location
	if err := json.Unmarshal(data, &loc); err != nil {
		return nil, err
	}

	return &loc, nil
}

func (s *Store) SaveLocation(loc model.Location) error {
	dir := s.LocationsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(loc, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(dir, loc.ID+".json"), data, 0644)
}

func (s *Store) DeleteLocation(id string) error {
	path := filepath.Join(s.LocationsDir(), id+".json")
	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}
