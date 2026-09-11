package handler

// TDD RED — Issue #2304 (S1 aus #2271/#2146, Epic #2138): Selbstheilung der
// E-Mail-Bestätigung bei Magic-Link- und Google-OAuth-Anmeldung.
// Spec: docs/specs/modules/email_verify_vorbereitung_2304.md — AC-4, AC-5, AC-6.
//
// Beide Anmeldewege weisen Adressbesitz nach: der Magic-Link durch den Empfang
// des Codes im Postfach, Google durch `email_verified` in der Userinfo. Stimmt
// die nachgewiesene Adresse mit der EFFEKTIVEN Kontaktadresse des Kontos
// überein (mail_to, ersatzweise email — dieselbe Vorrangregel wie
// dispatchVerificationMail, auth.go:761-764), darf `email_verified_at` gesetzt
// werden. Stimmt sie nicht überein, bleibt das Feld unangetastet.
//
// Geprüft wird am WIRKORT: die Tests durchlaufen den echten HTTP-Fluss der
// Anmeldewege und lesen das Konto danach frisch aus dem Dateispeicher — nicht
// eine interne Adressvergleichs-Funktion. Kein Mock: echter Store auf echter
// Platte, Google gegen zwei echte httptest-Server. Kein Netz, kein Versand —
// SMTPHost bleibt leer bzw. der Bestands-Zweig löst keinen Dispatch aus.
//
// Diese Datei liegt bewusst in `package handler`: der Magic-Link-Code entsteht
// im paketprivaten otpStore und ist von außen nur über den Mailversand
// erreichbar.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const selbstheilungSecret = "test-secret-32-chars-minimum-ok!"

// otpCodeFor liest den vom echten MagicLinkRequestHandler erzeugten Code aus
// dem Paket-Speicher. Der Umweg über die Mail entfällt damit, der Fluss selbst
// bleibt unverfälscht: derselbe Code, den der Nutzer aus dem Postfach abtippt.
func otpCodeFor(t *testing.T, email string) string {
	t.Helper()
	val, ok := otpStore.Load(strings.ToLower(strings.TrimSpace(email)))
	if !ok {
		t.Fatalf("kein OTP-Eintrag für %q — der Magic-Link-Anforderungs-Schritt hat nichts hinterlegt", email)
	}
	entry, ok := val.(*otpEntry)
	if !ok || entry.code == "" {
		t.Fatalf("OTP-Eintrag für %q ist leer/unerwartet: %#v", email, val)
	}
	return entry.code
}

// magicLinkAnmeldung durchläuft den echten Zwei-Schritt-Fluss
// (POST /api/auth/magic-link → POST /api/auth/magic-link/verify) und gibt die
// Antwort des Verify-Schritts zurück.
func magicLinkAnmeldung(t *testing.T, s *store.Store, cfg *config.Config, email string) *httptest.ResponseRecorder {
	t.Helper()

	anfrage := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link",
		strings.NewReader(`{"email":"`+email+`"}`))
	anfrage.Header.Set("Content-Type", "application/json")
	wAnfrage := httptest.NewRecorder()
	MagicLinkRequestHandler(s, cfg).ServeHTTP(wAnfrage, anfrage)
	if wAnfrage.Code != http.StatusOK {
		t.Fatalf("Magic-Link-Anforderung: erwartet 200, bekommen %d: %s", wAnfrage.Code, wAnfrage.Body.String())
	}

	code := otpCodeFor(t, email)
	verify := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
		strings.NewReader(`{"email":"`+email+`","code":"`+code+`"}`))
	verify.Header.Set("Content-Type", "application/json")
	wVerify := httptest.NewRecorder()
	MagicLinkVerifyHandler(s, cfg).ServeHTTP(wVerify, verify)
	return wVerify
}

func ladeKonto(t *testing.T, s *store.Store, uid string) *model.User {
	t.Helper()
	user, err := s.LoadUser(uid)
	if err != nil || user == nil {
		t.Fatalf("Konto %q konnte nach der Anmeldung nicht frisch geladen werden: %v", uid, err)
	}
	return user
}

