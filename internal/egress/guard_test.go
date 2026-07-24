// TDD-Tests fuer den Egress-Waechter im Go-Dienst (Issue #1337, Scheibe
// "Go-Prozess"). Spec: docs/specs/modules/egress_guard_go.md, AC-1..AC-6.
//
// Beweisfuehrung wie in Scheibe A (Python, tests/tdd/test_egress_guard.py):
// UNTER den Waechter wird ein Sentinel-Transport gehaengt, der bei Erreichen
// einen Marker-Fehler liefert und das Erreichen protokolliert. Damit ist ohne
// ein einziges gesendetes Byte beweisbar, ob der Waechter geblockt hat (Sentinel
// nie erreicht) oder durchgelassen (Sentinel feuert). Kein Netz, kein Mock, der
// die eigene Annahme zurueckspiegelt.
package egress

import (
	"errors"
	"net/http"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

// errAssertedNetworkTouch signalisiert, dass der (simulierte) echte
// Netzwerk-Layer erreicht wurde.
var errAssertedNetworkTouch = errors.New("sentinel: transport reached")

type sentinelTransport struct {
	reached bool
	host    string
}

func (s *sentinelTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	s.reached = true
	s.host = req.URL.Hostname()
	return nil, errAssertedNetworkTouch
}

// withGuard haengt einen Sentinel als http.DefaultTransport ein, installiert den
// Waechter darueber und setzt am Testende den globalen Zustand vollstaendig
// zurueck (sonst vergiften sich die Tests gegenseitig).
func withGuard(t *testing.T, cfg *config.Config) (*sentinelTransport, bool) {
	t.Helper()
	orig := http.DefaultTransport
	sentinel := &sentinelTransport{}
	http.DefaultTransport = sentinel
	t.Cleanup(func() {
		Uninstall()
		http.DefaultTransport = orig
	})
	return sentinel, Install(cfg)
}

func stagingConfig() *config.Config {
	return &config.Config{Env: "staging"}
}

func TestUndeclaredHostBlockedBeforeTransport(t *testing.T) {
	// AC-1: undeklarierter Host in Staging -> Egress-Fehler, Transport nie erreicht.
	sentinel, installed := withGuard(t, stagingConfig())
	if !installed {
		t.Fatal("Install() haette in Staging installieren muessen")
	}

	client := &http.Client{Timeout: 2 * time.Second}
	_, err := client.Get("https://egress-tripwire.invalid/probe")

	if !errors.Is(err, ErrEgressBlocked) {
		t.Fatalf("erwartet ErrEgressBlocked, bekommen: %v", err)
	}
	if sentinel.reached {
		t.Fatal("Transport wurde erreicht — der Waechter hat zu spaet gegriffen")
	}
}

func TestDeclaredHostPassesThrough(t *testing.T) {
	// AC-2: deklarierter TestAccess-Host -> Waechter laesst durch, Sentinel feuert.
	sentinel, _ := withGuard(t, stagingConfig())

	client := &http.Client{Timeout: 2 * time.Second}
	_, err := client.Get("https://nominatim.openstreetmap.org/search?q=Wien")

	if !errors.Is(err, errAssertedNetworkTouch) {
		t.Fatalf("erwartet Sentinel-Signal, bekommen: %v", err)
	}
	if !sentinel.reached {
		t.Fatal("Transport wurde nicht erreicht — deklarierter Host wurde faelschlich geblockt")
	}
	if sentinel.host != "nominatim.openstreetmap.org" {
		t.Fatalf("unerwarteter Host am Transport: %q", sentinel.host)
	}
}

func TestPlainClientInheritsGuard(t *testing.T) {
	// AC-3: ein Client wie im Produktivcode — &http.Client{Timeout: ...} OHNE
	// eigenen Transport — unterliegt dem Waechter ohne Aenderung der Aufrufstelle.
	sentinel, _ := withGuard(t, stagingConfig())

	client := &http.Client{Timeout: 30 * time.Second}
	_, err := client.Get("https://api.example.com/v1/whatever")

	if !errors.Is(err, ErrEgressBlocked) {
		t.Fatalf("erwartet ErrEgressBlocked, bekommen: %v", err)
	}
	if sentinel.reached {
		t.Fatal("Transport wurde erreicht — Aufrufstelle erbt den Waechter nicht")
	}
}

func TestProdIsNoOp(t *testing.T) {
	// AC-4: Prod (Env leer/production, kein Fixture-Dir) -> kein Patch.
	for _, env := range []string{"", "production"} {
		orig := http.DefaultTransport
		installed := Install(&config.Config{Env: env})
		t.Cleanup(Uninstall)

		if installed {
			t.Fatalf("env=%q: Install() haette No-Op sein muessen", env)
		}
		if http.DefaultTransport != orig {
			t.Fatalf("env=%q: http.DefaultTransport wurde veraendert", env)
		}
	}
}

func TestHeartbeatHostBlocked(t *testing.T) {
	// AC-5: uptime.betterstack.com ist Blocked — Staging darf keine
	// Produktions-Heartbeats gruen pingen.
	sentinel, _ := withGuard(t, stagingConfig())

	client := &http.Client{Timeout: 2 * time.Second}
	_, err := client.Get("https://uptime.betterstack.com/api/v1/heartbeat/token")

	if !errors.Is(err, ErrEgressBlocked) {
		t.Fatalf("erwartet ErrEgressBlocked, bekommen: %v", err)
	}
	if sentinel.reached {
		t.Fatal("Heartbeat hat den Transport erreicht")
	}
}

func TestDoubleInstallIsIdempotent(t *testing.T) {
	// AC-6: doppelter Install, danach ein Uninstall -> Original zeiger-identisch.
	orig := http.DefaultTransport
	sentinel := &sentinelTransport{}
	http.DefaultTransport = sentinel
	t.Cleanup(func() {
		Uninstall()
		http.DefaultTransport = orig
	})

	if !Install(stagingConfig()) {
		t.Fatal("erster Install() haette installieren muessen")
	}
	if Install(stagingConfig()) {
		t.Fatal("zweiter Install() haette No-Op sein muessen")
	}
	Uninstall()

	if http.DefaultTransport != http.RoundTripper(sentinel) {
		t.Fatal("Uninstall() hat den Original-Transport nicht zeiger-identisch wiederhergestellt")
	}
}

func TestMixedCaseHostNormalized(t *testing.T) {
	// F001: Redirect-Location-Header fremder Server (googlemaps.go folgt ihnen)
	// liefern den Host in beliebiger Schreibweise. Ein deklarierter Host muss
	// unabhaengig von Gross-/Kleinschreibung durchgelassen, ein
	// undeklarierter/Blocked-Host ebenso geblockt werden.
	sentinel, _ := withGuard(t, stagingConfig())

	client := &http.Client{Timeout: 2 * time.Second}
	_, err := client.Get("https://Nominatim.OpenStreetMap.org/search?q=Wien")
	if !errors.Is(err, errAssertedNetworkTouch) {
		t.Fatalf("gemischt geschriebener TestAccess-Host haette durchgehen muessen: %v", err)
	}
	if !sentinel.reached {
		t.Fatal("Transport nicht erreicht — Casing hat den deklarierten Host faelschlich geblockt")
	}

	sentinel.reached = false
	_, err = client.Get("https://Uptime.BetterStack.com/api/v1/heartbeat/token")
	if !errors.Is(err, ErrEgressBlocked) {
		t.Fatalf("gemischt geschriebener Blocked-Host haette geblockt bleiben muessen: %v", err)
	}
	if sentinel.reached {
		t.Fatal("Blocked-Host hat den Transport erreicht (Casing-Umgehung)")
	}
}

func TestInstallsWithTestFixtureDir(t *testing.T) {
	// Zweite Aktivierungsbedingung aus der Spec: gesetztes TestFixtureDir.
	_, installed := withGuard(t, &config.Config{TestFixtureDir: "tests/fixtures"})
	if !installed {
		t.Fatal("TestFixtureDir gesetzt — Waechter haette installiert werden muessen")
	}
}

func TestLocalhostAlwaysAllowed(t *testing.T) {
	// Python-Core-Proxy, MQ und Frontend laufen ueber localhost — generisch frei.
	sentinel, _ := withGuard(t, stagingConfig())

	client := &http.Client{Timeout: 2 * time.Second}
	_, err := client.Get("http://127.0.0.1:8000/health")

	if !errors.Is(err, errAssertedNetworkTouch) {
		t.Fatalf("localhost haette durchgelassen werden muessen, bekommen: %v", err)
	}
	if !sentinel.reached {
		t.Fatal("localhost-Ruf hat den Transport nicht erreicht")
	}
}
