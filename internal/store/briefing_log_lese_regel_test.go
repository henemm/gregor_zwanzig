package store

// TDD RED — Issue #2281 (Epic #2345 P4): kind-neutraler Briefing-Log.
// SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md
// AC-3 (Zaehlschluessel), AC-4 (Lese-Regel statt Datei-Migration), Test 7.
//
// Vorlage: Alarm-Log-Lese-Regel #1467 (log.go LoadAlertLog) und deren Tests
// (internal/handler/alert_entity_id_test.go). Echte Dateien auf Platte, echter
// Store, keine Mocks. writeLogFile stammt aus archive_stats_test.go.

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// briefingLogPath liefert den Pfad, unter dem LoadBriefingLog liest.
func briefingLogPath(dataDir, userID string) string {
	return filepath.Join(dataDir, "users", userID, "briefing_log.json")
}

// AC-4: Ein Alt-Log nur mit trip_id wird beim Lesen uebersetzt — kein Eintrag
// geht verloren, jeder traegt entity_type="trip" und entity_id = alter trip_id,
// und die Datei auf der Platte bleibt byte-gleich (keine Datei-Migration).
func TestLoadBriefingLog_LegacyTripIDOnly_DerivesEntityFields_FileUntouched(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "alt", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "trip-A", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email", "telegram"}, "on_demand": true},
		{"trip_id": "trip-B", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"sms"}, "mail_to": "x@example.org"},
	})
	path := briefingLogPath(dataDir, "alt")
	before, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("Setup: %v", err)
	}

	entries, err := New(dataDir, "alt").LoadBriefingLog()
	if err != nil {
		t.Fatalf("LoadBriefingLog: %v", err)
	}
	if len(entries) != 3 {
		t.Fatalf("AC-4: 3 Eintraege erwartet (keiner darf verloren gehen), %d bekommen", len(entries))
	}
	for i, want := range []string{"trip-A", "trip-A", "trip-B"} {
		if entries[i].EntityID != want {
			t.Errorf("AC-4: Eintrag %d: EntityID=%q, erwartet %q (aus trip_id abgeleitet)", i, entries[i].EntityID, want)
		}
		if entries[i].EntityType != "trip" {
			t.Errorf("AC-4: Eintrag %d: EntityType=%q, erwartet \"trip\"", i, entries[i].EntityType)
		}
		if entries[i].TripID != want {
			t.Errorf("AC-4: Eintrag %d: TripID=%q, erwartet %q (Altfeld bleibt lesbar)", i, entries[i].TripID, want)
		}
	}
	if !entries[1].OnDemand {
		t.Errorf("AC-4: Eintrag 1 traegt on_demand=true auf Platte, Go liest %v", entries[1].OnDemand)
	}
	if entries[0].OnDemand {
		t.Errorf("AC-4: Eintrag 0 ohne on_demand muss false lesen, Go liest %v", entries[0].OnDemand)
	}

	after, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile nach dem Lesen: %v", err)
	}
	if !bytes.Equal(before, after) {
		t.Errorf("AC-4: briefing_log.json wurde beim Lesen veraendert (Lese-Regel, keine Migration):\nvorher:  %s\nnachher: %s", before, after)
	}
}

// AC-4 Roundtrip Datei -> Go -> JSON: die Ausgabe (so wie Cockpit/Historie sie
// serialisieren) enthaelt entity_type und entity_id fuer Alt-Eintraege.
func TestBriefingLogEntry_LegacyRoundtrip_MarshalCarriesEntityFields(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "alt", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "trip-R", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
	})

	entries, err := New(dataDir, "alt").LoadBriefingLog()
	if err != nil {
		t.Fatalf("LoadBriefingLog: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("1 Eintrag erwartet, %d bekommen", len(entries))
	}
	b, err := json.Marshal(entries[0])
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	var out map[string]interface{}
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	if out["entity_type"] != "trip" {
		t.Errorf("AC-4: JSON-Ausgabe entity_type=%v, erwartet \"trip\" (json=%s)", out["entity_type"], b)
	}
	if out["entity_id"] != "trip-R" {
		t.Errorf("AC-4: JSON-Ausgabe entity_id=%v, erwartet \"trip-R\" (json=%s)", out["entity_id"], b)
	}
	if out["kind"] != "morning" || out["sent_at"] != "2026-06-10T07:00:00Z" {
		t.Errorf("AC-4: kind/sent_at im Roundtrip verloren: %s", b)
	}
}

