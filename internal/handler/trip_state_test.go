package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

// dispatchPatchState invokes UpdateTripStateHandler via chi router
// so chi.URLParam works.
func dispatchPatchState(t *testing.T, id, body string) *httptest.ResponseRecorder {
	t.Helper()
	s := newTestStore(t)
	seedTrip(t, s, "existing", "Existing")
	if id != "existing" {
		// allow caller to provoke 404 by using a different id
	}

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	req := httptest.NewRequest("PATCH", "/api/trips/"+id+"/state", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// patchState executes a PATCH /state call against an existing store.
// Used when multiple calls on the same trip are needed (Idempotenz, Toggle).
func patchState(t *testing.T, h http.Handler, id, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("PATCH", "/api/trips/"+id+"/state", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

// AC-5: PATCH /state mit {"paused": true} → 200 + paused_at gesetzt.
func TestUpdateTripStateHandlerPauseSetsTimestamp(t *testing.T) {
	w := dispatchPatchState(t, "existing", `{"paused": true}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("response body not JSON: %v", err)
	}
	pausedAt, ok := resp["paused_at"]
	if !ok || pausedAt == nil || pausedAt == "" {
		t.Errorf("expected paused_at to be set, got %v (full=%v)", pausedAt, resp)
	}
	// Sanity-Check: parsbar als RFC3339
	s, isString := pausedAt.(string)
	if !isString {
		t.Errorf("expected paused_at to be a string, got %T", pausedAt)
	} else if _, err := time.Parse(time.RFC3339, s); err != nil {
		// Auch z.B. RFC3339Nano akzeptieren
		if _, err2 := time.Parse(time.RFC3339Nano, s); err2 != nil {
			t.Errorf("paused_at not a valid RFC3339 timestamp: %q (%v)", s, err)
		}
	}
}

// AC-6: PATCH /state mit {"paused": false} auf paused trip → 200 + paused_at gelöscht.
func TestUpdateTripStateHandlerResumeClearsTimestamp(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "to-resume", "Resume Me")

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))

	// Pause first
	if w := patchState(t, r, "to-resume", `{"paused": true}`); w.Code != 200 {
		t.Fatalf("setup pause failed: %d", w.Code)
	}
	// Resume
	w := patchState(t, r, "to-resume", `{"paused": false}`)
	if w.Code != 200 {
		t.Fatalf("expected 200 on resume, got %d: %s", w.Code, w.Body.String())
	}
	got, err := s.LoadTrip("to-resume")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.PausedAt != nil {
		t.Errorf("expected paused_at == nil after resume, got %v", *got.PausedAt)
	}
}

// AC-7: Idempotenz — zweimal {"paused": true} → 200 OK, Trip bleibt pausiert.
func TestUpdateTripStateHandlerPauseTwiceIsIdempotentOnResult(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "double-pause", "Double Pause")

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))

	if w := patchState(t, r, "double-pause", `{"paused": true}`); w.Code != 200 {
		t.Fatalf("first pause failed: %d", w.Code)
	}
	if w := patchState(t, r, "double-pause", `{"paused": true}`); w.Code != 200 {
		t.Fatalf("second pause failed: %d", w.Code)
	}
	got, err := s.LoadTrip("double-pause")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.PausedAt == nil {
		t.Error("expected trip to remain paused (paused_at != nil) after double pause")
	}
}

// AC-8: 404 wenn Trip-ID nicht existiert.
func TestUpdateTripStateHandlerNotFound(t *testing.T) {
	s := newTestStore(t)
	// keine seedTrip

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))

	req := httptest.NewRequest("PATCH", "/api/trips/ghost-trip/state", strings.NewReader(`{"paused": true}`))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-9: PUT /api/trips/{id} ohne paused_at im Body lässt bestehenden paused_at unverändert.
// Verifiziert, dass UpdateTripHandler die neuen Status-Felder NICHT überschreibt.
func TestUpdateTripHandlerDoesNotTouchPausedAt(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "isolated", "Isolated")

	// Erst pause via PATCH /state setzen
	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	if w := patchState(t, r, "isolated", `{"paused": true}`); w.Code != 200 {
		t.Fatalf("setup pause failed: %d", w.Code)
	}

	// PUT ohne paused_at-Feld
	putBody := `{"id":"isolated","name":"Renamed","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
	putR := chi.NewRouter()
	putR.Put("/api/trips/{id}", UpdateTripHandler(s))
	putReq := httptest.NewRequest("PUT", "/api/trips/isolated", strings.NewReader(putBody))
	putW := httptest.NewRecorder()
	putR.ServeHTTP(putW, putReq)
	if putW.Code != 200 {
		t.Fatalf("PUT failed: %d: %s", putW.Code, putW.Body.String())
	}

	got, err := s.LoadTrip("isolated")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.PausedAt == nil {
		t.Error("expected paused_at to remain set after PUT without paused_at field, got nil")
	}
	if got.Name != "Renamed" {
		t.Errorf("expected name=Renamed (PUT did apply other changes), got %q", got.Name)
	}
}

// AC-5/6 für Archive: PATCH /state mit {"archived": true} → archived_at gesetzt.
func TestUpdateTripStateHandlerArchiveSetsTimestamp(t *testing.T) {
	w := dispatchPatchState(t, "existing", `{"archived": true}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["archived_at"] == nil || resp["archived_at"] == "" {
		t.Errorf("expected archived_at to be set, got %v", resp["archived_at"])
	}
}

// PATCH /state mit beiden Feldern gleichzeitig setzt beide Timestamps.
func TestUpdateTripStateHandlerPauseAndArchiveTogether(t *testing.T) {
	w := dispatchPatchState(t, "existing", `{"paused": true, "archived": true}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["paused_at"] == nil {
		t.Error("expected paused_at set")
	}
	if resp["archived_at"] == nil {
		t.Error("expected archived_at set")
	}
}

// PATCH /state mit leerem Body {} → 200, keine Änderung.
func TestUpdateTripStateHandlerEmptyBodyNoChange(t *testing.T) {
	w := dispatchPatchState(t, "existing", `{}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["paused_at"] != nil && resp["paused_at"] != "" {
		t.Errorf("expected paused_at unset (no change), got %v", resp["paused_at"])
	}
}
