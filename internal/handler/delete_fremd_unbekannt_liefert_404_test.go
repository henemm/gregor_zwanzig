package handler

// Issue #2815 (Spec fix_2815_delete_fremd_404.md, AC-1..AC-13): DELETE auf
// eine fremde oder unbekannte ID antwortet wie bei den Presets mit 404
// not_found statt 204. Geprueft an der HTTP-Antwort des echten Handlers,
// Zwei-Nutzer-Tests je Endpunkt (ADR-0003), echtes Dateisystem, kein Mock.

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	d2815A = "nutzer-a-2815"
	d2815B = "nutzer-b-2815"
)

func d2815Store(t *testing.T) *store.Store {
	t.Helper()
	s := store.New(t.TempDir(), d2815A)
	s.ProvisionUserDirs(d2815A)
	s.ProvisionUserDirs(d2815B)
	return s
}

func d2815Assert404(t *testing.T, w *httptest.ResponseRecorder, wo string) {
	t.Helper()
	if w.Code != 404 {
		t.Fatalf("%s: erwartet 404, bekommen %d (%s)", wo, w.Code, w.Body.String())
	}
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s: Body kein JSON: %v (%s)", wo, err, w.Body.String())
	}
	if m["error"] != "not_found" {
		t.Errorf(`%s: error erwartet "not_found", bekommen %v`, wo, m["error"])
	}
}

func d2815Read(t *testing.T, p string) []byte {
	t.Helper()
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("Vorbedingung/Nachweis: %s nicht lesbar: %v", p, err)
	}
	return b
}

func d2815AssertSame(t *testing.T, p string, want []byte) {
	t.Helper()
	got, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("%s muss unveraendert vorhanden sein: %v", p, err)
	}
	if string(got) != string(want) {
		t.Errorf("%s veraendert:\nvorher  %s\nnachher %s", p, want, got)
	}
}

func delTrip(s *store.Store, id, user string) *httptest.ResponseRecorder {
	return p2158Do(DeleteTripHandler(s), "DELETE", "/api/trips/{id}", "/api/trips/"+id, "", user)
}

func delBriefingRoute(s *store.Store, id, user string) *httptest.ResponseRecorder {
	return p2158Do(DeleteBriefingHandler(s), "DELETE", "/api/briefings/{id}", "/api/briefings/"+id+"?kind=route", "", user)
}

func delLocation(s *store.Store, id, user string) *httptest.ResponseRecorder {
	return p2158Do(DeleteLocationHandler(s), "DELETE", "/api/locations/{id}", "/api/locations/"+id, "", user)
}

func delGroup(s *store.Store, id, user string) *httptest.ResponseRecorder {
	return p2158Do(DeleteGroupHandler(s), "DELETE", "/api/groups/{id}", "/api/groups/"+id, "", user)
}

// AC-1 + AC-7 (fremd): B loescht A's Trip-ID -> 404, A's Trip unveraendert,
// in B's Verzeichnis bleibt keine Sperrdatei zurueck.
func TestDeleteTrip_FremdeID_404_TripVonABleibt(t *testing.T) {
	s := d2815Store(t)
	seedTrip(t, s.WithUser(d2815A), "t1", "Trip A")
	pA := filepath.Join(s.WithUser(d2815A).BriefingsDir(), "t1.json")
	vorher := d2815Read(t, pA)

	w := delTrip(s, "t1", d2815B)

	d2815Assert404(t, w, "DELETE /api/trips/t1 als B")
	d2815AssertSame(t, pA, vorher)
	if tr, err := s.WithUser(d2815A).LoadTrip("t1"); err != nil || tr == nil || tr.Name != "Trip A" {
		t.Errorf("Trip von A muss weiter ladbar sein: trip=%v err=%v", tr, err)
	}
	dirB := s.WithUser(d2815B).BriefingsDir()
	for _, n := range []string{"t1.json", "t1.json.lock"} {
		if dlcExists(filepath.Join(dirB, n)) {
			t.Errorf("AC-7: %s darf nach dem 404 bei B nicht existieren", n)
		}
	}
}

// AC-2: dasselbe ueber DELETE /api/briefings/{id}?kind=route.
func TestDeleteBriefingRoute_FremdeID_404_TripVonABleibt(t *testing.T) {
	s := d2815Store(t)
	seedTrip(t, s.WithUser(d2815A), "t1", "Trip A")
	pA := filepath.Join(s.WithUser(d2815A).BriefingsDir(), "t1.json")
	vorher := d2815Read(t, pA)

	w := delBriefingRoute(s, "t1", d2815B)

	d2815Assert404(t, w, "DELETE /api/briefings/t1?kind=route als B")
	d2815AssertSame(t, pA, vorher)
}

