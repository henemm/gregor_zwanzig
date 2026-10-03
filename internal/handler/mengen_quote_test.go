package handler

// TDD RED — Mengen-Quoten je Tier (S5, Issue #2482, Sammel-Issue #2153, Epic #2138).
//
// Spec: docs/specs/modules/mengen_quoten_je_tier.md — AC-1 bis AC-9, AC-15.
//
// Bewusst OHNE neue Handler-Signatur: die Tests rufen die Create-/State-
// Handler mit ihrer heutigen Signatur auf. Admin/Ausnahme-Liste (AC-10),
// POST /api/briefings (AC-11) und die Profil-Grenzen (AC-13) werden im
// echten Router geprueft (internal/router/mengen_quote_route_test.go) — dort,
// wo die Verdrahtung WIRKT.
//
// RED-Signal: zuerst Uebersetzungsfehler (model.QuotaFor und die Test-Naht
// quotaBeforeSave existieren nicht); darunter Verhalten — heute gibt es keine
// Quote, der Anlage-Versuch ueber der Grenze liefert 201 statt 409
// quota_exceeded (Probe im RED-Artefakt belegt).
//
// Fehlervertrag (Spec "Antwort bei Ueberschreitung"):
//   409 {"error":"quota_exceeded","detail":"<deutsch>","resource":"trips|compare_presets|locations","limit":N,"current":M}

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Fixtures -----------------------------------------------------------------

const quoteKeinNutzer = "<kein-user-json>"

func quoteStore(t *testing.T) *store.Store {
	t.Helper()
	return store.New(t.TempDir(), "default")
}

// quoteTier legt user.json mit dem Tarif an. quoteKeinNutzer legt GAR KEINE
// user.json an (fehlender Tarif, fail-closed free).
func quoteTier(t *testing.T, s *store.Store, uid, tier string) {
	t.Helper()
	if tier == quoteKeinNutzer {
		return
	}
	if err := s.SaveUser(model.User{ID: uid, Tier: tier, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser %s: %v", uid, err)
	}
}

func quoteSeedTrips(t *testing.T, s *store.Store, uid string, aktiv, archiviert int) {
	t.Helper()
	us := s.WithUser(uid)
	for i := 0; i < aktiv+archiviert; i++ {
		trip := model.Trip{
			ID: fmt.Sprintf("seed-trip-%d", i), Name: fmt.Sprintf("Trip %d", i),
			Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
			}},
		}
		if i >= aktiv {
			now := time.Now().UTC()
			trip.ArchivedAt = &now
		}
		if err := us.SaveTrip(&trip); err != nil {
			t.Fatalf("SaveTrip: %v", err)
		}
	}
}

func quotePreset(uid, id string) model.ComparePreset {
	return model.ComparePreset{
		ID: id, UserID: uid, Name: "Vergleich " + id,
		LocationIDs: []string{"loc-a", "loc-b"}, Schedule: "daily", Profil: "SUMMER_TREKKING",
		HourFrom: 6, HourTo: 18, ForecastHours: 48, CreatedAt: time.Now().UTC(),
	}
}

func quoteSeedPresets(t *testing.T, s *store.Store, uid string, aktiv, archiviert int) {
	t.Helper()
	us := s.WithUser(uid)
	for i := 0; i < aktiv+archiviert; i++ {
		p := quotePreset(uid, fmt.Sprintf("seed-cp-%d", i))
		if i >= aktiv {
			now := time.Now().UTC()
			p.ArchivedAt = &now
		}
		if err := us.SaveComparePreset(p); err != nil {
			t.Fatalf("SaveComparePreset: %v", err)
		}
	}
}

func quoteSeedLocations(t *testing.T, s *store.Store, uid string, n int) {
	t.Helper()
	us := s.WithUser(uid)
	for i := 0; i < n; i++ {
		loc := model.Location{ID: fmt.Sprintf("seed-ort-%d", i), Name: fmt.Sprintf("Ort %d", i), Lat: 47.0 + float64(i)/100, Lon: 11.0}
		if err := us.SaveLocation(loc); err != nil {
			t.Fatalf("SaveLocation: %v", err)
		}
	}
}

func quoteActiveTrips(t *testing.T, s *store.Store, uid string) (aktiv, gesamt int) {
	t.Helper()
	trips, err := s.WithUser(uid).LoadTrips()
	if err != nil {
		t.Fatalf("LoadTrips: %v", err)
	}
	for _, tr := range trips {
		if tr.ArchivedAt == nil {
			aktiv++
		}
	}
	return aktiv, len(trips)
}

