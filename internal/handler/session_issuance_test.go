package handler

// TDD RED — Issue #2129: dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal.
// Spec: docs/specs/modules/session_allowlist.md — AC-1, AC-13, AC-18.
//
// Alle SECHS Anmeldewege in einem Lauf. Das ist der Test mit dem größten
// Selbstschadens-Schutz: wird beim Umbau auch nur EINE der sechs
// Ausstellungsstellen vergessen, sperrt dieser Anmeldeweg alle seine Nutzer
// aus — und ohne diesen Test fiele das erst in Produktion auf.
//
// Kein Mock-Theater: Google läuft gegen zwei echte httptest-Server, die drei
// Passkey-Wege gegen den vorhandenen ECDSA-Testauthentifikator mit echter
// Kryptographie, Magic-Link gegen den echten Verify-Handler. Kein Netz, kein
// Versand — die Konten sind so geseedet, dass kein Verifikations-Dispatch
// anläuft.
//
// Diese Datei liegt bewusst in `package handler`: vier der sechs Wege sind nur
// paketintern anfahrbar (otpStore, registerForUser, newTestWebAuthn,
// oauthFakeServers). Von außen bräuchte man einen echten WebAuthn-Client und
// einen echten Google-Roundtrip.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const issuanceSecret = "test-secret-32-chars-minimum-ok!"

// minOneYearSeconds ist die geforderte Untergrenze der Cookie-Lebensdauer
// (AC-18). Bewusst eine harte Zahl: ein Test, der "irgendeine Lebensdauer"
// durchgehen ließe, ließe auch die heutigen 86400 Sekunden durch und prüfte
// damit nichts.
const minOneYearSeconds = 365 * 24 * 60 * 60

// issued bündelt, was ein Anmeldeweg hinterlässt.
type issued struct {
	cookie  *http.Cookie
	dataDir string
	userID  string
}

func sessionCookieFrom(t *testing.T, w *httptest.ResponseRecorder, way string) *http.Cookie {
	t.Helper()
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			return c
		}
	}
	t.Fatalf("%s: kein gz_session-Cookie in der Antwort (Status %d): %s", way, w.Code, w.Body.String())
	return nil
}

// probeIssuedCookie legt das ausgestellte Merkmal der echten AuthMiddleware vor.
//
// dataDir ist die Wurzel des Datenbestands: der Store wird FRISCH darüber
// gebaut, nicht aus dem Ausstellungslauf übernommen. Damit misst die Sonde die
// Gästeliste auf der Platte und nicht einen Prozesszustand, den die
// Ausstellungsstelle zufällig noch hält.
func probeIssuedCookie(t *testing.T, dataDir, cookieValue string) int {
	t.Helper()
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	rr := httptest.NewRecorder()
	middleware.AuthMiddleware(issuanceSecret, store.New(dataDir, ""))(http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			if middleware.UserIDFromContext(r.Context()) == "" {
				w.WriteHeader(http.StatusInternalServerError)
				return
			}
			w.WriteHeader(http.StatusOK)
		})).ServeHTTP(rr, req)
	return rr.Code
}

// --- die sechs Anmeldewege -------------------------------------------------

