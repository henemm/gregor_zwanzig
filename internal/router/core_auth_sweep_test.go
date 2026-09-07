// TDD-RED fuer Issue #2142 Scheibe 1 (AC-1, Test 3): Sweep ueber ALLE vom
// Router registrierten Routen.
//
// Der Nachweis laeuft an der Wirkstelle, nicht an der Funktion: chi.Walk zaehlt
// die Routen selbsttaetig auf (kein handgepflegter Katalog — die 21. Route wird
// automatisch mitgeprueft), jede wird authentifiziert angefragt, und gemessen
// wird ausschliesslich an einem Fake-Python-Core, was dort ankommt. Routen, die
// schon vor dem Python-Aufruf abbrechen, tauchen dort gar nicht auf.
//
// Positivkontrolle ist Pflicht: kommt am Fake KEIN Request an, ist "alle
// eingetroffenen Requests trugen den Header" bei leerer Menge trivial wahr und
// der Sweep bewacht nichts. Der Test schlaegt dann fehl.
package router

import (
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"regexp"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	sweepCoreSecret = "core-shared-secret-fuer-tests-0123456789"
	sweepUserPrefix = "sweepuser"

	// minPythonCallsReached bewacht die MESSGRUNDLAGE, nicht die Routenliste —
	// aufgezaehlt wird weiterhin selbsttaetig ueber chi.Walk.
	//
	// Ist-Wert bei Anlage dieses Tests: 27 am Fake eingetroffene Requests.
	// Eine blosse "> 0"-Kontrolle ist zu schwach: gemessen brach die Menge
	// schon einmal von 27 auf 7 ein, weil POST /api/auth/logout mitten im
	// Sweep die Sitzung entwertete und alle spaeteren Routen auf 401 liefen —
	// 7 ist ebenfalls "> 0" und waere still durchgegangen.
	//
	// Faellt diese Zahl: Ursache suchen (Sitzung entwertet? Transport nicht
	// installiert? Fake nicht erreichbar?) — NICHT die Konstante senken.
	// Der Abstand von 3 zum Ist-Wert deckt das Entfernen einzelner
	// Python-Routen ab, ohne einen Einbruch der Groessenordnung zu verpassen.
	minPythonCallsReached = 24
)

// routeParamRe ersetzt chi-Platzhalter wie {id} oder {waypointId} durch einen
// konkreten Wert, damit der Pfad ueberhaupt routbar ist.
var routeParamRe = regexp.MustCompile(`\{[^}]+\}`)

// newCoreAuthSweepRouter baut den echten Produktions-Router (dieselbe
// Verdrahtung wie cmd/server/main.go) gegen einen Fake-Python-Core.
func newCoreAuthSweepRouter(t *testing.T, pythonURL string) (chi.Router, *config.Config, *store.Store) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL
	cfg.CoreSharedSecret = sweepCoreSecret
	// Kein SMTP im Sweep: einzelne Handler (z.B. Tier-Change) versenden sonst
	// echte Mail.
	cfg.SMTPHost, cfg.GoogleSMTPHost, cfg.FallbackSMTPHost = "", "", ""

	s := store.New(cfg.DataDir, cfg.UserID)

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, cfg, s
}

// callSweepRoute schickt einen authentifizierten Request. Panics werden
// abgefangen: Handler, die ohne vollstaendige Deps (z.B. WeatherProvider)
// panisch werden, erreichen den Python-Fake ohnehin nicht — gemessen wird
// ausschliesslich, was dort ankommt.
//
// Jede Route bekommt ein FRISCHES Konto samt frischem Cookie. Sonst vergiftet
// der Sweep sich selbst: DELETE /api/auth/account loescht das Konto und
// POST /api/auth/logout entwertet die Sitzung — gemessen liefen danach alle
// alphabetisch spaeteren Routen auf 401 und erreichten den Python-Fake nie.
func callSweepRoute(t *testing.T, r http.Handler, s *store.Store, secret, userID, method, path string) {
	t.Helper()
	defer func() {
		if rec := recover(); rec != nil {
			t.Logf("Route %s %s panicked (nicht gemessen): %v", method, path, rec)
		}
	}()
	if err := s.SaveUser(model.User{ID: userID, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	req := httptest.NewRequest(method, path, bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(sessionCookieFor(userID, secret))
	r.ServeHTTP(httptest.NewRecorder(), req)
}

// Test 3 (AC-1).
func TestCoreAuthHeaderOnEveryPythonCallFromRouter(t *testing.T) {
	var mu sync.Mutex
	arrived := 0
	var unauthenticated []string

	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		arrived++
		if got := r.Header.Get("X-GZ-Core-Auth"); got != sweepCoreSecret {
			unauthenticated = append(unauthenticated, r.Method+" "+r.URL.Path+" -> "+got)
		}
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{}`))
	}))
	defer py.Close()

	r, cfg, s := newCoreAuthSweepRouter(t, py.URL)

	origTransport := http.DefaultTransport
	coreauth.Install(cfg)
	t.Cleanup(func() {
		coreauth.Uninstall()
		http.DefaultTransport = origTransport
	})

	type route struct{ method, path string }
	var routes []route
	err := chi.Walk(r, func(method, pattern string, h http.Handler, mws ...func(http.Handler) http.Handler) error {
		routes = append(routes, route{method, routeParamRe.ReplaceAllString(pattern, "sweep")})
		return nil
	})
	if err != nil {
		t.Fatalf("chi.Walk: %v", err)
	}
	if len(routes) == 0 {
		t.Fatal("chi.Walk hat keine einzige Route gefunden — Messung ungueltig")
	}

	for i, rt := range routes {
		callSweepRoute(t, r, s, cfg.SessionSecret, fmt.Sprintf("%s%d", sweepUserPrefix, i), rt.method, rt.path)
	}

	mu.Lock()
	sweepArrived := arrived
	mu.Unlock()

	// Zweite Messgrundlagen-Kontrolle, direkt aus der gefundenen Regression:
	// nach der letzten Route muss eine authentifizierte Anfrage weiterhin
	// moeglich sein. Bricht die Sitzungsfaehigkeit unterwegs weg (Logout,
	// geloeschtes Konto), sinkt die Messmenge still — genau der Einbruch, der
	// oben nur an der Untergrenze auffiele.
	callSweepRoute(t, r, s, cfg.SessionSecret, sweepUserPrefix+"final", "GET", "/api/config")

	mu.Lock()
	defer mu.Unlock()
	if arrived == sweepArrived {
		t.Fatal("nach der letzten Route erreichte keine authentifizierte Anfrage mehr den Python-Core — der Sweep hat die Sitzungsfaehigkeit unterwegs zerstoert, die Messmenge ist wertlos")
	}
	if sweepArrived < minPythonCallsReached {
		t.Fatalf("nur %d von erwarteten mindestens %d Requests am Python-Core-Fake angekommen (%d Routen aufgezaehlt) — der Sweep erreicht den Python-Core nicht mehr flaechendeckend", sweepArrived, minPythonCallsReached, len(routes))
	}
	if len(unauthenticated) > 0 {
		t.Fatalf("%d von %d am Python-Core eingetroffenen Requests ohne gueltigen X-GZ-Core-Auth-Header: %v", len(unauthenticated), arrived, unauthenticated)
	}
}
