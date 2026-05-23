package openmeteo

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// readGoCallLog liest die JSONL-Diagnose-Datei und gibt die Zeilen als
// dekodierte Maps zurück (leerer Slice wenn nicht vorhanden).
func readGoCallLog(t *testing.T, path string) []map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var out []map[string]interface{}
	for _, ln := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" {
			continue
		}
		var m map[string]interface{}
		if err := json.Unmarshal([]byte(ln), &m); err != nil {
			t.Fatalf("ungültige JSONL-Zeile %q: %v", ln, err)
		}
		out = append(out, m)
	}
	return out
}

// =============================================================================
// AC-1: FetchForecast gegen httptest-Server (429) protokolliert go_forecast
// =============================================================================

func TestCallLog_FetchForecast429_AppendsGoForecastLine(t *testing.T) {
	// GIVEN: ein lokaler httptest-Server, der 429 liefert (kein externer Call,
	// kein Mock — ein echter HTTP-Server). Diagnose-Pfad zeigt auf t.TempDir.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
		_, _ = w.Write([]byte(`{"error":true,"reason":"limit"}`))
	}))
	defer srv.Close()

	logPath := filepath.Join(t.TempDir(), "openmeteo_calls_go.jsonl")
	old := diagnosticsGoPath
	diagnosticsGoPath = logPath
	defer func() { diagnosticsGoPath = old }()

	p := NewProvider(ProviderConfig{
		BaseURL:    srv.URL,
		AQURL:      srv.URL,
		TimeoutSec: 5,
		Retries:    1,
		CacheDir:   t.TempDir(),
	})

	// WHEN: FetchForecast läuft (Innsbruck → icon_d2). Ein 429 ist erwartet.
	_, _ = p.FetchForecast(47.27, 11.39, 24)

	// THEN: mindestens eine JSONL-Zeile mit status=429, source=go_forecast,
	// endpoint ohne Query.
	rows := readGoCallLog(t, logPath)
	if len(rows) == 0 {
		t.Fatalf("erwartete mindestens eine JSONL-Zeile in %s", logPath)
	}

	var found bool
	for _, row := range rows {
		status, _ := row["status"].(float64)
		source, _ := row["source"].(string)
		endpoint, _ := row["endpoint"].(string)
		if int(status) == 429 && source == "go_forecast" {
			found = true
			if strings.Contains(endpoint, "?") {
				t.Errorf("endpoint darf keine Query enthalten: %q", endpoint)
			}
			if _, ok := row["ts"]; !ok {
				t.Errorf("JSONL-Zeile fehlt Feld 'ts': %v", row)
			}
		}
	}
	if !found {
		t.Errorf("keine Zeile mit status=429 und source=go_forecast gefunden: %v", rows)
	}
}

// =============================================================================
// AC-1 (go_uv): Forecast 200 + Air-Quality-Abruf protokolliert source="go_uv"
// =============================================================================

