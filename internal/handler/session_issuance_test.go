package handler

// TDD RED — Issue #2129: dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal.
// Spec: docs/specs/modules/session_allowlist.md — AC-1, AC-13, AC-18.
//
// Fortgeschrieben für Issue #2271 (S2 aus #2146, Epic #2138), Spec
// docs/specs/modules/email_verify_scharfschaltung_2271.md — AC-4..AC-8:
// Aus den SECHS Anmeldewegen werden drei Gruppen mit je EIGENEM Zähler —
// 5 stellen aus, 4 verweigern, 1 Sonderfall stellt gar kein Merkmal mehr aus.
// Ein einzelner Gesamtzähler fiele nicht auf, wenn ein Weg zwischen den
// Gruppen wanderte; er ist deshalb durch drei ersetzt, nicht gestrichen.
// Die Zusicherung "alle sechs stellen aus" nimmt ADR-0066 dokumentiert zurück.
//
// Das ist der Test mit dem größten Selbstschadens-Schutz: wird beim Umbau auch
// nur EINE der ausstellenden Stellen vergessen, sperrt dieser Anmeldeweg alle
// seine Nutzer aus — und ohne diesen Test fiele das erst in Produktion auf.
// Umgekehrt gilt seit #2271 dasselbe für die Verweigerungen: fällt eine weg,
// steht ein Anmeldeweg wieder offen, für den die Adresse nie bestätigt wurde.
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

// --- Gruppe 1: die fünf ausstellenden Anmeldewege ---------------------------
//
// #2271: Wo der Ausgangszustand eine bestätigte Adresse braucht, seeden diese
// Minter sie SELBST. Sie messen die Ausstellung, nicht das Gate — ein Minter,
// der unbestätigt seedet, wäre nach der Scharfschaltung aus dem falschen Grund
// rot und die Positiv-Gruppe damit wertlos.

func mintViaPassword(t *testing.T) issued {
	t.Helper()
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	verifiziert := time.Now().UTC()
	if err := s.SaveUser(model.User{
		ID: "alice", PasswordHash: string(hash),
		EmailVerifiedAt: &verifiziert, CreatedAt: time.Now(),
	}); err != nil {
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
	// #2271: bestätigt seeden, BEVOR registerForUser läuft. Der geteilte
	// Helfer seedet nur unter `if existing == nil` (passkey_test.go:969) —
	// ein vorgeschaltetes SaveUser gewinnt, ohne den Helfer anzufassen.
	seedeKonto2271(t, s, "alice", true)
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
	seedeKonto2271(t, s, uid, true) // #2271: siehe mintViaPasskeyLogin
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

// --- Gruppe 2: die vier verweigernden Anmeldewege (#2271) ------------------

// seedeKonto2271 legt ein Konto mit oder ohne bestätigte Adresse an — VOR dem
// geteilten Seeder registerForUserAt (passkey_test.go:962), der nur unter
// `if existing == nil` (:969) selbst seedet und ein bestehendes Konto deshalb
// unangetastet lässt. Bewusst hier statt im Helfer: würde der Helfer bestätigt
// seeden, spülte das ALLE Negativfälle unten stillschweigend grün.
func seedeKonto2271(t *testing.T, s *store.Store, uid string, bestaetigt bool) {
	t.Helper()
	konto := model.User{ID: uid, PasswordHash: "h", CreatedAt: time.Now()}
	if bestaetigt {
		jetzt := time.Now().UTC()
		konto.EmailVerifiedAt = &jetzt
	}
	if err := s.SaveUser(konto); err != nil {
		t.Fatalf("SaveUser %q: %v", uid, err)
	}
}

// abgewiesen bündelt, was ein verweigerter Anmeldeweg hinterlässt. Der Store
// gehört dazu, weil eine Verweigerung auch NICHTS bestätigt haben darf — bei
// OAuth ist genau das die zweite Hälfte der Zusicherung (AC-4).
type abgewiesen struct {
	code     int
	body     string
	location string
	cookie   *http.Cookie
	store    *store.Store
	userID   string
}

// sessionCookieOderNil ist die Gegenstückfunktion zu sessionCookieFrom: sie
// darf NICHT fatalen, denn die Abwesenheit des Cookies ist hier der Normalfall.
func sessionCookieOderNil(w *httptest.ResponseRecorder) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			return c
		}
	}
	return nil
}

