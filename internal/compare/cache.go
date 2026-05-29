package compare

import (
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

const cacheTTL = 15 * time.Minute

// cacheKey identifies a single compare result entry. Profile is part of the
// key because winner-tags and downstream UI depend on it.
// Issue #454: Date → DateFrom/DateTo/HourFrom/HourTo for multi-day windows.
type cacheKey struct {
	LocationID string
	DateFrom   string
	DateTo     string
	HourFrom   int
	HourTo     int
	Profile    ActivityProfile
}

// cacheEntry stores the data needed to reconstruct a CompareRow without
// re-fetching from the provider, plus the hourly timeseries for the same day.
type cacheEntry struct {
	summary model.SegmentWeatherSummary
	hourly  []model.ForecastDataPoint
	storedAt time.Time
}

// resultCache is a small in-memory cache with TTL-based eviction on read.
type resultCache struct {
	mu      sync.RWMutex
	entries map[cacheKey]cacheEntry
}

func newResultCache() *resultCache {
	return &resultCache{entries: make(map[cacheKey]cacheEntry)}
}

// get returns (entry, true) if a fresh entry exists, otherwise (_, false).
func (c *resultCache) get(k cacheKey) (cacheEntry, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.entries[k]
	if !ok {
		return cacheEntry{}, false
	}
	if time.Since(e.storedAt) > cacheTTL {
		return cacheEntry{}, false
	}
	return e, true
}

// set stores a fresh entry, replacing any previous value.
func (c *resultCache) set(k cacheKey, summary model.SegmentWeatherSummary, hourly []model.ForecastDataPoint) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries[k] = cacheEntry{
		summary:  summary,
		hourly:   hourly,
		storedAt: time.Now(),
	}
}
