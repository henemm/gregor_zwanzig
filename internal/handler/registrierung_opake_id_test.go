package handler

// TDD RED — Issue #2194 (Epic #2138). Spec: docs/specs/modules/email_login_identifier.md
//
// AC-10: Registrierung ohne is_test_user vergibt u-<8hex>; ein mitgesendeter
//        username wird ignoriert; der Ordner data/users/u-<8hex>/ existiert.
// AC-11: Registrierung mit is_test_user=true und username legt das Testkonto
//        mit genau dieser ID an (Validator-Skript, Fixtures, E2E-Zweitnutzer);
//        anschliessender ID-Login gelingt; Wiederholung ohne email => 409
//        (Reihenfolge-Regel #1517). — Wächter, heute grün.
// AC-12: Einladung (ADR-0084) wird mit der generierten ID eingeloest, nicht
//        mit dem Formular-username.
//
// Echter Handler, echter Store/InviteStore in t.TempDir(). Nur bestehende
// Symbole; ID-Format per Regex (opakeID2194 aus passkey_login_per_email_test.go).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func registriere2194(t *testing.T, s *store.Store, inv *store.InviteStore, rumpf string) *httptest.ResponseRecorder {
	t.Helper()
	h := RegisterHandlerWithInvites(s, bcrypt.MinCost, config.Config{}, inv)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(rumpf))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func registrierID2194(t *testing.T, w *httptest.ResponseRecorder, fall string) string {
	t.Helper()
	if w.Code != http.StatusCreated {
		t.Fatalf("%s: Registrierung erwartet 201, bekommen %d: %s", fall, w.Code, w.Body.String())
	}
	var a struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &a); err != nil {
		t.Fatalf("%s: Antwort kein JSON: %v", fall, err)
	}
	return a.ID
}

func TestRegistrierungVergibtOpakeID_AC10_2194(t *testing.T) {
	s := newTestStore(t)

	idMit := registrierID2194(t, registriere2194(t, s, nil,
		`{"username":"wunsch2194","password":"geheim-pw-123","email":"wunsch2194@beispiel.de"}`),
		"AC-10 mit username")
	idOhne := registrierID2194(t, registriere2194(t, s, nil,
		`{"password":"geheim-pw-123","email":"ohne2194@beispiel.de"}`),
		"AC-10 ohne username")

	for _, id := range []string{idMit, idOhne} {
		if !opakeID2194.MatchString(id) {
			t.Errorf("AC-10: Konto-ID %q passt nicht zu ^u-[0-9a-f]{8}$", id)
			continue
		}
		if fi, err := os.Stat(s.UserDir(id)); err != nil || !fi.IsDir() {
			t.Errorf("AC-10: Ordner data/users/%s/ fehlt (err=%v)", id, err)
		}
		if u, err := s.LoadUser(id); err != nil || u == nil {
			t.Errorf("AC-10: Konto %q nicht ladbar (err=%v)", id, err)
		} else if u.IsTestUser {
			t.Errorf("AC-10: Konto %q darf kein Testkonto sein", id)
		}
	}
	if idMit == idOhne {
		t.Errorf("AC-10: zwei Registrierungen lieferten dieselbe ID %q", idMit)
	}
	if s.UserExists("wunsch2194") {
		t.Errorf("AC-10: der mitgesendete username darf ohne is_test_user kein Konto benennen")
	}
	if u, _ := s.LoadUser(idMit); u != nil && u.Email != "wunsch2194@beispiel.de" {
		t.Errorf("AC-10: Konto %q muss die registrierte Adresse tragen, hat %q", idMit, u.Email)
	}
}

// AC-11 — Wächter, heute grün.
func TestRegistrierungTestkontoBehaeltFesteID_AC11_2194(t *testing.T) {
	s := newTestStore(t)
	const id = "validator-2194"

	got := registrierID2194(t, registriere2194(t, s, nil,
		`{"username":"`+id+`","password":"geheim-pw-123","email":"validator2194@beispiel.de","is_test_user":true}`),
		"AC-11")
	if got != id {
		t.Fatalf("AC-11: Testkonto muss genau die ID %q bekommen, bekommen %q", id, got)
	}
	u, err := s.LoadUser(id)
	if err != nil || u == nil {
		t.Fatalf("AC-11: Testkonto %q nicht ladbar: %v", id, err)
	}
	if !u.IsTestUser {
		t.Errorf("AC-11: is_test_user muss persistiert sein")
	}

	// Bestaetigung wie nach dem Verify-Link (Gate ADR-0066), dann ID-Login.
	jetzt := time.Now().UTC()
	u.EmailVerifiedAt = &jetzt
	if err := s.SaveUser(*u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	lw := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login",
		strings.NewReader(`{"username":"`+id+`","password":"geheim-pw-123"}`))
	LoginHandler(s, timingSecret, "").ServeHTTP(lw, req)
	if lw.Code != http.StatusOK {
		t.Fatalf("AC-11: ID-Login des Testkontos erwartet 200, bekommen %d: %s", lw.Code, lw.Body.String())
	}
	if strings.TrimSpace(lw.Body.String()) != `{"id":"`+id+`"}` {
		t.Errorf("AC-11: Login-Antwort erwartet {\"id\":%q}, bekommen %q", id, lw.Body.String())
	}

	// #1517: Wiederholung ohne email (setup-validator-user.sh) => 409, nicht 400.
	w := registriere2194(t, s, nil, `{"username":"`+id+`","password":"geheim-pw-123","is_test_user":true}`)
	if w.Code != http.StatusConflict {
		t.Errorf("AC-11/#1517: erneute Testkonto-Registrierung ohne email erwartet 409, bekommen %d: %s",
			w.Code, w.Body.String())
	}
}

func TestRegistrierungMitEinladungNutztGenerierteID_AC12_2194(t *testing.T) {
	s := newTestStore(t)
	inv := store.NewInviteStore(t.TempDir())
	einladung, token, err := inv.Create("premium", "", "admin")
	if err != nil {
		t.Fatalf("Einladung anlegen: %v", err)
	}

	id := registrierID2194(t, registriere2194(t, s, inv,
		`{"username":"formular2194","password":"geheim-pw-123","email":"einladung2194@beispiel.de","invite":"`+token+`"}`),
		"AC-12")
	if !opakeID2194.MatchString(id) {
		t.Errorf("AC-12: Konto-ID %q passt nicht zu ^u-[0-9a-f]{8}$", id)
	}

	var einloeser string
	for _, i := range inv.List() {
		if i.ID == einladung.ID {
			einloeser = i.UsedBy
		}
	}
	if einloeser != id {
		t.Errorf("AC-12: Einladung muss mit der generierten ID %q verbunden sein, gespeichert ist %q", id, einloeser)
	}
	if einloeser == "formular2194" {
		t.Errorf("AC-12: Einladung darf nicht mit dem Formular-username verbunden sein")
	}
	if u, _ := s.LoadUser(id); u == nil || u.Tier != "premium" {
		t.Errorf("AC-12: das neue Konto %q muss die Stufe der Einladung tragen (u=%v)", id, u)
	}
}
