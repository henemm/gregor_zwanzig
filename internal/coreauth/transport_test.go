// TDD-RED fuer Issue #2142 Scheibe 1 (AC-2, Test 5): der umhuellende
// Auth-Transport setzt X-GZ-Core-Auth ausschliesslich bei Anfragen an Host UND
// Port aus cfg.PythonCoreURL — an jedes andere Ziel darf das Geheimnis nicht
// mitgehen (Open-Meteo, Google Maps, Komoot, BetterStack).
//
// Gemessen wird am Empfaenger, nicht an der Funktion: die Ziele sind echte
// httptest.Server, die den tatsaechlich eingetroffenen Header festhalten. Fuer
// den wirklich fremden Host (api.open-meteo.com) kann es keinen erreichbaren
// Server geben; dort haengt der Test — Bauform aus internal/egress/guard_test.go
// — einen Sentinel UNTER den Waechter, der den Request vor dem Netz abfaengt
// und seine Header protokolliert.
package coreauth

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

const testCoreSecret = "core-shared-secret-fuer-tests-0123456789"

// captured haelt fest, was am Ziel-Server tatsaechlich ankam.
type captured struct {
	hits   int
	header string
}

func newCapturingServer(t *testing.T, c *captured) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c.hits++
		c.header = r.Header.Get("X-GZ-Core-Auth")
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)
	return srv
}

// installForTest installiert den Waechter und raeumt den globalen
// Transport-Patch am Testende vollstaendig ab — sonst leckt er in fremde
// Testdateien desselben Pakets.
func installForTest(t *testing.T, cfg *config.Config) {
	t.Helper()
	orig := http.DefaultTransport
	Install(cfg)
	t.Cleanup(func() {
		Uninstall()
		http.DefaultTransport = orig
	})
}

func mustGet(t *testing.T, url string) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	resp.Body.Close()
}

// Test 5 (AC-2), Teil 1: gleicher Host, ANDERER Port als cfg.PythonCoreURL.
// Positivkontrolle im selben Test: exakt Host+Port aus cfg.PythonCoreURL traegt
// den Header — ohne sie prueft der Negativfall nichts.
func TestCoreAuthTransport_HeaderOnlyForPythonCoreHostAndPort(t *testing.T) {
	var core, otherPort captured
	coreSrv := newCapturingServer(t, &core)
	otherSrv := newCapturingServer(t, &otherPort)

	cfg := &config.Config{PythonCoreURL: coreSrv.URL, CoreSharedSecret: testCoreSecret}
	installForTest(t, cfg)

	mustGet(t, coreSrv.URL+"/config")
	if core.hits != 1 {
		t.Fatalf("Positivkontrolle: Python-Core-Fake wurde nicht erreicht (hits=%d)", core.hits)
	}
	if core.header != testCoreSecret {
		t.Fatalf("am Python-Core erwartet X-GZ-Core-Auth=%q, angekommen %q", testCoreSecret, core.header)
	}

	mustGet(t, otherSrv.URL+"/v1/forecast")
	if otherPort.hits != 1 {
		t.Fatalf("Fremd-Ziel wurde nicht erreicht (hits=%d)", otherPort.hits)
	}
	if otherPort.header != "" {
		t.Fatalf("Geheimnis an fremden Port geleckt: X-GZ-Core-Auth=%q", otherPort.header)
	}
}

var errSentinelReached = errors.New("sentinel: transport reached")

// sentinelTransport faengt jeden Request ab, bevor er das Netz erreicht, und
// protokolliert den Auth-Header je Ziel-URL.
type sentinelTransport struct {
	seen map[string]string
}

func (s *sentinelTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	s.seen[req.URL.String()] = req.Header.Get("X-GZ-Core-Auth")
	return nil, errSentinelReached
}

// Test 5 (AC-2), Teil 2: wirklich FREMDER Host. Positivkontrolle im selben Test
// ist der Python-Core-Host — beide laufen ueber denselben Sentinel, der
// Unterschied liegt also allein am Host-Filter.
func TestCoreAuthTransport_ForeignHostGetsNoHeader(t *testing.T) {
	sentinel := &sentinelTransport{seen: map[string]string{}}
	orig := http.DefaultTransport
	http.DefaultTransport = sentinel

	cfg := &config.Config{PythonCoreURL: "http://127.0.0.1:8000", CoreSharedSecret: testCoreSecret}
	Install(cfg)
	t.Cleanup(func() {
		Uninstall()
		http.DefaultTransport = orig
	})

	const foreignURL = "https://api.open-meteo.com/v1/forecast"
	const coreURL = "http://127.0.0.1:8000/config"
	// Beide Aufrufe enden am Sentinel mit errSentinelReached — gewollt.
	if resp, err := http.Get(foreignURL); err == nil {
		resp.Body.Close()
	}
	if resp, err := http.Get(coreURL); err == nil {
		resp.Body.Close()
	}

	got, seen := sentinel.seen[foreignURL]
	if !seen {
		t.Fatalf("Sentinel hat den Request an %s nie gesehen — Messung ungueltig", foreignURL)
	}
	if got != "" {
		t.Fatalf("Geheimnis an fremden Host geleckt: X-GZ-Core-Auth=%q", got)
	}

	coreGot, coreSeen := sentinel.seen[coreURL]
	if !coreSeen {
		t.Fatalf("Positivkontrolle: Sentinel hat den Request an %s nie gesehen", coreURL)
	}
	if coreGot != testCoreSecret {
		t.Fatalf("Positivkontrolle: am Python-Core erwartet %q, angekommen %q", testCoreSecret, coreGot)
	}
}
