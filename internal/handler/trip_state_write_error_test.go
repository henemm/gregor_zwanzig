package handler

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
)

// AC-4 (#1066): Ein Store-Schreibfehler beim PATCH /api/trips/{id}/state
// darf den Client-Response nicht mit Dateipfad oder OS-Fehlertext verlassen —
// die Response bleibt exakt {"error":"store_error"} mit Status 500, auch
// wenn serverseitig jetzt geloggt wird (Diagnostik bleibt intern).
func TestUpdateTripStateHandler_WriteFailureReturnsGenericStoreError(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "write-fail-trip", "Write Fail Trip")

	path := filepath.Join(s.BriefingsDir(), "write-fail-trip.json")
	if err := os.Chmod(path, 0444); err != nil {
		t.Fatalf("failed to chmod trip file read-only: %v", err)
	}
	defer func() {
		_ = os.Chmod(path, 0644)
	}()

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	req := httptest.NewRequest("PATCH", "/api/trips/write-fail-trip/state", strings.NewReader(`{"paused": true}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 500 {
		t.Fatalf("expected 500 on store write failure, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if body != `{"error":"store_error"}` {
		t.Fatalf("expected exact body {\"error\":\"store_error\"}, got: %q", body)
	}
	if strings.Contains(body, path) {
		t.Errorf("response body must not leak the file path, got: %q", body)
	}
	if strings.Contains(body, "permission denied") {
		t.Errorf("response body must not leak the OS error text, got: %q", body)
	}
}
