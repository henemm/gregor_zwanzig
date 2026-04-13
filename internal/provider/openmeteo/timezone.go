package openmeteo

import (
	"sync"

	"github.com/ringsaturn/tzf"
)

var (
	tzFinder     tzf.F
	tzFinderOnce sync.Once
	tzFinderErr  error
)

func TimezoneForCoords(lat, lon float64) string {
	tzFinderOnce.Do(func() {
		tzFinder, tzFinderErr = tzf.NewDefaultFinder()
	})
	if tzFinderErr != nil {
		return "UTC"
	}
	tz := tzFinder.GetTimezoneName(lon, lat)
	if tz == "" {
		return "UTC"
	}
	return tz
}
