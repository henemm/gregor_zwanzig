package handler

// TDD RED — Issue #1467 Scheibe S1: eine Kennung statt zwei Feldern.
//
// Spec: docs/specs/modules/rework_1467_s1_alarm_kennung.md
// AC-4, AC-5, AC-6, AC-7, AC-8, AC-10, AC-11, AC-12
//
// Echte Verhaltenstests: echter Store, echte JSON-Dateien, echte Handler via
// httptest. Keine Mocks. Helfer (seedAlertLog/withUserCtx/newTestStore)
// stammen aus cockpit_test.go bzw. trip_write_test.go.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// recent liefert einen Zeitstempel innerhalb des 24-h-Fensters des Cockpits.
func recent() string {
	return time.Now().UTC().Add(-1 * time.Hour).Format(time.RFC3339)
}

// legacyEntry baut einen Eintrag im Altformat (genau die vier Felder von #393).
func legacyEntry(tripID string) map[string]interface{} {
	return map[string]interface{}{
		"trip_id":       tripID,
		"sent_at":       recent(),
		"changes_count": 1,
		"severity":      "LOW",
	}
}

// entityEntry baut einen Eintrag im neuen Format.
func entityEntry(entityID, entityType string) map[string]interface{} {
	return map[string]interface{}{
		"entity_id":     entityID,
		"entity_type":   entityType,
		"sent_at":       recent(),
		"changes_count": 1,
		"severity":      "LOW",
	}
}

// decodeAlerts liest das alerts-Array aus der Cockpit-Antwort roh aus, damit
// auch die JSON-Feldnamen geprueft werden koennen.
func decodeAlerts(t *testing.T, w *httptest.ResponseRecorder) []map[string]interface{} {
	t.Helper()
	var resp struct {
		Alerts []map[string]interface{} `json:"alerts"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("keine gueltige JSON-Antwort: %v (body=%s)", err, w.Body.String())
	}
	return resp.Alerts
}

func decodeAlertCounts(t *testing.T, w *httptest.ResponseRecorder) map[string]float64 {
	t.Helper()
	var resp struct {
		Alerts map[string]float64 `json:"alerts"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("keine gueltige JSON-Antwort: %v (body=%s)", err, w.Body.String())
	}
	return resp.Alerts
}

// --- AC-4: Altbestand wird beim Lesen uebersetzt ---------------------------

func TestLoadAlertLog_DerivesEntityFromLegacyTripID(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		legacyEntry("trip-A"),
		legacyEntry("trip-B"),
	})

	entries, err := s.WithUser("test").LoadAlertLog()
	if err != nil {
		t.Fatalf("LoadAlertLog: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("2 Eintraege erwartet, %d bekommen", len(entries))
	}
	for i, want := range []string{"trip-A", "trip-B"} {
		if entries[i].EntityID != want {
			t.Errorf("Eintrag %d: EntityID=%q, erwartet %q", i, entries[i].EntityID, want)
		}
		if entries[i].EntityType != "trip" {
			t.Errorf("Eintrag %d: EntityType=%q, erwartet \"trip\"", i, entries[i].EntityType)
		}
	}
}

// --- AC-5: Cockpit zeigt fuer Altbestand dieselbe Anzahl wie vorher --------

func TestCockpitStatus_LegacyLogKeepsCountAndCarriesEntityFields(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		legacyEntry("trip-A"),
		legacyEntry("trip-A"),
		legacyEntry("trip-B"),
	})

	h := CockpitStatusHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	alerts := decodeAlerts(t, w)
	if len(alerts) != 3 {
		t.Fatalf("3 Alarme erwartet (unveraendert zum Bestand), %d bekommen", len(alerts))
	}
	for i, a := range alerts {
		if a["entity_id"] == "" || a["entity_id"] == nil {
			t.Errorf("Alarm %d ohne entity_id: %v", i, a)
		}
		if a["entity_type"] != "trip" {
			t.Errorf("Alarm %d: entity_type=%v, erwartet \"trip\"", i, a["entity_type"])
		}
	}
}

// --- AC-6: gemischter Bestand wird eintragsweise richtig zugeordnet --------

func TestCockpitStatus_MixedLegacyAndEntityEntries(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		legacyEntry("trip-A"),
		entityEntry("preset-P", "compare"),
		entityEntry("trip-B", "trip"),
	})

	h := CockpitStatusHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	alerts := decodeAlerts(t, w)
	if len(alerts) != 3 {
		t.Fatalf("3 Alarme erwartet, %d bekommen", len(alerts))
	}
	byType := map[string]int{}
	for _, a := range alerts {
		typ, _ := a["entity_type"].(string) // fehlend/nil -> "" statt Panik
		byType[typ]++
	}
	if byType["trip"] != 2 || byType["compare"] != 1 {
		t.Errorf("erwartet 2x trip / 1x compare, bekommen %v", byType)
	}
}

