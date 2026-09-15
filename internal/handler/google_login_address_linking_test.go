package handler

// TDD RED — Issue #2147 Scheibe C (Epic #2138): Google-Login verknüpft statt
// ein Doppelkonto anzulegen.
// Spec: docs/specs/modules/google_login_adress_verknuepfung.md — AC-1..AC-15
// (AC-16/AC-17 in internal/store/address_collisions_test.go, AC-18 im
// Frontend, AC-19 in tests/test_adr_0067_adress_eindeutigkeit_doku.py).
//
// Geprüft wird am WIRKORT: der echte Callback (GoogleOAuthCallbackHandlerWithEndpoints)
// gegen einen echten store.Store auf t.TempDir(). Google selbst ist ein echter
// HTTP-Gegenüber (httptest) — Token- und Userinfo-Endpoint; welcher Nutzer sich
// meldet, entscheidet der Autorisierungs-Code der Anfrage. Beobachtet werden
// Location-Header (inkl. error=-Code), Session-Cookie, danach frisch von der
// Platte gelesene Konten, rohe user.json-/sessions.json-Bytes und der
// Versandaufruf an der bestehenden Naht sendVerificationMailFn.
//
// Die Datei nennt KEINE neuen Produktivsymbole — das Handler-Testpaket muss
// unverändert kompilieren.
//
// Wiederverwendete Helfer (gleiches Paket): newTestStore, speichereKonto,
// kontenAnzahl, rohesKonto, roheGaesteliste, ladeKonto, jetztBestaetigt,
// sitzungen, alteSitzung, hatSessionCookie, sessionCookieOderNil,
// eindeutigSecret, schreibpfadAdresseHalterAnzahl, schreibpfadPasswort,
// dateienAusserKontoUndSitzungen, reichesKonto2304, seedTrip. Neue Helfer
// tragen das Präfix googleLink.
//
// WICHTIG für Fixtures: keine Kontokennung darf "test"/"tdd" enthalten — sonst
// überspringt forEachRealAccount das Konto UND der Versand läuft über den nicht
// beobachtbaren Testnutzer-Zweig.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	googleLinkZielAbgelehnt = "/login?error=oauth_link_failed"
	googleLinkZielFehler    = "/login?error=oauth_failed"
)

// --- Fake-Google -------------------------------------------------------------

type googleLinkIdentitaet struct {
	sub      string
	email    string
	verified bool
}

// googleLinkGoogle ist ein echter HTTP-Gegenüber für Token- und
// Userinfo-Endpoint. Der Autorisierungs-Code einer Callback-Anfrage wählt die
// Identität (Code -> Access-Token "tok-<code>" -> Userinfo). So können mehrere
// Anmeldungen parallel gegen DIESELBEN Server laufen (Race-Tests), ohne je
// Runde neue Listener zu öffnen.
type googleLinkGoogle struct {
	userinfoURL string
	tokenURL    string

	mu           sync.Mutex
	identitaeten map[string]googleLinkIdentitaet
	vorAntwort   func() // optional: läuft im Userinfo-Handler vor der Antwort
}

func googleLinkFakeGoogle(t *testing.T) *googleLinkGoogle {
	t.Helper()
	g := &googleLinkGoogle{identitaeten: map[string]googleLinkIdentitaet{}}

	token := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"access_token": "tok-" + r.PostFormValue("code"),
			"token_type":   "Bearer",
			"expires_in":   3600,
		})
	}))
	t.Cleanup(token.Close)

	userinfo := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		code := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer tok-")
		g.mu.Lock()
		id, ok := g.identitaeten[code]
		hook := g.vorAntwort
		g.mu.Unlock()
		if hook != nil {
			hook()
		}
		if !ok {
			http.Error(w, "unknown code", http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"sub":            id.sub,
			"email":          id.email,
			"email_verified": id.verified,
		})
	}))
	t.Cleanup(userinfo.Close)

	g.tokenURL, g.userinfoURL = token.URL, userinfo.URL
	return g
}

// setzeVorAntwort hängt den Userinfo-Haken unter der Sperre ein (der
// Server-Handler liest ihn nebenläufig).
func (g *googleLinkGoogle) setzeVorAntwort(fn func()) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.vorAntwort = fn
}

func (g *googleLinkGoogle) identitaet(code, sub, email string, verified bool) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.identitaeten[code] = googleLinkIdentitaet{sub: sub, email: email, verified: verified}
}

// googleLinkCfg: SMTPHost gesetzt, sonst überspringt der Versandweg für
// Nicht-Testkonten die Naht sendVerificationMailFn. 127.0.0.1:1 verhindert,
// dass ein Irrweg über SendWithFallback je das Netz erreicht.
func googleLinkCfg() *config.Config {
	return &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      eindeutigSecret,
		PublicHost:         "https://gregor20.henemm.com",
		SMTPHost:           "127.0.0.1",
		SMTPPort:           1,
	}
}

func googleLinkAnfrage(code string) *http.Request {
	state := "state-" + code
	req := httptest.NewRequest(http.MethodGet,
		"/api/auth/google/callback?code="+code+"&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	return req
}

func (g *googleLinkGoogle) handler(s *store.Store) http.HandlerFunc {
	return GoogleOAuthCallbackHandlerWithEndpoints(googleLinkCfg(), s, g.userinfoURL, g.tokenURL)
}

// handlerOhneVersand: wie handler, aber ohne SMTPHost — der Versandweg steigt
// vor jeder Goroutine aus. Für die Race-Tests: dort ist Versand nicht Gegenstand,
// und nachlaufende Versand-Goroutinen würden die Naht sendVerificationMailFn
// über das Testende hinaus lesen (Data Race mit dem Zurücksetzen).
func (g *googleLinkGoogle) handlerOhneVersand(s *store.Store) http.HandlerFunc {
	cfg := googleLinkCfg()
	cfg.SMTPHost, cfg.SMTPPort = "", 0
	return GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, g.userinfoURL, g.tokenURL)
}

func (g *googleLinkGoogle) anmelden(s *store.Store, code string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	g.handler(s).ServeHTTP(w, googleLinkAnfrage(code))
	return w
}

// googleLinkEinmal: eine Anmeldung mit genau einer Identität gegen frische Server.
func googleLinkEinmal(t *testing.T, s *store.Store, sub, email string, verified bool) *httptest.ResponseRecorder {
	t.Helper()
	g := googleLinkFakeGoogle(t)
	g.identitaet("code-einmal", sub, email, verified)
	return g.anmelden(s, "code-einmal")
}

// --- Beobachtung -------------------------------------------------------------

type googleLinkVersand struct {
	to  string
	msg mail.Mail
}

// googleLinkBeobachteVersand hängt sich an die bestehende Versand-Naht. antwort
// bestimmt den Rückgabewert des „SMTP-Versands" (nil = Erfolg).
func googleLinkBeobachteVersand(t *testing.T, antwort func(to string) error) chan googleLinkVersand {
	t.Helper()
	ch := make(chan googleLinkVersand, 16)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, msg mail.Mail) error {
		// Nie blockieren: die Race-Tests (AC-13/AC-14) erzeugen nach GREEN
		// hunderte Versandversuche, die niemand liest — ein volles Kanalpuffer
		// ließe sonst jede Versand-Goroutine dauerhaft hängen. Die Einzeltests
		// lesen nur die ersten Einträge.
		select {
		case ch <- googleLinkVersand{to: to, msg: msg}:
		default:
		}
		if antwort != nil {
			return antwort(to)
		}
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return ch
}

// googleLinkLogPuffer ist ein nebenläufigkeitsfester Log-Mitschnitt (der
// Versand-Log entsteht in einer Goroutine).
type googleLinkLogPuffer struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (p *googleLinkLogPuffer) Write(b []byte) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.b.Write(b)
}

func (p *googleLinkLogPuffer) String() string {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.b.String()
}

func googleLinkMitschnitt(t *testing.T) *googleLinkLogPuffer {
	t.Helper()
	p := &googleLinkLogPuffer{}
	log.SetOutput(p)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	return p
}