// AC-3: B loescht A's Orts-ID -> 404, A's Ort unveraendert.
func TestDeleteLocation_FremdeID_404_OrtVonABleibt(t *testing.T) {
	s := d2815Store(t)
	seedLocation(t, s.WithUser(d2815A), "loc-a", "Ort A")
	pA := filepath.Join(s.WithUser(d2815A).LocationsDir(), "loc-a.json")
	vorher := d2815Read(t, pA)

	w := delLocation(s, "loc-a", d2815B)

	d2815Assert404(t, w, "DELETE /api/locations/loc-a als B")
	d2815AssertSame(t, pA, vorher)
	if loc, err := s.WithUser(d2815A).LoadLocation("loc-a"); err != nil || loc == nil || loc.Name != "Ort A" {
		t.Errorf("Ort von A muss weiter ladbar sein: loc=%v err=%v", loc, err)
	}
}

// AC-4: B loescht A's Gruppen-ID -> 404, A's Gruppe und Orts-Verweise bleiben.
func TestDeleteGroup_FremdeID_404_GruppeVonABleibt(t *testing.T) {
	s := d2815Store(t)
	sa := s.WithUser(d2815A)
	gid := "ski"
	if err := sa.SaveGroup(model.Group{ID: gid, Name: "Ski", Order: 0}); err != nil {
		t.Fatal(err)
	}
	if err := sa.SaveLocation(model.Location{ID: "stubai", Name: "Stubai", Lat: 47, Lon: 11, GroupID: &gid}); err != nil {
		t.Fatal(err)
	}
	pLoc := filepath.Join(sa.LocationsDir(), "stubai.json")
	locVorher := d2815Read(t, pLoc)

	w := delGroup(s, gid, d2815B)

	d2815Assert404(t, w, "DELETE /api/groups/ski als B")
	groups, err := sa.LoadGroups()
	if err != nil || len(groups) != 1 || groups[0].ID != gid {
		t.Errorf("Gruppe von A muss bestehen bleiben: groups=%v err=%v", groups, err)
	}
	d2815AssertSame(t, pLoc, locVorher)
}

// AC-5: unbekannte, gueltige ID -> 404 not_found auf allen vier Endpunkten.
func TestDelete_UnbekannteID_404_AlleVierEndpunkte(t *testing.T) {
	for _, tc := range []struct {
		name string
		do   func(s *store.Store) *httptest.ResponseRecorder
	}{
		{"trips", func(s *store.Store) *httptest.ResponseRecorder { return delTrip(s, "gibt-es-nicht", d2815A) }},
		{"briefings?kind=route", func(s *store.Store) *httptest.ResponseRecorder {
			return delBriefingRoute(s, "gibt-es-nicht", d2815A)
		}},
		{"locations", func(s *store.Store) *httptest.ResponseRecorder { return delLocation(s, "gibt-es-nicht", d2815A) }},
		{"groups", func(s *store.Store) *httptest.ResponseRecorder { return delGroup(s, "gibt-es-nicht", d2815A) }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			d2815Assert404(t, tc.do(d2815Store(t)), "DELETE "+tc.name+"/gibt-es-nicht")
		})
	}
}

// AC-6: eigener Eintrag -> 204 und weg; zweites DELETE -> 404.
func TestDelete_EigenerEintrag_204_DannZweitesDelete404(t *testing.T) {
	t.Run("trip", func(t *testing.T) {
		s := d2815Store(t)
		seedTrip(t, s.WithUser(d2815A), "t1", "Trip A")
		if w := delTrip(s, "t1", d2815A); w.Code != 204 {
			t.Fatalf("erstes DELETE: erwartet 204, bekommen %d (%s)", w.Code, w.Body.String())
		}
		if dlcExists(filepath.Join(s.WithUser(d2815A).BriefingsDir(), "t1.json")) {
			t.Fatal("Trip muss nach 204 weg sein")
		}
		d2815Assert404(t, delTrip(s, "t1", d2815A), "zweites DELETE trip")
	})
	t.Run("location", func(t *testing.T) {
		s := d2815Store(t)
		seedLocation(t, s.WithUser(d2815A), "loc-a", "Ort A")
		if w := delLocation(s, "loc-a", d2815A); w.Code != 204 {
			t.Fatalf("erstes DELETE: erwartet 204, bekommen %d (%s)", w.Code, w.Body.String())
		}
		if dlcExists(filepath.Join(s.WithUser(d2815A).LocationsDir(), "loc-a.json")) {
			t.Fatal("Ort muss nach 204 weg sein")
		}
		d2815Assert404(t, delLocation(s, "loc-a", d2815A), "zweites DELETE location")
	})
	t.Run("group", func(t *testing.T) {
		s := d2815Store(t)
		if err := s.WithUser(d2815A).SaveGroup(model.Group{ID: "ski", Name: "Ski"}); err != nil {
			t.Fatal(err)
		}
		if w := delGroup(s, "ski", d2815A); w.Code != 204 {
			t.Fatalf("erstes DELETE: erwartet 204, bekommen %d (%s)", w.Code, w.Body.String())
		}
		groups, _ := s.WithUser(d2815A).LoadGroups()
		if len(groups) != 0 {
			t.Fatalf("Gruppe muss nach 204 weg sein: %v", groups)
		}
		d2815Assert404(t, delGroup(s, "ski", d2815A), "zweites DELETE group")
	})
}

