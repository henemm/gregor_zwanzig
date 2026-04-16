package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

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

func (s *Store) UserExists(id string) bool {
	path := filepath.Join(s.UserDir(id), "user.json")
	_, err := os.Stat(path)
	return err == nil
}