func mintViaPassword(t *testing.T) issued {
	t.Helper()
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: string(hash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	req := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(`{"username":"alice","password":"geheim123"}`))
	w := httptest.NewRecorder()
	LoginHandler(s, issuanceSecret).ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("Passwort-Anmeldung: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	return issued{cookie: sessionCookieFrom(t, w, "Passwort"), dataDir: s.DataDir, userID: "alice"}
}

func mintViaMagicLink(t *testing.T) issued {
	t.Helper()
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	const uid = "m-aabbccdd"
	if err := s.SaveUser(model.User{ID: uid, Email: "magic@example.com", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	otpStore.Store("magic@example.com", &otpEntry{
		code:      "123456",
		userID:    uid,
		expiresAt: time.Now().Add(15 * time.Minute),
	})

	cfg := &config.Config{SessionSecret: issuanceSecret}
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
		strings.NewReader(`{"email":"magic@example.com","code":"123456"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	MagicLinkVerifyHandler(s, cfg).ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("Magic-Link: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	return issued{cookie: sessionCookieFrom(t, w, "Magic-Link"), dataDir: s.DataDir, userID: uid}
}

func mintViaGoogle(t *testing.T) issued {
	t.Helper()
	s := newTestStore(t)

	// Konto vorab anlegen, damit der Callback den BESTANDS-Zweig nimmt: der
	// legt kein Konto an und löst deshalb keinen Verifikations-Dispatch aus.
	// Kein Mail-Versand aus diesem Test, auch nicht als Fire-and-Forget.
	const uid = "g-11223344"
	verified := time.Now()
	if err := s.SaveUser(model.User{
		ID: uid, Email: "google@example.com", OAuthProvider: "google", OAuthSub: "sub-2129",
		EmailVerifiedAt: &verified, CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	userinfoURL, tokenURL := oauthFakeServers(t, "sub-2129", "google@example.com")
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      issuanceSecret,
	}

	const state = "state-2129"
	req := httptest.NewRequest(http.MethodGet,
		"/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL).ServeHTTP(w, req)
	if w.Code != http.StatusFound {
		t.Fatalf("Google: erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
	}
	return issued{cookie: sessionCookieFrom(t, w, "Google"), dataDir: s.DataDir, userID: uid}
}

func mintViaPasskeyLogin(t *testing.T) issued {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	auth := registerForUser(t, s, wa, cs, "alice")

	beginW := httptest.NewRecorder()
	PasskeyLoginBeginHandler(s, wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
			bytes.NewReader([]byte(`{"username":"alice"}`))))
	if beginW.Code != 200 {
		t.Fatalf("Passkey-Login begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("Passkey-Login begin decode: %v", err)
	}

	finishW := httptest.NewRecorder()
	PasskeyLoginFinishHandler(s, wa, cs, issuanceSecret).ServeHTTP(finishW,
		httptest.NewRequest("POST", "/api/auth/passkey/login/finish",
			bytes.NewReader(auth.makeAssertionResponse(t, beginResp.PublicKey.Challenge, 1))))
	if finishW.Code != 200 {
		t.Fatalf("Passkey-Login finish: erwartet 200, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	return issued{cookie: sessionCookieFrom(t, finishW, "Passkey-Login"), dataDir: s.DataDir, userID: "alice"}
}

func mintViaPasskeyDiscoverable(t *testing.T) issued {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	const uid = "alice"
	auth := registerForUser(t, s, wa, cs, uid)

	beginW := httptest.NewRecorder()
	PasskeyLoginDiscoverableBeginHandler(wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil))
	if beginW.Code != http.StatusOK {
		t.Fatalf("Passkey-discoverable begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp map[string]interface{}
	_ = json.Unmarshal(beginW.Body.Bytes(), &beginResp)
	pk, _ := beginResp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		bytes.NewReader(auth.makeAssertionResponseDiscoverable(t, challenge, 1, uid)))
	finishReq.Header.Set("Content-Type", "application/json")
	finishW := httptest.NewRecorder()
	PasskeyLoginDiscoverableFinishHandler(s, wa, cs, issuanceSecret).ServeHTTP(finishW, finishReq)
	if finishW.Code != http.StatusOK {
		t.Fatalf("Passkey-discoverable finish: erwartet 200, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	return issued{cookie: sessionCookieFrom(t, finishW, "Passkey-discoverable"), dataDir: s.DataDir, userID: uid}
}

func mintViaPasskeyRegistration(t *testing.T) issued {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin",
			bytes.NewReader([]byte(`{"username":"passwordless","email":"pw@example.com"}`))))
	if beginW.Code != http.StatusOK {
		t.Fatalf("Passkey-Registrierung begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("Passkey-Registrierung begin decode: %v", err)
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishW := httptest.NewRecorder()
	// Leere config.Config: kein SMTPHost → kein Verifikations-Dispatch.
	PasskeyRegisterPublicFinishHandler(s, wa, cs, issuanceSecret, config.Config{}).ServeHTTP(finishW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish",
			bytes.NewReader(auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge))))
	if finishW.Code != http.StatusCreated {
		t.Fatalf("Passkey-Registrierung finish: erwartet 201, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	return issued{
		cookie:  sessionCookieFrom(t, finishW, "Passkey-Registrierung"),
		dataDir: s.DataDir,
		userID:  "passwordless",
	}
}

// AC-1 / AC-13 / AC-18: Jeder der sechs Anmeldewege stellt ein vierteiliges
// Anmelde-Merkmal aus, das die eigene Prüfung besteht und mindestens ein Jahr
// im Browser bleibt.
func TestAllSixLoginPaths_IssueFourPartCookie(t *testing.T) {
	ways := []struct {
		name string
		mint func(*testing.T) issued
	}{
		{"Passwort", mintViaPassword},
		{"Magic-Link", mintViaMagicLink},
		{"Google", mintViaGoogle},
		{"Passkey-Login", mintViaPasskeyLogin},
		{"Passkey-ohne-Kennungseingabe", mintViaPasskeyDiscoverable},
		{"Passkey-Registrierung", mintViaPasskeyRegistration},
	}

	if len(ways) != 6 {
		t.Fatalf("AC-13 verlangt sechs Anmeldewege, abgedeckt sind %d", len(ways))
	}

	for _, way := range ways {
		t.Run(way.name, func(t *testing.T) {
			got := way.mint(t)

			// AC-1: vierteiliges Merkmal.
			if n := len(strings.Split(got.cookie.Value, ".")); n != 4 {
				t.Errorf("AC-1/%s: erwartet 4 Punkt-Segmente, sind %d (%q)", way.name, n, got.cookie.Value)
			}
			if !strings.HasPrefix(got.cookie.Value, got.userID+".") {
				t.Errorf("AC-1/%s: Merkmal muss mit der Nutzerkennung %q beginnen, ist %q",
					way.name, got.userID, got.cookie.Value)
			}

			// AC-18: Lebensdauer mindestens ein Jahr — der heutige Wert 86400
			// darf diesen Nachweis nicht bestehen.
			if got.cookie.MaxAge < minOneYearSeconds {
				t.Errorf("AC-18/%s: MaxAge muss >= %d sein (ein Jahr), ist %d",
					way.name, minOneYearSeconds, got.cookie.MaxAge)
			}
			if !got.cookie.HttpOnly {
				t.Errorf("AC-18/%s: Merkmal muss HttpOnly bleiben", way.name)
			}
			if got.cookie.SameSite != http.SameSiteLaxMode {
				t.Errorf("AC-18/%s: SameSite muss Lax bleiben, ist %v", way.name, got.cookie.SameSite)
			}

			// AC-13: das ausgestellte Merkmal besteht die eigene Prüfung. Nach
			// GREEN ist das der Wächter dafür, dass diese Ausstellungsstelle
			// die Anmeldung auch wirklich in die Gästeliste eingetragen hat —
			// vergisst sie es, ist das Merkmal zwar wohlgeformt, aber nicht
			// gelistet und damit ungültig.
			if code := probeIssuedCookie(t, got.dataDir, got.cookie.Value); code != http.StatusOK {
				t.Errorf("AC-13/%s: ausgestelltes Merkmal muss die eigene Prüfung bestehen, bekommen %d",
					way.name, code)
			}
		})
	}
}
