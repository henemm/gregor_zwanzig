package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
)

// AC-4 (#1066): Ein Store-Schreibfehler beim PATCH /api/trips/{id}/state
// darf den Client-Response nicht mit Dateipfad oder OS-Fehlertext verlassen —
// die Response bleibt exakt {"error":"store_error"} mit Status 500, auch
// wenn serverseitig jetzt geloggt wird (Diagnostik bleibt intern).
func TestUpdateTripStateHandler_WriteFailureReturnsGenericStoreError(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "write-fail-trip", "Write Fail Trip")

	// Issue #1395 Scheibe 1: Der Store schreibt atomar (tmp-Datei + rename).
	// Fehler-Injektion darum ueber das schreibgeschuetzte VERZEICHNIS statt
	// ueber die schreibgeschuetzte Datei — die geprueften Zusagen aus #1066
	// (500 + generischer Body ohne Pfad/OS-Text) bleiben unveraendert.
	path := filepath.Join(s.BriefingsDir(), "write-fail-trip.json")
	if err := os.Chmod(s.BriefingsDir(), 0555); err != nil {
		t.Fatalf("failed to chmod briefings dir read-only: %v", err)
	}
	defer func() {
		_ = os.Chmod(s.BriefingsDir(), 0755)
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

	// Issue #2677: Fehlerobjekt aus dem Katalog — generischer Text, Code store_error.
	body := w.Body.String()
	var got map[string]any
	if err := json.Unmarshal([]byte(body), &got); err != nil || got["error"] != "store_error" || got["code"] != "store_error" ||
		got["message"] != i18n.T(i18n.De, "fehler.store_error", nil) || len(got) != 4 {
		t.Fatalf("expected generic store_error object, got: %q", body)
	}
	if strings.Contains(body, path) {
		t.Errorf("response body must not leak the file path, got: %q", body)
	}
	if strings.Contains(body, "permission denied") {
		t.Errorf("response body must not leak the OS error text, got: %q", body)
	}
}
