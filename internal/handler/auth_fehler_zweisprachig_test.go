package handler

// Issue #2676 (i18n G2) — Auth-/Konto-Fehler als {code, message} in der Sprache des Nutzers.
// Spec: docs/specs/modules/i18n_g2_go_handler_auth_2676.md — AC-1 bis AC-4.
//
// Echte Handler hinter der echten Lang-Middleware, echter Store im Temp-Verzeichnis.
// user.json wird vor und nach jedem Aufruf roh von der Platte gelesen. Kein Mock.

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

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const g2Secret = "test-secret-32-chars-long-enough!"

// g2Antwort liest code und message aus einer Fehlerantwort.
func g2Antwort(t *testing.T, w *httptest.ResponseRecorder) (string, string) {
	t.Helper()
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort ist kein JSON: %v (%s)", err, w.Body.String())
	}
	code, _ := body["code"].(string)
	msg, _ := body["message"].(string)
	return code, msg
}

// g2UserBytes liest user.json roh von der Platte.
func g2UserBytes(t *testing.T, s *store.Store, id string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json von %s nicht lesbar: %v", id, err)
	}
	return data
}

// g2Profil sendet PUT /api/auth/profile als Nutzer userID durch die Lang-Middleware.
func g2Profil(s *store.Store, userID, body string) *httptest.ResponseRecorder {
	h := middleware.Lang(s)(UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter))
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

const g2UngueltigeSMS = `{"sms_to":"12345"}`

// AC-1: en-Nutzer, ungueltige SMS-Nummer -> 400, englische Meldung, user.json byte-identisch.
func TestG2ProfilFehlerAufEnglisch(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna-en", Language: "en"})
	vor := g2UserBytes(t, s, "anna-en")

	w := g2Profil(s, "anna-en", g2UngueltigeSMS)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("AC-1: Status %d, erwartet 400: %s", w.Code, w.Body.String())
	}
	code, msg := g2Antwort(t, w)
	if code != "invalid_sms_number" {
		t.Errorf("AC-1: code %q, erwartet invalid_sms_number", code)
	}
	want := "The SMS number is invalid. Please use the format +491701234567."
	if msg != want {
		t.Errorf("AC-1: message %q, erwartet %q", msg, want)
	}
	if !bytes.Equal(vor, g2UserBytes(t, s, "anna-en")) {
		t.Errorf("AC-1: user.json wurde durch den abgelehnten Aufruf veraendert")
	}
}

// AC-2 (Profil): de-Nutzer, gleicher ungueltiger Wert -> deutsche Meldung laut Katalog.
func TestG2ProfilFehlerAufDeutsch(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna-de", Language: "de"})

	w := g2Profil(s, "anna-de", g2UngueltigeSMS)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("AC-2: Status %d, erwartet 400", w.Code)
	}
	code, msg := g2Antwort(t, w)
	if code != "invalid_sms_number" {
		t.Errorf("AC-2: code %q, erwartet invalid_sms_number", code)
	}
	if alt, _ := g2Feld(t, w, "error"); alt != "invalid_sms_number" {
		t.Errorf("AC-2: Uebergangsfeld error %q, erwartet invalid_sms_number", alt)
	}
	want := "Die SMS-Nummer ist ungültig. Bitte im Format +491701234567 angeben."
	if msg != want {
		t.Errorf("AC-2: message %q, erwartet %q", msg, want)
	}
}

// g2Feld liest ein beliebiges Feld der Fehlerantwort als String.
func g2Feld(t *testing.T, w *httptest.ResponseRecorder, feld string) (string, bool) {
	t.Helper()
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort ist kein JSON: %v", err)
	}
	v, ok := body[feld].(string)
	return v, ok
}

