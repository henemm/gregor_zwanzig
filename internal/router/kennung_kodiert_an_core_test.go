package router

// Issue #2961 (ADR-0114 Punkt 2, Spec AC-6 bis AC-8): eine Kennung erreicht
// den Python-Core nur als kodiertes Pfadsegment; Kennungen mit Query-,
// Fragment- oder Kodierungszeichen werden vorab mit 400 abgewiesen — auf den
// kind-neutralen UND den Alt-Routen. Gemessen am Ersatz-Core: er sieht nie
// eine fremde user_id.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// rufeRoh schickt den Pfad unveraendert (Prozent-Kodierung bleibt erhalten).
func (e *bremsUmgebung) rufeRoh(t *testing.T, method, rohPfad string, c *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, rohPfad, strings.NewReader("{}"))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(c)
	w := httptest.NewRecorder()
	e.r.ServeHTTP(w, req)
	return w
}

var kennungsRouten = []struct{ method, vor, nach string }{
	{http.MethodPost, "/api/trips/", "/send"},
	{http.MethodPost, "/api/compare/presets/", "/send"},
	{http.MethodPost, "/api/briefings/", "/send?kind=route"},
	{http.MethodGet, "/api/preview/", "/sms"},
	{http.MethodPost, "/api/trips/", "/alert-preview"},
	{http.MethodPost, "/api/briefings/", "/alert-preview?kind=route"},
	{http.MethodGet, "/api/trips/", "/stages/weather"},
	{http.MethodGet, "/api/_internal/trip/", "/loaded"},
}

func TestKennung_GefaehrlicheZeichenErreichenDenCoreNie(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-kennung", "de")

	for _, roh := range []string{
		"x%3Fuser_id=bert-kennung&z=",
		"x%23frag",
		"x%253Fuser_id=bert-kennung",
		"x%0Auser_id=bert-kennung",
		"..%2Ftrip-reports%3Fuser_id=bert-kennung",
	} {
		for _, rt := range kennungsRouten {
			vorher := e.core.Load()
			w := e.rufeRoh(t, rt.method, rt.vor+roh+rt.nach, anna)
			if w.Code != http.StatusBadRequest && w.Code != http.StatusNotFound {
				t.Errorf("%s %s%s%s: erwartet 400, bekommen %d: %s", rt.method, rt.vor, roh, rt.nach, w.Code, w.Body.String())
			}
			if e.core.Load() != vorher {
				t.Errorf("%s %s%s%s: ungueltige Kennung hat den Core erreicht", rt.method, rt.vor, roh, rt.nach)
			}
		}
	}
	for _, emp := range e.empfang() {
		for _, u := range emp.userIDs {
			if u != "anna-kennung" {
				t.Fatalf("Core sah fremde user_id %q (%s)", u, emp.uri)
			}
		}
	}
}

// Zulaessige Kennungen mit Sonderzeichen (Umlaut, Leerzeichen) kommen als
// genau EIN kodiertes Segment an, mit genau einer user_id — der eigenen.
func TestKennung_WirdKodiertWeitergereicht(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-kodiert", "de")

	for _, rt := range kennungsRouten {
		w := e.rufeRoh(t, rt.method, rt.vor+"m%C3%BChl%20bach"+rt.nach+anhang(rt.nach, "user_id=bert"), anna)
		if w.Code == http.StatusBadRequest {
			t.Fatalf("%s %s: gueltige Kennung abgewiesen: %s", rt.method, rt.vor, w.Body.String())
		}
	}
	emp := e.empfang()
	if len(emp) != len(kennungsRouten) {
		t.Fatalf("Core-Anfragen: %d, erwartet %d", len(emp), len(kennungsRouten))
	}
	for _, x := range emp {
		if !strings.Contains(x.uri, "/m%C3%BChl%20bach/") && !strings.Contains(x.uri, "/m%C3%BChl%20bach?") {
			t.Errorf("Kennung nicht als kodiertes Segment angekommen: %s", x.uri)
		}
		if !strings.Contains(x.path, "/mühl bach") {
			t.Errorf("dekodierter Pfad unerwartet: %s", x.path)
		}
		if len(x.userIDs) != 1 || x.userIDs[0] != "anna-kodiert" {
			t.Errorf("user_id am Core %v, erwartet genau [anna-kodiert] (%s)", x.userIDs, x.uri)
		}
	}
}

func anhang(nach, q string) string {
	if strings.Contains(nach, "?") {
		return "&" + q
	}
	return "?" + q
}
