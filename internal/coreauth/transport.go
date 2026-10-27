// Package coreauth haengt das gemeinsame Geheimnis (Issue #2142) an jede
// ausgehende Anfrage an den Python-Core.
//
// Bauform 1:1 nach internal/egress/guard.go: ein umhuellender RoundTripper auf
// http.DefaultTransport — dem gemeinsamen Ausgang aller Go-Clients im Repo, die
// als &http.Client{Timeout: ...} ohne eigenen Transport gebaut werden. Damit
// traegt jede der ~20 Aufrufstellen den Header, ohne dass eine von ihnen
// angefasst werden muesste; eine kuenftig hinzukommende ebenso.
//
// Gefiltert wird auf Host UND Port aus cfg.PythonCoreURL. Ohne diesen Filter
// ginge das Geheimnis an jedes andere Ziel mit (Open-Meteo, Google Maps,
// Komoot, BetterStack).
package coreauth

import (
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"

	"github.com/henemm/gregor-api/internal/config"
)

// HeaderName ist der Traeger des gemeinsamen Geheimnisses. Derselbe Name wird
// in api/main.py erzwungen.
const HeaderName = "X-GZ-Core-Auth"

var (
	mu        sync.Mutex
	installed bool
	// original ist der Transport, der im Moment des Install unter dem
	// Auth-Transport sass — Restore-Ziel fuer Uninstall.
	original http.RoundTripper
)

// authTransport setzt den Auth-Header, bevor der Request den darunterliegenden
// Transport erreicht.
type authTransport struct {
	next http.RoundTripper
	// target ist "host:port" des Python-Core, kleingeschrieben.
	target string
	secret string
}

func (a *authTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if hostPort(req.URL) != a.target {
		return a.next.RoundTrip(req)
	}
	// Klonen statt mutieren: der RoundTripper-Vertrag verbietet, den
	// uebergebenen Request zu veraendern.
	cloned := req.Clone(req.Context())
	cloned.Header.Set(HeaderName, a.secret)
	return a.next.RoundTrip(cloned)
}

// hostPort normalisiert eine URL auf "host:port" (kleingeschrieben), mit dem
// Standard-Port des Schemas, wenn keiner angegeben ist. Ohne die
// Port-Ergaenzung wuerde "http://localhost:80" nicht auf "http://localhost"
// passen — und umgekehrt ein fremder Host auf demselben Port faelschlich
// passen, wenn nur der Host verglichen wuerde.
func hostPort(u *url.URL) string {
	if u == nil {
		return ""
	}
	host := strings.ToLower(u.Hostname())
	if host == "" {
		return ""
	}
	port := u.Port()
	if port == "" {
		switch strings.ToLower(u.Scheme) {
		case "https":
			port = "443"
		default:
			port = "80"
		}
	}
	return host + ":" + port
}

// Install ersetzt http.DefaultTransport durch den Auth-Transport. No-Op ohne
// konfiguriertes Geheimnis oder mit unlesbarer PythonCoreURL — der Fail-Fast
// dafuer sitzt in config.ValidateCoreSharedSecret, nicht hier.
//
// Rueckgabe: true genau dann, wenn dieser Aufruf den Patch gesetzt hat.
//
// Reihenfolge (Issue #2142, AC-4): MUSS vor egress.Install laufen. Der
// Egress-Waechter merkt sich beim Installieren den vorgefundenen Transport und
// stellt ihn bei Uninstall zeiger-identisch wieder her — andersherum
// verschwaende ein egress.Uninstall() den Auth-Header still mit.
func Install(cfg *config.Config) bool {
	if cfg == nil || cfg.CoreSharedSecret == "" {
		return false
	}
	parsed, err := url.Parse(cfg.PythonCoreURL)
	if err != nil {
		log.Printf("[coreauth] PythonCoreURL %q unlesbar: %v — Auth-Header inaktiv", cfg.PythonCoreURL, err)
		return false
	}
	target := hostPort(parsed)
	if target == "" {
		log.Printf("[coreauth] PythonCoreURL %q ohne Host — Auth-Header inaktiv", cfg.PythonCoreURL)
		return false
	}

	mu.Lock()
	defer mu.Unlock()
	if installed {
		return false
	}

	original = http.DefaultTransport
	http.DefaultTransport = &authTransport{next: original, target: target, secret: cfg.CoreSharedSecret}
	installed = true
	log.Printf("[coreauth] Auth-Header aktiv für %s", target)
	return true
}

// Uninstall stellt den beim Install gemerkten Transport zeiger-identisch wieder
// her. No-Op, wenn nicht installiert.
func Uninstall() {
	mu.Lock()
	defer mu.Unlock()
	if !installed {
		return
	}
	http.DefaultTransport = original
	original = nil
	installed = false
}
