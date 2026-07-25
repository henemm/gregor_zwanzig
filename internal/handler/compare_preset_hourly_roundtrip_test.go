package handler

// Issue #1360 (Scheibe S1a von Epic #1372) — Go-seitiger Nachweis fuer AC-5:
// ein PUT /api/compare/presets/{id}, der die Stundenverlauf-Auswahl aendert,
// laesst `hour_from`/`hour_to` und alle uebrigen display_config-Felder
// unangetastet — und Nutzer B vollkommen unberuehrt.
//
// LOEST AB: compare_preset_top_n_test.go (#1104 F002). Dort war das geaenderte
// Feld `display_config.top_n` — ein Regler, den seit der PO-Entscheidung
// 2026-07-08 kein Renderer mehr liest und der mit #1360 ersatzlos entfaellt.
// Die WERTVOLLEN Zusicherungen dieser Suite (Zwei-Nutzer-Roundtrip,
// display_config-Bestandsschutz, Zeitfenster-Bestandsschutz) bleiben — sie
// haengen jetzt an dem Feld, das die umgezogene Steuerung wirklich schreibt.
//
// WARUM das hier zaehlt (Adversary-Fund F003 aus #1268): `HourFrom`/`HourTo`
// haben im Handler KEINEN Read-Modify-Write-Schutz. Fehlen sie im Anfrage-Rumpf,
// dekodiert Go den Zero-Value 0 und schreibt 0 — `validateComparePreset` laesst
// das durch (0..23 erlaubt, 0<0 ist falsch). Der Datenverlust waere still. Der
// einzige Schutz ist der Round-Trip-Spread des Clients
// (`compareEditorSave.ts::buildComparePresetSavePayload`, `{ ...original }`).
// Dieser Test bildet genau dieses reale Client-Verhalten ab: vollstaendiger
// Rumpf inkl. Zeitfenster, nur das Stundenverlauf-Delta ist neu.
//
// Vorbild (Struktur 1:1 gespiegelt):
// compare_preset_official_alerts_test.go::TestUpdateComparePreset_OfficialAlertsEnabledCrossUserIsolation
//
// display_config ist im Handler ein Ganz-oder-gar-nicht-Blob (siehe
// compare_preset.go:207-208 — nur erhalten, wenn der Client das Feld GAR NICHT
// mitschickt). Der echte Frontend-Client sendet beim Speichern das vollstaendige
// display_config per Round-Trip-Spread (bestehende Felder + Delta).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