// AC-2 (Registrierung): E-Mail ohne "@" -> 400 invalid_email in der Besuchersprache (de ohne Header).
func TestG2RegistrierungEmailOhneAtDeutsch(t *testing.T) {
	s := newTestStore(t)
	h := middleware.Lang(s)(RegisterHandlerWithInvites(s, 4, testRegisterCfg(), store.NewInviteStore(t.TempDir())))
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register",
		strings.NewReader(`{"username":"annade","password":"geheim-pw-123","email":"kein-at"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("AC-2: Status %d, erwartet 400: %s", w.Code, w.Body.String())
	}
	code, msg := g2Antwort(t, w)
	if code != "invalid_email" {
		t.Errorf("AC-2: code %q, erwartet invalid_email", code)
	}
	want := "Bitte gib eine gültige E-Mail-Adresse an."
	if msg != want {
		t.Errorf("AC-2: message %q, erwartet %q", msg, want)
	}
}

// g2Login sendet POST /api/auth/login durch die Lang-Middleware.
func g2Login(s *store.Store, user, pw, acceptLang string) *httptest.ResponseRecorder {
	h := middleware.Lang(s)(LoginHandler(s, g2Secret, ""))
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login",
		strings.NewReader(`{"username":"`+user+`","password":"`+pw+`"}`))
	if acceptLang != "" {
		req.Header.Set("Accept-Language", acceptLang)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

// AC-3: falsches Passwort, Accept-Language en bzw. ohne Header -> 401 invalid_credentials,
// Meldung in der Besuchersprache; unbekannter Nutzer liefert denselben Body.
func TestG2LoginFalschesPasswortSprachabhaengig(t *testing.T) {
	s := newTestStore(t)
	hash, err := bcrypt.GenerateFromPassword([]byte("richtig-pw-123"), bcrypt.MinCost)
	if err != nil {
		t.Fatal(err)
	}
	mustSaveUser(t, s, model.User{ID: "bert", PasswordHash: string(hash), Email: "bert@example.com"})

	cases := []struct {
		name, acceptLang, want string
	}{
		{"en per Header", "en", "Username or password is incorrect."},
		{"de ohne Header", "", "Benutzername oder Passwort ist falsch."},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			falsch := g2Login(s, "bert", "falsches-pw-999", tc.acceptLang)
			if falsch.Code != http.StatusUnauthorized {
				t.Fatalf("AC-3: Status %d, erwartet 401", falsch.Code)
			}
			code, msg := g2Antwort(t, falsch)
			if code != "invalid_credentials" {
				t.Errorf("AC-3: code %q, erwartet invalid_credentials", code)
			}
			if msg != tc.want {
				t.Errorf("AC-3: message %q, erwartet %q", msg, tc.want)
			}
			unbekannt := g2Login(s, "niemand", "falsches-pw-999", tc.acceptLang)
			if !bytes.Equal(falsch.Body.Bytes(), unbekannt.Body.Bytes()) {
				t.Errorf("AC-3: Body unbekannter Nutzer weicht ab: %s vs %s",
					unbekannt.Body.String(), falsch.Body.String())
			}
		})
	}
}

// AC-4: zwei Nutzer parallel, beide mit abgelehnter Profil-Aenderung. Jeder bekommt seine
// Sprache, und user.json beider Nutzer bleibt unveraendert.
func TestG2ZweiNutzerParallelJeEigeneSprache(t *testing.T) {
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna-en", Language: "en"})
	mustSaveUser(t, s, model.User{ID: "bert-de", Language: "de"})
	vorA, vorB := g2UserBytes(t, s, "anna-en"), g2UserBytes(t, s, "bert-de")

	const runden = 20
	var wg sync.WaitGroup
	fehler := make(chan string, 2*runden)
	for i := 0; i < runden; i++ {
		for _, tc := range []struct{ id, want string }{
			{"anna-en", "The SMS number is invalid. Please use the format +491701234567."},
			{"bert-de", "Die SMS-Nummer ist ungültig. Bitte im Format +491701234567 angeben."},
		} {
			wg.Add(1)
			go func(id, want string) {
				defer wg.Done()
				w := g2Profil(s, id, g2UngueltigeSMS)
				var body map[string]any
				_ = json.Unmarshal(w.Body.Bytes(), &body)
				if w.Code != http.StatusBadRequest || body["message"] != want {
					fehler <- id + ": " + w.Body.String()
				}
			}(tc.id, tc.want)
		}
	}
	wg.Wait()
	close(fehler)
	for f := range fehler {
		t.Errorf("AC-4: falsche Sprache oder Status: %s", f)
	}
	if !bytes.Equal(vorA, g2UserBytes(t, s, "anna-en")) || !bytes.Equal(vorB, g2UserBytes(t, s, "bert-de")) {
		t.Errorf("AC-4: user.json eines Nutzers hat sich veraendert")
	}
}

// fehlerCodeVon liefert das code-Feld einer Fehlerantwort (leer, wenn keins da ist).
func fehlerCodeVon(w *httptest.ResponseRecorder) string {
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	code, _ := body["code"].(string)
	return code
}