// googleLinkSitzungGehoert: das ausgestellte gz_session-Merkmal beginnt mit uid.
func googleLinkSitzungGehoert(w *httptest.ResponseRecorder, uid string) bool {
	c := sessionCookieOderNil(w)
	return c != nil && strings.HasPrefix(c.Value, uid+".")
}

// googleLinkSubAnzahl zählt ALLE Konten (auch Testkonten), die google/sub tragen.
func googleLinkSubAnzahl(t *testing.T, s *store.Store, sub string) int {
	t.Helper()
	ids, err := s.ListUserIDs()
	if err != nil {
		t.Fatalf("ListUserIDs: %v", err)
	}
	n := 0
	for _, id := range ids {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			continue
		}
		if u.OAuthProvider == "google" && u.OAuthSub == sub {
			n++
		}
	}
	return n
}

// googleLinkFelderAusser vergleicht zwei Kontostände feldweise über ihre
// JSON-Darstellung (Vereinigung beider Schlüsselmengen), ausgenommen die
// genannten JSON-Schlüssel.
func googleLinkFelderAusser(t *testing.T, was string, vorher, nachher *model.User, ausgenommen ...string) {
	t.Helper()
	karte := func(u *model.User) map[string]json.RawMessage {
		roh, err := json.Marshal(u)
		if err != nil {
			t.Fatalf("%s: Konto nicht serialisierbar: %v", was, err)
		}
		var m map[string]json.RawMessage
		if err := json.Unmarshal(roh, &m); err != nil {
			t.Fatalf("%s: Konto nicht lesbar: %v", was, err)
		}
		for _, k := range ausgenommen {
			delete(m, k)
		}
		return m
	}
	a, b := karte(vorher), karte(nachher)
	keys := map[string]bool{}
	for k := range a {
		keys[k] = true
	}
	for k := range b {
		keys[k] = true
	}
	for k := range keys {
		if string(a[k]) != string(b[k]) {
			t.Errorf("%s: Feld %q verändert — vorher %s, nachher %s", was, k, string(a[k]), string(b[k]))
		}
	}
}

// googleLinkPruefeAbgelehnt: Location exakt erwartet, kein Session-Cookie.
func googleLinkPruefeAbgelehnt(t *testing.T, ac string, w *httptest.ResponseRecorder, ziel string) {
	t.Helper()
	if w.Code != http.StatusFound || w.Header().Get("Location") != ziel {
		t.Errorf("%s: erwartet 302 auf %q, bekommen %d auf %q", ac, ziel, w.Code, w.Header().Get("Location"))
	}
	if c := sessionCookieOderNil(w); c != nil {
		t.Errorf("%s: abgelehnter Callback darf kein gz_session-Cookie setzen, bekommen %q", ac, c.Value)
	}
}

func googleLinkPasswortHash(t *testing.T) string {
	t.Helper()
	h, err := bcrypt.GenerateFromPassword([]byte("geheim-genug-2147c"), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	return string(h)
}

// --- AC-1 --------------------------------------------------------------------

// AC-1: freie Adresse, Google liefert sie mit Groß-/Kleinschreibung und
// Randleerzeichen -> Neukonto mit NORMALISIERTER Email und MailTo.
func TestGoogleLink_AC1_FreieAdresseErgibtNeukontoMitNormalisierterAdresse(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	googleLinkBeobachteVersand(t, nil)

	const sub = "sub-neu-ac1-2147c"
	w := googleLinkEinmal(t, s, sub, "  Neu-AC1-2147c@Beispiel.DE ", true)
	if w.Code != http.StatusFound {
		t.Fatalf("AC-1: erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
	}

	if n := kontenAnzahl(t, s); n != 1 {
		t.Fatalf("AC-1: genau ein Neukonto erwartet, vorhanden: %d", n)
	}
	u, err := s.FindUserByOAuthSub("google", sub)
	if err != nil || u == nil {
		t.Fatalf("AC-1: Neukonto mit google/%s fehlt: %v", sub, err)
	}
	const norm = "neu-ac1-2147c@beispiel.de"
	if u.Email != norm || u.MailTo != norm {
		t.Errorf("AC-1: Neukonto muss normalisiert gespeichert werden — erwartet email=mail_to=%q, ist email=%q mail_to=%q",
			norm, u.Email, u.MailTo)
	}
}

// --- AC-2 --------------------------------------------------------------------

// AC-2 (Wächter): die Google-Adresse steht nur als ausstehende Adresse eines
// fremden Kontos -> Neukonto, fremdes Konto byteidentisch.
func TestGoogleLink_AC2_AusstehendeFremdadresseGiltAlsFrei(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	googleLinkBeobachteVersand(t, nil)

	const fremd = "wechsler-ac2-2147c"
	const neu = "neu-ac2-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: fremd, Email: "alt-ac2-2147c@beispiel.de",
		MailTo: "alt-ac2-2147c@beispiel.de", PasswordHash: googleLinkPasswortHash(t),
		EmailVerifiedAt: jetztBestaetigt(), PendingContactAddress: neu, PendingContactField: "mail_to"})
	vorher := rohesKonto(t, s, fremd)

	const sub = "sub-ac2-2147c"
	w := googleLinkEinmal(t, s, sub, neu, true)
	if w.Code != http.StatusFound {
		t.Fatalf("AC-2: erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
	}
	if loc := w.Header().Get("Location"); loc == googleLinkZielAbgelehnt || loc == googleLinkZielFehler {
		t.Errorf("AC-2: eine nur ausstehende Fremdadresse ist frei — keine Ablehnung erwartet, bekommen %q", loc)
	}
	if n := kontenAnzahl(t, s); n != 2 {
		t.Errorf("AC-2: fremdes Konto + genau ein Neukonto erwartet, vorhanden: %d", n)
	}
	u, err := s.FindUserByOAuthSub("google", sub)
	if err != nil || u == nil || u.ID == fremd {
		t.Fatalf("AC-2: Neukonto für google/%s fehlt (oder landete im fremden Konto): %v / %+v", sub, err, u)
	}
	if u.Email != neu || u.MailTo != neu {
		t.Errorf("AC-2: Neukonto muss %q tragen, ist email=%q mail_to=%q", neu, u.Email, u.MailTo)
	}
	if !bytes.Equal(vorher, rohesKonto(t, s, fremd)) {
		t.Errorf("AC-2: das fremde Konto mit der ausstehenden Adresse wurde verändert")
	}
}

// --- AC-3 --------------------------------------------------------------------

// AC-3: bestätigtes Konto ohne OAuthSub, wirksame Adresse == Google-Adresse,
// email_verified=true -> Verknüpfung: OAuthProvider/OAuthSub gesetzt,
// EmailVerifiedAt unverändert, bestehende Sitzungen bleiben, kein Neukonto,
// Hinweis-Mail an die wirksame Adresse (ohne einlösbaren Token). Auch bei
// abweichender Groß-/Kleinschreibung bzw. Randleerzeichen der Google-Adresse.
func TestGoogleLink_AC3_BestaetigterInhaberWirdVerknuepft(t *testing.T) {
	const wirksam = "foo-ac3-2147c@beispiel.de"
	faelle := []struct {
		name        string
		email       string // gespeichertes Feld email
		googleEmail string // was Google liefert
	}{
		{"exakt", wirksam, wirksam},
		{"grossschreibung", wirksam, "Foo-AC3-2147c@Beispiel.de"},
		{"randleerzeichen", wirksam, "  foo-ac3-2147c@beispiel.de "},
		{"kontaktadresse-weicht-von-email-ab", "alt-ac3-2147c@beispiel.de", "FOO-ac3-2147c@beispiel.de"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			versand := googleLinkBeobachteVersand(t, nil)

			const uid = "wanderer-ac3-2147c"
			speichereKonto(t, s, model.User{ID: uid, Email: f.email, MailTo: wirksam,
				PasswordHash: googleLinkPasswortHash(t), DisplayName: "Wanderer",
				EmailVerifiedAt: jetztBestaetigt()})
			alt1 := alteSitzung(t, s, uid)
			alt2 := alteSitzung(t, s, uid)
			vorher := ladeKonto(t, s, uid)

			const sub = "sub-link-ac3-2147c"
			w := googleLinkEinmal(t, s, sub, f.googleEmail, true)

			if loc := w.Header().Get("Location"); w.Code != http.StatusFound || loc != "/" {
				t.Errorf("AC-3: Verknüpfung muss anmelden — erwartet 302 auf \"/\", bekommen %d auf %q", w.Code, loc)
			}
			if !googleLinkSitzungGehoert(w, uid) {
				t.Errorf("AC-3: das ausgestellte Session-Cookie muss dem verknüpften Konto %q gehören, ist %v",
					uid, sessionCookieOderNil(w))
			}
			if n := kontenAnzahl(t, s); n != 1 {
				t.Errorf("AC-3: kein Neukonto erlaubt — %d Konten statt 1", n)
			}
			nachher := ladeKonto(t, s, uid)
			if nachher.OAuthProvider != "google" || nachher.OAuthSub != sub {
				t.Errorf("AC-3: erwartet oauth_provider=google oauth_sub=%q, ist %q/%q",
					sub, nachher.OAuthProvider, nachher.OAuthSub)
			}
			if vorher.EmailVerifiedAt == nil || nachher.EmailVerifiedAt == nil ||
				!vorher.EmailVerifiedAt.Equal(*nachher.EmailVerifiedAt) {
				t.Errorf("AC-3: EmailVerifiedAt darf nicht angefasst werden — vorher %v, nachher %v",
					vorher.EmailVerifiedAt, nachher.EmailVerifiedAt)
			}
			googleLinkFelderAusser(t, "AC-3/"+f.name, vorher, nachher, "oauth_provider", "oauth_sub")

			gefunden := map[string]bool{}
			liste := sitzungen(t, s, uid)
			for _, sess := range liste {
				gefunden[sess.ID] = true
			}
			if !gefunden[alt1] || !gefunden[alt2] {
				t.Errorf("AC-3: bestehende Sitzungen müssen gültig bleiben (kein ClearSessions) — alt1=%v alt2=%v",
					gefunden[alt1], gefunden[alt2])
			}
			if len(liste) != 3 {
				t.Errorf("AC-3: zwei alte + genau eine neue Sitzung erwartet, vorhanden: %d", len(liste))
			}

			select {
			case v := <-versand:
				if v.to != wirksam {
					t.Errorf("AC-3: Hinweis-Mail ging an %q statt an die wirksame Adresse %q", v.to, wirksam)
				}
				body := v.msg.PlainBody + v.msg.HTMLBody
				if strings.Contains(body, "token=") || strings.Contains(body, "/verify-email") {
					t.Errorf("AC-3: die Hinweis-Mail darf keinen einlösbaren Link/Token enthalten: %q", v.msg.PlainBody)
				}
			case <-time.After(3 * time.Second):
				t.Errorf("AC-3: keine Hinweis-Mail über den bestehenden Auth-Versandweg (sendVerificationMailFn) beobachtet")
			}
			select {
			case extra := <-versand:
				t.Errorf("AC-3: genau EINE Mail erwartet, zusätzlich an %q", extra.to)
			case <-time.After(300 * time.Millisecond):
			}
			if _, err := os.Stat(filepath.Join(s.UserDir(uid), "email_verification.json")); err == nil {
				t.Errorf("AC-3: die Verknüpfung darf kein Verifikations-Token anlegen (email_verification.json existiert)")
			}
		})
	}
}

