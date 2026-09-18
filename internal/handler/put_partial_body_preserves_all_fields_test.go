package handler

// TDD RED: Issue #2285 AC-1 (Dach-Epic #1374)
//
// Spec: docs/specs/modules/fix_2285_compare_put_merge_kernel.md
//
// Reflection-basierter Roundtrip: JEDES exportierte Struct-Feld von
// model.ComparePreset und model.Trip wird mit einem synthetischen
// Nicht-Null-Wert belegt, gespeichert, ein minimaler PUT {"name":"neu"}
// ueber den echten HTTP-Router gesendet, danach neu geladen und (mit
// "name"/"Name" ausgenommen) gegen den VOR dem PUT geladenen Ausgangszustand
// verglichen. Das deckt automatisch jedes kuenftige Struct-Feld ab, ohne
// diesen Test anzufassen ("synthetisches Zukunftsfeld").
//
// Heutiger Stand: UpdateComparePresetHandler dekodiert den PUT-Rumpf voll in
// ein frisches model.ComparePreset und rettet nur einen Teil der Felder
// zurueck (LocationIDs/Empfaenger/Schedule/Profil/HourFrom/HourTo fehlen in
// der Rettung) -- ein minimaler Body zerstoert Pflichtfelder und die
// Validierung schlaegt fehl (400 statt 200). Erwartetes GRUEN erst nach
// applyComparePresetPatch (GREEN-Phase).
//
// Ausfuehrung:
//   go test ./internal/handler/... -run TestPutPartialBodyPreservesAllFields -v

