// Ausblick-Schalter eines Ortsvergleichs ueber den Go-Speicherweg (AC-13 aus
// docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md).
//
// Issue #3277 (docs/specs/modules/feat_3277_altfelder_entfernen.md, AC-6/AC-11):
// das Altfeld des Ausblick-Schalters ist aus model.ComparePreset entfernt
// (ADR-0124 Nr. 6). Der ausgeschaltete 3-Tages-Ausblick steht seither allein
// in der Tabelle "Was steht wo": display_config.placements.outlook_reports = [].
// Die beiden Tests pruefen dieselbe Nutzerzusage wie zuvor (ausgeschaltet
// bleibt ausgeschaltet; ein PUT ohne das Feld loescht nichts) an der neuen
// Quelle.

package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
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

// ausblickBerichte liest display_config.placements.outlook_reports aus einer
// GET-Antwort; ok=false, wenn der Schluessel fehlt.
func ausblickBerichte(got map[string]interface{}) (interface{}, bool) {
	dc, _ := got["display_config"].(map[string]interface{})
	pl, _ := dc["placements"].(map[string]interface{})
	if pl == nil {
		return nil, false
	}
	v, ok := pl["outlook_reports"]
	return v, ok
}

func ausblickAusBody(name string) map[string]interface{} {
	return map[string]interface{}{
		"name":         name,
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    9,
		"hour_to":      16,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"display_config": map[string]interface{}{
			"placements": map[string]interface{}{
				"version": 1, "rows": []interface{}{}, "outlook_reports": []interface{}{},
			},
		},
	}
}

// AC-13: Der Nutzer schaltet den 3-Tages-Ausblick aus (Tabelle: keine
// Briefings mit Ausblick). Nach dem Speichern und erneutem Laden bleibt er aus.
func TestUpdateComparePreset_OutlookEnabledFalseSurvivesRoundtrip(t *testing.T) {
	s := newTestStore(t)
	seedOutlookPreset(t, s, "cp-outlook-off")

	putComparePresetRaw(t, s, "cp-outlook-off", ausblickAusBody("Vergleich mit Ausblick"))

	got := getComparePresetRaw(t, s, "cp-outlook-off")
	val, ok := ausblickBerichte(got)
	if !ok {
		t.Fatalf("placements.outlook_reports fehlt in der GET-Antwort — der ausgeschaltete "+
			"3-Tages-Ausblick geht beim Go-seitigen Speichern verloren (AC-13). Antwort: %v", got)
	}
	if !reflect.DeepEqual(val, []interface{}{}) {
		t.Errorf("expected outlook_reports=[] nach dem Speichern, got %v", val)
	}
	if _, da := got["outlook_enabled"]; da {
		t.Errorf("Altfeld outlook_enabled darf nicht mehr als Feld erscheinen (#3277): %v", got)
	}
}

// AC-13 (Datenverlust-Schutz, CLAUDE.md): Ein PUT OHNE display_config (Client,
// der nur den Namen aendert) darf den ausgeschalteten Ausblick nicht loeschen.
func TestUpdateComparePreset_OutlookEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	seedOutlookPreset(t, s, "cp-outlook-rmw")

	putComparePresetRaw(t, s, "cp-outlook-rmw", ausblickAusBody("Vergleich mit Ausblick"))

	// Zweiter PUT: nur der Name aendert sich, die Tabelle fehlt im Body.
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
	val, ok := ausblickBerichte(got)
	if !ok {
		t.Fatalf("placements.outlook_reports wurde durch einen PUT ohne Tabelle geloescht "+
			"(Read-Modify-Write fehlt, AC-13). Antwort: %v", got)
	}
	if !reflect.DeepEqual(val, []interface{}{}) {
		t.Errorf("expected outlook_reports=[] erhalten, got %v", val)
	}
	if got["name"] != "Vergleich mit Ausblick (umbenannt)" {
		t.Errorf("expected name updated, got %v", got["name"])
	}
}
