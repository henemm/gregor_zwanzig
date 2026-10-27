package scheduler

// ---------------------------------------------------------------------------
// Fix #2286 AC-7 — briefing_health zaehlt kaputte Briefing-Dateien nach Art
//
// Spec: docs/specs/modules/fix_2286_compare_betrieb_health.md
// (Implementierungsdetails 5, AC-7).
//
// Python schreibt in users/<uid>/diagnostics/corrupt_trips.json zusaetzlich
// "by_kind": {"trip":n,"vergleich":n,"unbekannt":n}. aggregateCorruptTrips
// soll daraus corrupt_briefings_total und corrupt_briefings_by_kind liefern --
// nur Zahlen (Datenschutz #252). Altbestand ohne by_kind: last_skipped_count
// zaehlt vollstaendig als "unbekannt". corrupt_trips_* bleibt unveraendert.
// ---------------------------------------------------------------------------

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeCorruptBriefingsRaw schreibt eine echte corrupt_trips.json mit
// beliebigem (Python-geschriebenem) Inhalt.
func writeCorruptBriefingsRaw(t *testing.T, tmpDir, userID, body string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "corrupt_trips.json"), []byte(body), 0644); err != nil {
		t.Fatalf("write corrupt_trips.json: %v", err)
	}
}

func corruptByKind(t *testing.T, bh map[string]any) map[string]any {
	t.Helper()
	raw, ok := bh["corrupt_briefings_by_kind"]
	if !ok {
		t.Fatalf("briefing_health lacks corrupt_briefings_by_kind (AC-7)")
	}
	m, ok := raw.(map[string]any)
	if !ok {
		t.Fatalf("corrupt_briefings_by_kind must be an object, got %T: %v", raw, raw)
	}
	for _, k := range []string{"trip", "vergleich", "unbekannt"} {
		if _, ok := m[k]; !ok {
			t.Fatalf("corrupt_briefings_by_kind lacks key %q: %v", k, m)
		}
	}
	if len(m) != 3 {
		t.Fatalf("corrupt_briefings_by_kind must have exactly trip/vergleich/unbekannt, got %v", m)
	}
	return m
}

// AC-7: zwei Nutzer mit by_kind + ein Altbestands-Nutzer ohne by_kind ->
// Summen ueber alle Nutzer, corrupt_trips_* unveraendert, keine IDs/Dateinamen.
func TestBriefingHealthCorruptBriefingsByKindAggregatesAcrossUsers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir,
		"tdd-2286-usera", "tdd-2286-userb", "tdd-2286-userc")

	writeCorruptBriefingsRaw(t, tmpDir, "tdd-2286-usera",
		`{"notified":["geheim-trip-a.json","geheim-vergleich-a.json","geheim-vergleich-a2.json"],`+
			`"last_skipped_count":3,"last_run":"2026-10-21T10:00:00Z",`+
			`"by_kind":{"trip":1,"vergleich":2,"unbekannt":0}}`)
	writeCorruptBriefingsRaw(t, tmpDir, "tdd-2286-userb",
		`{"notified":["geheim-vergleich-b.json","geheim-unklar-b.json"],`+
			`"last_skipped_count":2,"last_run":"2026-10-21T12:00:00Z",`+
			`"by_kind":{"trip":0,"vergleich":1,"unbekannt":1}}`)
	// Altbestand (vor #2286): kein by_kind -> zaehlt als "unbekannt".
	writeCorruptBriefingsRaw(t, tmpDir, "tdd-2286-userc",
		`{"notified":["geheim-alt-c.json","geheim-alt-c2.json"],`+
			`"last_skipped_count":2,"last_run":"2026-10-21T11:00:00Z"}`)

	code, body, rawBody := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	// Bestehender Monitoring-Vertrag bleibt unveraendert.
	if got := bh["corrupt_trips_total"]; got != float64(7) {
		t.Errorf("corrupt_trips_total must stay the plain sum (7), got %v", got)
	}
	if got := bh["corrupt_trips_last_run_at"]; got != "2026-10-21T12:00:00Z" {
		t.Errorf("corrupt_trips_last_run_at: want newest last_run, got %v", got)
	}

	if got := bh["corrupt_briefings_total"]; got != float64(7) {
		t.Errorf("corrupt_briefings_total: want 7, got %v", got)
	}
	byKind := corruptByKind(t, bh)
	want := map[string]float64{"trip": 1, "vergleich": 3, "unbekannt": 3}
	for k, v := range want {
		if byKind[k] != v {
			t.Errorf("corrupt_briefings_by_kind[%s]: want %v, got %v", k, v, byKind[k])
		}
	}

	for _, forbidden := range []string{
		"tdd-2286-usera", "tdd-2286-userb", "tdd-2286-userc", "geheim-", ".json",
	} {
		if strings.Contains(rawBody, forbidden) {
			t.Errorf("Privacy-Leak (#252): status response contains %q", forbidden)
		}
	}
}

// Fail-soft: keine corrupt_trips.json -> corrupt_briefings_total 0 und alle
// drei Arten mit 0 vorhanden (Monitor kann sich auf die Felder verlassen).
func TestBriefingHealthCorruptBriefingsByKindZeroWhenNoFiles(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-2286-usera")

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["corrupt_briefings_total"]; got != float64(0) {
		t.Errorf("corrupt_briefings_total: want 0, got %v", got)
	}
	byKind := corruptByKind(t, bh)
	for _, k := range []string{"trip", "vergleich", "unbekannt"} {
		if byKind[k] != float64(0) {
			t.Errorf("corrupt_briefings_by_kind[%s]: want 0, got %v", k, byKind[k])
		}
	}
}
