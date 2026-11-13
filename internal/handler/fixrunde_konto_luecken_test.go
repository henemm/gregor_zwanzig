package handler

// Issue #2961, Fix-Runde Welle 2: Hinweis beim Anstossen eines Wechsels (F-F)
// und Testluecken aus der Gegenpruefung (M11, M13, M44).

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

func profilPut(h http.Handler, uid, body string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	h.ServeHTTP(w, addUserToContext(httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body)), uid))
	return w
}

// F-F: schon beim Anstossen eines Adress- bzw. Kennungswechsels geht ein
// Hinweis an die bisherige bestaetigte Adresse — nicht an die neue, nicht an
// fremde Konten, nicht bei unbestaetigten Konten.
func TestHinweis_WechselAngefordertGehtAnDieBisherigeAdresse(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "ff-a", "ff-a@beispiel.de", "")
	bestaetigtesKonto(t, s, "ff-b", "ff-b@beispiel.de", "")
	if err := s.SaveUser(model.User{ID: "ff-u", Email: "ff-u@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)

	if w := profilPut(h, "ff-a", `{"mail_to":"ff-a-neu@beispiel.de"}`); w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	if w := profilPut(h, "ff-u", `{"mail_to":"ff-u-neu@beispiel.de"}`); w.Code != http.StatusOK {
		t.Fatalf("PUT unbestaetigt: %d %s", w.Code, w.Body.String())
	}
	var hinweise []hinweisPost
	for _, m := range hinweiseAbwarten(post, 300*time.Millisecond) {
		if strings.Contains(m.msg.Subject, "angefordert") {
			hinweise = append(hinweise, m)
		}
	}
	if len(hinweise) != 1 || hinweise[0].to != "ff-a@beispiel.de" {
		t.Fatalf("erwartet genau einen Hinweis an die bisherige Adresse von ff-a, bekommen %+v", hinweise)
	}
	if !strings.Contains(hinweise[0].msg.PlainBody, "ff-a-neu@beispiel.de") || !strings.Contains(hinweise[0].msg.PlainBody, "/forgot-password") {
		t.Errorf("Hinweis nennt neue Adresse oder Rueckweg nicht: %q", hinweise[0].msg.PlainBody)
	}

	// Kennungswechsel: eigene Art.
	if w := profilPut(h, "ff-b", `{"email":"ff-b-login@beispiel.de"}`); w.Code != http.StatusOK {
		t.Fatalf("PUT email: %d %s", w.Code, w.Body.String())
	}
	var kennung []hinweisPost
	for _, m := range hinweiseAbwarten(post, 300*time.Millisecond) {
		if strings.Contains(m.msg.Subject, "Anmelde-Adresse") {
			kennung = append(kennung, m)
		}
	}
	if len(kennung) != 1 || kennung[0].to != "ff-b@beispiel.de" {
		t.Fatalf("Kennungswechsel: erwartet Hinweis an ff-b@beispiel.de, bekommen %+v", kennung)
	}
}

// M11: der Nachweis-Code geht an die BISHERIGE wirksame Adresse, auch wenn
// eine Adressaenderung aussteht — nie an die ausstehende.
func TestReauthCode_GehtAnBisherigeAdresseTrotzAusstehenderAenderung(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "m11", Email: "m11@beispiel.de", MailTo: "m11-post@beispiel.de",
		PendingContactAddress: "m11-angreifer@beispiel.de", PendingContactField: "mail_to",
		CreatedAt: jetzt, EmailVerifiedAt: &jetzt}); err != nil {
		t.Fatal(err)
	}
	h := RequestReauthCodeHandler(s, config.Config{SMTPHost: "smtp.test"}, NewMailFloodLimiter(10, time.Minute))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, addUserToContext(httptest.NewRequest(http.MethodPost, "/api/auth/reauth/code", strings.NewReader(`{}`)), "m11"))
	if w.Code != http.StatusOK {
		t.Fatalf("Code anfordern: %d %s", w.Code, w.Body.String())
	}
	mails := hinweiseAbwarten(post, 200*time.Millisecond)
	if len(mails) != 1 || mails[0].to != "m11-post@beispiel.de" {
		t.Fatalf("Code muss an die bisherige wirksame Adresse gehen, bekommen %+v", mails)
	}
	if _, ok := reauthCodeStore.Load("m11"); !ok {
		t.Error("Code muss gespeichert sein")
	}
}

// M13: Passwort-Raten am Nachweis-Endpunkt ist gebremst — nach 5 falschen
// Passwoertern binnen 15 Minuten wird auch das richtige abgewiesen (429); ein
// anderer Nutzer ist nicht betroffen.
func TestReauth_PasswortRatenGebremst(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "m13-a", "m13-a@beispiel.de")
	passwortKonto(t, s, "m13-b", "m13-b@beispiel.de")
	h := ReauthHandler(s, reauthTestSecret)
	for i := 1; i <= 5; i++ {
		if w := reauthAnfrage(h, "m13-a", "s1", `{"password":"falsch-`+string(rune('0'+i))+`"}`); w.Code != http.StatusForbidden {
			t.Fatalf("Versuch %d: erwartet 403, bekommen %d", i, w.Code)
		}
	}
	if w := reauthAnfrage(h, "m13-a", "s1", `{"password":"`+loeschPasswort+`"}`); w.Code != http.StatusTooManyRequests {
		t.Fatalf("nach 5 Fehlversuchen: erwartet 429, bekommen %d", w.Code)
	}
	if hasFreshReauth("m13-a", "s1", time.Now()) {
		t.Fatal("gebremster Versuch darf keinen Nachweis ergeben")
	}
	if w := reauthAnfrage(h, "m13-b", "s1", `{"password":"`+loeschPasswort+`"}`); w.Code != http.StatusOK {
		t.Fatalf("anderer Nutzer: erwartet 200, bekommen %d", w.Code)
	}
}

// M44: ein durch einen neueren Wechsel ueberholter Bestaetigungslink wirkt nicht.
func TestBestaetigung_UeberholterLinkWirktNicht(t *testing.T) {
	s := newTestStore(t)
	bestaetigtesKonto(t, s, "m44", "m44@beispiel.de", "")
	h := UpdateProfileHandler(s, config.Config{}, weitMailLimiter, weitSmsLimiter)
	if w := profilPut(h, "m44", `{"mail_to":"m44-x@beispiel.de"}`); w.Code != http.StatusOK {
		t.Fatal(w.Body.String())
	}
	alt, err := issueVerificationToken(s, "m44", "m44-x@beispiel.de")
	if err != nil {
		t.Fatal(err)
	}
	if w := profilPut(h, "m44", `{"mail_to":"m44-y@beispiel.de"}`); w.Code != http.StatusOK {
		t.Fatal(w.Body.String())
	}
	if _, err := issueVerificationToken(s, "m44", "m44-y@beispiel.de"); err != nil {
		t.Fatal(err)
	}
	w := httptest.NewRecorder()
	VerifyEmailHandler(s).ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/verify-email",
		strings.NewReader(`{"user":"m44","token":"`+alt+`"}`)))
	if w.Code != http.StatusBadRequest {
		t.Fatalf("ueberholter Link: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
	u, _ := s.LoadUser("m44")
	if u.MailTo != "" || u.PendingContactAddress != "m44-y@beispiel.de" {
		t.Fatalf("ueberholter Link hat etwas veraendert: mail_to=%q pending=%q", u.MailTo, u.PendingContactAddress)
	}
}
