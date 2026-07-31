package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1395 Scheibe S6 — der zweite Schreibweg auf dieselbe Datei.
// Spec: docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md
//
// PUT /api/briefings/{id}?kind=vergleich schreibt exakt dieselbe Datei wie
// PUT /api/compare/presets/{id}. Waere nur einer der beiden Wege abgesichert,
// bliebe der andere eine Umgehung — AC-9 prueft beide Richtungen.

func briefingVergleichEtagRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/briefings/{id}", GetBriefingHandler(s))
	r.Put("/api/briefings/{id}", UpdateBriefingHandler(s))
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Get("/api/trips/{id}", TripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	return r
}

// doReqWithin schickt eine Anfrage ab und bricht den Test ab, wenn sie nicht
// binnen der Frist antwortet. Genau dafuer da, einen Selbst-Blockierer als
// Testfehler sichtbar zu machen statt als haengenden Testlauf.
func doReqWithin(t *testing.T, d time.Duration, r http.Handler,
	method, path, body, ifMatch, user string) *httptest.ResponseRecorder {
	t.Helper()
	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		done <- doReq(r, method, path, body, ifMatch, user)
	}()
	select {
	case w := <-done:
		return w
	case <-time.After(d):
		t.Fatalf("%s %s hat binnen %s nicht geantwortet — Selbst-Blockierer (Sperre nicht wiedereintrittsfaehig)",
			method, path, d)
		return nil
	}
}

// AC-10: Beide Lesewege liefern denselben Stempel — es ist dieselbe Datei.
func TestGetBriefingHandler_Vergleich_ReturnsETag_MatchesComparePresetETag(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-brief-10", "Vergleich", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	viaBriefings := mustETag(t, doReq(r, http.MethodGet, "/api/briefings/cp-brief-10?kind=vergleich", "", "", ""))
	viaPreset := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-brief-10", "", "", ""))
	if viaBriefings != viaPreset {
		t.Errorf("beide Wege lesen dieselbe Datei, liefern aber verschiedene Stempel: %q vs %q",
			viaBriefings, viaPreset)
	}
}

// AC-8: Ohne If-Match wird der Umgehungsweg wie bisher angenommen und liefert
// den neuen Stempel mit.
func TestUpdateBriefingHandler_Vergleich_NoIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-brief-8a", "Alt", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/briefings/cp-brief-8a?kind=vergleich", `{"name":"Neu"}`, "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 ohne If-Match, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)
	if got := loadPresetOrFail(t, s, "cp-brief-8a").Name; got != "Neu" {
		t.Errorf("Aenderung nicht gespeichert, name = %q", got)
	}
}

// AC-8: Veralteter If-Match -> 412, Datei unveraendert.
func TestUpdateBriefingHandler_Vergleich_StaleIfMatch_Returns412_FileUnchanged(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-brief-8b", "Original", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	before, err := s.BriefingFingerprint("cp-brief-8b")
	if err != nil {
		t.Fatalf("BriefingFingerprint vorher: %v", err)
	}
	stale := `"0000000000000000000000000000000000000000000000000000000000000000"`

	w := doReq(r, http.MethodPut, "/api/briefings/cp-brief-8b?kind=vergleich",
		`{"name":"Ueberschrieben"}`, stale, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 bei veraltetem If-Match, got %d: %s", w.Code, w.Body.String())
	}
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("412-Antwort darf keinen ETag tragen, got %q", et)
	}

	after, err := s.BriefingFingerprint("cp-brief-8b")
	if err != nil {
		t.Fatalf("BriefingFingerprint nachher: %v", err)
	}
	if before != after {
		t.Errorf("Datei wurde trotz 412 veraendert: %q -> %q", before, after)
	}
	if got := loadPresetOrFail(t, s, "cp-brief-8b").Name; got != "Original" {
		t.Errorf("Inhalt veraendert, erwartet name=Original, got %q", got)
	}
}

// AC-8: Der zurueckgelieferte Stempel ist sofort wieder verwendbar.
func TestUpdateBriefingHandler_Vergleich_ReturnsNewETag(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-brief-8c", "Start", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/briefings/cp-brief-8c?kind=vergleich", "", "", ""))

	first := doReq(r, http.MethodPut, "/api/briefings/cp-brief-8c?kind=vergleich", `{"name":"Erster"}`, e0, "")
	if first.Code != 200 {
		t.Fatalf("erster PUT: expected 200, got %d: %s", first.Code, first.Body.String())
	}
	e1 := mustETag(t, first)
	if e1 == e0 {
		t.Fatalf("der Schreibvorgang haette den Stand aendern muessen, ETag blieb %q", e0)
	}

	second := doReq(r, http.MethodPut, "/api/briefings/cp-brief-8c?kind=vergleich", `{"name":"Zweiter"}`, e1, "")
	if second.Code != 200 {
		t.Fatalf("zweiter PUT mit dem zurueckgelieferten ETag: expected 200, got %d: %s",
			second.Code, second.Body.String())
	}
}

