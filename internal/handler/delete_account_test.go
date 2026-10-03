package handler

// Kontoloeschung mit Re-Authentifizierung — Issue #2160, Spec
// docs/specs/modules/account_deletion.md (AC-1, AC-3, AC-4, AC-6, AC-7).
//
// Neuer Vertrag: POST /api/auth/account/delete mit Body {password?, code?};
// DeleteAccountHandler bekommt den TelegramTokenStore, damit die gemeinsame
// Aufraeumfunktion dessen Reste des Nutzers entfernen kann.

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// loeschPasswort ist das Klartext-Passwort aller Passwort-Testkonten.
const loeschPasswort = "geheim-123"

// passwortKonto legt ein Konto MIT Passwort an (bcrypt, echter Hash).
func passwortKonto(t *testing.T, s *store.Store, id, email string) model.User {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(loeschPasswort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	u := model.User{ID: id, Email: email, PasswordHash: string(hash), CreatedAt: time.Now()}
	mustSaveUser(t, s, u)
	return u
}

// passwortloskonto legt ein Konto OHNE Passwort an (Magic-Link/Passkey/Google).
func passwortlosKonto(t *testing.T, s *store.Store, id, email string) model.User {
	t.Helper()
	u := model.User{ID: id, Email: email, MailTo: email, CreatedAt: time.Now()}
	mustSaveUser(t, s, u)
	return u
}

// postKontoLoeschen ruft den Loesch-Handler wie die Middleware es taete auf:
// echte user_id im Kontext, JSON-Body.
func postKontoLoeschen(h http.Handler, userID, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/account/delete", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func nutzerOrdnerVorhanden(s *store.Store, id string) bool {
	_, err := os.Stat(filepath.Join(s.DataDir, "users", id))
	return err == nil
}

// AC-1: korrektes Passwort -> 200 {"status":"deleted"}, Ordner weg.
func TestKontoLoeschen_KorrektesPasswort_LoeschtOrdner(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "alice", "alice@beispiel.de")
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(filepath.Join(dir, "locations"), 0755)
	os.WriteFile(filepath.Join(dir, "locations", "loc1.json"), []byte(`{"id":"loc1"}`), 0644)

	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))
	w := postKontoLoeschen(h, "alice", `{"password":"`+loeschPasswort+`"}`)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"status":"deleted"`) {
		t.Errorf("expected status deleted, got %s", w.Body.String())
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Error("user directory should be deleted")
	}
}

// AC-1: Cookie wird geloescht, Gaesteliste ist mit dem Ordner weg (#2129).
func TestKontoLoeschen_LoeschtSitzungsCookieUndGaesteliste(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "bob", "bob@beispiel.de")
	if err := s.AddSession("bob", "sess-bob"); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))
	w := postKontoLoeschen(h, "bob", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	found := false
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.MaxAge == -1 {
			found = true
		}
	}
	if !found {
		t.Error("gz_session cookie should be cleared")
	}
	if sessions, err := s.LoadSessions("bob"); err != nil || len(sessions) != 0 {
		t.Errorf("Gaesteliste muss nach der Kontoloeschung leer sein, sind %d (err=%v)", len(sessions), err)
	}
}

// Nutzer existiert nicht (mehr): 404 not_found, auch mit Nachweis im Body.
func TestKontoLoeschen_UnbekannterNutzer_404(t *testing.T) {
	s := newTestStore(t)
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	w := postKontoLoeschen(h, "nobody", `{"password":"egal"}`)
	if w.Code != 404 {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "not_found") {
		t.Errorf("expected error not_found, got %s", w.Body.String())
	}
}

// AC-3 (Teil Antwort): falsches Passwort -> 403 wrong_password, Ordner bleibt.
// Die Nebenwirkungsfreiheit (Tokens/OTPs/Lösch-Code) prueft
// account_deletion_leftovers_test.go.
func TestKontoLoeschen_FalschesPasswort_403WrongPassword(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "alice", "alice@beispiel.de")
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	w := postKontoLoeschen(h, "alice", `{"password":"falsch"}`)
	if w.Code != 403 {
		t.Fatalf("expected 403, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "wrong_password") {
		t.Errorf("expected error wrong_password, got %s", w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "alice") {
		t.Error("Ordner darf bei falschem Passwort nicht geloescht werden")
	}
}

// AC-4: weder Passwort noch Code -> 400 reauth_required, nichts geloescht.
func TestKontoLoeschen_OhneNachweis_400ReauthRequired(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "alice", "alice@beispiel.de")
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	for _, body := range []string{``, `{}`, `{"password":"","code":""}`} {
		w := postKontoLoeschen(h, "alice", body)
		if w.Code != 400 {
			t.Fatalf("body %q: expected 400, got %d: %s", body, w.Code, w.Body.String())
		}
		if !strings.Contains(w.Body.String(), "reauth_required") {
			t.Errorf("body %q: expected error reauth_required, got %s", body, w.Body.String())
		}
		if !nutzerOrdnerVorhanden(s, "alice") {
			t.Fatalf("body %q: Ordner darf ohne Nachweis nicht geloescht werden", body)
		}
	}
}

// AC-7: Konto ohne Passwort — Passwort-Nachweis 403 wrong_password (auch ein
// leeres/beliebiges Passwort), gueltiger Lösch-Code loescht.
func TestKontoLoeschen_PasswortlosesKonto_PasswortAbgelehntCodeLoescht(t *testing.T) {
	s := newTestStore(t)
	t.Cleanup(zuruecksetzenLoeschCodes)
	passwortlosKonto(t, s, "m-1a2b3c4d", "magic@beispiel.de")
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	w := postKontoLoeschen(h, "m-1a2b3c4d", `{"password":"irgendwas"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "wrong_password") {
		t.Fatalf("Passwort bei passwortlosem Konto: expected 403 wrong_password, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "m-1a2b3c4d") {
		t.Fatal("Konto darf durch abgelehntes Passwort nicht geloescht werden")
	}

	setzeLoeschCode("m-1a2b3c4d", "424242", time.Now().Add(10*time.Minute), 0)
	w = postKontoLoeschen(h, "m-1a2b3c4d", `{"code":"424242"}`)
	if w.Code != 200 {
		t.Fatalf("gueltiger Code: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "m-1a2b3c4d") {
		t.Error("Konto muss per gueltigem Lösch-Code geloescht sein")
	}
}

// AC-6: gueltiger Code loescht ein Passwort-Konto (ohne Passwort im Body); der
// Code ist danach verbraucht und nicht erneut verwendbar.
func TestKontoLoeschen_CodeIstEinmalig(t *testing.T) {
	s := newTestStore(t)
	t.Cleanup(zuruecksetzenLoeschCodes)
	passwortKonto(t, s, "alice", "alice@beispiel.de")
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	setzeLoeschCode("alice", "135790", time.Now().Add(10*time.Minute), 0)
	w := postKontoLoeschen(h, "alice", `{"code":"135790"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "alice") {
		t.Fatal("Konto muss per Code geloescht sein")
	}
	if _, ok := deleteCodeStore.Load("alice"); ok {
		t.Error("Lösch-Code muss nach der Löschung aus dem Store entfernt sein")
	}

	// Gleiche Kennung erneut angelegt (ein neuer Zustand) — der alte Code
	// darf nicht mehr gelten.
	passwortlosKonto(t, s, "alice", "alice@beispiel.de")
	w = postKontoLoeschen(h, "alice", `{"code":"135790"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("verbrauchter Code: expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "alice") {
		t.Error("zweiter Versuch mit verbrauchtem Code darf nichts loeschen")
	}
}
