package handler

// Kennungs-Eindeutigkeit Trip / Ortsvergleich (Issue #2359, Epic #2507).
// Spec: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
//
// Trips und Ortsvergleiche liegen in derselben Ablage
// (data/users/<uid>/briefings/<id>.json, ADR-0023) und teilen einen
// Kennungsraum. Diese Datei prueft das Verhalten ueber die echten Handler auf
// einem t.TempDir()-Store — ohne Attrappe, Daten ueber Produktpfade
// (SaveComparePreset/SaveTrip/POST). Sie kompiliert gegen den heutigen Code;
// Tests, die neue Symbole brauchen (ErrKindConflict, writeSaveError, Naht
// newComparePresetID), stehen in id_eindeutigkeit_sentinel_test.go.
//
// Hinweis Quote (#2482): der Test-Router hat keine Policy-Middleware und es
// gibt keine user.json -> jeder Nutzer ist "free" (3 aktive Trips). Ausser in
// AC-5 bleibt jeder Nutzer unter dieser Grenze.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// idEindTripBody ist ein gueltiger POST-/api/trips-Rumpf (validateTrip-fest).
func idEindTripBody(id, name string) string {
	return `{"id":"` + id + `","name":"` + name + `","stages":[{"id":"S1","name":"Tag 1","date":"2026-05-01",` +
		`"waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
}

// idEindSeedPreset legt einen Ortsvergleich ueber den Produktpfad an.
func idEindSeedPreset(t *testing.T, s *store.Store, uid, id string) {
	t.Helper()
	if err := s.WithUser(uid).SaveComparePreset(quotePreset(uid, id)); err != nil {
		t.Fatalf("SaveComparePreset(%s/%s): %v", uid, id, err)
	}
}

// idEindSeedTrip legt einen Trip ueber den Produktpfad an.
func idEindSeedTrip(t *testing.T, s *store.Store, uid, id, name string) {
	t.Helper()
	trip := model.Trip{
		ID: id, Name: name,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	if err := s.WithUser(uid).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip(%s/%s): %v", uid, id, err)
	}
}

func idEindPath(s *store.Store, uid, id string) string {
	return filepath.Join(s.WithUser(uid).BriefingsDir(), id+".json")
}

func idEindBytes(t *testing.T, s *store.Store, uid, id string) []byte {
	t.Helper()
	b, err := os.ReadFile(idEindPath(s, uid, id))
	if err != nil {
		t.Fatalf("Datei %s/%s nicht lesbar: %v", uid, id, err)
	}
	return b
}

// idEindErr dekodiert den JSON-Fehlerrumpf (error/detail).
func idEindErr(t *testing.T, w *httptest.ResponseRecorder) (code, detail string) {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		return "", ""
	}
	c, _ := m["error"].(string)
	d, _ := m["detail"].(string)
	return c, d
}

// idEindAssertIDConflict prueft den Fehlervertrag 409 id_conflict + deutsches detail.
func idEindAssertIDConflict(t *testing.T, w *httptest.ResponseRecorder) {
	t.Helper()
	if w.Code != http.StatusConflict {
		t.Errorf("Status: erwartet 409, bekommen %d (Body %s)", w.Code, w.Body.String())
	}
	code, detail := idEindErr(t, w)
	if code != "id_conflict" {
		t.Errorf(`error: erwartet "id_conflict", bekommen %q`, code)
	}
	if strings.TrimSpace(detail) == "" || !strings.Contains(detail, "Ortsvergleich") {
		t.Errorf("detail: erwartet deutschen Text mit \"Ortsvergleich\", bekommen %q", detail)
	}
}

// idEindTripVorabDetail ist der Spec-Wortlaut (AC-1/AC-9) fuer den Nutzerpfad
// POST /api/trips. Der neutrale Text des Store-Waechters (writeSaveError)
// genuegt dort NICHT — sonst bliebe ein entfernter Vorab-Check unbemerkt.
const idEindTripVorabDetail = "Ein Ortsvergleich trägt bereits diese Kennung — bitte anderen Namen wählen."

// idEindAssertTripVorabConflict prueft 409 id_conflict mit dem EXAKTEN
// Spec-Text des Handler-Vorab-Checks in POST /api/trips.
func idEindAssertTripVorabConflict(t *testing.T, w *httptest.ResponseRecorder) {
	t.Helper()
	idEindAssertIDConflict(t, w)
	if _, detail := idEindErr(t, w); detail != idEindTripVorabDetail {
		t.Errorf("detail: erwartet exakt %q (Vorab-Check), bekommen %q", idEindTripVorabDetail, detail)
	}
}

func idEindTripCount(t *testing.T, s *store.Store, uid string) int {
	t.Helper()
	trips, err := s.WithUser(uid).LoadTrips()
	if err != nil {
		t.Fatalf("LoadTrips(%s): %v", uid, err)
	}
	return len(trips)
}

// AC-1: POST /api/trips mit der Kennung eines eigenen Ortsvergleichs -> 409,
// der Ortsvergleich bleibt byte-gleich, kein neuer Trip.
func TestIdEindeutigkeit_TripAnlage_KennungVonOrtsvergleich_409_VergleichUnveraendert(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	idEindSeedPreset(t, s, uid, "x")
	vorher := idEindBytes(t, s, uid, "x")
	vorherPreset, err := s.WithUser(uid).LoadComparePreset("x")
	if err != nil || vorherPreset == nil {
		t.Fatalf("Vorbedingung: Ortsvergleich x nicht ladbar (%v)", err)
	}
	if n := idEindTripCount(t, s, uid); n != 0 {
		t.Fatalf("Vorbedingung: erwartet 0 Trips, bekommen %d", n)
	}

	w := doReq(etagRouter(s), http.MethodPost, "/api/trips", idEindTripBody("x", "Kollision"), "", uid)

	idEindAssertTripVorabConflict(t, w)
	if nachher := idEindBytes(t, s, uid, "x"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Ortsvergleichs-Datei wurde veraendert (stiller Datenverlust):\nvorher:  %s\nnachher: %s", vorher, nachher)
	}
	nachPreset, err := s.WithUser(uid).LoadComparePreset("x")
	if err != nil || nachPreset == nil {
		t.Errorf("Ortsvergleich x nach dem POST nicht mehr ladbar (err=%v, preset=%v)", err, nachPreset)
	} else if nachPreset.Name != vorherPreset.Name {
		t.Errorf("Ortsvergleich-Name veraendert: %q -> %q", vorherPreset.Name, nachPreset.Name)
	}
	if n := idEindTripCount(t, s, uid); n != 0 {
		t.Errorf("LoadTrips: erwartet 0 Trips, bekommen %d (Trip hat den Ortsvergleich ersetzt)", n)
	}
}

// AC-2: Mandantentrennung — B darf x frei anlegen, A (Besitzer des
// Ortsvergleichs x) bekommt 409.
func TestIdEindeutigkeit_ZweiNutzer_FremderNutzerFrei_BesitzerKonflikt(t *testing.T) {
	s := newTestStore(t)
	const a, b = "alice", "bob"
	idEindSeedPreset(t, s, a, "x")
	vorherA := idEindBytes(t, s, a, "x")
	r := etagRouter(s)

	t.Run("B_bekommt_201", func(t *testing.T) {
		w := doReq(r, http.MethodPost, "/api/trips", idEindTripBody("x", "Bobs Trip"), "", b)
		if w.Code != http.StatusCreated {
			t.Errorf("B: erwartet 201, bekommen %d (Body %s)", w.Code, w.Body.String())
		}
		trip, err := s.WithUser(b).LoadTrip("x")
		if err != nil || trip == nil || trip.Name != "Bobs Trip" {
			t.Errorf("B: eigener Trip x fehlt (err=%v, trip=%v)", err, trip)
		}
		if nachher := idEindBytes(t, s, a, "x"); !bytes.Equal(vorherA, nachher) {
			t.Errorf("B's POST hat A's Ortsvergleich veraendert")
		}
		if p, _ := s.WithUser(b).LoadComparePreset("x"); p != nil {
			t.Errorf("B: unerwarteter Ortsvergleich x im Konto von B")
		}
	})

	t.Run("A_bekommt_409", func(t *testing.T) {
		w := doReq(r, http.MethodPost, "/api/trips", idEindTripBody("x", "Alices Trip"), "", a)
		idEindAssertTripVorabConflict(t, w)
		if nachher := idEindBytes(t, s, a, "x"); !bytes.Equal(vorherA, nachher) {
			t.Errorf("A's Ortsvergleich x wurde durch A's Trip-POST ueberschrieben")
		}
		if n := idEindTripCount(t, s, a); n != 0 {
			t.Errorf("A: erwartet 0 Trips, bekommen %d", n)
		}
		trip, _ := s.WithUser(b).LoadTrip("x")
		if trip == nil || trip.Name != "Bobs Trip" {
			t.Errorf("A's POST hat B's Trip beruehrt (trip=%v)", trip)
		}
	})
}

// AC-3: Upsert der eigenen Art bleibt frei — auch fuer eine Alt-Datei ohne kind.
func TestIdEindeutigkeit_TripUpsert_EigeneArt_Bleibt201(t *testing.T) {
	const uid = "alice"

	t.Run("kind_route", func(t *testing.T) {
		s := newTestStore(t)
		idEindSeedTrip(t, s, uid, "t1", "Alt")
		w := doReq(etagRouter(s), http.MethodPost, "/api/trips", idEindTripBody("t1", "Neu"), "", uid)
		if w.Code != http.StatusCreated {
			t.Fatalf("erwartet 201, bekommen %d (Body %s)", w.Code, w.Body.String())
		}
		trip, err := s.WithUser(uid).LoadTrip("t1")
		if err != nil || trip == nil || trip.Name != "Neu" {
			t.Errorf("Trip t1 nicht aktualisiert (err=%v, trip=%v)", err, trip)
		}
	})

	t.Run("altdatei_ohne_kind", func(t *testing.T) {
		s := newTestStore(t)
		idEindSeedTrip(t, s, uid, "t1", "Alt")
		// Alt-Datei herstellen: Produktpfad-Datei laden, kind entfernen.
		pfad := idEindPath(s, uid, "t1")
		var m map[string]interface{}
		if err := json.Unmarshal(idEindBytes(t, s, uid, "t1"), &m); err != nil {
			t.Fatalf("Trip-Datei nicht als JSON lesbar: %v", err)
		}
		delete(m, "kind")
		roh, err := json.MarshalIndent(m, "", "  ")
		if err != nil {
			t.Fatalf("Marshal: %v", err)
		}
		if err := os.WriteFile(pfad, roh, 0644); err != nil {
			t.Fatalf("WriteFile: %v", err)
		}
		var probe map[string]interface{}
		_ = json.Unmarshal(idEindBytes(t, s, uid, "t1"), &probe)
		if _, hat := probe["kind"]; hat {
			t.Fatalf("Vorbedingung: Alt-Datei traegt noch ein kind-Feld")
		}

		w := doReq(etagRouter(s), http.MethodPost, "/api/trips", idEindTripBody("t1", "Neu"), "", uid)
		if w.Code != http.StatusCreated {
			t.Fatalf("erwartet 201, bekommen %d (Body %s)", w.Code, w.Body.String())
		}
		trip, err := s.WithUser(uid).LoadTrip("t1")
		if err != nil || trip == nil || trip.Name != "Neu" {
			t.Errorf("Alt-Trip t1 nicht aktualisiert (err=%v, trip=%v)", err, trip)
		}
	})
}

// AC-5: Kollisionspruefung laeuft VOR der Quote — am Limit lautet die Antwort
// id_conflict, nicht quota_exceeded.
func TestIdEindeutigkeit_TripAnlage_AmLimit_KollisionVorQuote(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	quoteTier(t, s, uid, "free")
	quoteSeedTrips(t, s, uid, 3, 0)
	idEindSeedPreset(t, s, uid, "x")
	vorher := idEindBytes(t, s, uid, "x")
	r := etagRouter(s)

	// Kontrolle: das Limit ist wirklich erreicht (freie Kennung -> Quote).
	kontrolle := doReq(r, http.MethodPost, "/api/trips", idEindTripBody("frei", "Frei"), "", uid)
	if code, _ := idEindErr(t, kontrolle); kontrolle.Code != http.StatusConflict || code != "quota_exceeded" {
		t.Fatalf("Vorbedingung: erwartet 409 quota_exceeded fuer freie Kennung, bekommen %d %q", kontrolle.Code, code)
	}

	w := doReq(r, http.MethodPost, "/api/trips", idEindTripBody("x", "Kollision"), "", uid)
	idEindAssertTripVorabConflict(t, w)
	if nachher := idEindBytes(t, s, uid, "x"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Ortsvergleich x wurde veraendert")
	}
}

// AC-7: Ein fremder Stempel (ETag der anderen Art) fuehrt in beiden
// Richtungen zu 404, beide Dateien bleiben byte-gleich.
func TestIdEindeutigkeit_PutMitFremdemStempel_404_BeideUnveraendert(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	idEindSeedPreset(t, s, uid, "c1")
	idEindSeedTrip(t, s, uid, "t1", "Trip 1")
	tripR := etagRouter(s)
	cmpR := comparePresetEtagRouter(s)

	etagC1 := mustETag(t, doReq(cmpR, http.MethodGet, "/api/compare/presets/c1", "", "", uid))
	etagT1 := mustETag(t, doReq(tripR, http.MethodGet, "/api/trips/t1", "", "", uid))
	vorC1 := idEindBytes(t, s, uid, "c1")
	vorT1 := idEindBytes(t, s, uid, "t1")

	t.Run("trip_put_auf_vergleich", func(t *testing.T) {
		w := doReq(tripR, http.MethodPut, "/api/trips/c1", `{"name":"Fremd"}`, etagC1, uid)
		if w.Code != http.StatusNotFound {
			t.Errorf("erwartet 404, bekommen %d (Body %s)", w.Code, w.Body.String())
		}
		if code, _ := idEindErr(t, w); code != "not_found" {
			t.Errorf(`error: erwartet "not_found", bekommen %q`, code)
		}
	})
	t.Run("vergleich_put_auf_trip", func(t *testing.T) {
		w := doReq(cmpR, http.MethodPut, "/api/compare/presets/t1", comparePresetPutBody("Fremd"), etagT1, uid)
		if w.Code != http.StatusNotFound {
			t.Errorf("erwartet 404, bekommen %d (Body %s)", w.Code, w.Body.String())
		}
		if code, _ := idEindErr(t, w); code != "not_found" {
			t.Errorf(`error: erwartet "not_found", bekommen %q`, code)
		}
	})

	if !bytes.Equal(vorC1, idEindBytes(t, s, uid, "c1")) {
		t.Errorf("Ortsvergleich c1 wurde veraendert")
	}
	if !bytes.Equal(vorT1, idEindBytes(t, s, uid, "t1")) {
		t.Errorf("Trip t1 wurde veraendert")
	}
}

// Vorbedingung fuer AC-8 (Sentinel-Datei): der dort verwendete Anlage-Rumpf
// ist gueltig — sonst scheiterte AC-8 spaeter an 400 statt am Konflikt.
func TestIdEindeutigkeit_CompareAnlage_RumpfGueltig_201(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	w := doReq(comparePresetEtagRouter(s), http.MethodPost, "/api/compare/presets", comparePresetPutBody("Probe"), "", uid)
	if w.Code != http.StatusCreated {
		t.Fatalf("erwartet 201, bekommen %d (Body %s)", w.Code, w.Body.String())
	}
	var p model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &p); err != nil || !strings.HasPrefix(p.ID, "cp-") {
		t.Errorf("Anlage-Antwort ohne cp-Kennung (err=%v, id=%q)", err, p.ID)
	}
}
