package resolver

import (
	"encoding/xml"
	"math"
	"regexp"
	"strconv"
	"strings"
)

// ---- Bereichsprüfung ----

func inRange(lat, lon float64) bool {
	return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180
}

// ---- Dezimal ----

func resolveDecimal(input string) (ResolveResult, error) {
	m := reDecimal.FindStringSubmatch(strings.TrimSpace(input))
	if m == nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "Konnte Dezimalkoordinaten nicht erkennen."}
	}
	lat, err1 := strconv.ParseFloat(m[1], 64)
	lon, err2 := strconv.ParseFloat(m[2], 64)
	if err1 != nil || err2 != nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "Dezimalkoordinaten konnten nicht geparst werden."}
	}
	if !inRange(lat, lon) {
		return ResolveResult{}, &ResolveError{
			Code:    "unknown_format",
			Message: "Koordinaten ausserhalb des gültigen Bereichs (lat ∈ [-90,90], lon ∈ [-180,180]).",
		}
	}
	return finalize(ResolveResult{Lat: lat, Lon: lon, SourceType: "decimal"}, true), nil
}

// ---- DMS ----

var reDMS = regexp.MustCompile(`(\d+)°\s*(\d+)['′]\s*([\d.]+)["″]?\s*([NS])\s*[, ]?\s*(\d+)°\s*(\d+)['′]\s*([\d.]+)["″]?\s*([EW])`)

func resolveDMS(input string) (ResolveResult, error) {
	m := reDMS.FindStringSubmatch(input)
	if m == nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "DMS-Format nicht erkannt."}
	}

	latD, _ := strconv.ParseFloat(m[1], 64)
	latM, _ := strconv.ParseFloat(m[2], 64)
	latS, _ := strconv.ParseFloat(m[3], 64)
	latHem := m[4]

	lonD, _ := strconv.ParseFloat(m[5], 64)
	lonM, _ := strconv.ParseFloat(m[6], 64)
	lonS, _ := strconv.ParseFloat(m[7], 64)
	lonHem := m[8]

	lat := latD + latM/60 + latS/3600
	lon := lonD + lonM/60 + lonS/3600
	if latHem == "S" {
		lat = -lat
	}
	if lonHem == "W" {
		lon = -lon
	}

	if !inRange(lat, lon) {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "DMS-Koordinaten ausserhalb des gültigen Bereichs."}
	}
	return finalize(ResolveResult{Lat: lat, Lon: lon, SourceType: "dms"}, true), nil
}

// ---- UTM (WGS84) ----

var reUTMParse = regexp.MustCompile(`(\d{1,2})([A-Z])\s+(\d{4,7})\s+(\d{4,7})`)

func resolveUTM(input string) (ResolveResult, error) {
	m := reUTMParse.FindStringSubmatch(input)
	if m == nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "UTM-Format nicht erkannt."}
	}

	zone, err := strconv.Atoi(m[1])
	if err != nil || zone < 1 || zone > 60 {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "UTM-Zone ausserhalb [1,60]."}
	}
	band := m[2]
	if band == "I" || band == "O" || band < "C" || band > "X" {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "UTM-Band ungültig."}
	}
	easting, err := strconv.ParseFloat(m[3], 64)
	if err != nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "Easting nicht parsebar."}
	}
	northing, err := strconv.ParseFloat(m[4], 64)
	if err != nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "Northing nicht parsebar."}
	}

	northern := band >= "N"
	lat, lon := utmToLatLon(zone, easting, northing, northern)

	if !inRange(lat, lon) {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "UTM-Konvertierung lieferte ungültige Koordinaten."}
	}
	return finalize(ResolveResult{Lat: lat, Lon: lon, SourceType: "utm"}, true), nil
}

