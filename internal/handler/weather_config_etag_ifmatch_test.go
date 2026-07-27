package handler

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1395 Scheibe S2 — derselbe ETag/If-Match-Vertrag auf
// /api/trips/{id}/weather-config. Der Pfad schreibt dieselbe Datei
// (briefings/<id>.json) wie PUT /api/trips/{id} und synchronisiert dabei
// zusaetzlich alert_rules — ein verlorener Schreibvorgang faellt hier also
// besonders folgenreich aus.

const wcPath = "/api/trips/wc-1395/weather-config"

// AC-8 (analog AC-1): GET liefert den ETag der Briefing-Datei.
func TestGetTripWeatherConfigHandler_ReturnsETag(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "wc-1395", "Weather Config Trip")
	r := etagRouter(s)

	w := doReq(r, http.MethodGet, wcPath, "", "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	et := mustETag(t, w)
	fp, err := s.BriefingFingerprint("wc-1395")
	if err != nil {
		t.Fatalf("BriefingFingerprint: %v", err)
	}
	if strings.Trim(et, `"`) != fp {
		t.Errorf("ETag %q entspricht nicht dem Datei-Fingerabdruck %q", et, fp)
	}
}

// AC-8 (analog AC-3): ohne If-Match wie bisher angenommen, mit neuem ETag.
func TestPutTripWeatherConfigHandler_NoIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "wc-1395", "Weather Config Trip")
	r := etagRouter(s)

	body := `{"metrics":[{"metric_id":"temperature","enabled":true}]}`
	w := doReq(r, http.MethodPut, wcPath, body, "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 ohne If-Match, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)

	loaded, _ := s.LoadTrip("wc-1395")
	if loaded == nil || loaded.DisplayConfig["metrics"] == nil {
		t.Errorf("metrics wurden nicht gespeichert: %+v", loaded)
	}
}

// AC-8 (analog AC-5): veralteter If-Match -> 412 und display_config unveraendert.
func TestPutTripWeatherConfigHandler_StaleIfMatch_Returns412_FileUnchanged(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "wc-1395", "Weather Config Trip")
	r := etagRouter(s)

	// Ausgangsstand setzen, damit es etwas zu verlieren gibt.
	if w := doReq(r, http.MethodPut, wcPath, `{"theme":"dark"}`, "", ""); w.Code != 200 {
		t.Fatalf("Vorbereitung: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	before, err := s.BriefingFingerprint("wc-1395")
	if err != nil {
		t.Fatalf("BriefingFingerprint vorher: %v", err)
	}

	stale := `"0000000000000000000000000000000000000000000000000000000000000000"`
	w := doReq(r, http.MethodPut, wcPath, `{"theme":"light"}`, stale, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 bei veraltetem If-Match, got %d: %s", w.Code, w.Body.String())
	}

	after, err := s.BriefingFingerprint("wc-1395")
	if err != nil {
		t.Fatalf("BriefingFingerprint nachher: %v", err)
	}
	if before != after {
		t.Errorf("Datei wurde trotz 412 veraendert: %q -> %q", before, after)
	}
	loaded, _ := s.LoadTrip("wc-1395")
	if loaded == nil || loaded.DisplayConfig["theme"] != "dark" {
		t.Errorf("display_config wurde trotz 412 veraendert: %+v", loaded.DisplayConfig)
	}
}

// AC-8 (analog AC-6): der zurueckgelieferte ETag traegt den zweiten PUT.
func TestPutTripWeatherConfigHandler_ReturnsNewETag(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "wc-1395", "Weather Config Trip")
	r := etagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, wcPath, "", "", ""))

	first := doReq(r, http.MethodPut, wcPath, `{"theme":"dark"}`, e0, "")
	if first.Code != 200 {
		t.Fatalf("erster PUT: expected 200, got %d: %s", first.Code, first.Body.String())
	}
	e1 := mustETag(t, first)
	if e1 == e0 {
		t.Fatalf("ETag haette sich nach dem Schreibvorgang aendern muessen, blieb %q", e0)
	}

	second := doReq(r, http.MethodPut, wcPath, `{"theme":"light"}`, e1, "")
	if second.Code != 200 {
		t.Fatalf("zweiter PUT mit dem zurueckgelieferten ETag: expected 200, got %d: %s",
			second.Code, second.Body.String())
	}
	var cfg map[string]interface{}
	json.Unmarshal(second.Body.Bytes(), &cfg)
	if cfg["theme"] != "light" {
		t.Errorf("zweiter PUT nicht wirksam, theme = %v", cfg["theme"])
	}
}

