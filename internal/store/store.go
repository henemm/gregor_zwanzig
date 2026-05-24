package store

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

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

		// Issue #205 Follow-Up: Read-Path-Coercion symmetrisch zu SaveTrip,
		// damit API niemals "alert_rules":null zurückgibt.
		if trip.AlertRules == nil {
			trip.AlertRules = []model.AlertRule{}
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

	// Issue #205 Follow-Up: Read-Path-Coercion symmetrisch zu SaveTrip,
	// damit API niemals "alert_rules":null zurückgibt.
	if trip.AlertRules == nil {
		trip.AlertRules = []model.AlertRule{}
	}

	return &trip, nil
}

func (s *Store) SaveTrip(trip model.Trip) error {
	dir := s.TripsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Issue #205 F002: Nil-Coercion verhindert "alert_rules":null im JSON,
	// das beim nächsten Python-Load die Legacy-Migration erneut triggern würde.
	if trip.AlertRules == nil {
		trip.AlertRules = []model.AlertRule{}
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

// --- MetricPresets (Epic #138 Issue #177) ---

// PresetsFile gibt den Pfad zur Preset-Datei des aktuellen Users zurück.
func (s *Store) PresetsFile() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "metric_presets.json")
}

// LoadMetricPresets lädt alle User-Presets. Gibt leeren Slice (nicht nil)
// zurück wenn die Datei nicht existiert (Erst-Aufruf).
//
// Issue #342: Zwei-Phasen-Decode mit Legacy-Migration. Bestehende Presets im
// alten Schema ({metrics:[]string, friendly_ids:[]string}) werden lazy in
// das neue Schema ([]DisplayMetric mit horizons-Defaults) ueberfuehrt; das
// JSON auf der Platte bleibt unveraendert bis zum naechsten Save.
func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error) {
	data, err := os.ReadFile(s.PresetsFile())
	if err != nil {
		if os.IsNotExist(err) {
			return []model.MetricPreset{}, nil
		}
		return nil, err
	}
	var rawPresets []map[string]interface{}
	if err := json.Unmarshal(data, &rawPresets); err != nil {
		return nil, fmt.Errorf("metric_presets.json korrupt: %w", err)
	}
	presets := make([]model.MetricPreset, 0, len(rawPresets))
	for _, rp := range rawPresets {
		presets = append(presets, migrateMetricPreset(rp))
	}
	return presets, nil
}

// migrateMetricPreset fuehrt die Schema-Migration eines einzelnen Preset-
// Datensatzes durch. Erkennt drei Layouts:
//   - Legacy: metrics ist []string + paralleler friendly_ids
//   - Neu:    metrics ist []map mit metric_id/enabled/use_friendly_format/horizons
//   - Mischform: Neu-Schema ohne horizons-Feld -> Default {true,true,true}.
//
// Fehlende horizons-Felder werden auf {Today:true, Tomorrow:true,
// DayAfter:true} defaultet (= altes Verhalten, alle Tage sichtbar).
func migrateMetricPreset(rp map[string]interface{}) model.MetricPreset {
	allTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}

	p := model.MetricPreset{Metrics: []model.DisplayMetric{}}
	if v, ok := rp["id"].(string); ok {
		p.ID = v
	}
	if v, ok := rp["name"].(string); ok {
		p.Name = v
	}
	if v, ok := rp["description"].(string); ok {
		p.Description = v
	}
	if v, ok := rp["is_default"].(bool); ok {
		p.IsDefault = v
	}
	if v, ok := rp["created_at"].(string); ok {
		if ts, err := time.Parse(time.RFC3339, v); err == nil {
			p.CreatedAt = ts
		}
	}

	// Friendly-IDs aus Legacy-Layout extrahieren (Set fuer O(1) Lookup).
	friendlySet := map[string]bool{}
	if rawFIDs, ok := rp["friendly_ids"].([]interface{}); ok {
		for _, fid := range rawFIDs {
			if s, ok := fid.(string); ok {
				friendlySet[s] = true
			}
		}
	}

	rawMetrics, _ := rp["metrics"].([]interface{})
	for _, rm := range rawMetrics {
		// Legacy-Pfad: metric_id als String.
		if id, ok := rm.(string); ok {
			p.Metrics = append(p.Metrics, model.DisplayMetric{
				MetricID:          id,
				Enabled:           true,
				UseFriendlyFormat: friendlySet[id],
				Horizons:          allTrue,
			})
			continue
		}
		// Neu/Mischform-Pfad: metric_id als Map.
		m, ok := rm.(map[string]interface{})
		if !ok {
			continue
		}
		dm := model.DisplayMetric{Horizons: allTrue}
		if v, ok := m["metric_id"].(string); ok {
			dm.MetricID = v
		}
		if v, ok := m["enabled"].(bool); ok {
			dm.Enabled = v
		} else {
			dm.Enabled = true
		}
		if v, ok := m["use_friendly_format"].(bool); ok {
			dm.UseFriendlyFormat = v
		}
		if h, ok := m["horizons"].(map[string]interface{}); ok {
			if v, ok := h["today"].(bool); ok {
				dm.Horizons.Today = v
			}
			if v, ok := h["tomorrow"].(bool); ok {
				dm.Horizons.Tomorrow = v
			}
			if v, ok := h["day_after"].(bool); ok {
				dm.Horizons.DayAfter = v
			}
		}
		p.Metrics = append(p.Metrics, dm)
	}
	return p
}

