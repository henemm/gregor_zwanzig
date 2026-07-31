package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1395 Scheibe S6 — ETag/If-Match auf den Ortsvergleich-Schreibpfaden.
// Spec: docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md
//
// Aufbau exakt wie trip_etag_ifmatch_test.go (S2): echte Dateien via
// t.TempDir()-Store, echte HTTP-Header, keine Attrappe. Wiederverwendet die
// dortigen Helfer doReq/mustETag (gleiches Paket).

// comparePresetEtagRouter verdrahtet die in dieser Scheibe beruehrten
// Preset-Routen an EINEM Router (chi-URL-Param statt handgesetztem
// RouteContext).
func comparePresetEtagRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Delete("/api/compare/presets/{id}", DeleteComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))
	return r
}

// comparePresetPutBody ist ein vollstaendiger PUT-Rumpf (der Preset-PUT ist ein
// Voll-Ersetzen, kein Patch — Pflichtfelder muessen mit).
func comparePresetPutBody(name string) string {
	return `{"name":"` + name + `","location_ids":["loc-1","loc-2"],"schedule":"daily",` +
		`"profil":"ALLGEMEIN","hour_from":6,"hour_to":18,"empfaenger":["test@example.com"]}`
}

func loadPresetOrFail(t *testing.T, s *store.Store, id string) *model.ComparePreset {
	t.Helper()
	p, err := s.LoadComparePreset(id)
	if err != nil {
		t.Fatalf("LoadComparePreset(%s): %v", id, err)
	}
	if p == nil {
		t.Fatalf("Preset %s existiert nicht mehr", id)
	}
	return p
}

// AC-1: GET liefert einen ETag, der dem Fingerabdruck der Datei entspricht.
func TestGetComparePresetHandler_ReturnsETag(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-1", "Vergleich 1", []string{"loc-1", "loc-2"})
	r := comparePresetEtagRouter(s)

	w := doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-1", "", "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	et := mustETag(t, w)
	if !strings.HasPrefix(et, `"`) || !strings.HasSuffix(et, `"`) {
		t.Errorf("ETag muss in doppelten Anfuehrungszeichen stehen (RFC 7232), got %q", et)
	}
	fp, err := s.BriefingFingerprint("cp-etag-1")
	if err != nil {
		t.Fatalf("BriefingFingerprint: %v", err)
	}
	if strings.Trim(et, `"`) != fp {
		t.Errorf("ETag %q entspricht nicht dem Datei-Fingerabdruck %q", et, fp)
	}
}

// AC-2: Zwei Lesevorgaenge ohne Aenderung dazwischen liefern denselben ETag.
func TestGetComparePresetHandler_ETagStableAcrossReads(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-2", "Vergleich 2", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	first := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-2", "", "", ""))
	second := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-2", "", "", ""))
	if first != second {
		t.Errorf("ETag aendert sich ohne Schreibvorgang: %q vs %q", first, second)
	}
}

// AC-3: Ohne If-Match verhaelt sich der PUT wie bisher (angenommen), liefert
// aber den neuen ETag mit.
func TestUpdateComparePresetHandler_NoIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-3", "Alt", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-3", comparePresetPutBody("Neu"), "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 ohne If-Match, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)

	if got := loadPresetOrFail(t, s, "cp-etag-3").Name; got != "Neu" {
		t.Errorf("Aenderung nicht sichtbar, name = %q", got)
	}
}

// AC-4: PUT mit dem zuletzt gelesenen ETag wird angenommen.
func TestUpdateComparePresetHandler_MatchingIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-4", "Alt", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	et := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-4", "", "", ""))
	w := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-4", comparePresetPutBody("Neu"), et, "")
	if w.Code != 200 {
		t.Fatalf("expected 200 mit passendem If-Match, got %d: %s", w.Code, w.Body.String())
	}
	if got := loadPresetOrFail(t, s, "cp-etag-4").Name; got != "Neu" {
		t.Errorf("Aenderung nicht gespeichert, name = %q", got)
	}
}

// AC-5: Veralteter If-Match -> 412 UND die Datei bleibt unveraendert.
func TestUpdateComparePresetHandler_StaleIfMatch_Returns412_FileUnchanged(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-5", "Original", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	stale := `"0000000000000000000000000000000000000000000000000000000000000000"`
	before, err := s.BriefingFingerprint("cp-etag-5")
	if err != nil {
		t.Fatalf("BriefingFingerprint vorher: %v", err)
	}

	w := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-5",
		comparePresetPutBody("Ueberschrieben"), stale, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 bei veraltetem If-Match, got %d: %s", w.Code, w.Body.String())
	}
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("412-Antwort darf keinen ETag tragen, got %q", et)
	}
	var body map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("412-Body ist kein JSON: %v (%s)", err, w.Body.String())
	}
	if body["error"] != "precondition_failed" {
		t.Errorf("expected error=precondition_failed, got %q", body["error"])
	}

	after, err := s.BriefingFingerprint("cp-etag-5")
	if err != nil {
		t.Fatalf("BriefingFingerprint nachher: %v", err)
	}
	if before != after {
		t.Errorf("Datei wurde trotz 412 veraendert: %q -> %q", before, after)
	}
	if got := loadPresetOrFail(t, s, "cp-etag-5").Name; got != "Original" {
		t.Errorf("Inhalt veraendert, erwartet name=Original, got %q", got)
	}
}

