package resolver_test

// Freitext-Ortssuche fuer den MCP-Konnektor (Issue #3281, Scheibe 1).
// SPEC: docs/specs/modules/mcp_wetter_konnektor.md (AC-12, AC-13, Ortssuche).
//
// Netzfrei: Nominatim wird durch einen lokalen httptest-Server mit
// aufgezeichneten Antworten (testdata/nominatim_ortssuche_*.json, abgerufen am
// 2026-11-22, accept-language=de) vertreten. Kein Mock: die echte
// OrtSuchen-Funktion spricht ueber den abgeschotteten Client mit dem Server.

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/resolver"
)

// nominatimFixture beantwortet /search je Suchtext mit einer aufgezeichneten
// Antwort und merkt sich jede empfangene Anfrage.
type nominatimFixture struct {
	srv     *httptest.Server
	mu      sync.Mutex
	anfrage []*url.URL
}

func ladeTestdata(t *testing.T, name string) []json.RawMessage {
	t.Helper()
	roh, err := os.ReadFile("testdata/" + name)
	if err != nil {
		t.Fatalf("Fixture %s fehlt: %v", name, err)
	}
	var liste []json.RawMessage
	if err := json.Unmarshal(roh, &liste); err != nil {
		t.Fatalf("Fixture %s unlesbar: %v", name, err)
	}
	return liste
}

func neueNominatimFixture(t *testing.T, status int) *nominatimFixture {
	t.Helper()
	antworten := map[string][]json.RawMessage{
		"Frankfurt am Main": ladeTestdata(t, "nominatim_ortssuche_frankfurt_am_main.json"),
		"Frankfurt":         ladeTestdata(t, "nominatim_ortssuche_frankfurt.json"),
		"Neustadt":          ladeTestdata(t, "nominatim_ortssuche_neustadt.json"),
		// Sieben verschiedene Orte (Muenster + Frankfurt): mehr, als die
		// Ortssuche je weitergeben darf.
		// Synthetisch: zwei Fundstellen 3 km bzw. 10 km auseinander
		// (0,027 bzw. 0,09 Grad Breite) und unbrauchbare Koordinaten.
		"Nah": {
			json.RawMessage(`{"name":"Nah A","lat":"47.000","lon":"11.0","address":{"country":"Oesterreich"}}`),
			json.RawMessage(`{"name":"Nah B","lat":"47.027","lon":"11.0","address":{"country":"Oesterreich"}}`),
		},
		"Fern": {
			json.RawMessage(`{"name":"Fern A","lat":"47.000","lon":"11.0","address":{"country":"Oesterreich"}}`),
			json.RawMessage(`{"name":"Fern B","lat":"47.090","lon":"11.0","address":{"country":"Oesterreich"}}`),
		},
		"Kaputt": {
			json.RawMessage(`{"name":"NaN","lat":"NaN","lon":"11.0"}`),
			json.RawMessage(`{"name":"Nord","lat":"95.0","lon":"11.0"}`),
			json.RawMessage(`{"name":"Ost","lat":"47.0","lon":"200.0"}`),
			json.RawMessage(`{"name":"Leer","lat":"","lon":"11.0"}`),
			json.RawMessage(`{"name":"Gut","lat":"47.0","lon":"11.0","address":{"country":"Oesterreich"}}`),
		},
		"Viele": append(ladeTestdata(t, "nominatim_ortssuche_muenster.json"),
			ladeTestdata(t, "nominatim_ortssuche_frankfurt.json")...),
	}
	f := &nominatimFixture{}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		f.anfrage = append(f.anfrage, r.URL)
		f.mu.Unlock()
		if status != http.StatusOK {
			w.WriteHeader(status)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		liste, ok := antworten[r.URL.Query().Get("q")]
		if !ok {
			liste = []json.RawMessage{}
		}
		json.NewEncoder(w).Encode(liste)
	}))
	t.Cleanup(f.srv.Close)
	resolver.NominatimAuf(t, f.srv.URL+"/search")
	return f
}