// AC-4: Konto ohne email_verified_at, effektive Kontaktadresse == die per
// Magic-Link nachgewiesene Adresse → nach der Anmeldung ist das Feld gesetzt.
//
// Der Vorrang mail_to > email wird hier NICHT mitgemessen — er KANN hier nicht
// gemessen werden: der Magic-Link löst das Konto über FindUserByEmail auf
// (auth_magic.go:64). Trüge email eine andere Adresse als die nachgewiesene,
// fände der Fluss dieses Konto gar nicht und legte ein neues an; der Test
// prüfte dann nichts. Deshalb sind beide Felder hier absichtlich gleich.
// Bewacht wird der Vorrang von AC-5 (abweichendes mail_to → Feld bleibt nil)
// und AC-6, dessen Fixture email und mail_to tatsächlich auseinanderzieht.
func TestSelbstheilungMagicLinkSetztBestaetigungBeiAdressgleichheit_AC4(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)

	const uid = "m-rosa2304"
	const nachgewiesen = "rosa-postfach@beispiel.de"
	if err := s.SaveUser(model.User{
		ID:        uid,
		Email:     nachgewiesen, // Grundlage der Konto-Auflösung (FindUserByEmail)
		MailTo:    nachgewiesen, // effektive Kontaktadresse — identisch
		CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("AC-4: Konto anlegen: %v", err)
	}

	// SMTPHost leer → der Magic-Link-Handler überspringt den Versand.
	cfg := &config.Config{SessionSecret: selbstheilungSecret}
	w := magicLinkAnmeldung(t, s, cfg, nachgewiesen)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4: Magic-Link-Anmeldung erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	user := ladeKonto(t, s, uid)
	if user.EmailVerifiedAt == nil {
		t.Fatalf("AC-4: nach erfolgreicher Magic-Link-Anmeldung an die effektive Kontaktadresse %q "+
			"muss email_verified_at gesetzt sein — es ist nicht gesetzt (Selbstheilung fehlt)", nachgewiesen)
	}
	if user.EmailVerifiedAt.After(time.Now().Add(time.Minute)) ||
		user.EmailVerifiedAt.Before(time.Now().Add(-time.Hour)) {
		t.Errorf("AC-4: email_verified_at %v liegt nicht plausibel nahe am Anmeldezeitpunkt", user.EmailVerifiedAt)
	}
}

// AC-5: mail_to zeigt auf eine ANDERE Adresse als die nachgewiesene → das Feld
// bleibt ungesetzt, UND die Anmeldung gelingt trotzdem (S1 sperrt nichts).
//
// Hinweis zur Aussagekraft: die erste Hälfte ist heute grün, weil es die
// Selbstheilung noch gar nicht gibt (Grün durch Bauart). Ihre Wächterwirkung
// entsteht erst mit der Implementierung — wer den Adressvergleich dann
// weglässt und bedingungslos setzt, wird von genau diesem Test gefangen.
func TestSelbstheilungMagicLinkSchweigtBeiAbweichenderKontaktadresse_AC5(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)

	const uid = "m-bruno2304"
	const nachgewiesen = "bruno-postfach@beispiel.de"
	const andereKontaktadresse = "bruno-woanders@beispiel.de"
	if err := s.SaveUser(model.User{
		ID:        uid,
		Email:     nachgewiesen,
		MailTo:    andereKontaktadresse, // effektive Kontaktadresse WEICHT AB
		CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("AC-5: Konto anlegen: %v", err)
	}

	cfg := &config.Config{SessionSecret: selbstheilungSecret}
	w := magicLinkAnmeldung(t, s, cfg, nachgewiesen)

	// Hälfte 1: die Anmeldung gelingt — mit gültigem Sitzungs-Merkmal.
	if w.Code != http.StatusOK {
		t.Fatalf("AC-5: die Anmeldung muss trotz abweichender Kontaktadresse gelingen, "+
			"bekommen %d: %s", w.Code, w.Body.String())
	}
	var sitzung *http.Cookie
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			sitzung = c
		}
	}
	if sitzung == nil || sitzung.Value == "" {
		t.Fatalf("AC-5: kein gz_session-Cookie in der Antwort — die Anmeldung wurde faktisch verweigert")
	}

	// Hälfte 2: das Bestätigungsfeld bleibt unangetastet.
	user := ladeKonto(t, s, uid)
	if user.EmailVerifiedAt != nil {
		t.Errorf("AC-5: email_verified_at darf bei abweichender Kontaktadresse NICHT gesetzt werden, "+
			"ist aber %v (nachgewiesen: %q, Kontaktadresse: %q)",
			user.EmailVerifiedAt, nachgewiesen, andereKontaktadresse)
	}
}