// AC-6: Der zurueckgelieferte ETag ist sofort wieder verwendbar — sonst liefe
// ein Client nach dem ersten Speichern dauerhaft ins 412.
func TestUpdateComparePresetHandler_ReturnsNewETag_SecondPutSucceeds(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-6", "Start", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-6", "", "", ""))

	first := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-6", comparePresetPutBody("Erster"), e0, "")
	if first.Code != 200 {
		t.Fatalf("erster PUT: expected 200, got %d: %s", first.Code, first.Body.String())
	}
	e1 := mustETag(t, first)
	if e1 == e0 {
		t.Fatalf("der Schreibvorgang haette den Stand aendern muessen, ETag blieb %q", e0)
	}

	second := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-6", comparePresetPutBody("Zweiter"), e1, "")
	if second.Code != 200 {
		t.Fatalf("zweiter PUT mit dem zurueckgelieferten ETag: expected 200, got %d: %s",
			second.Code, second.Body.String())
	}
	if got := loadPresetOrFail(t, s, "cp-etag-6").Name; got != "Zweiter" {
		t.Errorf("zweiter Schreibvorgang nicht gespeichert, name = %q", got)
	}
}

// AC-7: Zwei Clients mit demselben Ausgangsstand — der zweite verliert.
func TestUpdateComparePresetHandler_ConcurrentWrites_SecondWithStaleETagLoses(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-7", "Start", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-7", "", "", ""))

	a := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-7", comparePresetPutBody("Client A"), e0, "")
	if a.Code != 200 {
		t.Fatalf("Client A: expected 200, got %d: %s", a.Code, a.Body.String())
	}

	b := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-7", comparePresetPutBody("Client B"), e0, "")
	if b.Code != http.StatusPreconditionFailed {
		t.Fatalf("Client B mit veraltetem Stand: expected 412, got %d: %s", b.Code, b.Body.String())
	}
	if got := loadPresetOrFail(t, s, "cp-etag-7").Name; got != "Client A" {
		t.Errorf("Client A's Aenderung wurde ueberschrieben, name = %q", got)
	}
}

// AC-12: Der Fingerabdruck von Nutzer A gilt nicht fuer Nutzer B — gleiche
// Preset-ID, getrennte Dateien, getrennte Sperren.
func TestUpdateComparePresetHandler_TenantIsolation_ETagNotSharedAcrossUsers(t *testing.T) {
	base := t.TempDir()
	sA := store.New(base, "usera-s6")
	sB := store.New(base, "userb-s6")
	seedComparePreset(t, sA, "cp-shared-s6", "Vergleich A", []string{"loc-1"})
	// Abweichender Name -> abweichende Bytes -> abweichender Fingerabdruck.
	seedComparePreset(t, sB, "cp-shared-s6", "Vergleich B von Nutzer B", []string{"loc-1"})

	r := comparePresetEtagRouter(sA)

	etA := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-shared-s6", "", "", "usera-s6"))
	etB := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-shared-s6", "", "", "userb-s6"))
	if etA == etB {
		t.Fatalf("beide Nutzer haben denselben ETag %q — Testaufbau erzeugt keine Trennung", etA)
	}

	cross := doReq(r, http.MethodPut, "/api/compare/presets/cp-shared-s6",
		comparePresetPutBody("Fremd"), etA, "userb-s6")
	if cross.Code != http.StatusPreconditionFailed {
		t.Fatalf("A's ETag gegen B: expected 412, got %d: %s", cross.Code, cross.Body.String())
	}

	own := doReq(r, http.MethodPut, "/api/compare/presets/cp-shared-s6",
		comparePresetPutBody("Eigen"), etB, "userb-s6")
	if own.Code != 200 {
		t.Fatalf("B mit eigenem ETag: expected 200, got %d: %s", own.Code, own.Body.String())
	}

	if got := loadPresetOrFail(t, sA, "cp-shared-s6").Name; got != "Vergleich A" {
		t.Errorf("Cross-User-Leck: A's Preset veraendert, name = %q", got)
	}
}

// AC-13: If-Match: * wird angenommen, solange das Preset existiert.
func TestUpdateComparePresetHandler_IfMatchWildcard_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-13", "Alt", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/compare/presets/cp-etag-13", comparePresetPutBody("Neu"), "*", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 bei If-Match: *, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)
}

