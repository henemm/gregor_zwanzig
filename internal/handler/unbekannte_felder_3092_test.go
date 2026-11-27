package handler

// TDD RED — Issue #3092 (ADR-0101): Go-Schreibwege (PUT, State-PATCH) bewahren
// dem Go-Modell unbekannte Top-Level-Felder in der Datei auf der Platte.
// Spec: docs/specs/modules/fix_3092_unbekannte_felder_erhalten.md — AC-1, AC-2, AC-3, AC-5.
//
// Mock-frei: echter Store auf t.TempDir() + httptest, echte Auth-Kontexte
// (addUserToContext) fuer zwei verschiedene Nutzer. Geprueft wird der
// Dateiinhalt, nicht nur die Antwort.

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

const uf3092Fremd = `{"x":1,"liste":["a","b"]}`

func uf3092Router(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	return r
}

func uf3092Pfad(s *store.Store, user, id string) string {
	return filepath.Join(s.WithUser(user).BriefingsDir(), id+".json")
}

func uf3092Schreiben(t *testing.T, s *store.Store, user, id, inhalt string) {
	t.Helper()
	p := uf3092Pfad(s, user, id)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(inhalt), 0o644); err != nil {
		t.Fatal(err)
	}
}

func uf3092Roh(t *testing.T, s *store.Store, user, id string) map[string]json.RawMessage {
	t.Helper()
	data, err := os.ReadFile(uf3092Pfad(s, user, id))
	if err != nil {
		t.Fatalf("Datei lesen (%s/%s): %v", user, id, err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("Datei kein JSON-Objekt: %v", err)
	}
	return m
}

func uf3092PresetJSON(id, extra string) string {
	return `{"id":"` + id + `","name":"Vergleich","kind":"vergleich",` +
		`"location_ids":["loc-a","loc-b"],"schedule":"daily","profil":"ALLGEMEIN",` +
		`"created_at":"2026-09-01T00:00:00Z"` + extra + `}`
}

func uf3092TripJSON(id, extra string) string {
	return `{"id":"` + id + `","name":"Tour","kind":"route","stages":[{"id":"S1","name":"Tag 1",` +
		`"date":"2026-08-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":800}]}]` +
		extra + `}`
}

const uf3092TripPut = `{"name":"Tour neu","stages":[{"id":"S1","name":"Tag 1","date":"2026-08-01",` +
	`"waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":800}]}]}`

func uf3092FremdfeldDa(t *testing.T, raw map[string]json.RawMessage, wo string) {
	t.Helper()
	got, ok := raw["zukunftsfeld"]
	if !ok {
		t.Errorf("%s: zukunftsfeld fehlt in der Datei", wo)
		return
	}
	var a, b interface{}
	_ = json.Unmarshal(got, &a)
	_ = json.Unmarshal([]byte(uf3092Fremd), &b)
	am, _ := json.Marshal(a)
	bm, _ := json.Marshal(b)
	if string(am) != string(bm) {
		t.Errorf("%s: zukunftsfeld veraendert: %s", wo, am)
	}
}

func uf3092Pruefe200(t *testing.T, code int, body, wo string) {
	t.Helper()
	if code != http.StatusOK {
		t.Fatalf("%s: erwartet 200, bekommen %d: %s", wo, code, body)
	}
}

// AC-1: PUT Orts-Vergleich bewahrt unbekanntes Feld auf der Platte.
func TestUnbekannteFelder3092_AC1_PresetPutBehaeltFeld(t *testing.T) {
	s := newTestStore(t)
	r := uf3092Router(s)
	uf3092Schreiben(t, s, "alice", "p1", uf3092PresetJSON("p1", `,"zukunftsfeld":`+uf3092Fremd))

	w := doReq(r, http.MethodPut, "/api/compare/presets/p1", `{"name":"Vergleich neu"}`, "", "alice")
	uf3092Pruefe200(t, w.Code, w.Body.String(), "PUT preset")

	raw := uf3092Roh(t, s, "alice", "p1")
	if string(raw["name"]) != `"Vergleich neu"` {
		t.Errorf("gewollte Aenderung fehlt: name=%s", raw["name"])
	}
	uf3092FremdfeldDa(t, raw, "PUT preset")
}

// AC-2: PUT Trip bewahrt unbekanntes Feld auf der Platte.
func TestUnbekannteFelder3092_AC2_TripPutBehaeltFeld(t *testing.T) {
	s := newTestStore(t)
	r := uf3092Router(s)
	uf3092Schreiben(t, s, "alice", "t1", uf3092TripJSON("t1", `,"zukunftsfeld":`+uf3092Fremd))

	w := doReq(r, http.MethodPut, "/api/trips/t1", uf3092TripPut, "", "alice")
	uf3092Pruefe200(t, w.Code, w.Body.String(), "PUT trip")

	raw := uf3092Roh(t, s, "alice", "t1")
	if string(raw["name"]) != `"Tour neu"` {
		t.Errorf("gewollte Aenderung fehlt: name=%s", raw["name"])
	}
	uf3092FremdfeldDa(t, raw, "PUT trip")
}

// AC-3: State-PATCH (Orts-Vergleich archivieren, Trip pausieren) bewahrt das Feld.
func TestUnbekannteFelder3092_AC3_StatePatchBehaeltFeld(t *testing.T) {
	s := newTestStore(t)
	r := uf3092Router(s)
	uf3092Schreiben(t, s, "alice", "p1", uf3092PresetJSON("p1", `,"zukunftsfeld":`+uf3092Fremd))
	uf3092Schreiben(t, s, "alice", "t1", uf3092TripJSON("t1", `,"zukunftsfeld":`+uf3092Fremd))

	w := doReq(r, http.MethodPatch, "/api/compare/presets/p1/state", `{"archived":true}`, "", "alice")
	uf3092Pruefe200(t, w.Code, w.Body.String(), "PATCH preset state")
	raw := uf3092Roh(t, s, "alice", "p1")
	if _, ok := raw["archived_at"]; !ok {
		t.Errorf("Archivierung nicht gespeichert")
	}
	uf3092FremdfeldDa(t, raw, "PATCH preset state")

	w = doReq(r, http.MethodPatch, "/api/trips/t1/state", `{"paused":true}`, "", "alice")
	uf3092Pruefe200(t, w.Code, w.Body.String(), "PATCH trip state")
	raw = uf3092Roh(t, s, "alice", "t1")
	if _, ok := raw["paused_at"]; !ok {
		t.Errorf("Pausieren nicht gespeichert")
	}
	uf3092FremdfeldDa(t, raw, "PATCH trip state")
}

// AC-5: zwei Nutzer — B's Speichern beruehrt A nicht, B bekommt kein fremdes Feld,
// A behaelt sein Feld beim eigenen Speichern.
func TestUnbekannteFelder3092_AC5_ZweiNutzer(t *testing.T) {
	type fall struct {
		name, id, pfad, put string
		datei              func(id, extra string) string
	}
	faelle := []fall{
		{"preset", "gemeinsam", "/api/compare/presets/gemeinsam", `{"name":"Neu"}`, uf3092PresetJSON},
		{"trip", "gemeinsam", "/api/trips/gemeinsam", uf3092TripPut, uf3092TripJSON},
	}
	for _, f := range faelle {
		f := f
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			r := uf3092Router(s)
			uf3092Schreiben(t, s, "alice", f.id, f.datei(f.id, `,"zukunftsfeld":`+uf3092Fremd))
			uf3092Schreiben(t, s, "bob", f.id, f.datei(f.id, ""))
			vorA, _ := os.ReadFile(uf3092Pfad(s, "alice", f.id))

			w := doReq(r, http.MethodPut, f.pfad, f.put, "", "bob")
			uf3092Pruefe200(t, w.Code, w.Body.String(), "PUT bob")
			nachA, _ := os.ReadFile(uf3092Pfad(s, "alice", f.id))
			if string(vorA) != string(nachA) {
				t.Errorf("Speichern von bob hat die Datei von alice veraendert")
			}
			if _, ok := uf3092Roh(t, s, "bob", f.id)["zukunftsfeld"]; ok {
				t.Errorf("bob's Datei enthaelt fremdes Feld von alice")
			}

			w = doReq(r, http.MethodPut, f.pfad, f.put, "", "alice")
			uf3092Pruefe200(t, w.Code, w.Body.String(), "PUT alice")
			uf3092FremdfeldDa(t, uf3092Roh(t, s, "alice", f.id), "PUT alice")
		})
	}
}
