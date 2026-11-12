package resolver

// Abschottung fuer Abrufe nutzerbestimmter Ziele (Issue #2961, ADR-0114).
//
// Ein geteilter Kartenlink ist die einzige Stelle im Resolver, an der eine vom
// Nutzer eingegebene URL tatsaechlich abgerufen wird. Dafuer gilt:
//
//  1. Nur https und nur Hosts aus der Erlaubnisliste (linkHostAllowed) —
//     sowohl fuer die Eingabe als auch fuer jeden Redirect-Hop.
//  2. Eigener Transport statt http.DefaultTransport: das Dienstgeheimnis fuer
//     den Python-Core (internal/coreauth) haengt am DefaultTransport und geht
//     ueber diesen Client nie mit. Kein Proxy aus der Umgebung — sonst pruefte
//     die Adresssperre die Adresse des Proxys statt des Ziels.
//  3. Die Adresssperre sitzt im Control-Hook des Dialers, also an der
//     TATSAECHLICH aufgeloesten IP: auch ein erlaubter Name, der auf eine
//     interne Adresse zeigt (DNS-Rebinding), wird nicht verbunden.
//  4. Der Staging-Egress-Waechter (internal/egress) wird je Anfrage gefragt,
//     weil dieser Client nicht ueber den gepatchten DefaultTransport laeuft.
//
// Tests ersetzen die Paket-Variablen unten ausschliesslich ueber
// export_test.go (nur im Testbinary vorhanden) — es gibt keinen Schalter zur
// Laufzeit, der die Pruefungen in Produktion abschalten koennte.

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"regexp"
	"strings"
	"syscall"
	"time"

	"github.com/henemm/gregor-api/internal/egress"
)

// maxRedirectHops begrenzt die Kette geteilter Links (maps.app.goo.gl ->
// www.google.com braucht einen Hop).
const maxRedirectHops = 5

// maxResponseHeaderBytes begrenzt die Antwortkoepfe; den Rumpf liest der
// Resolver nie (ausgewertet wird nur die End-URL).
const maxResponseHeaderBytes = 64 << 10

// errZielGesperrt ist die Wurzel aller Abschottungs-Fehler.
var errZielGesperrt = errors.New("ziel fuer nutzerbestimmten abruf gesperrt")

// googleLinkHosts: Hosts geteilter Google-Maps-Links und ihrer Redirect-Ziele.
var googleLinkHosts = map[string]bool{
	"maps.app.goo.gl": true,
	"goo.gl":          true,
	"www.google.com":  true,
	"maps.google.com": true,
	"google.com":      true,
}

// reGoogleCountryHost deckt die Laender-Domains von Google Maps ab
// (google.de, www.google.co.uk, maps.google.com.au), aber keine beliebigen
// Unterdomains oder Namen wie google.evil.example.
var reGoogleCountryHost = regexp.MustCompile(`^(www\.|maps\.)?google\.(com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$`)

// komootLinkHosts: Hosts, die als Komoot-Link akzeptiert werden. Abgerufen
// wird dort nie die Eingabe selbst, nur die feste Komoot-API.
var komootLinkHosts = map[string]bool{
	"www.komoot.com": true,
	"komoot.com":     true,
	"www.komoot.de":  true,
	"komoot.de":      true,
}

// Paket-Variablen der Pruefungen; nur export_test.go ersetzt sie.
var (
	linkHostAllowed = isGoogleLinkHost
	linkSchemes     = map[string]bool{"https": true}
	dialIPAllowed   = isPublicUnicastIP
)

func isGoogleLinkHost(host string) bool {
	host = strings.ToLower(host)
	return googleLinkHosts[host] || reGoogleCountryHost.MatchString(host)
}

func isKomootLinkHost(host string) bool {
	return komootLinkHosts[strings.ToLower(host)]
}

// parseLinkURL parst die Eingabe streng als absolute URL und prueft Schema
// und Host gegen die Erlaubnisliste. Nutzer-Info (user@host) ist nie erlaubt.
func parseLinkURL(raw string) (*url.URL, error) {
	u, err := url.Parse(raw)
	if err != nil {
		return nil, err
	}
	if err := checkLinkURL(u); err != nil {
		return nil, err
	}
	return u, nil
}

