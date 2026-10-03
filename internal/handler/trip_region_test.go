package handler

// Issue #202: Trip.Region — optionales Freitext-Feld.
// TDD RED — Tests fallen, bis Region im Struct + DTO + Merge-Block implementiert ist.
//
// Spec: docs/specs/modules/issue_202_region_feld.md
// AC-1: Region nach POST wieder via GET abrufbar.
// AC-3: Region bleibt nach PUT ohne region-Feld erhalten (Read-Modify-Write).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-1: POST mit "region":"Korsika" → gespeicherte Region wieder lesbar.
func TestTripRegion_CreateAndRead(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"region-create","name":"Korsika-Trip","region":"Korsika","stages":[` +
		`{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[` +
		`{"id":"W1","name":"Start","lat":42.0,"lon":9.0,"elevation_m":100}` +
		`]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// Direkt aus Store lesen (Persistenz-Check).
	got, err := s.LoadTrip("region-create")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Korsika" {
		t.Errorf("AC-1 FAIL: got.Region = %q, want %q", got.Region, "Korsika")
	}

	// Auch via HTTP-GET pruefen, dass das Feld in der JSON-Antwort steht.
	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	req2 := httptest.NewRequest("GET", "/api/trips/region-create", nil)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	if w2.Code != 200 {
		t.Fatalf("expected 200, got %d", w2.Code)
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w2.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if resp["region"] != "Korsika" {
		t.Errorf("AC-1 FAIL: JSON response region = %v, want %q", resp["region"], "Korsika")
	}
}

// AC-3: Trip mit region:"Korsika" + PUT ohne region-Feld → region bleibt erhalten.
func TestTripRegion_PreservedOnUpdate(t *testing.T) {
	s := newTestStore(t)

	// Seed Trip mit Region direkt im Store.
	seed := model.Trip{
		ID: "region-keep", Name: "Korsika-Trip", Region: "Korsika",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 100}},
		}},
	}
	if err := s.SaveTrip(&seed); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	// PUT mit nur name+stages — kein region-Feld im Body.
	body := `{"id":"region-keep","name":"Korsika-Renamed","stages":[` +
		`{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[` +
		`{"id":"W1","name":"Start","lat":42.0,"lon":9.0,"elevation_m":100}` +
		`]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/region-keep", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("region-keep")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Korsika" {
		t.Errorf("AC-3 FAIL: Region nach PUT ohne region-Feld = %q, want %q (Read-Modify-Write greift nicht)",
			got.Region, "Korsika")
	}
	if got.Name != "Korsika-Renamed" {
		t.Errorf("Name wurde nicht aktualisiert: got %q", got.Name)
	}
}

// Bonus-Test: PUT mit explizitem region-Wert ersetzt das Feld.
func TestTripRegion_UpdateReplacesWhenSent(t *testing.T) {
	s := newTestStore(t)

	seed := model.Trip{
		ID: "region-replace", Name: "Trip", Region: "Korsika",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 100}},
		}},
	}
	if err := s.SaveTrip(&seed); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"region":"Mallorca"}`
	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/region-replace", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("region-replace")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Mallorca" {
		t.Errorf("Region nach PUT mit region:\"Mallorca\" = %q, want %q", got.Region, "Mallorca")
	}
}

