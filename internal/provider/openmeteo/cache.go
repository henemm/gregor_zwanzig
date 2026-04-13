package openmeteo

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type ModelAvailability struct {
	Available   []string `json:"available"`
	Unavailable []string `json:"unavailable"`
}

type AvailabilityCache struct {
	ProbeDate string                       `json:"probe_date"`
	Models    map[string]ModelAvailability `json:"models"`
}

var cacheMu sync.Mutex

const cacheTTLDays = 7

func LoadAvailabilityCache(path string) (*AvailabilityCache, error) {
	cacheMu.Lock()
	defer cacheMu.Unlock()

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var cache AvailabilityCache
	if err := json.Unmarshal(data, &cache); err != nil {
		return nil, nil
	}

	probeDate, err := time.Parse("2006-01-02", cache.ProbeDate)
	if err != nil {
		return nil, nil
	}

	if time.Since(probeDate) > time.Duration(cacheTTLDays)*24*time.Hour {
		return nil, nil
	}

	return &cache, nil
}

func SaveAvailabilityCache(path string, cache *AvailabilityCache) error {
	cacheMu.Lock()
	defer cacheMu.Unlock()

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(cache, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(path, data, 0644)
}
