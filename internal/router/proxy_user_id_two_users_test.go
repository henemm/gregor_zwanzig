package router

// TDD RED — Issue #2163 Scheibe 1, AC-13 (Zwei-Nutzer-Test, ADR-0003).
// Spec: docs/specs/modules/auth_haertung_go_2163.md
//
// Ueber den ECHTEN Router (router.New inkl. AuthMiddleware, echte
// gz_session-Cookies) stellt Nutzer A auf jeder der fuenf ProxyHandler-Routen
// eine Anfrage mit user_id=B. Der httptest-Core spiegelt die empfangene
// Roh-Query in seinen Body — nur so ist "Antwort an A gleich der Antwort ohne
// Parameter" eine echte Zusicherung (ein statischer Core waere immer gleich).
//
// Zugesichert: (1) der Core sieht nie ein user_id, (2) Status und Body der
// Antwort an A mit user_id=B sind byte-gleich zur Antwort ohne den Parameter.
// Verglichen werden nur Status und Body (der durchgereichte Date-Header kann
// sich zwischen zwei Aufrufen aendern). Beide Richtungen (alice->bob, bob->alice).
//
// RED-Signal heute: ProxyHandler reicht die Query unveraendert weiter; der Core
// sieht user_id=bob und spiegelt es in die Antwort.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
)

type echoQueryCore struct {
	mu  sync.Mutex
	raw []string
}

func (c *echoQueryCore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	c.raw = append(c.raw, r.URL.RawQuery)
	c.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	b, _ := json.Marshal(map[string]string{"path": r.URL.Path, "seen_query": r.URL.RawQuery})
	w.Write(b)
}

func (c *echoQueryCore) all() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]string(nil), c.raw...)
}

// userIDProxyRouten sind die fuenf ProxyHandler-Routen aus router.go.
var userIDProxyRouten = []string{
	"/api/config",
	"/api/metrics",
	"/api/templates",
	"/api/sms-symbols",
	"/api/compare/metrics",
}

func proxyGet(t *testing.T, r http.Handler, target string, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestProxyRouten_ZweiNutzer_FremdeUserIDErreichtCoreNie_AntwortGleich_AC13(t *testing.T) {
	core := &echoQueryCore{}
	srv := httptest.NewServer(core)
	t.Cleanup(srv.Close)
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, pythonZiel: srv.URL})

	richtungen := []struct{ anfrager, fremd string }{
		{"alice", "bob"},
		{"bob", "alice"},
	}
	for _, pfad := range userIDProxyRouten {
		for _, ri := range richtungen {
			pfad, ri := pfad, ri
			t.Run(pfad+"_"+ri.anfrager+"_fragt_als_"+ri.fremd, func(t *testing.T) {
				cookie := sessionCookieFor(ri.anfrager, secret)

				ohne := proxyGet(t, r, pfad+"?lang=de&q=a+b", cookie)
				mit := proxyGet(t, r, pfad+"?lang=de&user_id="+url.QueryEscape(ri.fremd)+"&q=a+b", cookie)

				if ohne.Code != http.StatusOK {
					t.Fatalf("%s ohne user_id: erwartet 200, bekommen %d: %s", pfad, ohne.Code, ohne.Body.String())
				}
				if mit.Code != ohne.Code {
					t.Errorf("AC-13 %s: Status mit user_id=%s (%d) != ohne (%d)", pfad, ri.fremd, mit.Code, ohne.Code)
				}
				if mit.Body.String() != ohne.Body.String() {
					t.Errorf("AC-13 %s: Antwort an %s mit user_id=%s weicht ab:\n mit:  %s\n ohne: %s",
						pfad, ri.anfrager, ri.fremd, mit.Body.String(), ohne.Body.String())
				}
			})
		}
	}

	gesehen := core.all()
	if len(gesehen) != len(userIDProxyRouten)*len(richtungen)*2 {
		t.Fatalf("Core sah %d Aufrufe, erwartet %d", len(gesehen), len(userIDProxyRouten)*len(richtungen)*2)
	}
	for _, q := range gesehen {
		vals, _ := url.ParseQuery(q)
		if _, ok := vals["user_id"]; ok || strings.Contains(q, "user_id") {
			t.Errorf("AC-13: Core hat user_id gesehen: RawQuery %q", q)
		}
		if q != "lang=de&q=a+b" {
			t.Errorf("AC-13: Rest-Query muss in Reihenfolge und Kodierung erhalten bleiben, Core sah %q", q)
		}
	}
}
