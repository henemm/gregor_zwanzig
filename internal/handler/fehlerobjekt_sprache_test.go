package handler

// Issue #2675 (i18n G1) — Fehlerobjekt {code, message} in Nutzersprache.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-1, AC-2.
//
// Echter chi-Router mit AuthMiddleware und Lang (Produktions-Reihenfolge),
// echtes Nutzerverzeichnis in t.TempDir(), echte Sitzungen. Gemessen wird der
// ausgelieferte JSON-Body.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

const fehlerSecret = "test-secret-32-chars-long-enough!"

func fehlerSitzung(t *testing.T, s *store.Store, id, lang string) *http.Cookie {
	t.Helper()
	m := map[string]interface{}{"id": id, "email": id + "@example.com", "created_at": "2026-04-15T00:00:00Z"}
	if lang != "" {
		m["language"] = lang
	}
	onbWriteRawUser(t, s, id, m)
	sid, err := middleware.NewSessionID()
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(id, sid); err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID(id, sid, fehlerSecret)}
}

// fehlerRouter: Auth -> Lang -> echte Briefing-Route und ein oeffentlicher
// Test-Endpunkt (Pfad aus der Public-Allowlist), der WriteError aufruft.
func fehlerRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.AuthMiddleware(fehlerSecret, s))
	r.Use(middleware.Lang(s))
	r.Get("/api/briefings/{id}", GetBriefingHandler(s))
	r.Get("/api/health", func(w http.ResponseWriter, r *http.Request) {
		WriteError(w, r, http.StatusNotFound, "not_found", nil)
	})
	return r
}

func fehlerAufruf(t *testing.T, h http.Handler, path string, c *http.Cookie, accept string) (int, map[string]any) {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if c != nil {
		req.AddCookie(c)
	}
	if accept != "" {
		req.Header.Set("Accept-Language", accept)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("%s: Content-Type %q, erwartet application/json", path, ct)
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("%s: Antwort kein JSON: %v (%s)", path, err, w.Body.String())
	}
	return w.Code, body
}

// AC-1: Nutzer en -> 404, code not_found, message "Not found.", error weiter not_found.
func TestBriefingNichtGefundenEnglischFuerEnNutzer(t *testing.T) {
	s := newTestStore(t)
	h := fehlerRouter(s)
	c := fehlerSitzung(t, s, "anna-en", "en")
	code, body := fehlerAufruf(t, h, "/api/briefings/unbekannt?kind=route", c, "de")
	if code != http.StatusNotFound {
		t.Fatalf("AC-1: Status %d, erwartet 404 (%v)", code, body)
	}
	if body["code"] != "not_found" || body["message"] != "Not found." || body["error"] != "not_found" {
		t.Errorf("AC-1: Body %v, erwartet code/error not_found und message \"Not found.\"", body)
	}
	if body["detail"] != "Not found." {
		t.Errorf("AC-1: detail=%v, erwartet message", body["detail"])
	}
	// Auch der vergleich-Zweig nutzt denselben Fehlerpfad (Trip/Ortsvergleich-Teilung).
	_, body = fehlerAufruf(t, h, "/api/briefings/unbekannt?kind=vergleich", c, "de")
	if body["message"] != "Not found." {
		t.Errorf("AC-1 vergleich: message=%v, erwartet \"Not found.\"", body["message"])
	}
}

// AC-2: Nutzer de und Besucher mit Accept-Language de -> deutsch; en-US -> englisch.
func TestFehlermeldungDeutschFuerDeNutzerUndBesucher(t *testing.T) {
	s := newTestStore(t)
	h := fehlerRouter(s)
	cDe := fehlerSitzung(t, s, "bert-de", "de")
	cOhne := fehlerSitzung(t, s, "carl-ohne", "")

	cases := []struct {
		name, path, accept string
		c                  *http.Cookie
		want               string
	}{
		{"Nutzer de (Header en)", "/api/briefings/unbekannt?kind=route", "en", cDe, "Nicht gefunden."},
		{"Nutzer ohne Sprache, Header de", "/api/briefings/unbekannt?kind=route", "de", cOhne, "Nicht gefunden."},
		{"Besucher de", "/api/health", "de", nil, "Nicht gefunden."},
		{"Besucher ohne Header", "/api/health", "", nil, "Nicht gefunden."},
		{"Besucher en-US", "/api/health", "en-US,en;q=0.9,de;q=0.8", nil, "Not found."},
	}
	for _, tc := range cases {
		code, body := fehlerAufruf(t, h, tc.path, tc.c, tc.accept)
		if code != http.StatusNotFound || body["message"] != tc.want || body["code"] != "not_found" {
			t.Errorf("AC-2 %s: %d %v, erwartet 404 message %q", tc.name, code, body, tc.want)
		}
	}
}

// Besucher-Cookie gz_lang gilt vor Accept-Language (oeffentliche Route).
func TestBesucherCookieVorHeader(t *testing.T) {
	h := fehlerRouter(newTestStore(t))
	_, body := fehlerAufruf(t, h, "/api/health", &http.Cookie{Name: "gz_lang", Value: "en"}, "de")
	if body["message"] != "Not found." {
		t.Errorf("Cookie en vor Header de: message=%v", body["message"])
	}
}

// WriteErrorWith: Zusatzfelder, vom Aufrufer gesetzte Header bleiben, Sprache aus dem Kontext.
func TestWriteErrorWithZusatzfelderUndHeader(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/x", nil)
	req = req.WithContext(i18n.WithLang(req.Context(), i18n.En))
	w := httptest.NewRecorder()
	w.Header().Set("Retry-After", "60")
	WriteErrorWith(w, req, http.StatusTooManyRequests, "rate_limit_exceeded", nil, map[string]any{"resource": "trips"})
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if w.Code != http.StatusTooManyRequests || w.Header().Get("Retry-After") != "60" {
		t.Errorf("Status %d Retry-After %q", w.Code, w.Header().Get("Retry-After"))
	}
	if body["resource"] != "trips" || body["message"] != "Too many requests. Please try again later." || body["code"] != "rate_limit_exceeded" {
		t.Errorf("Body %v", body)
	}
}

// Ohne Sprach-Middleware (direkter Aufruf) faellt WriteError auf de zurueck;
// unbekannter Code -> fehler.unbekannt mit {code}.
func TestWriteErrorOhneMiddlewareDeutschUndUnbekannterCode(t *testing.T) {
	w := httptest.NewRecorder()
	WriteError(w, httptest.NewRequest(http.MethodGet, "/x", nil), http.StatusBadRequest, "ganz_neu", nil)
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["message"] != "Unbekannter Fehler (ganz_neu)." || body["code"] != "ganz_neu" || body["error"] != "ganz_neu" {
		t.Errorf("Body %v", body)
	}
}
