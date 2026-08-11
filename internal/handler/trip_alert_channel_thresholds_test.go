package handler

// Issue #1461 Scheibe S3b-2a — AlertChannelThresholds-Pointer-Feld auf Trip:
// ZWEI Ebenen Datenverlustschutz, beide Pflicht (nicht Kann): Top-Level-nil-
// Erbe (AC-6, Muster OfficialWarnings) UND Feld-Level-Merge INNERHALB des
// Unterobjekts (AC-7, Muster OfficialWarnings.Sources, Fix-Loop F002).
//
// Spec: docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md AC-6/AC-7.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func strPtr(s string) *string { return &s }

// AC-6: PUT ohne alert_channel_thresholds im Body laesst eine zuvor gesetzte
// Schwelle unveraendert -- Top-Level-nil-Erbe (Datenverlust-Schutz analog
// BUG-DATALOSS-GR221).
func TestUpdateTripHandler_AlertChannelThresholdsPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1461-ac6",
		Name: "AC6-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Telegram: strPtr("HIGH"),
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT-Body OHNE alert_channel_thresholds — nur "name" geaendert.
	body := map[string]interface{}{"name": "AC6-Test (umbenannt)"}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1461-ac6", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1461-ac6")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Telegram == nil ||
		*loaded.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"alert_channel_thresholds erased by PUT without field: expected telegram=HIGH, got %+v",
			loaded.AlertChannelThresholds,
		)
	}
	if loaded.Name != "AC6-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
}

