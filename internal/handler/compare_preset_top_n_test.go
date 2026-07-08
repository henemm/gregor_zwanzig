package handler

// Issue #1104 F002 — Adversary-Fix: fehlender Beweis fuer den AC-3-geforderten
// Zwei-Nutzer-Roundtrip: PUT /api/compare/presets/{id} aendert display_config.top_n,
// alle anderen display_config-Felder (region, ideal_ranges) sowie sonstige
// Preset-Felder bleiben erhalten, Nutzer B ist vollkommen unberuehrt.
//
// Vorbild (Struktur 1:1 gespiegelt):
// compare_preset_official_alerts_test.go::TestUpdateComparePreset_OfficialAlertsEnabledCrossUserIsolation
//
// display_config ist im Handler ein Ganz-oder-gar-nicht-Blob (siehe
// compare_preset.go:207-208 — nur erhalten, wenn der Client das Feld GAR NICHT
// mitschickt). Der echte Frontend-Client sendet beim Speichern das vollstaendige
// display_config per Round-Trip-Spread (bestehende Felder + geaenderter top_n).
// Dieser Test bildet genau dieses reale Client-Verhalten ab.

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

func TestUpdateComparePreset_TopNPreservesDisplayConfigAndIsolatesUsers(t *testing.T) {
	s := newTestStore(t)

	presetA := model.ComparePreset{
		ID:          "cp-topn-usera",
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
			"top_n":  float64(3),
			"region": "Ortler",
			"ideal_ranges": map[string]interface{}{
				"temp_max_c": []interface{}{float64(15), float64(25)},
			},
			"channel_layouts": map[string]interface{}{
				"email": []interface{}{
					map[string]interface{}{"metric_id": "wind_max_kmh", "enabled": true},
				},
				"sms": []interface{}{
					map[string]interface{}{"metric_id": "temp_max_c", "enabled": true},
				},
			},
		},
	}
	presetB := model.ComparePreset{
		ID:          "cp-topn-userb",
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
			"top_n":  float64(5),
			"region": "Stubai",
		},
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	// Nutzer A aendert NUR top_n (5), sendet aber das vollstaendige display_config
	// wie ein echter Frontend-Client (Round-Trip-Spread: bestehende Felder + Delta)
	// plus alle Scheduler-Felder unveraendert.
	body := map[string]interface{}{
		"name":         "Nutzer A Preset",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"display_config": map[string]interface{}{
			"top_n":  5,
			"region": "Ortler",
			"ideal_ranges": map[string]interface{}{
				"temp_max_c": []interface{}{15, 25},
			},
			"channel_layouts": map[string]interface{}{
				"email": []interface{}{
					map[string]interface{}{"metric_id": "wind_max_kmh", "enabled": true},
				},
				"sms": []interface{}{
					map[string]interface{}{"metric_id": "temp_max_c", "enabled": true},
				},
			},
		},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-topn-usera", bytes.NewReader(buf))
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
	if topN, ok := dcA["top_n"].(float64); !ok || topN != 5 {
		t.Errorf("expected usera top_n=5 after PUT, got %v", dcA["top_n"])
	}
	if region, ok := dcA["region"].(string); !ok || region != "Ortler" {
		t.Errorf("expected usera region='Ortler' preserved, got %v", dcA["region"])
	}
	if _, ok := dcA["ideal_ranges"]; !ok {
		t.Errorf("expected usera ideal_ranges preserved, got missing key")
	}

	// F004: channel_layouts (Spec AC-3 nennt es explizit) muss struktur-identisch
	// erhalten bleiben, wenn nur top_n geaendert wird.
	wantChannelLayouts := map[string]interface{}{
		"email": []interface{}{
			map[string]interface{}{"metric_id": "wind_max_kmh", "enabled": true},
		},
		"sms": []interface{}{
			map[string]interface{}{"metric_id": "temp_max_c", "enabled": true},
		},
	}
	wantJSON, err := json.Marshal(wantChannelLayouts)
	if err != nil {
		t.Fatalf("marshal wantChannelLayouts: %v", err)
	}
	gotJSON, err := json.Marshal(dcA["channel_layouts"])
	if err != nil {
		t.Fatalf("marshal dcA[channel_layouts]: %v", err)
	}
	if string(gotJSON) != string(wantJSON) {
		t.Errorf("expected usera channel_layouts preserved struct-identical, want %s, got %s", wantJSON, gotJSON)
	}

	// Uebrige Nicht-display_config-Felder (Empfaenger/Zeitfenster) byte-identisch erhalten.
	if len(loadedA[0].Empfaenger) != 1 || loadedA[0].Empfaenger[0] != "a@example.com" {
		t.Errorf("expected usera empfaenger preserved, got %v", loadedA[0].Empfaenger)
	}
	if loadedA[0].HourFrom != 8 || loadedA[0].HourTo != 17 {
		t.Errorf("expected usera hour_from/hour_to preserved, got %d/%d", loadedA[0].HourFrom, loadedA[0].HourTo)
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
	if topN, ok := dcB["top_n"].(float64); !ok || topN != 5 {
		t.Errorf("cross-user leak: userb's top_n changed, expected original 5, got %v", dcB["top_n"])
	}
	if region, ok := dcB["region"].(string); !ok || region != "Stubai" {
		t.Errorf("cross-user leak: userb's region changed, expected 'Stubai', got %v", dcB["region"])
	}
}
