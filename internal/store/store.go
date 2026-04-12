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