// --- AC-4 --------------------------------------------------------------------

// AC-4: Verknüpfungsfall, der Versand der Hinweis-Mail scheitert (der
// SMTP-Fehler nennt — wie echte Server — den Empfänger) -> Login gelingt
// trotzdem, das Log enthält keine E-Mail-Adresse.
func TestGoogleLink_AC4_VersandfehlerDerHinweisMailBrichtLoginNichtAb(t *testing.T) {
	s := newTestStore(t)
	const uid = "wanderer-ac4-2147c"
	const adresse = "foo-ac4-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse,
		PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()})

	versand := googleLinkBeobachteVersand(t, func(to string) error {
		return fmt.Errorf("smtp: 550 5.1.1 <%s>: mailbox unavailable", to)
	})
	mitschnitt := googleLinkMitschnitt(t)

	const sub = "sub-ac4-2147c"
	w := googleLinkEinmal(t, s, sub, "Foo-AC4-2147c@beispiel.de", true)

	// Erst den Versandversuch abwarten — sonst wäre „keine Adresse im Log"
	// trivial wahr, weil der Fehler-Log (Goroutine) noch gar nicht geschrieben ist.
	select {
	case v := <-versand:
		if v.to != adresse {
			t.Errorf("AC-4: Versandversuch ging an %q statt an %q", v.to, adresse)
		}
	case <-time.After(3 * time.Second):
		t.Errorf("AC-4: kein Versandversuch der Hinweis-Mail beobachtet — der Fehlerfall wurde nicht hergestellt")
	}
	time.Sleep(300 * time.Millisecond)
	log.SetOutput(os.Stderr)

	if loc := w.Header().Get("Location"); w.Code != http.StatusFound || loc != "/" {
		t.Errorf("AC-4: der Login muss trotz Versandfehler gelingen — erwartet 302 auf \"/\", bekommen %d auf %q", w.Code, loc)
	}
	if !googleLinkSitzungGehoert(w, uid) {
		t.Errorf("AC-4: Session-Cookie für %q erwartet, bekommen %v", uid, sessionCookieOderNil(w))
	}
	if u := ladeKonto(t, s, uid); u.OAuthSub != sub {
		t.Errorf("AC-4: die Verknüpfung muss trotz Versandfehler bestehen bleiben — oauth_sub=%q", u.OAuthSub)
	}
	protokoll := strings.ToLower(mitschnitt.String())
	if strings.Contains(protokoll, "foo-ac4-2147c") || strings.Contains(protokoll, "@beispiel.de") {
		t.Errorf("AC-4: das Log nennt die E-Mail-Adresse: %q", mitschnitt.String())
	}
}

// --- AC-5 --------------------------------------------------------------------

// AC-5: bestätigter Inhaber trägt bereits einen ANDEREN OAuthSub -> neutrale
// Ablehnung, bestehender Sub unverändert, nichts geschrieben.
func TestGoogleLink_AC5_InhaberMitAnderemSubWirdNieUeberschrieben(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	googleLinkBeobachteVersand(t, nil)

	const uid = "inhaber-ac5-2147c"
	const adresse = "foo-ac5-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse,
		OAuthProvider: "google", OAuthSub: "sub-alt-ac5-2147c", EmailVerifiedAt: jetztBestaetigt()})
	alteSitzung(t, s, uid)
	vorher := rohesKonto(t, s, uid)
	vorherSitzungen := roheGaesteliste(t, s, uid)

	w := googleLinkEinmal(t, s, "sub-neu-ac5-2147c", adresse, true)

	googleLinkPruefeAbgelehnt(t, "AC-5", w, googleLinkZielAbgelehnt)
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-5: kein Neukonto erlaubt — %d Konten statt 1", n)
	}
	if !bytes.Equal(vorher, rohesKonto(t, s, uid)) {
		t.Errorf("AC-5: user.json des Inhabers wurde verändert (bestehender Sub überschrieben?)")
	}
	if !bytes.Equal(vorherSitzungen, roheGaesteliste(t, s, uid)) {
		t.Errorf("AC-5: Gästeliste des Inhabers wurde verändert")
	}
	if n := googleLinkSubAnzahl(t, s, "sub-neu-ac5-2147c"); n != 0 {
		t.Errorf("AC-5: der neue Sub darf nirgends gespeichert sein, gefunden in %d Konto/Konten", n)
	}
}

// --- AC-6 --------------------------------------------------------------------