func TestUpdateComparePreset_HourlyMetricsPreserveTimeWindowAndIsolateUsers(t *testing.T) {
	s := newTestStore(t)

	presetA := model.ComparePreset{
		ID:          "cp-hourly-usera",
		Name:        "Nutzer A Preset",
		UserID:      "usera",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
		DisplayConfig: map[string]interface{}{
			"hourly_metrics": []interface{}{"temp_c"},
			"active_metrics": []interface{}{"temp_max_c", "wind_max_kmh"},
			"region":         "Ortler",
			"ideal_ranges": map[string]interface{}{
				"temp_max_c": []interface{}{float64(15), float64(25)},
			},
		},
	}
	presetB := model.ComparePreset{
		ID:          "cp-hourly-userb",
		Name:        "Nutzer B Preset",
		UserID:      "userb",
		LocationIDs: []string{"loc-b"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    9,
		HourTo:      16,
		Empfaenger:  []string{"b@example.com"},
		CreatedAt:   time.Now().UTC(),
		DisplayConfig: map[string]interface{}{
			"hourly_metrics": []interface{}{"wind_kmh"},
			"region":         "Stubai",
		},
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	// Nutzer A aendert NUR die Stundenverlauf-Auswahl (Reiter Wetter-Metriken,
	// Abschnitt Stundenverlauf), sendet aber das vollstaendige display_config wie
	// ein echter Frontend-Client (Round-Trip-Spread: bestehende Felder + Delta)
	// plus alle Scheduler-Felder inkl. Zeitfenster unveraendert.
	body := map[string]interface{}{
		"name":         "Nutzer A Preset",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"display_config": map[string]interface{}{
			"hourly_metrics": []interface{}{"temp_c", "thunder_level"},
			"active_metrics": []interface{}{"temp_max_c", "wind_max_kmh"},
			"region":         "Ortler",
			"ideal_ranges": map[string]interface{}{
				"temp_max_c": []interface{}{15, 25},
			},
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-hourly-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := s.WithUser("usera").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets usera: %v", err)
	}
	if len(loadedA) != 1 {
		t.Fatalf("expected 1 preset for usera, got %d", len(loadedA))
	}

	dcA := loadedA[0].DisplayConfig
	if dcA == nil {
		t.Fatalf("expected usera display_config to be present, got nil")
	}
	gotHourly, err := json.Marshal(dcA["hourly_metrics"])
	if err != nil {
		t.Fatalf("marshal dcA[hourly_metrics]: %v", err)
	}
	if string(gotHourly) != `["temp_c","thunder_level"]` {
		t.Errorf("expected usera hourly_metrics=[temp_c,thunder_level] after PUT, got %s", gotHourly)
	}
	if region, ok := dcA["region"].(string); !ok || region != "Ortler" {
		t.Errorf("expected usera region='Ortler' preserved, got %v", dcA["region"])
	}
	if _, ok := dcA["ideal_ranges"]; !ok {
		t.Errorf("expected usera ideal_ranges preserved, got missing key")
	}

	// Die Metrik-Auswahl des NACHBARABSCHNITTS im selben Reiter darf durch eine
	// Stundenverlauf-Aenderung nicht verlorengehen (beide Commits laufen ueber
	// denselben Round-Trip-Spread).
	gotActive, err := json.Marshal(dcA["active_metrics"])
	if err != nil {
		t.Fatalf("marshal dcA[active_metrics]: %v", err)
	}
	if string(gotActive) != `["temp_max_c","wind_max_kmh"]` {
		t.Errorf("expected usera active_metrics preserved, got %s", gotActive)
	}

	// Kein toter Ballast wird durch einen Speichervorgang wieder eingefuehrt.
	if _, ok := dcA["top_n"]; ok {
		t.Errorf("Issue #1360: 'top_n' darf nach einem Speichervorgang nicht mehr auftauchen, got %v", dcA["top_n"])
	}

	// AC-5 KERN: Zeitfenster byte-identisch erhalten (kein stiller Zero-Value 0).
	if len(loadedA[0].Empfaenger) != 1 || loadedA[0].Empfaenger[0] != "a@example.com" {
		t.Errorf("expected usera empfaenger preserved, got %v", loadedA[0].Empfaenger)
	}
	if loadedA[0].HourFrom != 8 || loadedA[0].HourTo != 17 {
		t.Errorf("AC-5 verletzt: hour_from/hour_to muessen 8/17 bleiben, got %d/%d "+
			"(0/0 bedeutet: der Round-Trip-Spread des Clients ist beim Umzug des "+
			"Bubble-Wrappers verlorengegangen)", loadedA[0].HourFrom, loadedA[0].HourTo)
	}

	// Nutzer B's Preset muss vollkommen unberuehrt bleiben (eigener Store-Bereich).
	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if len(loadedB) != 1 {
		t.Fatalf("expected 1 preset for userb, got %d", len(loadedB))
	}
	dcB := loadedB[0].DisplayConfig
	if dcB == nil {
		t.Fatalf("cross-user leak: userb's display_config vanished")
	}
	gotHourlyB, err := json.Marshal(dcB["hourly_metrics"])
	if err != nil {
		t.Fatalf("marshal dcB[hourly_metrics]: %v", err)
	}
	if string(gotHourlyB) != `["wind_kmh"]` {
		t.Errorf("cross-user leak: userb's hourly_metrics changed, expected [wind_kmh], got %s", gotHourlyB)
	}
	if region, ok := dcB["region"].(string); !ok || region != "Stubai" {
		t.Errorf("cross-user leak: userb's region changed, expected 'Stubai', got %v", dcB["region"])
	}
	if loadedB[0].HourFrom != 9 || loadedB[0].HourTo != 16 {
		t.Errorf("cross-user leak: userb's hour_from/hour_to changed, expected 9/16, got %d/%d",
			loadedB[0].HourFrom, loadedB[0].HourTo)
	}
}
