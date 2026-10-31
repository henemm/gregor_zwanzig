package middleware_test

// Issue #2675 (i18n G1) — Sprach-Middleware mit zwei Nutzern, Cookie gz_lang.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-4, AC-6.
//
// Externes Testpaket, damit die echten Handler (handler-Paket importiert
// middleware) ohne Zyklus verwendet werden koennen. Echter Store in
// t.TempDir(), echte Sitzungen, echte Middleware-Kette, keine Mocks.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const sprachSecret = "test-secret-32-chars-long-enough!"

// schreibeNutzer legt user.json roh an (language nur, wenn gesetzt).
func schreibeNutzer(t *testing.T, s *store.Store, id, lang, hash string) {
	t.Helper()
	m := map[string]any{
		"id": id, "email": id + "@example.com", "password_hash": hash,
		"email_verified_at": "2026-04-15T00:00:00Z", "created_at": "2026-04-15T00:00:00Z",
	}
	if lang != "" {
		m["language"] = lang
	}
	data, _ := json.MarshalIndent(m, "", "  ")
	if err := os.MkdirAll(s.UserDir(id), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(s.UserDir(id), "user.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func sitzung(t *testing.T, s *store.Store, id string) *http.Cookie {
	t.Helper()
	sid, err := middleware.NewSessionID()
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(id, sid); err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID(id, sid, sprachSecret)}
}

func userJSON(t *testing.T, s *store.Store, id string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatal(err)
	}
	return data
}

// kette baut die Produktions-Reihenfolge: Auth -> Lang -> echter Briefing-Handler.
func kette(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.AuthMiddleware(sprachSecret, s))
	r.Use(middleware.Lang(s))
	r.Get("/api/briefings/{id}", handler.GetBriefingHandler(s))
	return r
}

func fehlerMeldung(t *testing.T, w *httptest.ResponseRecorder) (string, string) {
	t.Helper()
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort kein JSON: %v (%s)", err, w.Body.String())
	}
	code, _ := body["code"].(string)
	msg, _ := body["message"].(string)
	return code, msg
}

// AC-4: zwei Nutzer, parallele Anfragen, jeder nur seine Sprache, user.json unveraendert.
func TestZweiNutzerParallelJeEigeneSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	schreibeNutzer(t, s, "anna-en", "en", "x")
	schreibeNutzer(t, s, "bert-de", "de", "x")
	vorA, vorB := userJSON(t, s, "anna-en"), userJSON(t, s, "bert-de")
	cA, cB := sitzung(t, s, "anna-en"), sitzung(t, s, "bert-de")
	h := kette(s)

	const runden = 40
	var wg sync.WaitGroup
	fehler := make(chan string, 2*runden)
	for i := 0; i < runden; i++ {
		for _, tc := range []struct {
			c    *http.Cookie
			want string
			acc  string
		}{{cA, "Not found.", "de"}, {cB, "Nicht gefunden.", "en"}} {
			wg.Add(1)
			go func(c *http.Cookie, want, acc string) {
				defer wg.Done()
				req := httptest.NewRequest(http.MethodGet, "/api/briefings/unbekannt?kind=route", nil)
				req.AddCookie(c)
				req.Header.Set("Accept-Language", acc)
				w := httptest.NewRecorder()
				h.ServeHTTP(w, req)
				var body map[string]any
				_ = json.Unmarshal(w.Body.Bytes(), &body)
				if w.Code != http.StatusNotFound || body["message"] != want {
					fehler <- c.Value[:6] + ": " + w.Body.String()
				}
			}(tc.c, tc.want, tc.acc)
		}
	}
	wg.Wait()
	close(fehler)
	for f := range fehler {
		t.Errorf("AC-4: falsche Sprache/Antwort: %s", f)
	}
	if !bytes.Equal(vorA, userJSON(t, s, "anna-en")) || !bytes.Equal(vorB, userJSON(t, s, "bert-de")) {
		t.Errorf("AC-4: user.json eines Nutzers hat sich durch Lese-Anfragen veraendert")
	}
}

