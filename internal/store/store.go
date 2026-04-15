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

// WithUser returns a shallow copy of the Store with a different UserID.
// Empty userId is a no-op: returns the original Store unchanged.
func (s *Store) WithUser(userId string) *Store {
	if userId == "" {
		return s
	}
	copy := *s
	copy.UserID = userId
	return &copy
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

// --- Subscriptions (single-file storage) ---

func (s *Store) SubscriptionsDir() string {
	return filepath.Join(s.DataDir, "users", s.UserID)
}

func (s *Store) subscriptionsFile() string {
	return filepath.Join(s.SubscriptionsDir(), "compare_subscriptions.json")
}

func (s *Store) LoadSubscriptions() ([]model.CompareSubscription, error) {
	data, err := os.ReadFile(s.subscriptionsFile())
	if err != nil {
		if os.IsNotExist(err) {
			return []model.CompareSubscription{}, nil
		}
		return nil, err
	}

	var wrapper struct {
		Subscriptions []model.CompareSubscription `json:"subscriptions"`
	}
	if err := json.Unmarshal(data, &wrapper); err != nil {
		return nil, err
	}

	for i := range wrapper.Subscriptions {
		if wrapper.Subscriptions[i].Schedule == "weekly_friday" {
			wrapper.Subscriptions[i].Schedule = "weekly"
			wrapper.Subscriptions[i].Weekday = 4
		}
		if wrapper.Subscriptions[i].Locations == nil {
			wrapper.Subscriptions[i].Locations = []string{}
		}
	}

	if wrapper.Subscriptions == nil {
		wrapper.Subscriptions = []model.CompareSubscription{}
	}

	return wrapper.Subscriptions, nil
}

func (s *Store) LoadSubscription(id string) (*model.CompareSubscription, error) {
	subs, err := s.LoadSubscriptions()
	if err != nil {
		return nil, err
	}
	for _, sub := range subs {
		if sub.ID == id {
			return &sub, nil
		}
	}
	return nil, nil
}

func (s *Store) SaveSubscription(sub model.CompareSubscription) error {
	subs, err := s.LoadSubscriptions()
	if err != nil {
		return err
	}

	found := false
	for i, existing := range subs {
		if existing.ID == sub.ID {
			subs[i] = sub
			found = true
			break
		}
	}
	if !found {
		subs = append(subs, sub)
	}

	return s.saveSubscriptions(subs)
}

func (s *Store) DeleteSubscription(id string) error {
	subs, err := s.LoadSubscriptions()
	if err != nil {
		return err
	}

	var filtered []model.CompareSubscription
	for _, sub := range subs {
		if sub.ID != id {
			filtered = append(filtered, sub)
		}
	}
	if filtered == nil {
		filtered = []model.CompareSubscription{}
	}

	return s.saveSubscriptions(filtered)
}

func (s *Store) saveSubscriptions(subs []model.CompareSubscription) error {
	dir := s.SubscriptionsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	wrapper := struct {
		Subscriptions []model.CompareSubscription `json:"subscriptions"`
	}{Subscriptions: subs}

	data, err := json.MarshalIndent(wrapper, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(s.subscriptionsFile(), data, 0644)
}
