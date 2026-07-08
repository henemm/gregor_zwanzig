package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

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

	return writeFileLogged(s.subscriptionsFile(), data)
}
