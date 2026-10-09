package router

// TDD RED — Issue #2159 AC-1/AC-2/AC-3/AC-4: die zwei internen Endpunkte
// haengen hinter coreauth.RequireCoreAuth. Gemessen am ECHTEN Router, mit
// Store aus zwei Nutzern; bei 401/503 muss der Datenbestand byte-gleich bleiben.
//
// Diese Datei nutzt nur heute existierende Symbole: RED ist die Bug-
// Reproduktion (heute antwortet die Route ohne Header NICHT mit 401).

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const internalSecret = "core-shared-secret-fuer-tests-0123456789"

var internalPaths = []string{"/api/internal/telegram-connect", "/api/internal/premium-sms-learn"}

type internalFixture struct {
	r      chi.Router
	cfg    *config.Config
	tokenA string
}

func newInternalRouter(t *testing.T, secret string) internalFixture {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.CoreSharedSecret = secret
	cfg.SMTPHost, cfg.GoogleSMTPHost, cfg.FallbackSMTPHost = "", "", ""
	s := store.New(cfg.DataDir, cfg.UserID)

	for _, u := range []model.User{
		{ID: "intuser-a", Tier: "premium", Email: "a@example.invalid", CreatedAt: time.Now()},
		{ID: "intuser-b", Tier: "premium", Email: "b@example.invalid", CreatedAt: time.Now()},
	} {
		if err := s.SaveUser(u); err != nil {
			t.Fatalf("SaveUser: %v", err)
		}
	}
	ts := handler.NewTelegramTokenStore(cfg.DataDir)
	tokenA, err := ts.IssueToken("intuser-a")
	if err != nil {
		t.Fatalf("IssueToken: %v", err)
	}

	wa, err := webauthn.New(&webauthn.Config{RPID: cfg.WebAuthnRPID, RPDisplayName: cfg.WebAuthnRPDisplayName, RPOrigins: []string{"http://localhost:5173"}})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config: cfg, Store: s, WebAuthn: wa, ChallengeStore: handler.NewChallengeStore(),
		Scheduler: sched, TelegramTokenStore: ts, GitCommit: "test",
	})
	return internalFixture{r: r, cfg: cfg, tokenA: tokenA}
}

// snapshotDataDir hasht jede Datei unter dem Datenverzeichnis.
func snapshotDataDir(t *testing.T, dir string) map[string][32]byte {
	t.Helper()
	out := map[string][32]byte{}
	err := filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		b, rerr := os.ReadFile(p)
		if rerr != nil {
			return rerr
		}
		out[p] = sha256.Sum256(b)
		return nil
	})
	if err != nil {
		t.Fatalf("Snapshot: %v", err)
	}
	return out
}

func sameSnapshot(a, b map[string][32]byte) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if bv, ok := b[k]; !ok || bv != v {
			return false
		}
	}
	return true
}

func internalBody(f internalFixture, path string) []byte {
	if path == "/api/internal/telegram-connect" {
		b, _ := json.Marshal(map[string]string{"token": f.tokenA, "chat_id": "424242"})
		return b
	}
	b, _ := json.Marshal(map[string]string{"from": "4917000000001", "code": "000000"})
	return b
}

func callInternal(f internalFixture, path string, headers map[string]string) int {
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(internalBody(f, path)))
	req.Header.Set("Content-Type", "application/json")
	req.RemoteAddr = "127.0.0.1:50000"
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rr := httptest.NewRecorder()
	f.r.ServeHTTP(rr, req)
	return rr.Code
}

// AC-1 + AC-2: ohne bzw. mit falschem Header => 401, Datenbestand unveraendert.
func TestInternalRoutes_OhneUndMitFalschemHeaderIst401UndStoreUnveraendert(t *testing.T) {
	for _, path := range internalPaths {
		for name, hdr := range map[string]map[string]string{
			"ohne Header":   nil,
			"falscher Wert": {"X-GZ-Core-Auth": internalSecret + "x"},
			"leerer Wert":   {"X-GZ-Core-Auth": ""},
		} {
			// Frischer Aufbau je Fall: heute veraendert ein ungeschuetzter
			// Aufruf den Bestand (Token wird eingeloest), das darf spaetere
			// Faelle nicht verfaelschen.
			f := newInternalRouter(t, internalSecret)
			before := snapshotDataDir(t, f.cfg.DataDir)
			if code := callInternal(f, path, hdr); code != http.StatusUnauthorized {
				t.Errorf("%s %s: erwartet 401, bekam %d", path, name, code)
			}
			if after := snapshotDataDir(t, f.cfg.DataDir); !sameSnapshot(before, after) {
				t.Errorf("%s %s: Datenbestand (zwei Nutzer + Token-Store) hat sich trotz fehlender Berechtigung veraendert", path, name)
			}
		}
	}
}

// AC-3: leeres Go-Secret => 503, auch mit leerem Header, nichts veraendert.
func TestInternalRoutes_LeeresSecretIst503UndStoreUnveraendert(t *testing.T) {
	for _, path := range internalPaths {
		for name, hdr := range map[string]map[string]string{
			"ohne Header":  nil,
			"leerer Wert":  {"X-GZ-Core-Auth": ""},
			"anderer Wert": {"X-GZ-Core-Auth": "irgendwas"},
		} {
			f := newInternalRouter(t, "")
			before := snapshotDataDir(t, f.cfg.DataDir)
			if code := callInternal(f, path, hdr); code != http.StatusServiceUnavailable {
				t.Errorf("%s %s: erwartet 503, bekam %d", path, name, code)
			}
			if after := snapshotDataDir(t, f.cfg.DataDir); !sameSnapshot(before, after) {
				t.Errorf("%s %s: Datenbestand hat sich trotz 503 veraendert", path, name)
			}
		}
	}
}

// AC-4: richtiger Header von Loopback => heutiges Verhalten (Handler laeuft).
func TestInternalRoutes_RichtigerHeaderLaesstHandlerLaufen(t *testing.T) {
	f := newInternalRouter(t, internalSecret)
	hdr := map[string]string{"X-GZ-Core-Auth": internalSecret}

	if code := callInternal(f, "/api/internal/telegram-connect", hdr); code != http.StatusOK {
		t.Errorf("telegram-connect mit gueltigem Token: erwartet 200, bekam %d", code)
	}
	// Learn mit unpassendem Code: Handler lehnt fachlich ab, aber NICHT per 401/503/403.
	code := callInternal(f, "/api/internal/premium-sms-learn", hdr)
	if code == http.StatusUnauthorized || code == http.StatusServiceUnavailable || code == http.StatusForbidden {
		t.Errorf("premium-sms-learn mit richtigem Header: Middleware/Guard hat abgelehnt (%d)", code)
	}
}

// AC-4: nginx-Header + richtiger Header => weiterhin 403 (requireLocalOnly).
func TestInternalRoutes_NginxHeaderMitRichtigemSecretBleibt403(t *testing.T) {
	for _, path := range internalPaths {
		f := newInternalRouter(t, internalSecret)
		before := snapshotDataDir(t, f.cfg.DataDir)
		hdr := map[string]string{"X-GZ-Core-Auth": internalSecret, "X-Real-IP": "203.0.113.9", "X-Forwarded-For": "203.0.113.9"}
		if code := callInternal(f, path, hdr); code != http.StatusForbidden {
			t.Errorf("%s: erwartet 403, bekam %d", path, code)
		}
		if after := snapshotDataDir(t, f.cfg.DataDir); !sameSnapshot(before, after) {
			t.Errorf("%s: Datenbestand hat sich trotz 403 veraendert", path)
		}
	}
}
