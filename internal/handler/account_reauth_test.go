package handler

// Issue #2961 (GA3, ADR-0115): Nachweis vor Kontoaenderungen — Ablauf nach 10
// Minuten, Bindung an Nutzer und Sitzung, Code-Weg getrennt vom Lösch-Code.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
)

const reauthTestSecret = "reauth-test-secret"

func reauthAnfrage(h http.Handler, userID, sessionID, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/reauth", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	if sessionID != "" {
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID(userID, sessionID, reauthTestSecret)})
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func TestReauth_NachweisLaeuftNachZehnMinutenAb(t *testing.T) {
	jetzt := time.Now()
	grantReauth("reauth-ablauf", "s1", jetzt)
	if !hasFreshReauth("reauth-ablauf", "s1", jetzt.Add(9*time.Minute+59*time.Second)) {
		t.Fatal("innerhalb von 10 Minuten muss der Nachweis gelten")
	}
	if hasFreshReauth("reauth-ablauf", "s1", jetzt.Add(10*time.Minute)) {
		t.Fatal("nach 10 Minuten darf der Nachweis nicht mehr gelten")
	}
	if hasFreshReauth("reauth-ablauf", "s2", jetzt) || hasFreshReauth("reauth-anderer", "s1", jetzt) {
		t.Fatal("der Nachweis gilt nur fuer genau diesen Nutzer und diese Sitzung")
	}
	gcReauthGrants(jetzt.Add(11 * time.Minute))
	if _, ok := reauthGrants.Load(reauthKey("reauth-ablauf", "s1")); ok {
		t.Error("abgelaufener Nachweis muss vom Reaper entfernt werden")
	}
}

func TestReauth_CodeWegGetrenntVomLoeschCode(t *testing.T) {
	s := newTestStore(t)
	passwortlosKonto(t, s, "reauth-code-a", "a@beispiel.de")
	passwortlosKonto(t, s, "reauth-code-b", "b@beispiel.de")
	h := ReauthHandler(s, reauthTestSecret)
	ablauf := time.Now().Add(deleteCodeTTL)

	// Ein Lösch-Code ist kein Nachweis-Code.
	deleteCodeStore.Store("reauth-code-a", &deleteCodeEntry{code: "111111", expiresAt: ablauf})
	t.Cleanup(func() { deleteCodeStore.Delete("reauth-code-a") })
	if w := reauthAnfrage(h, "reauth-code-a", "s1", `{"code":"111111"}`); w.Code != http.StatusForbidden {
		t.Fatalf("Lösch-Code als Nachweis: erwartet 403, bekommen %d: %s", w.Code, w.Body.String())
	}

	// Der Code von a gilt nicht fuer b.
	reauthCodeStore.Store("reauth-code-a", &deleteCodeEntry{code: "222222", expiresAt: ablauf})
	if w := reauthAnfrage(h, "reauth-code-b", "s1", `{"code":"222222"}`); w.Code != http.StatusForbidden {
		t.Fatalf("fremder Code: erwartet 403, bekommen %d", w.Code)
	}
	if hasFreshReauth("reauth-code-b", "s1", time.Now()) {
		t.Fatal("b darf keinen Nachweis haben")
	}

	w := reauthAnfrage(h, "reauth-code-a", "s1", `{"code":"222222"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("richtiger Code: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !hasFreshReauth("reauth-code-a", "s1", time.Now()) {
		t.Fatal("nach richtigem Code muss der Nachweis fuer diese Sitzung gelten")
	}
	// Einmalig.
	if w := reauthAnfrage(h, "reauth-code-a", "s2", `{"code":"222222"}`); w.Code != http.StatusForbidden {
		t.Fatalf("Code zweimal: erwartet 403, bekommen %d", w.Code)
	}
	if _, ok := deleteCodeStore.Load("reauth-code-a"); !ok {
		t.Error("der Nachweis-Weg darf den Lösch-Code nicht verbrauchen")
	}
}

func TestReauth_OhneSitzungUndOhneNachweis(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "reauth-leer", "leer@beispiel.de")
	h := ReauthHandler(s, reauthTestSecret)
	if w := reauthAnfrage(h, "reauth-leer", "", `{"password":"`+loeschPasswort+`"}`); w.Code != http.StatusUnauthorized {
		t.Fatalf("ohne Sitzungs-Cookie: erwartet 401, bekommen %d", w.Code)
	}
	if w := reauthAnfrage(h, "reauth-leer", "s1", `{}`); w.Code != http.StatusBadRequest {
		t.Fatalf("ohne Nachweis: erwartet 400, bekommen %d", w.Code)
	}
	// Passwortloses Konto: ein mitgeschicktes Passwort ist kein Nachweis.
	passwortlosKonto(t, s, "reauth-ohnepw", "ohnepw@beispiel.de")
	if w := reauthAnfrage(h, "reauth-ohnepw", "s1", `{"password":"irgendwas"}`); w.Code != http.StatusForbidden {
		t.Fatalf("Passwort am passwortlosen Konto: erwartet 403, bekommen %d", w.Code)
	}
	if w := reauthAnfrage(h, "reauth-leer", "s1", `{"password":"`+loeschPasswort+`"}`); w.Code != http.StatusOK {
		t.Fatalf("richtiges Passwort: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}
