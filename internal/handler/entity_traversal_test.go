package handler

// TDD RED — Issue #2140 Scheibe 2 (Entitaets-Achse). SPEC:
// docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md AC-1 bis AC-7, AC-11.
//
// WICHTIGER EMPIRISCHER BEFUND (Details im Bericht an den Team-Lead, mit
// Scratch-Belegen aus `go test`): fuer JEDE Route, deren Entitaets-ID ein
// URL-PFAD-PARAMETER ist (PUT/PATCH/DELETE auf .../{id}), kann eine
// Traversal-Kennung mit echtem "/" den Handler NIEMALS erreichen:
//   - unkodiert ("../../bob/user") matcht chi die Route gar nicht (zu viele
//     Pfadsegmente fuer das Ein-Segment-Muster {id}) -> 404 VOM ROUTER, der
//     Handler wird nie aufgerufen (empirisch verifiziert).
//   - prozent-kodiert ("..%2F..%2Fbob%2Fuser") erreicht den Handler zwar als
//     EIN Segment, aber chi.URLParam liefert den Wert weiterhin KODIERT
//     zurueck (chi dekodiert %2F nicht) — kein echter "/" erreicht je
//     filepath.Join (empirisch verifiziert, s. AC-11 unten).
// Der reale Angriffsweg fuer diese Achse ist deshalb NICHT der Pfad-
// Parameter, sondern (a) der REQUEST-BODY bei POST /api/trips bzw.
// /api/locations (AC-1/AC-2, echte Kennungen landen dort ungeprueft in
// SaveTrip/SaveLocation) und (b) der direkte Store-Aufruf unter Umgehung von
// HTTP (AC-8, internal/store/entity_id_test.go). Fuer AC-3/AC-4/AC-5 (Pfad-
// Parameter) verwenden die Tests deshalb NICHT "../../bob/user" (das wuerde
// die Route gar nicht treffen), sondern "." — ein Segment, das den Handler
// NACHWEISLICH erreicht (chi fuehrt anders als Starlette/Python KEINE
// RFC-3986-Dot-Segment-Aufloesung durch, s. AC-9-Pythontest) und gegen
// ValidEntityID verstoesst ("nicht . und nicht .."). Da jede Store-Methode
// nur id+".json" anhaengt (nie einen rohen Verzeichnis-Join), wird ein
// blankes "." zu einer harmlosen Datei "..json" IM EIGENEN Verzeichnis — die
// RED-Wirkung liegt hier im FALSCHEN STATUSCODE (404/204/409 statt der von
// der Spec verlangten 400), nicht in einem tatsaechlichen Fremdzugriff.
// Empirisch mit dem unveraenderten Produktivcode gemessen: CreateTrip mit
// Traversal-Body -> 201, CreateLocation (Zufalls-409-Fall) -> 409, alle
// Pfad-Parameter-Routen mit "." -> 404 oder 204 (nie 400).
//
// WEGWEISER, welche Tests einen Bug reproduzieren und welche einen bereits
// sicheren Zustand bewachen (QA-Rueckmeldung nach Erstfassung):
//   - ECHTE SICHERHEITS-BEFUNDE (belegen Fremdzugriff ohne Guard): AC-1,
//     AC-2 (Haupttest TestCreateLocationHandler_TraversalIDInBody_Rejected_AC2,
//     Ziel-ID ohne bereits existierende Kollisionsdatei), AC-7, AC-8
//     (internal/store/entity_id_test.go).
//   - STATUSCODE-VEREINHEITLICHUNG (kein Fremdzugriff moeglich, nur
//     404/204/409 statt 400): AC-3, AC-4, AC-5, sowie der AC-2-Zusatztest
//     TestCreateLocationHandler_TraversalIDCollidesWithExistingFile_AC2.
//   - REGRESSIONSWAECHTER (bereits heute gruen, kein RED-Signal): AC-11.