// AC-7 (unbekannt): nach 404 liegt weder Trip- noch Sperrdatei unter der ID.
func TestDeleteTrip_UnbekannteID_HinterlaesstKeineSperrdatei(t *testing.T) {
	s := d2815Store(t)
	w := delTrip(s, "zufall-id", d2815A)
	d2815Assert404(t, w, "DELETE /api/trips/zufall-id")
	dir := s.WithUser(d2815A).BriefingsDir()
	for _, n := range []string{"zufall-id.json", "zufall-id.json.lock"} {
		if dlcExists(filepath.Join(dir, n)) {
			t.Errorf("%s darf nach dem 404 nicht existieren", n)
		}
	}
}

// AC-8: kaputte Trip-Datei -> 204, Datei entfernt (fail-open).
func TestDeleteTrip_KaputteDatei_204UndWeg(t *testing.T) {
	s := d2815Store(t)
	dir := s.WithUser(d2815A).BriefingsDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, "kaputt.json")
	if err := os.WriteFile(p, []byte("{kein json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if w := delTrip(s, "kaputt", d2815A); w.Code != 204 {
		t.Fatalf("erwartet 204, bekommen %d (%s)", w.Code, w.Body.String())
	}
	if dlcExists(p) {
		t.Error("kaputte Trip-Datei muss entfernt sein")
	}
}

// AC-10: kaputte Ortsdatei -> 204, Datei entfernt.
func TestDeleteLocation_KaputteDatei_204UndWeg(t *testing.T) {
	s := d2815Store(t)
	p := filepath.Join(s.WithUser(d2815A).LocationsDir(), "kaputt.json")
	if err := os.WriteFile(p, []byte("{kein json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if w := delLocation(s, "kaputt", d2815A); w.Code != 204 {
		t.Fatalf("erwartet 204, bekommen %d (%s)", w.Code, w.Body.String())
	}
	if dlcExists(p) {
		t.Error("kaputte Ortsdatei muss entfernt sein")
	}
}

// AC-11: veralteter Preset-Verweis auf eine nicht existierende Orts-ID ->
// 404, nicht 409.
func TestDeleteLocation_UnbekannteIDMitVeraltetemPresetVerweis_404Nicht409(t *testing.T) {
	s := d2815Store(t)
	sa := s.WithUser(d2815A)
	seedLocation(t, sa, "loc-da", "Ort da")
	seedVergleich(t, sa, "cmp-1", "Vergleich", "loc-da", "loc-weg")

	w := delLocation(s, "loc-weg", d2815A)

	d2815Assert404(t, w, "DELETE /api/locations/loc-weg (veralteter Verweis)")
}

// AC-13: verwaiste group_id-Verweise auf eine nicht mehr existierende Gruppe
// -> 404, die Verweise sind danach trotzdem genullt (Heilpfad).
func TestDeleteGroup_UnbekannteID_NulltVerwaisteVerweise_404(t *testing.T) {
	s := d2815Store(t)
	sa := s.WithUser(d2815A)
	// Eine andere Gruppe existiert, damit groups.json vorhanden ist und keine
	// Lazy-Migration dazwischenfunkt.
	if err := sa.SaveGroup(model.Group{ID: "andere", Name: "Andere"}); err != nil {
		t.Fatal(err)
	}
	ghost := "ghost"
	andere := "andere"
	for _, l := range []model.Location{
		{ID: "l1", Name: "L1", Lat: 47, Lon: 11, GroupID: &ghost},
		{ID: "l2", Name: "L2", Lat: 47, Lon: 11, GroupID: &ghost},
		{ID: "l3", Name: "L3", Lat: 47, Lon: 11, GroupID: &andere},
	} {
		if err := sa.SaveLocation(l); err != nil {
			t.Fatal(err)
		}
	}

	w := delGroup(s, ghost, d2815A)

	d2815Assert404(t, w, "DELETE /api/groups/ghost")
	for _, id := range []string{"l1", "l2"} {
		loc, err := sa.LoadLocation(id)
		if err != nil || loc == nil {
			t.Fatalf("Ort %s verschwunden: err=%v", id, err)
		}
		if loc.GroupID != nil {
			t.Errorf("Ort %s: verwaister group_id-Verweis %q nicht genullt", id, *loc.GroupID)
		}
		if loc.Name == "" {
			t.Errorf("Ort %s hat Felder verloren", id)
		}
	}
	if l3, _ := sa.LoadLocation("l3"); l3 == nil || l3.GroupID == nil || *l3.GroupID != andere {
		t.Errorf("Ort l3 der anderen Gruppe darf nicht angefasst werden: %v", l3)
	}
}
