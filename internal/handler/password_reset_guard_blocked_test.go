package handler

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #1412 Scheibe S5, AC-7: Passwort-Reset bei Empfängerschutz-
// Block. Nach außen bleibt die Antwort `{"status":"ok"}` (Anti-Enumeration),
// im Journal steht genau EINE eindeutige Marker-Zeile ohne Klartext-Empfänger
// und ohne Benutzername.
// SPEC: docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md (AC-7)
//
// Echter Guard-Pfad: ForgotPasswordHandler -> echtes SendWithFallback ->
// echter Sender mit Nicht-Resend-Host (127.0.0.1:1, nicht erreichbar). Kein
// Stub von sendResetMailFn. Zwei verschiedene Nutzer (Fremdadresse vs.
// @henemm.com) plus unbekanntes Konto als Antwort-Referenz.

const resetGuardMarker = "password reset: Empfängerschutz hat Versand blockiert"

// syncBuf ist ein nebenläufigkeitssicherer Log-Puffer (die Reset-Mail läuft
// in einer Goroutine).
type syncBuf struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuf) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuf) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

func captureLog(t *testing.T) *syncBuf {
	t.Helper()
	b := &syncBuf{}
	orig := log.Writer()
	log.SetOutput(io.MultiWriter(b))
	t.Cleanup(func() { log.SetOutput(orig) })
	return b
}

// waitForLog pollt bis eine der Teilzeichenketten im Log steht (Deadline,
// kein fester Sleep als Synchronisation) und lässt der Goroutine danach kurz
// Zeit, eine eventuelle zweite Zeile zu schreiben.
func waitForLog(t *testing.T, b *syncBuf, anyOf ...string) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		s := b.String()
		for _, needle := range anyOf {
			if strings.Contains(s, needle) {
				time.Sleep(150 * time.Millisecond)
				return
			}
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("keine der erwarteten Logzeilen %v binnen 10s, Log:\n%s", anyOf, b.String())
}

func TestForgotPassword_GuardBlockedIsVisibleInLogButResponseUnchanged_AC7(t *testing.T) {
	logs := captureLog(t)
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	for _, u := range []model.User{
		{ID: "reset-fremd-s5", PasswordHash: string(hash), Email: "fremd.s5@gmail.com"},
		{ID: "reset-lokal-s5", PasswordHash: string(hash), Email: "lokal.s5@henemm.com"},
	} {
		if err := s.SaveUser(u); err != nil {
			t.Fatalf("SaveUser %s: %v", u.ID, err)
		}
	}
	t.Setenv("GZ_DATA_DIR", t.TempDir())
	cfg := config.Config{
		PublicHost: "https://example.com",
		// Nicht-Resend-Primärweg, nicht erreichbar: ein Block muss VOR dem Dial fallen.
		SMTPHost: "127.0.0.1", SMTPPort: 1, SMTPUser: "u", SMTPPass: "p",
	}
	call := func(username string) (int, string) {
		body, _ := json.Marshal(map[string]string{"username": username})
		req := httptest.NewRequest("POST", "/api/auth/forgot-password", bytes.NewReader(body))
		rec := httptest.NewRecorder()
		ForgotPasswordHandler(s, bcrypt.MinCost, cfg)(rec, req)
		return rec.Code, rec.Body.String()
	}

	// Fall 1: Fremdadresse -> Empfängerschutz blockt (Marker erwartet).
	codeF, bodyF := call("reset-fremd-s5")
	waitForLog(t, logs, resetGuardMarker, "mail send failed for reset-fremd-s5")
	afterFremd := logs.String()

	// Fall 2: eigene Domain -> kein Block (Dial scheitert nur am toten Port).
	codeL, bodyL := call("reset-lokal-s5")
	waitForLog(t, logs, "mail send failed for reset-lokal-s5", "mail send timeout")

	// Referenz: unbekanntes Konto.
	codeU, bodyU := call("unbekannt-s5")

	for name, got := range map[string]struct {
		code int
		body string
	}{"fremd": {codeF, bodyF}, "lokal": {codeL, bodyL}, "unbekannt": {codeU, bodyU}} {
		if got.code != 200 {
			t.Errorf("AC-7: %s: HTTP %d statt 200", name, got.code)
		}
		if got.body != `{"status":"ok"}` {
			t.Errorf("AC-7: %s: Antwortkörper %q statt bytegleich {\"status\":\"ok\"}", name, got.body)
		}
	}

	// Marker: im Blockfall genau einmal ...
	if n := strings.Count(afterFremd, resetGuardMarker); n != 1 {
		t.Errorf("AC-7: Marker %q muss im Blockfall genau einmal im Log stehen, war %dx. Log:\n%s",
			resetGuardMarker, n, afterFremd)
	}
	// ... und im Nicht-Blockfall gar nicht (Gesamtlog minus Fremd-Teil).
	if n := strings.Count(logs.String(), resetGuardMarker); n != 1 {
		t.Errorf("AC-7: Marker darf nur durch den Fremdadress-Reset entstehen (gesamt 1x), war %dx", n)
	}
	// Marker-Zeile ohne Klartext-Empfänger und ohne Benutzername.
	for _, line := range strings.Split(logs.String(), "\n") {
		if !strings.Contains(line, resetGuardMarker) {
			continue
		}
		for _, verboten := range []string{"@", "reset-fremd-s5", "fremd.s5", "reset-lokal-s5", "gmail.com"} {
			if strings.Contains(line, verboten) {
				t.Errorf("AC-7: Marker-Zeile enthält %q (Klartext-Empfänger/Benutzername): %s", verboten, line)
			}
		}
	}
}
