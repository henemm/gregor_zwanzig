package handler

// TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe)
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md (AC-2, AC-4, AC-5, AC-8)
//
// Etappen-PUT (PUT /api/trips/{id} mit "stages") traegt je Etappe das
// optionale grundtempo_kmh. Gueltig 0.5..60, sonst 422 und nichts
// gespeichert (auch beim Anlege-POST). Gesetzt -> SaveTrip rechnet die
// Ankuenfte NUR dieser Etappe neu; weggelassen -> Feld entfernt.
// Zwei Nutzer: A aendert nur seinen Trip.
//
// Ausfuehrung: go test ./internal/handler/ -run 'TestStageTempo3197' -v

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Zwei Etappen wie die Falltabelle (je 0/4/8 km, 1000/1600/1000 m), Trip zu Fuss 4 km/h.
func stagesJSON3197(s1Extra, s2Extra string) string {
	wps := func(p string) string {
		return `[{"id":"` + p + `A","name":"A","lat":47,"lon":11,"elevation_m":1000,"distance_from_start_km":0},` +
			`{"id":"` + p + `B","name":"B","lat":47,"lon":11,"elevation_m":1600,"distance_from_start_km":4},` +
			`{"id":"` + p + `C","name":"C","lat":47,"lon":11,"elevation_m":1000,"distance_from_start_km":8}]`
	}
	return `[{"id":"S1","name":"Tag 1","date":"2026-07-01"` + s1Extra + `,"waypoints":` + wps("S1") + `},` +
		`{"id":"S2","name":"Tag 2","date":"2026-07-02"` + s2Extra + `,"waypoints":` + wps("S2") + `}]`
}

func seedStageTempoTrip(t *testing.T, s *store.Store, user, id string) {
	t.Helper()
	w := doReq(CreateTripHandler(s, ""), http.MethodPost, "/api/trips",
		`{"id":"`+id+`","name":"Etappen-Tempo","region":"Mallorca","tempo":{"fortbewegung":"fuss","grundtempo_kmh":4},"stages":`+
			stagesJSON3197("", "")+`}`, "", user)
	if w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Seed %s/%s: %d %s", user, id, w.Code, w.Body.String())
	}
}

func ank3197(st model.Stage) string {
	parts := make([]string, 0, len(st.Waypoints))
	for _, wp := range st.Waypoints {
		if wp.ArrivalCalculated == nil {
			parts = append(parts, "-")
		} else {
			parts = append(parts, *wp.ArrivalCalculated)
		}
	}
	return strings.Join(parts, ",")
}

// AC-2/AC-5: PUT mit grundtempo_kmh=3 an S2 -> nur S2 neu gerechnet, Feld
// bleibt nach GET, uebrige Trip-Felder unveraendert.
func TestStageTempo3197_PutSetztNurDieseEtappe(t *testing.T) {
	s := newTestStore(t)
	seedStageTempoTrip(t, s, "userA", "t1")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t1", "userA", `{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":3`)+`}`)

	tr := ladeTempoTrip(t, s, "userA", "t1")
	if len(tr.Stages) != 2 {
		t.Fatalf("Etappen verloren: %d", len(tr.Stages))
	}
	if tr.Stages[1].GrundtempoKmh == nil || *tr.Stages[1].GrundtempoKmh != 3 {
		t.Fatalf("S2: grundtempo_kmh nicht gespeichert: %v", tr.Stages[1].GrundtempoKmh)
	}
	if tr.Stages[0].GrundtempoKmh != nil {
		t.Errorf("S1: grundtempo_kmh darf nicht entstehen")
	}
	if got := ank3197(tr.Stages[0]); got != "08:00,10:30,12:12" {
		t.Errorf("S1 muss beim Trip-Tempo bleiben, bekommen %s", got)
	}
	if got := ank3197(tr.Stages[1]); got != "08:00,11:20,13:36" {
		t.Errorf("S2 mit 3 km/h: erwartet 08:00,11:20,13:36, bekommen %s", got)
	}
	if tr.Name != "Etappen-Tempo" || tr.Region != "Mallorca" || tr.Tempo == nil ||
		tr.Tempo.Fortbewegung != "fuss" || tr.Tempo.GrundtempoKmh != 4 {
		t.Errorf("Trip-Felder veraendert: name=%q region=%q tempo=%+v", tr.Name, tr.Region, tr.Tempo)
	}
}

// AC-4: Zuruecknehmen -- Etappen ohne grundtempo_kmh -> Feld entfernt, S2 wie Trip-Tempo.
func TestStageTempo3197_PutOhneFeldNimmtZurueck(t *testing.T) {
	s := newTestStore(t)
	seedStageTempoTrip(t, s, "userA", "t2")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t2", "userA", `{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":3`)+`}`)
	putOK(t, r, "/api/trips/t2", "userA", `{"stages":`+stagesJSON3197("", "")+`}`)

	tr := ladeTempoTrip(t, s, "userA", "t2")
	if tr.Stages[1].GrundtempoKmh != nil {
		t.Errorf("S2: Feld nach Zuruecknehmen noch da: %v", *tr.Stages[1].GrundtempoKmh)
	}
	if got := ank3197(tr.Stages[1]); got != "08:00,10:30,12:12" {
		t.Errorf("S2 nach Zuruecknehmen: erwartet Trip-Tempo, bekommen %s", got)
	}
	raw, _ := os.ReadFile(filepath.Join(s.WithUser("userA").BriefingsDir(), "t2.json"))
	if len(raw) > 0 && strings.Count(string(raw), "grundtempo_kmh") != 1 {
		t.Errorf("auf der Platte steht noch ein Etappenwert: %s", raw)
	}
}

