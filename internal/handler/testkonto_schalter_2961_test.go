package handler

// Issue #2961 (GA4) — Testkonto-Schalter und Kontoanlage.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-7 bis AC-11).
//
// Echter RegisterHandler gegen einen echten Store in t.TempDir(); geprueft
// werden Antwort und Plattenzustand (Kontoordner, user.json).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const schalterSecret2961 = "schalter-2961-secret-32-zeichen!"

func registriere2961(t *testing.T, s *store.Store, cfg config.Config, rumpf string, cookie *http.Cookie) *httptest.ResponseRecorder {
	return registriereMitKosten2961(t, s, cfg, rumpf, cookie, bcrypt.MinCost)
}

func registriereMitKosten2961(t *testing.T, s *store.Store, cfg config.Config, rumpf string, cookie *http.Cookie, kosten int) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(rumpf))
	req.Header.Set("Content-Type", "application/json")
	if cookie != nil {
		req.AddCookie(cookie)
	}
	w := httptest.NewRecorder()
	RegisterHandlerWithInvites(s, kosten, cfg, nil).ServeHTTP(w, req)
	return w
}

func testkontoRumpf2961(id string) string {
	return `{"username":"` + id + `","password":"geheim-pw-123","email":"` + id + `@beispiel.de","is_test_user":true}`
}

func antwortCode2961(w *httptest.ResponseRecorder) string {
	var b map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &b)
	c, _ := b["code"].(string)
	return c
}

func sitzungFuer2961(t *testing.T, s *store.Store, uid string) *http.Cookie {
	t.Helper()
	now := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: uid, Email: uid + "@beispiel.de", CreatedAt: now, EmailVerifiedAt: &now}); err != nil {
		t.Fatal(err)
	}
	sid, err := middleware.NewSessionID()
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(uid, sid); err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID(uid, sid, schalterSecret2961)}
}

