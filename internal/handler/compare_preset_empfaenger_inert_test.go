package handler

// Issue #2161 (Spec: docs/specs/modules/multi_user_doc_drift.md, AC-1/AC-2)
//
// preset.empfaenger ist seit #1452 inert: kein Service liest das Feld mehr,
// Empfaenger kommen aus dem Nutzerprofil. Die Go-API darf deshalb keinen
// Eintrag ohne "@" mehr mit 400 abweisen, muss den Wert aber unveraendert
// round-trippen (Merge-Pflicht #102: Bestandsdaten bleiben erhalten).
//
// Echt gegen Handler + Store mit t.TempDir()-Datenverzeichnis (newTestStore),
// kein Mock. Mandantentrennung mit zwei Nutzern (user_id aus dem Auth-Kontext).
//
// Ausfuehrung:
//   go test ./internal/handler -run TestComparePresetEmpfaengerInert -v

import (
	"encoding/json"
	"net/http"
	"reflect"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/store"
)

func empfaengerInertRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/compare/presets", ListComparePresetsHandler(s))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	return r
}

// presetBodyWithEmpfaenger liefert einen ansonsten gueltigen Preset-Rumpf.
// empfaenger == nil laesst das Feld komplett weg.
func presetBodyWithEmpfaenger(t *testing.T, name string, empfaenger []string) string {
	t.Helper()
	body := validPresetBody()
	body["name"] = name
	if empfaenger == nil {
		delete(body, "empfaenger")
	} else {
		body["empfaenger"] = empfaenger
	}
	b, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("json.Marshal: %v", err)
	}
	return string(b)
}

type empfaengerView struct {
	ID         string   `json:"id"`
	Name       string   `json:"name"`
	Empfaenger []string `json:"empfaenger"`
}

func decodeEmpfaengerView(t *testing.T, raw []byte) empfaengerView {
	t.Helper()
	var v empfaengerView
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("Antwort nicht dekodierbar: %v: %s", err, raw)
	}
	return v
}

func is2xx(code int) bool { return code >= 200 && code < 300 }

// Test 1 (AC-1): POST mit empfaenger ohne "@" wird gespeichert, nicht abgewiesen.
func TestComparePresetEmpfaengerInert_PostOhneAtWirdGespeichert(t *testing.T) {
	s := newTestStore(t)
	r := empfaengerInertRouter(s)

	w := doReq(r, http.MethodPost, "/api/compare/presets",
		presetBodyWithEmpfaenger(t, "A Vergleich", []string{"kein-at"}), "", "usera")
	if !is2xx(w.Code) {
		t.Fatalf("POST mit empfaenger [\"kein-at\"]: erwartet 2xx (Feld inert seit #1452), bekam %d: %s",
			w.Code, w.Body.String())
	}
	created := decodeEmpfaengerView(t, w.Body.Bytes())
	if !reflect.DeepEqual(created.Empfaenger, []string{"kein-at"}) {
		t.Fatalf("POST-Antwort: empfaenger erwartet [\"kein-at\"], bekam %#v", created.Empfaenger)
	}

	wGet := doReq(r, http.MethodGet, "/api/compare/presets/"+created.ID, "", "", "usera")
	if wGet.Code != http.StatusOK {
		t.Fatalf("GET: erwartet 200, bekam %d: %s", wGet.Code, wGet.Body.String())
	}
	got := decodeEmpfaengerView(t, wGet.Body.Bytes())
	if !reflect.DeepEqual(got.Empfaenger, []string{"kein-at"}) {
		t.Fatalf("GET nach POST: empfaenger nicht round-getrippt, bekam %#v", got.Empfaenger)
	}
}

// Test 2 (AC-1): PUT mit gemischten empfaenger-Werten wird gespeichert und
// beim GET unveraendert zurueckgeliefert.
func TestComparePresetEmpfaengerInert_PutRoundTrip(t *testing.T) {
	s := newTestStore(t)
	r := empfaengerInertRouter(s)

	wPost := doReq(r, http.MethodPost, "/api/compare/presets",
		presetBodyWithEmpfaenger(t, "A Vergleich", []string{"a@b.de"}), "", "usera")
	if !is2xx(wPost.Code) {
		t.Fatalf("Seed-POST: erwartet 2xx, bekam %d: %s", wPost.Code, wPost.Body.String())
	}
	id := decodeEmpfaengerView(t, wPost.Body.Bytes()).ID

	want := []string{"kein-at", "a@b.de"}
	wPut := doReq(r, http.MethodPut, "/api/compare/presets/"+id,
		presetBodyWithEmpfaenger(t, "A Vergleich", want), "", "usera")
	if !is2xx(wPut.Code) {
		t.Fatalf("PUT mit empfaenger %v: erwartet 2xx, bekam %d: %s", want, wPut.Code, wPut.Body.String())
	}

	wGet := doReq(r, http.MethodGet, "/api/compare/presets/"+id, "", "", "usera")
	if wGet.Code != http.StatusOK {
		t.Fatalf("GET: erwartet 200, bekam %d: %s", wGet.Code, wGet.Body.String())
	}
	got := decodeEmpfaengerView(t, wGet.Body.Bytes())
	if !reflect.DeepEqual(got.Empfaenger, want) {
		t.Fatalf("GET nach PUT: empfaenger erwartet %#v, bekam %#v", want, got.Empfaenger)
	}
}

