package router

// Issue #2961 (Spec AC-10, Fix-Runde Gegenpruefung F2/F3/M69): Dateigrenze
// fuer Orte und Ortsvergleiche, Wachstumsgrenzen beim ANLEGEN und
// Bestandsschutz fuer Schluessel ausserhalb des Musters. Die Dateigrenze steht
// hier bewusst als Literal (2 MiB) — eine Verfaelschung der Konstante muss
// rot werden.

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

const grenzeDateiBytes = 2 << 20

// fastVoll / Zuwachs: der Rumpf bleibt unter der globalen Rumpfgrenze (1 MB),
// erst die gespeicherte Datei wuerde die 2-MiB-Grenze reissen.
func fastVoll() string { return strings.Repeat("b", grenzeDateiBytes-(600<<10)) }

func zuwachs(kib int) string {
	return `{"zuwachs":"` + strings.Repeat("x", kib<<10) + `"}`
}

func leseDatei(t *testing.T, p string) string {
	t.Helper()
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func gueltigerPresetRumpf(extra string) string {
	return `{"name":"V","location_ids":["ort-1"],"schedule":"manual","profil":"allgemein","forecast_hours":48,"hour_from":6,"hour_to":20` + extra + `}`
}

// F2: SaveLocation setzt die Dateigrenze durch.
func TestDateigrenze_OrtLiteral2MiB(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "quirin-groesse", "de")
	s := e.s.WithUser("quirin-groesse")
	if err := s.SaveLocation(model.Location{ID: "ort-1", Name: "Ort", Lat: 47, Lon: 11,
		DisplayConfig: map[string]interface{}{"bestand": fastVoll()}}); err != nil {
		t.Fatal(err)
	}
	pfad := filepath.Join(s.LocationsDir(), "ort-1.json")
	vorher := leseDatei(t, pfad)
	erwarteCode(t, "Ort > 2 MiB", e.rufe(t, http.MethodPut, "/api/locations/ort-1/weather-config", []byte(zuwachs(900)), c),
		http.StatusRequestEntityTooLarge, "entity_too_large")
	if leseDatei(t, pfad) != vorher {
		t.Fatal("zu grosse Aenderung hat die Ortsdatei veraendert")
	}
	// Knapp darunter passt (Gegenprobe gegen eine zu kleine Grenze).
	if w := e.rufe(t, http.MethodPut, "/api/locations/ort-1/weather-config", []byte(zuwachs(500)), c); w.Code != http.StatusOK {
		t.Fatalf("knapp unter 2 MiB: %d %s", w.Code, w.Body.String())
	}
}

// F2: SaveComparePreset setzt die Dateigrenze durch.
func TestDateigrenze_OrtsvergleichLiteral2MiB(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "rita-groesse", "de")
	s := e.s.WithUser("rita-groesse")
	if err := s.SaveLocation(model.Location{ID: "ort-1", Name: "Ort", Lat: 47, Lon: 11}); err != nil {
		t.Fatal(err)
	}
	w := e.rufe(t, http.MethodPost, "/api/compare/presets", []byte(gueltigerPresetRumpf("")), c)
	if w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Anlage: %d %s", w.Code, w.Body.String())
	}
	var p struct{ ID string }
	_ = json.Unmarshal(w.Body.Bytes(), &p)
	preset, err := s.LoadComparePreset(p.ID)
	if err != nil || preset == nil {
		t.Fatalf("LoadComparePreset: %v", err)
	}
	preset.DisplayConfig = map[string]interface{}{"bestand": fastVoll()}
	if err := s.SaveComparePreset(*preset); err != nil {
		t.Fatal(err)
	}
	pfad := filepath.Join(s.BriefingsDir(), p.ID+".json")
	vorher := leseDatei(t, pfad)
	erwarteCode(t, "Ortsvergleich > 2 MiB", e.rufe(t, http.MethodPut, "/api/compare/presets/"+p.ID,
		[]byte(`{"display_config":`+zuwachs(900)+`}`), c), http.StatusRequestEntityTooLarge, "entity_too_large")
	if leseDatei(t, pfad) != vorher {
		t.Fatal("zu grosse Aenderung hat die Ortsvergleichsdatei veraendert")
	}
	if w := e.rufe(t, http.MethodPut, "/api/compare/presets/"+p.ID, []byte(`{"display_config":`+zuwachs(500)+`}`), c); w.Code != http.StatusOK {
		t.Fatalf("knapp unter 2 MiB: %d %s", w.Code, w.Body.String())
	}
}