// zaehlLader zaehlt LoadUser-Aufrufe am echten Store (kein Spiegel-Mock).
type zaehlLader struct {
	s     *store.Store
	mu    sync.Mutex
	calls []string
}

func (z *zaehlLader) LoadUser(id string) (*model.User, error) {
	z.mu.Lock()
	z.calls = append(z.calls, id)
	z.mu.Unlock()
	return z.s.LoadUser(id)
}

func spracheDurchLang(users middleware.UserLoader, req *http.Request) (i18n.Lang, int) {
	var got i18n.Lang
	h := middleware.Lang(users)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = i18n.FromContext(r.Context())
	}))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return got, w.Code
}

// Ohne Nutzerkennung wird nichts geladen (nie "default"); Header entscheidet.
func TestLangOhneNutzerLaedtNichts(t *testing.T) {
	z := &zaehlLader{s: store.New(t.TempDir(), "")}
	schreibeNutzer(t, z.s, "default", "en", "x")
	req := httptest.NewRequest(http.MethodGet, "/api/health", nil)
	req.Header.Set("Accept-Language", "de")
	lang, _ := spracheDurchLang(z, req)
	if lang != i18n.De {
		t.Errorf("oeffentliche Anfrage: Sprache %q, erwartet de (Header)", lang)
	}
	if len(z.calls) != 0 {
		t.Errorf("ohne Nutzerkennung wurde LoadUser aufgerufen: %v", z.calls)
	}
}

// Die Middleware laedt genau die Kennung aus dem Auth-Kontext.
func TestLangLaedtNurNutzerAusKontext(t *testing.T) {
	z := &zaehlLader{s: store.New(t.TempDir(), "")}
	schreibeNutzer(t, z.s, "anna-en", "en", "x")
	req := httptest.NewRequest(http.MethodGet, "/api/briefings", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "anna-en"))
	if lang, _ := spracheDurchLang(z, req); lang != i18n.En {
		t.Errorf("Sprache %q, erwartet en", lang)
	}
	if len(z.calls) != 1 || z.calls[0] != "anna-en" {
		t.Errorf("LoadUser-Aufrufe %v, erwartet genau [anna-en]", z.calls)
	}
}

// Ladefehler (kaputte user.json) bricht die Anfrage nicht ab: Cookie/Header gelten.
func TestLangLadefehlerBrichtNichtAb(t *testing.T) {
	s := store.New(t.TempDir(), "")
	_ = os.MkdirAll(s.UserDir("kaputt"), 0o755)
	_ = os.WriteFile(filepath.Join(s.UserDir("kaputt"), "user.json"), []byte("{kein json"), 0o644)
	req := httptest.NewRequest(http.MethodGet, "/api/briefings", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "kaputt"))
	req.Header.Set("Accept-Language", "en")
	lang, code := spracheDurchLang(s, req)
	if lang != i18n.En || code != http.StatusOK {
		t.Errorf("Ladefehler: Sprache %q Status %d, erwartet en/200", lang, code)
	}
}

func langCookieAus(w *httptest.ResponseRecorder) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_lang" {
			return c
		}
	}
	return nil
}

func pruefeLangCookie(t *testing.T, ac string, w *httptest.ResponseRecorder, want string, secure bool) {
	t.Helper()
	c := langCookieAus(w)
	if want == "" {
		if c != nil {
			t.Errorf("%s: Nutzer ohne Sprache bekommt gz_lang=%q", ac, c.Value)
		}
		return
	}
	if c == nil {
		t.Fatalf("%s: kein gz_lang (Set-Cookie %v)", ac, w.Header().Values("Set-Cookie"))
	}
	if c.Value != want || c.Path != "/" || c.MaxAge != 31536000 || c.SameSite != http.SameSiteLaxMode || c.HttpOnly || c.Secure != secure {
		t.Errorf("%s: Cookie %+v, erwartet %s, Path=/, Max-Age=31536000, Lax, nicht HttpOnly, Secure=%v", ac, c, want, secure)
	}
	if n := strings.Count(strings.Join(w.Header().Values("Set-Cookie"), "\n"), "gz_lang="); n != 1 {
		t.Errorf("%s: gz_lang %d-mal gesetzt, erwartet 1", ac, n)
	}
}

