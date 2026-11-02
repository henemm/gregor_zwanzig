package handler

// Issue #2194, Adversary-Finding F001: resolveLoginEmail darf bei Lesefehler
// (unlesbare user.json) und bei Mehrfachtreffer nur Anzahlen loggen, NIE die
// E-Mail-Adresse (Spec email_login_identifier.md, ADR-0105). Geprueft wird am
// Wirkort: ueber die echten Handler (Login, Passwort vergessen,
// Verify-Resend) mit echtem Store in t.TempDir() und Log-Mitschnitt per
// log.SetOutput (logMitschneiden aus pii_log_guard_test.go).
//
// Positiv-Anker: die konkrete Log-Zeile "<ctx>: login email ambiguous" bzw.
// "<ctx>: login email lookup failed" muss entstanden sein — sonst pruefte der
// Test ins Leere.
//
// Kein t.Parallel (log.SetOutput ist prozessweit).

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// Gemischte Schreibung mit Leerzeichen: geprueft werden roh, getrimmt und
// normalisiert.
const adresseRoh2194 = "  Doppelt.Kontakt@Beispiel.DE "

func adressFormen2194() []string {
	return []string{
		adresseRoh2194,
		strings.TrimSpace(adresseRoh2194),
		store.NormalizeEmailAddress(adresseRoh2194),
	}
}

type logPfad2194 struct {
	name    string
	ctx     string // Praefix der Log-Zeile in resolveLoginEmail
	handler func(s *store.Store) http.Handler
	route   string
	body    func(kennung string) string
}

func logPfade2194() []logPfad2194 {
	return []logPfad2194{
		{
			name: "Login", ctx: "login", route: "/api/auth/login",
			handler: func(s *store.Store) http.Handler { return LoginHandler(s, timingSecret, "") },
			body: func(k string) string {
				return `{"username":"` + k + `","password":"irgendwas-123"}`
			},
		},
		{
			name: "Passwort vergessen", ctx: "password reset", route: "/api/auth/forgot-password",
			handler: func(s *store.Store) http.Handler {
				return ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{})
			},
			body: func(k string) string { return `{"username":"` + k + `"}` },
		},
		{
			name: "Verify-Resend", ctx: "email verification resend", route: "/api/auth/resend-verification",
			handler: func(s *store.Store) http.Handler {
				return ResendVerificationHandler(s, config.Config{}, NewMailFloodLimiter(10, time.Hour))
			},
			body: func(k string) string { return `{"username":"` + k + `"}` },
		},
	}
}

func pruefeLogOhneAdresse2194(t *testing.T, log, anker string) {
	t.Helper()
	if !strings.Contains(log, anker) {
		t.Fatalf("Positiv-Anker fehlt: erwartete Log-Zeile %q, Log war: %q", anker, log)
	}
	for _, form := range adressFormen2194() {
		if strings.Contains(log, form) {
			t.Errorf("F001: Log enthaelt die E-Mail-Adresse %q (Spec/ADR-0105: nur Anzahlen). Log: %q", form, log)
		}
	}
}

func TestLoginEmail_Mehrfachtreffer_LogNenntKeineAdresse_F001_2194(t *testing.T) {
	for _, p := range logPfade2194() {
		t.Run(p.name, func(t *testing.T) {
			s := newTestStore(t)
			norm := store.NormalizeEmailAddress(adresseRoh2194)
			kontoBcrypt2194(t, s, "konto-a2194", norm, "passwort-a-1")
			kontoBcrypt2194(t, s, "konto-b2194", strings.TrimSpace(adresseRoh2194), "passwort-b-1")

			mitschnitt := logMitschneiden(t)
			req := httptest.NewRequest(http.MethodPost, p.route, strings.NewReader(p.body(adresseRoh2194)))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			p.handler(s).ServeHTTP(w, req)

			pruefeLogOhneAdresse2194(t, mitschnitt.String(), p.ctx+": login email ambiguous")
		})
	}
}

func TestLoginEmail_UnlesbareUserJSON_LogNenntKeineAdresse_F001_2194(t *testing.T) {
	for _, p := range logPfade2194() {
		t.Run(p.name, func(t *testing.T) {
			s := newTestStore(t)
			// Ein echtes Konto mit der Adresse und ein Konto mit kaputter
			// user.json (neutraler Name, keine Adresse im Inhalt — sonst
			// kaeme sie ueber %v des Fehlers ins Log).
			kontoBcrypt2194(t, s, "konto-c2194", store.NormalizeEmailAddress(adresseRoh2194), "passwort-c-1")
			dir := filepath.Join(s.DataDir, "users", "kaputt2194")
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatalf("MkdirAll: %v", err)
			}
			if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{not valid json`), 0o644); err != nil {
				t.Fatalf("WriteFile: %v", err)
			}

			mitschnitt := logMitschneiden(t)
			req := httptest.NewRequest(http.MethodPost, p.route, strings.NewReader(p.body(adresseRoh2194)))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			p.handler(s).ServeHTTP(w, req)

			pruefeLogOhneAdresse2194(t, mitschnitt.String(), p.ctx+": login email lookup failed")
		})
	}
}
