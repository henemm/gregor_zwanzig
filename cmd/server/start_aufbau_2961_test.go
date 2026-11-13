package main

// Issue #2961 Nachbesserung (Gegenpruefung F6) — der Start benutzt wirklich
// newHTTPServer (Zeitgrenzen) und warnPrivilegedIDsWithoutAccount: gemessen
// an buildServer, das main() unveraendert aufruft.

import (
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

func TestBuildServer_NutztZeitgrenzenUndStartwarnung(t *testing.T) {
	cfg := &config.Config{
		Host: "127.0.0.1", Port: "0",
		DataDir: t.TempDir(), CacheDir: t.TempDir(),
		Env:                "staging", // Scheduler aus
		TestFixtureDir:     t.TempDir(),
		PublicHost:         "https://gregor.example.invalid",
		SessionSecret:      "build-server-2961-secret-32-zeichen",
		AdminUserIDs:       "geisteradmin",
		QuotaExemptUserIDs: "geisterausnahme",
		PythonCoreURL:      "http://127.0.0.1:1",
	}
	var srvTimeouts [3]time.Duration
	var writeTimeout time.Duration
	out := captureLog(t, func() {
		srv, cleanup, err := buildServer(cfg)
		if err != nil {
			t.Fatalf("buildServer: %v", err)
		}
		defer cleanup()
		srvTimeouts = [3]time.Duration{srv.ReadHeaderTimeout, srv.ReadTimeout, srv.IdleTimeout}
		writeTimeout = srv.WriteTimeout
		if srv.Handler == nil || srv.Addr != "127.0.0.1:0" {
			t.Errorf("Server ohne Router oder falsche Adresse: %q", srv.Addr)
		}
	})
	if srvTimeouts != [3]time.Duration{serverReadHeaderTimeout, serverReadTimeout, serverIdleTimeout} {
		t.Errorf("Start-Server traegt nicht die Zeitgrenzen aus newHTTPServer: %v", srvTimeouts)
	}
	if writeTimeout != 0 {
		t.Errorf("Start-Server darf kein WriteTimeout haben, hat %v", writeTimeout)
	}
	for _, id := range []string{"geisteradmin", "geisterausnahme"} {
		if !strings.Contains(out, id) {
			t.Errorf("Startwarnung fuer %q fehlt im Log:\n%s", id, out)
		}
	}
}