// seedTripWithInnerID legt briefings/<datei>.json an, dessen INNERE Kennung
// bewusst vom Dateinamen abweicht — der Zustand, den F002 offenlegt.
func seedTripWithInnerID(t *testing.T, s *store.Store, datei, innereID string) {
	t.Helper()
	dir := s.BriefingsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	raw := `{"id":"` + innereID + `","kind":"route","name":"Drift","stages":[{"id":"S1",` +
		`"name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,` +
		`"lon":11.0,"elevation_m":500}]}]}`
	if err := os.WriteFile(filepath.Join(dir, datei+".json"), []byte(raw), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
}

// F002 (Adversary, HIGH): Weicht die innere Kennung einer Briefing-Datei vom
// Dateinamen ab, schrieb dieser Pfad die Aenderung in die Datei der INNEREN
// Kennung — also in eine fremde Tour — und meldete dem Nutzer trotzdem 200 mit
// einem gueltig aussehenden ETag. Der Stempel gehoerte zur unveraenderten
// Datei und war damit formal richtig: der Client haelt danach einen gueltigen
// Stand und glaubt, gespeichert zu haben, waehrend seine Aenderung nirgends
// angekommen ist. Vor S2 gab es diesen Vertrauensanker nicht — die Scheibe darf
// die Fehlerklasse nicht verschaerfen (AC-8 verlangt, dass der Pfad die
// ANGEFRAGTE Ressource veraendert).
func TestPutTripWeatherConfigHandler_WritesRequestedTripNotInnerID(t *testing.T) {
	s := newTestStore(t)
	seedTripWithInnerID(t, s, "aussen", "innen-anders")
	r := etagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/aussen/weather-config", `{"theme":"dark"}`, "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// (a) Die angefragte Tour traegt die Aenderung wirklich.
	loaded, err := s.LoadTrip("aussen")
	if err != nil {
		t.Fatalf("LoadTrip(aussen): %v", err)
	}
	if loaded == nil {
		t.Fatalf("aussen.json ist verschwunden")
	}
	if loaded.DisplayConfig["theme"] != "dark" {
		t.Errorf("Aenderung ist bei der angefragten Tour nicht angekommen, display_config = %+v",
			loaded.DisplayConfig)
	}

	// (b) Keine fremde Tour angelegt.
	if _, err := os.Stat(filepath.Join(s.BriefingsDir(), "innen-anders.json")); err == nil {
		t.Errorf("Schreibvorgang landete in der fremden Tour briefings/innen-anders.json")
	}

	// (c) Der gelieferte Stempel gehoert zum NEUEN Stand der angefragten Datei.
	fp, err := s.BriefingFingerprint("aussen")
	if err != nil {
		t.Fatalf("BriefingFingerprint(aussen): %v", err)
	}
	if got := strings.Trim(w.Header().Get("ETag"), `"`); got != fp {
		t.Errorf("ETag %q gehoert nicht zum neuen Stand von aussen.json (%q)", got, fp)
	}
}

// AC-9 fuer /weather-config: der ETag von Nutzer A greift nicht bei Nutzer B.
func TestPutTripWeatherConfigHandler_TenantIsolation(t *testing.T) {
	base := t.TempDir()
	sA := store.New(base, "usera-wc")
	sB := store.New(base, "userb-wc")
	seedTrip(t, sA, "wc-shared", "Trip A")
	seedTrip(t, sB, "wc-shared", "Trip B von Nutzer B")

	r := etagRouter(sA)
	path := "/api/trips/wc-shared/weather-config"

	etA := mustETag(t, doReq(r, http.MethodGet, path, "", "", "usera-wc"))
	etB := mustETag(t, doReq(r, http.MethodGet, path, "", "", "userb-wc"))
	if etA == etB {
		t.Fatalf("beide Nutzer haben denselben ETag %q — Testaufbau erzeugt keine Trennung", etA)
	}

	cross := doReq(r, http.MethodPut, path, `{"theme":"dark"}`, etA, "userb-wc")
	if cross.Code != http.StatusPreconditionFailed {
		t.Fatalf("A's ETag gegen B: expected 412, got %d: %s", cross.Code, cross.Body.String())
	}

	own := doReq(r, http.MethodPut, path, `{"theme":"dark"}`, etB, "userb-wc")
	if own.Code != 200 {
		t.Fatalf("B mit eigenem ETag: expected 200, got %d: %s", own.Code, own.Body.String())
	}

	loadedA, _ := sA.LoadTrip("wc-shared")
	if loadedA == nil || loadedA.DisplayConfig["theme"] != nil {
		t.Errorf("Cross-User-Leck: A's display_config veraendert: %+v", loadedA.DisplayConfig)
	}
}
