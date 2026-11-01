package handler

// TDD RED — Issue #2163 Scheibe 1 (Auth-Haertung Go), Timing-Block.
// Spec: docs/specs/modules/auth_haertung_go_2163.md (AC-2 bis AC-9)
//
// Jeder Nicht-Treffer-Zweig von Login und "Passwort vergessen" muss mindestens
// die Laufzeit eines bcrypt-Vergleichs bei bcrypt.DefaultCost brauchen
// (Dummy-Vergleich), damit die Antwortzeit nicht verraet, ob ein Konto
// existiert. Zugesichert wird NUR eine Untergrenze (>= 20 ms; Cost 10 braucht
// ca. 50 ms, der heutige Zweig ohne Dummy < 1 ms) — bewusst KEIN Vergleich
// "Treffer ~ Nicht-Treffer" (flaky).
//
// Gemessen wird das Minimum aus drei Laeufen: eine Untergrenze darf nur durch
// echte Arbeit erreicht werden, nicht durch einen zufaellig langsamen Lauf.
//
// RED-Signal heute: alle Nicht-Treffer-Zweige antworten ohne bcrypt in < 20 ms.
// Die Antwort-Charakterisierung (AC-8) und der Erfolgspfad (AC-9) sind heute
// gruen und bewachen, dass die Aenderung NUR die Laufzeit veraendert.
//
// Kein Mock: echter Handler, echter Store in t.TempDir(), echte Platte.

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// timingFloor ist die zugesicherte Mindestlaufzeit eines Nicht-Treffer-Zweigs.
const timingFloor = 20 * time.Millisecond

const timingSecret = "test-secret-32-chars-long-enough"

// timedRun fuehrt body dreimal gegen h aus und liefert die letzte Antwort sowie
// die kleinste gemessene Laufzeit.
func timedRun(h http.Handler, path, body string) (*httptest.ResponseRecorder, time.Duration) {
	var last *httptest.ResponseRecorder
	min := time.Duration(1<<63 - 1)
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		start := time.Now()
		h.ServeHTTP(w, req)
		if d := time.Since(start); d < min {
			min = d
		}
		last = w
	}
	return last, min
}

// Erwartete Antworten der Nicht-Treffer-Zweige, gemessen am unveraenderten
// Code (origin/main 7b8a62fb7). Body ohne abschliessenden Zeilenumbruch
// (auth.go schreibt per w.Write, nicht per json.Encoder).
const (
	wantLoginRejectBody  = `{"error":"invalid credentials"}`
	wantForgotNeutralBod = `{"status":"ok"}`
)

var wantJSONOnlyHeader = http.Header{"Content-Type": []string{"application/json"}}

// assertExactResponse verlangt Status, Body und den VOLLEN Header-Satz
// byte-gleich (AC-8) — ein neu hinzukommender Header faellt ebenfalls auf.
func assertExactResponse(t *testing.T, fall string, w *httptest.ResponseRecorder, wantStatus int, wantBody string) {
	t.Helper()
	if w.Code != wantStatus {
		t.Errorf("%s: Status erwartet %d, bekommen %d", fall, wantStatus, w.Code)
	}
	if got := w.Body.String(); got != wantBody {
		t.Errorf("%s: Body erwartet %q, bekommen %q", fall, wantBody, got)
	}
	if got := w.Header(); !reflect.DeepEqual(got, wantJSONOnlyHeader) {
		t.Errorf("%s: Header erwartet %v, bekommen %v", fall, wantJSONOnlyHeader, got)
	}
}

func assertTimingFloor(t *testing.T, fall string, d time.Duration) {
	t.Helper()
	if d < timingFloor {
		t.Errorf("%s: Laufzeit %v < %v — der Zweig fuehrt keinen bcrypt-Dummy-Vergleich "+
			"bei DefaultCost aus und verraet ueber die Antwortzeit, dass kein Konto/Hash existiert",
			fall, d, timingFloor)
	} else {
		t.Logf("%s: Laufzeit %v (>= %v)", fall, d, timingFloor)
	}
}

// --- Login-Zweige ----------------------------------------------------------

// loginNichtTrefferFaelle baut fuer jeden Login-Nicht-Treffer-Zweig einen
// Store-Zustand und den passenden Request-Body.
type loginNichtTreffer struct {
	name  string
	ac    string
	setup func(t *testing.T, s *store.Store)
	body  string
}

