package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

// ListUserIDs returns the IDs of all registered users.
// A valid user directory must contain a user.json file.
// Returns an empty slice if the users directory does not exist.
func (s *Store) ListUserIDs() ([]string, error) {
	usersDir := filepath.Join(s.DataDir, "users")
	entries, err := os.ReadDir(usersDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, fmt.Errorf("read users dir: %w", err)
	}

	var ids []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		userJSON := filepath.Join(usersDir, e.Name(), "user.json")
		if _, err := os.Stat(userJSON); err == nil {
			ids = append(ids, e.Name())
		}
	}
	if ids == nil {
		ids = []string{}
	}
	return ids, nil
}

// UserDir returns the directory for a specific user.
// Uses explicit id parameter, NOT s.UserID — user records are global.
func (s *Store) UserDir(id string) string {
	return filepath.Join(s.DataDir, "users", id)
}

func (s *Store) LoadUser(id string) (*model.User, error) {
	path := filepath.Join(s.UserDir(id), "user.json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var user model.User
	if err := json.Unmarshal(data, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

func (s *Store) SaveUser(user model.User) error {
	dir := s.UserDir(user.ID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(user, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(dir, "user.json"), data, 0644)
}

// ProvisionUserDirs creates the standard subdirectories for a new user.
func (s *Store) ProvisionUserDirs(id string) error {
	base := s.UserDir(id)
	for _, sub := range []string{"locations", "trips", "gpx", "weather_snapshots"} {
		if err := os.MkdirAll(filepath.Join(base, sub), 0755); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) SaveResetToken(userId string, token model.PasswordResetToken) error {
	dir := s.UserDir(userId)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(token, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "password_reset.json"), data, 0644)
}

func (s *Store) LoadResetToken(userId string) (*model.PasswordResetToken, error) {
	path := filepath.Join(s.UserDir(userId), "password_reset.json")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var token model.PasswordResetToken
	if err := json.Unmarshal(data, &token); err != nil {
		return nil, err
	}
	return &token, nil
}

func (s *Store) DeleteResetToken(userId string) error {
	path := filepath.Join(s.UserDir(userId), "password_reset.json")
	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

func (s *Store) DeleteUser(id string) error {
	dir := s.UserDir(id)
	return os.RemoveAll(dir)
}

func (s *Store) UserExists(id string) bool {
	path := filepath.Join(s.UserDir(id), "user.json")
	_, err := os.Stat(path)
	return err == nil
}
