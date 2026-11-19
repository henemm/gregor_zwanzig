// Netzsperre fuer die Kern-Schicht des Handler-Pakets (Issue #3115,
// ADR-0094): ohne Build-Tag laesst http.DefaultTransport nur Loopback
// (127.0.0.1, ::1, localhost) durch. Jeder andere Versuch wird abgelehnt und
// vermerkt; am Ende macht TestMain den Lauf rot, auch wenn der aufrufende
// Code den Fehler still schluckt. Tests, die DefaultTransport selbst
// ersetzen, legen sich darueber und stellen beim Aufraeumen diese Sperre
// wieder her. Live-Tests (//go:build integration) sind ausgenommen: die
// Sperre installiert erst TestMain in netzsperre_main_test.go.
package handler

import (
	"fmt"
	"net/http"
	"net/netip"
	"strings"
	"sync"
	"testing"
)

type netzsperreTransport struct{ next http.RoundTripper }

var (
	netzsperreMu       sync.Mutex
	netzsperreVersuche []string
)

const netzsperreFehlerTag = "netzsperre (#3115)"

func istLoopbackHost(host string) bool {
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip, err := netip.ParseAddr(strings.Trim(host, "[]"))
	return err == nil && ip.Unmap().IsLoopback()
}

func (n netzsperreTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	host := req.URL.Hostname()
	// Ohne Host (z. B. leere Core-Adresse im Test) baut net/http keine
	// Verbindung auf, sondern scheitert selbst; das ist kein Netzabruf.
	if host == "" || istLoopbackHost(host) {
		return n.next.RoundTrip(req)
	}
	netzsperreMu.Lock()
	netzsperreVersuche = append(netzsperreVersuche, req.URL.Scheme+"://"+req.URL.Host+req.URL.Path)
	netzsperreMu.Unlock()
	return nil, fmt.Errorf("%s: Abruf an %q ausserhalb Loopback im Kern-Test verboten", netzsperreFehlerTag, host)
}

// erwarteAbgelehntenHoehenNachschlag erklaert den Hoehen-Nachschlag
// (open-elevation, Soft-Fail im Resolver) fuer diesen Test als erwartet
// abgelehnt: die Netzsperre lehnt ihn ab, der Resolver laesst die Hoehe leer,
// und der Versuch zaehlt am Laufende nicht als Rueckfall. Jeder andere
// Netzabruf bleibt ein Fehler. Das Handler-Paket kann den Testhebel
// resolver.OhneNachschlagDienste nicht nutzen (export_test.go gilt nur im
// Resolver-Paket), und einen Laufzeitschalter gibt es bewusst nicht (ADR-0114).
func erwarteAbgelehntenHoehenNachschlag(t *testing.T) {
	t.Helper()
	netzsperreMu.Lock()
	start := len(netzsperreVersuche)
	netzsperreMu.Unlock()
	t.Cleanup(func() {
		netzsperreMu.Lock()
		defer netzsperreMu.Unlock()
		if start > len(netzsperreVersuche) {
			return
		}
		rest := append([]string(nil), netzsperreVersuche[:start]...)
		for _, v := range netzsperreVersuche[start:] {
			if !strings.HasPrefix(v, hoehenNachschlagPraefix) {
				rest = append(rest, v)
			}
		}
		netzsperreVersuche = rest
	})
}

const hoehenNachschlagPraefix = "https://api.open-elevation.com/"
