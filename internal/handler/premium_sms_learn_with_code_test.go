package handler

// TDD RED — Issue #2154 Scheibe A, Artefakt 2 (neue Flaechen, Lern-Endpoint).
// Spec: docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md v1.0
//
// Uebersetzungsfehler ist hier der ERWARTETE RED-Beleg: die Symbole
// NewPremiumSmsRateLimiter, PostPremiumSmsLearnHandler(s, rl),
// model.PremiumSmsLinkCode und store.SaveLinkCode existieren noch nicht.
//
// Von den Tests geforderte, neue Produktiv-Signaturen (Spec nennt die Dateien,
// nicht die Signaturen — s. Bericht "Abweichungen"):
//   PostPremiumSmsLearnHandler(s *store.Store, rl *PremiumSmsRateLimiter) http.HandlerFunc
//   NewPremiumSmsRateLimiter(budget int) *PremiumSmsRateLimiter
//   (*PremiumSmsRateLimiter).FailedAttempts() int
// Der Budget-Parameter ist Pflicht: mit dem Produktionsbudget kostet das
// Erschoepfen der Bremse je Test Sekunden an bcrypt-Rechenzeit.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	garminFromCoded  = "4917000000005"
	garminFromCodedB = "4917000000006"

	linkCodeAnna  = "AB3CD9F"
	linkCodeBert  = "XY7ZQ4M"
	linkCodeWrong = "ZZ9ZZ9Z"
)

// ---------------------------------------------------------------------------
// AC-2: der Code entscheidet, welches Konto die Nummer bekommt.
//
// Geprueft wird in BEIDE Richtungen: jedes Konto traegt die zu seinem Code
// gehoerende Nummer UND die des anderen Kontos steht nirgends in seiner
// user.json. Ohne die Negativ-Haelfte bliebe eine Umsetzung unentdeckt, die
// beide Nummern auf denselben Nutzer schreibt.
// ---------------------------------------------------------------------------

func TestLearnMatchesCodeToCorrectAccountAmongTwoUsers(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
	mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)
	mustSaveLinkCode(t, s, "premium-bert", linkCodeBert)

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))

	for _, call := range []struct {
		userID string
		from   string
		code   string
	}{
		{"premium-anna", garminFromCodedB, linkCodeAnna},
		{"premium-bert", garminFromCoded, linkCodeBert},
	} {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": call.from, "code": call.code}))
		if rr.Code != http.StatusOK {
			t.Fatalf("AC-2: Lernaufruf mit gueltigem Code fuer %s erwartet 200, bekam %d, body=%s",
				call.userID, rr.Code, rr.Body.String())
		}
	}

	anna := mustLoadUser(t, s, "premium-anna")
	bert := mustLoadUser(t, s, "premium-bert")
	if anna.PremiumSmsReplyTo != garminFromCodedB {
		t.Errorf("AC-2: Anna traegt den Code %q, erwartet Rueckadresse %q, bekam %q",
			linkCodeAnna, garminFromCodedB, anna.PremiumSmsReplyTo)
	}
	if bert.PremiumSmsReplyTo != garminFromCoded {
		t.Errorf("AC-2: Bert traegt den Code %q, erwartet Rueckadresse %q, bekam %q",
			linkCodeBert, garminFromCoded, bert.PremiumSmsReplyTo)
	}
	if anna.PremiumSmsReplyTo == bert.PremiumSmsReplyTo {
		t.Errorf("AC-2: beide Konten duerfen NIE dieselbe Rueckadresse tragen (%q)", anna.PremiumSmsReplyTo)
	}

	// Negativ-Haelfte: die fremde Nummer darf in der ganzen Datei nicht
	// vorkommen — nicht nur nicht im Feld PremiumSmsReplyTo.
	for _, c := range []struct{ userID, fremd string }{
		{"premium-anna", garminFromCoded},
		{"premium-bert", garminFromCodedB},
	} {
		raw := readUserJSON2154(t, s, c.userID)
		if bytes.Contains(raw, []byte(c.fremd)) {
			t.Errorf("AC-2: die Nummer des ANDEREN Kontos (%s) steht in der user.json von %s: %s",
				c.fremd, c.userID, raw)
		}
	}
}

// ---------------------------------------------------------------------------
// AC-4 (Annahme-Haelfte): dieselbe Nachricht, die ohne Code am veralteten
// Treffer scheitert (Artefakt 1), wird MIT dem Code des Nutzers zugeordnet.
// ---------------------------------------------------------------------------

