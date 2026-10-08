package openmeteo

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"
)

// Issue #1994 (Audit B-04): jede produktive Open-Meteo-Anfrage muss die
// Einheiten explizit senden, statt sich auf API-Defaults zu verlassen.
// Anfrage-Pfad-Test: ein lokaler Fake-Server liest die ANGEKOMMENE Query.

var erwarteteEinheiten = map[string]string{
	"wind_speed_unit":    "kmh",
	"temperature_unit":   "celsius",
	"precipitation_unit": "mm",
}

func TestFetchForecast_SendetExpliziteEinheitenAnForecastUndUV(t *testing.T) {
	var mu sync.Mutex
	seen := map[string][]url.Values{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		seen[r.URL.Path] = append(seen[r.URL.Path], r.URL.Query())
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"hourly":{"time":["2026-10-08T12:00"],"temperature_2m":[5.0]}}`))
	}))
	defer srv.Close()

	p := NewProvider(ProviderConfig{
		BaseURL:    srv.URL,
		AQURL:      srv.URL,
		TimeoutSec: 5,
		Retries:    1,
		CacheDir:   t.TempDir(),
	})
	// Ergebnis/Fehler sind hier egal: geprueft wird die abgesetzte Anfrage.
	_, _ = p.FetchForecast(47.0614, 11.1211, 24)

	mu.Lock()
	defer mu.Unlock()
	if len(seen["/v1/air-quality"]) == 0 {
		t.Fatal("kein UV-Request (/v1/air-quality) beobachtet")
	}
	forecastSeen := 0
	for path, queries := range seen {
		if path != "/v1/air-quality" {
			forecastSeen += len(queries)
		}
		for _, q := range queries {
			for k, want := range erwarteteEinheiten {
				got := q[k]
				if len(got) != 1 || got[0] != want {
					t.Errorf("%s: %s = %v, erwartet genau [%s]", path, k, got, want)
				}
			}
		}
	}
	if forecastSeen == 0 {
		t.Fatal("kein Forecast-Request beobachtet")
	}
}