func (f *nominatimFixture) anfragen() []*url.URL {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]*url.URL(nil), f.anfrage...)
}

func nahe(a, b float64) bool { return math.Abs(a-b) < 1e-6 }

func TestOrtSuchen_EindeutigerOrt_LiefertNameLandKoordinatenZeitzone(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Frankfurt am Main", "de")
	if err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	ort, err := resolver.OrtEindeutig(kandidaten)
	if err != nil {
		t.Fatalf("Frankfurt am Main muss eindeutig sein, bekam %v (%+v)", err, kandidaten)
	}
	if ort.Name != "Frankfurt am Main" || ort.Land != "Deutschland" {
		t.Errorf("Name/Land falsch: %+v", ort)
	}
	if !nahe(ort.Lat, 50.1106444) || !nahe(ort.Lon, 8.6820917) {
		t.Errorf("Koordinaten falsch: %v/%v", ort.Lat, ort.Lon)
	}
	if ort.Zeitzone != "Europe/Berlin" {
		t.Errorf("Zeitzone: erwartet Europe/Berlin, bekam %q", ort.Zeitzone)
	}
	if !strings.Contains(ort.Anzeigename, "Hessen") {
		t.Errorf("Anzeigename soll die Region nennen, bekam %q", ort.Anzeigename)
	}
}

func TestOrtSuchen_MehrdeutigerOrt_NenntKandidatenStattZuRaten(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Frankfurt", "de")
	if err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	if len(kandidaten) != 2 {
		t.Fatalf("erwartet 2 Kandidaten, bekam %d: %+v", len(kandidaten), kandidaten)
	}
	if _, err := resolver.OrtEindeutig(kandidaten); !errors.Is(err, resolver.ErrOrtMehrdeutig) {
		t.Errorf("AC-13: mehrdeutig erwartet, bekam %v", err)
	}
	oder := kandidaten[1]
	if oder.Name != "Frankfurt (Oder)" || oder.Land != "Deutschland" ||
		!nahe(oder.Lat, 52.3412273) || !nahe(oder.Lon, 14.549452) || oder.Zeitzone != "Europe/Berlin" {
		t.Errorf("zweiter Kandidat unvollstaendig: %+v", oder)
	}
}

func TestOrtSuchen_UnbekannterOrt_KeineKandidatenUndFehler(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Xqzzyvlorptown", "de")
	if err != nil {
		t.Fatalf("leeres Ergebnis ist kein Stoerfall: %v", err)
	}
	if len(kandidaten) != 0 {
		t.Fatalf("keine erfundenen Kandidaten erwartet: %+v", kandidaten)
	}
	if _, err := resolver.OrtEindeutig(kandidaten); !errors.Is(err, resolver.ErrOrtUnbekannt) {
		t.Errorf("AC-12: ErrOrtUnbekannt erwartet, bekam %v", err)
	}
}

func TestOrtSuchen_HoechstensFuenfKandidaten(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	f := neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Viele", "de")
	if err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	if len(kandidaten) != 5 {
		t.Errorf("hoechstens 5 Kandidaten erwartet (Server lieferte 7), bekam %d", len(kandidaten))
	}
	if q := f.anfragen()[0].Query(); q.Get("limit") != "5" {
		t.Errorf("Anfrage soll limit=5 tragen, bekam %q", q.Get("limit"))
	}
}

func TestOrtSuchen_DoppelteFundstellenDesselbenOrtsWerdenZusammengefasst(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	// Neustadt: zwei Fundstellen in Prag liegen ~200 m auseinander.
	kandidaten, err := resolver.OrtSuchen(context.Background(), "Neustadt", "de")
	if err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	if len(kandidaten) != 4 {
		t.Errorf("erwartet 4 verschiedene Orte, bekam %d: %+v", len(kandidaten), kandidaten)
	}
}