func TestLearnAcceptsCodeForStaleStoredMatch(t *testing.T) {
	s := learnTestStore(t)
	staleAt := time.Now().UTC().Add(-(model.PremiumSmsReplyTTL + 24*time.Hour))
	mustSaveUser(t, s, model.User{
		ID: "premium-anna", Tier: "premium",
		PremiumSmsReplyTo: garminFromCoded, PremiumSmsReplyAt: &staleAt,
	})
	mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": linkCodeAnna}))

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-4: mit gueltigem Code muss der veraltete Treffer neu verknuepft werden, "+
			"bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	anna := mustLoadUser(t, s, "premium-anna")
	if anna.PremiumSmsReplyTo != garminFromCoded {
		t.Errorf("AC-4: erwartet Rueckadresse %q, bekam %q", garminFromCoded, anna.PremiumSmsReplyTo)
	}
	if anna.PremiumSmsReplyAt == nil || !anna.PremiumSmsReplyAt.After(staleAt) {
		t.Errorf("AC-4: der Zeitstempel muss auffrischen (alt=%v, neu=%v)", staleAt, anna.PremiumSmsReplyAt)
	}
}

// ---------------------------------------------------------------------------
// AC-7: erschoepftes Budget -> 429, OHNE Hash-Vergleich.
//
// Messung der Trennung (s. Bericht): "kein Vergleich" ist von aussen nicht
// direkt beobachtbar. Zwei Teilmessungen zusammen kommen dem am naechsten:
//
//  a) mit dem TATSAECHLICH KORREKTEN Code -> trotzdem 429 und keine Schreibung.
//     Belegt: ein etwaiges Vergleichsergebnis wird nicht verwertet.
//  b) mit einem FALSCHEN Code -> der Fehlversuchszaehler bewegt sich NICHT
//     mehr. Belegt: der Pfad, der einen erfolglosen Vergleich verbucht
//     (Spec Schritt 6, "Zaehler +1"), wird gar nicht erst betreten.
//
// Was keine der beiden beweist: dass bcrypt.CompareHashAndPassword nicht doch
// aufgerufen wurde. Das koennte nur ein an der Vergleichsstelle selbst
// hochgezaehlter Zaehler zeigen — der wuerde die Struktur des Produktivcodes
// vom Test her diktieren und ist deshalb bewusst nicht gefordert.
// ---------------------------------------------------------------------------

func TestLearnExhaustedBudgetSkipsHashComparison(t *testing.T) {
	const budget = 2 // erlaubte erfolglose Vergleiche, danach 429

	// setup liefert eine Bremse mit bereits erschoepftem Budget, den
	// Lernaufruf und einen Schnappschuss-Leser fuer die user.json.
	setup := func(t *testing.T) (*PremiumSmsRateLimiter, func(string) *httptest.ResponseRecorder, func() []byte) {
		t.Helper()
		s := learnTestStore(t)
		mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium", Email: "anna@example.invalid"})
		mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)
		rl := NewPremiumSmsRateLimiter(budget)
		h := PostPremiumSmsLearnHandler(s, rl)
		learn := func(code string) *httptest.ResponseRecorder {
			rr := httptest.NewRecorder()
			h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": code}))
			return rr
		}
		for i := 0; i < budget; i++ {
			if rr := learn(linkCodeWrong); rr.Code == http.StatusOK {
				t.Fatalf("Vorbedingung: falscher Code darf nie 200 liefern (Versuch %d), body=%s",
					i+1, rr.Body.String())
			}
		}
		if got := rl.FailedAttempts(); got != budget {
			t.Fatalf("Vorbedingung: nach %d falschen Codes erwartet FailedAttempts()=%d, bekam %d",
				budget, budget, got)
		}
		return rl, learn, func() []byte { return readUserJSON2154(t, s, "premium-anna") }
	}

	t.Run("korrekter Code wird weder verwertet noch geschrieben", func(t *testing.T) {
		_, learn, snapshot := setup(t)
		before := snapshot()
		rr := learn(linkCodeAnna)
		if rr.Code != http.StatusTooManyRequests {
			t.Errorf("AC-7: erwartet 429 auch fuer den korrekten Code, bekam %d, body=%s",
				rr.Code, rr.Body.String())
		}
		if after := snapshot(); !bytes.Equal(before, after) {
			t.Errorf("AC-7: bei erschoepftem Budget darf NICHTS geschrieben werden.\nvorher:  %s\nnachher: %s",
				before, after)
		}
	})

	t.Run("falscher Code erhoeht den Zaehler nicht mehr", func(t *testing.T) {
		rl, learn, _ := setup(t)
		learn(linkCodeWrong)
		if got := rl.FailedAttempts(); got != budget {
			t.Errorf("AC-7: bei erschoepftem Budget wird kein erfolgloser Vergleich mehr verbucht — "+
				"erwartet FailedAttempts()=%d (unveraendert), bekam %d", budget, got)
		}
	})
}

// ---------------------------------------------------------------------------
// AC-8: Trockenlauf beruehrt die Ratebremse nie.
// ---------------------------------------------------------------------------

