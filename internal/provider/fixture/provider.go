// Package fixture implementiert einen WeatherProvider, der statische
// Timeseries-JSON-Daten aus lokalen Fixture-Dateien lädt. Er wird ausschließlich
// im E2E-Test-Kontext aktiviert (via GZ_TEST_FIXTURE_DIR), um OpenMeteo-Rate-Limits
// zu vermeiden. In Produktion wird er nie instanziiert.
package fixture

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
)

// Compiler-Check: FixtureProvider muss WeatherProvider erfüllen.
var _ provider.WeatherProvider = (*FixtureProvider)(nil)

type fixtureLocation struct {
	Name string
	Lat  float64
	Lon  float64
	File string
}

// testLocations ist die hardcodierte Registry der 3 E2E-Test-Locations.
// Nearest-Lookup über squared Euclidean distance (keine Wurzel nötig).
var testLocations = []fixtureLocation{
	{"Innsbruck", 47.2692, 11.4041, "innsbruck.json"},
	{"Stubai", 47.1015, 11.2958, "stubai.json"},
	{"Zillertal", 47.2190, 11.8767, "zillertal.json"},
}

// FixtureProvider liefert Wetter-Forecasts aus statischen JSON-Dateien.
// Thread-Safety: keine Shared Mutable State, jeder FetchForecast liest frisch von Disk.
type FixtureProvider struct {
	dir string
}

// NewProvider erzeugt einen FixtureProvider, der seine Fixture-Dateien
// aus dem angegebenen Verzeichnis lädt (z.B. "fixtures/openmeteo").
func NewProvider(dir string) *FixtureProvider {
	return &FixtureProvider{dir: dir}
}

// FetchForecast lädt die geographisch nächstliegende Fixture-Datei,
// deserialisiert sie in model.Timeseries und re-stempelt alle Timestamps
// auf den aktuellen UTC-Tag (00:00 UTC + i*1h).
func (fp *FixtureProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	nearest := nearestLocation(lat, lon)

	path := filepath.Join(fp.dir, nearest.File)
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, &provider.ProviderError{
			Msg: fmt.Sprintf("fixture read failed (%s): %v", path, err),
		}
	}

	var ts model.Timeseries
	if err := json.Unmarshal(data, &ts); err != nil {
		return nil, &provider.ProviderError{
			Msg: fmt.Sprintf("fixture unmarshal failed (%s): %v", path, err),
		}
	}

	// Re-Stamping: alle Timestamps am heutigen UTC-Tag verankern.
	today := time.Now().UTC().Truncate(24 * time.Hour)
	for i := range ts.Data {
		ts.Data[i].Time = model.UTCTime{Time: today.Add(time.Duration(i) * time.Hour)}
	}

	// Truncation: auf min(len, hours) kappen, damit der Aufrufer
	// nie mehr Punkte erhält als angefordert.
	if hours > 0 && hours < len(ts.Data) {
		ts.Data = ts.Data[:hours]
	}

	return &ts, nil
}

// nearestLocation berechnet die squared Euclidean distance über lat/lon
// und gibt die geographisch nächstliegende Test-Location zurück.
func nearestLocation(lat, lon float64) fixtureLocation {
	best := testLocations[0]
	dLat := lat - best.Lat
	dLon := lon - best.Lon
	bestDist := dLat*dLat + dLon*dLon

	for _, loc := range testLocations[1:] {
		dLat := lat - loc.Lat
		dLon := lon - loc.Lon
		dist := dLat*dLat + dLon*dLon
		if dist < bestDist {
			bestDist = dist
			best = loc
		}
	}
	return best
}
