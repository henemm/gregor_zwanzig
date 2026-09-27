package handler

// TDD -- Issue #2422 S2a: Go-Kern (AC-8/AC-9).
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-8, AC-9).
//
// AC-8: Roundtrip beider PUT-Pfade (PUT /api/trips/{id}/weather-config UND
// PUT /api/trips/{id}) mit den Golden-Bodys (A, C) -- der zurueckgelesene
// Stand von channel_layouts/display_config.metrics ist exakt der gesendete,
// fuer BEIDE Pfade unabhaengig voneinander.
// AC-9: Cross-User-Isolation -- Nutzer B sieht/aendert Nutzer As Trip NICHT,
// Nutzer As Trip bleibt nach dem abgewiesenen Versuch unveraendert.
//
// Kein Go-Produktivcode betroffen (Spec: "Kein Go-Test prueft channel_layouts
// am Trip", S1-Kontext) -- dieser Test ist ein GRUENER Guard, kein RED-Beweis
// (Go-Merge-Verhalten ist unveraendert korrekt fuer volle-Key-PUTs).
//
// Golden per os.ReadFile relativ zur Testdatei (kein Mock, kein Netz).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"
)

func loadGoldenDisplayConfig(t *testing.T, name string) map[string]interface{} {
	t.Helper()
	path := filepath.Join("..", "..", "tests", "fixtures", "einstellung_auslieferung", name+".json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("golden %q nicht lesbar: %v", name, err)
	}
	var golden map[string]interface{}
	if err := json.Unmarshal(raw, &golden); err != nil {
		t.Fatalf("golden %q nicht JSON-parsebar: %v", name, err)
	}
	dc, ok := golden["display_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("golden %q hat kein display_config-Objekt", name)
	}
	return dc
}

func weatherConfigRelevantFields(dc map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	if v, ok := dc["channel_layouts"]; ok {
		out["channel_layouts"] = v
	}
	if v, ok := dc["metrics"]; ok {
		out["metrics"] = v
	}
	return out
}

// jsonRoundtrip normalisiert ein Go-Wertegefuege ueber Marshal+Unmarshal, damit
// z.B. int vs. float64 (JSON kennt nur eine Zahlenart) den Vergleich nicht
// verfaelscht -- beide Seiten (gesendet, zurueckgelesen) durchlaufen denselben
// Normalisierungspfad.
func jsonRoundtrip(t *testing.T, v interface{}) interface{} {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("jsonRoundtrip marshal: %v", err)
	}
	var out interface{}
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("jsonRoundtrip unmarshal: %v", err)
	}
	return out
}

func doPutWeatherConfigPath(t *testing.T, r http.Handler, user, id string, dc map[string]interface{}) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(dc)
	req := httptest.NewRequest("PUT", "/api/trips/"+id+"/weather-config", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, user)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func doPutTripPath(t *testing.T, r http.Handler, user, id string, dc map[string]interface{}) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(map[string]interface{}{"display_config": dc})
	req := httptest.NewRequest("PUT", "/api/trips/"+id, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, user)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func doGetWeatherConfig(t *testing.T, r http.Handler, user, id string) (*httptest.ResponseRecorder, map[string]interface{}) {
	t.Helper()
	req := httptest.NewRequest("GET", "/api/trips/"+id+"/weather-config", nil)
	req = addUserToContext(req, user)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	var got map[string]interface{}
	if w.Code == http.StatusOK {
		_ = json.Unmarshal(w.Body.Bytes(), &got)
	}
	return w, got
}