// AC-6: unbestätigtes, zugangsloses Konto mit der Google-Adresse als wirksamer
// Adresse, email_verified=true -> Übernahme: EmailVerifiedAt gesetzt, OAuthSub
// gesetzt, alte Sitzungen erloschen, Nutzdaten und übrige Felder erhalten.
func TestGoogleLink_AC6_UnbestaetigtesZugangslosesKontoWirdUebernommen(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	versand := googleLinkBeobachteVersand(t, nil)

	const uid = "offen-ac6-2147c"
	const adresse = "offen-ac6-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse,
		DisplayName: "Offenes Konto", SmsTo: "+4915100002147"})
	alt := alteSitzung(t, s, uid)
	seedTrip(t, s.WithUser(uid), "trip-ac6-2147c", "Probe-Tour")
	vorherDaten := dateienAusserKontoUndSitzungen(t, s, uid)
	if len(vorherDaten) == 0 {
		t.Fatalf("AC-6: Fixture ohne Nutzdaten — der Erhalt-Nachweis wäre leer")
	}
	vorher := ladeKonto(t, s, uid)

	const sub = "sub-ac6-2147c"
	w := googleLinkEinmal(t, s, sub, "Offen-AC6-2147c@beispiel.de", true)

	if loc := w.Header().Get("Location"); w.Code != http.StatusFound || loc != "/" {
		t.Errorf("AC-6: Übernahme muss anmelden — erwartet 302 auf \"/\", bekommen %d auf %q", w.Code, loc)
	}
	if !googleLinkSitzungGehoert(w, uid) {
		t.Errorf("AC-6: Session-Cookie muss dem übernommenen Konto %q gehören, ist %v", uid, sessionCookieOderNil(w))
	}
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-6: kein Neukonto erlaubt — %d Konten statt 1", n)
	}
	nachher := ladeKonto(t, s, uid)
	if nachher.EmailVerifiedAt == nil {
		t.Errorf("AC-6: das übernommene Konto muss bestätigt sein")
	}
	if nachher.OAuthProvider != "google" || nachher.OAuthSub != sub {
		t.Errorf("AC-6: erwartet oauth_provider=google oauth_sub=%q, ist %q/%q", sub, nachher.OAuthProvider, nachher.OAuthSub)
	}
	googleLinkFelderAusser(t, "AC-6", vorher, nachher, "email_verified_at", "oauth_provider", "oauth_sub")

	liste := sitzungen(t, s, uid)
	for _, sess := range liste {
		if sess.ID == alt {
			t.Errorf("AC-6: die alte Sitzung muss nach der Übernahme ungültig sein (ClearSessions fehlt)")
		}
	}
	if len(liste) != 1 {
		t.Errorf("AC-6: genau eine Sitzung (die des Übernehmenden) erwartet, vorhanden: %d", len(liste))
	}
	nachherDaten := dateienAusserKontoUndSitzungen(t, s, uid)
	if len(nachherDaten) != len(vorherDaten) {
		t.Errorf("AC-6: Nutzdaten-Dateien vorher %d, nachher %d", len(vorherDaten), len(nachherDaten))
	}
	for rel, inhalt := range vorherDaten {
		if !bytes.Equal(inhalt, nachherDaten[rel]) {
			t.Errorf("AC-6: Nutzdatei %q wurde verändert oder gelöscht", rel)
		}
	}
	// Bei der Übernahme geht KEINE Mail hinaus (weder Hinweis- noch
	// Verifikationsmail) — Versand läuft in einer Goroutine, daher Wartefenster.
	select {
	case v := <-versand:
		t.Errorf("AC-6: bei der Übernahme darf keine Mail verschickt werden, bekommen an %q", v.to)
	case <-time.After(500 * time.Millisecond):
	}
}

// AC-6 (Fix-Loop 1, Adversary F001): zwischen Zuordnung („unbestätigt +
// zugangslos") und Übernahme ändert sich das Konto — über den echten Store,
// eingespielt an der Naht googleLinkBeforeTakeoverReload. Realer Auslöser:
// ResetPasswordHandler setzt PasswordHash, ohne die Adress-Sperre zu halten.
// Die Übernahme muss frisch laden und nachprüfen -> neutrale Ablehnung,
// nichts übernommen, die Zwischenzeit-Änderung bleibt erhalten.
func TestGoogleLink_AC6_UebernahmeRecheckVerweigertGeaendertesKonto(t *testing.T) {
	const adresse = "recheck-ac6-2147c@beispiel.de"
	const andereAdresse = "anders-ac6-2147c@beispiel.de"
	faelle := []struct {
		name     string
		aendern  func(t *testing.T, u *model.User)
		erhalten func(t *testing.T, u *model.User)
	}{
		{"neues-passwort", func(t *testing.T, u *model.User) {
			u.PasswordHash = googleLinkPasswortHash(t)
		}, func(t *testing.T, u *model.User) {
			if u.PasswordHash == "" {
				t.Errorf("AC-6/recheck: das zwischenzeitlich gesetzte Passwort ist verschwunden")
			}
		}},
		{"adresswechsel", func(t *testing.T, u *model.User) {
			u.Email, u.MailTo = andereAdresse, andereAdresse
		}, func(t *testing.T, u *model.User) {
			if u.Email != andereAdresse || u.MailTo != andereAdresse {
				t.Errorf("AC-6/recheck: die zwischenzeitliche Adressänderung wurde rückgängig gemacht — email=%q mail_to=%q",
					u.Email, u.MailTo)
			}
		}},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			versand := googleLinkBeobachteVersand(t, nil)

			const uid = "recheck-ac6-2147c"
			speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse})
			alt := alteSitzung(t, s, uid)

			aufgerufen := false
			orig := googleLinkBeforeTakeoverReload
			googleLinkBeforeTakeoverReload = func(userID string) {
				if userID != uid {
					return
				}
				aufgerufen = true
				u, err := s.LoadUser(userID)
				if err != nil || u == nil {
					t.Fatalf("AC-6/recheck: Zwischenzeit-Laden fehlgeschlagen: %v", err)
				}
				f.aendern(t, u)
				if err := s.SaveUser(*u); err != nil {
					t.Fatalf("AC-6/recheck: Zwischenzeit-Speichern fehlgeschlagen: %v", err)
				}
			}
			t.Cleanup(func() { googleLinkBeforeTakeoverReload = orig })

			w := googleLinkEinmal(t, s, "sub-recheck-ac6-2147c", adresse, true)

			if !aufgerufen {
				t.Fatalf("AC-6/recheck: Selbstprüfung — die Naht wurde nicht erreicht, der Übernahmezweig lief nicht")
			}
			googleLinkPruefeAbgelehnt(t, "AC-6/recheck/"+f.name, w, googleLinkZielAbgelehnt)
			if n := kontenAnzahl(t, s); n != 1 {
				t.Errorf("AC-6/recheck/%s: kein Neukonto erlaubt — %d Konten statt 1", f.name, n)
			}
			nachher := ladeKonto(t, s, uid)
			if nachher.OAuthSub != "" || nachher.OAuthProvider != "" {
				t.Errorf("AC-6/recheck/%s: das Konto darf nicht verknüpft werden — oauth=%q/%q",
					f.name, nachher.OAuthProvider, nachher.OAuthSub)
			}
			if nachher.EmailVerifiedAt != nil {
				t.Errorf("AC-6/recheck/%s: email_verified_at darf nicht gesetzt sein", f.name)
			}
			f.erhalten(t, nachher)
			gefunden := false
			for _, sess := range sitzungen(t, s, uid) {
				if sess.ID == alt {
					gefunden = true
				}
			}
			if !gefunden {
				t.Errorf("AC-6/recheck/%s: die bestehende Sitzung wurde trotz Ablehnung beendet", f.name)
			}
			select {
			case v := <-versand:
				t.Errorf("AC-6/recheck/%s: bei Ablehnung darf keine Mail verschickt werden, bekommen an %q", f.name, v.to)
			case <-time.After(200 * time.Millisecond):
			}
		})
	}
}

// --- AC-7 --------------------------------------------------------------------

