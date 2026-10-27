package router

// TDD RED — Issue #2155 Scheibe S2 (Admin-Rolle), AC-1, AC-2, AC-3.
//
// Spec: docs/specs/modules/admin_rolle_s2_status_token.md
//
// GET /api/scheduler/status ist nur noch mit dem Maschinen-Token
// (Header X-GZ-Status-Token, konfiguriert ueber GZ_STATUS_TOKEN) lesbar.
// Das Token wird bewusst per t.Setenv VOR config.Load() gesetzt und nicht
// direkt als cfg-Feld: so ist das envconfig-Tag an der Stelle bewacht, an der
// es WIRKT (ein falscher Tag-Name liesse eine Direktzuweisung gruen).
//
// RED-Signal heute: die Route steht auf der Public-Allowlist und hat keinen
// Waechter — jeder Aufruf ohne/mit falschem Token bekommt 200 statt 401.
// AC-1 (richtiges Token => 200) ist heute schon gruen und bleibt als
// Waechtertest stehen: er faengt eine Umsetzung, die den Endpunkt ganz sperrt.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const s2Token = "s2-status-token-7f3a9c"

// s2Optionen steuert den Aufbau des echten Routers fuer die S2-Tests.
type s2Optionen struct {
	statusToken string // Wert fuer GZ_STATUS_TOKEN ("" = nicht konfiguriert)
	admins      string // Wert fuer cfg.AdminUserIDs
	staging     bool   // GZ_ENV=staging (registriert /api/debug/trigger-radar-alert)
	// userState wird als scheduler_user_state.json VOR scheduler.New in das
	// Datenverzeichnis gelegt: [jobID][userID] -> Datensatz.
	userState  map[string]map[string]map[string]any
	pythonZiel string // URL des Proxy-Ziels ("" = keins)
}

// s2Router baut den echten Produktions-Router (router.New) mit AuthMiddleware
// und echten gz_session-Cookies. Nutzer: alice, bob, carol.
func s2Router(t *testing.T, o s2Optionen) (http.Handler, string) {
	t.Helper()

	t.Setenv("GZ_STATUS_TOKEN", o.statusToken)
	if o.staging {
		t.Setenv("GZ_ENV", "staging")
	} else {
		t.Setenv("GZ_ENV", "")
	}

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.UserID = "ops"
	cfg.AdminUserIDs = o.admins
	if o.pythonZiel != "" {
		cfg.PythonCoreURL = o.pythonZiel
	}

	s := store.New(cfg.DataDir, cfg.UserID)
	for _, id := range []string{"alice", "bob", "carol"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}

	if o.userState != nil {
		raw, err := json.Marshal(o.userState)
		if err != nil {
			t.Fatalf("userState marshal: %v", err)
		}
		if err := os.WriteFile(filepath.Join(cfg.DataDir, "scheduler_user_state.json"), raw, 0o600); err != nil {
			t.Fatalf("userState schreiben: %v", err)
		}
	}

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
	return r, cfg.SessionSecret
}

// statusAbruf ruft GET /api/scheduler/status; header == nil heisst: kein
// Token-Header, userID == "" heisst: ohne Sitzungscookie.
func statusAbruf(t *testing.T, r http.Handler, secret string, header *string, userID string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status", nil)
	if header != nil {
		req.Header.Set("X-GZ-Status-Token", *header)
	}
	if userID != "" {
		req.AddCookie(sessionCookieFor(userID, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func str(s string) *string { return &s }

// pruefe401 verlangt exakt 401, den JSON-Body und keinerlei Statusdaten.
func pruefe401(t *testing.T, fall string, w *httptest.ResponseRecorder) {
	t.Helper()
	if w.Code != http.StatusUnauthorized {
		t.Errorf("%s: erwartet 401, bekommen %d: %s", fall, w.Code, w.Body.String())
		return
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"error":"unauthorized"}` {
		t.Errorf("%s: Body erwartet %q, bekommen %q", fall, `{"error":"unauthorized"}`, got)
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Errorf("%s: Content-Type erwartet application/json, bekommen %q", fall, ct)
	}
	if strings.Contains(w.Body.String(), `"jobs"`) {
		t.Errorf("%s: 401-Antwort darf keine Statusdaten tragen: %s", fall, w.Body.String())
	}
}

// AC-1: richtiges Token => 200 mit vollem Status (jobs, running, timezone).
func TestStatusToken_CorrectHeader_Returns200WithFullStatus(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token})

	w := statusAbruf(t, r, secret, str(s2Token), "")
	if w.Code != http.StatusOK {
		t.Fatalf("richtiges Token: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var body map[string]json.RawMessage
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort ist kein JSON-Objekt: %v — %s", err, w.Body.String())
	}
	for _, feld := range []string{"jobs", "running", "timezone"} {
		if _, ok := body[feld]; !ok {
			t.Errorf("voller Status muss Feld %q tragen, bekommen %s", feld, w.Body.String())
		}
	}
}

// AC-2: ohne Header, falsches Token, leerer Header-Wert, Praefix/Verlaengerung
// des Tokens und NUR ein gueltiges Sitzungscookie => jeweils 401.
func TestStatusToken_MissingOrWrongOrSessionOnly_Returns401(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token})

	faelle := []struct {
		name   string
		header *string
		user   string
	}{
		{"ohne Header", nil, ""},
		{"falsches Token", str("falsch"), ""},
		{"leerer Header-Wert", str(""), ""},
		{"Praefix des Tokens", str(s2Token[:len(s2Token)-1]), ""},
		{"Token plus ein Zeichen", str(s2Token + "x"), ""},
		{"nur Sitzungscookie (alice)", nil, "alice"},
		{"Sitzungscookie + falsches Token", str("falsch"), "alice"},
	}
	for _, f := range faelle {
		pruefe401(t, f.name, statusAbruf(t, r, secret, f.header, f.user))
	}
}

// AC-3: GZ_STATUS_TOKEN leer => fail-closed. Weder ein leerer noch ein
// beliebiger Header-Wert oeffnet den Endpunkt.
func TestStatusToken_EmptyConfiguredToken_AlwaysLocked(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: ""})

	faelle := []struct {
		name   string
		header *string
		user   string
	}{
		{"ohne Header", nil, ""},
		{"leerer Header-Wert (== konfiguriertes Token)", str(""), ""},
		{"beliebiger Wert", str(s2Token), ""},
		{"nur Sitzungscookie", nil, "alice"},
	}
	for _, f := range faelle {
		pruefe401(t, "Token nicht konfiguriert, "+f.name, statusAbruf(t, r, secret, f.header, f.user))
	}
}
