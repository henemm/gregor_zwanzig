package model

import (
	"fmt"
	"math"
)

// Issue #296-BE — Naismith-Ankunftszeiten.
// Berechnet pro Wegpunkt eine Ankunftszeit ("HH:MM") nach angepasster
// Naismith's Rule. Spec: docs/specs/modules/issue_296_be_naismith_arrival.md
//
// Tempo-Konstanten gespiegelt aus src/app/models.py EtappenConfig (Single
// Source dort): speed_flat_kmh=4.0, speed_ascent_mh=300.0,
// speed_descent_mh=500.0. Bei Änderung dort: hier nachziehen.
const (
	speedFlatKmh   = 4.0
	speedAscentMh  = 300.0
	speedDescentMh = 500.0

	// earthRadiusKm — mittlerer Erdradius für Haversine.
	earthRadiusKm = 6371.0088

	// defaultStartTime — Fallback-Startzeit einer Stage ohne start_time.
	defaultStartTime = "08:00"
)

// ActivitySpeeds bündelt die drei Tempoparameter einer Aktivität.
// Issue #674: Fahrrad-Stufen (15/20/25 km/h) + Wanderer-Default (4/300/500).
// Querverweis TS: frontend/src/lib/utils/naismith.ts::activityToSpeed.
type ActivitySpeeds struct {
	FlatKmh   float64
	AscentMh  float64
	DescentMh float64
}

// ActivitySpeed liefert die Tempoparameter für eine Trip.Activity.
// Unbekannte oder leere Werte → Wanderer-Default (gespiegelt aus EtappenConfig).
// Fahrrad-Höhenmeter: 600/1000 Hm/h (doppelt so schnell wie Wanderer).
func ActivitySpeed(activity string) ActivitySpeeds {
	switch activity {
	case "fahrrad_15":
		return ActivitySpeeds{FlatKmh: 15.0, AscentMh: 600.0, DescentMh: 1000.0}
	case "fahrrad_20":
		return ActivitySpeeds{FlatKmh: 20.0, AscentMh: 600.0, DescentMh: 1000.0}
	case "fahrrad_25":
		return ActivitySpeeds{FlatKmh: 25.0, AscentMh: 600.0, DescentMh: 1000.0}
	default:
		return ActivitySpeeds{FlatKmh: speedFlatKmh, AscentMh: speedAscentMh, DescentMh: speedDescentMh}
	}
}

// naismithHours: angepasste Naismith's Rule als SUMME (nicht max!).
// Querverweis: src/core/segment_builder.py compute_hiking_time.
func naismithHours(distKm, ascentM, descentM float64, sp ActivitySpeeds) float64 {
	return distKm/sp.FlatKmh + ascentM/sp.AscentMh + descentM/sp.DescentMh
}

// haversineKm berechnet die Großkreis-Distanz in km zwischen zwei lat/lon.
func haversineKm(lat1, lon1, lat2, lon2 float64) float64 {
	rad := math.Pi / 180.0
	dLat := (lat2 - lat1) * rad
	dLon := (lon2 - lon1) * rad
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*rad)*math.Cos(lat2*rad)*math.Sin(dLon/2)*math.Sin(dLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
	return earthRadiusKm * c
}

// parseStartMinutes parst "HH:MM" in Minuten ab Mitternacht; Fehler → Default.
// F002: Eine unsinnige Startzeit (Stunde >23 ODER Minute >59, z.B. "99:99")
// fällt ebenfalls auf den Default zurück, statt den Unsinn zu übernehmen.
func parseStartMinutes(startTime *string) int {
	s := defaultStartTime
	if startTime != nil && *startTime != "" {
		s = *startTime
	}
	var h, m int
	if _, err := fmt.Sscanf(s, "%d:%d", &h, &m); err != nil || h > 23 || h < 0 || m > 59 || m < 0 {
		fmt.Sscanf(defaultStartTime, "%d:%d", &h, &m)
	}
	return h*60 + m
}

// formatHHMM formatiert Minuten ab Mitternacht als "HH:MM".
// F001: Stunden werden auf <=23 begrenzt (Clamp auf "23:59" ab >=24*60 min).
// Grund: Die Python-Gegenseite (_parse_hhmm) kann einen Stunden-Teil >23 nicht
// konsumieren und fällt sonst still auf die divergente Interpolation zurück —
// das untergräbt das Ziel "Editor-Zeit == Wetterabruf-Zeit". Der Clamp hält den
// Wert cross-layer konsistent. Eine >24h-Etappe ist ohnehin Known Limitation
// (siehe Spec §2, Etappen sind Tagesabschnitte).
func formatHHMM(totalMin int) string {
	const maxMin = 24*60 - 1 // "23:59"
	if totalMin > maxMin {
		totalMin = maxMin
	}
	return fmt.Sprintf("%02d:%02d", totalMin/60, totalMin%60)
}

// ComputeStageArrivals setzt Waypoint.ArrivalCalculated für jeden Wegpunkt.
// Start = stage.StartTime (parse "HH:MM") oder Default "08:00".
// arrival[0] = Start; arrival[i] = arrival[i-1] + naismithHours(dist, asc, desc).
// Pausentag (0 Wegpunkte): keine Berechnung, kein Feld.
// sp: Tempoparameter aus ActivitySpeed(trip.Activity).
func ComputeStageArrivals(stage *Stage, sp ActivitySpeeds) {
	if stage == nil || len(stage.Waypoints) == 0 {
		return
	}
	cur := float64(parseStartMinutes(stage.StartTime))
	first := formatHHMM(int(math.Round(cur)))
	stage.Waypoints[0].ArrivalCalculated = &first

	for i := 1; i < len(stage.Waypoints); i++ {
		prev, wp := stage.Waypoints[i-1], stage.Waypoints[i]
		dist := haversineKm(prev.Lat, prev.Lon, wp.Lat, wp.Lon)
		dElev := float64(wp.ElevationM - prev.ElevationM)
		asc := math.Max(0, dElev)
		desc := math.Max(0, -dElev)
		cur += naismithHours(dist, asc, desc, sp) * 60.0
		v := formatHHMM(int(math.Round(cur)))
		stage.Waypoints[i].ArrivalCalculated = &v
	}
}
