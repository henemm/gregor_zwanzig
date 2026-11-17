//go:build integration

package openmeteo

import "testing"

// Live-Variante (Issue #3106): prueft dieselben Zusicherungen wie die
// Fixture-Tests, aber gegen die echte Open-Meteo-API. Laeuft nur mit
// `go test -tags=integration`, nie im Kern-CI (geteilte Runner-IP -> 429).
func TestFetchForecast_Live_Mallorca48h(t *testing.T) {
	p := NewProvider(ProviderConfig{
		BaseURL:    "https://api.open-meteo.com",
		AQURL:      "https://air-quality-api.open-meteo.com",
		TimeoutSec: 30,
		Retries:    5,
		CacheDir:   t.TempDir(),
	})
	ts, err := p.FetchForecast(39.7, 3.0, 48)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pruefeMallorcaZeitreihe(t, ts)
	if ts.Timezone == "" {
		t.Error("expected timezone to be set, got empty string")
	}
}
