package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1398: store.LoadLocation(id) liest aus der Datei mit dem ANGEFRAGTEN
// Namen (Dateiname), store.SaveLocation(loc) schreibt in die Datei mit dem
// Namen aus loc.ID (INNERES Feld). Weicht die innere Kennung vom Dateinamen
// ab, landet jeder Schreibvorgang, der die geladene Fassung zurueckspeichert,
// in einer FREMDEN Datei — die angefragte bleibt unberuehrt, der Nutzer
// bekommt trotzdem 200.
//
// Bewusst NICHT ueber Aenderungsstempel/ETag gemessen (in #1395 S2 gemessen):
// der Stempel der unveraenderten Datei ist formal korrekt und schlaegt nicht
// an. Nur zwei Zusicherungen fangen den Schaden:
//
//	(a) die Aenderung kommt bei der ANGEFRAGTEN Ressource an
//	(b) es entsteht KEINE fremde Datei
const (
	driftRequestedID = "aussen-loc" // Dateiname = angefragte Ressource
	driftInnerID     = "innen-loc"  // abweichende innere Kennung
)

// seedDriftedLocation legt die Datei aussen-loc.json mit der abweichenden
// inneren Kennung innen-loc an — direkt auf Platte, weil SaveLocation genau
// diese Drift wieder aufloesen wuerde (es schreibt ja nach loc.ID).
func seedDriftedLocation(t *testing.T, s *store.Store) {
	t.Helper()
	dir := s.LocationsDir()
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		t.Fatalf("setup: mkdir %s: %v", dir, err)
	}
	raw := "{\"id\":\"" + driftInnerID + "\",\"name\":\"Aussen\",\"lat\":47.0,\"lon\":11.0}"
	err = os.WriteFile(filepath.Join(dir, driftRequestedID+".json"), []byte(raw), 0644)
	if err != nil {
		t.Fatalf("setup: write drifted location: %v", err)
	}
}

func readLocationFile(t *testing.T, s *store.Store, name string) map[string]interface{} {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.LocationsDir(), name+".json"))
	if err != nil {
		t.Fatalf("read %s.json: %v", name, err)
	}
	var m map[string]interface{}
	err = json.Unmarshal(data, &m)
	if err != nil {
		t.Fatalf("parse %s.json: %v", name, err)
	}
	return m
}

// assertNoForeignFile — Zusicherung (b): der Schreibvorgang darf keine zweite
// Datei unter der inneren Kennung erzeugen.
func assertNoForeignFile(t *testing.T, s *store.Store) {
	t.Helper()
	foreign := filepath.Join(s.LocationsDir(), driftInnerID+".json")
	_, err := os.Stat(foreign)
	if err == nil {
		t.Errorf("fremde Datei %s.json wurde geschrieben — der Schreibvorgang landete am falschen Ort", driftInnerID)
	} else if !os.IsNotExist(err) {
		t.Fatalf("stat %s: %v", foreign, err)
	}
}

// PATCH /api/locations/{id} — erstes Loch (PatchLocationHandler).
func TestPatchLocationWritesToRequestedFileOnIDDrift(t *testing.T) {
	s := newTestStore(t)
	seedDriftedLocation(t, s)

	r := chi.NewRouter()
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))

	req := httptest.NewRequest("PATCH", "/api/locations/"+driftRequestedID,
		strings.NewReader("{\"group_id\":\"gruppe-neu\"}"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// (a) Die Aenderung kommt bei der angefragten Ressource an.
	got := readLocationFile(t, s, driftRequestedID)
	if got["group_id"] != "gruppe-neu" {
		t.Errorf("%s.json: group_id = %v, erwartet gruppe-neu — die Aenderung kam bei der angefragten Ressource nicht an",
			driftRequestedID, got["group_id"])
	}
	// (b) Keine fremde Datei.
	assertNoForeignFile(t, s)
}

// PATCH /api/locations/{id} mit LEEREM Rumpf — haelt die Korrektur (id = id)
// unabhaengig vom Vorhandensein einzelner Patch-Felder wie group_id. Faengt
// eine Verfaelschung, die "existing.ID = id" in den group_id-Zweig
// hineinzoege: bei leerem Rumpf ist die korrigierte Kennung die einzige
// beobachtbare Wirkung.
func TestPatchLocationWritesToRequestedFileOnIDDriftWithEmptyBody(t *testing.T) {
	s := newTestStore(t)
	seedDriftedLocation(t, s)

	r := chi.NewRouter()
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))

	req := httptest.NewRequest("PATCH", "/api/locations/"+driftRequestedID,
		strings.NewReader("{}"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// (a) Die angefragte Datei traegt danach die korrigierte Kennung.
	got := readLocationFile(t, s, driftRequestedID)
	if got["id"] != driftRequestedID {
		t.Errorf("%s.json: id = %v, erwartet %s — die Kennung wurde bei leerem Rumpf nicht korrigiert",
			driftRequestedID, got["id"], driftRequestedID)
	}
	// (b) Keine fremde Datei.
	assertNoForeignFile(t, s)
}

// PUT /api/locations/{id}/weather-config — zweites Loch
// (PutLocationWeatherConfigHandler).
func TestPutLocationWeatherConfigWritesToRequestedFileOnIDDrift(t *testing.T) {
	s := newTestStore(t)
	seedDriftedLocation(t, s)

	r := chi.NewRouter()
	r.Put("/api/locations/{id}/weather-config", PutLocationWeatherConfigHandler(s))

	req := httptest.NewRequest("PUT", "/api/locations/"+driftRequestedID+"/weather-config",
		strings.NewReader("{\"theme\":\"dunkel\"}"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// (a)
	got := readLocationFile(t, s, driftRequestedID)
	cfg, _ := got["display_config"].(map[string]interface{})
	if cfg == nil || cfg["theme"] != "dunkel" {
		t.Errorf("%s.json: display_config = %v, erwartet theme=dunkel — die Aenderung kam bei der angefragten Ressource nicht an",
			driftRequestedID, got["display_config"])
	}
	// (b)
	assertNoForeignFile(t, s)
}

// PUT /api/locations/{id} — bereits korrekt (setzt loc.ID = id). Gehoert in
// den Waechter, damit die ganze Schreibflaeche gehalten wird und der Fehler
// nicht eine Tuer weiter wandert.
func TestUpdateLocationWritesToRequestedFileOnIDDrift(t *testing.T) {
	s := newTestStore(t)
	seedDriftedLocation(t, s)

	r := chi.NewRouter()
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))

	req := httptest.NewRequest("PUT", "/api/locations/"+driftRequestedID,
		strings.NewReader("{\"name\":\"Neuer Name\",\"lat\":47.5,\"lon\":11.5}"))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// (a)
	got := readLocationFile(t, s, driftRequestedID)
	if got["name"] != "Neuer Name" {
		t.Errorf("%s.json: name = %v, erwartet Neuer Name — die Aenderung kam bei der angefragten Ressource nicht an",
			driftRequestedID, got["name"])
	}
	// (b)
	assertNoForeignFile(t, s)
}