func TestWeatherConfigEditorRoundtrip_AC8_BothPutPaths(t *testing.T) {
	for _, goldenName := range []string{"golden_a", "golden_c"} {
		t.Run(goldenName, func(t *testing.T) {
			t.Run("weather-config-Pfad", func(t *testing.T) {
				s := newTestStore(t)
				user := "user-ac8-" + goldenName + "-a"
				r := chi.NewRouter()
				r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))
				r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

				us := s.WithUser(user)
				seedTrip(t, us, "trip-"+goldenName, "AC-8 Trip")

				dc := loadGoldenDisplayConfig(t, goldenName)

				wPut := doPutWeatherConfigPath(t, r, user, "trip-"+goldenName, dc)
				if wPut.Code != http.StatusOK {
					t.Fatalf("PUT weather-config: erwartet 200, erhalten %d: %s", wPut.Code, wPut.Body.String())
				}

				wGet, got := doGetWeatherConfig(t, r, user, "trip-"+goldenName)
				if wGet.Code != http.StatusOK {
					t.Fatalf("GET weather-config: erwartet 200, erhalten %d", wGet.Code)
				}

				erwartet := jsonRoundtrip(t, weatherConfigRelevantFields(dc))
				ist := jsonRoundtrip(t, weatherConfigRelevantFields(got))
				if !reflect.DeepEqual(erwartet, ist) {
					t.Fatalf("AC-8 (%s, weather-config-Pfad): zurueckgelesener Stand weicht ab.\nerwartet=%#v\nist=%#v", goldenName, erwartet, ist)
				}
			})

			t.Run("trip-Pfad", func(t *testing.T) {
				s := newTestStore(t)
				user := "user-ac8-" + goldenName + "-b"
				r := chi.NewRouter()
				r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))
				r.Put("/api/trips/{id}", UpdateTripHandler(s))

				us := s.WithUser(user)
				seedTrip(t, us, "trip-"+goldenName, "AC-8 Trip")

				dc := loadGoldenDisplayConfig(t, goldenName)

				wPut := doPutTripPath(t, r, user, "trip-"+goldenName, dc)
				if wPut.Code != http.StatusOK {
					t.Fatalf("PUT trip: erwartet 200, erhalten %d: %s", wPut.Code, wPut.Body.String())
				}

				wGet, got := doGetWeatherConfig(t, r, user, "trip-"+goldenName)
				if wGet.Code != http.StatusOK {
					t.Fatalf("GET weather-config: erwartet 200, erhalten %d", wGet.Code)
				}

				erwartet := jsonRoundtrip(t, weatherConfigRelevantFields(dc))
				ist := jsonRoundtrip(t, weatherConfigRelevantFields(got))
				if !reflect.DeepEqual(erwartet, ist) {
					t.Fatalf("AC-8 (%s, trip-Pfad): zurueckgelesener Stand weicht ab.\nerwartet=%#v\nist=%#v", goldenName, erwartet, ist)
				}
			})
		})
	}
}

func TestWeatherConfigEditorRoundtrip_AC9_CrossUserIsolation(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	nutzerA, nutzerB := "nutzer-a-ac9", "nutzer-b-ac9"
	usA := s.WithUser(nutzerA)
	seedTrip(t, usA, "shared-id-ac9", "Nutzer-A-Trip")
	// AC-9 (Spec-Wortlaut "mit je eigenem Trip"): Nutzer B hat einen EIGENEN,
	// unabhaengigen Trip -- kein Zufallsergebnis, weil B ueberhaupt keinen
	// Trip haette.
	usB := s.WithUser(nutzerB)
	seedTrip(t, usB, "eigener-trip-b-ac9", "Nutzer-B-eigener-Trip")

	dcA := loadGoldenDisplayConfig(t, "golden_a")
	wSeedPut := doPutWeatherConfigPath(t, r, nutzerA, "shared-id-ac9", dcA)
	if wSeedPut.Code != http.StatusOK {
		t.Fatalf("Vorbedingung: Nutzer A PUT muss 200 liefern, erhalten %d: %s", wSeedPut.Code, wSeedPut.Body.String())
	}

	// Nutzer B versucht denselben Trip zu lesen -- muss fehlschlagen (404,
	// eigener Namespace kennt die ID nicht), NICHT Nutzer As Daten liefern.
	wGetB, _ := doGetWeatherConfig(t, r, nutzerB, "shared-id-ac9")
	if wGetB.Code == http.StatusOK {
		t.Fatalf("AC-9: Nutzer B durfte Nutzer As Trip NICHT lesen koennen (Cross-User-Datenleck), erhalten 200: %s", wGetB.Body.String())
	}

	// Nutzer B versucht denselben Trip zu aendern -- muss ebenfalls fehlschlagen.
	dcC := loadGoldenDisplayConfig(t, "golden_c")
	wPutB := doPutWeatherConfigPath(t, r, nutzerB, "shared-id-ac9", dcC)
	if wPutB.Code == http.StatusOK {
		t.Fatalf("AC-9: Nutzer B durfte Nutzer As Trip NICHT aendern koennen, erhalten 200: %s", wPutB.Body.String())
	}

	// Nutzer As Trip muss nach dem abgewiesenen Versuch UNVERAENDERT sein.
	wGetA, gotA := doGetWeatherConfig(t, r, nutzerA, "shared-id-ac9")
	if wGetA.Code != http.StatusOK {
		t.Fatalf("Nutzer A GET nach abgewiesenem B-Zugriff: erwartet 200, erhalten %d", wGetA.Code)
	}
	erwartet := jsonRoundtrip(t, weatherConfigRelevantFields(dcA))
	ist := jsonRoundtrip(t, weatherConfigRelevantFields(gotA))
	if !reflect.DeepEqual(erwartet, ist) {
		t.Fatalf("AC-9: Nutzer As Trip wurde durch den abgewiesenen B-Zugriff veraendert.\nerwartet=%#v\nist=%#v", erwartet, ist)
	}
}
