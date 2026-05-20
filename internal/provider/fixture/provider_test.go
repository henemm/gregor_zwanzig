// TDD RED — Tests für den FixtureProvider (Issue #263).
// Erwartet: FAIL (package fixture does not exist) bis FixtureProvider implementiert ist.
//
// Ausführung:
//   go test ./internal/provider/fixture/... -v -race
package fixture_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider/fixture"
)

// buildTestFixtureDir schreibt drei minimale Timeseries-JSON-Dateien in ein
// temporäres Verzeichnis und gibt dessen Pfad zurück.
func buildTestFixtureDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()

	locations := []struct {
		name string
		temp float64
	}{
		{"innsbruck", 2.0},
		{"stubai", -5.0},
		{"zillertal", 1.0},
	}

	for _, loc := range locations {
		ts := model.Timeseries{
			Timezone: "Europe/Vienna",
			Meta: model.ForecastMeta{
				Provider:  "FIXTURE",
				Model:     "fixture",
				GridResKm: 0,
			},
			Data: makeDataPoints(72, loc.temp),
		}
		data, err := json.Marshal(ts)
		if err != nil {
			t.Fatalf("json.Marshal(%s): %v", loc.name, err)
		}
		if err := os.WriteFile(filepath.Join(dir, loc.name+".json"), data, 0644); err != nil {
			t.Fatalf("WriteFile(%s): %v", loc.name, err)
		}
	}
	return dir
}

func makeDataPoints(n int, tempC float64) []model.ForecastDataPoint {
	pts := make([]model.ForecastDataPoint, n)
	wind := 15.0
	gust := 22.0
	precip := 0.1
	vis := 9000.0
	cloud := 40
	cape := 0.0
	uv := 1.2
	snow := 5.0
	dni := 250.0
	isDay := 1
	wmo := 2
	for i := range pts {
		pts[i] = model.ForecastDataPoint{
			Time:          model.UTCTime{Time: time.Date(2026, 1, 1, i, 0, 0, 0, time.UTC)},
			T2mC:          &tempC,
			Wind10mKmh:    &wind,
			GustKmh:       &gust,
			Precip1hMm:    &precip,
			VisibilityM:   &vis,
			CloudTotalPct: &cloud,
			CapeJkg:       &cape,
			UvIndex:       &uv,
			SnowDepthCm:   &snow,
			DniWm2:        &dni,
			IsDay:         &isDay,
			WmoCode:       &wmo,
		}
	}
	return pts
}

// --- Test 1: FetchForecast nahe Innsbruck gibt 72 Datenpunkte zurück ----------

func TestFixtureProvider_Innsbruck_Returns72Points(t *testing.T) {
	// GIVEN: FixtureProvider mit drei Fixture-Dateien (Innsbruck T=2, Stubai T=-5, Zillertal T=1)
	// WHEN:  FetchForecast mit Innsbruck-Koordinaten aufgerufen
	// THEN:  Kein Fehler, genau 72 Datenpunkte, Meta.Provider == "FIXTURE"
	dir := buildTestFixtureDir(t)
	p := fixture.NewProvider(dir)

	ts, err := p.FetchForecast(47.2692, 11.4041, 72)
	if err != nil {
		t.Fatalf("FetchForecast Innsbruck: unerwarteter Fehler: %v", err)
	}
	if ts == nil {
		t.Fatal("FetchForecast Innsbruck: Timeseries ist nil")
	}
	if len(ts.Data) != 72 {
		t.Errorf("erwartet 72 Datenpunkte, got %d", len(ts.Data))
	}
	if ts.Meta.Provider != "FIXTURE" {
		t.Errorf("Meta.Provider: erwartet FIXTURE, got %q", ts.Meta.Provider)
	}
}

// --- Test 2: Nearest-Match — Stubai-Koordinaten liefern Stubai-Daten (T=-5) ----

