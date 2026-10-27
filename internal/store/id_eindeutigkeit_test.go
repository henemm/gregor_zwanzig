package store

// Kennungs-Eindeutigkeit Trip / Ortsvergleich im Store (Issue #2359, AC-4).
// Spec: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
//
// SaveTrip und SaveComparePreset schreiben dieselbe Datei briefings/<id>.json.
// Trifft ein Save auf eine Datei der anderen Art, muss er mit Fehler abbrechen
// und die Datei byte-gleich lassen; fehlende/leere/korrupte Zieldateien
// werden fail-open ueberschrieben. Diese Datei kompiliert gegen den heutigen
// Code und prueft nur err != nil + Bytes; die Sentinel-Pruefung
// (errors.Is ErrKindConflict) steht in id_eindeutigkeit_sentinel_test.go.
//
// Keine Attrappe: echter Store auf t.TempDir(), Daten ueber SaveTrip /
// SaveComparePreset. Handgeschriebene Dateien nur fuer die von der Spec
// verlangten Faelle (Alt-Datei ohne kind, 0 Byte, "{kaputt").

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func idEindStore(t *testing.T) *Store {
	t.Helper()
	return New(t.TempDir(), "alice")
}

func idEindTrip(id, name string) model.Trip {
	return model.Trip{
		ID: id, Name: name,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
}

func idEindPreset(id, name string) model.ComparePreset {
	return model.ComparePreset{
		ID: id, Name: name, UserID: "alice",
		LocationIDs: []string{"loc-1", "loc-2"}, Schedule: "daily", Profil: "ALLGEMEIN",
		HourFrom: 6, HourTo: 18,
	}
}

func idEindDatei(s *Store, id string) string {
	return filepath.Join(s.briefingsDir(), id+".json")
}

func idEindLies(t *testing.T, s *Store, id string) []byte {
	t.Helper()
	b, err := os.ReadFile(idEindDatei(s, id))
	if err != nil {
		t.Fatalf("Datei %s nicht lesbar: %v", id, err)
	}
	return b
}

// idEindKindEntfernen macht aus einer per Produktpfad geschriebenen Datei eine
// Alt-Datei ohne kind-Feld (Spec AC-3/AC-4) und belegt den Zustand.
func idEindKindEntfernen(t *testing.T, s *Store, id string) {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(idEindLies(t, s, id), &m); err != nil {
		t.Fatalf("Datei %s kein JSON: %v", id, err)
	}
	delete(m, "kind")
	roh, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	if err := os.WriteFile(idEindDatei(s, id), roh, 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
	var probe map[string]interface{}
	_ = json.Unmarshal(idEindLies(t, s, id), &probe)
	if _, hat := probe["kind"]; hat {
		t.Fatalf("Vorbedingung: Datei %s traegt noch kind", id)
	}
}

// AC-4 Richtung 1: SaveTrip auf eine Ortsvergleichs-Datei -> Fehler, Datei unveraendert.
func TestIdEindeutigkeit_SaveTripAufVergleichsDatei_FehlerUndUnveraendert(t *testing.T) {
	s := idEindStore(t)
	if err := s.SaveComparePreset(idEindPreset("x", "Vergleich")); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	vorher := idEindLies(t, s, "x")

	trip := idEindTrip("x", "Trip")
	err := s.SaveTrip(&trip)

	if err == nil {
		t.Errorf("SaveTrip auf kind=vergleich: erwartet Fehler, bekommen nil")
	}
	if nachher := idEindLies(t, s, "x"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Ortsvergleichs-Datei wurde von SaveTrip ueberschrieben")
	}
	if p, lerr := s.LoadComparePreset("x"); lerr != nil || p == nil {
		t.Errorf("Ortsvergleich x nach SaveTrip nicht mehr ladbar (err=%v)", lerr)
	}
}

// AC-4 Richtung 2: SaveComparePreset auf eine Trip-Datei (kind=route) -> Fehler.
func TestIdEindeutigkeit_SaveVergleichAufTripDatei_FehlerUndUnveraendert(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	vorher := idEindLies(t, s, "t1")

	err := s.SaveComparePreset(idEindPreset("t1", "Vergleich"))

	if err == nil {
		t.Errorf("SaveComparePreset auf kind=route: erwartet Fehler, bekommen nil")
	}
	if nachher := idEindLies(t, s, "t1"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Trip-Datei wurde von SaveComparePreset ueberschrieben")
	}
	if tr, lerr := s.LoadTrip("t1"); lerr != nil || tr == nil {
		t.Errorf("Trip t1 nach SaveComparePreset nicht mehr ladbar (err=%v)", lerr)
	}
}

// AC-4 Richtung 2b: SaveComparePreset auf eine gueltige Trip-Alt-Datei ohne kind -> Fehler.
func TestIdEindeutigkeit_SaveVergleichAufTripAltDateiOhneKind_FehlerUndUnveraendert(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	idEindKindEntfernen(t, s, "t1")
	vorher := idEindLies(t, s, "t1")

	err := s.SaveComparePreset(idEindPreset("t1", "Vergleich"))

	if err == nil {
		t.Errorf("SaveComparePreset auf Trip-Alt-Datei ohne kind: erwartet Fehler, bekommen nil")
	}
	if nachher := idEindLies(t, s, "t1"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Trip-Alt-Datei wurde von SaveComparePreset ueberschrieben")
	}
}

// AC-4: kind=="" zaehlt beim Trip-Speichern als eigene Art (kein Konflikt).
func TestIdEindeutigkeit_SaveTripAufTripAltDateiOhneKind_Erlaubt(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Alt")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	idEindKindEntfernen(t, s, "t1")

	neu := idEindTrip("t1", "Neu")
	if err := s.SaveTrip(&neu); err != nil {
		t.Fatalf("SaveTrip auf eigene Alt-Datei: erwartet nil, bekommen %v", err)
	}
	tr, err := s.LoadTrip("t1")
	if err != nil || tr == nil || tr.Name != "Neu" {
		t.Errorf("Trip t1 nicht aktualisiert (err=%v, trip=%v)", err, tr)
	}
}

// AC-4 fail-open: fehlende, leere oder korrupte Zieldatei blockiert nicht.
func TestIdEindeutigkeit_FailOpen_FehlendLeerKorrupt(t *testing.T) {
	faelle := []struct {
		name   string
		inhalt []byte // nil = Datei fehlt
	}{
		{"fehlend", nil},
		{"null_byte", []byte{}},
		{"korrupt", []byte("{kaputt")},
	}
	for _, f := range faelle {
		f := f
		vorbereiten := func(t *testing.T, s *Store, id string) {
			t.Helper()
			if f.inhalt == nil {
				return
			}
			if err := os.MkdirAll(s.briefingsDir(), 0755); err != nil {
				t.Fatalf("MkdirAll: %v", err)
			}
			if err := os.WriteFile(idEindDatei(s, id), f.inhalt, 0644); err != nil {
				t.Fatalf("WriteFile: %v", err)
			}
		}

		t.Run("SaveTrip_"+f.name, func(t *testing.T) {
			s := idEindStore(t)
			vorbereiten(t, s, "z1")
			trip := idEindTrip("z1", "Trip")
			if err := s.SaveTrip(&trip); err != nil {
				t.Fatalf("SaveTrip (%s): erwartet nil, bekommen %v", f.name, err)
			}
			if tr, err := s.LoadTrip("z1"); err != nil || tr == nil {
				t.Errorf("Trip z1 nach fail-open nicht geschrieben (err=%v)", err)
			}
		})

		t.Run("SaveComparePreset_"+f.name, func(t *testing.T) {
			s := idEindStore(t)
			vorbereiten(t, s, "z1")
			if err := s.SaveComparePreset(idEindPreset("z1", "Vergleich")); err != nil {
				t.Fatalf("SaveComparePreset (%s): erwartet nil, bekommen %v", f.name, err)
			}
			if p, err := s.LoadComparePreset("z1"); err != nil || p == nil {
				t.Errorf("Ortsvergleich z1 nach fail-open nicht geschrieben (err=%v)", err)
			}
		})
	}
}

// Bulk-Wrapper (Spec, Risiken): SaveComparePresets bricht bei einem Konflikt
// mit Fehler ab, die fremde Datei bleibt unveraendert.
func TestIdEindeutigkeit_SaveComparePresets_Konflikt_FehlerUndTripUnveraendert(t *testing.T) {
	s := idEindStore(t)
	trip := idEindTrip("t1", "Trip")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	vorher := idEindLies(t, s, "t1")

	err := s.SaveComparePresets([]model.ComparePreset{
		idEindPreset("ok-1", "Frei"),
		idEindPreset("t1", "Kollision"),
	})

	if err == nil {
		t.Errorf("SaveComparePresets mit Kollision: erwartet Fehler, bekommen nil")
	}
	if nachher := idEindLies(t, s, "t1"); !bytes.Equal(vorher, nachher) {
		t.Errorf("Trip-Datei t1 wurde vom Bulk-Wrapper ueberschrieben")
	}
	if tr, lerr := s.LoadTrip("t1"); lerr != nil || tr == nil {
		t.Errorf("Trip t1 nach Bulk-Save nicht mehr ladbar (err=%v)", lerr)
	}
}
