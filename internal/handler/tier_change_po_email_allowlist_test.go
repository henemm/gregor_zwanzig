package handler

// TDD RED — Issue #2147 Scheibe B2, AC-16 (Handler-Pfad): ein Tier-Antrag an
// cfg.PoEmail wird vom Resend-Empfaenger-Guard NICHT blockiert, auch wenn die
// PO-Adresse in keinem Nutzerprofil steht.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §5, AC-16.
//
// Beobachtbarkeit: RequestTierChangeHandler versendet asynchron und meldet
// das Ergebnis ausschliesslich ueber log ("tier-change: mail send failed ...").
// Unter go test sperrt resendBlocked (#1122) JEDEN Resend-Host — der Versand
// scheitert also in jedem Fall, ohne Netz. Unterschieden wird, WELCHE Linie
// ihn stoppt: heute der Empfaenger-Guard ("nicht in der Resend-Allowlist"),
// nach der Umsetzung erst die Host-Sperre ("unter go test gesperrt (#1122)").
// Kein Dial, kein Kontingentverbrauch.
//
// Konfiguration wie in Produktion: cfg.PoEmail und GZ_PO_EMAIL tragen
// denselben Wert (config.Load liest cfg.PoEmail aus GZ_PO_EMAIL); /50 ist
// damit frei, den Guard ueber die Umgebung ODER ueber den Handler zu
// verdrahten. Zwei-Nutzer-Pflicht: zwei bestaetigte Konten mit eigenen
// Adressen, keines traegt die PO-Adresse.

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

type syncLogBuffer struct {
	mu sync.Mutex
	b  strings.Builder
}

func (w *syncLogBuffer) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.b.Write(p)
}

func (w *syncLogBuffer) String() string {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.b.String()
}

func TestAC16_TierAntragAnBetreiberAdresseScheitertNichtAmEmpfaengerGuard(t *testing.T) {
	s := newTestStore(t)
	verified := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	if err := s.SaveUser(model.User{
		ID: "wanderer-antrag", Tier: "free",
		MailTo: "wanderer-antrag@gmail.com", EmailVerifiedAt: &verified,
	}); err != nil {
		t.Fatalf("SaveUser wanderer-antrag: %v", err)
	}
	if err := s.SaveUser(model.User{
		ID: "wanderer-zweit", Tier: "free",
		Email: "wanderer-zweit-login@gmail.com", MailTo: "wanderer-zweit@gmail.com", EmailVerifiedAt: &verified,
	}); err != nil {
		t.Fatalf("SaveUser wanderer-zweit: %v", err)
	}

	const poAdresse = "betreiber-antraege@gmail.com"
	t.Setenv("GZ_DATA_DIR", s.DataDir)
	t.Setenv("GZ_PO_EMAIL", poAdresse)
	cfg := config.Config{
		PoEmail:  poAdresse,
		SMTPHost: "smtp.resend-fixture.test",
		SMTPPort: 587,
		SMTPUser: "resend",
		SMTPPass: "ungueltig",
		SMTPFrom: "gregor_zwanzig@henemm.com",
	}

	mitschnitt := &syncLogBuffer{}
	log.SetOutput(mitschnitt)
	defer log.SetOutput(os.Stderr)

	h := RequestTierChangeHandler(s, cfg)
	body, _ := json.Marshal(map[string]string{"requested_tier": "standard"})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "wanderer-antrag"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("AC-16 Vorbedingung: Tier-Antrag erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	var zeile string
	frist := time.Now().Add(5 * time.Second)
	for time.Now().Before(frist) {
		for _, z := range strings.Split(mitschnitt.String(), "\n") {
			if strings.Contains(z, "tier-change: mail send") {
				zeile = z
			}
		}
		if zeile != "" {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	if zeile == "" {
		t.Fatalf("AC-16: kein Versand-Ergebnis des Tier-Antrags im Log innerhalb 5 s — Messung unmoeglich. Log:\n%s",
			mitschnitt.String())
	}
	if strings.Contains(zeile, "Resend-Allowlist") {
		t.Errorf("AC-16: Tier-Antrag an die konfigurierte Betreiber-Adresse wurde vom Empfaenger-Guard "+
			"(Resend-Allowlist) blockiert, obwohl GZ_PO_EMAIL/cfg.PoEmail sie benennt:\n%s", zeile)
	}
	if !strings.Contains(zeile, "#1122") {
		t.Errorf("AC-16: erwartet, dass der Versand erst an der go-test-Host-Sperre (#1122) endet "+
			"(Empfaenger-Guard passiert), Log-Zeile war:\n%s", zeile)
	}
}
