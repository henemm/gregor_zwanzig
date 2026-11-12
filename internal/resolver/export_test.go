package resolver

import (
	"net/netip"
	"strings"
	"testing"
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
