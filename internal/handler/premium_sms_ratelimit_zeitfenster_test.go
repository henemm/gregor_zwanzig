package handler

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-21):
// die Ratebremse fuer Verknuepfungs-Codes zaehlt Fehlversuche in einem
// gleitenden Stundenfenster statt "bis zum Neustart", warnt bei Erschoepfung
// im Log und laesst nach Ablauf des Fensters den gueltigen Code wieder durch.
// Gemessen am echten Lern-Handler mit Testuhr.

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestPremiumSmsRatebremse_GleitendesStundenfenster(t *testing.T) {
	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })

	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-anna", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)

	uhr := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	rl := NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget)
	rl.jetzt = func() time.Time { return uhr }
	h := PostPremiumSmsLearnHandler(s, rl)

	falsch := func() int {
		rr := httptest.NewRecorder()
		h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": "XXZZZ999"}))
		return rr.Code
	}
	for i := 0; i < DefaultPremiumSmsLinkCodeBudget; i++ {
		falsch()
		uhr = uhr.Add(time.Minute)
	}
	if got := rl.FailedAttempts(); got != DefaultPremiumSmsLinkCodeBudget {
		t.Fatalf("Messaufbau: %d Fehlversuche, erwartet %d", got, DefaultPremiumSmsLinkCodeBudget)
	}

	// Erschoepft: auch der gueltige Code wird nicht verglichen (429).
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": linkCodeAnna}))
	if rr.Code != http.StatusTooManyRequests {
		t.Fatalf("erschoepfte Bremse: erwartet 429, bekommen %d: %s", rr.Code, rr.Body.String())
	}
	if !strings.Contains(logBuf.String(), "Ratebremse") {
		t.Fatalf("keine Warnung bei Erschoepfung im Log: %q", logBuf.String())
	}

	// Eine Stunde nach dem ersten Fehlversuch ist wieder Platz.
	uhr = time.Date(2026, 11, 12, 11, 0, 1, 0, time.UTC)
	rr = httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": linkCodeAnna}))
	if rr.Code != http.StatusOK {
		t.Fatalf("nach Ablauf des Fensters muss der gueltige Code verknuepfen, bekommen %d: %s", rr.Code, rr.Body.String())
	}
	if got := mustLoadUser(t, s, "premium-anna").PremiumSmsReplyTo; got != garminFromCoded {
		t.Fatalf("Rueckadresse %q, erwartet %q", got, garminFromCoded)
	}
}