// AC-7: PUT mit alert_channel_thresholds, das nur EINEN der zwei zuvor
// gesetzten Kanaele mitschickt, darf den anderen, nicht angefassten Kanal
// nicht loeschen -- Feld-Level-Merge INNERHALB des Unterobjekts (Fix-Loop
// F002-Muster von OfficialWarnings.Sources).
func TestUpdateTripHandler_AlertChannelThresholdsFieldLevelMergePreservesUntouchedChannel(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1461-ac7",
		Name: "AC7-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email:    strPtr("MODERATE"),
			Telegram: strPtr("HIGH"),
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT aendert NUR telegram, email fehlt im Unterobjekt komplett.
	body := map[string]interface{}{
		"alert_channel_thresholds": map[string]interface{}{"telegram": "LOW"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1461-ac7", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1461-ac7")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Telegram == nil ||
		*loaded.AlertChannelThresholds.Telegram != "LOW" {
		t.Fatalf("expected telegram=LOW applied, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.Email == nil || *loaded.AlertChannelThresholds.Email != "MODERATE" {
		t.Errorf(
			"AC-7: email erased by telegram-only PUT, expected MODERATE (unangetastet), got %+v",
			loaded.AlertChannelThresholds.Email,
		)
	}
}

// AC-7 fuer Premium-SMS (#1701 S2b, D6): vierter Schwellenwert-Fall,
// identisches Muster wie TestUpdateTripHandler_AlertChannelThresholdsField
// LevelMergePreservesUntouchedChannel oben, nur fuer das neue Geschwister-
// feld PremiumSms statt Email/Telegram/Sms.
func TestUpdateTripHandler_AlertChannelThresholdsPremiumSmsFieldLevelMerge(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1701-thr-premium",
		Name: "PremiumSms-Threshold-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{
			Email: strPtr("MODERATE"), PremiumSms: strPtr("HIGH"),
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT aendert NUR email, premium_sms fehlt im Unterobjekt komplett.
	body := map[string]interface{}{
		"alert_channel_thresholds": map[string]interface{}{"email": "LOW"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1701-thr-premium", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1701-thr-premium")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.AlertChannelThresholds == nil || loaded.AlertChannelThresholds.Email == nil ||
		*loaded.AlertChannelThresholds.Email != "LOW" {
		t.Fatalf("expected email=LOW applied, got %+v", loaded.AlertChannelThresholds)
	}
	if loaded.AlertChannelThresholds.PremiumSms == nil ||
		*loaded.AlertChannelThresholds.PremiumSms != "HIGH" {
		t.Errorf(
			"premium_sms erased by email-only PUT, expected HIGH (unangetastet), got %+v",
			loaded.AlertChannelThresholds.PremiumSms,
		)
	}
}

// Gegenprobe: ein neu angelegter Trip ohne alert_channel_thresholds bleibt
// nil (Startwert "LOW" je Kanal wird von Python code-seitig angenommen,
// nicht hier persistiert).
func TestCreateTripHandler_AlertChannelThresholdsDefaultsNil(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"id":   "trip-1461-create",
		"name": "Neuanlage",
		"stages": []map[string]interface{}{{
			"id": "S1", "name": "D1", "date": "2026-07-15",
			"waypoints": []map[string]interface{}{{
				"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
			}},
		}},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/trips", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1461-create")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.AlertChannelThresholds != nil {
		t.Errorf("expected nil alert_channel_thresholds on a fresh trip, got %+v", loaded.AlertChannelThresholds)
	}
}

// F004 (Adversary Runde 2, LOW): CLAUDE.md verlangt fuer jeden neuen daten-
// bewegenden Endpunkt einen Test mit ZWEI verschiedenen Nutzern. PUT
// /api/trips/{id} mit alert_channel_thresholds ist ein neuer, datenbewegender
// Aufrufpfad -- Nutzer A aendert die Schwelle seines Trips, der gleichnamige
// Trip von Nutzer B (eigenes Verzeichnis, eigener Store) bleibt unangetastet.
// Muster: TestUpdateTripHandler_OfficialWarningsCrossUserIsolation.
func TestUpdateTripHandler_AlertChannelThresholdsCrossUserIsolation(t *testing.T) {
	baseDir := t.TempDir()
	sA := store.New(baseDir, "usera-1461")
	sB := store.New(baseDir, "userb-1461")

	tripA := model.Trip{
		ID: "trip-1461-shared", Name: "Nutzer A Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{Telegram: strPtr("LOW")},
	}
	tripB := model.Trip{
		ID: "trip-1461-shared", Name: "Nutzer B Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannelThresholds: &model.AlertChannelThresholdsConfig{Telegram: strPtr("MODERATE")},
	}
	if err := sA.SaveTrip(&tripA); err != nil {
		t.Fatalf("SaveTrip A: %v", err)
	}
	if err := sB.SaveTrip(&tripB); err != nil {
		t.Fatalf("SaveTrip B: %v", err)
	}

	// Nutzer A setzt telegram auf HIGH ueber PUT.
	body := map[string]interface{}{
		"alert_channel_thresholds": map[string]interface{}{"telegram": "HIGH"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(sA))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1461-shared", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera-1461")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := sA.LoadTrip("trip-1461-shared")
	if err != nil {
		t.Fatalf("LoadTrip usera: %v", err)
	}
	if loadedA.AlertChannelThresholds == nil || loadedA.AlertChannelThresholds.Telegram == nil ||
		*loadedA.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf("expected usera telegram=HIGH after PUT, got %+v", loadedA.AlertChannelThresholds)
	}

	// Nutzer B's gleichnamiger Trip darf weder Name noch Schwelle verlieren.
	loadedB, err := sB.LoadTrip("trip-1461-shared")
	if err != nil {
		t.Fatalf("LoadTrip userb: %v", err)
	}
	if loadedB.Name != "Nutzer B Trip" {
		t.Errorf("cross-user leak: userb's trip name changed to %q", loadedB.Name)
	}
	if loadedB.AlertChannelThresholds == nil || loadedB.AlertChannelThresholds.Telegram == nil ||
		*loadedB.AlertChannelThresholds.Telegram != "MODERATE" {
		t.Errorf(
			"cross-user leak: userb's alert_channel_thresholds changed by usera's PUT, "+
				"expected unveraendert telegram=MODERATE (Nutzer B's eigener Ursprungswert, "+
				"NICHT usera's neuer Wert HIGH), got %+v",
			loadedB.AlertChannelThresholds,
		)
	}

	// Gegenrichtung (Adversary Runde 3): Nutzer B setzt jetzt SEINERSEITS eine
	// Schwelle per PUT -- Nutzer A's Wert (gerade erst auf HIGH gesetzt) darf
	// davon unberuehrt bleiben. Isolation muss richtungsunabhaengig gelten,
	// nicht nur A->B.
	bodyB := map[string]interface{}{
		"alert_channel_thresholds": map[string]interface{}{"telegram": "LOW"},
	}
	bufB, _ := json.Marshal(bodyB)

	rB := chi.NewRouter()
	rB.Put("/api/trips/{id}", UpdateTripHandler(sB))
	reqB := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1461-shared", bytes.NewReader(bufB))
	reqB.Header.Set("Content-Type", "application/json")
	reqB = addUserToContext(reqB, "userb-1461")
	wB := httptest.NewRecorder()
	rB.ServeHTTP(wB, reqB)

	if wB.Code != http.StatusOK {
		t.Fatalf("expected 200 for userb PUT, got %d: %s", wB.Code, wB.Body.String())
	}

	loadedB2, err := sB.LoadTrip("trip-1461-shared")
	if err != nil {
		t.Fatalf("LoadTrip userb (2nd): %v", err)
	}
	if loadedB2.AlertChannelThresholds == nil || loadedB2.AlertChannelThresholds.Telegram == nil ||
		*loadedB2.AlertChannelThresholds.Telegram != "LOW" {
		t.Errorf("expected userb telegram=LOW after userb's own PUT, got %+v", loadedB2.AlertChannelThresholds)
	}

	// Nutzer A's Trip darf durch userb's PUT nicht angetastet werden.
	loadedA2, err := sA.LoadTrip("trip-1461-shared")
	if err != nil {
		t.Fatalf("LoadTrip usera (2nd): %v", err)
	}
	if loadedA2.Name != "Nutzer A Trip" {
		t.Errorf("cross-user leak (B->A): usera's trip name changed to %q", loadedA2.Name)
	}
	if loadedA2.AlertChannelThresholds == nil || loadedA2.AlertChannelThresholds.Telegram == nil ||
		*loadedA2.AlertChannelThresholds.Telegram != "HIGH" {
		t.Errorf(
			"cross-user leak (B->A): usera's alert_channel_thresholds changed by userb's PUT, "+
				"expected unveraendert telegram=HIGH (usera's Wert aus dem ersten PUT, "+
				"NICHT userb's neuer Wert LOW), got %+v",
			loadedA2.AlertChannelThresholds,
		)
	}
}
