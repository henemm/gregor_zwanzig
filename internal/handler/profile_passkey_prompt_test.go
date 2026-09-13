package handler

// TDD RED — Issue #2248 (Scheibe 3 von #2199): einmaliges, geraeteuebergreifend
// abweisbares Passkey-Angebot.
// Spec: docs/specs/modules/passkey_angebot_banner.md — AC-6.
//
// Zusicherung: ein `PUT /api/auth/profile`, der AUSSCHLIESSLICH
// `passkey_prompt_dismissed` mitbringt, setzt genau dieses Feld und laesst alle
// Nachbarfelder unberuehrt. Das ist die direkte Gegenprobe zur
// Datenverlust-Klasse BUG-DATALOSS-GR221 (Read-Modify-Write statt Replace).
//
// RED ist es, weil `passkey_prompt_dismissed` heute weder im Update-Decoder
// (auth.go:671) noch im Modell (internal/model/user.go) noch in der
// Profil-Antwort (toProfileResponse) existiert — der Schluessel wird still
// verschluckt und taucht nirgends wieder auf.
//
// Gemessen wird auf der PLATTE (mustLoadUser / rohe user.json), nicht in der
// Antwort: `email_verified_at` wird absichtlich NIE serialisiert
// (TestGetProfileHandlerEmailVerifiedField_AC20, profile_test.go:564), und
// `passkey_credentials` erscheint in der Antwort nur umgeformt als
// `passkeys`/`has_passkey`. Beide Felder sind in der Antwort also gar nicht
// pruefbar — die Zusicherung wirkt in der gespeicherten Datei.
//
// Keine Mocks: echter UpdateProfileHandler ueber einen echten HTTP-Request,
// echter Store auf t.TempDir(), echte user.json.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

const angebotFeld2248 = "passkey_prompt_dismissed"

