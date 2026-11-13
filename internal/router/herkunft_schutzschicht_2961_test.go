package router

// Issue #2961 (GA5/GA8) — globale Schutzschicht fuer schreibende Anfragen:
// Herkunftspruefung, JSON-Pflicht, Groessenbegrenzung.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-13 bis AC-18).
//
// Gemessen ueber den ECHTEN Produktions-Router (Verdrahtung inklusive).

import (
	"bytes"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
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

// schutzRouter2961 baut den echten Router mit Produktionsursprung
// https://gregor20.henemm.com (kein Staging, kein Fixture-Modus), mutate darf
// die Konfiguration vorher anpassen.
func schutzRouter2961(t *testing.T, mutate func(*config.Config)) (http.Handler, *store.Store, string) {
	t.Helper()
	t.Setenv("GZ_ENV", "")
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.SMTPHost, cfg.GoogleSMTPHost = "", ""
	cfg.Env, cfg.TestFixtureDir = "", ""
	cfg.PublicHost = "https://gregor20.henemm.com"
	cfg.WebAuthnRPOrigins = ""
	cfg.PythonCoreURL = "http://127.0.0.1:1"
	if mutate != nil {
		mutate(cfg)
	}
	s := store.New(cfg.DataDir, cfg.UserID)
	wa, err := webauthn.New(&webauthn.Config{RPID: "gregor20.henemm.com", RPDisplayName: "x",
		RPOrigins: []string{"https://gregor20.henemm.com"}})
	if err != nil {
		t.Fatal(err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(sched.Stop)
	r := New(Deps{Config: cfg, Store: s, WebAuthn: wa, ChallengeStore: handler.NewChallengeStore(),
		Scheduler: sched, TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir), GitCommit: "test"})
	return r, s, cfg.SessionSecret
}

func kontoMitSitzung2961(t *testing.T, s *store.Store, secret, uid string) *http.Cookie {
	t.Helper()
	now := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: uid, Email: uid + "@beispiel.de", CreatedAt: now, EmailVerifiedAt: &now}); err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(uid, sessionIDFor(uid)); err != nil {
		t.Fatal(err)
	}
	return sessionCookieFor(uid, secret)
}

type anfrage2961 struct {
	method, path, body, contentType string
	header                          map[string]string
	cookie                          *http.Cookie
	rawBody                         []byte
}

func schicke2961(t *testing.T, r http.Handler, a anfrage2961) *httptest.ResponseRecorder {
	t.Helper()
	var body *bytes.Reader
	if a.rawBody != nil {
		body = bytes.NewReader(a.rawBody)
	} else {
		body = bytes.NewReader([]byte(a.body))
	}
	req := httptest.NewRequest(a.method, a.path, body)
	if a.contentType != "" {
		req.Header.Set("Content-Type", a.contentType)
	}
	for k, v := range a.header {
		req.Header.Set(k, v)
	}
	if a.cookie != nil {
		req.AddCookie(a.cookie)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func code2961(w *httptest.ResponseRecorder) string {
	var b map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &b)
	c, _ := b["code"].(string)
	return c
}

const ortRumpf2961 = `{"name":"Testort","lat":47.1,"lon":11.2,"elevation_m":1000}`

// AC-13: fremder Origin bzw. Sec-Fetch-Site cross-site/same-site → 403
// origin_forbidden, die Aenderung findet nicht statt.
func TestHerkunft_FremdeHerkunftWirdAbgewiesen(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "herkunft1")
	faelle := []map[string]string{
		{"Origin": "https://angreifer.example"},
		{"Origin": "https://staging.gregor20.henemm.com"},
		{"Origin": "null"},
		{"Origin": "http://localhost:5173"},
		{"Sec-Fetch-Site": "cross-site"},
		{"Sec-Fetch-Site": "same-site"},
		{"Origin": "https://gregor20.henemm.com", "Sec-Fetch-Site": "cross-site"},
	}
	for _, h := range faelle {
		w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
			contentType: "application/json", header: h, cookie: c})
		if w.Code != http.StatusForbidden || code2961(w) != "origin_forbidden" {
			t.Fatalf("%v: erwartet 403 origin_forbidden, bekommen %d: %s", h, w.Code, w.Body.String())
		}
	}
	if locs, _ := s.WithUser("herkunft1").LoadLocations(); len(locs) != 0 {
		t.Fatalf("abgewiesene Anfragen duerfen nichts anlegen, vorhanden: %d", len(locs))
	}
	// Auch die oeffentliche Anmeldung ist geschuetzt (Login-Faelschung).
	w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/auth/login",
		body: `{"username":"herkunft1","password":"x"}`, contentType: "application/json",
		header: map[string]string{"Origin": "https://angreifer.example"}})
	if w.Code != http.StatusForbidden {
		t.Fatalf("Login mit fremder Herkunft: erwartet 403, bekommen %d", w.Code)
	}
}

