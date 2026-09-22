package handler

// TDD RED — Issue #2147 Scheibe B2: "Erneut senden" und Staging-Token-Weg
// adressieren die AUSSTEHENDE Adresse.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md — AC-11 (beide
// Varianten), §3 StagingVerificationTokenHandler. JSON-Vertrag und Helfer:
// profile_email_pending_test.go.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func ausstehendResend(s *store.Store, cfg config.Config, uid string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email/resend",
		strings.NewReader(fmt.Sprintf(`{"username":%q}`, uid)))
	w := httptest.NewRecorder()
	ResendVerificationHandler(s, cfg, weitMailLimiter).ServeHTTP(w, req)
	return w
}

// AC-11 (mit ausstehender Aenderung): bestaetigtes Konto mit Pending ruft
// "Erneut senden" -> genau EINE neue Mail an die AUSSTEHENDE Adresse, keine an
// die wirksame; es entsteht ein NEUES Token, gebunden an die ausstehende
// Adresse; der Link aus der Resend-Mail wirkt.
func TestAC11_ResendBeiAusstehenderAenderungGehtAnAusstehendeAdresse(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "resend-ac11-b2"
	const email = "resend-ac11-email-b2@beispiel.de"
	const alt = "resend-ac11-alt-b2@beispiel.de"
	const neu = "resend-ac11-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, alt)

	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("AC-11: Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	mustMail(t, versand, neu) // erste Mail aus dem Profil-Update abholen

	zwischen := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(zwischen, "mail_to"); got != alt {
		t.Errorf("AC-11 Ausgangslage: wirksame mail_to muss %q bleiben, ist %q — sonst ist "+
			"'ausstehend' und 'wirksam' nicht unterscheidbar", alt, got)
	}
	if ausstehendZeitstempel(t, "AC-11", zwischen) == nil {
		t.Errorf("AC-11 Ausgangslage: das Konto muss bestaetigt bleiben")
	}
	if got := ausstehendStr(zwischen, "pending_contact_address"); got != neu {
		t.Errorf("AC-11 Ausgangslage: pending_contact_address muss %q sein, ist %q", neu, got)
	}
	tokVorher, _ := ausstehendTokenMap(t, s, uid)

	w := ausstehendResend(s, cfg, uid)
	if w.Code != http.StatusOK || strings.TrimSpace(w.Body.String()) != `{"status":"ok"}` {
		t.Fatalf("AC-11: Resend erwartet 200 {\"status\":\"ok\"}, bekommen %d: %s", w.Code, w.Body.String())
	}
	tokNachher, da := ausstehendTokenMap(t, s, uid)
	if !da {
		t.Fatalf("AC-11: nach dem Resend muss ein Token existieren")
	}
	if ausstehendStr(tokVorher, "token_hash") == ausstehendStr(tokNachher, "token_hash") {
		t.Errorf("AC-11: der Resend muss ein NEUES Token ausstellen (token_hash unveraendert)")
	}
	if got := ausstehendStr(tokNachher, "address"); got != neu {
		t.Errorf("AC-11: das neue Token muss an die ausstehende Adresse %q gebunden sein, ist %q", neu, got)
	}

	m, andere := ausstehendWarteAufMail(t, versand, neu)
	for _, o := range andere {
		if o.to == alt || o.to == email {
			t.Errorf("AC-11: Resend-Mail ging an die wirksame Adresse %q statt an die ausstehende", o.to)
		}
	}
	ausstehendKeineWeitereMail(t, versand, "AC-11", neu, alt, email)

	if ew := ausstehendEinloesen(s, uid, ausstehendToken(t, m)); ew.Code != http.StatusOK {
		t.Errorf("AC-11: der Link aus der Resend-Mail muss wirken (200), bekommen %d: %s", ew.Code, ew.Body.String())
	}
}

// AC-11 (ohne ausstehende Aenderung) — Regressionswächter B2: heute grün.
// Bestaetigtes Konto ohne Pending ruft "Erneut senden" -> kein Token, keine
// Mail; Positivkontrolle auf demselben Kanal.
func TestAC11_ResendOhneAusstehendeAenderungBeiBestaetigtemKontoTutNichts(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "resend-still-ac11-b2"
	const email = "resend-still-ac11-email-b2@beispiel.de"
	const mt = "resend-still-ac11-mt-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, mt)
	vorher := rohesKonto(t, s, uid)

	w := ausstehendResend(s, cfg, uid)
	if w.Code != http.StatusOK || strings.TrimSpace(w.Body.String()) != `{"status":"ok"}` {
		t.Fatalf("AC-11b: Resend erwartet 200 {\"status\":\"ok\"}, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("AC-11b: fuer ein bestaetigtes Konto ohne ausstehende Aenderung darf kein Token entstehen")
	}
	if string(vorher) != string(rohesKonto(t, s, uid)) {
		t.Errorf("AC-11b: user.json darf sich nicht aendern")
	}
	ausstehendKeinVersandAn(t, s, cfg, versand, "AC-11b", email, mt)
}

// Spec §3: StagingVerificationTokenHandler adressiert bei ausstehender
// Aenderung die AUSSTEHENDE Adresse — das gelieferte Token ist an sie
// gebunden, und sein Einloesen macht sie wirksam (so wird der Ablauf auf
// Staging per /e2e-verify gemessen).
func TestStagingTokenwegAdressiertAusstehendeAdresse(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "staging-pend-b2"
	const alt = "staging-pend-alt-b2@beispiel.de"
	const neu = "staging-pend-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, "staging-pend-email-b2@beispiel.de", alt)

	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("Staging-Token: Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	mustMail(t, versand, neu)

	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email/staging-token",
		strings.NewReader(fmt.Sprintf(`{"username":%q}`, uid)))
	w := httptest.NewRecorder()
	StagingVerificationTokenHandler(s).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("Staging-Token: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var antwort struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &antwort); err != nil || antwort.Token == "" {
		t.Fatalf("Staging-Token: Antwort ohne Token: %q", w.Body.String())
	}

	tok, da := ausstehendTokenMap(t, s, uid)
	if !da {
		t.Fatalf("Staging-Token: email_verification.json fehlt")
	}
	if got := ausstehendStr(tok, "address"); got != neu {
		t.Errorf("Staging-Token: das Token muss an die ausstehende Adresse %q gebunden sein, ist %q", neu, got)
	}
	if got := ausstehendStr(ausstehendKontoMap(t, s, uid), "mail_to"); got != alt {
		t.Errorf("Staging-Token: vor dem Einloesen muss mail_to %q bleiben, ist %q", alt, got)
	}

	if ew := ausstehendEinloesen(s, uid, antwort.Token); ew.Code != http.StatusOK {
		t.Fatalf("Staging-Token: Einloesen erwartet 200, bekommen %d: %s", ew.Code, ew.Body.String())
	}
	danach := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(danach, "mail_to"); got != neu {
		t.Errorf("Staging-Token: nach dem Einloesen muss mail_to %q sein, ist %q", neu, got)
	}
	ausstehendKeinePendingFelder(t, "Staging-Token (nach Einloesen)", danach)
}