// AC-1 (Tabellen-Anteil): Passwort-Login auf ein unbestätigtes Konto.
func denyViaPassword(t *testing.T) abgewiesen {
	t.Helper()
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: string(hash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	req := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(`{"username":"bob","password":"geheim123"}`))
	w := httptest.NewRecorder()
	LoginHandler(s, issuanceSecret).ServeHTTP(w, req)
	return abgewiesen{
		code: w.Code, body: strings.TrimSpace(w.Body.String()),
		cookie: sessionCookieOderNil(w), store: s, userID: "bob",
	}
}

// AC-2: Passkey-Login MIT Kennungseingabe auf ein unbestätigtes Konto.
func denyViaPasskeyLogin(t *testing.T) abgewiesen {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	const uid = "bob"
	seedeKonto2271(t, s, uid, false)
	auth := registerForUser(t, s, wa, cs, uid)

	beginW := httptest.NewRecorder()
	PasskeyLoginBeginHandler(s, wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
			bytes.NewReader([]byte(`{"username":"`+uid+`"}`))))
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
	return abgewiesen{
		code: finishW.Code, body: strings.TrimSpace(finishW.Body.String()),
		cookie: sessionCookieOderNil(finishW), store: s, userID: uid,
	}
}

// AC-3: Passkey-Login OHNE Kennungseingabe (discoverable) auf ein
// unbestätigtes Konto.
func denyViaPasskeyDiscoverable(t *testing.T) abgewiesen {
	t.Helper()
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	const uid = "bob"
	seedeKonto2271(t, s, uid, false)
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
	return abgewiesen{
		code: finishW.Code, body: strings.TrimSpace(finishW.Body.String()),
		cookie: sessionCookieOderNil(finishW), store: s, userID: uid,
	}
}

