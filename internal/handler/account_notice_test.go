package handler

// Issue #2961 (GA3, ADR-0115): Hinweis-Mails bei sicherheitsrelevanten
// Kontoaenderungen. Beobachtet am Postausgang (sendVerificationMailFn, die
// Transportgrenze des engen Versandwegs), nicht an einer Hilfsfunktion.

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type hinweisPost struct {
	to  string
	msg mail.Mail
}

// hinweisPostausgang faengt alle Mails des engen Versandwegs ab; fehler
// steuert, ob der Versand scheitert.
func hinweisPostausgang(t *testing.T, fehler error) chan hinweisPost {
	t.Helper()
	ch := make(chan hinweisPost, 50)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, msg mail.Mail) error {
		ch <- hinweisPost{to: to, msg: msg}
		return fehler
	}
	alt := accountNoticeCfg.Load()
	SetAccountNoticeConfig(config.Config{SMTPHost: "smtp.hinweis.test", PublicHost: "https://gz.beispiel.de"})
	t.Cleanup(func() {
		sendVerificationMailFn = orig
		accountNoticeCfg.Store(alt)
	})
	return ch
}

// hinweiseAbwarten sammelt Mails, bis waehrend `ruhe` keine weitere kommt.
func hinweiseAbwarten(ch chan hinweisPost, ruhe time.Duration) []hinweisPost {
	var out []hinweisPost
	for {
		select {
		case p := <-ch:
			out = append(out, p)
		case <-time.After(ruhe):
			return out
		}
	}
}

func bestaetigtesKonto(t *testing.T, s *store.Store, id, adresse, passwort string) {
	t.Helper()
	jetzt := time.Now().UTC()
	u := model.User{ID: id, Email: adresse, CreatedAt: jetzt, EmailVerifiedAt: &jetzt}
	if passwort != "" {
		h, err := bcrypt.GenerateFromPassword([]byte(passwort), bcrypt.MinCost)
		if err != nil {
			t.Fatal(err)
		}
		u.PasswordHash = string(h)
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatal(err)
	}
}

func passwortAendern(s *store.Store, id, alt, neu string) *httptest.ResponseRecorder {
	body, _ := json.Marshal(map[string]string{"old_password": alt, "new_password": neu})
	req := addUserToContext(httptest.NewRequest(http.MethodPut, "/api/auth/password", bytes.NewReader(body)), id)
	w := httptest.NewRecorder()
	ChangePasswordHandler(s, bcrypt.MinCost, changePwTestSecret, "")(w, req)
	return w
}

func TestHinweis_PasswortGeaendert_NurAnDasEigeneKonto(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "hinweis-pw-a", "pw-a@beispiel.de", "altes-pw-1")
	bestaetigtesKonto(t, s, "hinweis-pw-b", "pw-b@beispiel.de", "altes-pw-2")

	if w := passwortAendern(s, "hinweis-pw-a", "altes-pw-1", "neues-pw-1"); w.Code != http.StatusOK {
		t.Fatalf("Passwortwechsel: %d %s", w.Code, w.Body.String())
	}
	mails := hinweiseAbwarten(post, 300*time.Millisecond)
	if len(mails) != 1 || mails[0].to != "pw-a@beispiel.de" {
		t.Fatalf("erwartet genau eine Hinweis-Mail an pw-a@beispiel.de, bekommen %+v", mails)
	}
	if !strings.Contains(mails[0].msg.Subject, "Passwort") || !strings.Contains(mails[0].msg.PlainBody, "/forgot-password") {
		t.Errorf("Hinweis-Mail ohne Betreff/Rueckweg: %q / %q", mails[0].msg.Subject, mails[0].msg.PlainBody)
	}
}

func TestHinweis_MailfehlerBrichtAenderungNichtAb(t *testing.T) {
	post := hinweisPostausgang(t, errors.New("smtp kaputt"))
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "hinweis-fehler", "fehler@beispiel.de", "altes-pw-1")
	if w := passwortAendern(s, "hinweis-fehler", "altes-pw-1", "neues-pw-1"); w.Code != http.StatusOK {
		t.Fatalf("Mailfehler darf den Wechsel nicht abbrechen: %d %s", w.Code, w.Body.String())
	}
	if len(hinweiseAbwarten(post, 300*time.Millisecond)) != 1 {
		t.Fatal("Versand wurde nicht versucht")
	}
	u, _ := s.LoadUser("hinweis-fehler")
	if bcrypt.CompareHashAndPassword([]byte(u.PasswordHash), []byte("neues-pw-1")) != nil {
		t.Error("neues Passwort nicht gespeichert")
	}
}

func TestHinweis_MengenbremseFuenfJeNutzerUndStunde(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "hinweis-flut-a", "flut-a@beispiel.de", "pw-0-langgenug")
	bestaetigtesKonto(t, s, "hinweis-flut-b", "flut-b@beispiel.de", "pw-0-langgenug")
	for i := 0; i < 6; i++ {
		alt, neu := "pw-"+string(rune('0'+i))+"-langgenug", "pw-"+string(rune('1'+i))+"-langgenug"
		if w := passwortAendern(s, "hinweis-flut-a", alt, neu); w.Code != http.StatusOK {
			t.Fatalf("Wechsel %d: %d %s", i, w.Code, w.Body.String())
		}
	}
	if w := passwortAendern(s, "hinweis-flut-b", "pw-0-langgenug", "pw-1-langgenug"); w.Code != http.StatusOK {
		t.Fatalf("Wechsel b: %d", w.Code)
	}
	zaehler := map[string]int{}
	for _, m := range hinweiseAbwarten(post, 400*time.Millisecond) {
		zaehler[m.to]++
	}
	if zaehler["flut-a@beispiel.de"] != 5 {
		t.Errorf("Nutzer a: erwartet 5 Hinweis-Mails (Bremse), bekommen %d", zaehler["flut-a@beispiel.de"])
	}
	if zaehler["flut-b@beispiel.de"] != 1 {
		t.Errorf("Nutzer b darf von der Bremse von a nicht betroffen sein: %d", zaehler["flut-b@beispiel.de"])
	}
}

