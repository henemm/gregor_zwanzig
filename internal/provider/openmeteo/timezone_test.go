package openmeteo

import (
	"testing"
)

// =============================================================================
// Test 13: Timezone-Lookup
// =============================================================================

func TestTimezoneForCoords_Vienna_ReturnsEuropeVienna(t *testing.T) {
	// GIVEN: Koordinaten fuer Wien (48.2, 16.37)
	// WHEN: TimezoneForCoords aufgerufen
	// THEN: "Europe/Vienna"
	tz := TimezoneForCoords(48.2, 16.37)
	if tz != "Europe/Vienna" {
		t.Errorf("expected 'Europe/Vienna', got '%s'", tz)
	}
}