import (
	"encoding/json"
	"io/fs"
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

// entityTestRouter registriert exakt die von dieser Spec betroffenen Routen
// (Source-Sektion der Spec) mit echtem chi-Routing, analog zu den
// bestehenden *_test.go-Vorlagen (briefing_history_test.go u.a.).
func entityTestRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))

	r.Post("/api/locations", CreateLocationHandler(s))
	r.Get("/api/locations/{id}", LocationHandler(s))
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))
	r.Delete("/api/locations/{id}", DeleteLocationHandler(s))

	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))
	r.Delete("/api/compare/presets/{id}", DeleteComparePresetHandler(s))
	return r
}

// seedRealBobForHandler legt einen echten zweiten Nutzer "bob" an (Basis fuer
// die Positivkontrolle nach Regel A: dessen user.json ist ueber
// briefingsDir()/LocationsDir() — beide ZWEI Ebenen unter data/users/ —
// exakt das Ziel von "../../bob/user", siehe entity_id_test.go). base traegt
// bewusst eine ANDERE UserID als "bob"; der Angriff wird ueber
// withUserCtx(..., "alice") gefahren, nie ueber bob selbst.
func seedRealBobForHandler(t *testing.T) (base *store.Store, bobUserFile string, before []byte) {
	t.Helper()
	tmpDir := t.TempDir()
	base = store.New(tmpDir, "irrelevant")
	if err := base.SaveUser(model.User{ID: "bob", PasswordHash: "bobs-real-hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	bobUserFile = filepath.Join(base.UserDir("bob"), "user.json")
	var err error
	before, err = os.ReadFile(bobUserFile)
	if err != nil {
		t.Fatalf("ReadFile(bob) setup: %v", err)
	}
	return base, bobUserFile, before
}

func assertBobUnchanged(t *testing.T, bobUserFile string, before []byte) {
	t.Helper()
	after, err := os.ReadFile(bobUserFile)
	if err != nil {
		t.Fatalf("ReadFile(bob) after attack: %v", err)
	}
	if string(before) != string(after) {
		t.Errorf("Bobs echte user.json wurde veraendert:\nvorher:  %s\nnachher: %s", before, after)
	}
}

// -----------------------------------------------------------------------
// AC-1 / AC-2 — Traversal-Kennung im Request-Body
// -----------------------------------------------------------------------

// AC-1: POST /api/trips mit {"id":"../../bob/user"} ueberschreibt heute
// tatsaechlich Bobs echte user.json mit Trip-JSON (empirisch verifiziert:
// SaveTrip erhaelt die Kennung ungeprueft, filepath.Join kappt "briefings"
// und die eigene UserID und landet bei data/users/bob/user.json). Heutiger
// Statuscode: 201 (nicht 400).
func TestCreateTripHandler_TraversalIDInBody_Rejected_AC1(t *testing.T) {
	base, bobFile, before := seedRealBobForHandler(t)
	router := entityTestRouter(base)

	body := `{"id":"../../bob/user","name":"Angreifer-Trip"}`
	req := httptest.NewRequest(http.MethodPost, "/api/trips", strings.NewReader(body))
	req = withUserCtx(req, "alice")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("AC-1: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	assertBobUnchanged(t, bobFile, before)
}

// AC-2: POST /api/locations mit einer Ausbruchs-ID, an deren Ziel VOR dem
// Angriff nachweislich NICHTS liegt (Nachbesserung nach QA-Rueckmeldung: die
// urspruengliche Wahl "../../bob/user" bewachte einen Zufall — siehe
// TestCreateLocationHandler_TraversalIDCollidesWithExistingFile_AC2 unten).
// "../../bob/eingeschleust" landet ueber denselben Zwei-Ebenen-Trick
// (LocationsDir liegt wie briefingsDir ZWEI Ebenen unter data/users/) bei
// data/users/bob/eingeschleust.json. Positivkontrolle (empirisch mit einem
// Scratch-`go test` gegen den unveraenderten Produktivcode verifiziert, nicht
// committed): LoadLocation("../../bob/eingeschleust") liefert VOR dem Angriff
// (nil, nil) — kein Conflict-Block greift also —, und SaveLocation legt die
// Datei anschliessend TATSAECHLICH unter genau diesem Pfad in Bobs
// Nutzerverzeichnis an (Inhalt: {"id":"../../bob/eingeschleust",
// "name":"Angriffsort",...}). Das ist der reale Bug, den diese Spec schliesst
// — nicht das Zufalls-409 der Kollisionsvariante.
func TestCreateLocationHandler_TraversalIDInBody_Rejected_AC2(t *testing.T) {
	base, bobFile, before := seedRealBobForHandler(t)
	router := entityTestRouter(base)
	bobDir := base.UserDir("bob")
	dirBefore := snapshotDir(t, bobDir)

	const attackID = "../../bob/eingeschleust"
	body := `{"id":"` + attackID + `","name":"Angriffsort","lat":47.0,"lon":11.0}`
	req := httptest.NewRequest(http.MethodPost, "/api/locations", strings.NewReader(body))
	req = withUserCtx(req, "alice")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("AC-2: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	assertBobUnchanged(t, bobFile, before)

	dirAfter := snapshotDir(t, bobDir)
	if len(dirAfter) != len(dirBefore) {
		t.Errorf("AC-2: in Bobs Verzeichnis ist eine neue Datei entstanden (vorher=%d, nachher=%d): %v", len(dirBefore), len(dirAfter), dirAfter)
	}
	injectedPath := filepath.Join(bobDir, "eingeschleust.json")
	if _, statErr := os.Stat(injectedPath); statErr == nil {
		t.Errorf("AC-2: eingeschleuste Datei %q existiert in Bobs Verzeichnis", injectedPath)
	}
}

// AC-2 (Zusatzfall, KEIN tragender Nachweis fuer diese AC): dieselbe Route
// mit der urspruenglich in der Spec genannten Kennung "../../bob/user"
// antwortet heute mit 409 statt 400 — NICHT weil eine Sperre greift, sondern
// weil Bobs echte user.json zufaellig als (fast leere) Location
// deserialisierbar ist und LoadLocation("../../bob/user") deshalb
// existing!=nil liefert (CreateLocationHandler bricht dann VOR SaveLocation
// mit Conflict ab). Dieser Schutz haengt an einer Feld-Kompatibilitaet
// zwischen User und Location, die niemand zugesichert hat — ein
// Pflichtfeld-Wechsel bei Location wuerde ihn stillschweigend aufheben,
// ohne dass dieser Test es merkt (er misst nur "nicht 400"). Er bewacht
// deshalb ausschliesslich den heutigen STATUSCODE (409 statt der von der
// Spec verlangten 400), NICHT die Datensicherheit — die leistet
// ausschliesslich der Test oben.
func TestCreateLocationHandler_TraversalIDCollidesWithExistingFile_AC2(t *testing.T) {
	base, bobFile, before := seedRealBobForHandler(t)
	router := entityTestRouter(base)

	body := `{"id":"../../bob/user","name":"Angriffsort","lat":47.0,"lon":11.0}`
	req := httptest.NewRequest(http.MethodPost, "/api/locations", strings.NewReader(body))
	req = withUserCtx(req, "alice")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("AC-2 (Kollisionsfall, Zufalls-409): expected 400, got %d: %s", w.Code, w.Body.String())
	}
	assertBobUnchanged(t, bobFile, before)
}

// -----------------------------------------------------------------------
// AC-3 / AC-4 / AC-5 — ungueltige Kennung als URL-Pfad-Parameter
// -----------------------------------------------------------------------

// AC-3 ist NACH DEM MESSERGEBNIS AM DATEIANFANG KEINE SICHERHEITS-AC MEHR
// (kein Fremdzugriff via Pfad-Parameter moeglich), sondern reine
// STATUSCODE-VEREINHEITLICHUNG: PUT/PATCH(state)/DELETE /api/trips/{id} mit
// id="." — "." erreicht den Handler nachweislich (chi loest anders als
// Starlette keine Dot-Segmente auf), verstoesst aber gegen ValidEntityID
// ("nicht ."). Der Store-Join haengt nur id+".json" an, "." wird so zur
// harmlosen Datei "..json" IM EIGENEN Verzeichnis — kein Fremdzugriff auch
// ohne Guard. Heutiger Stand (empirisch verifiziert): PUT -> 404, PATCH
// state -> 404, DELETE -> 204 — nie 400, das ist der einzige RED-Befund.
func TestTripIDRoutes_InvalidPathID_Rejected_AC3(t *testing.T) {
	const invalidID = "."

	t.Run("PUT", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPut, "/api/trips/"+invalidID, strings.NewReader(`{"name":"x"}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-3 PUT: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("PATCH_state", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPatch, "/api/trips/"+invalidID+"/state", strings.NewReader(`{"paused":true}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-3 PATCH state: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("DELETE", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/trips/"+invalidID, nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-3 DELETE: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})
}

// AC-4 ist wie AC-3 KEINE SICHERHEITS-AC (kein Fremdzugriff via
// Pfad-Parameter moeglich), sondern reine Statuscode-Vereinheitlichung —
// analog fuer /api/locations/{id}. Heutiger Stand: PUT -> 404, PATCH -> 404,
// DELETE -> 204 — nie 400.
func TestLocationIDRoutes_InvalidPathID_Rejected_AC4(t *testing.T) {
	const invalidID = "."

	t.Run("PUT", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPut, "/api/locations/"+invalidID, strings.NewReader(`{"id":".","name":"x","lat":1,"lon":1}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-4 PUT: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("PATCH", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPatch, "/api/locations/"+invalidID, strings.NewReader(`{"group_id":"g"}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-4 PATCH: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("DELETE", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/locations/"+invalidID, nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-4 DELETE: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})
}

// AC-5 ist ebenfalls KEINE SICHERHEITS-AC, sondern reine Statuscode-
// Vereinheitlichung — analog fuer /api/compare/presets/{id}. Hier ist ein
// Fremdzugriff via Pfad-Parameter STRUKTURELL nie moeglich (Array-basierte
// Suche per Content-ID statt direktem Pfad-Join, s. Kommentar am Dateianfang)
// — unabhaengig von der gewaehlten Kennung. Heutiger Stand: PUT -> 404,
// PATCH state -> 404, DELETE -> 404 (nie 400, das ist der einzige RED-Befund).
func TestComparePresetIDRoutes_InvalidPathID_Rejected_AC5(t *testing.T) {
	const invalidID = "."

	t.Run("PUT", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/"+invalidID, strings.NewReader(`{}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-5 PUT: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("PATCH_state", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodPatch, "/api/compare/presets/"+invalidID+"/state", strings.NewReader(`{"archived":true}`))
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-5 PATCH state: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("DELETE", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/compare/presets/"+invalidID, nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-5 DELETE: expected 400, got %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})
}

// -----------------------------------------------------------------------
// AC-6 — Positivkontrolle: Umlaut-ID bleibt vollstaendig nutzbar
// -----------------------------------------------------------------------

// AC-6: ein real angelegter Ort mit Umlaut in der Kennung ("hochfügen")
// bleibt ueber GET/PUT/DELETE normal bedienbar — unterscheidet die
// Segment-Pruefung von der verworfenen ASCII-Whitelist (Spec, Abschnitt
// "Warum die ... ASCII-Whitelist verworfen wurde").
func TestLocationWithUmlautID_RemainsFullyUsable_AC6(t *testing.T) {
	base := store.New(t.TempDir(), "irrelevant")
	router := entityTestRouter(base)
	const id = "hochfügen"

	createBody := `{"id":"hochfügen","name":"Hochfügen","lat":47.35,"lon":11.86}`
	req := httptest.NewRequest(http.MethodPost, "/api/locations", strings.NewReader(createBody))
	req = withUserCtx(req, "henning")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-6 setup: POST hochfügen expected 201, got %d: %s", w.Code, w.Body.String())
	}

	getReq := httptest.NewRequest(http.MethodGet, "/api/locations/"+id, nil)
	getReq = withUserCtx(getReq, "henning")
	getW := httptest.NewRecorder()
	router.ServeHTTP(getW, getReq)
	if getW.Code != http.StatusOK {
		t.Errorf("AC-6: GET hochfügen expected 200, got %d: %s", getW.Code, getW.Body.String())
	}

	putBody := `{"id":"hochfügen","name":"Hochfügen (aktualisiert)","lat":47.35,"lon":11.86}`
	putReq := httptest.NewRequest(http.MethodPut, "/api/locations/"+id, strings.NewReader(putBody))
	putReq = withUserCtx(putReq, "henning")
	putW := httptest.NewRecorder()
	router.ServeHTTP(putW, putReq)
	if putW.Code != http.StatusOK {
		t.Errorf("AC-6: PUT hochfügen expected 200, got %d: %s", putW.Code, putW.Body.String())
	}
	var updated model.Location
	if err := json.Unmarshal(putW.Body.Bytes(), &updated); err != nil {
		t.Fatalf("AC-6: decode PUT response: %v", err)
	}
	if updated.Name != "Hochfügen (aktualisiert)" {
		t.Errorf("AC-6: expected updated name after PUT, got %q", updated.Name)
	}

	delReq := httptest.NewRequest(http.MethodDelete, "/api/locations/"+id, nil)
	delReq = withUserCtx(delReq, "henning")
	delW := httptest.NewRecorder()
	router.ServeHTTP(delW, delReq)
	if delW.Code != http.StatusNoContent {
		t.Errorf("AC-6: DELETE hochfügen expected 204, got %d: %s", delW.Code, delW.Body.String())
	}
	loc, err := base.WithUser("henning").LoadLocation(id)
	if err != nil {
		t.Errorf("AC-6: LoadLocation after delete: unexpected err %v", err)
	}
	if loc != nil {
		t.Error("AC-6: hochfügen sollte nach DELETE nicht mehr existieren")
	}
}

// -----------------------------------------------------------------------
// AC-7 — Zwei-Nutzer-Nachweis (ADR-0003), rekursiver Verzeichnis-Diff
// -----------------------------------------------------------------------

// snapshotDir liest alle Dateien unter dir rekursiv (relativer Pfad ->
// Inhalt) — Grundlage fuer den in AC-7 verlangten Verzeichnis-Diff.
func snapshotDir(t *testing.T, dir string) map[string]string {
	t.Helper()
	snap := map[string]string{}
	_ = filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		data, rerr := os.ReadFile(path)
		if rerr != nil {
			return nil
		}
		rel, relErr := filepath.Rel(dir, path)
		if relErr != nil {
			rel = path
		}
		snap[rel] = string(data)
		return nil
	})
	return snap
}

// AC-7: Nutzer "alice" fuehrt ALLE in AC-1 bis AC-5 verwendeten Angriffe
// aus; Bobs kompletter Nutzerordner muss danach (rekursiver Diff) exakt dem
// Ausgangszustand entsprechen. Die AC-1/AC-2-Body-Angriffe sind die einzigen
// mit echtem Fremdzugriffs-Potenzial (s. Kommentar am Dateianfang) — sie
// tragen hier das eigentliche Gewicht des Nachweises.
func TestTwoRealUsers_AllEntityAttacks_NeverTouchSecondUsersDirectory_AC7(t *testing.T) {
	base, _, _ := seedRealBobForHandler(t)
	router := entityTestRouter(base)
	bobDir := base.UserDir("bob")
	before := snapshotDir(t, bobDir)
	if len(before) == 0 {
		t.Fatal("AC-7 Setup-Invariante verletzt: Bobs Verzeichnis muesste mindestens user.json enthalten")
	}

	attacks := []struct {
		name, method, path, body string
	}{
		{"CreateTrip-body-attack", http.MethodPost, "/api/trips", `{"id":"../../bob/user","name":"x"}`},
		{"CreateLocation-body-attack", http.MethodPost, "/api/locations", `{"id":"../../bob/user","name":"x","lat":1,"lon":1}`},
		{"PutTrip-dot", http.MethodPut, "/api/trips/.", `{"name":"x"}`},
		{"PatchTripState-dot", http.MethodPatch, "/api/trips/./state", `{"paused":true}`},
		{"DeleteTrip-dot", http.MethodDelete, "/api/trips/.", ""},
		{"PutLocation-dot", http.MethodPut, "/api/locations/.", `{"id":".","name":"x","lat":1,"lon":1}`},
		{"PatchLocation-dot", http.MethodPatch, "/api/locations/.", `{"group_id":"g"}`},
		{"DeleteLocation-dot", http.MethodDelete, "/api/locations/.", ""},
		{"PutComparePreset-dot", http.MethodPut, "/api/compare/presets/.", `{}`},
		{"PatchComparePresetState-dot", http.MethodPatch, "/api/compare/presets/./state", `{"archived":true}`},
		{"DeleteComparePreset-dot", http.MethodDelete, "/api/compare/presets/.", ""},
	}

	for _, a := range attacks {
		var req *http.Request
		if a.body != "" {
			req = httptest.NewRequest(a.method, a.path, strings.NewReader(a.body))
		} else {
			req = httptest.NewRequest(a.method, a.path, nil)
		}
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		t.Logf("AC-7 %s -> status=%d", a.name, w.Code)
	}

	after := snapshotDir(t, bobDir)
	if len(before) != len(after) {
		t.Fatalf("AC-7: Anzahl der Dateien in Bobs Verzeichnis hat sich geaendert: vorher=%d nachher=%d", len(before), len(after))
	}
	for rel, content := range before {
		if after[rel] != content {
			t.Errorf("AC-7: Datei %q in Bobs Verzeichnis wurde durch einen Angriff unter Alices Session veraendert", rel)
		}
	}
}

// -----------------------------------------------------------------------
// AC-11 — URL-kodierter Trenner im ID-Pfadsegment (empirisch gemessen)
// -----------------------------------------------------------------------

// AC-11 ist ein REGRESSIONSWAECHTER, keine RED-erzeugende Sicherheits-AC:
// empirisch mit chi v5 gegen den unveraenderten Produktivcode gemessen
// (siehe Bericht an den Team-Lead fuer die Rohbelege):
//   - unkodiert ("../../bob/user"): chi matcht die Route NICHT (zu viele
//     Pfadsegmente fuer das Ein-Segment-Muster {id}) -> 404 VOM ROUTER,
//     Handler wird nicht erreicht.
//   - prozent-kodiert ("..%2F..%2Fbob%2Fuser"): Route matcht (EIN Segment),
//     aber chi.URLParam liefert den Wert weiterhin KODIERT ("..%2F..%2F...")
//     zurueck — chi dekodiert %2F nicht selbst. filepath.Join(dir, id+".json")
//     erhaelt dadurch NIE einen echten Trenner und bleibt im eigenen
//     Verzeichnis.
// Beide Wege sind also bereits heute sicher gegen Fremdzugriff — dieser
// Test ist ein Regressions-/Verteidigungsnachweis (er waere unabhaengig von
// ValidEntityID bereits heute gruen), keine RED-erzeugende Pruefung. Das
// AC deckt trotzdem das beobachtbare Ergebnis "kein fremder Dateizugriff"
// fuer beide Faelle ab, wie von der Spec verlangt.
func TestURLEncodedSeparatorInPathID_NoForeignFileAccess_AC11(t *testing.T) {
	const encoded = "..%2F..%2Fbob%2Fuser"

	t.Run("Trip_DELETE_encoded", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/trips/"+encoded, nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		t.Logf("AC-11 Trip DELETE mit %%2F-kodierter ID: status=%d body=%q", w.Code, w.Body.String())
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("Location_DELETE_encoded", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/locations/"+encoded, nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		t.Logf("AC-11 Location DELETE mit %%2F-kodierter ID: status=%d body=%q", w.Code, w.Body.String())
		assertBobUnchanged(t, bobFile, before)
	})

	t.Run("Trip_DELETE_unencoded_blocked_by_router", func(t *testing.T) {
		base, bobFile, before := seedRealBobForHandler(t)
		router := entityTestRouter(base)
		req := httptest.NewRequest(http.MethodDelete, "/api/trips/../../bob/user", nil)
		req = withUserCtx(req, "alice")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusNotFound {
			t.Errorf("AC-11: unkodiertes '../../bob/user' im Pfad erwartet 404 (Router-Mismatch), bekam %d: %s", w.Code, w.Body.String())
		}
		assertBobUnchanged(t, bobFile, before)
	})
}
