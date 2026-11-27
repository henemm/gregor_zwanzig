package router

// Issue #3441 (S5b): Route POST /api/briefings/{id}/test-alert haengt hinter der Mengenbremse
// bremsen.Versand und teilt deren Kontingent mit dem Handversand (Spec feat_3441_test_alarm.md,
// AC-9). Gemessen am ECHTEN Produktions-Router mit zaehlendem Ersatz-Core (Muster
// mengenbremsen_verdrahtung_test.go).

import (
	"net/http"
	"testing"

	"github.com/henemm/gregor-api/internal/handler"
)

func TestTestAlert_RouteErreichtCoreMitAuthNutzer(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-testalarm", "de")

	w := e.rufe(t, http.MethodPost, "/api/briefings/t1/test-alert?kind=route&user_id=bert", nil, anna)
	if w.Code != http.StatusOK {
		t.Fatalf("Status %d, erwartet 200 (body=%s)", w.Code, w.Body.String())
	}
	emp := e.empfang()
	if len(emp) != 1 || emp[0].path != "/api/briefings/t1/test-alert" {
		t.Fatalf("Core-Empfang %+v, erwartet genau /api/briefings/t1/test-alert", emp)
	}
	if len(emp[0].userIDs) != 1 || emp[0].userIDs[0] != "anna-testalarm" {
		t.Fatalf("user_id am Core %v, erwartet [anna-testalarm]", emp[0].userIDs)
	}
}

func TestTestAlert_TeiltDieVersandBremseMitDemHandversand(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-testalarm", "de")
	bert := e.konto(t, "bert-testalarm", "de")

	for i := 0; i < handler.BremseVersandJeStunde; i++ {
		pfad := "/api/briefings/t1/test-alert?kind=route"
		if i%2 == 1 {
			pfad = "/api/briefings/t1/send?kind=route"
		}
		if w := e.rufe(t, http.MethodPost, pfad, nil, anna); w.Code == http.StatusTooManyRequests {
			t.Fatalf("Aufruf %d vorzeitig gebremst", i+1)
		}
	}
	vorher := e.core.Load()
	erwarte429(t, e.rufe(t, http.MethodPost, "/api/briefings/t1/test-alert?kind=vergleich", nil, anna), "versand")
	if e.core.Load() != vorher {
		t.Fatal("gebremster Test-Alarm hat den Core dennoch erreicht")
	}
	if w := e.rufe(t, http.MethodPost, "/api/briefings/t1/test-alert?kind=route", nil, bert); w.Code != http.StatusOK {
		t.Fatalf("zweiter Nutzer: Status %d, erwartet 200", w.Code)
	}
}
