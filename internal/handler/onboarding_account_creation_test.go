package handler

// TDD RED — Onboarding S2: Merkmal "neu eingeladen" (`onboarding_pending`).
// Spec: docs/specs/modules/onboarding_willkommen_checkliste.md — AC-1.
//
// Zusicherung: JEDER der vier nutzerseitigen Anlagewege legt das Konto mit
// `onboarding_pending: true` in user.json an — Registrierung (mit und ohne
// Einladung, RegisterHandlerWithInvites), Magic-Link (createMagicLinkUser beim
// Einloesen), Google-OAuth (createOAuthUser im Callback),
// Passkey-Registrierung (PasskeyRegisterPublicFinishHandler). Eine Anmeldung in
// ein BESTEHENDES Konto setzt es nie (Bestandsnutzer sehen nichts).
//
// Je Weg eine eigene Testfunktion: wird der Helfer-Aufruf in genau einem Weg
// weggelassen, wird genau dieser Test rot. Die Fixtures schreiben das Feld
// NIE selbst — das Produkt muss es schreiben. Gemessen wird roh auf der Platte
// (kompiliert ohne das neue Modellfeld, rot per Assertion).
//
// Vorbild der Anlage-Rundlaeufe: register_mail_to_fallback_test.go (#2144).
// Der Verifikations-Mail-Seam wird gestubbt und es wird auf den Dispatch
// gewartet, bevor user.json gelesen wird.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/store"
)

// onbStubVerificationMail ersetzt den Versand-Seam; der Rueckkanal meldet
// jeden Dispatch, damit der Test vor dem Lesen auf die Goroutine warten kann.
func onbStubVerificationMail(t *testing.T) chan string {
	t.Helper()
	calls := make(chan string, 8)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- to
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return calls
}

func onbWaitDispatch(t *testing.T, calls chan string) {
	t.Helper()
	select {
	case <-calls:
	case <-time.After(2 * time.Second):
		t.Fatal("Messaufbau: Verifikations-Dispatch kam nicht innerhalb von 2s")
	}
}

func onbAssertPending(t *testing.T, s *store.Store, id, weg string) {
	t.Helper()
	m := onbReadRawUser(t, s, id)
	v, ok := m["onboarding_pending"]
	if !onbIstTrue(v, ok) {
		t.Errorf("AC-1 (%s): neu angelegtes Konto %q traegt onboarding_pending nicht als true "+
			"(Wert %s, vorhanden=%v) — der neue Nutzer saehe weder Willkommen noch Checkliste", weg, id, v, ok)
	}
}

