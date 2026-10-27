package handler

// Issue #2216 — Ort-Loeschen-Sperre: ein Ort, der in einem Ortsvergleich des
// Nutzers steht, wird mit 409 abgelehnt. Spec: fix_2216_ort_loeschen_sperre.md
// (AC-1..3). Geprueft wird an der HTTP-Antwort des Handlers, nicht am Store.

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func loescheOrtAls(t *testing.T, s *store.Store, uid, locID string) *httptest.ResponseRecorder {
	t.Helper()
	r := chi.NewRouter()
	r.Delete("/api/locations/{id}", DeleteLocationHandler(s))
	req := httptest.NewRequest("DELETE", "/api/locations/"+locID, nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func seedVergleich(t *testing.T, s *store.Store, id, name string, locIDs ...string) {
	t.Helper()
	p := model.ComparePreset{ID: id, Name: name, LocationIDs: locIDs, Schedule: "daily", Profil: "ALLGEMEIN"}
	if err := s.SaveComparePreset(p); err != nil {
		t.Fatalf("Vorbedingung: Ortsvergleich speichern: %v", err)
	}
}

// AC-1
func TestDeleteLocationHandler_InUse_409(t *testing.T) {
	s := newTestStore(t)
	su := s.WithUser("nutzer-a-2216")
	seedLocation(t, su, "loc-x", "Ort X")
	seedVergleich(t, su, "cmp-1", "Mein Vergleich", "loc-x", "loc-y")

	w := loescheOrtAls(t, s, "nutzer-a-2216", "loc-x")

	if w.Code != 409 {
		t.Fatalf("erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	var body struct {
		Error          string `json:"error"`
		ComparePresets []struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"compare_presets"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Body kein JSON: %v", err)
	}
	if body.Error != "location_in_use" {
		t.Errorf("error = %q, erwartet location_in_use", body.Error)
	}
	if len(body.ComparePresets) != 1 || body.ComparePresets[0].ID != "cmp-1" || body.ComparePresets[0].Name != "Mein Vergleich" {
		t.Errorf("compare_presets unerwartet: %+v", body.ComparePresets)
	}
	if loc, err := su.LoadLocation("loc-x"); err != nil || loc == nil {
		t.Errorf("Ort muss nach 409 weiter existieren: %v / %v", loc, err)
	}
}

// AC-2
func TestDeleteLocationHandler_NotInUse_204(t *testing.T) {
	s := newTestStore(t)
	su := s.WithUser("nutzer-a-2216")
	seedLocation(t, su, "loc-frei", "Freier Ort")
	seedVergleich(t, su, "cmp-1", "Anderer Vergleich", "loc-andere")

	w := loescheOrtAls(t, s, "nutzer-a-2216", "loc-frei")

	if w.Code != 204 {
		t.Fatalf("erwartet 204, bekommen %d: %s", w.Code, w.Body.String())
	}
	if loc, err := su.LoadLocation("loc-frei"); err != nil || loc != nil {
		t.Errorf("Ort muss nach 204 geloescht sein: %v / %v", loc, err)
	}
}

// F001: Fehlerpfad der Nutzungspruefung -> 500 store_error, NICHT loeschen.
// Ungueltige user_id -> ComparePresetsUsingLocation scheitert (requireUser) ->
// 500 store_error; der Ort des echten Nutzers bleibt unberuehrt. Hinweis: Der
// Store liefert sonst keinen Lesefehler (LoadComparePresets ueberspringt
// kaputte/unlesbare Dateien und meldet nur ungueltige Nutzer), daher ist das
// der einzige erreichbare Ausloeser dieses Zweigs.
func TestDeleteLocationHandler_PruefFehler_500_und_Ort_bleibt(t *testing.T) {
	s := newTestStore(t)
	su := s.WithUser("nutzer-a-2216")
	seedLocation(t, su, "loc-x", "Ort X")

	w := loescheOrtAls(t, s, "../nutzer-a-2216", "loc-x")

	if w.Code != 500 {
		t.Fatalf("erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"store_error"`) {
		t.Errorf("erwartet error=store_error, bekommen %s", w.Body.String())
	}
	if loc, err := su.LoadLocation("loc-x"); err != nil || loc == nil {
		t.Errorf("Ort muss nach Pruefungsfehler weiter existieren: %v / %v", loc, err)
	}
}

// AC-3: zwei Nutzer, gleiche Ort-ID — keine Vermischung in beide Richtungen.
func TestDeleteLocationHandler_InUse_Mandantentrennung(t *testing.T) {
	s := newTestStore(t)
	a, b := s.WithUser("nutzer-a-2216"), s.WithUser("nutzer-b-2216")
	seedLocation(t, a, "loc-x", "Ort X (A)")
	seedLocation(t, b, "loc-x", "Ort X (B)")
	seedVergleich(t, a, "cmp-a", "Vergleich von A", "loc-x")

	wB := loescheOrtAls(t, s, "nutzer-b-2216", "loc-x")
	if wB.Code != 204 {
		t.Fatalf("B: erwartet 204, bekommen %d: %s", wB.Code, wB.Body.String())
	}
	if loc, err := a.LoadLocation("loc-x"); err != nil || loc == nil {
		t.Errorf("Ort von A darf durch Loeschen von B nicht verschwinden: %v / %v", loc, err)
	}

	// B bekommt einen eigenen Vergleich; A sieht in seiner 409 nur SEINEN.
	seedLocation(t, b, "loc-x", "Ort X (B) neu")
	seedVergleich(t, b, "cmp-b", "Vergleich von B", "loc-x")
	wA := loescheOrtAls(t, s, "nutzer-a-2216", "loc-x")
	if wA.Code != 409 {
		t.Fatalf("A: erwartet 409, bekommen %d", wA.Code)
	}
	body := wA.Body.String()
	if !strings.Contains(body, "cmp-a") || strings.Contains(body, "cmp-b") || strings.Contains(body, "Vergleich von B") {
		t.Errorf("409 an A darf nur A's Vergleiche nennen: %s", body)
	}
}