func checkLinkURL(u *url.URL) error {
	if u == nil || !linkSchemes[strings.ToLower(u.Scheme)] || u.User != nil {
		return fmt.Errorf("%w: schema", errZielGesperrt)
	}
	if !linkHostAllowed(u.Hostname()) {
		return fmt.Errorf("%w: host", errZielGesperrt)
	}
	return nil
}

// Netze, die zusaetzlich zu den netip-Praedikaten gesperrt sind.
var blockedPrefixes = []netip.Prefix{
	netip.MustParsePrefix("0.0.0.0/8"),      // "dieses Netz"
	netip.MustParsePrefix("100.64.0.0/10"),  // CGNAT
	netip.MustParsePrefix("192.0.0.0/24"),   // IETF-Protokollzuweisungen
	netip.MustParsePrefix("198.18.0.0/15"),  // Benchmark-Netz
	netip.MustParsePrefix("240.0.0.0/4"),    // reserviert inkl. Broadcast
	netip.MustParsePrefix("64:ff9b::/96"),   // NAT64 (bettet IPv4 ein)
	netip.MustParsePrefix("64:ff9b:1::/48"), // lokales NAT64
	netip.MustParsePrefix("2002::/16"),      // 6to4 (bettet IPv4 ein)
	netip.MustParsePrefix("100::/64"),       // Discard-Only
}

// isPublicUnicastIP lehnt Loopback-, private, Link-Local-, CGNAT-, Multicast-
// und reservierte Adressen ab — IPv4 und IPv6, IPv4-mapped wird entpackt.
func isPublicUnicastIP(ip netip.Addr) bool {
	if !ip.IsValid() {
		return false
	}
	ip = ip.Unmap()
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsUnspecified() ||
		ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() ||
		ip.IsInterfaceLocalMulticast() || ip.IsMulticast() {
		return false
	}
	for _, p := range blockedPrefixes {
		if p.Contains(ip) {
			return false
		}
	}
	return true
}

// dialControl prueft die tatsaechlich verbundene Adresse.
func dialControl(_, address string, _ syscall.RawConn) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return fmt.Errorf("%w: adresse", errZielGesperrt)
	}
	ip, err := netip.ParseAddr(host)
	if err != nil || !dialIPAllowed(ip) {
		return fmt.Errorf("%w: adresse", errZielGesperrt)
	}
	return nil
}

// egressTransport fragt den Staging-Waechter vor jeder Anfrage (auch je Hop).
type egressTransport struct{ next http.RoundTripper }

func (e egressTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if err := egress.HTTPAllowed(req.URL.Hostname()); err != nil {
		return nil, err
	}
	return e.next.RoundTrip(req)
}

// newLinkClient baut den abgeschotteten Client fuer EINEN Abruf.
func newLinkClient(timeout time.Duration) *http.Client {
	dialer := &net.Dialer{Timeout: timeout, Control: dialControl}
	transport := &http.Transport{
		Proxy: nil,
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return dialer.DialContext(ctx, network, addr)
		},
		TLSHandshakeTimeout:    timeout,
		ResponseHeaderTimeout:  timeout,
		MaxResponseHeaderBytes: maxResponseHeaderBytes,
		DisableKeepAlives:      true,
	}
	return &http.Client{
		Timeout:   timeout,
		Transport: egressTransport{next: transport},
		// Ein Hop ausserhalb der Liste wird NICHT abgerufen: der Client
		// liefert die Weiterleitungsantwort selbst zurueck, ihr Ziel wird
		// hoechstens als Text ausgewertet (followGoogleMapsRedirect).
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= maxRedirectHops {
				return fmt.Errorf("%w: zu viele weiterleitungen", errZielGesperrt)
			}
			if checkLinkURL(req.URL) != nil {
				return http.ErrUseLastResponse
			}
			return nil
		},
	}
}
