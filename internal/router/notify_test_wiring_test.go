package router

// Issue #2521 S2 (Fix-Loop 1, F001): die Router-Verdrahtung von
// POST /api/notify/test auf NotifyTestHandler wird dort bewacht, wo sie WIRKT —
// am vollstaendig verdrahteten Produktions-Router. Der Handler-Test allein
// beweist nicht, dass der Router ihn auch einhaengt (Mutation: zurueck auf den
// reinen ProxyPostHandler -> Antwort identisch, aber test_mail_sent_at fehlt).
//
// Python-Core ist ein echter httptest-Server (kein Mock-Objekt): er antwortet
// wie der Core mit HTTP 200 und {"status":"ok","channel":"email"}.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

func newNotifyWiringRouter(t *testing.T, coreURL string) (http.Handler, *store.Store, string) {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = coreURL
	s := store.New(cfg.DataDir, cfg.UserID)
	for _, id := range []string{"userA", "userB"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}
	wa, err := webauthn.New(&webauthn.Config{
		RPID: cfg.WebAuthnRPID, RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins: []string{"http://localhost:5173"},
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
		Config: cfg, Store: s, WebAuthn: wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, s, cfg.SessionSecret
}

func rawTestMailSentAt(t *testing.T, s *store.Store, id string) (string, bool) {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json %s: %v", id, err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("user.json %s kein JSON: %v", id, err)
	}
	v, ok := m["test_mail_sent_at"]
	return string(v), ok
}

// AC-8/AC-9 (Verdrahtung): Testmail ueber den ECHTEN Router setzt
// test_mail_sent_at im Profil des Aufrufers (userA), nicht bei userB.
func TestNotifyTestRouteStampsTestMailSentAtForCaller(t *testing.T) {
	core := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok","channel":"email"}`))
	}))
	defer core.Close()
	r, s, secret := newNotifyWiringRouter(t, core.URL)

	if _, ok := rawTestMailSentAt(t, s, "userA"); ok {
		t.Fatalf("Vorbedingung: userA hat schon test_mail_sent_at")
	}

	w := doBriefingRequest(t, r, http.MethodPost, "/api/notify/test",
		[]byte(`{"channel":"email"}`), sessionCookieFor("userA", secret))
	if w.Code != http.StatusOK {
		t.Fatalf("POST /api/notify/test: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	if v, ok := rawTestMailSentAt(t, s, "userA"); !ok || v == "" || v == "null" {
		t.Errorf("Router-Verdrahtung: test_mail_sent_at von userA nach erfolgreicher Testmail nicht gesetzt (%q, vorhanden=%v) — "+
			"/api/notify/test haengt nicht am NotifyTestHandler", v, ok)
	}
	if v, ok := rawTestMailSentAt(t, s, "userB"); ok {
		t.Errorf("Cross-User: userB bekam test_mail_sent_at=%s durch As Testmail", v)
	}
}
