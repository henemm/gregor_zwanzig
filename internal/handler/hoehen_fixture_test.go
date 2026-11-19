// Hoehen-Nachschlag-Fixture fuer die Handler-Tests (Issue #3158, ADR-0094,
// ADR-0114): ein lokaler Open-Elevation-Nachbau auf Loopback. Der Helfer
// legt fuer die Dauer eines Tests einen umleitenden Transport ueber
// http.DefaultTransport, der nur Anfragen an den exakten Host
// api.open-elevation.com auf den Loopback-Server umschreibt; alles andere
// geht unveraendert an den vorigen Transport (die Netzsperre). Kein
// Laufzeitschalter, nur Testcode. Nicht in t.Parallel-Tests verwenden
// (globaler Zustand). Ohne Build-Tag, damit er auch im integration-Build
// kompiliert.
package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"
)

const hoehenDienstHost = "api.open-elevation.com"

// hoehenFixture merkt sich die beim Nachbau angekommenen locations-Abfragen.
type hoehenFixture struct {
	mu       sync.Mutex
	anfragen []string
}

// locations liefert eine Kopie der angekommenen locations-Abfragen.
func (f *hoehenFixture) locations() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]string(nil), f.anfragen...)
}

type hoehenUmleitung struct {
	ziel *url.URL
	next http.RoundTripper
}

func (u hoehenUmleitung) RoundTrip(req *http.Request) (*http.Response, error) {
	if req.URL.Hostname() != hoehenDienstHost {
		return u.next.RoundTrip(req)
	}
	umgeleitet := req.Clone(req.Context())
	umgeleitet.URL.Scheme = u.ziel.Scheme
	umgeleitet.URL.Host = u.ziel.Host
	umgeleitet.Host = u.ziel.Host
	return u.next.RoundTrip(umgeleitet)
}

// hoehenDienstAuf startet den Open-Elevation-Nachbau mit fester Hoehe und
// leitet api.open-elevation.com fuer die Dauer des Tests dorthin um.
func hoehenDienstAuf(t *testing.T, hoehe float64) *hoehenFixture {
	t.Helper()
	fx := &hoehenFixture{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fx.mu.Lock()
		fx.anfragen = append(fx.anfragen, r.URL.Query().Get("locations"))
		fx.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"results": []map[string]float64{{"elevation": hoehe}},
		})
	}))
	ziel, err := url.Parse(srv.URL)
	if err != nil {
		srv.Close()
		t.Fatalf("Fixture-URL %q nicht lesbar: %v", srv.URL, err)
	}
	vorher := http.DefaultTransport
	http.DefaultTransport = hoehenUmleitung{ziel: ziel, next: vorher}
	t.Cleanup(func() {
		http.DefaultTransport = vorher
		srv.Close()
	})
	return fx
}