// AC-1, Weg 1a: Registrierung MIT Einladung.
func TestRegisterWithInviteMarksAccountOnboardingPending(t *testing.T) {
	s := newTestStore(t)
	calls := onbStubVerificationMail(t)
	inv := store.NewInviteStore(t.TempDir())
	_, token, err := inv.Create("premium", "", "admin")
	if err != nil {
		t.Fatal(err)
	}

	h := RegisterHandlerWithInvites(s, 4, testRegisterCfg(), inv)
	body := `{"username":"onb-invite","password":"geheim-pw-123","email":"onb-invite@beispiel.de","invite":"` + token + `"}`
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body)))
	if w.Code != http.StatusCreated {
		t.Fatalf("Registrierung: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	onbWaitDispatch(t, calls)
	onbAssertPending(t, s, "onb-invite", "Registrierung mit Einladung")
}

// AC-1, Weg 1b: Registrierung OHNE Einladung — die Registrierung ist nicht auf
// Einladungen beschraenkt; faengt die Mutation "Merkmal nur bei invite".
func TestRegisterWithoutInviteMarksAccountOnboardingPending(t *testing.T) {
	s := newTestStore(t)
	calls := onbStubVerificationMail(t)

	h := RegisterHandlerWithInvites(s, 4, testRegisterCfg(), store.NewInviteStore(t.TempDir()))
	body := `{"username":"onb-offen","password":"geheim-pw-123","email":"onb-offen@beispiel.de"}`
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body)))
	if w.Code != http.StatusCreated {
		t.Fatalf("Registrierung: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	onbWaitDispatch(t, calls)
	onbAssertPending(t, s, "onb-offen", "Registrierung ohne Einladung")
}

// AC-1, Weg 2: Magic-Link — das Konto entsteht beim Einloesen des Codes.
func TestMagicLinkNewAccountMarksOnboardingPending(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: "", SessionSecret: "test-secret"}

	w := magicLinkAnmeldung(t, s, cfg, "onb-magic@beispiel.de")
	if w.Code != http.StatusOK {
		t.Fatalf("Magic-Link-Einloesen: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	ids, err := s.ListUserIDs()
	if err != nil || len(ids) != 1 {
		t.Fatalf("Messaufbau: genau ein neues Konto erwartet, bekommen %v (%v)", ids, err)
	}
	onbAssertPending(t, s, ids[0], "Magic-Link")
}

// AC-1, Wächter (heute schon gruen): Magic-Link-Anmeldung in ein BESTEHENDES
// Konto setzt das Merkmal nicht — sonst saehen Bestandsnutzer nach dem
// naechsten Login ploetzlich die Checkliste. Faengt die Mutation "Merkmal bei
// jedem Login statt bei jeder Anlage".
func TestMagicLinkLoginIntoExistingAccountDoesNotMarkOnboardingPending(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: "", SessionSecret: "test-secret"}
	const uid = "bestand2521"
	datei := onbAltdatei(uid)
	datei["email"] = "bestand2521@beispiel.de"
	datei["mail_to"] = "bestand2521@beispiel.de"
	onbWriteRawUser(t, s, uid, datei)

	w := magicLinkAnmeldung(t, s, cfg, "bestand2521@beispiel.de")
	if w.Code != http.StatusOK {
		t.Fatalf("Magic-Link-Login: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if ids, _ := s.ListUserIDs(); len(ids) != 1 {
		t.Fatalf("Messaufbau: Login darf kein zweites Konto anlegen, Konten: %v", ids)
	}
	if v, ok := onbReadRawUser(t, s, uid)["onboarding_pending"]; ok && !onbJSONEqual(v, json.RawMessage("false")) {
		t.Errorf("AC-1: Login in ein Bestandskonto hat onboarding_pending gesetzt (%s)", v)
	}
}

// AC-1, Weg 3: Google-OAuth — unbekannter sub legt ein Konto an.
func TestGoogleOAuthNewAccountMarksOnboardingPending(t *testing.T) {
	userinfoURL, tokenURL := oauthFakeServers(t, "sub-onb-2521", "onb-oauth@beispiel.de")
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      "test-session-secret",
		PublicHost:         "https://gregor20.henemm.com",
		SMTPHost:           "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}
	s := newTestStore(t)
	calls := onbStubVerificationMail(t)

	h := GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL)
	const state = "test-state-value"
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusFound {
		t.Fatalf("OAuth-Callback: erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
	}
	onbWaitDispatch(t, calls)

	neu, err := s.FindUserByOAuthSub("google", "sub-onb-2521")
	if err != nil || neu == nil {
		t.Fatalf("Messaufbau: neues OAuth-Konto fehlt: %v", err)
	}
	onbAssertPending(t, s, neu.ID, "Google-OAuth")
}

// AC-1, Weg 4: Passkey-Registrierung (Begin + Finish, echter Attestations-Rundlauf).
func TestPasskeyPublicRegistrationMarksOnboardingPending(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	beginBody := []byte(`{"username":"onb-pk","email":"onb-pk@beispiel.de"}`)
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody)))
	if beginW.Code != http.StatusOK {
		t.Fatalf("Passkey begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("Passkey begin: Antwort nicht lesbar: %v", err)
	}

	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	finishBody := auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, config.Config{}).ServeHTTP(finishW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody)))
	if finishW.Code != http.StatusCreated {
		t.Fatalf("Passkey finish: erwartet 201, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	onbAssertPending(t, s, "onb-pk", "Passkey-Registrierung")
}