// AC-7: unbestätigtes Konto MIT Zugangsdaten (Passwort, Passkey, fremder
// Google-Sub) -> neutrale Ablehnung, kein Feld geschrieben, kein Neukonto.
func TestGoogleLink_AC7_UnbestaetigtesKontoMitZugangsdatenWirdNieUebernommen(t *testing.T) {
	const adresse = "zugang-ac7-2147c@beispiel.de"
	stempel := time.Date(2026, 9, 1, 8, 0, 0, 0, time.UTC)
	faelle := []struct {
		name   string
		zugang func(t *testing.T, u *model.User)
	}{
		{"passwort", func(t *testing.T, u *model.User) { u.PasswordHash = googleLinkPasswortHash(t) }},
		{"passkey", func(t *testing.T, u *model.User) {
			u.PasskeyCredentials = []model.WebAuthnCredential{{
				ID: []byte{4, 5, 6}, PublicKey: []byte{7, 8, 9},
				AttestationType: "none", Transport: []string{"internal"},
				CreatedAt: stempel, Label: "Telefon",
			}}
		}},
		{"fremder-google-sub", func(t *testing.T, u *model.User) {
			u.OAuthProvider, u.OAuthSub = "google", "sub-fremd-ac7-2147c"
		}},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			googleLinkBeobachteVersand(t, nil)

			const uid = "zugang-ac7-2147c"
			konto := model.User{ID: uid, Email: adresse, MailTo: adresse}
			f.zugang(t, &konto)
			speichereKonto(t, s, konto)
			alteSitzung(t, s, uid)
			vorher := rohesKonto(t, s, uid)
			vorherSitzungen := roheGaesteliste(t, s, uid)

			w := googleLinkEinmal(t, s, "sub-neu-ac7-2147c", adresse, true)

			googleLinkPruefeAbgelehnt(t, "AC-7/"+f.name, w, googleLinkZielAbgelehnt)
			if n := kontenAnzahl(t, s); n != 1 {
				t.Errorf("AC-7/%s: kein Neukonto erlaubt — %d Konten statt 1", f.name, n)
			}
			if !bytes.Equal(vorher, rohesKonto(t, s, uid)) {
				t.Errorf("AC-7/%s: user.json wurde verändert", f.name)
			}
			if !bytes.Equal(vorherSitzungen, roheGaesteliste(t, s, uid)) {
				t.Errorf("AC-7/%s: Gästeliste wurde verändert", f.name)
			}
		})
	}
}

// --- AC-8 --------------------------------------------------------------------

// AC-8: Google-Adresse steht nur im Nebenfeld (email) eines bestätigten Kontos,
// dessen wirksame Adresse eine andere ist -> neutrale Ablehnung, kein Neukonto.
func TestGoogleLink_AC8_AdresseNurImNebenfeldWirdAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	googleLinkBeobachteVersand(t, nil)

	const uid = "nebenfeld-ac8-2147c"
	const nebenfeld = "neben-ac8-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: nebenfeld, MailTo: "kontakt-ac8-2147c@beispiel.de",
		PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()})
	vorher := rohesKonto(t, s, uid)

	const sub = "sub-ac8-2147c"
	w := googleLinkEinmal(t, s, sub, nebenfeld, true)

	googleLinkPruefeAbgelehnt(t, "AC-8", w, googleLinkZielAbgelehnt)
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-8: kein Neukonto erlaubt — %d Konten statt 1", n)
	}
	if !bytes.Equal(vorher, rohesKonto(t, s, uid)) {
		t.Errorf("AC-8: user.json des Nebenfeld-Kontos wurde verändert")
	}
	if n := googleLinkSubAnzahl(t, s, sub); n != 0 {
		t.Errorf("AC-8: der Sub darf nirgends gespeichert sein, gefunden: %d", n)
	}
}

// --- AC-9 --------------------------------------------------------------------

// AC-9 (Wächter, Spec-Korrektur nach RED-Befund): Google liefert
// email_verified=false -> die bestehende Sperre (auth_oauth.go:150) lehnt VOR
// jeder Adressprüfung ab, in ALLEN vier Adresslagen (frei, Owned bestätigt,
// Owned unbestätigt, Ambiguous) mit exakt derselben Antwort `oauth_failed`;
// nichts wird geschrieben oder verknüpft. Die identische Antwort ist die
// eigentliche Zusicherung: der Code darf nicht verraten, ob die Adresse
// existiert (Enumeration).
func TestGoogleLink_AC9_UnbestaetigteGoogleAdresseWirdVorJederAdresspruefungAbgelehnt(t *testing.T) {
	const adresse = "belegt-ac9-2147c@beispiel.de"
	faelle := []struct {
		name  string
		konto func(t *testing.T) *model.User // nil = Adresse frei
	}{
		{"frei", func(t *testing.T) *model.User { return nil }},
		{"owned-bestaetigt-ohne-sub", func(t *testing.T) *model.User {
			return &model.User{ID: "inhaber-ac9-2147c", Email: adresse, MailTo: adresse,
				PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()}
		}},
		{"owned-unbestaetigt-zugangslos", func(t *testing.T) *model.User {
			return &model.User{ID: "offen-ac9-2147c", Email: adresse, MailTo: adresse}
		}},
		{"ambiguous-nebenfeld", func(t *testing.T) *model.User {
			return &model.User{ID: "neben-ac9-2147c", Email: adresse, MailTo: "kontakt-ac9-2147c@beispiel.de",
				EmailVerifiedAt: jetztBestaetigt()}
		}},
	}
	type antwort struct {
		code     int
		location string
		body     string
	}
	antworten := map[string]antwort{}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			versand := googleLinkBeobachteVersand(t, nil)

			konto := f.konto(t)
			var vorher []byte
			vorherAnzahl := 0
			if konto != nil {
				speichereKonto(t, s, *konto)
				vorher = rohesKonto(t, s, konto.ID)
				vorherAnzahl = 1
			}

			const sub = "sub-ac9-2147c"
			w := googleLinkEinmal(t, s, sub, adresse, false)
			antworten[f.name] = antwort{w.Code, w.Header().Get("Location"), w.Body.String()}

			googleLinkPruefeAbgelehnt(t, "AC-9/"+f.name, w, googleLinkZielFehler)
			if n := kontenAnzahl(t, s); n != vorherAnzahl {
				t.Errorf("AC-9/%s: nichts darf geschrieben werden — Konten vorher %d, nachher %d", f.name, vorherAnzahl, n)
			}
			if konto != nil && !bytes.Equal(vorher, rohesKonto(t, s, konto.ID)) {
				t.Errorf("AC-9/%s: user.json wurde verändert (verknüpft/übernommen?)", f.name)
			}
			if n := googleLinkSubAnzahl(t, s, sub); n != 0 {
				t.Errorf("AC-9/%s: der Sub darf nirgends gespeichert sein, gefunden: %d", f.name, n)
			}
			select {
			case v := <-versand:
				t.Errorf("AC-9/%s: bei email_verified=false darf keine Mail verschickt werden, bekommen an %q", f.name, v.to)
			case <-time.After(200 * time.Millisecond):
			}
		})
	}
	basis, ok := antworten["frei"]
	if !ok {
		t.Fatalf("AC-9: Referenzfall \"frei\" lief nicht")
	}
	for name, a := range antworten {
		if a != basis {
			t.Errorf("AC-9: Antwort für %q unterscheidet sich von der freien Adresse — Enumeration: %+v vs. %+v",
				name, a, basis)
		}
	}
}

// --- AC-10 -------------------------------------------------------------------

