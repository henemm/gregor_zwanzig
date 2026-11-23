package resolver

// Freitext-Ortssuche fuer den MCP-Konnektor „Gregor Wetter“ (Issue #3281,
// Scheibe 1; SPEC docs/specs/modules/mcp_wetter_konnektor.md).
//
// Nominatim wird ueber den abgeschotteten Client (newLinkClient, ADR-0114)
// gefragt: kein Proxy aus der Umgebung, Adresssperre am Dialer, Staging-
// Egress-Waechter, Weiterleitungen nur als Antwort. Die Eingabe geht nur als
// Wert des Parameters q hinaus, nie als Pfad.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/henemm/gregor-api/internal/provider/openmeteo"
)

const (
	// OrtsucheMaxKandidaten: hoechstens so viele Kandidaten je Suche.
	OrtsucheMaxKandidaten = 5
	// OrtsucheMaxZeichen begrenzt die Eingabe (Ortsnamen samt Zusatz).
	OrtsucheMaxZeichen = 120
	// ortsucheGleicherOrtKm: Fundstellen naeher als das gelten als derselbe Ort.
	ortsucheGleicherOrtKm = 5.0
	ortsucheTimeout       = 10 * time.Second
	ortsucheMaxAntwort    = 1 << 20
)

var (
	ErrOrtEingabe        = errors.New("ortssuche: eingabe leer oder zu lang")
	ErrOrtssucheGestoert = errors.New("ortssuche: anbieter nicht erreichbar")
	ErrOrtUnbekannt      = errors.New("ortssuche: ort unbekannt")
	ErrOrtMehrdeutig     = errors.New("ortssuche: ort mehrdeutig")
)

// OrtKandidat ist ein Treffer der Ortssuche.
type OrtKandidat struct {
	Name        string  `json:"name"`
	Anzeigename string  `json:"anzeigename"`
	Land        string  `json:"land"`
	Lat         float64 `json:"lat"`
	Lon         float64 `json:"lon"`
	Zeitzone    string  `json:"zeitzone"`
}

type nominatimTreffer struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Lat         string `json:"lat"`
	Lon         string `json:"lon"`
	Address     struct {
		Country string `json:"country"`
	} `json:"address"`
}

// OrtSuchen fragt Nominatim per Freitext und liefert hoechstens
// OrtsucheMaxKandidaten verschiedene Orte (Reihenfolge des Anbieters, nahe
// Doppelfunde zusammengefasst). Kein Treffer ist kein Fehler: leere Liste.
func OrtSuchen(ctx context.Context, text, sprache string) ([]OrtKandidat, error) {
	text = strings.TrimSpace(text)
	if text == "" || utf8.RuneCountInString(text) > OrtsucheMaxZeichen {
		return nil, ErrOrtEingabe
	}
	frage := url.Values{}
	frage.Set("q", text)
	frage.Set("format", "jsonv2")
	frage.Set("addressdetails", "1")
	frage.Set("limit", strconv.Itoa(OrtsucheMaxKandidaten))
	if sprache != "" {
		frage.Set("accept-language", sprache)
	}
	treffer, err := nominatimAbfragen(ctx, nominatimSearchURL+"?"+frage.Encode())
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrOrtssucheGestoert, err)
	}
	return kandidatenAus(treffer), nil
}

func nominatimAbfragen(ctx context.Context, ziel string) ([]nominatimTreffer, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, ziel, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "gregor-zwanzig/1.0")
	req.Header.Set("Accept", "application/json")
	resp, err := newLinkClient(ortsucheTimeout).Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	var treffer []nominatimTreffer
	if err := json.NewDecoder(io.LimitReader(resp.Body, ortsucheMaxAntwort)).Decode(&treffer); err != nil {
		return nil, err
	}
	return treffer, nil
}

func kandidatenAus(treffer []nominatimTreffer) []OrtKandidat {
	kandidaten := []OrtKandidat{}
	for _, t := range treffer {
		lat, err1 := strconv.ParseFloat(t.Lat, 64)
		lon, err2 := strconv.ParseFloat(t.Lon, 64)
		if err1 != nil || err2 != nil || !inRange(lat, lon) || schonGefunden(kandidaten, lat, lon) {
			continue
		}
		name := t.Name
		if name == "" {
			name = t.DisplayName
		}
		kandidaten = append(kandidaten, OrtKandidat{
			Name: name, Anzeigename: t.DisplayName, Land: t.Address.Country,
			Lat: lat, Lon: lon, Zeitzone: openmeteo.TimezoneForCoords(lat, lon),
		})
		if len(kandidaten) == OrtsucheMaxKandidaten {
			break
		}
	}
	return kandidaten
}

func schonGefunden(kandidaten []OrtKandidat, lat, lon float64) bool {
	for _, k := range kandidaten {
		if abstandKm(k.Lat, k.Lon, lat, lon) < ortsucheGleicherOrtKm {
			return true
		}
	}
	return false
}

// abstandKm: Grosskreisabstand (Haversine).
func abstandKm(lat1, lon1, lat2, lon2 float64) float64 {
	const erdradiusKm = 6371.0
	rad := math.Pi / 180
	dLat, dLon := (lat2-lat1)*rad, (lon2-lon1)*rad
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*rad)*math.Cos(lat2*rad)*math.Sin(dLon/2)*math.Sin(dLon/2)
	return 2 * erdradiusKm * math.Asin(math.Sqrt(a))
}

// OrtEindeutig entscheidet, ob die Suche genau einen Ort ergab. Mehrere
// Kandidaten heissen: nachfragen statt raten (AC-13); keiner: ErrOrtUnbekannt.
func OrtEindeutig(kandidaten []OrtKandidat) (OrtKandidat, error) {
	switch len(kandidaten) {
	case 0:
		return OrtKandidat{}, ErrOrtUnbekannt
	case 1:
		return kandidaten[0], nil
	}
	return OrtKandidat{}, ErrOrtMehrdeutig
}