func TestOrtSuchen_EingabeAlsFreitextKodiert(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	f := neueNominatimFixture(t, http.StatusOK)

	text := "../../admin?x=1&format=xml#frag"
	if _, err := resolver.OrtSuchen(context.Background(), text, "en"); err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	anfragen := f.anfragen()
	if len(anfragen) != 1 {
		t.Fatalf("genau eine Anfrage erwartet, bekam %d", len(anfragen))
	}
	u := anfragen[0]
	if u.Path != "/search" {
		t.Errorf("Eingabe darf den Pfad nicht veraendern, bekam %q", u.Path)
	}
	q := u.Query()
	if q.Get("q") != text || q.Get("format") != "jsonv2" || q.Get("accept-language") != "en" {
		t.Errorf("Anfrage-Parameter falsch: %v", q)
	}
}

func TestOrtSuchen_LeereOderZuLangeEingabe_OhneAbruf(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	f := neueNominatimFixture(t, http.StatusOK)

	for _, text := range []string{"", "   ", strings.Repeat("ä", 121)} {
		if _, err := resolver.OrtSuchen(context.Background(), text, "de"); !errors.Is(err, resolver.ErrOrtEingabe) {
			t.Errorf("Eingabe %q: ErrOrtEingabe erwartet, bekam %v", text, err)
		}
	}
	if n := len(f.anfragen()); n != 0 {
		t.Errorf("ungueltige Eingaben duerfen Nominatim nicht erreichen, %d Anfragen", n)
	}
	// 120 Zeichen sind noch erlaubt.
	if _, err := resolver.OrtSuchen(context.Background(), strings.Repeat("ä", 120), "de"); err != nil {
		t.Errorf("120 Zeichen muessen erlaubt sein: %v", err)
	}
}

func TestOrtSuchen_AnbieterStoerung_IstFehlerOhneKandidaten(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusInternalServerError)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Frankfurt", "de")
	if !errors.Is(err, resolver.ErrOrtssucheGestoert) || len(kandidaten) != 0 {
		t.Errorf("Stoerung erwartet, bekam %v / %+v", err, kandidaten)
	}
}

// Die Ortssuche laeuft ueber den abgeschotteten Client (ADR-0114): ohne
// Freigabe der Loopback-Adresse erreicht sie den lokalen Server nicht.
func TestOrtSuchen_LaeuftUeberAbgeschottetenClient(t *testing.T) {
	f := neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Frankfurt am Main", "de")
	if !errors.Is(err, resolver.ErrOrtssucheGestoert) || len(kandidaten) != 0 {
		t.Errorf("Loopback-Ziel muss gesperrt sein, bekam %v / %+v", err, kandidaten)
	}
	if n := len(f.anfragen()); n != 0 {
		t.Errorf("gesperrtes Ziel darf nicht erreicht werden, %d Anfragen", n)
	}
}

func TestOrtSuchen_GrenzeGleicherOrt_DreiKmZusammenZehnKmGetrennt(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	nah, err := resolver.OrtSuchen(context.Background(), "Nah", "de")
	if err != nil || len(nah) != 1 || nah[0].Name != "Nah A" {
		t.Errorf("3 km: ein Ort (der erste) erwartet, bekam %v / %+v", err, nah)
	}
	fern, err := resolver.OrtSuchen(context.Background(), "Fern", "de")
	if err != nil || len(fern) != 2 {
		t.Errorf("10 km: zwei Orte erwartet, bekam %v / %+v", err, fern)
	}
}

func TestOrtSuchen_UnbrauchbareKoordinatenWerdenVerworfen(t *testing.T) {
	resolver.ErlaubeLoopbackVerbindung(t)
	neueNominatimFixture(t, http.StatusOK)

	kandidaten, err := resolver.OrtSuchen(context.Background(), "Kaputt", "de")
	if err != nil {
		t.Fatalf("Ortssuche fehlgeschlagen: %v", err)
	}
	if len(kandidaten) != 1 || kandidaten[0].Name != "Gut" {
		t.Errorf("nur der Fund mit gueltigen Koordinaten darf bleiben: %+v", kandidaten)
	}
}