// AC-4: Google-OAuth auf ein unbestätigtes Bestandskonto, dessen effektive
// Kontaktadresse von der durch Google bestätigten ABWEICHT — die Selbstheilung
// greift dort nicht (EqualFold in selfHealEmailVerification schlägt fehl), also
// bleibt das Konto unbestätigt und die Vorprüfung muss es abweisen.
//
// Ohne diesen Fall wäre der Deny-Zweig im OAuth-Fluss toter Code.
func denyViaGoogleAdressabweichung(t *testing.T) abgewiesen {
	t.Helper()
	s := newTestStore(t)

	// Bestands-Zweig erzwingen (OAuthProvider+OAuthSub passend zum Fake-Server):
	// im Neuanlage-Zweig liefe createOAuthUser und der Test misst etwas anderes.
	const uid = "g-2271-abw"
	if err := s.SaveUser(model.User{
		ID: uid, Email: "anders@example.com", MailTo: "anders@example.com",
		OAuthProvider: "google", OAuthSub: "sub-2271-abw", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	userinfoURL, tokenURL := oauthFakeServers(t, "sub-2271-abw", "google@example.com")
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      issuanceSecret,
	}

	const state = "state-2271-abw"
	req := httptest.NewRequest(http.MethodGet,
		"/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL).ServeHTTP(w, req)
	return abgewiesen{
		code: w.Code, body: strings.TrimSpace(w.Body.String()),
		location: w.Header().Get("Location"),
		cookie:   sessionCookieOderNil(w), store: s, userID: uid,
	}
}

// #2129 AC-1/AC-13/AC-18 · #2271 AC-6: Die FÜNF ausstellenden Anmeldewege
// stellen ein vierteiliges Anmelde-Merkmal aus, das die eigene Prüfung besteht
// und mindestens ein Jahr im Browser bleibt.
//
// #2271 AC-6: Der Zähler ist von 6 auf 5 gewandert, nicht gefallen. Der
// Magic-Link-Eintrag ist zugleich der Wächter über die Reihenfolge
// Heilung-vor-Gate: liefe das Gate zuerst, fehlte dort das Cookie und die
// Gruppe hätte nur vier Einträge.
func TestIssuingLoginPaths_IssueFourPartCookie(t *testing.T) {
	issuing := []struct {
		name string
		mint func(*testing.T) issued
	}{
		{"Passwort", mintViaPassword},
		{"Magic-Link", mintViaMagicLink},
		{"Google", mintViaGoogle},
		{"Passkey-Login", mintViaPasskeyLogin},
		{"Passkey-ohne-Kennungseingabe", mintViaPasskeyDiscoverable},
	}

	if len(issuing) != 5 {
		t.Fatalf("#2271 AC-6 verlangt fünf ausstellende Anmeldewege, abgedeckt sind %d", len(issuing))
	}

	for _, way := range issuing {
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

// --- #2271 AC-7: die vier verweigernden Anmeldewege -------------------------

// Der Antwort-Vertrag des Gates (Spec "Antwortform"): JSON-Wege antworten 403
// mit genau diesem Körper, der OAuth-Redirect-Fluss ausschließlich über den
// Location-Parameter — kein rohes JSON in einem Redirect-Fluss.
const (
	verweigerungsKoerper2271 = `{"error":"email_not_verified"}`
	verweigerungsZiel2271    = "/login?error=email_not_verified"
)

// AC-7: Vier Anmeldewege verweigern das Merkmal, solange die Adresse
// unbestätigt ist. Der eigene Zähler ist nicht Kosmetik — eine Gruppe ohne ihn
// fängt einen vergessenen oder unbemerkt entfernten Blockierfall nicht, genau
// das, wogegen die alte `!= 6`-Zeile stand.
func TestBlockingLoginPaths_RefuseUnverifiedAccounts(t *testing.T) {
	blocking := []struct {
		name string
		// perRedirect: Die Ablehnung reist im Location-Header, nicht im
		// Statuscode. Bei OAuth sind Erfolg UND Ablehnung beide 302 — ein
		// Statuscode-Assert bewachte dort nichts.
		perRedirect bool
		deny        func(*testing.T) abgewiesen
	}{
		{"Passwort-unbestaetigt", false, denyViaPassword},
		{"Passkey-Login-unbestaetigt", false, denyViaPasskeyLogin},
		{"Passkey-ohne-Kennungseingabe-unbestaetigt", false, denyViaPasskeyDiscoverable},
		{"Google-Adressabweichung", true, denyViaGoogleAdressabweichung},
	}

	if len(blocking) != 4 {
		t.Fatalf("#2271 AC-7 verlangt vier verweigernde Anmeldewege, abgedeckt sind %d", len(blocking))
	}

	for _, way := range blocking {
		t.Run(way.name, func(t *testing.T) {
			got := way.deny(t)

			if way.perRedirect {
				// AC-4: der Location-Header trägt die Aussage.
				if got.location != verweigerungsZiel2271 {
					t.Errorf("AC-7/%s: erwartet Weiterleitung auf %q, bekommen %q (Status %d, Körper %s)",
						way.name, verweigerungsZiel2271, got.location, got.code, got.body)
				}
			} else {
				if got.code != http.StatusForbidden {
					t.Errorf("AC-7/%s: erwartet 403, bekommen %d: %s", way.name, got.code, got.body)
				}
				if got.body != verweigerungsKoerper2271 {
					t.Errorf("AC-7/%s: erwarteter Antwortkörper %s, bekommen %q",
						way.name, verweigerungsKoerper2271, got.body)
				}
			}

			// Gemeinsam für alle vier: kein Anmelde-Merkmal.
			if got.cookie != nil {
				t.Errorf("AC-7/%s: verweigerter Anmeldeweg darf kein gz_session-Cookie setzen, bekommen %q",
					way.name, got.cookie.Value)
			}

			// Und: eine Verweigerung bestätigt nebenbei nichts. Bei AC-4 ist das
			// die zweite Hälfte der Zusicherung — sonst bliebe "abgewiesen, aber
			// im selben Zug bestätigt" unbemerkt.
			nutzer, err := got.store.LoadUser(got.userID)
			if err != nil || nutzer == nil {
				t.Fatalf("AC-7/%s: Nutzer %q nach dem Versuch nicht ladbar: %v", way.name, got.userID, err)
			}
			if nutzer.EmailVerifiedAt != nil {
				t.Errorf("AC-7/%s: ein verweigerter Anmeldeweg darf die Adresse nicht bestätigen, "+
					"email_verified_at ist %v", way.name, nutzer.EmailVerifiedAt)
			}
		})
	}
}

// --- #2271 AC-8: der Sonderfall --------------------------------------------

// AC-8: Die öffentliche Passkey-Registrierung stellt KEIN Merkmal mehr aus.
// Sie bleibt 201 — die Kontoerstellung war erfolgreich, ein 403 wäre hier
// falsch — verliert aber das Auto-Login und weist stattdessen auf die
// ausstehende Bestätigung hin.
//
// Bewusst eigenständig statt als sechster Tabelleneintrag: die Positiv-Gruppe
// holt ihr Cookie über sessionCookieFrom, das ohne Cookie fatal abbricht.
func TestPasskeyPublicRegistration_IssuesNoSession(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin",
			bytes.NewReader([]byte(`{"username":"passwordless","email":"pw@example.com"}`))))
	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-8 begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-8 begin decode: %v", err)
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishW := httptest.NewRecorder()
	// Leere config.Config: kein SMTPHost → kein Verifikations-Dispatch.
	PasskeyRegisterPublicFinishHandler(s, wa, cs, issuanceSecret, config.Config{}).ServeHTTP(finishW,
		httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish",
			bytes.NewReader(auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge))))

	if finishW.Code != http.StatusCreated {
		t.Fatalf("AC-8: die Kontoerstellung bleibt erfolgreich — erwartet 201, bekommen %d: %s",
			finishW.Code, finishW.Body.String())
	}
	if c := sessionCookieOderNil(finishW); c != nil {
		t.Errorf("AC-8: die öffentliche Passkey-Registrierung darf kein gz_session-Cookie mehr "+
			"ausstellen (Auto-Login entfällt), bekommen %q", c.Value)
	}

	// Der Hinweis auf die ausstehende Bestätigung ist maschinenlesbar, damit
	// der Nachweis nicht an einer Formulierung hängt.
	var antwort map[string]string
	if err := json.Unmarshal(finishW.Body.Bytes(), &antwort); err != nil {
		t.Fatalf("AC-8: Antwortkörper nicht lesbar: %v (%s)", err, finishW.Body.String())
	}
	if antwort["status"] != "verification_pending" {
		t.Errorf("AC-8: Antwort muss auf die ausstehende Bestätigung hinweisen "+
			`(status "verification_pending"), bekommen %q`, finishW.Body.String())
	}
	if antwort["id"] != "passwordless" {
		t.Errorf("AC-8: die angelegte Kennung muss weiter in der Antwort stehen, bekommen %q",
			finishW.Body.String())
	}
}