// SaveMetricPresets schreibt alle Presets atomar.
func (s *Store) SaveMetricPresets(presets []model.MetricPreset) error {
	dir := filepath.Join(s.DataDir, "users", s.UserID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	if presets == nil {
		presets = []model.MetricPreset{}
	}
	data, err := json.MarshalIndent(presets, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.PresetsFile(), data, 0644)
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

// --- Groups (single-file storage) — Issue #341 ---

func (s *Store) groupsFile() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "groups.json")
}

// slugify mirrors handler.toKebab logic (lowercase, non-alphanumeric → "-",
// trimmed). Re-implemented locally to avoid an import cycle with the handler
// package.
func slugify(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	var b strings.Builder
	prevDash := false
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			prevDash = false
		} else if !prevDash {
			b.WriteByte('-')
			prevDash = true
		}
	}
	return strings.Trim(b.String(), "-")
}

// LoadGroups returns the user's groups sorted by Order. On first call (no
// groups.json yet) it triggers the one-time lazy migration (§4) that derives
// groups from distinct legacy Location.Group strings, persists groups.json and
// backfills group_id on the locations. Subsequent calls take the fast path.
func (s *Store) LoadGroups() ([]model.Group, error) {
	data, err := os.ReadFile(s.groupsFile())
	if err == nil {
		var wrapper struct {
			Groups []model.Group `json:"groups"`
		}
		if uerr := json.Unmarshal(data, &wrapper); uerr != nil {
			return nil, uerr
		}
		if wrapper.Groups == nil {
			wrapper.Groups = []model.Group{}
		}
		sort.Slice(wrapper.Groups, func(i, j int) bool {
			return wrapper.Groups[i].Order < wrapper.Groups[j].Order
		})
		return wrapper.Groups, nil
	}
	if !os.IsNotExist(err) {
		return nil, err
	}

	return s.migrateGroups()
}

// migrateGroups performs the one-time lazy migration (§4). Idempotency is
// guaranteed by the existence of groups.json after step 4.
func (s *Store) migrateGroups() ([]model.Group, error) {
	locations, err := s.LoadLocations()
	if err != nil {
		return nil, err
	}

	// Collect distinct, non-empty legacy group strings, alphabetically.
	seen := map[string]bool{}
	var names []string
	for _, loc := range locations {
		if loc.Group == nil {
			continue
		}
		name := *loc.Group
		if strings.TrimSpace(name) == "" || seen[name] {
			continue
		}
		seen[name] = true
		names = append(names, name)
	}
	sort.Strings(names)

	// Build groups with kebab IDs, dedup slug collisions via -2/-3 suffix.
	usedIDs := map[string]bool{}
	groups := make([]model.Group, 0, len(names))
	nameToID := map[string]string{}
	for i, name := range names {
		base := slugify(name)
		if base == "" {
			base = "group"
		}
		id := base
		for n := 2; usedIDs[id]; n++ {
			id = base + "-" + strconv.Itoa(n)
		}
		usedIDs[id] = true
		nameToID[name] = id
		groups = append(groups, model.Group{ID: id, Name: name, Order: i})
	}

	// Persist groups.json (also when empty → migration marker).
	if err := s.saveGroups(groups); err != nil {
		return nil, err
	}

	// Backfill group_id on locations (Read-Modify-Write, only group_id added).
	for _, loc := range locations {
		if loc.Group == nil {
			continue
		}
		gid, ok := nameToID[*loc.Group]
		if !ok {
			continue
		}
		existing, lerr := s.LoadLocation(loc.ID)
		if lerr != nil || existing == nil {
			continue
		}
		existing.GroupID = &gid
		if serr := s.SaveLocation(*existing); serr != nil {
			return nil, serr
		}
	}

	return groups, nil
}

func (s *Store) saveGroups(gs []model.Group) error {
	dir := filepath.Join(s.DataDir, "users", s.UserID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	if gs == nil {
		gs = []model.Group{}
	}

	wrapper := struct {
		Groups []model.Group `json:"groups"`
	}{Groups: gs}

	data, err := json.MarshalIndent(wrapper, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(s.groupsFile(), data, 0644)
}

// SaveGroup upserts a group by ID.
func (s *Store) SaveGroup(g model.Group) error {
	groups, err := s.LoadGroups()
	if err != nil {
		return err
	}

	found := false
	for i, existing := range groups {
		if existing.ID == g.ID {
			groups[i] = g
			found = true
			break
		}
	}
	if !found {
		groups = append(groups, g)
	}

	return s.saveGroups(groups)
}

// DeleteGroup removes a group by ID. Membership cleanup (group_id=nil on
// locations) is the handler's responsibility.
func (s *Store) DeleteGroup(id string) error {
	groups, err := s.LoadGroups()
	if err != nil {
		return err
	}

	var filtered []model.Group
	for _, g := range groups {
		if g.ID != id {
			filtered = append(filtered, g)
		}
	}
	if filtered == nil {
		filtered = []model.Group{}
	}

	return s.saveGroups(filtered)
}
