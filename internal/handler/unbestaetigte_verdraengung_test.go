package handler

// Issue #2961 (GA2a, Fix-Runde F-B): verdraengt wird erst unmittelbar vor der
// Kontoanlage; scheitert die Registrierung vorher (ungueltige Einladung) oder
// die Anlage danach, bleibt bzw. kommt die fremde unbestaetigte Anmeldung
// zurueck. Bremse: hoechstens eine Ersetzung je Zieladresse und Stunde. Der
// Passkey-Registrierungsweg ersetzt ebenso.

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
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func registrierenMitEinladung(s *store.Store, inv *store.InviteStore, adresse, invite string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	RegisterHandlerWithInvites(s, bcrypt.MinCost, config.Config{}, inv).ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register",
		strings.NewReader(`{"password":"eigenes-pw-123","email":"`+adresse+`","invite":"`+invite+`"}`)))
	return w
}

func TestVerdraengung_GescheiterteRegistrierungLaesstAnmeldungStehen(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-bleibt-inv", "fb-inv@beispiel.de", jetzt, jetzt.Add(time.Hour))
	inv := store.NewInviteStore(s.DataDir)

	if w := registrierenMitEinladung(s, inv, "fb-inv@beispiel.de", "gibt-es-nicht"); w.Code != http.StatusBadRequest {
		t.Fatalf("ungueltige Einladung: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !s.UserExists("u-bleibt-inv") || len(ablageEintraege(t, s)) != 0 {
		t.Fatal("eine gescheiterte Registrierung darf die fremde Anmeldung nicht verdraengen")
	}
}

func TestVerdraengung_ScheiterndeAnlageHoltAnmeldungZurueck(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-zurueck", "fb-zurueck@beispiel.de", jetzt, jetzt.Add(time.Hour))
	orig := createUserFn
	createUserFn = func(*store.Store, model.User) error { return errors.New("platte voll") }
	t.Cleanup(func() { createUserFn = orig })

	if w := registrieren(s, "fb-zurueck@beispiel.de", "eigenes-pw-123"); w.Code != http.StatusInternalServerError {
		t.Fatalf("scheiternde Anlage: erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
	}
	u, err := s.LoadUser("u-zurueck")
	if err != nil || u == nil || u.Email != "fb-zurueck@beispiel.de" {
		t.Fatalf("die verdraengte Anmeldung muss zurueck in users/ sein: %+v %v", u, err)
	}
	if a := ablageEintraege(t, s); len(a) != 0 {
		t.Fatalf("Ablage muss wieder leer sein: %v", a)
	}
}

func TestVerdraengung_HoechstensEinmalJeAdresseUndStunde(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-erste", "fb-bremse@beispiel.de", jetzt, jetzt.Add(time.Hour))
	unbestaetigteAnmeldung(t, s, "u-andere", "fb-andere@beispiel.de", jetzt, jetzt.Add(time.Hour))

	w := registrieren(s, "fb-bremse@beispiel.de", "eigenes-pw-123")
	if w.Code != http.StatusCreated {
		t.Fatalf("erste Ersetzung: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	var neu struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &neu)
	if w := registrieren(s, "fb-bremse@beispiel.de", "noch-ein-pw-123"); w.Code != http.StatusConflict {
		t.Fatalf("zweite Ersetzung binnen einer Stunde: erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !s.UserExists(neu.ID) {
		t.Fatal("das Konto der ersten Ersetzung muss bleiben")
	}
	// Die Bremse gilt je Adresse: eine andere Adresse ist nicht betroffen.
	if w := registrieren(s, "fb-andere@beispiel.de", "eigenes-pw-123"); w.Code != http.StatusCreated {
		t.Fatalf("andere Adresse: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Nach einer Stunde ist eine Ersetzung wieder erlaubt.
	if !ersetzenErlaubt("fb-bremse@beispiel.de", time.Now().Add(ersetzungsAbstand+time.Second)) {
		t.Fatal("nach Ablauf der Stunde muss eine Ersetzung wieder erlaubt sein")
	}
}

// M35: bestaetigt sich das Konto zwischen erster Pruefung und Sperre, wird es
// nicht verschoben (zweite Pruefung unter der Sperre).
func TestReaper_ZweitePruefungUnterDerSperre(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-reaper-zwischen", "fb-zwischen@beispiel.de", jetzt.Add(-49*time.Hour), jetzt.Add(-25*time.Hour))
	reaperVorZweiterPruefung = func(id string) {
		if id != "u-reaper-zwischen" {
			return
		}
		b := time.Now().UTC()
		if _, err := s.UpdateUser(id, func(u *model.User) error { u.EmailVerifiedAt = &b; return nil }); err != nil {
			t.Fatal(err)
		}
	}
	t.Cleanup(func() { reaperVorZweiterPruefung = nil })
	if n := reapUnconfirmedAccounts(s, jetzt); n != 0 {
		t.Fatalf("inzwischen bestaetigtes Konto darf nicht verschoben werden, verschoben: %d", n)
	}
	if !s.UserExists("u-reaper-zwischen") || len(ablageEintraege(t, s)) != 0 {
		t.Fatal("Konto muss in users/ bleiben")
	}
}

// M42: der oeffentliche Passkey-Weg ersetzt eine leere unbestaetigte Anmeldung wirklich.
func TestVerdraengung_PasskeyRegistrierungErsetztWirklich(t *testing.T) {
	s := newTestStore(t)
	rpID, origin := "localhost", "http://localhost"
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-pk-vorweg", "fb-pk@beispiel.de", jetzt, jetzt.Add(time.Hour))

	bw := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(bw, httptest.NewRequest(http.MethodPost,
		"/api/auth/passkey/register/public/begin", strings.NewReader(`{"email":"fb-pk@beispiel.de"}`)))
	if bw.Code != http.StatusOK {
		t.Fatalf("begin: erwartet 200, bekommen %d: %s", bw.Code, bw.Body.String())
	}
	var begin struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	_ = json.Unmarshal(bw.Body.Bytes(), &begin)
	neuID := passkeyBeginKontoID(t, bw.Body.Bytes())
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	fw := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, "test-secret-32-chars-long-enough", config.Config{}).ServeHTTP(fw,
		httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/finish",
			bytes.NewReader(auth.MakeAttestationResponse(t, begin.PublicKey.Challenge))))
	if fw.Code != http.StatusCreated {
		t.Fatalf("finish: erwartet 201, bekommen %d: %s", fw.Code, fw.Body.String())
	}
	if s.UserExists("u-pk-vorweg") {
		t.Error("die unbestaetigte Anmeldung muss ersetzt (in die Ablage verschoben) sein")
	}
	if u, _ := s.LoadUser(neuID); u == nil || u.Email != "fb-pk@beispiel.de" || len(u.PasskeyCredentials) != 1 {
		t.Fatalf("neues Passkey-Konto erwartet: %+v", u)
	}
	if a := ablageEintraege(t, s); len(a) != 1 {
		t.Errorf("Ablage muss genau den verdraengten Ordner enthalten: %v", a)
	}
}
