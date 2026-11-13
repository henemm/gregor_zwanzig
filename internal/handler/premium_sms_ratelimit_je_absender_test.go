package handler

// Issue #2961 Welle 2 (ADR-0116, Spec AC-6): Bremse je Absendernummer.
// Ein einzelner Absender darf hoechstens drei Fehlversuche je gleitender Stunde
// verbrauchen; das globale Budget (30/h) bleibt fuer alle anderen frei. Gemessen
// am echten Lern-Handler mit echtem Store und zwei Konten.

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestPremiumSmsRatebremse_JeAbsenderSchontGlobalesBudget(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
	mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)
	mustSaveLinkCode(t, s, "premium-bert", linkCodeBert)

	uhr := time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)
	rl := NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget)
	rl.jetzt = func() time.Time { return uhr }
	h := PostPremiumSmsLearnHandler(s, rl)
	lerne := func(from, code string) *httptest.ResponseRecorder {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": from, "code": code}))
		return rr
	}

	// Absender A probiert fuenfmal falsch.
	for i := 0; i < 5; i++ {
		rr := lerne(garminFromCoded, linkCodeWrong)
		if i < DefaultPremiumSmsLinkCodeSenderBudget && rr.Code != http.StatusConflict {
			t.Fatalf("Versuch %d: erwartet 409 (falscher Code), bekam %d", i+1, rr.Code)
		}
		if i >= DefaultPremiumSmsLinkCodeSenderBudget && rr.Code != http.StatusTooManyRequests {
			t.Fatalf("Versuch %d: erwartet 429 (Absender-Bremse), bekam %d", i+1, rr.Code)
		}
	}
	if got := rl.FailedAttempts(); got != DefaultPremiumSmsLinkCodeSenderBudget {
		t.Fatalf("global duerfen nur %d Fehlversuche verbucht sein, bekam %d",
			DefaultPremiumSmsLinkCodeSenderBudget, got)
	}

	// Auch ein gueltiger Code aus derselben Nummer wird in dieser Stunde nicht
	// mehr verglichen.
	if rr := lerne(garminFromCoded, linkCodeAnna); rr.Code != http.StatusTooManyRequests {
		t.Fatalf("gesperrter Absender: erwartet 429, bekam %d: %s", rr.Code, rr.Body.String())
	}
	if got := mustLoadUser(t, s, "premium-anna").PremiumSmsReplyTo; got != "" {
		t.Fatalf("anna darf ueber den gesperrten Absender nichts lernen, hat %q", got)
	}

	// Ein anderer Absender verknuepft ungehindert.
	if rr := lerne(garminFromCodedB, linkCodeBert); rr.Code != http.StatusOK {
		t.Fatalf("anderer Absender: erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}
	if got := mustLoadUser(t, s, "premium-bert").PremiumSmsReplyTo; got != garminFromCodedB {
		t.Fatalf("bert: Rueckadresse %q, erwartet %q", got, garminFromCodedB)
	}

	// Nach Ablauf der Stunde darf Absender A wieder.
	uhr = uhr.Add(time.Hour + time.Second)
	if rr := lerne(garminFromCoded, linkCodeAnna); rr.Code != http.StatusOK {
		t.Fatalf("nach Fensterablauf: erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}
	if got := rl.SenderFailedAttempts(garminFromCoded); got != 0 {
		t.Fatalf("nach Fensterablauf erwartet 0 Absender-Fehlversuche, bekam %d", got)
	}
}

// Die globale Obergrenze ist 30 je Stunde, die Absender-Stufe 3 (ADR-0116).
func TestPremiumSmsRatebremse_Grenzwerte(t *testing.T) {
	if DefaultPremiumSmsLinkCodeBudget != 30 {
		t.Errorf("globale Obergrenze: erwartet 30, ist %d", DefaultPremiumSmsLinkCodeBudget)
	}
	if DefaultPremiumSmsLinkCodeSenderBudget != 3 {
		t.Errorf("Absender-Stufe: erwartet 3, ist %d", DefaultPremiumSmsLinkCodeSenderBudget)
	}
}

// F004 (ADR-0116): alle Schreibweisen derselben Nummer sind EIN Absender —
// fuer die gespeicherte Zuordnung und fuer die Absender-Bremse.
func TestPremiumSmsSchreibweisenSindEinAbsender(t *testing.T) {
	s := learnTestStore(t)
	frisch := time.Now().UTC().Add(-time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-anna", Tier: "premium",
		PremiumSmsReplyTo: "+4917000000091", PremiumSmsReplyAt: &frisch,
	})
	mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-bert", linkCodeBert)
	rl := NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget)
	h := PostPremiumSmsLearnHandler(s, rl)
	lerne := func(from, code string) *httptest.ResponseRecorder {
		rr := httptest.NewRecorder()
		body := map[string]any{"from": from}
		if code != "" {
			body["code"] = code
		}
		h(rr, newLearnRequest("127.0.0.1:54321", body))
		return rr
	}

	// Gespeicherte Zuordnung greift auch in anderer Schreibweise, ohne Code.
	if rr := lerne("004917000000091", ""); rr.Code != http.StatusOK {
		t.Fatalf("andere Schreibweise der gespeicherten Nummer: erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}

	// Drei Fehlversuche in drei Schreibweisen: danach ist der Absender gesperrt.
	for _, from := range []string{"+4917000000092", "4917000000092", "0049 170 000 000 92"} {
		if rr := lerne(from, linkCodeWrong); rr.Code != http.StatusConflict {
			t.Fatalf("%q: erwartet 409, bekam %d", from, rr.Code)
		}
	}
	if rr := lerne("+49-170-00000092", linkCodeBert); rr.Code != http.StatusTooManyRequests {
		t.Fatalf("vierte Schreibweise desselben Absenders: erwartet 429, bekam %d: %s", rr.Code, rr.Body.String())
	}
}

// F003: Konten ausserhalb des Premium-Tarifs sind beim Lernen keine
// Kandidaten — weder ueber den Code noch ueber eine gespeicherte Nummer.
func TestLearnNichtPremiumKontenSindKeineKandidaten(t *testing.T) {
	s := learnTestStore(t)
	frisch := time.Now().UTC().Add(-time.Hour)
	mustSaveUser(t, s, model.User{ID: "standard-anna", Tier: "standard"})
	mustSaveUser(t, s, model.User{
		ID: "free-bert", Tier: "free",
		PremiumSmsReplyTo: "4917000000093", PremiumSmsReplyAt: &frisch,
	})
	mustSaveLinkCode(t, s, "standard-anna", linkCodeAnna)
	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget))
	for _, body := range []map[string]any{
		{"from": "4917000000094", "code": linkCodeAnna},
		{"from": "4917000000093"},
	} {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", body))
		if rr.Code == http.StatusOK {
			t.Fatalf("Nicht-Premium-Konto zugeordnet (%v): %s", body, rr.Body.String())
		}
	}
	if got := mustLoadUser(t, s, "standard-anna").PremiumSmsReplyTo; got != "" {
		t.Errorf("standard-anna darf nichts lernen, hat %q", got)
	}
}
