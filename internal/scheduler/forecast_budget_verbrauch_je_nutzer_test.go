package scheduler

// TDD RED — Issue #2475 (S4 von #2150).
// Spec: docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md (AC-5, AC-7, AC-8)
// Echte Dateien in t.TempDir(), Zugriff ueber den echten Scheduler-Status.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func vbHeute() string { return time.Now().UTC().Format("2006-01-02") }

func vbSchreibe(t *testing.T, pfad, inhalt string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(pfad), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(pfad, []byte(inhalt), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func vbNutzerZaehler(t *testing.T, dir, uid string, n int) {
	t.Helper()
	vbSchreibe(t, filepath.Join(dir, "users", uid, "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":`+strconv.Itoa(n)+`}}`)
}

func vbToJSONMap(t *testing.T, v map[string]any) (map[string]any, string) {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("Serialisierung: %v", err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Rueckwandlung: %v", err)
	}
	return m, string(raw)
}

// AC-5: vier anonyme Kennzahlen, keine Kennung, kein Schluessel active_users.
func TestForecastBudgetStatus_AC5_AnonymeKennzahlen(t *testing.T) {
	dir := t.TempDir()
	const kennA, kennB = "privat-kennung-a", "privat-kennung-b"
	vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":7400},"active_users":["`+kennA+`","`+kennB+`"]}`)
	vbNutzerZaehler(t, dir, kennA, 7300)
	vbNutzerZaehler(t, dir, kennB, 100)

	m, raw := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, dir).ForecastBudgetHealth())

	if m["active_pots"] != float64(2) {
		t.Errorf("AC-5: active_pots = %v, erwartet 2", m["active_pots"])
	}
	if m["fair_share"] != float64(4500) {
		t.Errorf("AC-5: fair_share = %v, erwartet 4500", m["fair_share"])
	}
	if m["max_user_calls"] != float64(7300) {
		t.Errorf("AC-5: max_user_calls = %v, erwartet 7300", m["max_user_calls"])
	}
	if m["users_over_fair_share"] != float64(1) {
		t.Errorf("AC-5: users_over_fair_share = %v, erwartet 1", m["users_over_fair_share"])
	}
	for _, verboten := range []string{kennA, kennB, "active_users"} {
		if strings.Contains(raw, verboten) {
			t.Errorf("AC-5: %q steht in der Statusantwort: %s", verboten, raw)
		}
	}
}

// AC-7: die vier Felder sind in JEDEM Zustand da; bisherige Schluessel bleiben.
func TestForecastBudgetStatus_AC7_FelderInAllenZustaenden(t *testing.T) {
	bisher := []string{"date", "calls_today", "daily_budget", "usage_ratio", "cache_hits",
		"cache_misses", "cache_hit_ratio", "throttle_level", "status"}
	gestern := time.Now().UTC().AddDate(0, 0, -1).Format("2006-01-02")
	faelle := map[string]func(t *testing.T, dir string){
		"keine Datei": func(t *testing.T, dir string) {},
		"kaputte Datei": func(t *testing.T, dir string) {
			vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"), "{kaputt")
		},
		"gestern": func(t *testing.T, dir string) {
			vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"),
				`{"date":"`+gestern+`","calls":{"openmeteo":5000},"active_users":["x"]}`)
		},
	}
	for name, aufbau := range faelle {
		t.Run(name, func(t *testing.T) {
			dir := t.TempDir()
			aufbau(t, dir)
			m, _ := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, dir).ForecastBudgetHealth())
			for _, k := range bisher {
				if _, ok := m[k]; !ok {
					t.Errorf("AC-7: bisheriger Schluessel %q fehlt", k)
				}
			}
			for _, k := range []string{"active_pots", "max_user_calls", "users_over_fair_share"} {
				if m[k] != float64(0) {
					t.Errorf("AC-7: %s = %v, erwartet 0 (nil = fehlt)", k, m[k])
				}
			}
			if m["fair_share"] != float64(forecastDailyBudget) {
				t.Errorf("AC-7: fair_share = %v, erwartet daily_budget %d", m["fair_share"], forecastDailyBudget)
			}
		})
	}
}

// AC-8: manipulierte Nutzer-ID liest nichts ausserhalb von data/users/.
func TestUserForecastCalls_AC8_PfadTraversalLiefertNull(t *testing.T) {
	dir := t.TempDir()
	// Positivkontrolle: gueltiger Nutzer wird gelesen.
	vbNutzerZaehler(t, dir, "alice", 55)
	if got := userForecastCalls(dir, "alice"); got != 55 {
		t.Fatalf("AC-8 Positivkontrolle: alice = %d, erwartet 55", got)
	}
	// Koeder AUSSERHALB von users/: <dir>/x/diagnostics/forecast_budget.json
	vbSchreibe(t, filepath.Join(dir, "x", "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":999}}`)
	for _, uid := range []string{"../x", "..", "alice/../../x", "", "/etc"} {
		if got := userForecastCalls(dir, uid); got != 0 {
			t.Errorf("AC-8: uid %q lieferte %d, erwartet 0", uid, got)
		}
	}
}