// AC-14: POST liefert bewusst KEINEN ETag (der Client holt danach ohnehin
// frisch) — der nachfolgende GET aber sehr wohl.
//
// Zur Sperre: ein blockierender Nachweis wie beim DELETE ist hier NICHT
// moeglich, weil die ID erst im Handler entsteht (newComparePresetID, 8
// Zufallsbytes) — der Test kann sie vorher nicht sperren. Nachweisbar ist die
// Gegenrichtung: die Sperre der neuen ID muss unmittelbar nach dem POST wieder
// frei sein. Bleibt die Freigabe aus (genommen, nie freigegeben), haengt dieser
// Test an genau dieser Stelle — mehr traegt der Aufbau ehrlicherweise nicht.
func TestCreateComparePresetHandler_NoETagInResponse_TakesLock(t *testing.T) {
	s := newTestStore(t)
	r := comparePresetEtagRouter(s)

	w := doReq(r, http.MethodPost, "/api/compare/presets", comparePresetPutBody("Neu angelegt"), "", "")
	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("POST darf keinen ETag liefern, got %q", et)
	}

	var created model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("POST-Antwort ist kein Preset: %v (%s)", err, w.Body.String())
	}
	if !strings.HasPrefix(created.ID, "cp-") {
		t.Fatalf("unerwartete ID %q", created.ID)
	}

	acquired := make(chan struct{})
	go func() {
		unlock := s.LockBriefing(created.ID)
		unlock()
		close(acquired)
	}()
	select {
	case <-acquired:
	case <-time.After(2 * time.Second):
		t.Fatalf("Sperre von %s ist nach dem POST noch belegt — sie wird genommen, aber nicht freigegeben",
			created.ID)
	}

	mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/"+created.ID, "", "", ""))
}

// AC-15: DELETE nimmt dieselbe Sperre wie der Schreibpfad und prueft KEIN
// If-Match.
//
// Der Sperr-Nachweis ist strukturell (analog TestDeleteTripHandler_...): der
// Test HAELT die Sperre selbst — genau der Zustand, in dem ein PUT geladen, aber
// noch nicht gespeichert hat. Solange sie gehalten wird, darf das DELETE die
// Datei nicht anfassen.
func TestDeleteComparePresetHandler_WaitsForBriefingLock_NoIfMatchCheck(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-del", "Zu loeschen", []string{"loc-1"})
	r := comparePresetEtagRouter(s)
	path := filepath.Join(s.BriefingsDir(), "cp-etag-del.json")

	unlock := s.LockBriefing("cp-etag-del")
	unlocked := false
	defer func() {
		if !unlocked {
			unlock()
		}
	}()

	started := make(chan struct{})
	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		close(started)
		// Voellig falscher If-Match: DELETE muss ihn ignorieren.
		done <- doReq(r, http.MethodDelete, "/api/compare/presets/cp-etag-del", "", `"voellig-falsch"`, "")
	}()
	<-started

	deadline := time.Now().Add(300 * time.Millisecond)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); os.IsNotExist(err) {
			t.Fatalf("DELETE hat die Datei geloescht, obwohl die Briefing-Sperre gehalten wurde " +
				"— der Loeschpfad nimmt die Sperre nicht")
		}
		time.Sleep(5 * time.Millisecond)
	}

	unlock()
	unlocked = true

	w := <-done
	if w.Code != 204 {
		t.Fatalf("DELETE nach Freigabe (mit falschem If-Match): expected 204, got %d: %s",
			w.Code, w.Body.String())
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Errorf("Datei haette nach der Freigabe geloescht sein muessen (Stat-Fehler: %v)", err)
	}
}

// AC-15: PATCH /state nimmt die Sperre und prueft KEIN If-Match.
func TestUpdateComparePresetStateHandler_NoIfMatchCheck_LockOnly(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-etag-state", "Alt", []string{"loc-1"})
	r := comparePresetEtagRouter(s)

	before := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-state", "", "", ""))
	fpBefore, err := s.BriefingFingerprint("cp-etag-state")
	if err != nil {
		t.Fatalf("BriefingFingerprint vorher: %v", err)
	}

	unlock := s.LockBriefing("cp-etag-state")
	unlocked := false
	defer func() {
		if !unlocked {
			unlock()
		}
	}()

	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		done <- doReq(r, http.MethodPatch, "/api/compare/presets/cp-etag-state/state",
			`{"archived":true}`, `"voellig-falsch"`, "")
	}()

	// Solange die Sperre gehalten wird, darf sich die Datei nicht aendern.
	deadline := time.Now().Add(300 * time.Millisecond)
	for time.Now().Before(deadline) {
		fp, err := s.BriefingFingerprint("cp-etag-state")
		if err != nil {
			t.Fatalf("BriefingFingerprint waehrend der Sperre: %v", err)
		}
		if fp != fpBefore {
			t.Fatalf("PATCH /state hat geschrieben, obwohl die Briefing-Sperre gehalten wurde " +
				"— der Zustandspfad nimmt die Sperre nicht")
		}
		time.Sleep(5 * time.Millisecond)
	}

	unlock()
	unlocked = true

	w := <-done
	if w.Code != 200 {
		t.Fatalf("PATCH /state muss If-Match ignorieren, got %d: %s", w.Code, w.Body.String())
	}
	if loadPresetOrFail(t, s, "cp-etag-state").ArchivedAt == nil {
		t.Fatalf("archived_at wurde nicht gesetzt")
	}
	after := mustETag(t, doReq(r, http.MethodGet, "/api/compare/presets/cp-etag-state", "", "", ""))
	if after == before {
		t.Errorf("ETag haette sich nach dem PATCH aendern muessen, blieb %q", before)
	}
}