// AC-10: eine fremde Kontodatei ist unlesbar (beschädigtes JSON im echten
// Store) -> fail-closed oauth_failed, nichts geschrieben — egal ob die Adresse
// sonst frei oder belegt wäre.
func TestGoogleLink_AC10_UnlesbareKontodateiIstFailClosed(t *testing.T) {
	const adresse = "geprueft-ac10-2147c@beispiel.de"
	for _, belegt := range []bool{false, true} {
		name := "adresse-frei"
		if belegt {
			name = "adresse-belegt"
		}
		t.Run(name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			googleLinkBeobachteVersand(t, nil)

			dir := s.UserDir("defekt-ac10-2147c")
			if err := os.MkdirAll(dir, 0755); err != nil {
				t.Fatalf("MkdirAll: %v", err)
			}
			if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte("{das ist kein json"), 0644); err != nil {
				t.Fatalf("beschädigte user.json schreiben: %v", err)
			}
			const inhaber = "inhaber-ac10-2147c"
			var vorherInhaber []byte
			if belegt {
				speichereKonto(t, s, model.User{ID: inhaber, Email: adresse, MailTo: adresse,
					PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()})
				vorherInhaber = rohesKonto(t, s, inhaber)
			}
			vorherAnzahl := kontenAnzahl(t, s)

			const sub = "sub-ac10-2147c"
			w := googleLinkEinmal(t, s, sub, adresse, true)

			googleLinkPruefeAbgelehnt(t, "AC-10/"+name, w, googleLinkZielFehler)
			if n := kontenAnzahl(t, s); n != vorherAnzahl {
				t.Errorf("AC-10/%s: nichts darf geschrieben werden — Konten vorher %d, nachher %d", name, vorherAnzahl, n)
			}
			if n := googleLinkSubAnzahl(t, s, sub); n != 0 {
				t.Errorf("AC-10/%s: der Sub darf nirgends gespeichert sein, gefunden: %d", name, n)
			}
			if belegt && !bytes.Equal(vorherInhaber, rohesKonto(t, s, inhaber)) {
				t.Errorf("AC-10/%s: der Inhaber wurde trotz Lesefehler verändert (verknüpft?)", name)
			}
		})
	}
}

// --- AC-11 -------------------------------------------------------------------

// AC-11: die drei inhaltlichen Ablehnungsgründe (AC-5/7/8) enden in EXAKT derselben
// Antwort (Status, Location, Körper), und das Log nennt weder die Adresse noch
// eine user_id.
func TestGoogleLink_AC11_AlleAblehnungenSindUnunterscheidbarUndLogOhneIDs(t *testing.T) {
	const adresse = "neutral-ac11-2147c@beispiel.de"
	faelle := []struct {
		name     string
		konten   func(t *testing.T) []model.User
		verified bool
	}{
		{"AC-5-anderer-sub", func(t *testing.T) []model.User {
			return []model.User{{ID: "inhabera-ac11-2147c", Email: adresse, MailTo: adresse,
				OAuthProvider: "google", OAuthSub: "sub-alt-ac11-2147c", EmailVerifiedAt: jetztBestaetigt()}}
		}, true},
		{"AC-7-unbestaetigt-mit-passwort", func(t *testing.T) []model.User {
			return []model.User{{ID: "zugangb-ac11-2147c", Email: adresse, MailTo: adresse,
				PasswordHash: googleLinkPasswortHash(t)}}
		}, true},
		{"AC-8-nebenfeld", func(t *testing.T) []model.User {
			return []model.User{{ID: "nebenc-ac11-2147c", Email: adresse, MailTo: "kontakt-ac11-2147c@beispiel.de",
				EmailVerifiedAt: jetztBestaetigt()}}
		}, true},
		// AC-9 gehört seit der Spec-Korrektur nicht mehr in diese Gruppe
		// (email_verified=false -> oauth_failed vor jeder Adressprüfung, eigener Test).
	}

	type antwort struct {
		code     int
		location string
		body     string
	}
	var antworten []antwort
	for _, f := range faelle {
		s := newTestStore(t)
		googleLinkBeobachteVersand(t, nil)
		konten := f.konten(t)
		for _, k := range konten {
			speichereKonto(t, s, k)
		}

		mitschnitt := googleLinkMitschnitt(t)
		w := googleLinkEinmal(t, s, "sub-neu-ac11-2147c", adresse, f.verified)
		time.Sleep(100 * time.Millisecond) // etwaige Goroutinen-Logs einsammeln
		log.SetOutput(os.Stderr)

		antworten = append(antworten, antwort{w.Code, w.Header().Get("Location"), w.Body.String()})
		if loc := w.Header().Get("Location"); loc != googleLinkZielAbgelehnt {
			t.Errorf("AC-11/%s: erwartet Location %q, bekommen %q", f.name, googleLinkZielAbgelehnt, loc)
		}
		protokoll := strings.ToLower(mitschnitt.String())
		if strings.Contains(protokoll, "neutral-ac11-2147c") || strings.Contains(protokoll, "@beispiel.de") {
			t.Errorf("AC-11/%s: das Log nennt eine E-Mail-Adresse: %q", f.name, mitschnitt.String())
		}
		for _, k := range konten {
			if strings.Contains(protokoll, strings.ToLower(k.ID)) {
				t.Errorf("AC-11/%s: das Log nennt die user_id %q: %q", f.name, k.ID, mitschnitt.String())
			}
		}
	}
	for i := 1; i < len(antworten); i++ {
		if antworten[i] != antworten[0] {
			t.Errorf("AC-11: Ablehnung %q unterscheidet sich von %q — %+v vs. %+v",
				faelle[i].name, faelle[0].name, antworten[i], antworten[0])
		}
	}
}

// --- AC-12 -------------------------------------------------------------------

// AC-12 (Wächter): ein bereits bekannter Sub meldet sich mit einer Adresse, die
// inzwischen einem anderen Konto gehört -> Bestandszweig unverändert (Login per
// Sub, Selbstheilung), keine Verknüpfungslogik, das andere Konto bleibt unberührt.
func TestGoogleLink_AC12_BekannterSubLaeuftUnveraendertImBestandszweig(t *testing.T) {
	const adresse = "fremdbelegt-ac12-2147c@beispiel.de"
	faelle := []struct {
		name            string
		bekannt         func() model.User
		heilungErwartet bool
	}{
		{"bestaetigt-andere-adresse", func() model.User {
			return model.User{ID: "g-bekannt-ac12-2147c", Email: "alt-ac12-2147c@beispiel.de",
				MailTo: "alt-ac12-2147c@beispiel.de", OAuthProvider: "google", OAuthSub: "sub-bekannt-ac12-2147c",
				EmailVerifiedAt: jetztBestaetigt()}
		}, false},
		{"unbestaetigt-selbstheilung", func() model.User {
			return model.User{ID: "g-bekannt-ac12-2147c", Email: adresse, MailTo: adresse,
				OAuthProvider: "google", OAuthSub: "sub-bekannt-ac12-2147c"}
		}, true},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })
			versand := googleLinkBeobachteVersand(t, nil)

			const anderer = "inhaber-ac12-2147c"
			speichereKonto(t, s, model.User{ID: anderer, Email: adresse, MailTo: adresse,
				PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()})
			bekannt := f.bekannt()
			speichereKonto(t, s, bekannt)
			vorherAnderer := rohesKonto(t, s, anderer)
			vorherBekannt := ladeKonto(t, s, bekannt.ID)

			w := googleLinkEinmal(t, s, bekannt.OAuthSub, adresse, true)

			if loc := w.Header().Get("Location"); w.Code != http.StatusFound || loc != "/" {
				t.Errorf("AC-12/%s: Bestandszweig muss anmelden — erwartet 302 auf \"/\", bekommen %d auf %q", f.name, w.Code, loc)
			}
			if !googleLinkSitzungGehoert(w, bekannt.ID) {
				t.Errorf("AC-12/%s: Session-Cookie muss dem Konto des bekannten Subs gehören, ist %v", f.name, sessionCookieOderNil(w))
			}
			if !bytes.Equal(vorherAnderer, rohesKonto(t, s, anderer)) {
				t.Errorf("AC-12/%s: das andere Konto wurde verändert", f.name)
			}
			if n := kontenAnzahl(t, s); n != 2 {
				t.Errorf("AC-12/%s: kein Neukonto erlaubt — %d Konten statt 2", f.name, n)
			}
			nachher := ladeKonto(t, s, bekannt.ID)
			if f.heilungErwartet {
				if nachher.EmailVerifiedAt == nil {
					t.Errorf("AC-12/%s: selfHealEmailVerification muss im Bestandszweig weiterhin greifen", f.name)
				}
				googleLinkFelderAusser(t, "AC-12/"+f.name, vorherBekannt, nachher, "email_verified_at")
			} else {
				googleLinkFelderAusser(t, "AC-12/"+f.name, vorherBekannt, nachher)
			}
			select {
			case v := <-versand:
				t.Errorf("AC-12/%s: im Bestandszweig darf keine Mail verschickt werden, bekommen an %q", f.name, v.to)
			case <-time.After(300 * time.Millisecond):
			}
		})
	}
}

