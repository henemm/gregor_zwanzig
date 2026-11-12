package resolver

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type openElevationResponse struct {
	Results []struct {
		Elevation float64 `json:"elevation"`
	} `json:"results"`
}

// elevationLookupURL: fester Anbieter-Endpunkt; nur export_test.go ersetzt ihn
// (netzfreie Kern-Tests, Issue #2961).
var elevationLookupURL = "https://api.open-elevation.com/api/v1/lookup"

// lookupElevation fragt Open-Elevation nach der Höhe für lat/lon.
// Soft-Fail: bei jedem Fehler nil zurückgeben, kein Error an Caller.
func lookupElevation(lat, lon float64) *int {
	url := fmt.Sprintf("%s?locations=%f,%f", elevationLookupURL, lat, lon)

	client := &http.Client{Timeout: 8 * time.Second}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "gregor-zwanzig/1.0")

	resp, err := client.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil
	}

	var data openElevationResponse
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil
	}
	if len(data.Results) == 0 {
		return nil
	}

	ele := int(data.Results[0].Elevation + 0.5)
	return &ele
}
