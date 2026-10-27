package store

// Kennungs-Eindeutigkeit — Sentinel-Pruefung (Issue #2359, AC-4).
// Spec: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
//
// Braucht das NEUE Symbol ErrKindConflict und kompiliert deshalb vor der
// Implementierung bewusst NICHT (RED-Signal: Build-Fehler). Helfer stammen aus
// id_eindeutigkeit_test.go (gleiches Paket).

import (
	"errors"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestIdEindeutigkeitSentinel_SaveTripAufVergleich_ErrKindConflict(t *testing.T) {
	s := idEindStore(t)
	if err := s.SaveComparePreset(idEindPreset("x", "Vergleich")); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	trip := idEindTrip("x", "Trip")
	if err := s.SaveTrip(&trip); !errors.Is(err, ErrKindConflict) {
		t.Errorf("SaveTrip auf kind=vergleich: erwartet ErrKindConflict, bekommen %v", err)
	}
}

func TestIdEindeutigkeitSentinel_SaveVergleichAufTrip_ErrKindConflict(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	if err := s.SaveComparePreset(idEindPreset("t1", "Vergleich")); !errors.Is(err, ErrKindConflict) {
		t.Errorf("SaveComparePreset auf kind=route: erwartet ErrKindConflict, bekommen %v", err)
	}
}

func TestIdEindeutigkeitSentinel_SaveVergleichAufTripAltDatei_ErrKindConflict(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	idEindKindEntfernen(t, s, "t1")
	if err := s.SaveComparePreset(idEindPreset("t1", "Vergleich")); !errors.Is(err, ErrKindConflict) {
		t.Errorf("SaveComparePreset auf Trip-Alt-Datei: erwartet ErrKindConflict, bekommen %v", err)
	}
}

func TestIdEindeutigkeitSentinel_SaveComparePresets_Konflikt_ErrKindConflict(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	err := s.SaveComparePresets([]model.ComparePreset{idEindPreset("t1", "Kollision")})
	if !errors.Is(err, ErrKindConflict) {
		t.Errorf("SaveComparePresets mit Kollision: erwartet ErrKindConflict, bekommen %v", err)
	}
}
