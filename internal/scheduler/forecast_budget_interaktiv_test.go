package scheduler

// ADR-0117 (#2961): der Betriebsstatus weist den interaktiven Verbrauch
// getrennt aus; der Admin-Leser liefert den interaktiven Anteil je Nutzer.
// Spec: docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md

import (
	"path/filepath"
	"strconv"
	"testing"
)

func TestForecastBudgetStatus_InteraktivGetrenntAusgewiesen(t *testing.T) {
	dir := t.TempDir()
	vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":6300},"interactive_calls":{"openmeteo":4000},"active_users":["a","b"]}`)

	m, _ := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, dir).ForecastBudgetHealth())
	if m["interactive_calls_today"] != float64(4000) {
		t.Errorf("interactive_calls_today = %v, erwartet 4000", m["interactive_calls_today"])
	}
	if m["interactive_budget"] != float64(6300) {
		t.Errorf("interactive_budget = %v, erwartet 6300 (70 %% von 9000)", m["interactive_budget"])
	}
	if m["interactive_throttled"] != true {
		t.Errorf("interactive_throttled = %v, erwartet true bei calls_today = Obergrenze", m["interactive_throttled"])
	}
	if m["throttle_level"] != "none" {
		t.Errorf("throttle_level darf sich nicht aendern: %v", m["throttle_level"])
	}
}

func TestForecastBudgetStatus_InteraktivUnterGrenzeUndOhneDatei(t *testing.T) {
	dir := t.TempDir()
	vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":6299}}`)
	m, _ := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, dir).ForecastBudgetHealth())
	if m["interactive_throttled"] != false || m["interactive_calls_today"] != float64(0) {
		t.Errorf("unter der Grenze: throttled=%v calls=%v", m["interactive_throttled"], m["interactive_calls_today"])
	}

	leer, _ := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, t.TempDir()).ForecastBudgetHealth())
	for _, k := range []string{"interactive_calls_today", "interactive_budget", "interactive_throttled"} {
		if _, ok := leer[k]; !ok {
			t.Errorf("Feld %q fehlt ohne Zaehlerdatei", k)
		}
	}
}

func TestUserForecastUsage_InteraktiverAnteilJeNutzer(t *testing.T) {
	dir := t.TempDir()
	for uid, werte := range map[string][2]int{"alice": {120, 100}, "bob": {30, 0}} {
		vbSchreibe(t, filepath.Join(dir, "users", uid, "diagnostics", "forecast_budget.json"),
			`{"date":"`+vbHeute()+`","calls":{"openmeteo":`+strconv.Itoa(werte[0])+
				`},"interactive":{"openmeteo":`+strconv.Itoa(werte[1])+`}}`)
	}
	if g, i, _ := userForecastUsage(dir, "alice"); g != 120 || i != 100 {
		t.Errorf("alice = (%d, %d), erwartet (120, 100)", g, i)
	}
	if g, i, _ := userForecastUsage(dir, "bob"); g != 30 || i != 0 {
		t.Errorf("bob = (%d, %d), erwartet (30, 0)", g, i)
	}
	if g, i, _ := userForecastUsage(dir, "../alice"); g != 0 || i != 0 {
		t.Errorf("Pfad-Traversal muss 0 liefern, bekam (%d, %d)", g, i)
	}
}

// ADR-0117 Nachtrag: user_manual (Handversand, Antwort-Befehle) getrennt.
func TestForecastBudgetStatus_ManuellGetrenntAusgewiesen(t *testing.T) {
	dir := t.TempDir()
	vbSchreibe(t, filepath.Join(dir, "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":8100},"manual_calls":{"openmeteo":3000}}`)
	m, _ := vbToJSONMap(t, newForecastBudgetHealthTestScheduler(t, dir).ForecastBudgetHealth())
	if m["manual_calls_today"] != float64(3000) || m["manual_budget"] != float64(8100) || m["manual_throttled"] != true {
		t.Errorf("manuell: calls=%v budget=%v throttled=%v", m["manual_calls_today"], m["manual_budget"], m["manual_throttled"])
	}
	vbSchreibe(t, filepath.Join(dir, "users", "carla", "diagnostics", "forecast_budget.json"),
		`{"date":"`+vbHeute()+`","calls":{"openmeteo":40},"interactive":{"openmeteo":10},"manual":{"openmeteo":25}}`)
	if g, i, mn := userForecastUsage(dir, "carla"); g != 40 || i != 10 || mn != 25 {
		t.Errorf("carla = (%d, %d, %d), erwartet (40, 10, 25)", g, i, mn)
	}
}