// AC-14: eigener Ursprung, same-origin/none und fehlende Header (Server-zu-
// Server) werden durchgelassen; lesende Anfragen sind nicht betroffen.
func TestHerkunft_EigeneHerkunftUndServerAufrufeErlaubt(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "herkunft2")
	faelle := []map[string]string{
		{"Origin": "https://gregor20.henemm.com", "Sec-Fetch-Site": "same-origin"},
		{"Origin": "HTTPS://Gregor20.henemm.com"},
		{"Sec-Fetch-Site": "none"},
		nil,
	}
	for i, h := range faelle {
		rumpf := strings.Replace(ortRumpf2961, "Testort", "Ort "+string(rune('A'+i)), 1)
		w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: rumpf,
			contentType: "application/json", header: h, cookie: c})
		if w.Code != http.StatusCreated && w.Code != http.StatusOK {
			t.Fatalf("%v: erwartet Anlage, bekommen %d: %s", h, w.Code, w.Body.String())
		}
	}
	w := schicke2961(t, r, anfrage2961{method: http.MethodGet, path: "/api/locations",
		header: map[string]string{"Origin": "https://angreifer.example", "Sec-Fetch-Site": "cross-site"}, cookie: c})
	if w.Code != http.StatusOK {
		t.Fatalf("GET darf nicht abgewiesen werden, bekommen %d", w.Code)
	}
}

// AC-15: Maschinenpfade (Webhooks, interne Pfade) sind ausgenommen.
func TestHerkunft_MaschinenpfadeAusgenommen(t *testing.T) {
	r, _, _ := schutzRouter2961(t, nil)
	for _, p := range []string{"/api/webhooks/telegram/inbound", "/api/webhooks/mail/irgendwas",
		"/api/internal/telegram-connect"} {
		w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: p, body: "x=1",
			contentType: "application/x-www-form-urlencoded",
			header:      map[string]string{"Origin": "https://angreifer.example", "Sec-Fetch-Site": "cross-site"}})
		if c := code2961(w); c == "origin_forbidden" || c == "unsupported_media_type" {
			t.Fatalf("%s: Maschinenpfad darf nicht von der Schutzschicht abgewiesen werden (%d %s)", p, w.Code, w.Body.String())
		}
	}
}

// AC-14: im Fixture-Modus (CI-Stack, Playwright) und im Staging sind
// localhost-Urspruenge erlaubt — in Produktion nicht (AC-13).
func TestHerkunft_LoopbackNurImFixtureOderStaging(t *testing.T) {
	for _, m := range []func(*config.Config){
		func(c *config.Config) { c.TestFixtureDir = "fixtures/openmeteo" },
		func(c *config.Config) { c.Env = "staging" },
	} {
		r, s, secret := schutzRouter2961(t, m)
		c := kontoMitSitzung2961(t, s, secret, "loopback")
		for _, o := range []string{"http://localhost:4173", "http://127.0.0.1:5173"} {
			w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations",
				body: strings.Replace(ortRumpf2961, "Testort", o, 1), contentType: "application/json",
				header: map[string]string{"Origin": o, "Sec-Fetch-Site": "same-origin"}, cookie: c})
			if w.Code == http.StatusForbidden {
				t.Fatalf("%s: im Fixture-/Staging-Modus erwartet erlaubt, bekommen 403", o)
			}
		}
	}
}

