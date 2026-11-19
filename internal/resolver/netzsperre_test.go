//go:build !integration

// Netzsperre fuer die Kern-Schicht des Resolver-Pakets (Issue #3115,
// ADR-0094): Ohne Build-Tag darf kein Test dieses Pakets einen Host
// ausserhalb von Loopback erreichen. Die Sperre gilt fuer das ganze
// Testbinary (package resolver und resolver_test) und wirkt an beiden
// Abrufwegen des Pakets:
//
//   - Link-Client (safefetch.go, ohne Umgebungs-Proxy): dialIPAllowed wird
//     auf "nichts erlaubt" gesetzt. Tests, die Loopback brauchen, oeffnen es
//     gezielt mit ErlaubeLoopbackVerbindung; die Abschottungstests erwarten
//     ohne diesen Hebel "kein Abruf" und bleiben dadurch gueltig.
//   - Anbieter-Abrufe ueber http.DefaultTransport (Komoot, Nominatim,
//     Hoehe): ein umhuellender RoundTripper laesst nur 127.0.0.1, ::1 und
//     localhost durch. Jeder andere Versuch wird abgelehnt UND vermerkt;
//     am Ende macht TestMain den Lauf rot, auch wenn der aufrufende Code den
//     Fehler still schluckt (z. B. der Hoehen-Nachschlag).
//
// Eine Proxy-Sperre (HTTPS_PROXY=127.0.0.1:9) genuegt nicht, weil der
// Link-Client bewusst keinen Umgebungs-Proxy nutzt (ADR-0114).
// Live-Tests (//go:build integration) sind von dieser Datei ausgenommen.
package resolver

import (
	"fmt"
	"net/http"
	"net/netip"
	"os"
	"strings"
	"sync"
	"testing"
)

type netzsperreTransport struct{ next http.RoundTripper }

var (
	netzsperreMu        sync.Mutex
	netzsperreVersuche  []string
	netzsperreFehlerTag = "netzsperre (#3115)"
)

func istLoopbackHost(host string) bool {
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip, err := netip.ParseAddr(strings.Trim(host, "[]"))
	return err == nil && ip.Unmap().IsLoopback()
}

func (n netzsperreTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	host := req.URL.Hostname()
	if istLoopbackHost(host) {
		return n.next.RoundTrip(req)
	}
	netzsperreMu.Lock()
	netzsperreVersuche = append(netzsperreVersuche, req.URL.Scheme+"://"+req.URL.Host+req.URL.Path)
	netzsperreMu.Unlock()
	return nil, fmt.Errorf("%s: Abruf an %q ausserhalb Loopback im Kern-Test verboten", netzsperreFehlerTag, host)
}

func vergissNetzsperreVersuch(prefix string) {
	netzsperreMu.Lock()
	defer netzsperreMu.Unlock()
	rest := netzsperreVersuche[:0]
	for _, v := range netzsperreVersuche {
		if !strings.HasPrefix(v, prefix) {
			rest = append(rest, v)
		}
	}
	netzsperreVersuche = rest
}

func TestMain(m *testing.M) {
	dialIPAllowed = func(netip.Addr) bool { return false }
	http.DefaultTransport = netzsperreTransport{next: http.DefaultTransport}

	code := m.Run()

	netzsperreMu.Lock()
	versuche := append([]string(nil), netzsperreVersuche...)
	netzsperreMu.Unlock()
	if len(versuche) > 0 {
		fmt.Fprintf(os.Stderr, "FAIL: %s: %d Netzabruf(e) ausserhalb Loopback im Kern-Test:\n", netzsperreFehlerTag, len(versuche))
		for _, v := range versuche {
			fmt.Fprintf(os.Stderr, "  - %s\n", v)
		}
		if code == 0 {
			code = 1
		}
	}
	os.Exit(code)
}

// Die Sperre selbst ist bewacht: ein Abruf an einen fremden Host scheitert
// ueber den Standard-Client, ohne den Host zu erreichen.
func TestNetzsperre_StandardClientBlocktFremdenHost(t *testing.T) {
	const ziel = "http://netzsperre-probe.example/"
	t.Cleanup(func() { vergissNetzsperreVersuch(ziel) })
	_, err := http.Get(ziel)
	if err == nil || !strings.Contains(err.Error(), netzsperreFehlerTag) {
		t.Fatalf("Abruf an fremden Host muss von der Netzsperre abgelehnt werden, bekam err=%v", err)
	}
	netzsperreMu.Lock()
	gefunden := false
	for _, v := range netzsperreVersuche {
		if strings.HasPrefix(v, ziel) {
			gefunden = true
		}
	}
	netzsperreMu.Unlock()
	if !gefunden {
		t.Fatal("abgelehnter Abruf muss vermerkt werden, sonst bleibt ein still geschluckter Netzabruf unbemerkt")
	}
}

// Der Link-Client verbindet unter der Sperre zu keiner Adresse, auch nicht zu
// oeffentlichen.
func TestNetzsperre_LinkClientVerbindetNirgendwohin(t *testing.T) {
	for _, s := range []string{"8.8.8.8", "2001:4860:4860::8888", "127.0.0.1"} {
		if dialIPAllowed(netip.MustParseAddr(s)) {
			t.Errorf("dialIPAllowed(%s) = true unter der Netzsperre, erwartet false", s)
		}
	}
}

// Loopback bleibt ueber den Standard-Client erreichbar (Fixture-Server).
func TestNetzsperre_LoopbackBleibtErreichbar(t *testing.T) {
	for _, h := range []string{"127.0.0.1", "::1", "[::1]", "localhost", "LOCALHOST"} {
		if !istLoopbackHost(h) {
			t.Errorf("istLoopbackHost(%q) = false, erwartet true", h)
		}
	}
	for _, h := range []string{"www.komoot.com", "nominatim.openstreetmap.org", "10.0.0.1", "localhost.example", ""} {
		if istLoopbackHost(h) {
			t.Errorf("istLoopbackHost(%q) = true, erwartet false", h)
		}
	}
}
