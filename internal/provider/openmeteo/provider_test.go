package openmeteo

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// =============================================================================
// Tests 1-5: SelectModel — regionale Modellauswahl
// =============================================================================

func TestSelectModel_Mallorca_ReturnsAROME(t *testing.T) {
	// GIVEN: Koordinaten auf Mallorca (39.7, 3.0) innerhalb AROME-Bounds
	// WHEN: SelectModel aufgerufen
	// THEN: meteofrance_arome (1.3km, Priority 1)
	model, err := SelectModel(39.7, 3.0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if model.ID != "meteofrance_arome" {
		t.Errorf("expected meteofrance_arome, got %s", model.ID)
	}
	if model.GridResKm != 1.3 {
		t.Errorf("expected grid_res 1.3, got %f", model.GridResKm)
	}
}

func TestSelectModel_Innsbruck_ReturnsICOND2(t *testing.T) {
	// GIVEN: Koordinaten in Innsbruck (47.3, 11.4) innerhalb ICON-D2-Bounds
	// WHEN: SelectModel aufgerufen
	// THEN: icon_d2 (2km, Priority 2)
	model, err := SelectModel(47.3, 11.4)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if model.ID != "icon_d2" {
		t.Errorf("expected icon_d2, got %s", model.ID)
	}
}

func TestSelectModel_Oslo_ReturnsMetNo(t *testing.T) {
	// GIVEN: Koordinaten in Oslo (59.9, 10.7) innerhalb MetNo-Bounds
	// WHEN: SelectModel aufgerufen
	// THEN: metno_nordic (1km, Priority 3)
	model, err := SelectModel(59.9, 10.7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if model.ID != "metno_nordic" {
		t.Errorf("expected metno_nordic, got %s", model.ID)
	}
}

func TestSelectModel_Athens_ReturnsICONEU(t *testing.T) {
	// GIVEN: Koordinaten in Athen (37.9, 23.7) ausserhalb AROME/D2/MetNo, innerhalb ICON-EU
	// WHEN: SelectModel aufgerufen
	// THEN: icon_eu (7km, Priority 4)
	model, err := SelectModel(37.9, 23.7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if model.ID != "icon_eu" {
		t.Errorf("expected icon_eu, got %s", model.ID)
	}
}

func TestSelectModel_Tokyo_ReturnsECMWF(t *testing.T) {
	// GIVEN: Koordinaten in Tokio (35.7, 139.7) ausserhalb aller EU-Modelle
	// WHEN: SelectModel aufgerufen
	// THEN: ecmwf_ifs04 (40km, Global Fallback)
	model, err := SelectModel(35.7, 139.7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if model.ID != "ecmwf_ifs04" {
		t.Errorf("expected ecmwf_ifs04, got %s", model.ID)
	}
}

// =============================================================================
// Tests 6-7: FetchForecast — gegen lokalen Fixture-Server (Issue #3106)
// Die Live-Variante gegen die echte API steht in provider_live_test.go
// (Build-Tag integration, laeuft nicht im Kern-CI).
// =============================================================================

func TestFetchForecast_Mallorca48h_ReturnsTimeseries(t *testing.T) {
	// GIVEN: OpenMeteo Provider, Basis-URLs zeigen auf den Fixture-Server
	// WHEN: FetchForecast fuer Mallorca (39.7, 3.0), 48h
	// THEN: Timeseries mit 48 Datenpunkten, Meta ausgefuellt
	fake := neuerOpenMeteoFixtureServer(t)
	ts, err := fake.provider(t).FetchForecast(39.7, 3.0, 48)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pruefeMallorcaZeitreihe(t, ts)
	fake.pruefeAnfragen(t)
	if ts.Meta.Model != "meteofrance_arome" {
		t.Errorf("expected meta.model 'meteofrance_arome', got '%s'", ts.Meta.Model)
	}
	if len(ts.Data) != 48 {
		t.Errorf("expected 48 data points from 48h fixture, got %d", len(ts.Data))
	}
	if ts.Data[12].UvIndex == nil {
		t.Error("expected uv_index from air-quality fixture merged at 12:00")
	}
}

// pruefeMallorcaZeitreihe enthaelt die Zusicherungen, die Fixture- und
// Live-Variante gemeinsam haben.
func pruefeMallorcaZeitreihe(t *testing.T, ts *model.Timeseries) {
	t.Helper()
	if ts == nil {
		t.Fatal("expected non-nil timeseries")
	}
	if len(ts.Data) < 24 {
		t.Errorf("expected at least 24 data points, got %d", len(ts.Data))
	}
	if ts.Meta.Model == "" {
		t.Error("expected meta.model to be set")
	}
	if ts.Meta.Provider != "OPENMETEO" {
		t.Errorf("expected provider 'OPENMETEO', got '%s'", ts.Meta.Provider)
	}
	if ts.Meta.GridResKm <= 0 {
		t.Error("expected grid_res_km > 0")
	}
	// Mindestens ein t2m_c Wert muss gesetzt sein
	hasTemp := false
	for _, dp := range ts.Data {
		if dp.T2mC != nil {
			hasTemp = true
			break
		}
	}
	if !hasTemp {
		t.Error("expected at least one non-nil t2m_c value")
	}
}

func TestFetchForecast_SetsTimezoneCorrectly(t *testing.T) {
	// GIVEN: OpenMeteo Provider, Basis-URLs zeigen auf den Fixture-Server
	// WHEN: FetchForecast fuer Mallorca (39.7, 3.0), 24h
	// THEN: Timezone-Feld ist gesetzt ("Europe/Madrid"), auf 24h gekuerzt
	fake := neuerOpenMeteoFixtureServer(t)
	ts, err := fake.provider(t).FetchForecast(39.7, 3.0, 24)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ts.Timezone == "" {
		t.Error("expected timezone to be set, got empty string")
	}
	if ts.Timezone != "Europe/Madrid" {
		t.Errorf("expected timezone 'Europe/Madrid' for Mallorca, got '%s'", ts.Timezone)
	}
	if len(ts.Data) != 24 {
		t.Errorf("expected 48h fixture truncated to 24 points, got %d", len(ts.Data))
	}
	fake.pruefeAnfragen(t)
}

// =============================================================================
// Tests 8-9: ThunderLevel Ableitung
// =============================================================================

func TestThunderLevel_WMO95_ReturnsHigh(t *testing.T) {
	// GIVEN: WMO-Code 95 (Gewitter)
	// WHEN: parseThunderLevel aufgerufen
	// THEN: ThunderHigh ("HIGH")
	level := parseThunderLevel(95)
	if level != model.ThunderHigh {
		t.Errorf("expected ThunderHigh for WMO 95, got %s", level)
	}
}

func TestThunderLevel_WMO61_ReturnsNone(t *testing.T) {
	// GIVEN: WMO-Code 61 (leichter Regen)
	// WHEN: parseThunderLevel aufgerufen
	// THEN: ThunderNone ("NONE")
	level := parseThunderLevel(61)
	if level != model.ThunderNone {
		t.Errorf("expected ThunderNone for WMO 61, got %s", level)
	}
}
