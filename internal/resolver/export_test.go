package resolver

import (
	"net/http"
	"net/http/httptest"
	"net/netip"
	"strings"
	"testing"
	"time"
)

// Nur im Testbinary vorhanden (Issue #2961): die Abschottung des Link-Abrufs
// ist in Produktion nicht abschaltbar. Tests mit httptest-Servern (127.0.0.1,
// http://) oeffnen sie hier gezielt und stellen den Ausgangszustand am
// Testende wieder her.

// ErlaubeTestHosts laesst zusaetzlich die genannten Hosts (ohne Port) als
// Link-Hosts zu.
func ErlaubeTestHosts(t *testing.T, hosts ...string) {
	t.Helper()
	orig := linkHostAllowed
	t.Cleanup(func() { linkHostAllowed = orig })
	linkHostAllowed = func(h string) bool {
		for _, x := range hosts {
			if strings.EqualFold(h, x) {
				return true
			}
		}
		return orig(h)
	}
}

// ErlaubeHTTPSchema laesst http:// zu (httptest.NewServer spricht kein TLS).
func ErlaubeHTTPSchema(t *testing.T) {
	t.Helper()
	orig := linkSchemes
	t.Cleanup(func() { linkSchemes = orig })
	linkSchemes = map[string]bool{"https": true, "http": true}
	origPort := linkPortErlaubt
	t.Cleanup(func() { linkPortErlaubt = origPort })
	// httptest-Server lauschen auf beliebigen Ports.
	linkPortErlaubt = func(string) bool { return true }
}

// ErlaubeLoopbackVerbindung laesst Verbindungen zu 127.0.0.1/::1 zu.
func ErlaubeLoopbackVerbindung(t *testing.T) {
	t.Helper()
	orig := dialIPAllowed
	t.Cleanup(func() { dialIPAllowed = orig })
	dialIPAllowed = func(ip netip.Addr) bool { return ip.Unmap().IsLoopback() || orig(ip) }
}

// IstOeffentlicheAdresse macht die Adresspruefung direkt pruefbar.
func IstOeffentlicheAdresse(s string) bool {
	return isPublicUnicastIP(netip.MustParseAddr(s))
}

// IstGoogleLinkHost macht die Erlaubnisliste direkt pruefbar.
func IstGoogleLinkHost(h string) bool { return isGoogleLinkHost(h) }

// OhneNachschlagDienste lenkt Hoehen- und Ortsnamen-Nachschlag auf einen
// lokalen Server, der nichts findet — Tests bleiben netzfrei.
func OhneNachschlagDienste(t *testing.T) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	t.Cleanup(srv.Close)
	origE, origN := elevationLookupURL, nominatimSearchURL
	t.Cleanup(func() { elevationLookupURL, nominatimSearchURL = origE, origN })
	elevationLookupURL, nominatimSearchURL = srv.URL+"/hoehe", srv.URL+"/suche"
}

// PruefeLinkURL macht die Link-Pruefung (Schema, Nutzer-Info, Host, Port)
// direkt pruefbar.
func PruefeLinkURL(raw string) error {
	_, err := parseLinkURL(raw)
	return err
}

// GoogleLaenderDomains liefert die feste Liste der Laender-Domains.
func GoogleLaenderDomains() []string { return append([]string(nil), googleLaenderDomains...) }

// LinkClientOhneUmgebungsProxy belegt, dass der abgeschottete Client keinen
// Proxy aus der Umgebung nutzt (Transport.Proxy == nil).
func LinkClientOhneUmgebungsProxy() bool {
	c := newLinkClient(time.Second)
	et, ok := c.Transport.(egressTransport)
	if !ok {
		return false
	}
	tr, ok := et.next.(*http.Transport)
	return ok && tr.Proxy == nil
}