import (
	"net/http"
	"reflect"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// fillValue belegt v rekursiv per Reflection mit einem synthetischen
// Nicht-Null/Nicht-Zero-Wert, passend zur Art (Kind) des Feldes. Deckt damit
// auch kuenftige Struct-Felder ab, ohne dass dieser Test angepasst werden
// muss.
func fillValue(v reflect.Value) {
	if !v.CanSet() {
		return
	}
	switch v.Kind() {
	case reflect.Bool:
		v.SetBool(true)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		v.SetInt(7)
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		v.SetUint(7)
	case reflect.Float32, reflect.Float64:
		v.SetFloat(3.5)
	case reflect.String:
		v.SetString("synthetic-value")
	case reflect.Ptr:
		if v.IsNil() {
			v.Set(reflect.New(v.Type().Elem()))
		}
		fillValue(v.Elem())
	case reflect.Slice:
		s := reflect.MakeSlice(v.Type(), 1, 1)
		fillValue(s.Index(0))
		v.Set(s)
	case reflect.Array:
		for i := 0; i < v.Len(); i++ {
			fillValue(v.Index(i))
		}
	case reflect.Map:
		m := reflect.MakeMap(v.Type())
		key := reflect.New(v.Type().Key()).Elem()
		fillValue(key)
		val := reflect.New(v.Type().Elem()).Elem()
		fillValue(val)
		m.SetMapIndex(key, val)
		v.Set(m)
	case reflect.Interface:
		v.Set(reflect.ValueOf("synthetic-interface-value"))
	case reflect.Struct:
		if v.Type() == reflect.TypeOf(time.Time{}) {
			v.Set(reflect.ValueOf(time.Date(2030, 6, 15, 10, 30, 0, 0, time.UTC)))
			return
		}
		for i := 0; i < v.NumField(); i++ {
			if v.Type().Field(i).PkgPath != "" {
				continue // unexported
			}
			fillValue(v.Field(i))
		}
	}
}

// syntheticComparePreset fuellt jedes Feld generisch und korrigiert danach
// gezielt die Felder, die validateComparePreset formal/als Enum prueft.
func syntheticComparePreset(id, userID string) model.ComparePreset {
	var p model.ComparePreset
	fillValue(reflect.ValueOf(&p).Elem())

	p.ID = id
	p.UserID = userID
	p.Schedule = "daily"
	p.Profil = "ALLGEMEIN"
	p.ForecastHours = 48
	p.HourFrom = 6
	p.HourTo = 18
	p.Empfaenger = []string{"a@example.com", "b@example.com"}
	morning, evening := "07:00:00", "19:00:00"
	p.MorningTime, p.EveningTime = &morning, &evening
	endDate := "2030-01-01"
	p.EndDate = &endDate
	dayStart, dayEnd := 4, 19
	p.DayWindowStartHour, p.DayWindowEndHour = &dayStart, &dayEnd
	return p
}

// syntheticTrip fuellt jedes Feld generisch und korrigiert danach gezielt die
// Felder, die validateTrip prueft (Waypoint-Koordinaten, Stage-Datum).
func syntheticTrip(id string) model.Trip {
	var tr model.Trip
	fillValue(reflect.ValueOf(&tr).Elem())

	tr.ID = id
	if len(tr.Stages) > 0 {
		tr.Stages[0].Date = "2026-05-01"
		if len(tr.Stages[0].Waypoints) > 0 {
			tr.Stages[0].Waypoints[0].Lat = 47.1
			tr.Stages[0].Waypoints[0].Lon = 11.2
		}
	}
	return tr
}

// assertPreservedExceptName vergleicht baseline/after nach Ausnahme des
// Namensfeldes per reflect.DeepEqual.
func assertPreservedExceptName(t *testing.T, label string, baseline, after interface{}) {
	t.Helper()
	if !reflect.DeepEqual(baseline, after) {
		t.Errorf("%s: minimaler PUT hat Felder verloren.\nvorher:  %+v\nnachher: %+v", label, baseline, after)
	}
}

func TestPutPartialBodyPreservesAllFields_ComparePresetDirectPUT(t *testing.T) {
	s := newTestStore(t)
	id := "cp-ac1-direct"
	if err := s.SaveComparePreset(syntheticComparePreset(id, "test")); err != nil {
		t.Fatalf("seed SaveComparePreset: %v", err)
	}
	baseline := loadPresetOrFail(t, s, id)

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/compare/presets/"+id, `{"name":"neu"}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	after := loadPresetOrFail(t, s, id)
	if after.Name != "neu" {
		t.Errorf("name nicht uebernommen, got %q", after.Name)
	}
	baseline.Name, after.Name = "", ""
	assertPreservedExceptName(t, "compare-preset direct PUT", *baseline, *after)
}

func TestPutPartialBodyPreservesAllFields_BriefingVergleichPUT(t *testing.T) {
	s := newTestStore(t)
	id := "cp-ac1-briefing"
	if err := s.SaveComparePreset(syntheticComparePreset(id, "test")); err != nil {
		t.Fatalf("seed SaveComparePreset: %v", err)
	}
	baseline := loadPresetOrFail(t, s, id)

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/"+id+"?kind=vergleich", `{"name":"neu"}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	after := loadPresetOrFail(t, s, id)
	if after.Name != "neu" {
		t.Errorf("name nicht uebernommen, got %q", after.Name)
	}
	baseline.Name, after.Name = "", ""
	assertPreservedExceptName(t, "briefing PUT kind=vergleich", *baseline, *after)
}

func TestPutPartialBodyPreservesAllFields_TripDirectPUT(t *testing.T) {
	s := newTestStore(t)
	id := "trip-ac1-direct"
	tr := syntheticTrip(id)
	if err := s.SaveTrip(&tr); err != nil {
		t.Fatalf("seed SaveTrip: %v", err)
	}
	baseline, err := s.LoadTrip(id)
	if err != nil || baseline == nil {
		t.Fatalf("seed reload: %v / %+v", err, baseline)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/trips/"+id, `{"name":"neu"}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	after, err := s.LoadTrip(id)
	if err != nil || after == nil {
		t.Fatalf("reload after PUT: %v / %+v", err, after)
	}
	if after.Name != "neu" {
		t.Errorf("name nicht uebernommen, got %q", after.Name)
	}
	baseline.Name, after.Name = "", ""
	assertPreservedExceptName(t, "trip direct PUT", *baseline, *after)
}

func TestPutPartialBodyPreservesAllFields_BriefingRoutePUT(t *testing.T) {
	s := newTestStore(t)
	id := "trip-ac1-briefing"
	tr := syntheticTrip(id)
	if err := s.SaveTrip(&tr); err != nil {
		t.Fatalf("seed SaveTrip: %v", err)
	}
	baseline, err := s.LoadTrip(id)
	if err != nil || baseline == nil {
		t.Fatalf("seed reload: %v / %+v", err, baseline)
	}

	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/briefings/"+id+"?kind=route", `{"name":"neu"}`, "", "test")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	after, err := s.LoadTrip(id)
	if err != nil || after == nil {
		t.Fatalf("reload after PUT: %v / %+v", err, after)
	}
	if after.Name != "neu" {
		t.Errorf("name nicht uebernommen, got %q", after.Name)
	}
	baseline.Name, after.Name = "", ""
	assertPreservedExceptName(t, "briefing PUT kind=route", *baseline, *after)
}