func TestFixtureProvider_NearestMatch_StubaiCoords_ReturnsStubaiData(t *testing.T) {
	// GIVEN: FixtureProvider mit drei Fixture-Dateien
	// WHEN:  FetchForecast mit Stubai-Koordinaten (47.10, 11.30) aufgerufen
	// THEN:  Erster Datenpunkt hat T2mC == -5.0 (Stubai-Fixture-Wert)
	dir := buildTestFixtureDir(t)
	p := fixture.NewProvider(dir)

	ts, err := p.FetchForecast(47.10, 11.30, 72)
	if err != nil {
		t.Fatalf("FetchForecast Stubai: %v", err)
	}
	if ts == nil || len(ts.Data) == 0 {
		t.Fatal("Timeseries leer")
	}
	if ts.Data[0].T2mC == nil {
		t.Fatal("T2mC ist nil")
	}
	if *ts.Data[0].T2mC != -5.0 {
		t.Errorf("erwartet T2mC=-5.0 (Stubai), got %v", *ts.Data[0].T2mC)
	}
}

// --- Test 3: Timestamp-Re-Stamping — alle Timestamps am heutigen UTC-Tag ------

func TestFixtureProvider_TimestampsAnchoredToCurrentDay(t *testing.T) {
	// GIVEN: FixtureProvider mit Fixture-Daten aus 2026-01-01
	// WHEN:  FetchForecast aufgerufen
	// THEN:  Erster Timestamp = heutiger UTC-Tag 00:00, zweiter = 01:00 (1h Abstand)
	dir := buildTestFixtureDir(t)
	p := fixture.NewProvider(dir)

	ts, err := p.FetchForecast(47.2692, 11.4041, 72)
	if err != nil {
		t.Fatalf("FetchForecast: %v", err)
	}
	if len(ts.Data) < 2 {
		t.Fatal("zu wenige Datenpunkte für Timestamp-Test")
	}

	today := time.Now().UTC().Truncate(24 * time.Hour)
	firstTs := ts.Data[0].Time.UTC()

	if !firstTs.Equal(today) {
		t.Errorf("erster Timestamp: erwartet %v (heute 00:00 UTC), got %v", today, firstTs)
	}

	delta := ts.Data[1].Time.UTC().Sub(ts.Data[0].Time.UTC())
	if delta != time.Hour {
		t.Errorf("Timestamp-Abstand: erwartet 1h, got %v", delta)
	}
}

// --- Test 4: Thread-Safety — 10 parallele Goroutinen ohne Race-Condition ------

func TestFixtureProvider_ConcurrentFetch_ThreadSafe(t *testing.T) {
	// GIVEN: FixtureProvider mit Fixture-Dateien
	// WHEN:  10 Goroutinen rufen FetchForecast gleichzeitig auf
	// THEN:  Kein Panic, alle 10 Ergebnisse haben genau 72 Datenpunkte
	dir := buildTestFixtureDir(t)
	p := fixture.NewProvider(dir)

	const goroutines = 10
	results := make([]*model.Timeseries, goroutines)
	var wg sync.WaitGroup
	var mu sync.Mutex
	var firstErr error

	for i := 0; i < goroutines; i++ {
		i := i
		wg.Add(1)
		go func() {
			defer wg.Done()
			ts, err := p.FetchForecast(47.2692, 11.4041, 72)
			mu.Lock()
			defer mu.Unlock()
			if err != nil && firstErr == nil {
				firstErr = err
			}
			results[i] = ts
		}()
	}
	wg.Wait()

	if firstErr != nil {
		t.Fatalf("parallele FetchForecast: %v", firstErr)
	}
	for i, ts := range results {
		if ts == nil {
			t.Errorf("Goroutine %d: Timeseries ist nil", i)
			continue
		}
		if len(ts.Data) != 72 {
			t.Errorf("Goroutine %d: erwartet 72 Punkte, got %d", i, len(ts.Data))
		}
	}
}

// --- Test 5: Ungültiges Verzeichnis gibt Fehler zurück -----------------------

func TestFixtureProvider_InvalidDir_ReturnsError(t *testing.T) {
	// GIVEN: FixtureProvider mit nicht-existierendem Verzeichnis
	// WHEN:  FetchForecast aufgerufen
	// THEN:  Fehler ist nicht nil, Timeseries ist nil
	p := fixture.NewProvider("/nonexistent/path/to/fixtures")

	ts, err := p.FetchForecast(47.2692, 11.4041, 72)
	if err == nil {
		t.Error("erwartet Fehler bei ungültigem Verzeichnis, got nil")
	}
	if ts != nil {
		t.Errorf("erwartet nil Timeseries bei Fehler, got non-nil")
	}
}
