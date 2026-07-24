package egress

import (
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"

	"github.com/henemm/gregor-api/internal/config"
)

// ErrEgressBlocked ist die Wurzel aller Waechter-Fehler — Aufrufer pruefen mit
// errors.Is, unabhaengig vom Host im Meldungstext.
var ErrEgressBlocked = errors.New("egress blockiert (#1337)")

var localhostHosts = map[string]bool{"localhost": true, "127.0.0.1": true}

var (
	mu        sync.Mutex
	installed bool
	// original ist der Transport, der im Moment des Install unter dem Waechter
	// sass — Restore-Ziel fuer Uninstall.
	original http.RoundTripper
)

// guardedTransport prueft jeden ausgehenden Request gegen das Inventar, bevor
// er den darunterliegenden Transport erreicht.
type guardedTransport struct {
	next http.RoundTripper
}

func (g *guardedTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	host := req.URL.Hostname()
	if !isAllowed(host) {
		return nil, fmt.Errorf("%w: Host %q ist nicht als TestAccess deklariert", ErrEgressBlocked, host)
	}
	return g.next.RoundTrip(req)
}

// isAllowed ist die Entscheidungsregel, identisch zu Scheibe A (Python):
// TestAccess durchlassen, Blocked und undeklariert sperren, localhost frei.
// F001: Der Host wird vor dem Lookup case-insensitiv normalisiert —
// Redirect-Location-Header fremder Server (googlemaps.go folgt ihnen) liefern
// beliebiges Casing, das die (lowercase) Inventar-Keys sonst nicht traefe.
func isAllowed(host string) bool {
	if host == "" {
		return false
	}
	host = strings.ToLower(host)
	if localhostHosts[host] {
		return true
	}
	kind, declared := Inventory[host]
	return declared && kind == TestAccess
}

// Install ersetzt http.DefaultTransport durch den Waechter — den gemeinsamen
// Ausgang aller Go-Clients im Repo, die als &http.Client{Timeout: ...} ohne
// eigenen Transport gebaut werden. Installiert wird ausschliesslich bei
// Env == "staging" oder gesetztem TestFixtureDir; jeder andere Zustand ist ein
// No-Op mit Prod-Verhalten (ein Konfigurationsfehler darf Prod nie lahmlegen).
// Rueckgabe: true genau dann, wenn dieser Aufruf den Patch gesetzt hat.
func Install(cfg *config.Config) bool {
	if cfg == nil || (cfg.Env != "staging" && cfg.TestFixtureDir == "") {
		return false
	}

	mu.Lock()
	defer mu.Unlock()
	if installed {
		return false
	}

	original = http.DefaultTransport
	http.DefaultTransport = &guardedTransport{next: original}
	installed = true
	log.Printf("[egress] Wächter aktiv — %d Hosts deklariert", len(Inventory))
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

// SMTPAllowed ist die zweite Waechter-Linie: net/smtp laeuft nicht ueber
// http.DefaultTransport. Ohne installierten Waechter (Prod) immer nil.
func SMTPAllowed(host string) error {
	mu.Lock()
	active := installed
	mu.Unlock()

	if !active || isAllowed(host) {
		return nil
	}
	return fmt.Errorf("%w: SMTP-Host %q ist nicht als TestAccess deklariert", ErrEgressBlocked, host)
}