// AC-6: PUT mit nur `passkey_prompt_dismissed` — Feld gesetzt, Nachbarfelder
// unveraendert.
//
// Mutation, die hier rot werden MUSS: den Handler auf Replace umbauen
// (`s.SaveUser(model.User{ID: userId, PasskeyPromptDismissed: true})`) statt
// das geladene Objekt zu aendern. Genau deshalb steht vor dem PUT eine
// Positivkontrolle, die jedes der sechs Nachbarfelder als BELEGT nachweist:
// "unveraendert" auf einem Leerwert waere trivial wahr und bewachte nichts.
func TestUpdateProfilePasskeyPromptDismissedPreservesNeighbours(t *testing.T) {
	s := newTestStore(t)
	const uid = "pia2248"

	verifiziertAm := time.Date(2026, 7, 1, 8, 30, 0, 0, time.UTC)
	angelegtAm := time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC)

	// GIVEN: ein Nutzerprofil mit durchweg BELEGTEN Nachbarfeldern.
	// tier bewusst "standard", nicht "free": model.EffectiveTier() macht aus
	// einem geleerten tier beim Lesen wieder "free" — ein Verlust waere mit
	// "free" als Startwert unsichtbar.
	mustSaveUser(t, s, model.User{
		ID:              uid,
		PasswordHash:    "$2a$04$abcdefghijklmnopqrstuv",
		DisplayName:     "Pia Pfadfinder",
		MailTo:          "pia2248@example.com",
		SmsTo:           "+49151TEST2248",
		Tier:            "standard",
		EmailVerifiedAt: &verifiziertAm,
		CreatedAt:       angelegtAm,
		PasskeyCredentials: []model.WebAuthnCredential{{
			ID:              []byte("passkey-id-2248"),
			PublicKey:       []byte("public-key-2248"),
			AttestationType: "none",
			Label:           "Handy von Pia",
			CreatedAt:       angelegtAm,
		}},
	})

	// Positivkontrolle: die sechs Nachbarfelder sind wirklich belegt, bevor
	// gemessen wird. Ohne diesen Block beweist der Vergleich unten nichts.
	vorher := mustLoadUser(t, s, uid)
	if vorher.DisplayName == "" || vorher.MailTo == "" || vorher.SmsTo == "" ||
		vorher.Tier == "" || vorher.EmailVerifiedAt == nil || len(vorher.PasskeyCredentials) == 0 {
		t.Fatalf("Positivkontrolle: Testaufbau hat nicht alle Nachbarfelder belegt — "+
			"display_name=%q mail_to=%q sms_to=%q tier=%q email_verified_at=%v passkeys=%d",
			vorher.DisplayName, vorher.MailTo, vorher.SmsTo, vorher.Tier,
			vorher.EmailVerifiedAt, len(vorher.PasskeyCredentials))
	}

	// WHEN: PUT mit AUSSCHLIESSLICH dem Angebot-Feld. Enge Nutzlast ist Teil
	// der Zusicherung (Spec, "Nutzlast-Disziplin"): kaeme ein abweichender
	// email/mail_to-Wert mit, setzte auth.go:706-715 email_verified_at zurueck
	// — nach #2271 (Login nur mit bestaetigter Adresse) eine Aussperr-Falle.
	body := `{"` + angebotFeld2248 + `":true}`
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, config.Config{}).ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("PUT /api/auth/profile: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	// THEN 1: das Feld ist gesetzt — in der Antwort UND in der gespeicherten
	// Datei. Nur die Datei traegt geraeteuebergreifend; die Antwort ist der
	// Weg, auf dem das Frontend es beim naechsten Laden erfaehrt.
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Antwort ist kein lesbares JSON: %v (%s)", err, w.Body.String())
	}
	if got, ok := resp[angebotFeld2248]; !ok || got != true {
		t.Errorf("AC-6: %s fehlt in der Profil-Antwort oder ist nicht true (%v, vorhanden=%v) — "+
			"ohne das Feld in der Antwort kann das Frontend die Abweisung beim naechsten "+
			"Laden nicht erkennen. Antwort: %s", angebotFeld2248, got, ok, w.Body.String())
	}

	pfad := filepath.Join(s.DataDir, "users", uid, "user.json")
	rohdaten, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("user.json nicht lesbar (%s): %v", pfad, err)
	}
	var gespeichert map[string]interface{}
	if err := json.Unmarshal(rohdaten, &gespeichert); err != nil {
		t.Fatalf("user.json ist kein lesbares JSON: %v (%s)", err, rohdaten)
	}
	if got, ok := gespeichert[angebotFeld2248]; !ok || got != true {
		t.Errorf("AC-6: %s steht nicht als true in user.json (%v, vorhanden=%v) — die Abweisung "+
			"ist damit nicht geraeteuebergreifend gemerkt, sondern verloren. Datei: %s",
			angebotFeld2248, got, ok, rohdaten)
	}

	// THEN 2: jedes Nachbarfeld einzeln auf Unveraendertheit.
	nachher := mustLoadUser(t, s, uid)

	if nachher.DisplayName != vorher.DisplayName {
		t.Errorf("AC-6: display_name veraendert: %q -> %q", vorher.DisplayName, nachher.DisplayName)
	}
	if nachher.MailTo != vorher.MailTo {
		t.Errorf("AC-6: mail_to veraendert: %q -> %q", vorher.MailTo, nachher.MailTo)
	}
	if nachher.SmsTo != vorher.SmsTo {
		t.Errorf("AC-6: sms_to veraendert: %q -> %q", vorher.SmsTo, nachher.SmsTo)
	}
	if nachher.Tier != vorher.Tier {
		t.Errorf("AC-6: tier veraendert: %q -> %q (ein geleertes tier liest sich als \"free\" "+
			"zurueck und wuerde den Verlust verdecken)", vorher.Tier, nachher.Tier)
	}
	if nachher.EmailVerifiedAt == nil {
		t.Errorf("AC-6: email_verified_at wurde geloescht (vorher %s) — nach #2271 sperrt das "+
			"den Nutzer aus seinem Konto aus", vorher.EmailVerifiedAt.Format(time.RFC3339))
	} else if !nachher.EmailVerifiedAt.Equal(*vorher.EmailVerifiedAt) {
		t.Errorf("AC-6: email_verified_at veraendert: %s -> %s",
			vorher.EmailVerifiedAt.Format(time.RFC3339), nachher.EmailVerifiedAt.Format(time.RFC3339))
	}

	if len(nachher.PasskeyCredentials) != len(vorher.PasskeyCredentials) {
		t.Fatalf("AC-6: passkey_credentials veraendert: %d -> %d Eintraege — ein verlorener "+
			"Passkey nimmt dem Nutzer seinen Anmeldeweg",
			len(vorher.PasskeyCredentials), len(nachher.PasskeyCredentials))
	}
	for i := range vorher.PasskeyCredentials {
		alt, neu := vorher.PasskeyCredentials[i], nachher.PasskeyCredentials[i]
		if string(neu.ID) != string(alt.ID) {
			t.Errorf("AC-6: passkey_credentials[%d].id veraendert: %q -> %q", i, alt.ID, neu.ID)
		}
		if string(neu.PublicKey) != string(alt.PublicKey) {
			t.Errorf("AC-6: passkey_credentials[%d].public_key veraendert", i)
		}
		if neu.Label != alt.Label {
			t.Errorf("AC-6: passkey_credentials[%d].label veraendert: %q -> %q", i, alt.Label, neu.Label)
		}
	}

	// THEN 3: auch der Passwort-Hash bleibt stehen — ohne ihn waere der
	// Nutzer nach seiner eigenen Abweisung ausgesperrt.
	if nachher.PasswordHash != vorher.PasswordHash {
		t.Errorf("AC-6: password_hash veraendert: %q -> %q", vorher.PasswordHash, nachher.PasswordHash)
	}
}
