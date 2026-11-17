package openmeteo

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// Issue #3106: die Kern-Tests von FetchForecast liefen gegen die echte
// Open-Meteo-API und scheiterten im CI am Tageslimit (HTTP 429) des geteilten
// Runner-IPs. Statt dessen bedient ein echter lokaler HTTP-Server die
// Anfragen mit einer Open-Meteo-Antwort im Originalformat aus testdata/
// (Forecast: /v1/meteofrance, UV: /v1/air-quality). Kein Mock: der Provider
// baut URL, Query und Parsing unveraendert, nur die Basis-URL zeigt lokal.

// openMeteoFixtureServer liefert die aufgezeichnete Antwort nur fuer Anfragen,
// die die echte API auch beantworten wuerde; alles andere bekommt den
// Open-Meteo-Fehlerkoerper und wird als unerwarteter Pfad gemerkt.
type openMeteoFixtureServer struct {
	srv        *httptest.Server
	mu         sync.Mutex
	pfade      []string
	unerwartet []string
}

func neuerOpenMeteoFixtureServer(t *testing.T) *openMeteoFixtureServer {
	t.Helper()
	forecast := leseFixture(t, "meteofrance_mallorca_48h.json")
	uv := leseFixture(t, "air_quality_mallorca_48h.json")

	f := &openMeteoFixtureServer{}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		f.mu.Lock()
		f.pfade = append(f.pfade, r.URL.Path)
		f.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		gueltig := q.Get("latitude") != "" && q.Get("longitude") != "" && q.Get("timezone") == "UTC"
		switch {
		case r.URL.Path == "/v1/meteofrance" && gueltig && strings.Contains(q.Get("hourly"), "temperature_2m"):
			_, _ = w.Write(forecast)
		case r.URL.Path == "/v1/air-quality" && gueltig && q.Get("hourly") == "uv_index":
			_, _ = w.Write(uv)
		default:
			f.mu.Lock()
			f.unerwartet = append(f.unerwartet, r.URL.String())
			f.mu.Unlock()
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":true,"reason":"unexpected request in fixture server"}`))
		}
	}))
	t.Cleanup(f.srv.Close)

	// Diagnose-Zeilen (logAPICall) nicht ins Projekt-"data/" schreiben.
	alt := diagnosticsGoPath
	diagnosticsGoPath = filepath.Join(t.TempDir(), "openmeteo_calls_go.jsonl")
	t.Cleanup(func() { diagnosticsGoPath = alt })
	return f
}

func leseFixture(t *testing.T, name string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatalf("Fixture %s nicht lesbar: %v", name, err)
	}
	return data
}

// provider baut den Provider mit der Produktiv-Konfiguration, nur mit lokaler
// Basis-URL fuer Forecast und Air-Quality.
func (f *openMeteoFixtureServer) provider(t *testing.T) *OpenMeteoProvider {
	return NewProvider(ProviderConfig{
		BaseURL:    f.srv.URL,
		AQURL:      f.srv.URL,
		TimeoutSec: 5,
		Retries:    1,
		CacheDir:   t.TempDir(),
	})
}

// pruefeAnfragen stellt sicher, dass Forecast UND UV am Fake ankamen und kein
// unerwarteter Abruf (etwa ein Fallback-Modell) stattfand.
func (f *openMeteoFixtureServer) pruefeAnfragen(t *testing.T) {
	t.Helper()
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.unerwartet) > 0 {
		t.Errorf("unerwartete Anfragen am Fixture-Server: %v", f.unerwartet)
	}
	gesehen := map[string]bool{}
	for _, p := range f.pfade {
		gesehen[p] = true
	}
	for _, p := range []string{"/v1/meteofrance", "/v1/air-quality"} {
		if !gesehen[p] {
			t.Errorf("keine Anfrage an %s beobachtet (gesehen: %v)", p, f.pfade)
		}
	}
}