// AC-8: ungueltiger Etappenwert -> 422, Bestand unveraendert (PUT und POST).
func TestStageTempo3197_Ungueltig422(t *testing.T) {
	for _, wert := range []string{"0", "0.4", "60.5", "61", "-3", "1e-320", `"3"`, "true"} {
		t.Run("PUT "+wert, func(t *testing.T) {
			s := newTestStore(t)
			seedStageTempoTrip(t, s, "userA", "t3")
			r := briefingVergleichEtagRouter(s)
			w := doReq(r, http.MethodPut, "/api/trips/t3",
				`{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":`+wert)+`}`, "", "userA")
			// Fix-Loop 1 (F001, AC-8): auch kein Zahlwert ("3", true) -> exakt 422.
			if w.Code != http.StatusUnprocessableEntity {
				t.Errorf("erwartet 422, bekommen %d: %s", w.Code, w.Body.String())
			}
			tr := ladeTempoTrip(t, s, "userA", "t3")
			if tr.Stages[1].GrundtempoKmh != nil || ank3197(tr.Stages[1]) != "08:00,10:30,12:12" {
				t.Errorf("Bestand nach abgelehntem PUT veraendert: %v %s", tr.Stages[1].GrundtempoKmh, ank3197(tr.Stages[1]))
			}
		})
		t.Run("POST "+wert, func(t *testing.T) {
			s := newTestStore(t)
			w := doReq(CreateTripHandler(s, ""), http.MethodPost, "/api/trips",
				`{"id":"neu","name":"Neu","tempo":{"fortbewegung":"fuss","grundtempo_kmh":4},"stages":`+
					stagesJSON3197("", `,"grundtempo_kmh":`+wert)+`}`, "", "userA")
			if w.Code != http.StatusUnprocessableEntity {
				t.Errorf("erwartet 422, bekommen %d", w.Code)
			}
			if tr, _ := s.WithUser("userA").LoadTrip("neu"); tr != nil {
				t.Errorf("abgelehnter Trip trotzdem gespeichert")
			}
		})
	}
}

// Fix-Loop 2 (Anlegen = Bearbeiten): der Anlege-POST mit grundtempo_kmh=3 an S2
// speichert das Feld und rechnet arrival_calculated je Etappe; Nutzer B (gleiche
// Trip-ID) bleibt unberuehrt.
func TestStageTempo3197_PostSpeichertUndRechnetJeEtappe(t *testing.T) {
	s := newTestStore(t)
	seedStageTempoTrip(t, s, "userB", "neu")
	w := doReq(CreateTripHandler(s, ""), http.MethodPost, "/api/trips",
		`{"id":"neu","name":"Neu","tempo":{"fortbewegung":"fuss","grundtempo_kmh":4},"stages":`+
			stagesJSON3197("", `,"grundtempo_kmh":3`)+`}`, "", "userA")
	if w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("POST: %d %s", w.Code, w.Body.String())
	}
	tr := ladeTempoTrip(t, s, "userA", "neu")
	if tr.Stages[1].GrundtempoKmh == nil || *tr.Stages[1].GrundtempoKmh != 3 {
		t.Fatalf("S2: grundtempo_kmh beim Anlegen verloren: %v", tr.Stages[1].GrundtempoKmh)
	}
	if tr.Stages[0].GrundtempoKmh != nil {
		t.Errorf("S1: grundtempo_kmh darf nicht entstehen")
	}
	if got := ank3197(tr.Stages[0]); got != "08:00,10:30,12:12" {
		t.Errorf("S1 muss beim Trip-Tempo bleiben, bekommen %s", got)
	}
	if got := ank3197(tr.Stages[1]); got != "08:00,11:20,13:36" {
		t.Errorf("S2 mit 3 km/h: erwartet 08:00,11:20,13:36, bekommen %s", got)
	}
	if b := ladeTempoTrip(t, s, "userB", "neu"); b.Stages[1].GrundtempoKmh != nil ||
		ank3197(b.Stages[1]) != "08:00,10:30,12:12" {
		t.Errorf("B: Trip durch A-POST veraendert: %s", ank3197(b.Stages[1]))
	}
}

