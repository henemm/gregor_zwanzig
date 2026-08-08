package openmeteo

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Issue #338: Diagnose-Zähler für den Go-Provider. Jeder ausgehende
// Open-Meteo-Abruf (Forecast/UV, inkl. Retry-Versuche) hängt eine JSONL-Zeile
// an. Reine Observability, fail-soft. Eigene Datei (getrennt von Python), um
// Cross-Language-Schreibkonflikte zu vermeiden.

// diagnosticsGoPath ist als Paket-Variable konfigurierbar, damit Tests ihn auf
// ein t.TempDir umlenken können (Konfiguration, kein Mock). Leer = kein
// Override, dann entscheidet diagnosticsGoLogPath() zur Laufzeit.
//
// Issue #1595: der Pfad darf NICHT mehr beim Paket-Import festgelegt werden.
// Die Datenwurzel steht in GZ_DATA_DIR, und die wird erst nach dem Import
// gelesen — ein früh gebundener Wert zeigte weiter auf das relative "data"
// im Projektordner, also seit dem Umzug auf einen leeren Ordner.
var diagnosticsGoPath string

// diagnosticsGoLogPath löst den Zielpfad beim Zugriff auf: Test-Override zuerst,
// sonst GZ_DATA_DIR mit unverändertem Rückfall auf "data".
func diagnosticsGoLogPath() string {
	if diagnosticsGoPath != "" {
		return diagnosticsGoPath
	}
	root := os.Getenv("GZ_DATA_DIR")
	if root == "" {
		root = "data"
	}
	return filepath.Join(root, "diagnostics", "openmeteo_calls_go.jsonl")
}

// logAPICall hängt fail-soft eine JSONL-Zeile an diagnosticsGoLogPath() an. Diagnose
// darf den Abruf NIE beeinträchtigen — jeder Fehler/Panic wird geschluckt.
func logAPICall(reqURL string, status int, errStr string) {
	defer func() { _ = recover() }()

	source := "go_forecast"
	if strings.Contains(reqURL, "/v1/air-quality") {
		source = "go_uv"
	}

	endpoint := reqURL
	if i := strings.IndexByte(reqURL, '?'); i >= 0 {
		endpoint = reqURL[:i] // ohne Query
	}

	line, err := json.Marshal(map[string]interface{}{
		"ts":       time.Now().UTC().Format(time.RFC3339Nano),
		"endpoint": endpoint,
		"status":   status,
		"source":   source,
		"error":    errStr,
	})
	if err != nil {
		return
	}

	logPath := diagnosticsGoLogPath()
	if dir := filepath.Dir(logPath); dir != "" {
		if mkErr := os.MkdirAll(dir, 0o755); mkErr != nil {
			return
		}
	}

	f, openErr := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if openErr != nil {
		return
	}
	defer f.Close()
	_, _ = f.Write(append(line, '\n'))
}