func TestHinweis_UnbestaetigtesKontoBekommtKeine(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	setupUserWithPassword(t, s, "hinweis-unbestaetigt", "altes-pw-1")
	if w := passwortAendern(s, "hinweis-unbestaetigt", "altes-pw-1", "neues-pw-1"); w.Code != http.StatusOK {
		t.Fatalf("%d %s", w.Code, w.Body.String())
	}
	if m := hinweiseAbwarten(post, 300*time.Millisecond); len(m) != 0 {
		t.Errorf("unbestaetigtes Konto: keine Hinweis-Mail erwartet, bekommen %+v", m)
	}
}

func TestHinweis_AdresswechselGehtAnDieAlteAdresse(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "hinweis-adr-a", "alt-a@beispiel.de", "")
	bestaetigtesKonto(t, s, "hinweis-adr-b", "alt-b@beispiel.de", "")

	// Adresswechsel anstossen (wartet auf Bestaetigung), Link einloesen.
	put := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(`{"mail_to":"neu-a@beispiel.de"}`))
	put = addUserToContext(put, "hinweis-adr-a")
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter).ServeHTTP(w, put)
	if w.Code != http.StatusOK {
		t.Fatalf("Profil: %d %s", w.Code, w.Body.String())
	}
	token, err := issueVerificationToken(s, "hinweis-adr-a", "neu-a@beispiel.de")
	if err != nil {
		t.Fatal(err)
	}
	hinweiseAbwarten(post, 200*time.Millisecond) // Bestaetigungsmail o. ae. verwerfen
	vw := httptest.NewRecorder()
	VerifyEmailHandler(s).ServeHTTP(vw, httptest.NewRequest(http.MethodPost, "/api/auth/verify-email",
		strings.NewReader(`{"user":"hinweis-adr-a","token":"`+token+`"}`)))
	if vw.Code != http.StatusOK {
		t.Fatalf("Bestaetigung: %d %s", vw.Code, vw.Body.String())
	}
	mails := hinweiseAbwarten(post, 300*time.Millisecond)
	if len(mails) != 1 || mails[0].to != "alt-a@beispiel.de" {
		t.Fatalf("erwartet genau eine Hinweis-Mail an die ALTE Adresse, bekommen %+v", mails)
	}
	if !strings.Contains(mails[0].msg.PlainBody, "neu-a@beispiel.de") {
		t.Errorf("Hinweis nennt die neue Adresse nicht: %q", mails[0].msg.PlainBody)
	}
}

func TestHinweis_PasskeyHinzugefuegtUndEntfernt(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	bestaetigtesKonto(t, s, "hinweis-pk", "pk@beispiel.de", "pw-langgenug")
	bestaetigtesKonto(t, s, "hinweis-pk-b", "pk-b@beispiel.de", "pw-langgenug")

	bw := httptest.NewRecorder()
	PasskeyRegisterBeginHandler(s, wa, cs).ServeHTTP(bw, authedRequest("POST", "/api/auth/passkey/register/begin", "hinweis-pk", nil))
	var begin struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(bw.Body.Bytes(), &begin); err != nil {
		t.Fatal(err)
	}
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	fw := httptest.NewRecorder()
	PasskeyRegisterFinishHandler(s, wa, cs).ServeHTTP(fw, authedRequest("POST", "/api/auth/passkey/register/finish", "hinweis-pk",
		auth.MakeAttestationResponse(t, begin.PublicKey.Challenge)))
	if fw.Code != http.StatusCreated {
		t.Fatalf("Passkey anlegen: %d %s", fw.Code, fw.Body.String())
	}
	var neu struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(fw.Body.Bytes(), &neu)

	dw := httptest.NewRecorder()
	PasskeyDeleteCredentialHandler(s).ServeHTTP(dw, authedRequest("DELETE", "/api/auth/passkey/credentials/"+neu.ID, "hinweis-pk", nil))
	if dw.Code != http.StatusOK {
		t.Fatalf("Passkey entfernen: %d %s", dw.Code, dw.Body.String())
	}
	// Ein Entfernen ohne Treffer ist keine Aenderung und meldet nichts.
	dw = httptest.NewRecorder()
	PasskeyDeleteCredentialHandler(s).ServeHTTP(dw, authedRequest("DELETE", "/api/auth/passkey/credentials/AQID", "hinweis-pk-b", nil))

	mails := hinweiseAbwarten(post, 300*time.Millisecond)
	if len(mails) != 2 {
		t.Fatalf("erwartet 2 Hinweis-Mails (hinzugefuegt, entfernt), bekommen %d: %+v", len(mails), mails)
	}
	var betreffe []string
	for _, m := range mails {
		if m.to != "pk@beispiel.de" {
			t.Errorf("Hinweis an falsche Adresse: %q", m.to)
		}
		betreffe = append(betreffe, m.msg.Subject)
	}
	if betreffe[0] == betreffe[1] {
		t.Errorf("hinzugefuegt und entfernt muessen unterscheidbar sein: %v", betreffe)
	}
}
