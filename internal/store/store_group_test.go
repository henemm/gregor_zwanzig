package store

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED: Issue #341 — Group-Entity + Lazy-Migration der Legacy-`group`-Strings.
// Spec: docs/specs/modules/issue_341_group_backend.md §3/§4
//
// Diese Tests referenzieren model.Group, model.Location.GroupID und
// Store.LoadGroups/SaveGroup/DeleteGroup — in RED existiert nichts davon, das
// Paket kompiliert nicht → alle Tests sind rot (Konvention wie #252).

func sptr(s string) *string { return &s }

// AC-1/AC-6: Lazy-Migration leitet aus distinkten Legacy-`group`-Strings Gruppen ab.
func TestLoadGroups_LazyMigrationDerivesGroups(t *testing.T) {
	s := New(t.TempDir(), "default")

	s.SaveLocation(model.Location{ID: "stubai", Name: "Stubaier", Lat: 47.1, Lon: 11.3, Group: sptr("Skigebiete Tirol")})
	s.SaveLocation(model.Location{ID: "hintertux", Name: "Hintertux", Lat: 47.0, Lon: 11.6, Group: sptr("Skigebiete Tirol")})
	s.SaveLocation(model.Location{ID: "nazare", Name: "Nazare", Lat: 39.6, Lon: -9.0, Group: sptr("Surfspots Portugal")})
	s.SaveLocation(model.Location{ID: "loner", Name: "Loner", Lat: 48.0, Lon: 12.0})

	groups, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}
	if len(groups) != 2 {
		t.Fatalf("expected 2 derived groups, got %d: %+v", len(groups), groups)
	}
	names := map[string]bool{}
	for _, g := range groups {
		names[g.Name] = true
		if g.ID == "" {
			t.Errorf("group %q has empty id", g.Name)
		}
	}
	if !names["Skigebiete Tirol"] || !names["Surfspots Portugal"] {
		t.Errorf("missing expected group names: %+v", groups)
	}
}

// AC-6: Migration backfillt group_id auf den Orten.
func TestLoadGroups_BackfillsGroupID(t *testing.T) {
	s := New(t.TempDir(), "default")
	s.SaveLocation(model.Location{ID: "stubai", Name: "Stubaier", Lat: 47.1, Lon: 11.3, Group: sptr("Skigebiete Tirol")})

	groups, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}
	if len(groups) != 1 {
		t.Fatalf("expected 1 group, got %d", len(groups))
	}

	loc, err := s.LoadLocation("stubai")
	if err != nil || loc == nil {
		t.Fatalf("LoadLocation: %v", err)
	}
	if loc.GroupID == nil {
		t.Fatal("expected group_id backfilled, got nil")
	}
	if *loc.GroupID != groups[0].ID {
		t.Errorf("group_id %q != group id %q", *loc.GroupID, groups[0].ID)
	}
}

// AC-6: Idempotenz — zweiter Aufruf erzeugt keine Duplikate.
func TestLoadGroups_Idempotent(t *testing.T) {
	s := New(t.TempDir(), "default")
	s.SaveLocation(model.Location{ID: "a", Name: "A", Lat: 47, Lon: 11, Group: sptr("G1")})
	s.SaveLocation(model.Location{ID: "b", Name: "B", Lat: 47, Lon: 11, Group: sptr("G1")})

	first, _ := s.LoadGroups()
	second, _ := s.LoadGroups()
	if len(first) != 1 || len(second) != 1 {
		t.Fatalf("expected 1 group both times, got %d then %d", len(first), len(second))
	}
	if first[0].ID != second[0].ID {
		t.Errorf("group id changed between loads: %q vs %q", first[0].ID, second[0].ID)
	}
}

// AC-7: Roundtrip — Anzahl Locations vor==nach Migration, kein verwaister FK.
func TestMigration_RoundtripPreservesLocationCount(t *testing.T) {
	s := New(t.TempDir(), "default")
	seed := []model.Location{
		{ID: "a", Name: "A", Lat: 47, Lon: 11, Group: sptr("Alpen")},
		{ID: "b", Name: "B", Lat: 47, Lon: 11, Group: sptr("Alpen")},
		{ID: "c", Name: "C", Lat: 39, Lon: -9, Group: sptr("Kueste")},
		{ID: "d", Name: "D", Lat: 48, Lon: 12},
	}
	for _, l := range seed {
		s.SaveLocation(l)
	}
	before, _ := s.LoadLocations()

	groups, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}

	after, _ := s.LoadLocations()
	if len(after) != len(before) {
		t.Fatalf("location count changed: before %d, after %d", len(before), len(after))
	}

	groupIDs := map[string]bool{}
	for _, g := range groups {
		groupIDs[g.ID] = true
	}
	for _, l := range after {
		if l.Group != nil && *l.Group != "" {
			if l.GroupID == nil {
				t.Errorf("location %q has legacy group but no group_id", l.ID)
				continue
			}
			if !groupIDs[*l.GroupID] {
				t.Errorf("location %q has dangling group_id %q", l.ID, *l.GroupID)
			}
		}
	}
}

// AC-8: Keine Locations, keine groups.json → LoadGroups liefert leeren Slice (kein Fehler, kein nil).
func TestLoadGroups_EmptyWhenNoLocations(t *testing.T) {
	s := New(t.TempDir(), "default")
	groups, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}
	if groups == nil {
		t.Fatal("expected empty slice, got nil")
	}
	if len(groups) != 0 {
		t.Errorf("expected 0 groups, got %d", len(groups))
	}
}

// Adversary F001 (Issue #341): Whitespace-only Group-String darf KEINE Gruppe erzeugen.
// Spec §4: "distinkte, nicht-leere Location.Group-Strings". "   " gilt als leer.
func TestLoadGroups_WhitespaceGroupStringIgnored(t *testing.T) {
	s := New(t.TempDir(), "default")
	s.SaveLocation(model.Location{ID: "ws", Name: "Whitespace", Lat: 47, Lon: 11, Group: sptr("   ")})
	s.SaveLocation(model.Location{ID: "empty", Name: "Empty", Lat: 47, Lon: 11, Group: sptr("")})

	groups, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}
	if len(groups) != 0 {
		t.Errorf("expected 0 groups for whitespace/empty strings, got %d: %+v", len(groups), groups)
	}

	loc, _ := s.LoadLocation("ws")
	if loc.GroupID != nil {
		t.Errorf("whitespace-group location must stay ungrouped, got group_id %q", *loc.GroupID)
	}
}

// Store-Roundtrip: SaveGroup/DeleteGroup.
func TestSaveAndDeleteGroup(t *testing.T) {
	s := New(t.TempDir(), "default")
	if _, err := s.LoadGroups(); err != nil {
		t.Fatalf("LoadGroups: %v", err)
	}
	if err := s.SaveGroup(model.Group{ID: "ski-tirol", Name: "Ski Tirol", Order: 0}); err != nil {
		t.Fatalf("SaveGroup: %v", err)
	}
	groups, _ := s.LoadGroups()
	found := false
	for _, x := range groups {
		if x.ID == "ski-tirol" {
			found = true
		}
	}
	if !found {
		t.Fatal("saved group not found")
	}
	if err := s.DeleteGroup("ski-tirol"); err != nil {
		t.Fatalf("DeleteGroup: %v", err)
	}
	groups, _ = s.LoadGroups()
	for _, x := range groups {
		if x.ID == "ski-tirol" {
			t.Error("group still present after delete")
		}
	}
}
