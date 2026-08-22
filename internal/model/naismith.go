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
// F001: Stunden bleiben <=23 — ab >=24*60 min wird über Mitternacht GEWICKELT
// (Wrap, Modulo), nicht mehr auf "23:59" geklemmt (Issue #1667 S2).
// Grund für die Bereichsgrenze gilt unverändert: Die Python-Gegenseite
// (_parse_hhmm) kann einen Stunden-Teil >23 nicht konsumieren und fällt sonst
// still auf die divergente Interpolation zurück — das untergräbt das Ziel
// "Editor-Zeit == Wetterabruf-Zeit". Der Wrap ERFÜLLT diese Bedingung (Ausgabe
// weiterhin nur 00:00-23:59), statt sie zu umgehen; die frühere Klemme tat das
// zwar auch, ließ aber mehrere Wegpunkte auf denselben Wert "23:59" fallen, so
// dass der wp_days-Rollover den Tageswechsel nicht mehr erkannte und Segmente
// samt Wetterüberwachung verworfen wurden.
// Kein negativsicherer Modulo (((x%m)+m)%m) nötig: totalMin ist konstruktiv >= 0
// (Startzeit >= 0 plus kumulierte, nie negative Naismith-Minuten). Bitte nicht
// "sicherheitshalber" umbauen.
func formatHHMM(totalMin int) string {
	totalMin %= 24 * 60
	return fmt.Sprintf("%02d:%02d", totalMin/60, totalMin%60)
}

// ComputeStageArrivals setzt Waypoint.ArrivalCalculated für jeden Wegpunkt.
// Start = stage.StartTime (parse "HH:MM") oder Default "08:00".
// arrival[0] = Start; arrival[i] = arrival[i-1] + naismithHours(dist, asc, desc).
// Pausentag (0 Wegpunkte): keine Berechnung, kein Feld.
// sp: Tempoparameter aus ActivitySpeed(trip.Activity).
// measuredSlackKm spiegelt _MEASURED_SLACK_KM der Python-Regel: 10 m Zugabe,
// die die Rundung gespeicherter Werte abfaengt -- nicht mehr.
const measuredSlackKm = 0.01

// stageMeasuredDistances liefert die gemessene Wegstrecke je Wegpunkt, auf den
// Etappenstart normiert -- oder nil, wenn die Etappe als UNVERMESSEN gilt
// (Issue #2082).
//
// Spiegelt Python stage_measured_distances (services/trip_segments.py). Eine
// Etappe ist nur vermessen, wenn
//
//  1. JEDER Wegpunkt einen Wert traegt (0 ist gueltig, fehlend nicht),
//  2. die Werte STRIKT monoton steigen, und
//  3. jede Teilstrecke mindestens so gross ist wie die Luftlinie zwischen den
//     beiden Wegpunkten -- ein Track kann nie kuerzer sein als die direkte
//     Verbindung.
//
// Verletzt EIN Paar die Regel, gilt die GESAMTE Etappe als unvermessen: eine
// teilweise vermessene Etappe waere eine Ankunftszeit, die an einer Stelle
// stimmt und an der naechsten still falsch ist -- und sie widerspraeche der
// Ortsangabe desselben Briefings, die schon je Etappe entscheidet.
func stageMeasuredDistances(wps []Waypoint) []float64 {
	if len(wps) == 0 {
		return nil
	}
	values := make([]float64, len(wps))
	for i, wp := range wps {
		if wp.DistanceFromStartKm == nil {
			return nil
		}
		values[i] = *wp.DistanceFromStartKm
	}
	for i := 0; i < len(values)-1; i++ {
		span := values[i+1] - values[i]
		if span <= 0 { // nicht strikt monoton
			return nil
		}
		luftlinie := haversineKm(wps[i].Lat, wps[i].Lon, wps[i+1].Lat, wps[i+1].Lon)
		if span+measuredSlackKm < luftlinie {
			return nil
		}
	}
	base := values[0]
	out := make([]float64, len(values))
	for i, v := range values {
		out[i] = v - base
	}
	return out
}

func ComputeStageArrivals(stage *Stage, sp ActivitySpeeds) {
	if stage == nil || len(stage.Waypoints) == 0 {
		return
	}
	measured := stageMeasuredDistances(stage.Waypoints)

	cur := float64(parseStartMinutes(stage.StartTime))
	first := formatHHMM(int(math.Round(cur)))
	stage.Waypoints[0].ArrivalCalculated = &first

	for i := 1; i < len(stage.Waypoints); i++ {
		prev, wp := stage.Waypoints[i-1], stage.Waypoints[i]
		var dist float64
		if measured != nil {
			dist = measured[i] - measured[i-1]
		} else {
			dist = haversineKm(prev.Lat, prev.Lon, wp.Lat, wp.Lon)
		}
		dElev := float64(wp.ElevationM - prev.ElevationM)
		asc := math.Max(0, dElev)
		desc := math.Max(0, -dElev)
		cur += naismithHours(dist, asc, desc, sp) * 60.0
		v := formatHHMM(int(math.Round(cur)))
		stage.Waypoints[i].ArrivalCalculated = &v
	}
}
