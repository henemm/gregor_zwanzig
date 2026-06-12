package store

// Echte Verhaltenstests für die Archiv-Statistik-Zählung (Issue #772).
// Keine Mocks, kein Source-Grep: echte store.New(t.TempDir(), ...)-Instanzen,
// echte JSON-Log-Dateien auf Platte, echte Methodenaufrufe.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// writeLogFile schreibt ein {"entries":[...]}-Log-File ins user-scoped Verzeichnis.
func writeLogFile(t *testing.T, dataDir, userID, name string, entries []map[string]interface{}) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(map[string]interface{}{"entries": entries})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, name), b, 0o644); err != nil {
		t.Fatal(err)
	}
}

// AC-1: briefing_log.json mit mehreren Einträgen für zwei Trips → korrekte Map.
func TestBriefingCountByTrip_CountsPerTrip(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "test", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "trip-A", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
		{"trip_id": "trip-B", "kind": "morning", "sent_at": "2026-06-11T07:05:00Z", "channels": []string{"email"}},
	})

	s := New(dataDir, "test")
	counts, err := s.BriefingCountByTrip()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if counts["trip-A"] != 3 {
		t.Errorf("expected trip-A=3, got %d", counts["trip-A"])
	}
	if counts["trip-B"] != 1 {
		t.Errorf("expected trip-B=1, got %d", counts["trip-B"])
	}
	if len(counts) != 2 {
		t.Errorf("expected exactly 2 trips, got %d: %v", len(counts), counts)
	}
}

// AC-2: alert_log.json mit mehreren Einträgen für zwei Trips → korrekte Map.
func TestAlertCountByTrip_CountsPerTrip(t *testing.T) {
	dataDir := t.TempDir()
	writeLogFile(t, dataDir, "test", "alert_log.json", []map[string]interface{}{
		{"trip_id": "trip-A", "sent_at": "2026-06-10T09:00:00Z", "changes_count": 2, "severity": "MODERATE"},
		{"trip_id": "trip-A", "sent_at": "2026-06-11T10:00:00Z", "changes_count": 1, "severity": "LOW"},
		{"trip_id": "trip-B", "sent_at": "2026-06-11T11:00:00Z", "changes_count": 3, "severity": "HIGH"},
	})

	s := New(dataDir, "test")
	counts, err := s.AlertCountByTrip()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if counts["trip-A"] != 2 {
		t.Errorf("expected trip-A=2, got %d", counts["trip-A"])
	}
	if counts["trip-B"] != 1 {
		t.Errorf("expected trip-B=1, got %d", counts["trip-B"])
	}
	if len(counts) != 2 {
		t.Errorf("expected exactly 2 trips, got %d: %v", len(counts), counts)
	}
}

// AC-3: Store ganz ohne Log-Dateien → beide Methoden liefern leere Map, kein Fehler.
func TestCountByTrip_FailSoftWhenNoLogs(t *testing.T) {
	s := New(t.TempDir(), "test")

	briefings, err := s.BriefingCountByTrip()
	if err != nil {
		t.Fatalf("BriefingCountByTrip returned error on missing log: %v", err)
	}
	if len(briefings) != 0 {
		t.Errorf("expected empty briefings map, got %v", briefings)
	}

	alerts, err := s.AlertCountByTrip()
	if err != nil {
		t.Fatalf("AlertCountByTrip returned error on missing log: %v", err)
	}
	if len(alerts) != 0 {
		t.Errorf("expected empty alerts map, got %v", alerts)
	}
}

// AC-4: Zwei Nutzer mit eigenen Logs → WithUser zählt strikt getrennt.
func TestCountByTrip_IsolatedPerUser(t *testing.T) {
	dataDir := t.TempDir()

	// userA: 2x trip-A1 (briefings), 1x trip-A1 (alert)
	writeLogFile(t, dataDir, "userA", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "trip-A1", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A1", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
	})
	writeLogFile(t, dataDir, "userA", "alert_log.json", []map[string]interface{}{
		{"trip_id": "trip-A1", "sent_at": "2026-06-10T09:00:00Z", "changes_count": 1, "severity": "LOW"},
	})

	// userB: 1x trip-B1 (briefing), 2x trip-B1 (alerts)
	writeLogFile(t, dataDir, "userB", "briefing_log.json", []map[string]interface{}{
		{"trip_id": "trip-B1", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
	})
	writeLogFile(t, dataDir, "userB", "alert_log.json", []map[string]interface{}{
		{"trip_id": "trip-B1", "sent_at": "2026-06-11T10:00:00Z", "changes_count": 2, "severity": "MODERATE"},
		{"trip_id": "trip-B1", "sent_at": "2026-06-11T12:00:00Z", "changes_count": 1, "severity": "LOW"},
	})

	base := New(dataDir, "default")

	// userA sieht nur trip-A1
	aBrief, err := base.WithUser("userA").BriefingCountByTrip()
	if err != nil {
		t.Fatal(err)
	}
	if aBrief["trip-A1"] != 2 {
		t.Errorf("userA: expected trip-A1=2 briefings, got %d", aBrief["trip-A1"])
	}
	if _, leaked := aBrief["trip-B1"]; leaked {
		t.Errorf("cross-user leak: userB trip-B1 appeared in userA briefings: %v", aBrief)
	}

	aAlert, err := base.WithUser("userA").AlertCountByTrip()
	if err != nil {
		t.Fatal(err)
	}
	if aAlert["trip-A1"] != 1 {
		t.Errorf("userA: expected trip-A1=1 alert, got %d", aAlert["trip-A1"])
	}
	if _, leaked := aAlert["trip-B1"]; leaked {
		t.Errorf("cross-user leak: userB trip-B1 appeared in userA alerts: %v", aAlert)
	}

	// userB sieht nur trip-B1
	bBrief, err := base.WithUser("userB").BriefingCountByTrip()
	if err != nil {
		t.Fatal(err)
	}
	if bBrief["trip-B1"] != 1 {
		t.Errorf("userB: expected trip-B1=1 briefing, got %d", bBrief["trip-B1"])
	}
	if _, leaked := bBrief["trip-A1"]; leaked {
		t.Errorf("cross-user leak: userA trip-A1 appeared in userB briefings: %v", bBrief)
	}

	bAlert, err := base.WithUser("userB").AlertCountByTrip()
	if err != nil {
		t.Fatal(err)
	}
	if bAlert["trip-B1"] != 2 {
		t.Errorf("userB: expected trip-B1=2 alerts, got %d", bAlert["trip-B1"])
	}
	if _, leaked := bAlert["trip-A1"]; leaked {
		t.Errorf("cross-user leak: userA trip-A1 appeared in userB alerts: %v", bAlert)
	}
}
