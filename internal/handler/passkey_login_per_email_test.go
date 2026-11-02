package handler

// TDD RED — Issue #2194 (Epic #2138). Spec: docs/specs/modules/email_login_identifier.md
//
// AC-9:  Passkey-Login mit Kennung nimmt die E-Mail-Adresse; unbekannte,
//        mehrfach vergebene und Testkonto-Adresse antworten wie eine
//        unbekannte Kennung.
// AC-13: Oeffentliche Passkey-Registrierung vergibt eine generierte
//        u-<8hex>-ID; zwei Registrierungen liefern verschiedene IDs; ein im
//        Rumpf mitgesendeter username wird ignoriert.
//
// Echte WebAuthn-Zeremonie (passkeytest: ECDSA-P-256, "none"-Attestation),
// echter Store in t.TempDir(). Nur bestehende Symbole; das ID-Format wird per
// Regex geprueft, nicht ueber den neuen Generator.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

var opakeID2194 = regexp.MustCompile(`^u-[0-9a-f]{8}$`)

// seedPasskeyKonto2194 legt ein bestaetigtes Konto mit Adresse an — VOR
// registerForUser, der nur ein fehlendes Konto selbst seedet.
func seedPasskeyKonto2194(t *testing.T, s *store.Store, uid, email string, testkonto bool) {
	t.Helper()
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: uid, Email: email, MailTo: email, PasswordHash: "h",
		EmailVerifiedAt: &jetzt, IsTestUser: testkonto, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser %q: %v", uid, err)
	}
}

func TestPasskeyLoginBeginPerEmail_AC9_2194(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	seedPasskeyKonto2194(t, s, "rita2194", "rita@beispiel.de", false)
	auth := registerForUser(t, s, wa, cs, "rita2194")
	seedPasskeyKonto2194(t, s, "sven2194", "doppelt2194@beispiel.de", false)
	registerForUser(t, s, wa, cs, "sven2194")
	seedPasskeyKonto2194(t, s, "tom2194", "doppelt2194@beispiel.de", false)
	registerForUser(t, s, wa, cs, "tom2194")
	seedPasskeyKonto2194(t, s, "tina2194", "tina@beispiel.de", true)
	registerForUser(t, s, wa, cs, "tina2194")

	begin := PasskeyLoginBeginHandler(s, wa, cs)
	rufe := func(kennung string) *httptest.ResponseRecorder {
		body, _ := json.Marshal(map[string]string{"username": kennung})
		req := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/login/begin", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		begin.ServeHTTP(w, req)
		return w
	}

	// Referenz: unbekannte Kennung (ohne "@").
	ref := rufe("unbekannt2194")
	if ref.Code != http.StatusUnauthorized {
		t.Fatalf("AC-9 Referenz: unbekannte Kennung erwartet 401, bekommen %d: %s", ref.Code, ref.Body.String())
	}
	for _, f := range []struct{ name, kennung string }{
		{"unbekannte Adresse", "niemand2194@beispiel.de"},
		{"mehrfach vergebene Adresse", "doppelt2194@beispiel.de"},
		{"Testkonto-Adresse", "tina@beispiel.de"},
	} {
		w := rufe(f.kennung)
		if w.Code != ref.Code || !bytes.Equal(w.Body.Bytes(), ref.Body.Bytes()) {
			t.Errorf("AC-9 [%s]: Antwort %d %q muss der unbekannten Kennung (%d %q) gleichen",
				f.name, w.Code, w.Body.String(), ref.Code, ref.Body.String())
		}
	}

	// Bekannte Adresse (andere Schreibweise): Zeremonie fuer rita2194.
	w := rufe(" Rita@Beispiel.DE ")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-9: Passkey-Login-Begin per E-Mail erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &beginResp); err != nil || beginResp.PublicKey.Challenge == "" {
		t.Fatalf("AC-9: Begin-Antwort ohne Challenge (%v): %s", err, w.Body.String())
	}

	finishBody := auth.MakeAssertionResponse(t, beginResp.PublicKey.Challenge, 1)
	finish := PasskeyLoginFinishHandler(s, wa, cs, "test-secret-32-chars-long-enough", "")
	fw := httptest.NewRecorder()
	finish.ServeHTTP(fw, httptest.NewRequest(http.MethodPost, "/api/auth/passkey/login/finish", bytes.NewReader(finishBody)))
	if fw.Code != http.StatusOK {
		t.Fatalf("AC-9: Passkey-Login-Finish erwartet 200, bekommen %d: %s", fw.Code, fw.Body.String())
	}
	var sess *http.Cookie
	for _, c := range fw.Result().Cookies() {
		if c.Name == "gz_session" {
			sess = c
		}
	}
	if sess == nil || !strings.HasPrefix(sess.Value, "rita2194.") {
		t.Errorf("AC-9: Sitzung muss dem aufgeloesten Konto rita2194 gehoeren, Cookie=%v", sess)
	}
}

// registriereOeffentlich2194 fuehrt eine oeffentliche Passkey-Registrierung
// (Begin + Finish) durch und liefert die vergebene Konto-ID.
func registriereOeffentlich2194(t *testing.T, s *store.Store, beginRumpf string) string {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	bw := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(bw,
		httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin", strings.NewReader(beginRumpf)))
	if bw.Code != http.StatusOK {
		t.Fatalf("AC-13: Begin mit %s erwartet 200, bekommen %d: %s", beginRumpf, bw.Code, bw.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(bw.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-13: Begin-Antwort: %v", err)
	}
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	fw := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, "test-secret-32-chars-long-enough", config.Config{}).ServeHTTP(fw,
		httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/finish",
			bytes.NewReader(auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge))))
	if fw.Code != http.StatusCreated {
		t.Fatalf("AC-13: Finish erwartet 201, bekommen %d: %s", fw.Code, fw.Body.String())
	}
	var resp struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(fw.Body.Bytes(), &resp); err != nil {
		t.Fatalf("AC-13: Finish-Antwort: %v", err)
	}
	return resp.ID
}

func TestPasskeyOeffentlicheRegistrierungVergibtOpakeID_AC13_2194(t *testing.T) {
	s := newTestStore(t)

	id1 := registriereOeffentlich2194(t, s, `{"email":"neu1-2194@beispiel.de"}`)
	id2 := registriereOeffentlich2194(t, s, `{"username":"wunschname2194","email":"neu2-2194@beispiel.de"}`)

	for _, id := range []string{id1, id2} {
		if !opakeID2194.MatchString(id) {
			t.Errorf("AC-13: Konto-ID %q passt nicht zu ^u-[0-9a-f]{8}$", id)
		}
		if u, err := s.LoadUser(id); err != nil || u == nil {
			t.Errorf("AC-13: Konto %q nach der Registrierung nicht ladbar (err=%v)", id, err)
		}
	}
	if id1 == id2 {
		t.Errorf("AC-13: zwei Registrierungen lieferten dieselbe ID %q", id1)
	}
	if s.UserExists("wunschname2194") {
		t.Errorf("AC-13: ein im Rumpf mitgesendeter username darf kein Konto mit diesem Namen anlegen")
	}
}