func quoteActivePresets(t *testing.T, s *store.Store, uid string) (aktiv, gesamt int) {
	t.Helper()
	ps, err := s.WithUser(uid).LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	for _, p := range ps {
		if p.ArchivedAt == nil {
			aktiv++
		}
	}
	return aktiv, len(ps)
}

func quoteLocationCount(t *testing.T, s *store.Store, uid string) int {
	t.Helper()
	locs, err := s.WithUser(uid).LoadLocations()
	if err != nil {
		t.Fatalf("LoadLocations: %v", err)
	}
	return len(locs)
}

// quoteRouter verdrahtet alle betroffenen Handler mit ihrer HEUTIGEN Signatur.
func quoteRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))
	r.Delete("/api/compare/presets/{id}", DeleteComparePresetHandler(s))
	r.Post("/api/locations", CreateLocationHandler(s))
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))
	r.Delete("/api/locations/{id}", DeleteLocationHandler(s))
	return r
}

func quoteCall(t *testing.T, r http.Handler, method, path, body, uid string) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if body == "" {
		req = httptest.NewRequest(method, path, nil)
	} else {
		req = httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	}
	req = addUserToContext(req, uid)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func quoteTripBody(id string) string {
	return `{"id":"` + id + `","name":"Trip ` + id + `","stages":[{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
}

func quotePresetBody(name string) string {
	return `{"name":"` + name + `","location_ids":["loc-1","loc-2"],"schedule":"daily","profil":"SUMMER_TREKKING","hour_from":6,"hour_to":18}`
}

func quoteLocationBody(name string) string {
	return `{"name":"` + name + `","lat":46.5,"lon":10.5}`
}

type quoteFehler struct {
	Error    string `json:"error"`
	Detail   string `json:"detail"`
	Resource string `json:"resource"`
	Limit    int    `json:"limit"`
	Current  int    `json:"current"`
}

// quoteMuss409 prueft den vollstaendigen Fehlervertrag.
func quoteMuss409(t *testing.T, w *httptest.ResponseRecorder, resource string, limit, current int) quoteFehler {
	t.Helper()
	if w.Code != http.StatusConflict {
		t.Fatalf("erwartet 409 quota_exceeded (%s), bekommen %d: %s", resource, w.Code, w.Body.String())
	}
	var f quoteFehler
	if err := json.Unmarshal(w.Body.Bytes(), &f); err != nil {
		t.Fatalf("409-Body ist kein JSON: %v — %s", err, w.Body.String())
	}
	if f.Error != "quota_exceeded" {
		t.Errorf("error: erwartet quota_exceeded, bekommen %q", f.Error)
	}
	if f.Resource != resource {
		t.Errorf("resource: erwartet %q, bekommen %q", resource, f.Resource)
	}
	if f.Limit != limit || f.Current != current {
		t.Errorf("limit/current: erwartet %d/%d, bekommen %d/%d", limit, current, f.Limit, f.Current)
	}
	if strings.TrimSpace(f.Detail) == "" {
		t.Errorf("detail fehlt — die Anlege-Oberflaechen zeigen detail ?? error an")
	}
	return f
}

func quoteMussAngelegt(t *testing.T, w *httptest.ResponseRecorder, was string) {
	t.Helper()
	if w.Code != http.StatusCreated {
		t.Fatalf("%s: erwartet 201, bekommen %d: %s", was, w.Code, w.Body.String())
	}
}

// --- AC-1 / AC-15: Trip-Grenze Free ------------------------------------------

func TestMengenQuote_AC1_FreeDritterTripOkVierterAbgelehnt(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedTrips(t, s, "alice", 2, 0)
	r := quoteRouter(s)

	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-drei"), "alice"), "3. Trip")

	w := quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-vier"), "alice")
	f := quoteMuss409(t, w, "trips", 3, 3)

	if !strings.Contains(f.Detail, "3 von 3 Trips") {
		t.Errorf("detail muss \"3 von 3 Trips\" nennen, bekommen %q", f.Detail)
	}
	// AC-15: nur "Trip"/"Trips", kein anderer Begriff fuer diese Objekte.
	if strings.Contains(strings.ToLower(f.Detail), "tour") {
		t.Errorf("detail darf keinen anderen Begriff als Trip verwenden: %q", f.Detail)
	}
	if aktiv, gesamt := quoteActiveTrips(t, s, "alice"); aktiv != 3 || gesamt != 3 {
		t.Errorf("Trip-Bestand muss bei 3 bleiben, bekommen aktiv=%d gesamt=%d", aktiv, gesamt)
	}
}

// --- AC-2 / AC-15: Ortsvergleiche und Orte -----------------------------------

func TestMengenQuote_AC2_FreeOrtsvergleichUeberGrenzeAbgelehnt(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedPresets(t, s, "alice", 2, 0)
	r := quoteRouter(s)

	w := quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody("Dritter"), "alice")
	f := quoteMuss409(t, w, "compare_presets", 2, 2)
	if !strings.Contains(f.Detail, "Ortsvergleich") {
		t.Errorf("detail muss von Ortsvergleichen sprechen, bekommen %q", f.Detail)
	}
	if _, gesamt := quoteActivePresets(t, s, "alice"); gesamt != 2 {
		t.Errorf("es darf nichts gespeichert werden, Bestand=%d", gesamt)
	}
}

func TestMengenQuote_AC2_FreeOrtUeberGrenzeAbgelehnt(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedLocations(t, s, "alice", 10)
	r := quoteRouter(s)

	w := quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Elfter Ort"), "alice")
	f := quoteMuss409(t, w, "locations", 10, 10)
	if !strings.Contains(f.Detail, "Orte") {
		t.Errorf("detail muss von Orten sprechen, bekommen %q", f.Detail)
	}
	if n := quoteLocationCount(t, s, "alice"); n != 10 {
		t.Errorf("es darf nichts gespeichert werden, Bestand=%d", n)
	}
}

// Spec: Die bestehende Orts-Dublette (409 conflict) hat Vorrang vor der Quote.
func TestMengenQuote_AC2_OrtDubletteAnDerGrenzeBleibtConflict(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedLocations(t, s, "alice", 9)
	r := quoteRouter(s)

	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Zehnter Ort"), "alice"), "10. Ort")

	w := quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Zehnter Ort"), "alice")
	if w.Code != http.StatusConflict {
		t.Fatalf("Dublette: erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	var f quoteFehler
	json.Unmarshal(w.Body.Bytes(), &f)
	if f.Error != "conflict" {
		t.Errorf("Dublette muss conflict bleiben (Vorrang vor der Quote), bekommen %q", f.Error)
	}
}

// Spec "Reihenfolge": Validierung (400) hat Vorrang vor der Quote — auch an
// der Grenze bekommt ein ungueltiger Rumpf 400 validation_error, nicht 409.
func TestMengenQuote_ValidierungVorQuote(t *testing.T) {
	faelle := []struct {
		name, path, body string
		seed             func(t *testing.T, s *store.Store)
	}{
		{"Trip_ohne_Name", "/api/trips",
			`{"id":"trip-ungueltig","name":"","stages":[]}`,
			func(t *testing.T, s *store.Store) { quoteSeedTrips(t, s, "alice", 3, 0) }},
		{"Ortsvergleich_hour_from_25", "/api/compare/presets",
			`{"name":"Ungueltig","location_ids":["loc-1","loc-2"],"schedule":"daily","profil":"SUMMER_TREKKING","hour_from":25,"hour_to":18}`,
			func(t *testing.T, s *store.Store) { quoteSeedPresets(t, s, "alice", 2, 0) }},
		{"Ort_ohne_Koordinaten", "/api/locations",
			`{"name":"Ohne Koordinaten","lat":0,"lon":0}`,
			func(t *testing.T, s *store.Store) { quoteSeedLocations(t, s, "alice", 10) }},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := quoteStore(t)
			quoteTier(t, s, "alice", "free")
			f.seed(t, s)
			r := quoteRouter(s)

			w := quoteCall(t, r, "POST", f.path, f.body, "alice")
			if w.Code != http.StatusBadRequest {
				t.Fatalf("ungueltiger Rumpf an der Grenze: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
			}
			var fe quoteFehler
			json.Unmarshal(w.Body.Bytes(), &fe)
			if fe.Error != "validation_error" {
				t.Errorf("error: erwartet validation_error, bekommen %q", fe.Error)
			}
		})
	}
}

// AC-8 / Spec "Der Lock ist je Nutzer": waehrend alice im Quoten-Abschnitt
// steht (quotaBeforeSave blockiert), kommt bob mit seiner Anlage durch.
func TestMengenQuote_LockJeNutzerBlockiertAndereNicht(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteTier(t, s, "bob", "free")
	r := quoteRouter(s)

	drin := make(chan struct{})
	frei := make(chan struct{})
	var once sync.Once
	quotaBeforeSave = func() {
		erster := false
		once.Do(func() { erster = true })
		if erster { // nur alice' Anfrage haelt den Abschnitt fest
			close(drin)
			<-frei
		}
	}
	t.Cleanup(func() { quotaBeforeSave = nil })

	aliceFertig := make(chan int)
	go func() {
		aliceFertig <- quoteCall(t, r, "POST", "/api/trips", quoteTripBody("alice-trip"), "alice").Code
	}()
	<-drin // alice haelt jetzt ihren Quoten-Lock

	bobFertig := make(chan int)
	go func() {
		bobFertig <- quoteCall(t, r, "POST", "/api/trips", quoteTripBody("bob-trip"), "bob").Code
	}()
	select {
	case code := <-bobFertig:
		if code != http.StatusCreated {
			t.Errorf("bob: erwartet 201, bekommen %d", code)
		}
	case <-time.After(2 * time.Second):
		close(frei)
		<-aliceFertig
		<-bobFertig
		t.Fatalf("bob blockiert, solange alice den Quoten-Lock haelt — Lock ist nicht je Nutzer")
	}
	close(frei)
	if code := <-aliceFertig; code != http.StatusCreated {
		t.Errorf("alice: erwartet 201, bekommen %d", code)
	}
}

// --- AC-3: exakte Grenze je Tarif, fail-closed free --------------------------

type quoteRessource struct {
	name     string
	seed     func(t *testing.T, s *store.Store, uid string, n int)
	post     func(t *testing.T, r http.Handler, uid string, i int) *httptest.ResponseRecorder
	resource string
}

func quoteRessourcen() []quoteRessource {
	return []quoteRessource{
		{"Trips", func(t *testing.T, s *store.Store, uid string, n int) { quoteSeedTrips(t, s, uid, n, 0) },
			func(t *testing.T, r http.Handler, uid string, i int) *httptest.ResponseRecorder {
				return quoteCall(t, r, "POST", "/api/trips", quoteTripBody(fmt.Sprintf("neu-trip-%d", i)), uid)
			}, "trips"},
		{"Ortsvergleiche", func(t *testing.T, s *store.Store, uid string, n int) { quoteSeedPresets(t, s, uid, n, 0) },
			func(t *testing.T, r http.Handler, uid string, i int) *httptest.ResponseRecorder {
				return quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody(fmt.Sprintf("Neu %d", i)), uid)
			}, "compare_presets"},
		{"Orte", func(t *testing.T, s *store.Store, uid string, n int) { quoteSeedLocations(t, s, uid, n) },
			func(t *testing.T, r http.Handler, uid string, i int) *httptest.ResponseRecorder {
				return quoteCall(t, r, "POST", "/api/locations", fmt.Sprintf(`{"name":"Neuer Ort %d","lat":46.%d,"lon":10.5}`, i, i+1), uid)
			}, "locations"},
	}
}

func TestMengenQuote_AC3_ExakteGrenzeJeTarif(t *testing.T) {
	grenzen := map[string][3]int{ // Trips, Ortsvergleiche, Orte
		"free":     {3, 2, 10},
		"standard": {15, 10, 50},
		"premium":  {50, 30, 200},
	}
	// Leerer, fehlender und unbekannter Tarif werden wie free behandelt.
	faelle := []struct{ tier, wie string }{
		{"free", "free"}, {"standard", "standard"}, {"premium", "premium"},
		{"", "free"}, {quoteKeinNutzer, "free"}, {"gold", "free"},
	}
	// Die absoluten Werte oben sind der freigegebene PO-Vertrag; die Tabelle
	// in internal/model muss genau sie liefern (eine Quelle der Wahrheit).
	for tier, g := range grenzen {
		if q := model.QuotaFor(tier); q.Trips != g[0] || q.ComparePresets != g[1] || q.Locations != g[2] {
			t.Errorf("model.QuotaFor(%q) = %+v, freigegeben %v", tier, q, g)
		}
	}
	for _, fall := range faelle {
		for ri, res := range quoteRessourcen() {
			limit := grenzen[fall.wie][ri]
			t.Run(fmt.Sprintf("%s/%s", fall.tier, res.name), func(t *testing.T) {
				s := quoteStore(t)
				quoteTier(t, s, "alice", fall.tier)
				res.seed(t, s, "alice", limit-1)
				r := quoteRouter(s)

				quoteMussAngelegt(t, res.post(t, r, "alice", 1), fmt.Sprintf("Anlage Nr. %d (= Grenze)", limit))
				quoteMuss409(t, res.post(t, r, "alice", 2), res.resource, limit, limit)
			})
		}
	}
}

// Fail-closed free gilt NUR fuer "kein Tarif" (user.json fehlt). Ein echter
// Ladefehler (kaputte user.json) darf nicht als free gelten — sonst bekaeme
// z. B. ein Premium-Nutzer eine falsche 409 "4 von 3 Trips". Erwartet: 500
// store_error, nichts wird gespeichert.
func TestMengenQuote_AC3_LadefehlerDesNutzersIstKeinFree(t *testing.T) {
	t.Run("kaputte_user_json_500", func(t *testing.T) {
		s := quoteStore(t)
		quoteSeedTrips(t, s, "alice", 4, 0)
		if err := os.WriteFile(filepath.Join(s.UserDir("alice"), "user.json"), []byte(`{kaputt`), 0o644); err != nil {
			t.Fatalf("user.json schreiben: %v", err)
		}
		r := quoteRouter(s)

		w := quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-neu"), "alice")
		if w.Code != http.StatusInternalServerError {
			t.Fatalf("kaputte user.json: erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
		}
		var f quoteFehler
		json.Unmarshal(w.Body.Bytes(), &f)
		if f.Error != "store_error" {
			t.Errorf("error: erwartet store_error, bekommen %q", f.Error)
		}
		if _, gesamt := quoteActiveTrips(t, s, "alice"); gesamt != 4 {
			t.Errorf("es darf nichts gespeichert werden, Bestand=%d", gesamt)
		}
	})

	t.Run("fehlende_user_json_bleibt_free", func(t *testing.T) {
		s := quoteStore(t)
		quoteSeedTrips(t, s, "alice", 3, 0) // keine user.json
		r := quoteRouter(s)

		quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-neu"), "alice"), "trips", 3, 3)
	})
}

// --- AC-4: Archivieren und Loeschen schaffen Platz ---------------------------

func TestMengenQuote_AC4_ArchivierteTripsZaehlenNicht(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedTrips(t, s, "alice", 2, 5) // 5 archivierte duerfen nicht zaehlen
	r := quoteRouter(s)

	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-a"), "alice"), "3. aktiver Trip neben 5 archivierten")
	quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-b"), "alice"), "trips", 3, 3)

	// Archivieren schafft Platz.
	if w := quoteCall(t, r, "PATCH", "/api/trips/seed-trip-0/state", `{"archived":true}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Archivieren: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-c"), "alice"), "Neuanlage nach Archivieren")

	// Loeschen schafft Platz.
	if w := quoteCall(t, r, "DELETE", "/api/trips/seed-trip-1", "", "alice"); w.Code != http.StatusNoContent {
		t.Fatalf("Loeschen: erwartet 204, bekommen %d: %s", w.Code, w.Body.String())
	}
	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-d"), "alice"), "Neuanlage nach Loeschen")
}

func TestMengenQuote_AC4_ArchivierteOrtsvergleicheZaehlenNicht(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedPresets(t, s, "alice", 2, 3)
	r := quoteRouter(s)

	quoteMuss409(t, quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody("Zu viel"), "alice"), "compare_presets", 2, 2)

	if w := quoteCall(t, r, "PATCH", "/api/compare/presets/seed-cp-0/state", `{"archived":true}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Archivieren: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody("Passt wieder"), "alice"), "Neuanlage nach Archivieren")
}

func TestMengenQuote_AC4_OrteZaehlenAlleLoeschenSchafftPlatz(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedLocations(t, s, "alice", 10)
	r := quoteRouter(s)

	quoteMuss409(t, quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Zu viel"), "alice"), "locations", 10, 10)
	if w := quoteCall(t, r, "DELETE", "/api/locations/seed-ort-0", "", "alice"); w.Code != http.StatusNoContent && w.Code != http.StatusOK {
		t.Fatalf("Ort loeschen: erwartet 204/200, bekommen %d: %s", w.Code, w.Body.String())
	}
	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Passt wieder"), "alice"), "Neuanlage nach Loeschen")
}

// --- AC-5: Bestand ueber der Grenze bleibt voll bearbeitbar ------------------

func TestMengenQuote_AC5_UeberDerGrenzeBearbeitenArchivierenLoeschenFrei(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free") // z. B. nach Herabstufung: weit ueber 3/2/10
	quoteSeedTrips(t, s, "alice", 6, 0)
	quoteSeedPresets(t, s, "alice", 4, 0)
	quoteSeedLocations(t, s, "alice", 14)
	r := quoteRouter(s)

	schritte := []struct {
		method, path, body string
		ok                 []int
	}{
		{"PUT", "/api/trips/seed-trip-0", `{"name":"Umbenannt"}`, []int{200}},
		{"PATCH", "/api/trips/seed-trip-1/state", `{"archived":true}`, []int{200}},
		{"PATCH", "/api/trips/seed-trip-2/state", `{"paused":true}`, []int{200}},
		{"DELETE", "/api/trips/seed-trip-3", "", []int{204}},
		{"PUT", "/api/compare/presets/seed-cp-0", `{"name":"Umbenannt"}`, []int{200}},
		{"PATCH", "/api/compare/presets/seed-cp-1/state", `{"archived":true}`, []int{200}},
		{"DELETE", "/api/compare/presets/seed-cp-2", "", []int{200, 204}},
		{"PATCH", "/api/locations/seed-ort-0", `{"name":"Umbenannt"}`, []int{200}},
		{"DELETE", "/api/locations/seed-ort-1", "", []int{200, 204}},
	}
	for _, sc := range schritte {
		w := quoteCall(t, r, sc.method, sc.path, sc.body, "alice")
		passt := false
		for _, c := range sc.ok {
			if w.Code == c {
				passt = true
			}
		}
		if !passt {
			t.Errorf("%s %s ueber der Grenze: erwartet %v, bekommen %d: %s", sc.method, sc.path, sc.ok, w.Code, w.Body.String())
		}
	}
	// Kein Datensatz geht verloren — nur die explizit geloeschten fehlen.
	if _, gesamt := quoteActiveTrips(t, s, "alice"); gesamt != 5 {
		t.Errorf("Trips: erwartet 5 (6 minus 1 geloescht), bekommen %d", gesamt)
	}
	if _, gesamt := quoteActivePresets(t, s, "alice"); gesamt != 3 {
		t.Errorf("Ortsvergleiche: erwartet 3 (4 minus 1 geloescht), bekommen %d", gesamt)
	}
	if n := quoteLocationCount(t, s, "alice"); n != 13 {
		t.Errorf("Orte: erwartet 13 (14 minus 1 geloescht), bekommen %d", n)
	}
	// Nur die Neuanlage ist blockiert.
	quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-neu"), "alice"), "trips", 3, 4)
}

// --- AC-6 + AC-7: Upsert eigener ID vs. fremde ID ----------------------------

func TestMengenQuote_AC6_UpsertEigenerTripAnDerGrenzeBleibtUpsert(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedTrips(t, s, "alice", 4, 0) // ueber der Grenze
	r := quoteRouter(s)

	body := strings.Replace(quoteTripBody("seed-trip-0"), `"name":"Trip seed-trip-0"`, `"name":"Ueberschrieben"`, 1)
	quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", body, "alice"), "Upsert auf eigene ID")

	tr, err := s.WithUser("alice").LoadTrip("seed-trip-0")
	if err != nil || tr == nil || tr.Name != "Ueberschrieben" {
		t.Fatalf("Upsert muss den bestehenden Trip ueberschreiben, bekommen %+v (err=%v)", tr, err)
	}
	if _, gesamt := quoteActiveTrips(t, s, "alice"); gesamt != 4 {
		t.Errorf("Upsert darf keinen Trip hinzufuegen, Bestand=%d", gesamt)
	}
}

// AC-9 (Tech-Lead-Entscheidung zu AC-6): Ein Upsert, der einen ARCHIVIERTEN
// Trip reaktiviert (Rumpf ohne archived_at), ist fachlich ein Wiederherstellen
// und wird gegen die Grenze geprueft. AC-6 schuetzt nur das Ueberschreiben.
func TestMengenQuote_AC9_UpsertReaktiviertArchiviertenTripWirdGeprueft(t *testing.T) {
	archiviert := func(t *testing.T, s *store.Store) bool {
		t.Helper()
		tr, err := s.WithUser("alice").LoadTrip("seed-trip-3")
		if err != nil || tr == nil {
			t.Fatalf("LoadTrip seed-trip-3: %+v (err=%v)", tr, err)
		}
		return tr.ArchivedAt != nil
	}

	t.Run("an_der_Grenze_ohne_archived_at_abgelehnt", func(t *testing.T) {
		s := quoteStore(t)
		quoteTier(t, s, "alice", "free")
		quoteSeedTrips(t, s, "alice", 3, 1) // seed-trip-3 ist archiviert
		r := quoteRouter(s)

		quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("seed-trip-3"), "alice"), "trips", 3, 3)
		if !archiviert(t, s) {
			t.Errorf("abgelehnter Upsert: Trip muss archiviert bleiben")
		}
		if aktiv, gesamt := quoteActiveTrips(t, s, "alice"); aktiv != 3 || gesamt != 4 {
			t.Errorf("Bestand unveraendert erwartet (3 aktiv / 4 gesamt), bekommen %d/%d", aktiv, gesamt)
		}
	})

	t.Run("an_der_Grenze_mit_archived_at_bleibt_Upsert", func(t *testing.T) {
		s := quoteStore(t)
		quoteTier(t, s, "alice", "free")
		quoteSeedTrips(t, s, "alice", 3, 1)
		r := quoteRouter(s)

		body := strings.Replace(quoteTripBody("seed-trip-3"), `"name":"Trip seed-trip-3"`,
			`"name":"Archiv-Upsert","archived_at":"2026-09-01T10:00:00Z"`, 1)
		quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", body, "alice"), "Upsert, der archiviert bleibt")
		if !archiviert(t, s) {
			t.Errorf("Upsert mit archived_at: Trip muss archiviert bleiben")
		}
	})

	t.Run("mit_Platz_ohne_archived_at_ok", func(t *testing.T) {
		s := quoteStore(t)
		quoteTier(t, s, "alice", "free")
		quoteSeedTrips(t, s, "alice", 2, 2) // seed-trip-2 und seed-trip-3 archiviert
		r := quoteRouter(s)

		quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("seed-trip-3"), "alice"), "Reaktivierung mit Platz")
		if archiviert(t, s) {
			t.Errorf("Reaktivierung mit Platz: Trip muss aktiv sein")
		}
	})
}

// Eine ID, die nur bei bob existiert, ist fuer alice eine NEUANLAGE —
// die Existenzpruefung muss nutzergebunden sein.
func TestMengenQuote_AC6_AC7_FremdeTripIDIstNeuanlage(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteTier(t, s, "bob", "free")
	quoteSeedTrips(t, s, "alice", 3, 0)
	if err := s.WithUser("bob").SaveTrip(&model.Trip{ID: "nur-bei-bob", Name: "Bob",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}}}); err != nil {
		t.Fatalf("SaveTrip bob: %v", err)
	}
	r := quoteRouter(s)

	quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("nur-bei-bob"), "alice"), "trips", 3, 3)
}

// --- AC-7: strikt je Nutzer, beide Richtungen --------------------------------

func TestMengenQuote_AC7_ZaehlungStriktJeNutzer(t *testing.T) {
	for _, richtung := range [][2]string{{"alice", "bob"}, {"bob", "alice"}} {
		voll, frei := richtung[0], richtung[1]
		t.Run(voll+"_voll", func(t *testing.T) {
			s := quoteStore(t)
			quoteTier(t, s, voll, "free")
			quoteTier(t, s, frei, "free")
			quoteSeedTrips(t, s, voll, 3, 0)
			quoteSeedPresets(t, s, voll, 2, 0)
			quoteSeedLocations(t, s, voll, 10)
			r := quoteRouter(s)

			quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-x"), frei), frei+" Trip")
			quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody("Vergleich x"), frei), frei+" Ortsvergleich")
			quoteMussAngelegt(t, quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Ort x"), frei), frei+" Ort")

			quoteMuss409(t, quoteCall(t, r, "POST", "/api/trips", quoteTripBody("trip-y"), voll), "trips", 3, 3)
			quoteMuss409(t, quoteCall(t, r, "POST", "/api/compare/presets", quotePresetBody("Vergleich y"), voll), "compare_presets", 2, 2)
			quoteMuss409(t, quoteCall(t, r, "POST", "/api/locations", quoteLocationBody("Ort y"), voll), "locations", 10, 10)
		})
	}
}

// --- AC-8: Race — Zaehlen und Speichern unter Per-User-Lock ------------------

func TestMengenQuote_AC8_ParalleleNeuanlagenUeberschreitenNie(t *testing.T) {
	const parallel = 20
	for _, res := range quoteRessourcen() {
		t.Run(res.name, func(t *testing.T) {
			s := quoteStore(t)
			quoteTier(t, s, "alice", "free")
			limit := map[string]int{"trips": 3, "compare_presets": 2, "locations": 10}[res.resource]
			res.seed(t, s, "alice", limit-1)
			r := quoteRouter(s)

			// Test-Naht (Muster profileUpdateBeforeFreshReload, auth.go): im
			// Betrieb nil; der Quoten-Helfer ruft sie zwischen Zaehlen und
			// Speichern auf (innerhalb des Per-User-Locks). Die Verzoegerung
			// macht das Rennen deterministisch: ohne Lock zaehlen alle
			// Goroutinen vor dem ersten Speichern — "Lock entfernt" wird
			// verlaesslich rot, nicht nur wahrscheinlich.
			quotaBeforeSave = func() { time.Sleep(10 * time.Millisecond) }
			t.Cleanup(func() { quotaBeforeSave = nil })

			start := make(chan struct{})
			codes := make([]int, parallel)
			var wg sync.WaitGroup
			for i := 0; i < parallel; i++ {
				wg.Add(1)
				go func(i int) {
					defer wg.Done()
					<-start
					codes[i] = res.post(t, r, "alice", 100+i).Code
				}(i)
			}
			close(start)
			wg.Wait()

			ok, abgelehnt := 0, 0
			for _, c := range codes {
				switch c {
				case http.StatusCreated:
					ok++
				case http.StatusConflict:
					abgelehnt++
				}
			}
			if ok != 1 || abgelehnt != parallel-1 {
				t.Errorf("erwartet genau 1x 201 und %dx 409, bekommen %dx 201, %dx 409 (%v)", parallel-1, ok, abgelehnt, codes)
			}
			var bestand int
			switch res.resource {
			case "trips":
				bestand, _ = quoteActiveTrips(t, s, "alice")
			case "compare_presets":
				bestand, _ = quoteActivePresets(t, s, "alice")
			default:
				bestand = quoteLocationCount(t, s, "alice")
			}
			if bestand != limit {
				t.Errorf("Endbestand muss genau die Grenze %d sein, bekommen %d", limit, bestand)
			}
		})
	}
}

// --- AC-9: Wiederherstellen aus dem Archiv wird geprueft ---------------------

func TestMengenQuote_AC9_TripWiederherstellenAnDerGrenze(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedTrips(t, s, "alice", 3, 1) // seed-trip-3 ist archiviert
	r := quoteRouter(s)

	w := quoteCall(t, r, "PATCH", "/api/trips/seed-trip-3/state", `{"archived":false}`, "alice")
	quoteMuss409(t, w, "trips", 3, 3)
	tr, _ := s.WithUser("alice").LoadTrip("seed-trip-3")
	if tr == nil || tr.ArchivedAt == nil {
		t.Fatalf("abgelehntes Wiederherstellen: Trip muss unveraendert im Archiv bleiben, bekommen %+v", tr)
	}

	// Platz schaffen, dann gelingt es.
	if w := quoteCall(t, r, "PATCH", "/api/trips/seed-trip-0/state", `{"archived":true}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Archivieren: erwartet 200, bekommen %d", w.Code)
	}
	if w := quoteCall(t, r, "PATCH", "/api/trips/seed-trip-3/state", `{"archived":false}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Wiederherstellen nach Platzschaffen: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestMengenQuote_AC9_OrtsvergleichWiederherstellenAnDerGrenze(t *testing.T) {
	s := quoteStore(t)
	quoteTier(t, s, "alice", "free")
	quoteSeedPresets(t, s, "alice", 2, 1) // seed-cp-2 ist archiviert
	r := quoteRouter(s)

	quoteMuss409(t, quoteCall(t, r, "PATCH", "/api/compare/presets/seed-cp-2/state", `{"archived":false}`, "alice"), "compare_presets", 2, 2)
	ps, _ := s.WithUser("alice").LoadComparePresets()
	for _, p := range ps {
		if p.ID == "seed-cp-2" && p.ArchivedAt == nil {
			t.Fatalf("abgelehntes Wiederherstellen: Ortsvergleich muss im Archiv bleiben")
		}
	}

	if w := quoteCall(t, r, "DELETE", "/api/compare/presets/seed-cp-0", "", "alice"); w.Code != http.StatusOK && w.Code != http.StatusNoContent {
		t.Fatalf("Loeschen: erwartet 200/204, bekommen %d", w.Code)
	}
	if w := quoteCall(t, r, "PATCH", "/api/compare/presets/seed-cp-2/state", `{"archived":false}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Wiederherstellen nach Loeschen: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}
