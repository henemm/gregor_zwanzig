package router

// Issue #2404, Adversary-Befund F001: die WIRK-Stelle der geteilten
// Mengenbremse ist die Verdrahtung in router.go — ResendVerificationHandler
// und UpdateProfileHandler muessen DIESELBE *handler.MailFloodLimiter-Instanz
// bekommen, sonst gilt das Adress-Limit nicht endpointuebergreifend (Spec
// docs/specs/bugfix/profile_mail_ratelimit.md, "Implementation Details" §4;
// Grundlage fuer AC-2, AC-4 und AC-8).
//
// internal/handler/profile_mail_ratelimit_test.go prueft die ACs mit einer
// selbst gebauten Limiter-Instanz, die den Handlern von Hand durchgereicht
// wird — diese Tests bleiben restlos gruen, wenn router.go dem Resend-Pfad
// eine ZWEITE, separate Instanz gaebe. Folge einer solchen Regression: das
// Adress-Kontingent liesse sich doppelt ausschoepfen, der Cross-Account-
// Flood-Schutz waere still halbiert.
//
// Gemessen wird deshalb ueber echte HTTP-Requests gegen den ECHTEN
// Produktions-Router. Beobachtungspunkt ist der Profil-Pfad: nur er meldet die
// Ablehnung sichtbar (429), der Resend-Pfad antwortet zur Vermeidung von
// Konto-Enumeration immer 200. Verbrauchen Resend-Aufrufe Kontingent, das dem
// Profil-Pfad danach fehlt, ist die Instanz geteilt.

import (
	"fmt"
	"net/http"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// newFlutTestRouter baut den echten Produktions-Router wie
// newBriefingTestRouter, leert aber beide SMTP-Hosts: dispatchVerificationMail
// kehrt dann vor der Versand-Goroutine um (auth.go:1288/1292), der Test
// braucht kein Netz. Die Kontingent-Buchung bleibt unberuehrt — beide
// Limiter-Pruefungen stehen VOR dem Versand.
func newFlutTestRouter(t *testing.T) (http.Handler, *store.Store, string) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.SMTPHost = ""
	cfg.GoogleSMTPHost = ""

	s := store.New(cfg.DataDir, cfg.UserID)

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})

	return r, s, cfg.SessionSecret
}

func TestMailFloodLimiterIstZwischenProfilUndResendGeteilt(t *testing.T) {
	r, s, secret := newFlutTestRouter(t)

	const uid = "flutwire"
	const adresseX = "flutwire-x@beispiel.de"
	const adresseY = "flutwire-y@beispiel.de"
	bestaetigt := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	if err := s.SaveUser(model.User{
		ID: uid, Email: "flutwire-email@beispiel.de", MailTo: "flutwire-alt@beispiel.de",
		DisplayName: "Konto flutwire", EmailVerifiedAt: &bestaetigt, CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := s.AddSession(uid, sessionIDFor(uid)); err != nil {
		t.Fatalf("AddSession: %v", err)
	}
	cookie := sessionCookieFor(uid, secret)

	profilAufX := func(nr int) int {
		t.Helper()
		w := doBriefingRequest(t, r, http.MethodPut, "/api/auth/profile",
			[]byte(fmt.Sprintf(`{"mail_to":%q}`, adresseX)), cookie)
		if w.Code == http.StatusNotFound || w.Code == http.StatusMethodNotAllowed {
			t.Fatalf("VERDRAHTUNG FEHLT: PUT /api/auth/profile antwortet %d", w.Code)
		}
		if nr > 0 && w.Code != http.StatusOK {
			t.Fatalf("Saettigung: Profil-Versuch %d auf X erwartet 200, bekommen %d: %s",
				nr, w.Code, w.Body.String())
		}
		return w.Code
	}

	// 1 Token auf Adresse X: legt zugleich die ausstehende Aenderung an, ohne
	// die der Resend-Pfad gar nicht erst bis zum Adress-Bucket kaeme.
	profilAufX(1)

	// 3 Resend-Aufrufe — bewusst unter dem IP-Limit von 5/h
	// (resendVerifyLimiter in router.go): eine von der Middleware abgewiesene
	// Anfrage erreicht den Handler nie und bucht kein Token, das faelschte den
	// Befund.
	for i := 1; i <= 3; i++ {
		w := doBriefingRequest(t, r, http.MethodPost, "/api/auth/verify-email/resend",
			[]byte(fmt.Sprintf(`{"username":%q}`, uid)), cookie)
		if w.Code != http.StatusOK || w.Body.String() != `{"status":"ok"}` {
			t.Fatalf("Resend %d erwartet 200 {\"status\":\"ok\"}, bekommen %d: %s — der Aufruf hat den "+
				"Handler nicht erreicht (IP-Bremse, fehlende Route), der Messaufbau traegt nicht",
				i, w.Code, w.Body.String())
		}
	}

	// 6 weitere Profil-Versuche: bei GETEILTER Instanz steht der Adress-Bucket
	// von X danach auf 1+3+6 = 10/10.
	for i := 2; i <= 7; i++ {
		profilAufX(i)
	}

	// Der Diskriminator. Geteilt: 11. Buchung auf X -> 429. Zwei getrennte
	// Instanzen: der Profil-Limiter zaehlte erst 8 -> 200.
	code := profilAufX(0)
	if code != http.StatusTooManyRequests {
		t.Fatalf("F001: der 8. Profil-Wechsel auf %s erwartet 429, bekommen %d — router.go reicht "+
			"ResendVerificationHandler und UpdateProfileHandler NICHT dieselbe MailFloodLimiter-Instanz "+
			"durch; die drei Resend-Aufrufe haben kein Kontingent der Adresse verbraucht",
			adresseX, code)
	}

	// Kontrollmarke: der 429 haengt an der Adresse, nicht am erschoepften
	// User-Bucket (der steht bei 7/10). Ohne sie waere der Test auch dann
	// gruen, wenn die Ablehnung aus einer ganz anderen Ecke kaeme.
	wY := doBriefingRequest(t, r, http.MethodPut, "/api/auth/profile",
		[]byte(fmt.Sprintf(`{"mail_to":%q}`, adresseY)), cookie)
	if wY.Code != http.StatusOK {
		t.Fatalf("Messaufbau untauglich: der Wechsel auf die frische Adresse %s erwartet 200, bekommen %d: %s — "+
			"der 429 oben kam nicht vom Adress-Bucket", adresseY, wY.Code, wY.Body.String())
	}
}