// --- #2271 AC-5: die Reihenfolge Heilung-vor-Gate bei Google ----------------

// AC-5: Ein unbestätigtes Bestandskonto, dessen effektive Kontaktadresse der
// von Google bestätigten entspricht, heilt sich IM SELBEN Request und kommt
// durch — Location `/`, nicht der Fehlerpfad, und danach ist die Adresse
// bestätigt.
//
// Diese Reihenfolge war bei OAuth bisher unbewacht: mintViaGoogle seedet
// vorverifiziert, selfHealEmailVerification steigt dort sofort aus
// (auth.go:800), eine Vertauschung wäre unsichtbar geblieben. Beide
// Zusicherungen stehen deshalb in DERSELBEN Funktion — ein Statuscode-Assert
// allein bewachte nichts, weil Erfolg und Ablehnung beide 302 sind.
func TestGoogleOAuth_SelfHealRunsBeforeGate(t *testing.T) {
	s := newTestStore(t)

	const uid = "g-2271-heilung"
	const googleAdresse = "google@example.com"
	if err := s.SaveUser(model.User{
		ID: uid, Email: googleAdresse, MailTo: googleAdresse,
		OAuthProvider: "google", OAuthSub: "sub-2271-heilung", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	userinfoURL, tokenURL := oauthFakeServers(t, "sub-2271-heilung", googleAdresse)
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      issuanceSecret,
	}

	const state = "state-2271-heilung"
	req := httptest.NewRequest(http.MethodGet,
		"/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL).ServeHTTP(w, req)

	if ziel := w.Header().Get("Location"); ziel != "/" {
		t.Errorf("AC-5: ein Konto, das sich in diesem Request heilt, muss durchkommen — "+
			"erwartet Location %q, bekommen %q (Status %d)", "/", ziel, w.Code)
	}
	if c := sessionCookieOderNil(w); c == nil {
		t.Errorf("AC-5: das geheilte Konto muss ein gz_session-Cookie bekommen, es gibt keins (Status %d)", w.Code)
	}

	nutzer, err := s.LoadUser(uid)
	if err != nil || nutzer == nil {
		t.Fatalf("AC-5: Nutzer %q nach dem Callback nicht ladbar: %v", uid, err)
	}
	if nutzer.EmailVerifiedAt == nil {
		t.Error("AC-5: die Selbstheilung muss email_verified_at gesetzt haben — es ist nil")
	}
}