// AC-16: JSON-Endpunkte mit Rumpf verlangen application/json (415 sonst);
// der GPX-Upload nimmt multipart an; Anfragen ohne Rumpf sind nicht betroffen.
func TestSchutz_JSONPflichtFuerRumpfe(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "jsonpflicht")
	for _, ct := range []string{"", "text/plain;charset=UTF-8", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"} {
		w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
			contentType: ct, cookie: c})
		if w.Code != http.StatusUnsupportedMediaType || code2961(w) != "unsupported_media_type" {
			t.Fatalf("Content-Type %q: erwartet 415, bekommen %d: %s", ct, w.Code, w.Body.String())
		}
	}
	if w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", body: ortRumpf2961,
		contentType: "application/json; charset=utf-8", cookie: c}); w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("application/json mit charset: erwartet Anlage, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Ohne Rumpf: kein 415 (z. B. Passkey-Start).
	if w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/auth/passkey/discoverable/begin"}); w.Code == http.StatusUnsupportedMediaType {
		t.Fatalf("Anfrage ohne Rumpf darf nicht 415 bekommen")
	}
	// GPX-Upload: multipart erlaubt.
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	fw, _ := mw.CreateFormFile("file", "a.gpx")
	fw.Write([]byte("<gpx></gpx>"))
	mw.Close()
	w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/gpx/parse", rawBody: buf.Bytes(),
		contentType: mw.FormDataContentType(), cookie: c})
	if w.Code == http.StatusUnsupportedMediaType {
		t.Fatalf("GPX-Upload (multipart) darf nicht 415 bekommen: %s", w.Body.String())
	}
}

// AC-17: Rumpfe ueber 1 MB → 413; der GPX-Upload darf bis 10 MB.
func TestSchutz_GroessenBegrenzung(t *testing.T) {
	r, s, secret := schutzRouter2961(t, nil)
	c := kontoMitSitzung2961(t, s, secret, "groesse")
	gross := []byte(`{"name":"` + strings.Repeat("a", 1<<20) + `"}`)
	w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/locations", rawBody: gross,
		contentType: "application/json", cookie: c})
	if w.Code != http.StatusRequestEntityTooLarge || code2961(w) != "payload_too_large" {
		t.Fatalf("1 MB+: erwartet 413 payload_too_large, bekommen %d", w.Code)
	}
	// Login (oeffentlich) ebenso.
	w = schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/auth/login", rawBody: gross,
		contentType: "application/json"})
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("Login 1 MB+: erwartet 413, bekommen %d", w.Code)
	}
	// AC-18: Webhooks setzen eigene Grenzen, die globale greift dort nicht.
	if w := schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/webhooks/telegram/inbound",
		rawBody: gross, contentType: "application/json"}); code2961(w) == "payload_too_large" {
		t.Fatalf("Webhook: globale Rumpfgrenze darf nicht greifen")
	}
	gpx := func(n int) *httptest.ResponseRecorder {
		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)
		fw, _ := mw.CreateFormFile("file", "a.gpx")
		fw.Write(bytes.Repeat([]byte("x"), n))
		mw.Close()
		return schicke2961(t, r, anfrage2961{method: http.MethodPost, path: "/api/gpx/parse", rawBody: buf.Bytes(),
			contentType: mw.FormDataContentType(), cookie: c})
	}
	if w := gpx(3 << 20); w.Code == http.StatusRequestEntityTooLarge {
		t.Fatalf("GPX 3 MB: darf nicht 413 sein")
	}
	if w := gpx(11 << 20); w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("GPX 11 MB: erwartet 413, bekommen %d", w.Code)
	}
}