// AC-7: In Produktion (weder Staging noch Fixture-Modus) wird der Schalter
// ohne Admin-Sitzung abgelehnt — 400 validation_failed, kein Konto.
func TestTestkontoSchalter_ProduktionOhneAdminAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{SessionSecret: schalterSecret2961, AdminUserIDs: "chef"}

	w := registriere2961(t, s, cfg, testkontoRumpf2961("wunschid"), nil)
	if w.Code != http.StatusBadRequest || antwortCode2961(w) != "validation_failed" {
		t.Fatalf("erwartet 400 validation_failed, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, err := os.Stat(s.UserDir("wunschid")); !os.IsNotExist(err) {
		t.Fatalf("es darf kein Kontoordner entstehen (err=%v)", err)
	}
	if ids, _ := s.ListUserIDs(); len(ids) != 0 {
		t.Fatalf("es darf kein Konto entstehen, vorhanden: %v", ids)
	}

	// Eine gewoehnliche (Nicht-Admin-)Sitzung reicht nicht.
	c := sitzungFuer2961(t, s, "normalo")
	if w := registriere2961(t, s, cfg, testkontoRumpf2961("wunschid"), c); w.Code != http.StatusBadRequest {
		t.Fatalf("Nicht-Admin: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Gegenprobe: ohne Schalter klappt die Registrierung (opake Kennung).
	if w := registriere2961(t, s, cfg, `{"username":"egal","password":"geheim-pw-123","email":"neu@beispiel.de"}`, nil); w.Code != http.StatusCreated {
		t.Fatalf("Registrierung ohne Schalter: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-8: Staging, Fixture-Modus und Admin-Sitzung duerfen Testkonten anlegen.
func TestTestkontoSchalter_StagingFixtureUndAdminErlaubt(t *testing.T) {
	s := newTestStore(t)
	faelle := []struct {
		name  string
		cfg   config.Config
		id    string
		admin bool
	}{
		{"staging", config.Config{SessionSecret: schalterSecret2961, Env: "staging"}, "stagingtest", false},
		{"fixture", config.Config{SessionSecret: schalterSecret2961, TestFixtureDir: t.TempDir()}, "fixturetest", false},
		{"admin", config.Config{SessionSecret: schalterSecret2961, AdminUserIDs: "chef"}, "admintest", true},
	}
	for _, f := range faelle {
		var c *http.Cookie
		if f.admin {
			c = sitzungFuer2961(t, s, "chef")
		}
		w := registriere2961(t, s, f.cfg, testkontoRumpf2961(f.id), c)
		if w.Code != http.StatusCreated {
			t.Fatalf("%s: erwartet 201, bekommen %d: %s", f.name, w.Code, w.Body.String())
		}
		u, err := s.LoadUser(f.id)
		if err != nil || u == nil || !u.IsTestUser {
			t.Fatalf("%s: Testkonto %q mit is_test_user erwartet (u=%v, err=%v)", f.name, f.id, u, err)
		}
	}
}

// AC-9: Ein vorhandener Kontoordner ohne user.json gilt als belegt — die
// Registrierung uebernimmt keine verwaisten Daten.
func TestTestkontoSchalter_VerwaisterOrdnerIstBelegt(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{SessionSecret: schalterSecret2961, Env: "staging"}
	alt := filepath.Join(s.UserDir("verwaist"), "trips")
	if err := os.MkdirAll(alt, 0o770); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(alt, "t1.json"), []byte(`{"id":"t1"}`), 0o660); err != nil {
		t.Fatal(err)
	}
	if s.UserExists("verwaist") != true {
		t.Errorf("UserExists muss einen vorhandenen Kontoordner als belegt melden")
	}

	w := registriere2961(t, s, cfg, testkontoRumpf2961("verwaist"), nil)
	if w.Code != http.StatusConflict || antwortCode2961(w) != "user_already_exists" {
		t.Fatalf("erwartet 409 user_already_exists, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, err := os.Stat(filepath.Join(s.UserDir("verwaist"), "user.json")); !os.IsNotExist(err) {
		t.Fatalf("im verwaisten Ordner darf keine user.json entstehen (err=%v)", err)
	}
}

// AC-10: Reservierte Kennungen sind nie registrierbar, auch nicht im Staging.
func TestTestkontoSchalter_ReservierteKennungAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{SessionSecret: schalterSecret2961, Env: "staging"}
	for _, id := range []string{"default", "admin", "root", "system"} {
		w := registriere2961(t, s, cfg, testkontoRumpf2961(id), nil)
		if w.Code != http.StatusBadRequest || antwortCode2961(w) != "validation_failed" {
			t.Fatalf("%q: erwartet 400 validation_failed, bekommen %d: %s", id, w.Code, w.Body.String())
		}
		if _, err := os.Stat(s.UserDir(id)); !os.IsNotExist(err) {
			t.Fatalf("%q: es darf kein Kontoordner entstehen", id)
		}
	}
}

// AC-11: Zwei gleichzeitige Registrierungen derselben Kennung — genau eine
// gewinnt, alle anderen bekommen 409.
func TestTestkontoSchalter_KontoanlageIstExklusiv(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{SessionSecret: schalterSecret2961, Env: "staging"}
	const n = 12
	codes := make([]int, n)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			rumpf := `{"username":"gleichzeitig","password":"geheim-pw-123","email":"g` +
				string(rune('a'+i)) + `@beispiel.de","is_test_user":true}`
			// Volle bcrypt-Kosten: alle Anfragen stehen gleichzeitig vor dem Anlegen.
			codes[i] = registriereMitKosten2961(t, s, cfg, rumpf, nil, bcrypt.DefaultCost).Code
		}(i)
	}
	wg.Wait()
	gewonnen := 0
	for i, c := range codes {
		switch c {
		case http.StatusCreated:
			gewonnen++
		case http.StatusConflict:
		default:
			t.Errorf("Anfrage %d: unerwarteter Status %d", i, c)
		}
	}
	if gewonnen != 1 {
		t.Fatalf("genau eine Registrierung darf gewinnen, gewonnen: %d (%v)", gewonnen, codes)
	}
}