// Grenzen 0.5 und 60 sind gueltig.
func TestStageTempo3197_GrenzenGueltig(t *testing.T) {
	for _, wert := range []string{"0.5", "60"} {
		s := newTestStore(t)
		seedStageTempoTrip(t, s, "userA", "t4")
		r := briefingVergleichEtagRouter(s)
		putOK(t, r, "/api/trips/t4", "userA", `{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":`+wert)+`}`)
		if tr := ladeTempoTrip(t, s, "userA", "t4"); tr.Stages[1].GrundtempoKmh == nil {
			t.Errorf("Grenzwert %s nicht gespeichert", wert)
		}
	}
}

// Fix-Loop 4 (F006, AC-5): PUT nur mit "tempo" (ohne "stages") aendert das
// Trip-Tempo, darf aber vorhandene Etappen-Tempi nicht loeschen. Pruefung
// ueber GET (was der Editor nach dem Speichern sieht) und den Plattenstand.
func TestStageTempo3197_PutNurTempoBehaeltEtappenTempo(t *testing.T) {
	s := newTestStore(t)
	seedStageTempoTrip(t, s, "userA", "t5")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t5", "userA", `{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":3`)+`}`)
	putOK(t, r, "/api/trips/t5", "userA", `{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":5}}`)

	w := doReq(r, http.MethodGet, "/api/trips/t5", "", "", "userA")
	if w.Code != http.StatusOK {
		t.Fatalf("GET: %d %s", w.Code, w.Body.String())
	}
	var got model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("GET-Antwort nicht lesbar: %v", err)
	}
	if len(got.Stages) != 2 {
		t.Fatalf("Etappen verloren: %d", len(got.Stages))
	}
	if got.Tempo == nil || got.Tempo.GrundtempoKmh != 5 {
		t.Errorf("Trip-Tempo nicht uebernommen: %+v", got.Tempo)
	}
	if got.Stages[1].GrundtempoKmh == nil || *got.Stages[1].GrundtempoKmh != 3 {
		t.Fatalf("S2: Etappen-Tempo durch PUT {tempo} geloescht: %v", got.Stages[1].GrundtempoKmh)
	}
	if got.Stages[0].GrundtempoKmh != nil {
		t.Errorf("S1: grundtempo_kmh darf nicht entstehen")
	}

	tr := ladeTempoTrip(t, s, "userA", "t5")
	if tr.Stages[1].GrundtempoKmh == nil || *tr.Stages[1].GrundtempoKmh != 3 {
		t.Fatalf("Platte: S2-Etappen-Tempo verloren: %v", tr.Stages[1].GrundtempoKmh)
	}
	if a := ank3197(tr.Stages[1]); a != "08:00,11:20,13:36" {
		t.Errorf("S2 muss mit 3 km/h weiterrechnen, bekommen %s", a)
	}
	if a := ank3197(tr.Stages[0]); a == "08:00,10:30,12:12" {
		t.Errorf("S1 folgt dem Trip-Tempo 5 km/h nicht (noch 4 km/h): %s", a)
	}
}

// AC-5: Zwei Nutzer -- A setzt Etappen-Tempo, B (gleiche Trip-ID) bleibt unveraendert.
func TestStageTempo3197_ZweiNutzerGetrennt(t *testing.T) {
	dataDir := t.TempDir()
	s := store.New(dataDir, "test")
	seedStageTempoTrip(t, s, "userA", "gemeinsam")
	seedStageTempoTrip(t, s, "userB", "gemeinsam")
	r := briefingVergleichEtagRouter(s)

	putOK(t, r, "/api/trips/gemeinsam", "userA", `{"stages":`+stagesJSON3197("", `,"grundtempo_kmh":3`)+`}`)
	if tr := ladeTempoTrip(t, s, "userA", "gemeinsam"); tr.Stages[1].GrundtempoKmh == nil ||
		ank3197(tr.Stages[1]) != "08:00,11:20,13:36" {
		t.Fatalf("A: Etappen-Tempo nicht wirksam: %s", ank3197(tr.Stages[1]))
	}
	if tr := ladeTempoTrip(t, s, "userB", "gemeinsam"); tr.Stages[1].GrundtempoKmh != nil ||
		ank3197(tr.Stages[1]) != "08:00,10:30,12:12" {
		t.Errorf("B: Trip durch A-PUT veraendert: %s", ank3197(tr.Stages[1]))
	}
	if _, err := os.Stat(filepath.Join(dataDir, "users", "default", "briefings", "gemeinsam.json")); err == nil {
		t.Errorf("unter users/default geschrieben")
	}
}