// F3: Wachstumsgrenzen greifen auch beim Anlegen.
func TestWachstumsgrenzen_BeimAnlegen(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "sven-anlegen", "de")
	if err := e.s.WithUser("sven-anlegen").SaveLocation(model.Location{ID: "ort-1", Name: "Ort", Lat: 47, Lon: 11}); err != nil {
		t.Fatal(err)
	}
	for _, fall := range []struct{ name, display string }{
		{"201 Schluessel", vieleSchluessel(201, "k")},
		{"unzulaessiger Schluessel", `{"Boeser Schluessel!":1}`},
	} {
		erwarteCode(t, "POST Ort, "+fall.name, e.rufe(t, http.MethodPost, "/api/locations",
			[]byte(`{"id":"ort-neu","name":"Neu","lat":47,"lon":11,"display_config":`+fall.display+`}`), c),
			http.StatusBadRequest, "limit_exceeded")
		erwarteCode(t, "POST Ortsvergleich, "+fall.name, e.rufe(t, http.MethodPost, "/api/compare/presets",
			[]byte(gueltigerPresetRumpf(`,"display_config":`+fall.display)), c), http.StatusBadRequest, "limit_exceeded")
		erwarteCode(t, "POST /api/briefings vergleich, "+fall.name, e.rufe(t, http.MethodPost, "/api/briefings",
			[]byte(gueltigerPresetRumpf(`,"kind":"vergleich","display_config":`+fall.display)), c), http.StatusBadRequest, "limit_exceeded")
	}
	if l, _ := e.s.WithUser("sven-anlegen").LoadLocation("ort-neu"); l != nil {
		t.Fatal("abgelehnter Ort wurde angelegt")
	}
}

// M69: ein gespeicherter Schluessel ausserhalb des Musters bleibt
// schreibbar, ein neuer solcher Schluessel nicht (Ort und Ortsvergleich).
func TestWachstumsgrenzen_BestandsschluesselBleibtSchreibbar(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "tara-bestand", "de")
	s := e.s.WithUser("tara-bestand")
	if err := s.SaveLocation(model.Location{ID: "ort-1", Name: "Ort", Lat: 47, Lon: 11,
		DisplayConfig: map[string]interface{}{"AltSchluessel": 1}}); err != nil {
		t.Fatal(err)
	}
	if w := e.rufe(t, http.MethodPut, "/api/locations/ort-1/weather-config", []byte(`{"AltSchluessel":2}`), c); w.Code != http.StatusOK {
		t.Fatalf("Bestandsschluessel Ort: %d %s", w.Code, w.Body.String())
	}
	erwarteCode(t, "neuer Schluessel ausserhalb des Musters", e.rufe(t, http.MethodPut, "/api/locations/ort-1/weather-config",
		[]byte(`{"NeuSchluessel":1}`), c), http.StatusBadRequest, "limit_exceeded")
	l, _ := s.LoadLocation("ort-1")
	if l == nil || l.DisplayConfig["AltSchluessel"] != float64(2) {
		t.Fatalf("Bestandsschluessel nicht geschrieben: %+v", l)
	}
	if _, da := l.DisplayConfig["NeuSchluessel"]; da {
		t.Fatal("abgelehnter Schluessel wurde gespeichert")
	}
}