// --- AC-13 -------------------------------------------------------------------

// googleLinkSchranke hält jede Userinfo-Antwort an, bis BEIDE parallelen
// Callbacks ihre Userinfo abgeholt haben (Notausgang 300 ms). Danach laufen
// beide Callbacks im selben Zeitfenster in die Konto-Entscheidung — die
// HTTP-Laufzeitschwankung verwischt das Rennen sonst.
type googleLinkSchranke struct {
	mu sync.Mutex
	n  int
	ch chan struct{}
}

func (b *googleLinkSchranke) neu() {
	b.mu.Lock()
	b.n, b.ch = 0, make(chan struct{})
	b.mu.Unlock()
}

func (b *googleLinkSchranke) ankunft() {
	b.mu.Lock()
	b.n++
	ch := b.ch
	if b.n == 2 {
		close(ch)
	}
	b.mu.Unlock()
	select {
	case <-ch:
	case <-time.After(300 * time.Millisecond):
	}
}

func (b *googleLinkSchranke) anzahl() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.n
}

// googleLinkParallel führt zwei vorab gebaute Callback-Anfragen hinter einer
// Startschranke gleichzeitig aus.
func googleLinkParallel(h http.HandlerFunc, reqA, reqB *http.Request) (wA, wB *httptest.ResponseRecorder) {
	wA, wB = httptest.NewRecorder(), httptest.NewRecorder()
	start := make(chan struct{})
	var wg sync.WaitGroup
	wg.Add(2)
	go func() { defer wg.Done(); <-start; h.ServeHTTP(wA, reqA) }()
	go func() { defer wg.Done(); <-start; h.ServeHTTP(wB, reqB) }()
	close(start)
	wg.Wait()
	return wA, wB
}

// googleLinkPruefeDoppelklick: AC-13, gleicher Sub (Doppelklick) — BEIDE
// Callbacks enden gleich, keiner mit oauth_link_failed. Das fängt die Mutation
// „erneuten FindUserByOAuthSub unter dem Lock entfernt": der zweite Callback
// sähe dann das soeben angelegte/verknüpfte Konto nicht als eigenes, sondern
// liefe in die Adressklassifikation (frische Neuanlage = unbestätigt mit
// Zugangsdaten -> Ambiguous -> oauth_link_failed).
//
// inhaber != "" (bestätigtes Konto wird verknüpft): beide landen per Login auf
// "/" mit Session-Cookie für den Inhaber.
// inhaber == "" (freie Adresse): das neu angelegte Konto ist nach ADR 0066
// unbestätigt, das Login-Gate lässt KEINEN der beiden Callbacks herein —
// „Login" heißt hier: beide identisch auf dem Gate-Ergebnis
// (/login?error=email_not_verified), beide für DASSELBE Konto, keiner mit
// oauth_link_failed. Ein Session-Cookie ist dort strukturell unmöglich.
func googleLinkPruefeDoppelklick(t *testing.T, runde, runden int, inhaber string, wA, wB *httptest.ResponseRecorder) {
	t.Helper()
	locA, locB := wA.Header().Get("Location"), wB.Header().Get("Location")
	if locA == googleLinkZielAbgelehnt || locB == googleLinkZielAbgelehnt {
		t.Fatalf("AC-13 Doppelklick (Runde %d/%d): gleicher Sub darf nie oauth_link_failed liefern — A=%q B=%q "+
			"(fehlt der erneute FindUserByOAuthSub unter dem Lock?)", runde, runden, locA, locB)
	}
	if locA != locB {
		t.Fatalf("AC-13 Doppelklick (Runde %d/%d): beide Callbacks müssen gleich enden — A=%q B=%q", runde, runden, locA, locB)
	}
	if inhaber != "" {
		if locA != "/" || !googleLinkSitzungGehoert(wA, inhaber) || !googleLinkSitzungGehoert(wB, inhaber) {
			t.Fatalf("AC-13 Doppelklick (Runde %d/%d): beide Callbacks müssen per Login auf \"/\" mit Session für %q enden — "+
				"A=%q %v / B=%q %v", runde, runden, inhaber, locA, sessionCookieOderNil(wA), locB, sessionCookieOderNil(wB))
		}
	}
}

// AC-13: zwei parallele Callbacks mit gleicher Adresse -> am Ende trägt genau
// ein Konto die Adresse bzw. existiert der Sub genau einmal.
func TestGoogleLink_AC13_ParalleleCallbacksErgebenGenauEinenInhaber(t *testing.T) {
	// Rundenzahl: am Altcode scheitert jeder Untertest dank Userinfo-Schranke in
	// Runde 1–2 (15/15 Wiederholungen gemessen). Ein Callback kostet in dieser
	// Umgebung ~60 ms (Store-Schreibzugriffe) — 100 Runden je Untertest halten
	// die Laufzeit nach GREEN bei ~30 s statt ~90 s.
	const runden = 100
	const adresse = "parallel-ac13-2147c@beispiel.de"

	faelle := []struct {
		name string
		// subB leer = beide Anfragen mit demselben Sub
		subA, subB string
		// inhaber != "" = Adresse gehört bereits einem bestätigten Konto ohne Sub
		inhaber string
	}{
		{name: "gleicher-sub-freie-adresse", subA: "sub-gleich-ac13-2147c"},
		{name: "verschiedene-subs-freie-adresse", subA: "sub-a-ac13-2147c", subB: "sub-b-ac13-2147c"},
		{name: "gleicher-sub-verknuepfung", subA: "sub-link-ac13-2147c", inhaber: "inhaber-ac13-2147c"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			log.SetOutput(io.Discard)
			t.Cleanup(func() { log.SetOutput(os.Stderr) })

			subB := f.subB
			if subB == "" {
				subB = f.subA
			}
			g := googleLinkFakeGoogle(t)
			g.identitaet("code-a", f.subA, adresse, true)
			g.identitaet("code-b", subB, adresse, true)
			schranke := &googleLinkSchranke{}
			g.setzeVorAntwort(schranke.ankunft)

			for i := 0; i < runden; i++ {
				s := newTestStore(t)
				if f.inhaber != "" {
					speichereKonto(t, s, model.User{ID: f.inhaber, Email: adresse, MailTo: adresse,
						PasswordHash: "$2a$10$diesIstEinBcryptHashAC13x", EmailVerifiedAt: jetztBestaetigt()})
				}
				h := g.handlerOhneVersand(s)
				reqA, reqB := googleLinkAnfrage("code-a"), googleLinkAnfrage("code-b")
				schranke.neu()

				wA, wB := googleLinkParallel(h, reqA, reqB)

				if n := schranke.anzahl(); n != 2 {
					t.Fatalf("AC-13 (Runde %d/%d): Selbstprüfung — die Schranke sah %d statt 2 Userinfo-Abrufe, "+
						"das Rennen wurde nicht hergestellt", i+1, runden, n)
				}
				halter := schreibpfadAdresseHalterAnzahl(t, s, adresse)
				subsA := googleLinkSubAnzahl(t, s, f.subA)
				subsB := googleLinkSubAnzahl(t, s, subB)
				konten := kontenAnzahl(t, s)
				kaputt := halter != 1 || subsA > 1 || subsB > 1
				if f.subB == "" && subsA != 1 {
					kaputt = true // gleicher Sub: genau einmal vorhanden
				}
				if f.inhaber != "" && konten != 1 {
					kaputt = true // Verknüpfung: kein Neukonto
				}
				if kaputt {
					t.Fatalf("AC-13 (Runde %d/%d): erwartet genau 1 Adress-Inhaber, Sub je höchstens einmal "+
						"(gleicher Sub: genau einmal; Verknüpfung: kein Neukonto) — bekommen Inhaber=%d Sub-A=%d Sub-B=%d Konten=%d "+
						"(A=%d %q / B=%d %q)", i+1, runden, halter, subsA, subsB, konten,
						wA.Code, wA.Header().Get("Location"), wB.Code, wB.Header().Get("Location"))
				}
				if f.subB == "" {
					googleLinkPruefeDoppelklick(t, i+1, runden, f.inhaber, wA, wB)
				}
			}
		})
	}
}

