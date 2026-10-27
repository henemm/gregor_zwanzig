package main

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// Issue #2139: Prueft die WIRK-Stelle des Session-Secret-Gates — den Aufruf in
// main(). Der Unit-Test in internal/config prueft nur die Funktion selbst; wird
// der Aufruf aus main() entfernt, bleibt er gruen. Dieser Test startet deshalb
// das echte Binary und verlangt einen Abbruch vor dem Serverstart.

func goTool(t *testing.T) string {
	t.Helper()
	if p, err := exec.LookPath("go"); err == nil {
		return p
	}
	return filepath.Join(runtime.GOROOT(), "bin", "go")
}

func TestServerFailsFastOnDefaultSessionSecret(t *testing.T) {
	bin := filepath.Join(t.TempDir(), "gregor-api-failfast")
	build := exec.Command(goTool(t), "build", "-o", bin, ".")
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build failed: %v\n%s", err, out)
	}

	cmd := exec.Command(bin)
	cmd.Env = []string{
		"HOME=" + t.TempDir(),
		"PATH=" + os.Getenv("PATH"),
		"GZ_SESSION_SECRET=dev-secret-change-me",
		"GZ_DATA_DIR=" + t.TempDir(),
		// Port 0 und deaktivierter Scheduler begrenzen den Schaden, falls der
		// Fail-Fast fehlt und der Prozess tatsaechlich hochlaeuft.
		"GZ_PORT=0",
		"GZ_ENV=staging",
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		t.Fatalf("start failed: %v", err)
	}

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	select {
	case err := <-done:
		if err == nil {
			t.Fatalf("expected non-zero exit, got clean exit; stderr:\n%s", stderr.String())
		}
		if !strings.Contains(stderr.String(), "session secret invalid") {
			t.Fatalf("expected 'session secret invalid' on stderr, got:\n%s", stderr.String())
		}
	case <-time.After(10 * time.Second):
		_ = cmd.Process.Kill()
		<-done
		t.Fatalf("server did not terminate on default session secret; stderr:\n%s", stderr.String())
	}
}
