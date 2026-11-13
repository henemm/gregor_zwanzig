package router

// Issue #2961 (ADR-0117 und Nachtrag): Verdrahtung am ECHTEN Router —
// Mengenbremse fuer GET /api/forecast und Orte-Grenze des Sofortvergleichs.
// Spec docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md

import (
	"fmt"
	"net/http"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/handler"
)

// GET /api/forecast: 60 je Minute je Nutzer; der 61. Aufruf erreicht den Core
// (Kontingent-Reservierung) nicht mehr. Ein zweiter Nutzer ist unberuehrt.
func TestAbrufKontingent_VorhersageMengenbremse60JeMinute(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-vorhersage", "de")
	bert := e.konto(t, "bert-vorhersage", "de")
	pfad := "/api/forecast?lat=47.1&lon=11.1"

	for i := 0; i < handler.BremseAbrufJeMinute; i++ {
		// Der Ersatz-Core erlaubt nichts -> 429 budget_exceeded, nie ein Abruf.
		w := e.rufe(t, http.MethodGet, pfad, nil, anna)
		if strings.Contains(w.Body.String(), "rate_limit_exceeded") {
			t.Fatalf("Aufruf %d vorzeitig gebremst: %s", i+1, w.Body.String())
		}
	}
	vorher := e.core.Load()
	erwarte429(t, e.rufe(t, http.MethodGet, pfad, nil, anna), "abruf")
	if e.core.Load() != vorher {
		t.Fatal("gebremster Vorhersage-Aufruf hat den Core dennoch erreicht")
	}
	if w := e.rufe(t, http.MethodGet, pfad, nil, bert); strings.Contains(w.Body.String(), "rate_limit_exceeded") {
		t.Fatal("zweiter Nutzer wurde von der Bremse des ersten getroffen")
	}
}

// GET /api/compare: mehr Orte als die Orte-Quote (free: 10) -> 422 ohne Core;
// ein zweiter Nutzer mit wenigen Orten kommt durch.
func TestAbrufKontingent_VergleichOrteGrenzeVerdrahtet(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-orte", "de")
	bert := e.konto(t, "bert-orte", "de")
	ids := make([]string, 11)
	for i := range ids {
		ids[i] = fmt.Sprintf("o%d", i)
	}

	vorher := e.core.Load()
	w := e.rufe(t, http.MethodGet, "/api/compare?location_ids="+strings.Join(ids, ","), nil, anna)
	if w.Code != http.StatusUnprocessableEntity || !strings.Contains(w.Body.String(), "limit_exceeded") {
		t.Fatalf("erwartet 422 limit_exceeded, bekommen %d: %s", w.Code, w.Body.String())
	}
	if e.core.Load() != vorher {
		t.Fatal("abgelehnter Vergleich hat den Core dennoch erreicht")
	}
	if w := e.rufe(t, http.MethodGet, "/api/compare?location_ids=a,b", nil, bert); w.Code != http.StatusOK {
		t.Fatalf("zweiter Nutzer: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if e.core.Load() != vorher+1 {
		t.Fatal("erlaubter Vergleich hat den Core nicht erreicht")
	}
}