// --- AC-14 -------------------------------------------------------------------

// AC-14: Google-Callback parallel zu einer Registrierung mit derselben Adresse
// -> am Ende trägt genau ein Konto die Adresse.
//
// Die beiden Wege dauern sehr unterschiedlich lang (bcrypt vs. zwei
// HTTP-Rundläufe), und das Verhältnis kippt je Umgebung (z. B. unter -race).
// Eine feste Startschranke allein träfe deshalb immer dieselbe Reihenfolge.
// Stattdessen wird die Laufzeit beider Wege vorab gemessen und je Runde EINE
// Seite um eine zufällige Spanne aus [0, 2 × längere Laufzeit] verzögert —
// so kommen beide Reihenfolgen UND echte Überlappung im kritischen Fenster vor.
func TestGoogleLink_AC14_CallbackGegenRegistrierungErgibtGenauEinenInhaber(t *testing.T) {
	// 100 Runden: am Altcode Abbruch in Runde 1 (15/15 Wiederholungen, auch
	// unter -race); je Runde ~60 ms Laufzeit + Zufallsverzögerung.
	const runden = 100
	const adresse = "wettlauf-ac14-2147c@beispiel.de"
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })

	g := googleLinkFakeGoogle(t)
	g.identitaet("code-g", "sub-ac14-2147c", adresse, true)
	cfg := config.Config{}
	registrierung := func(s *store.Store, i int) (*httptest.ResponseRecorder, func()) {
		body := fmt.Sprintf(`{"username":%q,"password":%q,"email":%q}`,
			fmt.Sprintf("neuling%d-ac14-2147c", i), schreibpfadPasswort, adresse)
		req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h := RegisterHandler(s, bcrypt.MinCost, cfg)
		return w, func() { h.ServeHTTP(w, req) }
	}
	google := func(s *store.Store) (*httptest.ResponseRecorder, func()) {
		req := googleLinkAnfrage("code-g")
		w := httptest.NewRecorder()
		h := g.handlerOhneVersand(s)
		return w, func() { h.ServeHTTP(w, req) }
	}

	// Laufzeiten messen (je auf eigenem Wegwerf-Store, Median aus 5).
	messe := func(lauf func(i int) func()) time.Duration {
		var dauern []time.Duration
		for k := 0; k < 5; k++ {
			f := lauf(k)
			t0 := time.Now()
			f()
			dauern = append(dauern, time.Since(t0))
		}
		for a := 0; a < len(dauern); a++ {
			for b := a + 1; b < len(dauern); b++ {
				if dauern[b] < dauern[a] {
					dauern[a], dauern[b] = dauern[b], dauern[a]
				}
			}
		}
		return dauern[len(dauern)/2]
	}
	dReg := messe(func(i int) func() { _, f := registrierung(newTestStore(t), 9000+i); return f })
	dGoogle := messe(func(i int) func() { _, f := google(newTestStore(t)); return f })
	spanne := dReg
	if dGoogle > spanne {
		spanne = dGoogle
	}
	spanne = 2*spanne + 200*time.Microsecond
	t.Logf("AC-14: gemessene Laufzeit Registrierung=%v Google=%v, Verzögerungsspanne=%v", dReg, dGoogle, spanne)
	rng := rand.New(rand.NewSource(2147))

	for i := 0; i < runden; i++ {
		s := newTestStore(t)
		regW, regLauf := registrierung(s, i)
		gW, gLauf := google(s)
		verzoegerung := time.Duration(rng.Int63n(int64(spanne)))
		regVerzoegert := rng.Intn(2) == 0

		start := make(chan struct{})
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			<-start
			if regVerzoegert {
				time.Sleep(verzoegerung)
			}
			regLauf()
		}()
		go func() {
			defer wg.Done()
			<-start
			if !regVerzoegert {
				time.Sleep(verzoegerung)
			}
			gLauf()
		}()
		close(start)
		wg.Wait()

		halter := schreibpfadAdresseHalterAnzahl(t, s, adresse)
		if halter != 1 {
			t.Fatalf("AC-14 (Runde %d/%d): erwartet genau 1 Adress-Inhaber, bekommen %d "+
				"(Registrierung=%d %q / Google=%d %q)", i+1, runden, halter,
				regW.Code, regW.Body.String(), gW.Code, gW.Header().Get("Location"))
		}
	}
}

// --- AC-15 -------------------------------------------------------------------

// AC-15: zwei Nutzer — Konto A wird per Google verknüpft; Konto B bleibt in
// allen Feldern, Sitzungen und Nutzdaten unverändert, die Session gehört A.
func TestGoogleLink_AC15_VerknuepfungVonAIsoliertKontoB(t *testing.T) {
	s := newTestStore(t)
	log.SetOutput(io.Discard)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	googleLinkBeobachteVersand(t, nil)

	const idA = "konto-a-ac15-2147c"
	const idB = "konto-b-ac15-2147c"
	const adresseA = "anna-ac15-2147c@beispiel.de"
	const adresseB = "bert-ac15-2147c@beispiel.de"
	speichereKonto(t, s, model.User{ID: idA, Email: adresseA, MailTo: adresseA,
		PasswordHash: googleLinkPasswortHash(t), EmailVerifiedAt: jetztBestaetigt()})
	kontoB := reichesKonto2304(idB, adresseB, adresseB)
	kontoB.EmailVerifiedAt = jetztBestaetigt()
	speichereKonto(t, s, kontoB)
	alteSitzung(t, s, idB)
	seedTrip(t, s.WithUser(idB), "trip-b-ac15-2147c", "Bert-Tour")
	vorherB := rohesKonto(t, s, idB)
	vorherSitzungenB := roheGaesteliste(t, s, idB)
	vorherDatenB := dateienAusserKontoUndSitzungen(t, s, idB)

	const sub = "sub-anna-ac15-2147c"
	w := googleLinkEinmal(t, s, sub, adresseA, true)

	if loc := w.Header().Get("Location"); w.Code != http.StatusFound || loc != "/" {
		t.Errorf("AC-15: Verknüpfung von A muss anmelden — erwartet 302 auf \"/\", bekommen %d auf %q", w.Code, loc)
	}
	if !googleLinkSitzungGehoert(w, idA) {
		t.Errorf("AC-15: die ausgestellte Session muss Konto A %q gehören, ist %v", idA, sessionCookieOderNil(w))
	}
	if googleLinkSitzungGehoert(w, idB) {
		t.Errorf("AC-15: die ausgestellte Session gehört Konto B — Cross-User-Anmeldung")
	}
	if u := ladeKonto(t, s, idA); u.OAuthSub != sub {
		t.Errorf("AC-15: Konto A muss den Sub tragen, oauth_sub=%q", u.OAuthSub)
	}
	if n := kontenAnzahl(t, s); n != 2 {
		t.Errorf("AC-15: kein Neukonto erlaubt — %d Konten statt 2", n)
	}
	if !bytes.Equal(vorherB, rohesKonto(t, s, idB)) {
		t.Errorf("AC-15: user.json von Konto B wurde verändert")
	}
	if !bytes.Equal(vorherSitzungenB, roheGaesteliste(t, s, idB)) {
		t.Errorf("AC-15: Gästeliste von Konto B wurde verändert")
	}
	nachherDatenB := dateienAusserKontoUndSitzungen(t, s, idB)
	if len(nachherDatenB) != len(vorherDatenB) {
		t.Errorf("AC-15: Nutzdaten von B vorher %d Dateien, nachher %d", len(vorherDatenB), len(nachherDatenB))
	}
	for rel, inhalt := range vorherDatenB {
		if !bytes.Equal(inhalt, nachherDatenB[rel]) {
			t.Errorf("AC-15: Nutzdatei %q von Konto B wurde verändert oder gelöscht", rel)
		}
	}
}
