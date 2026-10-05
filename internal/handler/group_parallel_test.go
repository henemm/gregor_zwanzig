package handler

import (
	"fmt"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-2 (#2158): mehrere verschiedene Gruppen eines Nutzers werden gleichzeitig
// angelegt bzw. geaendert. Ohne Gruppen-Sperre ueberschreibt der letzte
// Schreiber groups.json mit seinem alten Stand.
func TestGroupParallel_CreateUndUpdate_BeideErhalten(t *testing.T) {
	const iterationen = 100
	const neue = 6
	verloren := 0
	for it := 0; it < iterationen; it++ {
		s := store.New(t.TempDir(), "u1")
		if err := s.SaveGroup(model.Group{ID: "alt", Name: "Alt", Order: 0}); err != nil {
			t.Fatalf("seed: %v", err)
		}
		fns := []func(){func() {
			w := p2158Do(UpdateGroupHandler(s), "PATCH", "/api/groups/{id}", "/api/groups/alt", `{"name":"Alt-Neu"}`, "u1")
			if w.Code != 200 {
				t.Errorf("PATCH: %d %s", w.Code, w.Body.String())
			}
		}}
		for k := 0; k < neue; k++ {
			k := k
			fns = append(fns, func() {
				w := p2158Do(CreateGroupHandler(s), "POST", "/api/groups", "/api/groups",
					fmt.Sprintf(`{"name":"Neu %d","order":%d}`, k, k+10), "u1")
				if w.Code != 201 {
					t.Errorf("POST: %d %s", w.Code, w.Body.String())
				}
			})
		}
		p2158Parallel(t, 30*time.Second, fns...)

		gs, err := s.LoadGroups()
		if err != nil {
			t.Fatalf("laden: %v", err)
		}
		if len(gs) != neue+1 {
			verloren++
			continue
		}
		for _, g := range gs {
			if g.ID == "alt" && g.Name != "Alt-Neu" {
				verloren++
			}
		}
	}
	if verloren > 0 {
		t.Errorf("Lost Update in groups.json in %d von %d Durchlaeufen", verloren, iterationen)
	}
}

// p2158GruppeMitOrt legt Gruppe g1 und einen Ort o1 an, der auf g1 verweist.
func p2158GruppeMitOrt(t *testing.T) *store.Store {
	t.Helper()
	s := store.New(t.TempDir(), "u1")
	gid := "g1"
	if err := s.SaveGroup(model.Group{ID: "g1", Name: "G1", Order: 0}); err != nil {
		t.Fatalf("seed gruppe: %v", err)
	}
	if err := s.SaveLocation(model.Location{ID: "o1", Name: "O1", Lat: 47, Lon: 11, GroupID: &gid}); err != nil {
		t.Fatalf("seed ort: %v", err)
	}
	return s
}

func p2158Loesche(s *store.Store) {
	w := p2158Do(DeleteGroupHandler(s), "DELETE", "/api/groups/{id}", "/api/groups/g1", "", "u1")
	if w.Code != 204 {
		_ = fmt.Sprintf("DELETE group: %d %s", w.Code, w.Body.String()) // Fehlstatus zeigt sich im Endstand
	}
}

func p2158OrtsUpdate(s *store.Store, key string) {
	w := p2158Do(PutLocationWeatherConfigHandler(s), "PUT", "/api/locations/{id}/weather-config",
		"/api/locations/o1/weather-config", fmt.Sprintf(`{%q:1}`, key), "u1")
	if w.Code != 200 {
		_ = fmt.Sprintf("PUT weather-config: %d %s", w.Code, w.Body.String()) // Fehlstatus zeigt sich im Endstand
	}
}

// p2158EndstandGruppeWeg: Gruppe fehlt, Ort traegt alle Felder und verweist
// nicht mehr auf die geloeschte Gruppe. Liefert true, wenn alles stimmt.
func p2158EndstandGruppeWeg(t *testing.T, s *store.Store, keys []string) bool {
	t.Helper()
	ok := true
	gs, err := s.LoadGroups()
	if err != nil {
		t.Fatalf("gruppen laden: %v", err)
	}
	for _, g := range gs {
		if g.ID == "g1" {
			t.Errorf("Gruppe g1 steht noch in groups.json")
			ok = false
		}
	}
	loc, err := s.LoadLocation("o1")
	if err != nil || loc == nil {
		t.Fatalf("ort laden: %v", err)
	}
	if loc.GroupID != nil {
		t.Errorf("Ort verweist noch auf Gruppe %q", *loc.GroupID)
		ok = false
	}
	for _, k := range keys {
		if _, has := loc.DisplayConfig[k]; !has {
			t.Errorf("Ort hat Feld %q verloren", k)
			ok = false
		}
	}
	return ok
}

// AC-3 (#2158): beide erzwungenen Reihenfolgen, danach identischer Endstand.
func TestGroupParallel_DeleteGruppeUndOrtsUpdate_BeideReihenfolgen(t *testing.T) {
	t.Run("update_dann_delete", func(t *testing.T) {
		s := p2158GruppeMitOrt(t)
		p2158Parallel(t, 20*time.Second, func() { p2158OrtsUpdate(s, "feld"); p2158Loesche(s) })
		p2158EndstandGruppeWeg(t, s, []string{"feld"})
	})
	t.Run("delete_dann_update", func(t *testing.T) {
		s := p2158GruppeMitOrt(t)
		p2158Parallel(t, 20*time.Second, func() { p2158Loesche(s); p2158OrtsUpdate(s, "feld") })
		p2158EndstandGruppeWeg(t, s, []string{"feld"})
	})
}

// AC-3 (#2158): wirklich gleichzeitig, viele Durchlaeufe. Ohne Sperre
// ueberschreibt der Loesch-Pfad (Ort mit group_id=nil speichern) das Feld des
// parallelen Orts-Updates; mit falscher Sperr-Reihenfolge haengt es (Timeout).
func TestGroupParallel_DeleteGruppeUndOrtsUpdate_GleichzeitigKeinLostUpdateKeineVerklemmung(t *testing.T) {
	const iterationen = 150
	const updater = 4
	schlecht := 0
	for it := 0; it < iterationen; it++ {
		s := p2158GruppeMitOrt(t)
		keys := []string{}
		fns := []func(){func() { p2158Loesche(s) }}
		for k := 0; k < updater; k++ {
			key := fmt.Sprintf("feld%d", k)
			keys = append(keys, key)
			fns = append(fns, func() { p2158OrtsUpdate(s, key) })
		}
		p2158Parallel(t, 20*time.Second, fns...)
		gs, _ := s.LoadGroups()
		loc, _ := s.LoadLocation("o1")
		bad := len(gs) != 0 || loc == nil || loc.GroupID != nil
		if loc != nil {
			for _, k := range keys {
				if _, has := loc.DisplayConfig[k]; !has {
					bad = true
				}
			}
		}
		if bad {
			schlecht++
		}
	}
	if schlecht > 0 {
		t.Errorf("Endstand falsch (Lost Update) in %d von %d Durchlaeufen", schlecht, iterationen)
	}
}