// AC-6: bestehendes Google-Konto ohne email_verified_at, effektive
// Kontaktadresse == die von Google bestätigte Adresse → nach erneuter
// Anmeldung ist das Feld gesetzt.
//
// Bestands-Zweig mit Absicht (FindUserByOAuthSub findet das Konto): dort läuft
// KEIN Verifikations-Dispatch, also kein Mailweg im Spiel. Auch hier trägt
// mail_to die Google-Adresse und email eine andere — der Vorrang wird
// mitgemessen.
func TestSelbstheilungGoogleSetztBestaetigungBeiAdressgleichheit_AC6(t *testing.T) {
	s := newTestStore(t)

	const uid = "g-clara2304"
	const googleAdresse = "clara-google@beispiel.de"
	const alteAdresse = "clara-alt@beispiel.de"
	const sub = "sub-2304-clara"
	if err := s.SaveUser(model.User{
		ID:            uid,
		OAuthProvider: "google",
		OAuthSub:      sub,
		Email:         alteAdresse,
		MailTo:        googleAdresse, // effektive Kontaktadresse == Google-Adresse
		CreatedAt:     time.Now(),
	}); err != nil {
		t.Fatalf("AC-6: Konto anlegen: %v", err)
	}

	userinfoURL, tokenURL := oauthFakeServers(t, sub, googleAdresse)
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      selbstheilungSecret,
	}

	const state = "state-2304-clara"
	req := httptest.NewRequest(http.MethodGet,
		"/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL).ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("AC-6: Google-Callback erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
	}

	user := ladeKonto(t, s, uid)
	if user.EmailVerifiedAt == nil {
		t.Fatalf("AC-6: nach erneuter Google-Anmeldung mit bestätigter Adresse %q muss "+
			"email_verified_at gesetzt sein — es ist nicht gesetzt (Selbstheilung fehlt)", googleAdresse)
	}
}

// vergleicheKontoFelderAusser vergleicht zwei Kontostände feldweise über ihre
// JSON-Darstellung — die Form, in der das Konto tatsächlich auf der Platte
// liegt. Verglichen wird die VEREINIGUNG beider Schlüsselmengen: Felder mit
// `omitempty` verschwinden beim Verlust vollständig aus der Karte, eine
// Schleife über nur eine Seite würde genau diesen Verlust übersehen.
func vergleicheKontoFelderAusser(t *testing.T, was string, vorher, nachher *model.User, ausgenommen string) {
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
		delete(m, ausgenommen)
		return m
	}
	zeige := func(r json.RawMessage) string {
		if r == nil {
			return "(Feld fehlt)"
		}
		return string(r)
	}
	a, b := karte(vorher), karte(nachher)
	schluessel := map[string]bool{}
	for k := range a {
		schluessel[k] = true
	}
	for k := range b {
		schluessel[k] = true
	}
	for k := range schluessel {
		if string(a[k]) == string(b[k]) {
			continue
		}
		t.Errorf("%s: Feld %q hat die Selbstheilung nicht überlebt — vorher %s, nachher %s. "+
			"Die Selbstheilung MUSS das vollständig geladene Konto zurückschreiben "+
			"(Read-Modify-Write, CLAUDE.md »Daten-Schema-Reworks«, BUG-DATALOSS-GR221) — "+
			"ein Teilobjekt löscht bei jeder Anmeldung stumm Kontodaten.",
			was, k, zeige(a[k]), zeige(b[k]))
	}
}

// reichesKonto2304 liefert ein Konto mit gefüllten Feldern quer durch das
// Modell — Anmeldegeheimnisse (PasswordHash, PasskeyCredentials), Kontaktwege
// und Profildaten. Nur so kann ein Feldverlust überhaupt sichtbar werden.
func reichesKonto2304(uid, email, mailTo string) model.User {
	stempel := time.Date(2026, 3, 4, 5, 6, 7, 0, time.UTC)
	return model.User{
		ID:           uid,
		Email:        email,
		MailTo:       mailTo,
		PasswordHash: "$2a$10$diesIstEinBcryptHashF001",
		PasskeyCredentials: []model.WebAuthnCredential{{
			ID: []byte{1, 2, 3}, PublicKey: []byte{9, 8, 7},
			AttestationType: "none", Transport: []string{"internal"},
			CreatedAt: stempel, Label: "Telefon",
		}},
		DisplayName:       "Konto mit Inhalt",
		Tier:              "premium",
		SmsTo:             "+4915112345678",
		TelegramChatID:    "123456789",
		RequestedTier:     "pro",
		RequestedAt:       &stempel,
		PremiumSmsReplyTo: "reply-2304@inreach.garmin.com",
		PremiumSmsReplyAt: &stempel,
		CreatedAt:         stempel,
	}
}

