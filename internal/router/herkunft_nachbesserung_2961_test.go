package router

// Issue #2961 Nachbesserung (Gegenpruefung F4/F5) — Schutzschicht und
// IP-Bremsen ueber den echten Router.

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// M55/M56: fremder Origin wird fuer alle schreibenden Methoden abgewiesen.
func TestHerkunft_AlleSchreibendenMethoden(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "methoden")
	if w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
		contentType: "application/json", cookie: c}); w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Aufbau: Ort anlegen %d %s", w.Code, w.Body.String())
	}
	for _, m := range []string{http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete} {
		pfad := "/api/locations/testort"
		if m == http.MethodPost {
			pfad = "/api/locations"
		}
		w := schicke2961(t, r, anfrage2961{method: m, path: pfad, body: ortRumpf2961, contentType: "application/json",
			header: map[string]string{"Origin": "https://angreifer.example"}, cookie: c})
		if w.Code != http.StatusForbidden || code2961(w) != "origin_forbidden" {
			t.Fatalf("%s %s: erwartet 403 origin_forbidden, bekommen %d %s", m, pfad, w.Code, w.Body.String())
		}
	}
	if w := schicke2961(t, r, anfrage2961{method: http.MethodGet, path: "/api/locations/testort", cookie: c}); w.Code != http.StatusOK {
		t.Fatalf("Ort muss nach abgewiesenem DELETE noch da sein, bekommen %d", w.Code)
	}
}

// M45/M46: Admin-Routen unter /api/scheduler/ und /api/_validator/ sind NICHT
// von der Herkunftspruefung ausgenommen. M43: unangemeldet mit fremdem Origin
// ist die Antwort 403 (Schutzschicht vor der Anmeldepruefung), nicht 401.
func TestHerkunft_KeineAusnahmeFuerAdminUndValidatorPfade(t *testing.T) {
	r, s, secret := schutzRouter2961(t, func(c *config.Config) { c.AdminUserIDs = "chef" })
	c := kontoMitSitzung2961(t, s, secret, "chef")
	fremd := map[string]string{"Origin": "https://angreifer.example"}
	for _, p := range []string{"/api/scheduler/trip-reports", "/api/scheduler/alert-checks", "/api/_validator/compare-email-preview"} {
		for _, mitSitzung := range []bool{true, false} {
			a := anfrage2961{method: http.MethodPost, path: p, body: `{}`, contentType: "application/json", header: fremd}
			if mitSitzung {
				a.cookie = c
			}
			w := schicke2961(t, r, a)
			if w.Code != http.StatusForbidden || code2961(w) != "origin_forbidden" {
				t.Fatalf("%s (Sitzung=%v): erwartet 403 origin_forbidden, bekommen %d %s", p, mitSitzung, w.Code, w.Body.String())
			}
		}
	}
	// Gegenprobe Reihenfolge: ohne Origin und ohne Sitzung → 401.
	if w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
		contentType: "application/json"}); w.Code != http.StatusUnauthorized {
		t.Fatalf("ohne Origin, ohne Sitzung: erwartet 401, bekommen %d", w.Code)
	}
}

// M52: in Produktion wird das http-Schema des eigenen Hosts abgewiesen.
func TestHerkunft_HttpSchemaDesEigenenHostsAbgewiesen(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "schema")
	for _, o := range []string{"http://gregor20.henemm.com", "https://gregor20.henemm.com:8443"} {
		w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
			contentType: "application/json", header: map[string]string{"Origin": o}, cookie: c})
		if w.Code != http.StatusForbidden {
			t.Fatalf("%s: erwartet 403, bekommen %d", o, w.Code)
		}
	}
}

// M48/M58 ueber den Router: chunked Rumpf ohne JSON-Typ → 415; chunked Rumpf
// ueber 1 MB → kein Ort entsteht.
func TestSchutz_ChunkedRumpfUeberRouter(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "chunked")
	chunked := func(body []byte, ct string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/api/locations", nil)
		req.Body = io.NopCloser(bytes.NewReader(body))
		req.ContentLength = -1
		req.TransferEncoding = []string{"chunked"}
		req.Header.Set("Content-Type", ct)
		req.AddCookie(c)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w
	}
	if w := chunked([]byte(ortRumpf2961), "text/plain"); w.Code != http.StatusUnsupportedMediaType {
		t.Fatalf("chunked ohne JSON-Typ: erwartet 415, bekommen %d", w.Code)
	}
	gross := []byte(`{"name":"Gross","lat":1,"lon":1,"elevation_m":1,"x":"` + strings.Repeat("a", 2<<20) + `"}`)
	if w := chunked(gross, "application/json"); w.Code < 400 {
		t.Fatalf("chunked ueber 1 MB: erwartet Fehler, bekommen %d", w.Code)
	}
	if locs, _ := s.WithUser("chunked").LoadLocations(); len(locs) != 0 {
		t.Fatalf("abgebrochener Rumpf darf nichts anlegen, vorhanden: %d", len(locs))
	}
}

// M09b/M10b/M11: die IP-Bremsen haengen an /api/auth/magic-link (5/15 min)
// und /verify (10/15 min); IPv6-Absender eines /64 teilen ein Kontingent.
func TestMagicLink_IPBremsenVerdrahtetUndIPv6Je64(t *testing.T) {
	r, _, _ := schutzRouter2961(t, nil)
	ruf := func(pfad, body, remote string) int {
		req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = remote
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w.Code
	}
	anfrage := `{"email":"ip@beispiel.de"}`
	for i := 0; i < 5; i++ {
		if c := ruf("/api/auth/magic-link", anfrage, "[2001:db8:7:7::"+string(rune('1'+i))+"]:1000"); c != http.StatusOK {
			t.Fatalf("Anforderung %d: erwartet 200, bekommen %d", i+1, c)
		}
	}
	if c := ruf("/api/auth/magic-link", anfrage, "[2001:db8:7:7::ff]:1000"); c != http.StatusTooManyRequests {
		t.Fatalf("6. Anforderung aus demselben /64: erwartet 429, bekommen %d", c)
	}
	if c := ruf("/api/auth/magic-link", anfrage, "[2001:db8:7:8::1]:1000"); c != http.StatusOK {
		t.Fatalf("anderes /64: erwartet 200, bekommen %d", c)
	}
	pruef := `{"email":"ip@beispiel.de","code":"00000000"}`
	for i := 0; i < 10; i++ {
		if c := ruf("/api/auth/magic-link/verify", pruef, "198.51.100.7:1"); c == http.StatusTooManyRequests {
			t.Fatalf("Einloesen %d: zu frueh 429", i+1)
		}
	}
	if c := ruf("/api/auth/magic-link/verify", pruef, "198.51.100.7:1"); c != http.StatusTooManyRequests {
		t.Fatalf("11. Einloesen: erwartet 429, bekommen %d", c)
	}
}