// --- AC-7: Archiv-Zaehlung getrennt je Typ, kein Sammel-Schluessel ---------

func TestArchiveStats_CountsPerEntityTypeAndID(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		legacyEntry("A"), legacyEntry("A"), legacyEntry("A"),
		legacyEntry("B"),
		entityEntry("P", "compare"), entityEntry("P", "compare"),
	})

	h := ArchiveStatsHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	counts := decodeAlertCounts(t, w)
	want := map[string]float64{"trip:A": 3, "trip:B": 1, "compare:P": 2}
	for k, v := range want {
		if counts[k] != v {
			t.Errorf("Schluessel %q: %v erwartet, %v bekommen (alle: %v)", k, v, counts[k], counts)
		}
	}
	if _, ok := counts[""]; ok {
		t.Errorf("Sammel-Schluessel \"\" darf nicht mehr vorkommen: %v", counts)
	}
	if len(counts) != 3 {
		t.Errorf("genau 3 Schluessel erwartet, bekommen %v", counts)
	}
}

// --- AC-8: gleiche Kennung, anderer Typ -> getrennt, nicht addiert ---------

func TestArchiveStats_SameIDDifferentTypeCountedSeparately(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		entityEntry("x1", "trip"),
		entityEntry("x1", "compare"),
		entityEntry("x1", "compare"),
	})

	h := ArchiveStatsHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	counts := decodeAlertCounts(t, w)
	if counts["trip:x1"] != 1 {
		t.Errorf("trip:x1 = 1 erwartet, bekommen %v (alle: %v)", counts["trip:x1"], counts)
	}
	if counts["compare:x1"] != 2 {
		t.Errorf("compare:x1 = 2 erwartet, bekommen %v (alle: %v)", counts["compare:x1"], counts)
	}
}

// --- AC-10: Mandantentrennung mit gleichlautenden Kennungen ----------------

func TestAlertLog_TwoUsersStaySeparate(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "userA", []map[string]interface{}{
		entityEntry("shared-id", "trip"),
		entityEntry("shared-id", "trip"),
	})
	seedAlertLog(t, s.DataDir, "userB", []map[string]interface{}{
		entityEntry("shared-id", "compare"),
	})

	h := ArchiveStatsHandler(s)

	wA := httptest.NewRecorder()
	h.ServeHTTP(wA, withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "userA"))
	countsA := decodeAlertCounts(t, wA)
	if countsA["trip:shared-id"] != 2 || len(countsA) != 1 {
		t.Errorf("userA sieht %v, erwartet genau {trip:shared-id: 2}", countsA)
	}

	wB := httptest.NewRecorder()
	h.ServeHTTP(wB, withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "userB"))
	countsB := decodeAlertCounts(t, wB)
	if countsB["compare:shared-id"] != 1 || len(countsB) != 1 {
		t.Errorf("userB sieht %v, erwartet genau {compare:shared-id: 1}", countsB)
	}
}

// --- AC-11: fail-soft bleibt fail-soft (Regressionsschutz) ----------------

func TestAlertLog_FailSoftOnMissingAndCorruptFile(t *testing.T) {
	// Fehlende Datei.
	s := newTestStore(t)
	for _, h := range []http.Handler{CockpitStatusHandler(s), ArchiveStatsHandler(s)} {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, withUserCtx(httptest.NewRequest(http.MethodGet, "/x", nil), "test"))
		if w.Code != http.StatusOK {
			t.Errorf("fehlende Datei: 200 erwartet, %d bekommen", w.Code)
		}
	}

	// Kaputte Datei.
	s2 := newTestStore(t)
	dir := filepath.Join(s2.DataDir, "users", "test")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "alert_log.json"), []byte("{kaputt"), 0644); err != nil {
		t.Fatal(err)
	}
	for _, h := range []http.Handler{CockpitStatusHandler(s2), ArchiveStatsHandler(s2)} {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, withUserCtx(httptest.NewRequest(http.MethodGet, "/x", nil), "test"))
		if w.Code != http.StatusOK {
			t.Errorf("kaputte Datei: 200 erwartet, %d bekommen", w.Code)
		}
	}
}

// --- AC-12: kennungsloser Eintrag wird nicht stumm verschluckt ------------

func TestArchiveStats_EntryWithoutAnyIDIsStillCounted(t *testing.T) {
	s := newTestStore(t)
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		legacyEntry("A"),
		{"sent_at": recent(), "changes_count": 1, "severity": "LOW"}, // gar keine Kennung
	})

	h := ArchiveStatsHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	counts := decodeAlertCounts(t, w)
	total := 0.0
	for _, v := range counts {
		total += v
	}
	if total != 2 {
		t.Errorf("beide Eintraege muessen gezaehlt werden, Summe=%v (alle: %v)", total, counts)
	}
	if counts["trip:"] != 1 {
		t.Errorf("kennungsloser Eintrag unter \"trip:\" erwartet, bekommen %v", counts)
	}
}
