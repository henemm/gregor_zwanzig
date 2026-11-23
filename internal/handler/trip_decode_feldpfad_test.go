// Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-1/AC-2):
// Die 422-Erkennung fuer einen falschen Typ bei stages[].grundtempo_kmh haengt
// nicht von der Go-Version ab. Go 1.25 meldet den Feldpfad als
// "stages.grundtempo_kmh", Go 1.27 mit Array-Index als "stages.1.grundtempo_kmh".
// Beide Formen werden hier direkt gebaut, damit der Nachweis auch unter der
// CI-Version 1.25 die 1.27-Form abdeckt.
package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
)

func decodeFehlerStatus(t *testing.T, feld string) int {
	t.Helper()
	err := fmt.Errorf("dekodieren: %w", &json.UnmarshalTypeError{
		Value: "string",
		Type:  reflect.TypeOf(float64(0)),
		Field: feld,
	})
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodPut, "/api/trips/t1", nil)
	writeTripDecodeError(w, r, err)
	return w.Code
}

// AC-1: Feldpfad mit und ohne Array-Index -> 422.
func TestTripDecodeFeldpfad3294_GrundtempoJeGoVersion422(t *testing.T) {
	for _, feld := range []string{
		"stages.grundtempo_kmh",    // Go 1.25
		"stages.1.grundtempo_kmh",  // Go 1.27
		"stages.12.grundtempo_kmh", // mehrstelliger Index
	} {
		if got := decodeFehlerStatus(t, feld); got != http.StatusUnprocessableEntity {
			t.Errorf("Feld %q: erwartet 422, bekommen %d", feld, got)
		}
	}
}

// AC-2: andere Dekodierfehler bleiben 400, auch mit Array-Index; ein
// grundtempo_kmh ausserhalb der Etappen (Trip-Tempo) ebenso.
func TestTripDecodeFeldpfad3294_AndereFelderBleiben400(t *testing.T) {
	for _, feld := range []string{
		"stages.1.name",
		"stages.name",
		"tempo.grundtempo_kmh",
		"grundtempo_kmh",
		"stages.1.waypoints.2.grundtempo_kmh",
		"stages.x.grundtempo_kmh",
		"",
	} {
		if got := decodeFehlerStatus(t, feld); got != http.StatusBadRequest {
			t.Errorf("Feld %q: erwartet 400, bekommen %d", feld, got)
		}
	}
}