// F001 (Adversary-Befund, CRITICAL): die Selbstheilung schreibt das Konto auf
// dem LIVE-Anmeldeweg zurück. Bewacht war bisher nur, DASS email_verified_at
// gesetzt wird — nicht, dass dabei alles andere erhalten bleibt. Ein
// Teilobjekt statt des geladenen Kontos (Replace statt Read-Modify-Write)
// löschte PasswordHash und PasskeyCredentials bei der nächsten Anmeldung,
// ohne dass ein Test rot wurde.
//
// Geprüft wird für BEIDE Selbstheilungs-Pfade am Wirkort: echter HTTP-Fluss,
// danach das Konto frisch von der Platte, Vergleich des VOLLSTÄNDIGEN Objekts
// gegen den Ausgangsstand bis auf email_verified_at. Der Ausgangsstand wird
// bewusst aus dem Speicher gelesen (nicht die Fixture im Arbeitsspeicher
// benutzt), damit beide Seiten denselben JSON-Rundlauf hinter sich haben.
func TestSelbstheilungErhaeltAlleUebrigenKontofelder_F001(t *testing.T) {
	const magicAdresse = "eva-postfach@beispiel.de"
	const googleAdresse = "fynn-google@beispiel.de"
	const googleSub = "sub-2304-fynn"

	faelle := []struct {
		name     string
		uid      string
		email    string
		mailTo   string
		sub      string
		anmelden func(t *testing.T, s *store.Store, konto model.User)
	}{
		{
			name: "magic-link", uid: "m-eva2304",
			email: magicAdresse, mailTo: magicAdresse,
			anmelden: func(t *testing.T, s *store.Store, konto model.User) {
				t.Cleanup(ResetOTPStoreForTest)
				cfg := &config.Config{SessionSecret: selbstheilungSecret}
				w := magicLinkAnmeldung(t, s, cfg, konto.Email)
				if w.Code != http.StatusOK {
					t.Fatalf("F001/Magic-Link: Anmeldung erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
				}
			},
		},
		{
			name: "google-oauth", uid: "g-fynn2304",
			email: "fynn-alt@beispiel.de", mailTo: googleAdresse, sub: googleSub,
			anmelden: func(t *testing.T, s *store.Store, konto model.User) {
				userinfoURL, tokenURL := oauthFakeServers(t, konto.OAuthSub, konto.MailTo)
				cfg := &config.Config{
					GoogleClientID:     "test-client-id",
					GoogleClientSecret: "test-secret",
					GoogleRedirectURL:  "https://example.com/callback",
					SessionSecret:      selbstheilungSecret,
				}
				const state = "state-2304-f001"
				req := httptest.NewRequest(http.MethodGet,
					"/api/auth/google/callback?code=test-code&state="+state, nil)
				req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
				w := httptest.NewRecorder()
				GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL).ServeHTTP(w, req)
				if w.Code != http.StatusFound {
					t.Fatalf("F001/Google: Callback erwartet 302, bekommen %d: %s", w.Code, w.Body.String())
				}
			},
		},
	}

	for _, fall := range faelle {
		t.Run(fall.name, func(t *testing.T) {
			s := newTestStore(t)

			konto := reichesKonto2304(fall.uid, fall.email, fall.mailTo)
			if fall.sub != "" {
				konto.OAuthProvider, konto.OAuthSub = "google", fall.sub
			}
			if err := s.SaveUser(konto); err != nil {
				t.Fatalf("F001: Konto anlegen: %v", err)
			}
			vorher := ladeKonto(t, s, fall.uid)
			if vorher.EmailVerifiedAt != nil {
				t.Fatalf("F001 Ausgangslage: email_verified_at darf vor der Anmeldung nicht gesetzt sein")
			}

			fall.anmelden(t, s, konto)

			nachher := ladeKonto(t, s, fall.uid)
			// Positivkontrolle: ohne tatsächlich gelaufene Selbstheilung wäre
			// der Feldvergleich trivial grün (nichts geschrieben, nichts verloren).
			if nachher.EmailVerifiedAt == nil {
				t.Fatalf("F001 Positivkontrolle: die Selbstheilung lief gar nicht — "+
					"email_verified_at ist nach der Anmeldung an %q nicht gesetzt, "+
					"der Feldvergleich unten hätte nichts zu bewachen", fall.mailTo)
			}
			vergleicheKontoFelderAusser(t, "F001/"+fall.name, vorher, nachher, "email_verified_at")
		})
	}
}