// Issue #2284 Scheibe S2, AC-7 (Spec docs/specs/modules/feat_2284_s2_trip_kopf.md):
// Nutzer B schickt genau den Rumpf, den der neue Trip-Kopf beim Region-Speichern
// sendet ({"region":"fremd"}), gegen die Trip-ID von Nutzer A. Erwartet: 404,
// A's Datei auf der Platte byte-gleich, unter B nichts angelegt, A liest seine
// alte Region und kann sie danach selbst aendern. Zwei echte Nutzer, echte
// Dateien (t.TempDir()), Router wie im Frontend-Weg (chi-URL-Param).
// Waechter: der Handler isoliert bereits per s.WithUser(UserIDFromContext) —
// die Mutation "fester Nutzer statt Kontext" muss diesen Test rot machen.
func TestUpdateTripHandler_Region_CrossUser_404_AFileUntouched(t *testing.T) {
	const (
		userA  = "usera-2284"
		userB  = "userb-2284"
		tripID = "region-mandant-2284"
	)
	base := t.TempDir()
	sA := store.New(base, userA)

	seed := model.Trip{
		ID: tripID, Name: "Trip von A", Region: "Alpen Sued",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	if err := sA.SaveTrip(&seed); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	// Ablage seit #1250 S7a: briefings/<id>.json (trips/ nur noch Rollback-Altbestand).
	fileA := filepath.Join(sA.BriefingsDir(), tripID+".json")
	sB := store.New(base, userB)
	fileB := filepath.Join(sB.BriefingsDir(), tripID+".json")
	fileBLegacy := filepath.Join(base, "users", userB, "trips", tripID+".json")
	before, err := os.ReadFile(fileA)
	if err != nil {
		t.Fatalf("A's Trip-Datei nicht am erwarteten Ort %s: %v", fileA, err)
	}

	r := etagRouter(sA)

	cross := doReq(r, http.MethodPut, "/api/trips/"+tripID, `{"region":"fremd"}`, "", userB)
	if cross.Code != http.StatusNotFound {
		// Errorf statt Fatalf: die Datei-Pruefungen danach sollen den Schaden
		// zusaetzlich zeigen (Status allein beweist nicht, was auf der Platte steht).
		t.Errorf("AC-7 FAIL: PUT von B auf A's Trip: expected 404, got %d: %s",
			cross.Code, cross.Body.String())
	}

	after, err := os.ReadFile(fileA)
	if err != nil {
		t.Fatalf("A's Trip-Datei nach fremdem PUT nicht lesbar: %v", err)
	}
	if !bytes.Equal(before, after) {
		t.Errorf("AC-7 FAIL: A's Trip-Datei wurde durch B's PUT veraendert\nvorher:  %s\nnachher: %s",
			before, after)
	}
	for _, f := range []string{fileB, fileBLegacy} {
		if _, err := os.Stat(f); !os.IsNotExist(err) {
			t.Errorf("AC-7 FAIL: unter Nutzer B wurde eine Trip-Datei angelegt (%s), err=%v", f, err)
		}
	}

	getA := doReq(r, http.MethodGet, "/api/trips/"+tripID, "", "", userA)
	if getA.Code != 200 {
		t.Fatalf("GET von A: expected 200, got %d: %s", getA.Code, getA.Body.String())
	}
	var respA map[string]interface{}
	if err := json.Unmarshal(getA.Body.Bytes(), &respA); err != nil {
		t.Fatalf("GET von A: kein JSON: %v", err)
	}
	if respA["region"] != "Alpen Sued" {
		t.Errorf("AC-7 FAIL: A liest region=%v, want %q", respA["region"], "Alpen Sued")
	}

	own := doReq(r, http.MethodPut, "/api/trips/"+tripID, `{"region":"Alpen Nord"}`, "", userA)
	if own.Code != 200 {
		t.Fatalf("AC-7 FAIL: A kann seine Region nicht mehr aendern: expected 200, got %d: %s",
			own.Code, own.Body.String())
	}
	loadedA, err := sA.LoadTrip(tripID)
	if err != nil || loadedA == nil {
		t.Fatalf("A's Trip nach eigenem PUT nicht ladbar: %v", err)
	}
	if loadedA.Region != "Alpen Nord" {
		t.Errorf("AC-7 FAIL: A's Region nach eigenem PUT = %q, want %q", loadedA.Region, "Alpen Nord")
	}
	if loadedA.Name != "Trip von A" || len(loadedA.Stages) != 1 {
		t.Errorf("AC-7 FAIL: A's eigener Region-PUT hat andere Felder veraendert: %+v", loadedA)
	}
}
