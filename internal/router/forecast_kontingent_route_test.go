// Adversary-Nachtrag zu Issue #2391 (F001, HIGH): Waechter an der WIRKSTELLE.
//
// Der Handler-Test in internal/handler/forecast_test.go beweist nur, dass
// ForecastHandler bei uebergebener Core-URL reserviert — NICHT, dass der echte
// Router diese URL auch uebergibt. Die Mutation
//
//	handler.ForecastHandler(deps.WeatherProvider, "")
//
// an internal/router/router.go liess vor diesem Test die gesamte Suite gruen:
// der Kontingent-Deckel waere lautlos abschaltbar gewesen. Auch der Sweep
// TestCoreAuthHeaderOnEveryPythonCallFromRouter faengt das nicht — er prueft
// Header auf EINGETROFFENEN Aufrufen, nie das AUSBLEIBEN eines Aufrufs.
//
// Gemessen wird deshalb am Python-Core-Stub: welcher Pfad kommt dort an, wenn
// ein authentifizierter GET /api/forecast durch den echten Router laeuft.
package router

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	kontingentReservePfad = "/api/_internal/forecast-budget/reserve"
	kontingentNutzer      = "kontingent-route-nutzer"
)

// stillerProvider ist eine echte provider.WeatherProvider-Implementierung ohne
// Netzzugriff. Sie darf nicht fehlen: nil wuerde nach der Reservierung in einen
// Panic laufen und den Test aus einem Grund faerben, der nichts mit der
// gemessenen Zusicherung zu tun hat.
type stillerProvider struct{}

func (stillerProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	return &model.Timeseries{
		Timezone: "Europe/Berlin",
		Meta:     model.ForecastMeta{Provider: "test", Model: "test-model", GridResKm: 2},
		Data:     []model.ForecastDataPoint{},
	}, nil
}

var _ provider.WeatherProvider = stillerProvider{}

// neuerKontingentRouter baut den echten Produktions-Router (dieselbe
// Verdrahtung wie cmd/server/main.go) gegen einen Fake-Python-Core — anders als
// newCoreAuthSweepRouter mit echtem WeatherProvider.
func neuerKontingentRouter(t *testing.T, pythonURL string) (chi.Router, *config.Config, *store.Store) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL
	// Kein SMTP im Test: sonst koennte ein Handler echte Mail versenden (#1477).
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
		WeatherProvider:    stillerProvider{},
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, cfg, s
}

// TestForecastRouteReserviertKontingentUeberDenEchtenRouter fixiert die
// Verdrahtung von /api/forecast auf den Kontingent-Endpunkt des Core.
func TestForecastRouteReserviertKontingentUeberDenEchtenRouter(t *testing.T) {
	var mu sync.Mutex
	var pfade []string

	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		pfade = append(pfade, r.URL.Path)
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"allowed": true}`))
	}))
	defer py.Close()

	r, cfg, s := neuerKontingentRouter(t, py.URL)

	// Ohne Konto und Sitzung antwortet der Handler 401 VOR jeder Reservierung;
	// ohne gueltige lat/lon 400 — beides waere rot ohne Defekt.
	if err := s.SaveUser(model.User{ID: kontingentNutzer, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := s.AddSession(kontingentNutzer, sessionIDFor(kontingentNutzer)); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	req := httptest.NewRequest("GET", "/api/forecast?lat=42.3&lon=9.0&hours=24", nil)
	req.AddCookie(sessionCookieFor(kontingentNutzer, cfg.SessionSecret))
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("GET /api/forecast antwortete %d (erwartet 200) — Messgrundlage ungueltig: Body %s", rec.Code, rec.Body.String())
	}

	mu.Lock()
	defer mu.Unlock()
	reservierungen := 0
	for _, p := range pfade {
		if p == kontingentReservePfad {
			reservierungen++
		}
	}
	if reservierungen != 1 {
		t.Fatalf("der Router hat %d Reservierungen auf %s ausgeloest (erwartet genau 1) — am Core angekommene Pfade: %v; die Route /api/forecast haengt nicht (mehr) am Kontingent-Gate", reservierungen, kontingentReservePfad, pfade)
	}
}