// utmToLatLon konvertiert UTM-Koordinaten (WGS84) in Lat/Lon.
// Vereinfachte Standardformel — ausreichend für Smart-Import-Vorschau (Toleranz ~1m).
func utmToLatLon(zone int, easting, northing float64, northern bool) (float64, float64) {
	const (
		a    = 6378137.0           // WGS84 semi-major axis
		e2   = 0.00669437999014    // WGS84 eccentricity squared
		k0   = 0.9996              // UTM scale factor
		falseEasting  = 500000.0
		falseNorthing = 10000000.0
	)
	ep2 := e2 / (1 - e2)

	x := easting - falseEasting
	y := northing
	if !northern {
		y -= falseNorthing
	}

	lonOrigin := float64(zone*6-183) * math.Pi / 180

	M := y / k0
	mu := M / (a * (1 - e2/4 - 3*e2*e2/64 - 5*e2*e2*e2/256))

	e1 := (1 - math.Sqrt(1-e2)) / (1 + math.Sqrt(1-e2))

	phi1 := mu +
		(3*e1/2-27*e1*e1*e1/32)*math.Sin(2*mu) +
		(21*e1*e1/16-55*e1*e1*e1*e1/32)*math.Sin(4*mu) +
		(151*e1*e1*e1/96)*math.Sin(6*mu)

	sinPhi1 := math.Sin(phi1)
	cosPhi1 := math.Cos(phi1)
	tanPhi1 := math.Tan(phi1)

	N1 := a / math.Sqrt(1-e2*sinPhi1*sinPhi1)
	T1 := tanPhi1 * tanPhi1
	C1 := ep2 * cosPhi1 * cosPhi1
	R1 := a * (1 - e2) / math.Pow(1-e2*sinPhi1*sinPhi1, 1.5)
	D := x / (N1 * k0)

	latRad := phi1 - (N1*tanPhi1/R1)*(D*D/2-
		(5+3*T1+10*C1-4*C1*C1-9*ep2)*D*D*D*D/24+
		(61+90*T1+298*C1+45*T1*T1-252*ep2-3*C1*C1)*D*D*D*D*D*D/720)

	lonRad := lonOrigin + (D-
		(1+2*T1+C1)*D*D*D/6+
		(5-2*C1+28*T1-3*C1*C1+8*ep2+24*T1*T1)*D*D*D*D*D/120)/cosPhi1

	return latRad * 180 / math.Pi, lonRad * 180 / math.Pi
}

// ---- GPX ----

type gpxTrkpt struct {
	Lat  float64 `xml:"lat,attr"`
	Lon  float64 `xml:"lon,attr"`
	Ele  *string `xml:"ele,omitempty"`
	Name string  `xml:"name,omitempty"`
}

func resolveGPX(input string) (ResolveResult, error) {
	// Substring extrahieren der das <trkpt>-Element umschließt
	start := strings.Index(input, "<trkpt")
	end := strings.Index(input, "</trkpt>")
	var snippet string
	if start >= 0 && end > start {
		snippet = input[start : end+len("</trkpt>")]
	} else if start >= 0 && strings.Contains(input[start:], "/>") {
		// self-closed
		closing := strings.Index(input[start:], "/>")
		snippet = input[start : start+closing+2]
	} else {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "GPX-Wegpunkt nicht erkannt."}
	}

	var pt gpxTrkpt
	if err := xml.Unmarshal([]byte(snippet), &pt); err != nil {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "GPX-Wegpunkt konnte nicht geparst werden."}
	}
	if !inRange(pt.Lat, pt.Lon) {
		return ResolveResult{}, &ResolveError{Code: "unknown_format", Message: "GPX-Koordinaten ausserhalb des gültigen Bereichs."}
	}

	result := ResolveResult{
		Lat:           pt.Lat,
		Lon:           pt.Lon,
		SuggestedName: pt.Name,
		SourceType:    "gpx",
	}
	if pt.Ele != nil {
		if f, err := strconv.ParseFloat(strings.TrimSpace(*pt.Ele), 64); err == nil {
			ele := int(f + 0.5)
			result.ElevationM = &ele
		}
	}
	return finalize(result, false), nil
}