func loginNichtTrefferFaelle() []loginNichtTreffer {
	return []loginNichtTreffer{
		{
			name: "pfad-unsichere Kennung", ac: "AC-2",
			setup: func(t *testing.T, s *store.Store) {},
			body:  `{"username":"../x","password":"geheim123"}`,
		},
		{
			name: "Ladefehler (kaputte user.json)", ac: "AC-3",
			setup: func(t *testing.T, s *store.Store) {
				dir := filepath.Join(s.DataDir, "users", "kaputtnutzer")
				if err := os.MkdirAll(dir, 0o755); err != nil {
					t.Fatalf("MkdirAll: %v", err)
				}
				if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{not valid json`), 0o644); err != nil {
					t.Fatalf("WriteFile: %v", err)
				}
				// Vorbedingung: der Zweig ist wirklich der Ladefehler-Zweig.
				if u, err := s.LoadUser("kaputtnutzer"); err == nil {
					t.Fatalf("Vorbedingung: LoadUser muss fuer kaputte user.json einen Fehler liefern, bekam user=%v", u)
				}
			},
			body: `{"username":"kaputtnutzer","password":"geheim123"}`,
		},
		{
			name: "unbekannter Nutzer", ac: "AC-4",
			setup: func(t *testing.T, s *store.Store) {
				if u, err := s.LoadUser("garantiert-unbekannt"); err != nil || u != nil {
					t.Fatalf("Vorbedingung: LoadUser muss (nil, nil) liefern, bekam %v, %v", u, err)
				}
			},
			body: `{"username":"garantiert-unbekannt","password":"geheim123"}`,
		},
		{
			name: "Nutzer ohne PasswordHash (Passkey/Google)", ac: "AC-5",
			setup: func(t *testing.T, s *store.Store) {
				verifiziert := time.Now().UTC()
				if err := s.SaveUser(model.User{ID: "ohnehash", PasswordHash: "",
					EmailVerifiedAt: &verifiziert, CreatedAt: time.Now()}); err != nil {
					t.Fatalf("SaveUser: %v", err)
				}
			},
			body: `{"username":"ohnehash","password":"geheim123"}`,
		},
		{
			// "kaputt" scheitert schon am bcrypt-Parser (ErrHashTooShort) — ein
			// formal gueltiger $2a$10$-String wuerde die volle Cost laufen und
			// den Test aus dem falschen Grund gruen machen.
			name: "Nutzer mit kaputtem PasswordHash", ac: "AC-5",
			setup: func(t *testing.T, s *store.Store) {
				verifiziert := time.Now().UTC()
				if err := s.SaveUser(model.User{ID: "kaputthash", PasswordHash: "kaputt",
					EmailVerifiedAt: &verifiziert, CreatedAt: time.Now()}); err != nil {
					t.Fatalf("SaveUser: %v", err)
				}
			},
			body: `{"username":"kaputthash","password":"geheim123"}`,
		},
	}
}

// AC-2 bis AC-5: jeder Login-Nicht-Treffer-Zweig braucht >= 20 ms.
func TestLoginNichtTreffer_BrauchtMindestensBcryptLaufzeit_AC2_bis_AC5(t *testing.T) {
	for _, f := range loginNichtTrefferFaelle() {
		f := f
		t.Run(f.ac+"_"+f.name, func(t *testing.T) {
			s := newTestStore(t)
			f.setup(t, s)
			h := LoginHandler(s, timingSecret, "")
			w, d := timedRun(h, "/api/auth/login", f.body)
			if w.Code != http.StatusUnauthorized {
				t.Fatalf("%s %s: Status erwartet 401, bekommen %d: %s", f.ac, f.name, w.Code, w.Body.String())
			}
			assertTimingFloor(t, f.ac+" "+f.name, d)
		})
	}
}

// AC-8 (Login-Teil): Status, Body und Header jedes Login-Nicht-Treffer-Zweigs
// sind byte-gleich zum bisherigen Stand. Heute gruen (Charakterisierung).
func TestLoginNichtTreffer_AntwortByteGleich_AC8(t *testing.T) {
	for _, f := range loginNichtTrefferFaelle() {
		f := f
		t.Run(f.ac+"_"+f.name, func(t *testing.T) {
			s := newTestStore(t)
			f.setup(t, s)
			h := LoginHandler(s, timingSecret, "")
			req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(f.body))
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			assertExactResponse(t, "AC-8 Login "+f.name, w, http.StatusUnauthorized, wantLoginRejectBody)
			if len(w.Result().Cookies()) != 0 {
				t.Errorf("AC-8 Login %s: darf kein Cookie setzen, bekam %v", f.name, w.Result().Cookies())
			}
		})
	}
}

// --- Forgot-Zweige ---------------------------------------------------------

type forgotNichtTreffer struct {
	name     string
	ac       string
	username string
}

func forgotNichtTrefferFaelle() []forgotNichtTreffer {
	return []forgotNichtTreffer{
		{name: "pfad-unsichere Kennung", ac: "AC-6", username: "../x"},
		{name: "unbekannter Nutzer", ac: "AC-7", username: "garantiert-unbekannt"},
	}
}

func forgotHandlerDefaultCost(s *store.Store) http.Handler {
	// DefaultCost wie im Router (router.go: ForgotPasswordHandler(..., bcrypt.DefaultCost, ...)).
	return ForgotPasswordHandler(s, bcrypt.DefaultCost, config.Config{PublicHost: "https://test.example.com"})
}

// AC-6/AC-7: "Passwort vergessen" fuer pfad-unsichere und unbekannte Kennung
// braucht >= 20 ms und antwortet weiter neutral.
func TestForgotNichtTreffer_BrauchtMindestensBcryptLaufzeit_AC6_AC7(t *testing.T) {
	for _, f := range forgotNichtTrefferFaelle() {
		f := f
		t.Run(f.ac+"_"+f.name, func(t *testing.T) {
			s := newTestStore(t)
			h := forgotHandlerDefaultCost(s)
			w, d := timedRun(h, "/api/auth/forgot-password", `{"username":"`+f.username+`"}`)
			if w.Code != http.StatusOK || w.Body.String() != wantForgotNeutralBod {
				t.Fatalf("%s %s: erwartet 200 %s, bekommen %d %q", f.ac, f.name, wantForgotNeutralBod, w.Code, w.Body.String())
			}
			assertTimingFloor(t, f.ac+" "+f.name, d)
		})
	}
}

// AC-7 (kein Mailversand / kein Token): ein unbekannter Nutzer bekommt keinen
// Reset-Token — weder im (nicht existierenden) eigenen Ordner noch irgendwo
// ausserhalb des Nutzerbaums (Muster #2140). Ohne Token gibt es keinen
// Versandweg; die Versand-Goroutine startet erst nach SaveResetToken.
// Heute gruen (Waechter gegen eine Umsetzung, die fuer den Dummy-Pfad doch
// einen Token schreibt oder einen Nutzer anlegt).
func TestForgotUnbekannterNutzer_KeinTokenKeinNutzer_AC7(t *testing.T) {
	s := newTestStore(t)
	h := forgotHandlerDefaultCost(s)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/forgot-password", strings.NewReader(`{"username":"garantiert-unbekannt"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK || w.Body.String() != wantForgotNeutralBod {
		t.Fatalf("AC-7: erwartet 200 %s, bekommen %d %q", wantForgotNeutralBod, w.Code, w.Body.String())
	}
	if _, err := os.Stat(filepath.Join(s.UserDir("garantiert-unbekannt"), "password_reset.json")); err == nil {
		t.Error("AC-7: fuer einen unbekannten Nutzer darf kein password_reset.json entstehen")
	}
	if found := findFilesOutsideUsersTree(t, s.DataDir, "password_reset.json"); len(found) > 0 {
		t.Errorf("AC-7: password_reset.json ausserhalb des Nutzerbaums: %v", found)
	}
	if s.UserExists("garantiert-unbekannt") {
		t.Error("AC-7: der Forgot-Pfad darf keinen Nutzer anlegen")
	}
}

// AC-8 (Forgot-Teil): Status, Body und Header byte-gleich. Heute gruen.
func TestForgotNichtTreffer_AntwortByteGleich_AC8(t *testing.T) {
	for _, f := range forgotNichtTrefferFaelle() {
		f := f
		t.Run(f.ac+"_"+f.name, func(t *testing.T) {
			s := newTestStore(t)
			h := forgotHandlerDefaultCost(s)
			req := httptest.NewRequest(http.MethodPost, "/api/auth/forgot-password", strings.NewReader(`{"username":"`+f.username+`"}`))
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			assertExactResponse(t, "AC-8 Forgot "+f.name, w, http.StatusOK, wantForgotNeutralBod)
		})
	}
}

// --- Erfolgspfad -----------------------------------------------------------

// AC-9: gueltiges Konto (Hash bei DefaultCost, bestaetigte Adresse — #2271)
// meldet sich weiter mit 200 + gz_session an; falsches Passwort bleibt 401
// mit unveraenderter Antwort. Heute gruen (Charakterisierung).
func TestLoginErfolgspfadUnveraendert_FalschesPasswort401_AC9(t *testing.T) {
	s := newTestStore(t)
	hash, err := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("GenerateFromPassword: %v", err)
	}
	verifiziert := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: string(hash),
		EmailVerifiedAt: &verifiziert, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	h := LoginHandler(s, timingSecret, "")

	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(`{"username":"alice","password":"geheim123"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-9: richtiges Passwort: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"id":"alice"}` {
		t.Errorf("AC-9: Erfolgs-Body erwartet %q, bekommen %q", `{"id":"alice"}`, got)
	}
	var session *http.Cookie
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			session = c
		}
	}
	if session == nil || session.Value == "" {
		t.Fatalf("AC-9: gz_session-Cookie fehlt, Cookies: %v", w.Result().Cookies())
	}
	if !session.HttpOnly {
		t.Error("AC-9: gz_session muss HttpOnly bleiben")
	}

	req2 := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(`{"username":"alice","password":"falsch-falsch"}`))
	w2 := httptest.NewRecorder()
	h.ServeHTTP(w2, req2)
	assertExactResponse(t, "AC-9 falsches Passwort", w2, http.StatusUnauthorized, wantLoginRejectBody)
	if len(w2.Result().Cookies()) != 0 {
		t.Errorf("AC-9: falsches Passwort darf kein Cookie setzen, bekam %v", w2.Result().Cookies())
	}
}