func TestLearnDryRunNeverIncrementsRateLimit(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)

	rl := NewPremiumSmsRateLimiter(5)
	h := PostPremiumSmsLearnHandler(s, rl)

	for i := 0; i < 3; i++ {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{
			"from": garminFromCoded, "code": linkCodeWrong, "dry_run": true,
		}))
		if rr.Code != http.StatusOK {
			t.Fatalf("AC-8: Trockenlauf meldet nie hart ab (Versuch %d), bekam %d, body=%s",
				i+1, rr.Code, rr.Body.String())
		}
		if got := rl.FailedAttempts(); got != 0 {
			t.Fatalf("AC-8: nach %d Trockenlaeufen mit falschem Code erwartet FailedAttempts()=0, bekam %d",
				i+1, got)
		}
	}

	anna := mustLoadUser(t, s, "premium-anna")
	if anna.PremiumSmsReplyTo != "" {
		t.Errorf("AC-8: der Trockenlauf darf nie schreiben, hat aber %q gesetzt", anna.PremiumSmsReplyTo)
	}
}

// ---------------------------------------------------------------------------
// Spec Schritt 6, Mehrdeutigkeits-Haelfte: ein Code, der auf MEHRERE
// Premium-Kandidaten passt, wird abgelehnt — er faellt nicht dem erstbesten
// Kandidaten zu.
//
// Die Positiv-Kontrolle im selben Rumpf ist Pflicht, nicht Zierde: passte der
// Klartext-Code wegen einer verrotteten Fixture auf KEINEN gespeicherten Hash,
// waere die Antwort dieselbe (409 link_code_invalid) — die Mehrdeutigkeits-
// Haelfte bestuende dann im Vakuum und wuerde nichts mehr bewachen.
// ---------------------------------------------------------------------------

func TestLearnRejectsAmbiguousCodeMatch(t *testing.T) {
	// codeHolders bestimmt, welche der beiden Premium-Nutzer DENSELBEN Code
	// tragen — so entsteht die Mehrdeutigkeit deterministisch, ohne auf eine
	// bcrypt-Kollision zu hoffen. Beide starten ohne gespeicherte Rueckadresse,
	// sonst entschiede Schritt 4 (frischer Treffer) statt der Code-Vergleich.
	setup := func(t *testing.T, codeHolders ...string) (*store.Store, *PremiumSmsRateLimiter, func() *httptest.ResponseRecorder) {
		t.Helper()
		s := learnTestStore(t)
		mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
		mustSaveUser(t, s, model.User{ID: "premium-bert", Tier: "premium"})
		for _, id := range codeHolders {
			mustSaveLinkCode(t, s, id, linkCodeAnna)
		}
		rl := NewPremiumSmsRateLimiter(5)
		h := PostPremiumSmsLearnHandler(s, rl)
		return s, rl, func() *httptest.ResponseRecorder {
			rr := httptest.NewRecorder()
			h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{
				"from": garminFromCoded, "code": linkCodeAnna,
			}))
			return rr
		}
	}

	t.Run("Positiv-Kontrolle: nur ein Traeger, der Code trifft wirklich", func(t *testing.T) {
		s, _, learn := setup(t, "premium-anna")
		if rr := learn(); rr.Code != http.StatusOK {
			t.Fatalf("Positiv-Kontrolle: eindeutiger Treffer erwartet 200, bekam %d, body=%s",
				rr.Code, rr.Body.String())
		}
		if got := mustLoadUser(t, s, "premium-anna").PremiumSmsReplyTo; got != garminFromCoded {
			t.Errorf("Positiv-Kontrolle: erwartet Rueckadresse %q bei premium-anna, bekam %q",
				garminFromCoded, got)
		}
	})

	t.Run("mehrdeutiger Treffer wird abgelehnt, kein Konto wird beschrieben", func(t *testing.T) {
		s, rl, learn := setup(t, "premium-anna", "premium-bert")
		userIDs := []string{"premium-anna", "premium-bert"}
		before := map[string][]byte{}
		for _, id := range userIDs {
			before[id] = readUserJSON2154(t, s, id)
		}

		rr := learn()
		if rr.Code != http.StatusConflict {
			t.Errorf("Schritt 6: mehrdeutiger Code erwartet 409, bekam %d, body=%s",
				rr.Code, rr.Body.String())
		}
		var body map[string]string
		if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
			t.Fatalf("Antwort nicht als JSON lesbar: %v (%s)", err, rr.Body.String())
		}
		if body["reason"] != reasonLinkCodeInvalid {
			t.Errorf("Schritt 6: erwartet Grund %q, bekam %q", reasonLinkCodeInvalid, body["reason"])
		}

		// BEIDE Konten pruefen: bliebe eines ungeprueft, verbliebe "der erste
		// wird genommen" unentdeckt.
		for _, id := range userIDs {
			if got := mustLoadUser(t, s, id).PremiumSmsReplyTo; got != "" {
				t.Errorf("Schritt 6: %s darf bei Mehrdeutigkeit keine Rueckadresse bekommen, hat aber %q",
					id, got)
			}
			if after := readUserJSON2154(t, s, id); !bytes.Equal(before[id], after) {
				t.Errorf("Schritt 6: user.json von %s wurde veraendert.\nvorher:  %s\nnachher: %s",
					id, before[id], after)
			}
		}

		if got := rl.FailedAttempts(); got != 1 {
			t.Errorf("Schritt 6: der mehrdeutige Treffer zaehlt als Fehlversuch — "+
				"erwartet FailedAttempts()=1, bekam %d", got)
		}
	})
}
