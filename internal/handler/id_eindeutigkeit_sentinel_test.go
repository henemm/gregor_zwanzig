package handler

// Kennungs-Eindeutigkeit — Tests mit neuen Symbolen (Issue #2359, AC-6, AC-8).
// Spec: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
//
// Braucht store.ErrKindConflict, den gemeinsamen Helfer writeSaveError und
// die Test-Naht newComparePresetID als Paket-Variable — kompiliert vor der
// Implementierung bewusst NICHT (RED-Signal: Build-Fehler). Helfer aus
// id_eindeutigkeit_test.go (gleiches Paket). Keine Attrappe: der Sentinel
// stammt aus einem echten SaveTrip auf eine echte Ortsvergleichs-Datei.

import (
	"bytes"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func idEindTripModel(id string) model.Trip {
	return model.Trip{
		ID: id, Name: "Trip " + id,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
}

// AC-6: writeSaveError bildet den ECHTEN Store-Sentinel auf 409 id_conflict ab.
func TestIdEindeutigkeitSentinel_WriteSaveError_KindConflict_409(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"
	idEindSeedPreset(t, s, uid, "x")
	vorher := idEindBytes(t, s, uid, "x")

	trip := idEindTripModel("x")
	err := s.WithUser(uid).SaveTrip(&trip)
	if err == nil {
		t.Fatalf("Vorbedingung: SaveTrip auf Ortsvergleichs-Datei lieferte keinen Fehler")
	}
	if !errors.Is(err, store.ErrKindConflict) {
		t.Fatalf("Vorbedingung: erwartet store.ErrKindConflict, bekommen %v", err)
	}

	w := httptest.NewRecorder()
	writeSaveError(w, err)

	idEindAssertIDConflict(t, w)
	if !bytes.Equal(vorher, idEindBytes(t, s, uid, "x")) {
		t.Errorf("Ortsvergleich x wurde veraendert")
	}
}

// AC-6: jeder andere Save-Fehler bleibt 500 store_error.
func TestIdEindeutigkeitSentinel_WriteSaveError_AndererFehler_500(t *testing.T) {
	w := httptest.NewRecorder()
	writeSaveError(w, errors.New("platte voll"))

	if w.Code != http.StatusInternalServerError {
		t.Errorf("erwartet 500, bekommen %d (Body %s)", w.Code, w.Body.String())
	}
	if code, _ := idEindErr(t, w); code != "store_error" {
		t.Errorf(`error: erwartet "store_error", bekommen %q`, code)
	}
}

// AC-8: Compare-Anlage trifft (per Naht erzwungen) auf eine Trip-Datei ->
// 409 id_conflict statt 500, Trip-Datei byte-gleich, kein neuer Ortsvergleich.
func TestIdEindeutigkeitSentinel_CompareAnlage_TrifftTrip_409(t *testing.T) {
	s := newTestStore(t)
	const uid = "alice"

	anlage := doReq(etagRouter(s), http.MethodPost, "/api/trips", idEindTripBody("t1", "Trip 1"), "", uid)
	if anlage.Code != http.StatusCreated {
		t.Fatalf("Vorbedingung: Trip t1 nicht angelegt (%d %s)", anlage.Code, anlage.Body.String())
	}
	vorher := idEindBytes(t, s, uid, "t1")

	orig := newComparePresetID
	newComparePresetID = func() string { return "t1" }
	t.Cleanup(func() { newComparePresetID = orig })

	w := doReq(comparePresetEtagRouter(s), http.MethodPost, "/api/compare/presets", comparePresetPutBody("Kollision"), "", uid)

	idEindAssertIDConflict(t, w)
	if !bytes.Equal(vorher, idEindBytes(t, s, uid, "t1")) {
		t.Errorf("Trip-Datei t1 wurde von der Compare-Anlage ueberschrieben")
	}
	presets, err := s.WithUser(uid).LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(presets) != 0 {
		t.Errorf("erwartet keinen Ortsvergleich, bekommen %d", len(presets))
	}
}