// Neue Eintraege: ein Compare-Eintrag ohne trip_id wird korrekt gelesen und
// beim Serialisieren erscheint KEIN trip_id (TripID wird omitempty).
func TestLoadBriefingLog_CompareEntryWithoutTripID(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "neu", "briefing_log.json", []map[string]interface{}{
		{"entity_id": "preset-P", "entity_type": "compare", "kind": "evening", "sent_at": "2026-06-12T18:00:00Z", "channels": []string{"telegram"}, "on_demand": false},
		{"entity_id": "trip-T", "entity_type": "trip", "trip_id": "trip-T", "kind": "morning", "sent_at": "2026-06-12T07:00:00Z", "channels": []string{"email"}, "on_demand": true},
	})

	entries, err := New(dataDir, "neu").LoadBriefingLog()
	if err != nil {
		t.Fatalf("LoadBriefingLog: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("2 Eintraege erwartet, %d bekommen", len(entries))
	}
	c := entries[0]
	if c.EntityType != "compare" {
		t.Errorf("Compare-Eintrag: EntityType=%q, erwartet \"compare\" (darf nicht auf \"trip\" kippen)", c.EntityType)
	}
	if c.EntityID != "preset-P" {
		t.Errorf("Compare-Eintrag: EntityID=%q, erwartet \"preset-P\"", c.EntityID)
	}
	if c.TripID != "" {
		t.Errorf("Compare-Eintrag: TripID=%q, erwartet leer", c.TripID)
	}
	if c.Kind != "evening" {
		t.Errorf("Compare-Eintrag: Kind=%q, erwartet \"evening\"", c.Kind)
	}
	b, err := json.Marshal(c)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	var out map[string]interface{}
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	if _, has := out["trip_id"]; has {
		t.Errorf("Compare-Eintrag serialisiert trip_id (TripID muss omitempty sein): %s", b)
	}
	if out["entity_type"] != "compare" || out["entity_id"] != "preset-P" {
		t.Errorf("Compare-Eintrag: entity-Felder fehlen in der JSON-Ausgabe: %s", b)
	}

	tr := entries[1]
	if tr.EntityType != "trip" || tr.EntityID != "trip-T" || tr.TripID != "trip-T" || !tr.OnDemand {
		t.Errorf("neuer Trip-Eintrag falsch gelesen: %+v", tr)
	}
}

// AC-3: BriefingCountByEntity zaehlt nach "<typ>:<kennung>"; gleiche ID bei
// Trip und Ortsvergleich ergibt zwei getrennte Zaehler. Alt-Eintraege zaehlen
// als "trip:<trip_id>". Kein nackter Schluessel, kein leerer Sammeltopf.
func TestBriefingCountByEntity_SameIDTripAndCompareCountedSeparately(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "mix", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "trip", "trip_id": "gleich", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": "2026-06-11T18:00:00Z", "channels": []string{"telegram"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-12T07:00:00Z", "channels": []string{"sms"}},
	})

	counts, err := New(dataDir, "mix").BriefingCountByEntity()
	if err != nil {
		t.Fatalf("BriefingCountByEntity: %v", err)
	}
	if counts["trip:gleich"] != 2 {
		t.Errorf("AC-3: trip:gleich=%d, erwartet 2 (Alt-Eintrag + neuer Trip-Eintrag)", counts["trip:gleich"])
	}
	if counts["compare:gleich"] != 3 {
		t.Errorf("AC-3: compare:gleich=%d, erwartet 3", counts["compare:gleich"])
	}
	if len(counts) != 2 {
		t.Errorf("AC-3: genau 2 Schluessel erwartet, bekommen %v", counts)
	}
	for _, bad := range []string{"gleich", "", ":", "trip:", "compare:"} {
		if _, has := counts[bad]; has {
			t.Errorf("AC-3: unerwarteter Schluessel %q in %v", bad, counts)
		}
	}
}

// AC-3/AC-8: Zaehlung bleibt strikt pro Nutzer — gleichlautende IDs bei zwei
// Nutzern vermischen sich nicht.
func TestBriefingCountByEntity_IsolatedPerUser(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "userA", "briefing_log.json", []map[string]interface{}{
		{"entity_id": "x", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"email"}},
	})
	writeLogFile(t, dataDir, "userB", "briefing_log.json", []map[string]interface{}{
		{"entity_id": "x", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"email"}},
		{"entity_id": "x", "entity_type": "compare", "kind": "evening", "sent_at": "2026-06-11T18:00:00Z", "channels": []string{"email"}},
	})
	base := New(dataDir, "irrelevant")
	a, err := base.WithUser("userA").BriefingCountByEntity()
	if err != nil {
		t.Fatal(err)
	}
	b, err := base.WithUser("userB").BriefingCountByEntity()
	if err != nil {
		t.Fatal(err)
	}
	if a["compare:x"] != 1 || b["compare:x"] != 2 {
		t.Errorf("Zaehler vermischt: userA=%v userB=%v", a, b)
	}
}