// AC-9 (Kern): geschrieben ueber den Preset-Endpunkt, veralteter Versuch ueber
// den Briefings-Endpunkt — muss ebenfalls scheitern.
func TestCrossPath_WriteViaComparePresetsThenStaleWriteViaBriefingsVergleich_Returns412(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-cross-1", "Start", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-cross-1", "", "", ""))

	a := doReq(r, http.MethodPut, "/api/compare/presets/cp-cross-1", comparePresetPutBody("Client A"), e0, "")
	if a.Code != 200 {
		t.Fatalf("Client A ueber /api/compare/presets: expected 200, got %d: %s", a.Code, a.Body.String())
	}

	b := doReq(r, http.MethodPut, "/api/briefings/cp-cross-1?kind=vergleich", `{"name":"Client B"}`, e0, "")
	if b.Code != http.StatusPreconditionFailed {
		t.Fatalf("Client B ueber /api/briefings?kind=vergleich mit veraltetem Stand: expected 412, got %d: %s",
			b.Code, b.Body.String())
	}
	if got := loadPresetOrFail(t, s, "cp-cross-1").Name; got != "Client A" {
		t.Errorf("der Umgehungsweg hat Client A's Aenderung ueberschrieben, name = %q", got)
	}
}

// AC-9 (Kern): dieselbe Zusage in der Gegenrichtung.
func TestCrossPath_WriteViaBriefingsVergleichThenStaleWriteViaComparePresets_Returns412(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-cross-2", "Start", []string{"loc-1"})
	r := briefingVergleichEtagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/briefings/cp-cross-2?kind=vergleich", "", "", ""))

	a := doReq(r, http.MethodPut, "/api/briefings/cp-cross-2?kind=vergleich", `{"name":"Client A"}`, e0, "")
	if a.Code != 200 {
		t.Fatalf("Client A ueber /api/briefings?kind=vergleich: expected 200, got %d: %s", a.Code, a.Body.String())
	}

	b := doReq(r, http.MethodPut, "/api/compare/presets/cp-cross-2", comparePresetPutBody("Client B"), e0, "")
	if b.Code != http.StatusPreconditionFailed {
		t.Fatalf("Client B ueber /api/compare/presets mit veraltetem Stand: expected 412, got %d: %s",
			b.Code, b.Body.String())
	}
	if got := loadPresetOrFail(t, s, "cp-cross-2").Name; got != "Client A" {
		t.Errorf("der Preset-Endpunkt hat Client A's Aenderung ueberschrieben, name = %q", got)
	}
}

// AC-11 (Reentrancy): kind=route reicht per ServeHTTP an UpdateTripHandler
// durch, der fuer dieselbe <Nutzer, ID> BEREITS die Briefing-Sperre nimmt
// (S2). Eine zweite Sperre vor der Weiche waere ein sicherer Selbst-Blockierer
// — dieser Test faellt dann mit einer Zeitueberschreitung auf, statt den
// Testlauf haengen zu lassen. Der zweite Aufruf beweist zusaetzlich, dass die
// Sperre danach wieder frei ist.
func TestUpdateBriefingHandler_Route_StillWorks_NoDeadlock(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "trip-s6-route", "Alt")
	r := briefingVergleichEtagRouter(s)

	first := doReqWithin(t, 5*time.Second, r, http.MethodPut,
		"/api/briefings/trip-s6-route?kind=route", `{"name":"Neu"}`, "", "")
	if first.Code != 200 {
		t.Fatalf("PUT ?kind=route: expected 200, got %d: %s", first.Code, first.Body.String())
	}
	trip, err := s.LoadTrip("trip-s6-route")
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip: %v (%+v)", err, trip)
	}
	if trip.Name != "Neu" {
		t.Errorf("Aenderung nicht gespeichert, name = %q", trip.Name)
	}

	second := doReqWithin(t, 5*time.Second, r, http.MethodPut,
		"/api/briefings/trip-s6-route?kind=route", `{"name":"Noch neuer"}`, "", "")
	if second.Code != 200 {
		t.Fatalf("zweiter PUT ?kind=route: expected 200, got %d: %s", second.Code, second.Body.String())
	}
}
