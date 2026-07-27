// VORBEREITETER GO-TEST (AC-13) — konnte in der RED-Phase NICHT abgelegt werden.
//
// Zielpfad: internal/handler/compare_preset_outlook_enabled_test.go
// Blocker:  core/hooks/edit_gate.py — "Phase phase5_tdd_red does not allow code
//           edits". Go-Tests muessen im Paketverzeichnis liegen (package
//           handler); dort gibt es keine vom Gate erlaubte tests/-Komponente.
//           In der Implementierungsphase (phase6_implement) 1:1 unter dem
//           Zielpfad ablegen und mitlaufen lassen.
//
// Spec: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md § AC-13
//
// Bewusst ueber rohes JSON (PUT-Body + GET-Antwort) statt ueber ein
// Struct-Feld: so kompiliert der Test auch VOR der Ergaenzung von
// model.ComparePreset.OutlookEnabled und scheitert an einer inhaltlichen
// Aussage statt an einem Compile-Fehler, der alle uebrigen Tests des Pakets
// mitreissen wuerde.

package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func seedOutlookPreset(t *testing.T, s *store.Store, id string) {
	t.Helper()
	preset := model.ComparePreset{
		ID:          id,
		Name:        "Vergleich mit Ausblick",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    9,
		HourTo:      16,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}
}

func putComparePresetRaw(t *testing.T, s *store.Store, id string, body map[string]interface{}) {
	t.Helper()
	buf, _ := json.Marshal(body)
	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/"+id, bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func getComparePresetRaw(t *testing.T, s *store.Store, id string) map[string]interface{} {
	t.Helper()
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodGet, "/api/compare/presets/"+id, nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("GET: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var out map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("GET: response is not JSON: %v (%s)", err, w.Body.String())
	}
	return out
}

// AC-13: Der Nutzer schaltet den 3-Tages-Ausblick aus. Nach dem Speichern und
// erneutem Laden muss er ausgeschaltet bleiben.
func TestUpdateComparePreset_OutlookEnabledFalseSurvivesRoundtrip(t *testing.T) {
	s := newTestStore(t)
	seedOutlookPreset(t, s, "cp-outlook-off")

	putComparePresetRaw(t, s, "cp-outlook-off", map[string]interface{}{
		"name":            "Vergleich mit Ausblick",
		"schedule":        "manual",
		"profil":          "SUMMER_TREKKING",
		"hour_from":       9,
		"hour_to":         16,
		"location_ids":    []string{"loc-a"},
		"empfaenger":      []string{"a@example.com"},
		"outlook_enabled": false,
	})

	got := getComparePresetRaw(t, s, "cp-outlook-off")
	val, ok := got["outlook_enabled"]
	if !ok {
		t.Fatalf("outlook_enabled fehlt in der GET-Antwort — der ausgeschaltete "+
			"3-Tages-Ausblick geht beim Go-seitigen Speichern verloren (AC-13). "+
			"Antwort: %v", got)
	}
	if val != false {
		t.Errorf("expected outlook_enabled=false nach dem Speichern, got %v", val)
	}
}

// AC-13 (Datenverlust-Schutz, CLAUDE.md): Ein PUT OHNE outlook_enabled (Client,
// der das Feld nicht kennt) darf einen gesetzten Wert nicht loeschen —
// nil-Preserve-Block analog HourlyEnabled (compare_preset.go:317-320).
func TestUpdateComparePreset_OutlookEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	seedOutlookPreset(t, s, "cp-outlook-rmw")

	putComparePresetRaw(t, s, "cp-outlook-rmw", map[string]interface{}{
		"name":            "Vergleich mit Ausblick",
		"schedule":        "manual",
		"profil":          "SUMMER_TREKKING",
		"hour_from":       9,
		"hour_to":         16,
		"location_ids":    []string{"loc-a"},
		"empfaenger":      []string{"a@example.com"},
		"outlook_enabled": false,
	})

	// Zweiter PUT: nur der Name aendert sich, das Feld fehlt im Body.
	putComparePresetRaw(t, s, "cp-outlook-rmw", map[string]interface{}{
		"name":         "Vergleich mit Ausblick (umbenannt)",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    9,
		"hour_to":      16,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	})

	got := getComparePresetRaw(t, s, "cp-outlook-rmw")
	val, ok := got["outlook_enabled"]
	if !ok {
		t.Fatalf("outlook_enabled wurde durch einen PUT ohne dieses Feld geloescht "+
			"(Read-Modify-Write fehlt, AC-13). Antwort: %v", got)
	}
	if val != false {
		t.Errorf("expected outlook_enabled=false erhalten, got %v", val)
	}
	if got["name"] != "Vergleich mit Ausblick (umbenannt)" {
		t.Errorf("expected name updated, got %v", got["name"])
	}
}
