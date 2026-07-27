package handler

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1395 Scheibe S2 — ETag/If-Match auf den Trip-Schreibpfaden.
// Alle Tests arbeiten auf echten Dateien (t.TempDir()-Store, Bestandsmuster aus
// trip_write_test.go) und lesen echte HTTP-Header, keine Store-Rueckgabewerte.

// etagRouter verdrahtet alle in dieser Scheibe beruehrten Routen an EINEM
// Router, damit die Tests denselben Weg gehen wie das Frontend (chi-URL-Param
// statt handgesetztem RouteContext).
func etagRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	r.Post("/api/trips", CreateTripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", ConfirmWaypointHandler(s))
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	return r
}

// doReq schickt eine Anfrage durch den Router. ifMatch/user werden nur gesetzt,
// wenn nicht leer — "kein Header" ist ein eigener, gepruefter Fall.
func doReq(r http.Handler, method, path, body, ifMatch, user string) *httptest.ResponseRecorder {
	var rd io.Reader
	if body != "" {
		rd = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, rd)
	req.Header.Set("Content-Type", "application/json")
	if ifMatch != "" {
		req.Header.Set("If-Match", ifMatch)
	}
	if user != "" {
		req = addUserToContext(req, user)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// mustETag liest den ETag-Header und bricht ab, wenn er fehlt.
func mustETag(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	et := w.Header().Get("ETag")
	if et == "" {
		t.Fatalf("ETag-Header fehlt (Status %d, Body %s)", w.Code, w.Body.String())
	}
	return et
}

// AC-1: GET liefert einen ETag, der dem Fingerabdruck der Datei entspricht.
func TestTripHandler_ReturnsETag(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-1", "Trip 1")
	r := etagRouter(s)

	w := doReq(r, http.MethodGet, "/api/trips/etag-1", "", "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	et := mustETag(t, w)
	if !strings.HasPrefix(et, `"`) || !strings.HasSuffix(et, `"`) {
		t.Errorf("ETag muss in doppelten Anfuehrungszeichen stehen (RFC 7232), got %q", et)
	}
	fp, err := s.BriefingFingerprint("etag-1")
	if err != nil {
		t.Fatalf("BriefingFingerprint: %v", err)
	}
	if strings.Trim(et, `"`) != fp {
		t.Errorf("ETag %q entspricht nicht dem Datei-Fingerabdruck %q", et, fp)
	}
}

// AC-2: Zwei Lesevorgaenge ohne Aenderung dazwischen liefern denselben ETag.
func TestTripHandler_ETagStableAcrossReads(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-2", "Trip 2")
	r := etagRouter(s)

	first := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-2", "", "", ""))
	second := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-2", "", "", ""))
	if first != second {
		t.Errorf("ETag aendert sich ohne Schreibvorgang: %q vs %q", first, second)
	}
}

// AC-3: Ohne If-Match verhaelt sich der PUT wie bisher (angenommen), liefert
// aber den neuen ETag mit.
func TestUpdateTripHandler_NoIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-3", "Alt")
	r := etagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/etag-3", `{"name":"Neu"}`, "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 ohne If-Match, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)

	got := doReq(r, http.MethodGet, "/api/trips/etag-3", "", "", "")
	var trip model.Trip
	json.Unmarshal(got.Body.Bytes(), &trip)
	if trip.Name != "Neu" {
		t.Errorf("Aenderung nicht sichtbar, name = %q", trip.Name)
	}
}

// AC-4: PUT mit dem zuletzt gelesenen ETag wird angenommen.
func TestUpdateTripHandler_MatchingIfMatch_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-4", "Alt")
	r := etagRouter(s)

	et := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-4", "", "", ""))
	w := doReq(r, http.MethodPut, "/api/trips/etag-4", `{"name":"Neu"}`, et, "")
	if w.Code != 200 {
		t.Fatalf("expected 200 mit passendem If-Match, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-5: Veralteter If-Match -> 412 UND die Datei bleibt byte-identisch.
func TestUpdateTripHandler_StaleIfMatch_Returns412_FileUnchanged(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-5", "Original")
	r := etagRouter(s)

	stale := `"0000000000000000000000000000000000000000000000000000000000000000"`
	before, err := s.BriefingFingerprint("etag-5")
	if err != nil {
		t.Fatalf("BriefingFingerprint vorher: %v", err)
	}

	w := doReq(r, http.MethodPut, "/api/trips/etag-5", `{"name":"Ueberschrieben"}`, stale, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 bei veraltetem If-Match, got %d: %s", w.Code, w.Body.String())
	}

	after, err := s.BriefingFingerprint("etag-5")
	if err != nil {
		t.Fatalf("BriefingFingerprint nachher: %v", err)
	}
	if before != after {
		t.Errorf("Datei wurde trotz 412 veraendert: %q -> %q", before, after)
	}
	loaded, _ := s.LoadTrip("etag-5")
	if loaded == nil || loaded.Name != "Original" {
		t.Errorf("Inhalt veraendert, erwartet name=Original, got %+v", loaded)
	}
}

// AC-6: Der S1-Heilungsfall. Die gespeicherte Datei traegt eine krumme
// Versandzeit ("07:30:00"); LoadTrip heilt sie in-memory auf "07:00:00" OHNE
// Rueckschreiben. Der erste PUT persistiert die Heilung — der Fingerabdruck
// aendert sich also, obwohl der Nutzer inhaltlich nichts geaendert hat. Genau
// deshalb MUSS der PUT den neuen ETag mitliefern, sonst laeuft der Client mit
// dem ersten Schreibvorgang dauerhaft ins 412.
func TestUpdateTripHandler_ReturnsNewETag_SecondPutSucceeds(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID: "etag-6", Name: "Heilung",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{"morning_time": "07:30:00", "enabled": true},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	r := etagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-6", "", "", ""))

	first := doReq(r, http.MethodPut, "/api/trips/etag-6", `{}`, e0, "")
	if first.Code != 200 {
		t.Fatalf("erster PUT: expected 200, got %d: %s", first.Code, first.Body.String())
	}
	e1 := mustETag(t, first)
	if e1 == e0 {
		t.Fatalf("Heilung haette den Stand aendern muessen, ETag blieb %q", e0)
	}

	second := doReq(r, http.MethodPut, "/api/trips/etag-6", `{"name":"Zweiter"}`, e1, "")
	if second.Code != 200 {
		t.Fatalf("zweiter PUT mit dem zurueckgelieferten ETag: expected 200, got %d: %s",
			second.Code, second.Body.String())
	}
}

// AC-7: Zwei Clients mit demselben Ausgangsstand — der zweite verliert.
func TestUpdateTripHandler_ConcurrentWrites_SecondWithStaleETagLoses(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-7", "Start")
	r := etagRouter(s)

	e0 := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-7", "", "", ""))

	a := doReq(r, http.MethodPut, "/api/trips/etag-7", `{"name":"Client A"}`, e0, "")
	if a.Code != 200 {
		t.Fatalf("Client A: expected 200, got %d: %s", a.Code, a.Body.String())
	}

	b := doReq(r, http.MethodPut, "/api/trips/etag-7", `{"name":"Client B"}`, e0, "")
	if b.Code != http.StatusPreconditionFailed {
		t.Fatalf("Client B mit veraltetem Stand: expected 412, got %d: %s", b.Code, b.Body.String())
	}

	loaded, _ := s.LoadTrip("etag-7")
	if loaded == nil || loaded.Name != "Client A" {
		t.Errorf("Client A's Aenderung wurde ueberschrieben: %+v", loaded)
	}
}

// AC-9: Der Fingerabdruck von Nutzer A gilt nicht fuer Nutzer B — gleiche
// Trip-ID, getrennte Dateien.
func TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers(t *testing.T) {
	base := t.TempDir()
	sA := store.New(base, "usera-1395")
	sB := store.New(base, "userb-1395")
	seedTrip(t, sA, "shared-1395", "Trip A")
	// Abweichender Name -> abweichende Bytes -> abweichender Fingerabdruck.
	seedTrip(t, sB, "shared-1395", "Trip B von Nutzer B")

	r := etagRouter(sA)

	etA := mustETag(t, doReq(r, http.MethodGet, "/api/trips/shared-1395", "", "", "usera-1395"))
	etB := mustETag(t, doReq(r, http.MethodGet, "/api/trips/shared-1395", "", "", "userb-1395"))
	if etA == etB {
		t.Fatalf("beide Nutzer haben denselben ETag %q — Testaufbau erzeugt keine Trennung", etA)
	}

	cross := doReq(r, http.MethodPut, "/api/trips/shared-1395", `{"name":"Fremd"}`, etA, "userb-1395")
	if cross.Code != http.StatusPreconditionFailed {
		t.Fatalf("A's ETag gegen B: expected 412, got %d: %s", cross.Code, cross.Body.String())
	}

	own := doReq(r, http.MethodPut, "/api/trips/shared-1395", `{"name":"Eigen"}`, etB, "userb-1395")
	if own.Code != 200 {
		t.Fatalf("B mit eigenem ETag: expected 200, got %d: %s", own.Code, own.Body.String())
	}

	loadedA, _ := sA.LoadTrip("shared-1395")
	if loadedA == nil || loadedA.Name != "Trip A" {
		t.Errorf("Cross-User-Leck: A's Trip veraendert: %+v", loadedA)
	}
}

// AC-10: If-Match: * wird angenommen, solange die Tour existiert.
func TestUpdateTripHandler_IfMatchWildcard_Accepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-10", "Alt")
	r := etagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/etag-10", `{"name":"Neu"}`, "*", "")
	if w.Code != 200 {
		t.Fatalf("expected 200 bei If-Match: *, got %d: %s", w.Code, w.Body.String())
	}
	mustETag(t, w)
}

// AC-14: Kommaliste — ein passender Wert genuegt.
func TestUpdateTripHandler_MultipleIfMatchValues_AnyMatchAccepted(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-14", "Alt")
	r := etagRouter(s)

	et := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-14", "", "", ""))
	list := `"deadbeef", ` + et + `, "cafebabe"`
	w := doReq(r, http.MethodPut, "/api/trips/etag-14", `{"name":"Neu"}`, list, "")
	if w.Code != 200 {
		t.Fatalf("expected 200 bei Kommaliste mit Treffer, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-12: POST /api/trips liefert bewusst KEINEN ETag (der Client holt danach
// ohnehin frisch) — der nachfolgende GET aber sehr wohl.
func TestCreateTripHandler_NoETagInResponse(t *testing.T) {
	s := newTestStore(t)
	r := etagRouter(s)

	body := `{"id":"etag-12","name":"Neu","stages":[{"id":"S1","name":"D1","date":"2026-05-01",` +
		`"waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
	w := doReq(r, http.MethodPost, "/api/trips", body, "", "")
	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("POST darf keinen ETag liefern, got %q", et)
	}
	mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-12", "", "", ""))
}

// AC-13: Die 412-Antwort traegt keinen ETag und einen deutschsprachigen
// detail-Text.
func TestUpdateTripHandler_412Response_NoETagHeader_GermanDetail(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-13", "Alt")
	r := etagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/etag-13", `{"name":"Neu"}`, `"veraltet"`, "")
	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("expected 412, got %d: %s", w.Code, w.Body.String())
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
	if strings.TrimSpace(body["detail"]) == "" {
		t.Fatalf("detail fehlt oder ist leer")
	}
	// Deutschsprachig: der Text nennt das Nachladen als Ausweg.
	if !strings.Contains(strings.ToLower(body["detail"]), "geaendert") &&
		!strings.Contains(strings.ToLower(body["detail"]), "geändert") {
		t.Errorf("detail wirkt nicht deutschsprachig/erklaerend: %q", body["detail"])
	}
}

// AC-15: PATCH /state ignoriert If-Match — der Header darf die Anfrage nicht
// scheitern lassen, der Schreibvorgang wirkt und der ETag zieht nach.
func TestUpdateTripStateHandler_NoIfMatchCheck_LockOnly(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-15", "Alt")
	r := etagRouter(s)

	before := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-15", "", "", ""))

	w := doReq(r, http.MethodPatch, "/api/trips/etag-15/state", `{"paused":true}`, `"voellig-falsch"`, "")
	if w.Code != 200 {
		t.Fatalf("PATCH /state muss If-Match ignorieren, got %d: %s", w.Code, w.Body.String())
	}
	loaded, _ := s.LoadTrip("etag-15")
	if loaded == nil || loaded.PausedAt == nil {
		t.Fatalf("paused_at wurde nicht gesetzt: %+v", loaded)
	}
	after := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-15", "", "", ""))
	if after == before {
		t.Errorf("ETag haette sich nach dem PATCH aendern muessen, blieb %q", before)
	}
}

// AC-15: Dasselbe fuer die Waypoint-Bestaetigung.
func TestConfirmWaypointHandler_NoIfMatchCheck_LockOnly(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-15b", "Alt")
	r := etagRouter(s)

	before := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-15b", "", "", ""))

	w := doReq(r, http.MethodPatch, "/api/trips/etag-15b/waypoints/W1/confirm",
		`{"confirmed":true}`, `"voellig-falsch"`, "")
	if w.Code != 200 {
		t.Fatalf("PATCH /confirm muss If-Match ignorieren, got %d: %s", w.Code, w.Body.String())
	}
	after := mustETag(t, doReq(r, http.MethodGet, "/api/trips/etag-15b", "", "", ""))
	if after == before {
		t.Errorf("ETag haette sich nach der Bestaetigung aendern muessen, blieb %q", before)
	}
}

// Sperre + atomares Schreiben: viele gleichzeitige PUTs ohne If-Match landen
// alle mit 200, jeder liefert einen ETag, und die Datei bleibt danach gueltiges,
// ladbares JSON (kein halb geschriebener Stand). Unter -race mitzulaufen ist
// Teil der Zusage.
func TestUpdateTripHandler_ConcurrentWritesWithoutIfMatch_FileStaysValid(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-par", "Start")
	r := etagRouter(s)

	const n = 12
	var wg sync.WaitGroup
	results := make([]*httptest.ResponseRecorder, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			body := `{"name":"Parallel ` + string(rune('A'+i)) + `"}`
			results[i] = doReq(r, http.MethodPut, "/api/trips/etag-par", body, "", "")
		}(i)
	}
	wg.Wait()

	for i, w := range results {
		if w.Code != 200 {
			t.Fatalf("PUT %d: expected 200, got %d: %s", i, w.Code, w.Body.String())
		}
		if w.Header().Get("ETag") == "" {
			t.Fatalf("PUT %d: ETag-Header fehlt", i)
		}
	}

	loaded, err := s.LoadTrip("etag-par")
	if err != nil {
		t.Fatalf("Datei nach parallelen Schreibvorgaengen nicht ladbar: %v", err)
	}
	if loaded == nil || !strings.HasPrefix(loaded.Name, "Parallel ") {
		t.Errorf("unerwarteter Endstand: %+v", loaded)
	}
}

// F002-Geschwisterfall: dieselbe Luecke wie in PutTripWeatherConfigHandler,
// nur auf dem Bestaetigungs-Pfad — auch er schrieb die geladene Tour zurueck,
// ohne die Kennung auf den URL-Parameter zu setzen. Folge: die Bestaetigung
// landet in einer fremden Tour, die angefragte bleibt unveraendert, und der
// Nutzer bekommt 200 mit gueltigem ETag.
func TestConfirmWaypointHandler_WritesRequestedTripNotInnerID(t *testing.T) {
	s := newTestStore(t)
	dir := s.BriefingsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	raw := `{"id":"innen-wp","kind":"route","name":"Drift","stages":[{"id":"S1","name":"D1",` +
		`"date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,` +
		`"elevation_m":500}]}]}`
	if err := os.WriteFile(filepath.Join(dir, "aussen-wp.json"), []byte(raw), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
	r := etagRouter(s)

	w := doReq(r, http.MethodPatch, "/api/trips/aussen-wp/waypoints/W1/confirm",
		`{"confirmed":true}`, "", "")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("aussen-wp")
	if err != nil {
		t.Fatalf("LoadTrip(aussen-wp): %v", err)
	}
	if loaded == nil || len(loaded.Stages) == 0 || len(loaded.Stages[0].Waypoints) == 0 {
		t.Fatalf("aussen-wp.json fehlt oder ist leer: %+v", loaded)
	}
	confirmed := loaded.Stages[0].Waypoints[0].Confirmed
	if confirmed == nil || !*confirmed {
		t.Errorf("Bestaetigung ist bei der angefragten Tour nicht angekommen, confirmed = %v", confirmed)
	}
	if _, err := os.Stat(filepath.Join(dir, "innen-wp.json")); err == nil {
		t.Errorf("Bestaetigung landete in der fremden Tour briefings/innen-wp.json")
	}
}

// Der Loeschpfad muss dieselbe Sperre nehmen wie die Schreibpfade — sonst
// bleibt genau die Luecke offen, um die es in #1395 geht: ein DELETE, das
// mitten in einen laufenden PUT faellt, entfernt die Datei, und der PUT
// schreibt sie danach wieder hin — die geloeschte Tour ersteht wieder auf.
//
// Der Nachweis ist bewusst NICHT ueber ein Zeitfenster gefuehrt (das waere ein
// Zufallstreffer im Mikrosekundenbereich), sondern strukturell: der Test HAELT
// die Sperre selbst — genau der Zustand, in dem ein PUT geladen, aber noch
// nicht gespeichert hat. Solange sie gehalten wird, darf das DELETE die Datei
// nicht anfassen.
func TestDeleteTripHandler_WaitsForBriefingLock(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "etag-del", "Zu loeschen")
	r := etagRouter(s)
	path := filepath.Join(s.BriefingsDir(), "etag-del.json")

	unlock := s.LockBriefing("etag-del")
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
		done <- doReq(r, http.MethodDelete, "/api/trips/etag-del", "", "", "")
	}()
	<-started

	// Solange die Sperre gehalten wird, darf die Datei nicht verschwinden.
	// Mit Sperre kann das NIE passieren (das DELETE haengt am Mutex), ohne
	// Sperre laeuft das DELETE sofort durch.
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
		t.Fatalf("DELETE nach Freigabe: expected 204, got %d: %s", w.Code, w.Body.String())
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Errorf("Datei haette nach der Freigabe geloescht sein muessen (Stat-Fehler: %v)", err)
	}
}

// Nutzersichtbare Zusage: nach einem gleichzeitigen DELETE und PUT ist der
// Zustand EINDEUTIG — entweder ist die Tour weg, oder sie liegt als gueltiges,
// ladbares JSON da. Eine halb geschriebene oder wiederauferstandene Datei ist
// beides nicht.
//
// Anders als der Test darueber ist das eine Invariante, kein struktureller
// Beweis: ohne Sperre kann sie mit Glueck trotzdem halten (das Zeitfenster ist
// winzig). Mit Sperre ist der Bruch strukturell ausgeschlossen — beide
// Reihenfolgen sind unbedenklich (PUT dann DELETE = weg; DELETE dann PUT =
// 404, es wird nichts geschrieben).
func TestDeleteAndPutConcurrently_NoResurrectedOrHalfWrittenTrip(t *testing.T) {
	s := newTestStore(t)
	r := etagRouter(s)

	for i := 0; i < 25; i++ {
		id := "race-del-" + strconv.Itoa(i)
		seedTrip(t, s, id, "Start")

		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			doReq(r, http.MethodPut, "/api/trips/"+id, `{"name":"Geschrieben"}`, "", "")
		}()
		go func() {
			defer wg.Done()
			doReq(r, http.MethodDelete, "/api/trips/"+id, "", "", "")
		}()
		wg.Wait()

		if _, err := os.Stat(filepath.Join(s.BriefingsDir(), id+".json")); os.IsNotExist(err) {
			continue // geloescht — eindeutiger Endzustand
		}
		loaded, err := s.LoadTrip(id)
		if err != nil {
			t.Fatalf("%s: Datei existiert, ist aber nicht ladbar: %v", id, err)
		}
		if loaded == nil || loaded.ID != id {
			t.Fatalf("%s: Datei existiert, enthaelt aber keine gueltige Tour: %+v", id, loaded)
		}
	}
}

// AC-16 (Fail-soft): Ist der Fingerabdruck nach einem erfolgreichen
// Schreibvorgang nicht lesbar, bleibt der ETag-Header schlicht weg — die
// Antwort selbst bleibt gueltig.
//
// Der Fehlerfall laesst sich NICHT durch den Handler hindurch erzeugen: der
// gelesene Pfad ist derselbe, den SaveTrip gerade erfolgreich geschrieben hat,
// und eine Store-Attrappe ist in diesem Projekt nicht erlaubt. Geprueft wird
// darum direkt die Produktivfunktion, die diese Entscheidung trifft — mit
// einem echten Fehlerwert, ohne Attrappe.
func TestSetETagHeader_OmitsHeaderWhenFingerprintUnavailable(t *testing.T) {
	w := httptest.NewRecorder()
	setETagHeader(w, "", errors.New("read briefings/x.json: permission denied"))
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("ETag darf bei Lesefehler nicht gesetzt werden, got %q", et)
	}
	if w.Code != 200 {
		t.Errorf("setETagHeader darf den Status nicht anfassen, got %d", w.Code)
	}

	ok := httptest.NewRecorder()
	setETagHeader(ok, "abc123", nil)
	if et := ok.Header().Get("ETag"); et != `"abc123"` {
		t.Errorf(`expected ETag "abc123", got %q`, et)
	}
}
