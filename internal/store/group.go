package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

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

	return writeFileLogged(s.groupsFile(), data)
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
