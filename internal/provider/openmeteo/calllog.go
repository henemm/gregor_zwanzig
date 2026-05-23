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
// ein t.TempDir umlenken können (Konfiguration, kein Mock).
var diagnosticsGoPath = filepath.Join("data", "diagnostics", "openmeteo_calls_go.jsonl")

// logAPICall hängt fail-soft eine JSONL-Zeile an diagnosticsGoPath an. Diagnose
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

	if dir := filepath.Dir(diagnosticsGoPath); dir != "" {
		if mkErr := os.MkdirAll(dir, 0o755); mkErr != nil {
			return
		}
	}

	f, openErr := os.OpenFile(diagnosticsGoPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if openErr != nil {
		return
	}
	defer f.Close()
	_, _ = f.Write(append(line, '\n'))
}
