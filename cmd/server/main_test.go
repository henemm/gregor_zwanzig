// TDD fuer Issue #2142 Adversary-Finding F002: die Installationsreihenfolge
// der Transport-Waechter muss dort geprueft werden, wo sie wirkt — in der von
// main() tatsaechlich aufgerufenen installGuards() — nicht in einer im
// Testkoerper nachgebauten Aufrufkette.
package main

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/egress"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func TestInstallGuardsOrderSurvivesEgressUninstall(t *testing.T) {
	var hits int
	var gotHeader string
	coreSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		gotHeader = r.Header.Get("X-GZ-Core-Auth")
		w.WriteHeader(http.StatusOK)
	}))
	defer coreSrv.Close()

	const secret = "core-shared-secret-fuer-main-test-0123456789"
	cfg := &config.Config{
		PythonCoreURL:    coreSrv.URL,
		CoreSharedSecret: secret,
		// Env=staging, weil egress.Install nur in Staging bzw. mit
		// TestFixtureDir installiert; ohne echten Egress-Waechter-Zyklus
		// waere die Reihenfolge nicht pruefbar.
		Env: "staging",
	}

	orig := http.DefaultTransport
	t.Cleanup(func() {
		egress.Uninstall()
		coreauth.Uninstall()
		http.DefaultTransport = orig
	})

	// Das ist die Pruefstelle: dieselbe Funktion, die main() aufruft.
	installGuards(cfg)

	// egress.Uninstall() darf den Auth-Header-Transport NICHT mit entfernen.
	egress.Uninstall()

	resp, err := http.Get(coreSrv.URL + "/config")
	if err != nil {
		t.Fatalf("GET fehlgeschlagen: %v", err)
	}
	resp.Body.Close()

	if hits != 1 {
		t.Fatalf("Positivkontrolle: Python-Core-Fake wurde nicht erreicht (hits=%d)", hits)
	}
	if gotHeader != secret {
		t.Fatalf("Auth-Header nach egress.Uninstall() verloren: erwartet %q, angekommen %q", secret, gotHeader)
	}
}

// captureLog leitet log.Default() waehrend fn() in einen Puffer um und
// stellt den vorherigen Writer danach wieder her — gemeinsamer Aufbau fuer
// die drei Seed-Tests (Issue #2151 Scheibe B, AC-1..AC-3).
func captureLog(t *testing.T, fn func()) string {
	t.Helper()
	var buf bytes.Buffer
	orig := log.Writer()
	log.SetOutput(&buf)
	defer log.SetOutput(orig)
	fn()
	return buf.String()
}

// TestSeedSkippedWithoutUserID prueft AC-1: ohne gesetzte GZ_USER_ID
// (cfg.UserID == "") darf seedAdminUser trotz gesetztem AuthPass kein neues
// Konto anlegen, keine "created"-Logzeile fuer die leere Kennung ausgeben,
// und ein bereits vorhandenes Bestandskonto "default" bleibt unangetastet.
func TestSeedSkippedWithoutUserID(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "default")

	if err := s.SaveUser(model.User{ID: "default", PasswordHash: "bestand"}); err != nil {
		t.Fatalf("setup SaveUser: %v", err)
	}
	before, err := os.ReadFile(filepath.Join(dir, "users", "default", "user.json"))
	if err != nil {
		t.Fatalf("setup read: %v", err)
	}

	cfg := &config.Config{UserID: "", AuthPass: "secret-pass"}
	var seedErr error
	logOutput := captureLog(t, func() {
		seedErr = seedAdminUser(s, cfg)
	})

	if seedErr != nil {
		t.Fatalf("seedAdminUser: unerwarteter Fehler: %v", seedErr)
	}
	if strings.Contains(logOutput, "Seed user '' created") {
		t.Fatalf("Logzeile fuer leere Kennung erschienen: %q", logOutput)
	}

	entries, err := os.ReadDir(filepath.Join(dir, "users"))
	if err != nil {
		t.Fatalf("users/ lesen: %v", err)
	}
	if len(entries) != 1 || entries[0].Name() != "default" {
		names := make([]string, len(entries))
		for i, e := range entries {
			names[i] = e.Name()
		}
		t.Fatalf("erwartet ausschliesslich 'default' unter users/, bekommen: %v", names)
	}

	after, err := os.ReadFile(filepath.Join(dir, "users", "default", "user.json"))
	if err != nil {
		t.Fatalf("after read: %v", err)
	}
	if string(before) != string(after) {
		t.Fatalf("users/default/user.json wurde durch seedAdminUser veraendert")
	}
}

// TestSeedCreatesAccountWhenUserIDSet prueft AC-2: mit gesetzter GZ_USER_ID
// (z. B. "admin", Vorbild frontend/e2e/ci-stack.sh:66) und noch nicht
// existierendem Konto legt seedAdminUser es an und loggt "created".
func TestSeedCreatesAccountWhenUserIDSet(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "admin")

	cfg := &config.Config{UserID: "admin", AuthPass: "secret-pass"}
	var seedErr error
	logOutput := captureLog(t, func() {
		seedErr = seedAdminUser(s, cfg)
	})

	if seedErr != nil {
		t.Fatalf("seedAdminUser: unerwarteter Fehler: %v", seedErr)
	}
	if !s.UserExists("admin") {
		t.Fatalf("Konto 'admin' wurde nicht angelegt")
	}
	if !strings.Contains(logOutput, "Seed user 'admin' created") {
		t.Fatalf("erwartete Logzeile fehlt: %q", logOutput)
	}
}

// TestSeedFailureIsLoggedNotFatal prueft AC-3: scheitert das Anlegen des
// Kontos technisch (hier: users/admin liegt als DATEI statt Ordner vor, damit
// SaveUsers os.MkdirAll fehlschlaegt), wird der Fehler protokolliert, es
// erscheint keine "created"-Zeile, und seedAdminUser kehrt normal zurueck
// (kein log.Fatal/Panic — der Server startet trotzdem weiter).
func TestSeedFailureIsLoggedNotFatal(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "users"), 0755); err != nil {
		t.Fatalf("setup mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "users", "admin"), []byte("blockiert"), 0644); err != nil {
		t.Fatalf("setup write: %v", err)
	}

	s := store.New(dir, "admin")
	cfg := &config.Config{UserID: "admin", AuthPass: "secret-pass"}

	var seedErr error
	logOutput := captureLog(t, func() {
		seedErr = seedAdminUser(s, cfg)
	})

	if seedErr == nil {
		t.Fatalf("erwartet Fehler von seedAdminUser, bekommen nil")
	}
	if strings.Contains(logOutput, "Seed user 'admin' created") {
		t.Fatalf("faelschlich 'created' geloggt trotz Fehlschlag: %q", logOutput)
	}
	if logOutput == "" {
		t.Fatalf("erwartet eine Log-Zeile mit dem Fehlschlag, aber Log ist leer")
	}
}