// Test 3 (AC-2): Mandantentrennung — B sieht weder As Preset noch As
// empfaenger-Wert; As Wert bleibt unveraendert.
func TestComparePresetEmpfaengerInert_ZweiNutzerGetrennt(t *testing.T) {
	s := newTestStore(t)
	r := empfaengerInertRouter(s)

	wA := doReq(r, http.MethodPost, "/api/compare/presets",
		presetBodyWithEmpfaenger(t, "A Vergleich", []string{"kein-at"}), "", "usera")
	if !is2xx(wA.Code) {
		t.Fatalf("POST A mit empfaenger [\"kein-at\"]: erwartet 2xx, bekam %d: %s", wA.Code, wA.Body.String())
	}
	idA := decodeEmpfaengerView(t, wA.Body.Bytes()).ID

	wB := doReq(r, http.MethodPost, "/api/compare/presets",
		presetBodyWithEmpfaenger(t, "B Vergleich", []string{"b@example.com"}), "", "userb")
	if !is2xx(wB.Code) {
		t.Fatalf("POST B: erwartet 2xx, bekam %d: %s", wB.Code, wB.Body.String())
	}

	// B listet: nur das eigene Preset, kein "kein-at".
	wList := doReq(r, http.MethodGet, "/api/compare/presets", "", "", "userb")
	if wList.Code != http.StatusOK {
		t.Fatalf("GET-Liste B: erwartet 200, bekam %d: %s", wList.Code, wList.Body.String())
	}
	var listB []empfaengerView
	if err := json.Unmarshal(wList.Body.Bytes(), &listB); err != nil {
		t.Fatalf("Liste B nicht dekodierbar: %v: %s", err, wList.Body.String())
	}
	if len(listB) != 1 || listB[0].Name != "B Vergleich" {
		t.Fatalf("Liste B: erwartet genau das eigene Preset, bekam %#v", listB)
	}
	if strings.Contains(wList.Body.String(), "kein-at") || strings.Contains(wList.Body.String(), idA) {
		t.Fatalf("Liste B enthaelt Daten von A: %s", wList.Body.String())
	}

	// B liest As ID direkt: kein Zugriff auf As Wert.
	wBGet := doReq(r, http.MethodGet, "/api/compare/presets/"+idA, "", "", "userb")
	if wBGet.Code == http.StatusOK || strings.Contains(wBGet.Body.String(), "kein-at") {
		t.Fatalf("B liest As Preset (HTTP %d): %s", wBGet.Code, wBGet.Body.String())
	}

	// As Wert bleibt unveraendert.
	wAGet := doReq(r, http.MethodGet, "/api/compare/presets/"+idA, "", "", "usera")
	if wAGet.Code != http.StatusOK {
		t.Fatalf("GET A: erwartet 200, bekam %d: %s", wAGet.Code, wAGet.Body.String())
	}
	if got := decodeEmpfaengerView(t, wAGet.Body.Bytes()).Empfaenger; !reflect.DeepEqual(got, []string{"kein-at"}) {
		t.Fatalf("As empfaenger veraendert: %#v", got)
	}
}

// Test 4 (Regress-Waechter): ohne empfaenger bleibt die nil-zu-[]-Normalisierung.
// Heute gruen by design; schuetzt davor, beim Streichen der Validierung die
// Normalisierung mit zu entfernen.
func TestComparePresetEmpfaengerInert_OhneFeldLiefertLeereListe(t *testing.T) {
	s := newTestStore(t)
	r := empfaengerInertRouter(s)

	w := doReq(r, http.MethodPost, "/api/compare/presets",
		presetBodyWithEmpfaenger(t, "Ohne Empfaenger", nil), "", "usera")
	if !is2xx(w.Code) {
		t.Fatalf("POST ohne empfaenger: erwartet 2xx, bekam %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"empfaenger":[]`) {
		t.Fatalf("POST-Antwort: empfaenger erwartet [] (nicht null), bekam %s", w.Body.String())
	}
	id := decodeEmpfaengerView(t, w.Body.Bytes()).ID
	wGet := doReq(r, http.MethodGet, "/api/compare/presets/"+id, "", "", "usera")
	if !strings.Contains(wGet.Body.String(), `"empfaenger":[]`) {
		t.Fatalf("GET: empfaenger erwartet [] (nicht null), bekam %s", wGet.Body.String())
	}
}