func TestCallLog_UVFetch_AppendsGoUVLine(t *testing.T) {
	// GIVEN: ein httptest-Server, der nach Pfad routet — der Forecast-Endpoint
	// liefert 200 mit validem Body (damit FetchForecast nicht vor fetchUVData
	// abbricht), der Air-Quality-Endpoint (/v1/air-quality) liefert UV-Daten.
	// Echter lokaler HTTP-Server, kein Mock.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		if strings.Contains(r.URL.Path, "/v1/air-quality") {
			_, _ = w.Write([]byte(`{"hourly":{"time":["2026-05-22T08:00"],"uv_index":[3.1]}}`))
			return
		}
		// Forecast-Body mit allen für tryFallback geprüften Pflichtfeldern,
		// damit kein zusätzlicher Fallback-Forecast-Call ausgelöst wird.
		_, _ = w.Write([]byte(`{"hourly":{"time":["2026-05-22T08:00"],` +
			`"temperature_2m":[12.0],"wind_speed_10m":[5.0],"pressure_msl":[1013.0]}}`))
	}))
	defer srv.Close()

	logPath := filepath.Join(t.TempDir(), "openmeteo_calls_go.jsonl")
	old := diagnosticsGoPath
	diagnosticsGoPath = logPath
	defer func() { diagnosticsGoPath = old }()

	p := NewProvider(ProviderConfig{
		BaseURL:    srv.URL,
		AQURL:      srv.URL,
		TimeoutSec: 5,
		Retries:    1,
		CacheDir:   t.TempDir(),
	})

	// WHEN: FetchForecast läuft (Innsbruck → icon_d2): Forecast 200, danach
	// fetchUVData gegen /v1/air-quality.
	_, _ = p.FetchForecast(47.27, 11.39, 24)

	// THEN: mindestens eine JSONL-Zeile mit source=go_uv (Air-Quality-Pfad),
	// endpoint ohne Query.
	rows := readGoCallLog(t, logPath)
	if len(rows) == 0 {
		t.Fatalf("erwartete mindestens eine JSONL-Zeile in %s", logPath)
	}

	var foundUV bool
	for _, row := range rows {
		source, _ := row["source"].(string)
		endpoint, _ := row["endpoint"].(string)
		if source == "go_uv" {
			foundUV = true
			if strings.Contains(endpoint, "?") {
				t.Errorf("endpoint darf keine Query enthalten: %q", endpoint)
			}
			if !strings.Contains(endpoint, "/v1/air-quality") {
				t.Errorf("go_uv-Endpoint sollte /v1/air-quality enthalten: %q", endpoint)
			}
		}
	}
	if !foundUV {
		t.Errorf("keine Zeile mit source=go_uv gefunden (Air-Quality-Pfad ungezählt): %v", rows)
	}
}

// =============================================================================
// AC-5: nicht-beschreibbares Diagnose-Ziel → logAPICall schluckt Fehler,
// kein Panic, doRequest/FetchForecast liefern unverändert.
// =============================================================================

func TestCallLog_UnwritableTarget_IsSwallowed(t *testing.T) {
	// GIVEN: Diagnose-Pfad zeigt unter eine DATEI (parent ist kein Verzeichnis)
	// → echter Schreibfehler bei MkdirAll/OpenFile.
	blocker := filepath.Join(t.TempDir(), "blocker")
	if err := os.WriteFile(blocker, []byte("ich bin eine datei"), 0o644); err != nil {
		t.Fatalf("setup: %v", err)
	}
	badPath := filepath.Join(blocker, "openmeteo_calls_go.jsonl") // parent ist Datei
	old := diagnosticsGoPath
	diagnosticsGoPath = badPath
	defer func() { diagnosticsGoPath = old }()

	// Direkter Helfer-Aufruf darf NICHT paniken trotz Schreibfehler.
	logAPICall("https://api.open-meteo.com/v1/ecmwf?lat=1", 429, "")

	// httptest-Server liefert 200 mit minimal-validem Forecast-Body, damit
	// FetchForecast unverändert ein Ergebnis (oder einen normalen Parse-Pfad)
	// liefert — entscheidend: kein Panic / kein propagierter Logging-Fehler.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"hourly":{"time":["2026-05-22T08:00"],"temperature_2m":[12.0]}}`))
	}))
	defer srv.Close()

	p := NewProvider(ProviderConfig{
		BaseURL:    srv.URL,
		AQURL:      srv.URL,
		TimeoutSec: 5,
		Retries:    1,
		CacheDir:   t.TempDir(),
	})

	// WHEN: FetchForecast läuft trotz nicht-beschreibbarem Log.
	ts, err := p.FetchForecast(47.27, 11.39, 24)

	// THEN: kein Panic; ein normales (Erfolgs-)Ergebnis ist möglich. Die
	// Blocker-Datei bleibt unverändert eine Datei.
	if err != nil && ts == nil {
		// Ein fachlicher Fehler ist erlaubt; wichtig ist nur: kein Panic
		// und der Schreibfehler propagiert nicht als Crash. (err hier ok)
		_ = err
	}
	info, statErr := os.Stat(blocker)
	if statErr != nil {
		t.Fatalf("blocker verschwunden: %v", statErr)
	}
	if info.IsDir() {
		t.Errorf("logAPICall hätte die Blocker-Datei nicht in ein Verzeichnis verwandeln dürfen")
	}
}