// AC-6: Login setzt gz_lang nur bei gespeicherter Sprache (zwei Nutzer).
func TestLoginSetztSprachCookieNurMitGespeicherterSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	schreibeNutzer(t, s, "anna-en", "en", string(hash))
	schreibeNutzer(t, s, "carl-ohne", "", string(hash))
	for _, tc := range []struct {
		uid, host, want string
		secure          bool
	}{
		{"anna-en", "https://gregor20.henemm.com", "en", true},
		{"anna-en", "http://localhost:4173", "en", false},
		{"carl-ohne", "https://gregor20.henemm.com", "", true},
	} {
		w := httptest.NewRecorder()
		body := `{"username":"` + tc.uid + `","password":"geheim123"}`
		handler.LoginHandler(s, sprachSecret, tc.host).ServeHTTP(w,
			httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(body)))
		if w.Code != http.StatusOK {
			t.Fatalf("Login %s: %d %s", tc.uid, w.Code, w.Body.String())
		}
		pruefeLangCookie(t, "AC-6 Login "+tc.uid+" "+tc.host, w, tc.want, tc.secure)
	}
}

// AC-6: Registrierung mit und ohne Sprache.
func TestRegisterSetztSprachCookieNurMitSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	cfg := config.Config{PublicHost: "https://gregor20.henemm.com"} // ohne SMTP: kein Versand
	inv := store.NewInviteStore(t.TempDir())
	for _, tc := range []struct{ uid, extra, want string }{
		{"dora-en", `,"language":"en"`, "en"},
		{"emil-ohne", ``, ""},
	} {
		body := `{"username":"` + tc.uid + `","password":"geheim-pw-123","email":"` + tc.uid + `@beispiel.de"` + tc.extra + `}`
		w := httptest.NewRecorder()
		handler.RegisterHandlerWithInvites(s, 4, cfg, inv).ServeHTTP(w,
			httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body)))
		if w.Code != http.StatusCreated {
			t.Fatalf("Register %s: %d %s", tc.uid, w.Code, w.Body.String())
		}
		pruefeLangCookie(t, "AC-6 Register "+tc.uid, w, tc.want, true)
	}
}

// AC-6: Profil-Update setzt gz_lang mit der gespeicherten Sprache.
func TestProfilUpdateSetztSprachCookieMitGespeicherterSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	schreibeNutzer(t, s, "anna-en", "en", "x")
	schreibeNutzer(t, s, "carl-ohne", "", "x")
	limiter := handler.NewMailFloodLimiter(1000, time.Hour)
	for _, tc := range []struct{ uid, body, want string }{
		{"anna-en", `{"display_name":"Anna"}`, "en"},
		{"carl-ohne", `{"display_name":"Carl"}`, ""},
		{"carl-ohne", `{"language":"en"}`, "en"},
	} {
		req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(tc.body))
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), tc.uid))
		w := httptest.NewRecorder()
		handler.UpdateProfileHandler(s, config.Config{PublicHost: "http://localhost:4173"}, limiter, limiter).ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("Profil %s: %d %s", tc.uid, w.Code, w.Body.String())
		}
		pruefeLangCookie(t, "AC-6 Profil "+tc.uid+" "+tc.body, w, tc.want, false)
	}
}

// SetLangCookie: Secure genau bei https.
func TestSetLangCookieAttribute(t *testing.T) {
	for host, secure := range map[string]bool{"https://gregor20.henemm.com": true, "http://localhost:4173": false} {
		w := httptest.NewRecorder()
		middleware.SetLangCookie(w, httptest.NewRequest(http.MethodGet, "/", nil), i18n.En, host)
		pruefeLangCookie(t, "SetLangCookie "+host, w, "en", secure)
	}
}
