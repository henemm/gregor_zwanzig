package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

// Issue #2130, Fix-Loop 1 (Finding F001): Prueft die WIRK-Stelle der
// Passkey-Konfiguration — den Aufruf von config.NewWebAuthn in main().
// Die Unit-Tests in internal/config pruefen nur die Ableitung selbst; baut
// main() sich seine webauthn-Instanz wieder inline zusammen (der Zustand, der
// drei Monate lang rpId "localhost" ausgeliefert hat), bleiben sie samt
// kompletter Suite gruen. Dieser Test startet deshalb das echte Binary und
// liest die RP-ID dort, wo sie wirkt: aus der Antwort des laufenden Servers.
//
// Muster: main_failfast_test.go (nebenan, Issue #2139) — echtes Binary bauen,
// starten, abfragen. goTool() stammt von dort.

// freierPort ermittelt einen freien Port, damit der Test weder Prod (8090)
// noch Staging (8091) noch einen Parallellauf stoert.
func freierPort(t *testing.T) string {
	t.Helper()
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("kein freier Port: %v", err)
	}
	defer l.Close()
	_, port, err := net.SplitHostPort(l.Addr().String())
	if err != nil {
		t.Fatalf("Adresse unlesbar: %v", err)
	}
	return port
}

func TestLaufenderServerFuehrtAbgeleiteteRPID(t *testing.T) {
	const publicHost = "https://staging.gregor20.henemm.com"
	const erwarteteRPID = "staging.gregor20.henemm.com"

	bin := filepath.Join(t.TempDir(), "gregor-api-rpid")
	build := exec.Command(goTool(t), "build", "-o", bin, ".")
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build failed: %v\n%s", err, out)
	}

	port := freierPort(t)
	cmd := exec.Command(bin)
	cmd.Env = []string{
		"HOME=" + t.TempDir(),
		"PATH=" + os.Getenv("PATH"),
		"GZ_HOST=127.0.0.1",
		"GZ_PORT=" + port,
		"GZ_DATA_DIR=" + t.TempDir(),
		"GZ_CACHE_DIR=" + t.TempDir(),
		// Fixture-Verzeichnis: setzt die beiden Secret-Gates aus (siehe
		// config.ValidateSessionSecret/ValidateCoreSharedSecret) und haelt den
		// Wetter-Provider offline.
		"GZ_TEST_FIXTURE_DIR=" + t.TempDir(),
		// Python-Core absichtlich unerreichbar — /api/health antwortet dann mit
		// status=degraded, das RP-ID-Feld muss trotzdem stimmen. Kein Netz.
		"GZ_PYTHON_CORE_URL=http://127.0.0.1:19999",
		"GZ_ENV=staging",
		// GIVEN: allein die oeffentliche Adresse ist gesetzt, keine expliziten
		// WebAuthn-Variablen.
		"GZ_PUBLIC_HOST=" + publicHost,
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		t.Fatalf("start failed: %v", err)
	}
	t.Cleanup(func() {
		_ = cmd.Process.Kill()
		_, _ = cmd.Process.Wait()
	})

	// WHEN: der real gestartete Server nach seinem Zustand gefragt wird
	url := "http://127.0.0.1:" + port + "/api/health"
	var body []byte
	deadline := time.Now().Add(20 * time.Second)
	for {
		resp, err := http.Get(url)
		if err == nil {
			body, _ = io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				break
			}
		}
		if time.Now().After(deadline) {
			t.Fatalf("Server auf %s nicht erreichbar; stderr:\n%s", url, stderr.String())
		}
		time.Sleep(100 * time.Millisecond)
	}

	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		t.Fatalf("ungueltiges JSON: %v — %s", err, string(body))
	}

	// THEN: der laufende Server fuehrt die aus GZ_PUBLIC_HOST abgeleitete RP-ID
	if payload["webauthn_rpid"] != erwarteteRPID {
		t.Errorf("F001: der laufende Server muss die aus GZ_PUBLIC_HOST=%q abgeleitete RP-ID %q fuehren, "+
			"bekommen %v — main() baut die WebAuthn-Instanz offenbar an config.NewWebAuthn vorbei (Antwort: %s)",
			publicHost, erwarteteRPID, payload["webauthn_rpid"], string(body))
	}
	// THEN: und ausdruecklich nicht mehr den alten localhost-Default
	if payload["webauthn_rpid"] == "localhost" {
		t.Errorf("F001: der laufende Server sendet weiterhin rpId \"localhost\" — genau der Prod-Ausfall aus #2130")
	}
}
