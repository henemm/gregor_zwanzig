package scheduler

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestForecastBudgetSnapshotLeaksNoUserID guards AC-6 of Issue #2387
// (docs/specs/modules/forecast_budget_je_nutzer.md): ForecastBudgetGate now
// records the set of users active today into the GLOBAL counter file
// ("active_users"), because that set yields N for the fair-share
// calculation. /api/scheduler/status is reachable WITHOUT authentication
// (ADR-0075, point 5), so no user identifier may ever reach its payload.
//
// The Go reader declares only the four known fields, so the extra field is
// dropped at unmarshal time — this test freezes that property so a later
// "let's expose active_users for observability" change has to break a test
// instead of quietly leaking identifiers.
func TestForecastBudgetSnapshotLeaksNoUserID(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "forecast_budget.json")

	const geheimA = "hennings-privatkennung"
	const geheimB = "zweite-privatkennung"

	payload := map[string]any{
		"date":         time.Now().UTC().Format("2006-01-02"),
		"calls":        map[string]int{"openmeteo": 7300},
		"cache_hits":   12,
		"cache_misses": 4,
		"active_users": []string{geheimA, geheimB},
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("Testaufbau: %v", err)
	}
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		t.Fatalf("Testaufbau: %v", err)
	}

	snap := forecastBudgetSnapshot(path)

	// Positivkontrolle: das Aggregat muss weiterhin verwertbar sein --
	// sonst bewiese die Abwesenheitspruefung unten nur, dass gar nichts
	// ausgeliefert wird.
	if snap["status"] != "ok" {
		t.Fatalf("AC-6: Aggregat muss verwertbar bleiben, status=%v", snap["status"])
	}
	if snap["calls_today"] != 7300 {
		t.Errorf("AC-6: calls_today = %v, erwartet 7300", snap["calls_today"])
	}
	if snap["throttle_level"] != "polling_throttled" {
		t.Errorf("AC-6: throttle_level = %v, erwartet polling_throttled", snap["throttle_level"])
	}
	if snap["date"] == nil {
		t.Errorf("AC-6: date fehlt im Aggregat")
	}

	// Abwesenheitspruefung ueber die serialisierte Antwort, nicht ueber
	// einzelne Felder: eine Kennung darf an KEINER Stelle auftauchen, auch
	// nicht in einem spaeter ergaenzten Feld.
	ausgeliefert, err := json.Marshal(snap)
	if err != nil {
		t.Fatalf("Serialisierung der Antwort: %v", err)
	}
	antwort := string(ausgeliefert)
	for _, kennung := range []string{geheimA, geheimB, "active_users"} {
		if strings.Contains(antwort, kennung) {
			t.Errorf(
				"AC-6 (ADR-0075, Punkt 5): %q steht in der Antwort von "+
					"/api/scheduler/status -- der Endpunkt ist ohne Anmeldung "+
					"erreichbar und darf nie eine Nutzerkennung ausgeben: %s",
				kennung, antwort,
			)
		}
	}
}
