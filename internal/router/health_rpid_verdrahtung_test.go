package router

// Issue #2130, Fix-Loop 1 (Finding F002): die WIRK-Stelle der RP-ID im
// Health-Endpunkt ist die Verdrahtung in router.go — der Aufruf muss die
// effektive RP-ID der real gebauten WebAuthn-Instanz durchreichen
// (deps.WebAuthn.Config.RPID), nicht den nicht abgeleiteten Rohwert aus der
// Konfiguration (deps.Config.WebAuthnRPID).
//
// health_rpid_test.go im Handler-Paket prueft den Handler nur isoliert mit
// einem injizierten String und bleibt gruen, wenn die Verdrahtung auf den
// Rohwert umgestellt wird. Folge einer solchen Regression: /api/health meldet
// "localhost", obwohl die Anmeldung funktioniert — der Post-Deploy-Selbsttest
// wuerde einen gesunden Deploy faelschlich als FAIL blocken.
//
// Gebaut wird deshalb der ECHTE Produktions-Router ueber config.Load() ->
// config.NewWebAuthn(), dieselbe Kette wie in cmd/server/main.go.

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// withRouterEnv leert die Prozess-Umgebung, setzt die uebergebenen Variablen
// und stellt den Ausgangszustand nach dem Test vollstaendig wieder her.
func withRouterEnv(t *testing.T, vars map[string]string) {
	t.Helper()
	saved := os.Environ()
	t.Cleanup(func() {
		os.Clearenv()
		for _, kv := range saved {
			if i := strings.IndexByte(kv, '='); i > 0 {
				os.Setenv(kv[:i], kv[i+1:])
			}
		}
	})
	os.Clearenv()
	for k, v := range vars {
		os.Setenv(k, v)
	}
}

func TestHealthRouteMeldetEffektiveRPIDNichtDenRohwert(t *testing.T) {
	// GIVEN: nur GZ_PUBLIC_HOST gesetzt — GZ_WEBAUTHN_RP_ID bleibt auf seinem
	// Default "localhost", die effektive RP-ID wird daraus abgeleitet.
	withRouterEnv(t, map[string]string{"GZ_PUBLIC_HOST": "https://staging.gregor20.henemm.com"})

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.CacheDir = t.TempDir()
	// Python-Core absichtlich unerreichbar: das Feld muss auch bei
	// status=degraded stimmen, kein Netz noetig.
	cfg.PythonCoreURL = "http://127.0.0.1:19999"

	wa, err := config.NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("config.NewWebAuthn: %v", err)
	}

	// Kontrollmarke: Rohwert und effektiver Wert muessen sich unterscheiden,
	// sonst koennte dieser Test die Verwechslung gar nicht sehen.
	if wa.Config.RPID == cfg.WebAuthnRPID {
		t.Fatalf("Testaufbau untauglich: Rohwert %q und effektive RP-ID %q sind gleich",
			cfg.WebAuthnRPID, wa.Config.RPID)
	}

	s := store.New(cfg.DataDir, cfg.UserID)
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})

	// WHEN: /api/health ueber den echten Router abgerufen wird
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("ungueltiges JSON: %v — %s", err, w.Body.String())
	}

	// THEN: gemeldet wird der abgeleitete, effektive Wert
	if body["webauthn_rpid"] != wa.Config.RPID {
		t.Errorf("F002: /api/health muss die effektive RP-ID %q melden, bekommen %v (Antwort: %s)",
			wa.Config.RPID, body["webauthn_rpid"], w.Body.String())
	}
	// THEN: und ausdruecklich NICHT den nicht abgeleiteten Rohwert
	if body["webauthn_rpid"] == cfg.WebAuthnRPID {
		t.Errorf("F002: /api/health meldet den Konfigurations-Rohwert %q statt der effektiven RP-ID %q — "+
			"der Selbsttest wuerde einen gesunden Deploy faelschlich blocken",
			cfg.WebAuthnRPID, wa.Config.RPID)
	}
}
