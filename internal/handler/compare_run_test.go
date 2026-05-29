// HTTP-Handler-Tests für POST /api/compare/run (Issue #250 + Issue #454).
// Verwendet das neue Request-Format mit date_from/date_to/hour_from/hour_to
// und das neue Response-Schema (ranking/matrix/stunden_verlauf).
//
// Echte Integrationstests — KEINE Mocks. FixtureProvider liefert
// reproduzierbare Wetterdaten (siehe fixtures/openmeteo/).
//
// Ausführung:
//   go test ./internal/handler/... -run "TestCompareRun|TestIssue454" -v
package handler

import (
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider/fixture"
	"github.com/henemm/gregor-api/internal/store"
)

// fixtureDir gibt den absoluten Pfad zum fixtures/openmeteo-Verzeichnis zurück.
func fixtureDir() string {
	_, file, _, _ := runtime.Caller(0)
	root := filepath.Join(filepath.Dir(file), "..", "..")
	return filepath.Join(root, "fixtures", "openmeteo")
}

// errorProvider implementiert provider.WeatherProvider und gibt bei jedem
// FetchForecast-Aufruf einen Fehler zurück — echtes Struct, kein Mock.
type errorProvider struct{}

func (e *errorProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	return nil, fmt.Errorf("provider error 429")
}

func seedCompareLocation(t *testing.T, s *store.Store, id, name string, lat, lon float64, ele int) {
	t.Helper()
	loc := model.Location{ID: id, Name: name, Lat: lat, Lon: lon, ElevationM: &ele}
	if err := s.SaveLocation(loc); err != nil {
		t.Fatalf("seedCompareLocation(%s): %v", id, err)
	}
}

// makeBody serialises a CompareRequest body in the new (#454) shape.
func makeBody(locIDs []string, dateFrom, dateTo string, hourFrom, hourTo int, profile string) string {
	ids := `"` + strings.Join(locIDs, `","`) + `"`
	return fmt.Sprintf(
		`{"location_ids":[%s],"date_from":%q,"date_to":%q,"hour_from":%d,"hour_to":%d,"profile":%q}`,
		ids, dateFrom, dateTo, hourFrom, hourTo, profile,
	)
}

func todayUTC() string {
	return time.Now().UTC().Format("2006-01-02")
}

// --- AC-1: zwei valide Locations → ranking ---------------------------------

func TestCompareRunHandler_TwoLocations_ReturnsRanking(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-a", "Ort A", 47.0, 11.0, 500)
	seedCompareLocation(t, s, "loc-b", "Ort B", 46.5, 13.5, 800)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-a", "loc-b"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	if err := json.NewDecoder(w.Body).Decode(&result); err != nil {
		t.Fatalf("JSON-Decode fehlgeschlagen: %v", err)
	}
	if len(result.Ranking) != 2 {
		t.Fatalf("erwartet 2 ranking-Einträge, got %d", len(result.Ranking))
	}
	for _, entry := range result.Ranking {
		if entry.Score < 0 || entry.Score > 100 {
			t.Errorf("Score %d außerhalb [0,100]", entry.Score)
		}
		if entry.Name == "" {
			t.Errorf("ranking-Eintrag hat leeres name-Feld: %+v", entry)
		}
	}
	if result.Ranking[0].Score < result.Ranking[1].Score {
		t.Errorf("ranking nicht absteigend sortiert: %d < %d",
			result.Ranking[0].Score, result.Ranking[1].Score)
	}
}

// --- AC-1 (matrix): matrix-Block vorhanden ---------------------------------

func TestCompareRunHandler_TwoLocations_ReturnsMatrix(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-a", "Ort A", 47.0, 11.0, 500)
	seedCompareLocation(t, s, "loc-b", "Ort B", 46.5, 13.5, 800)

	prov := fixture.NewProvider(fixtureDir())
	engine := compare.New(s, prov)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-a", "loc-b"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("matrix-Test: erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)
	if len(result.Matrix) != 2 {
		t.Fatalf("matrix-Test: erwartet 2 matrix-Einträge, got %d", len(result.Matrix))
	}
	for _, entry := range result.Matrix {
		if len(entry.Metrics) == 0 {
			t.Errorf("matrix-Test: Location %s hat leere metrics-Map", entry.LocationID)
		}
	}
}

// --- AC-1 (stunden_verlauf): stunden_verlauf-Block vorhanden ---------------

func TestCompareRunHandler_TwoLocations_ReturnsStundenVerlauf(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-ibk-a", "Innsbruck A", 47.27, 11.40, 574)
	seedCompareLocation(t, s, "loc-ibk-b", "Innsbruck B", 47.26, 11.41, 580)

	prov := fixture.NewProvider(fixtureDir())
	engine := compare.New(s, prov)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-ibk-a", "loc-ibk-b"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("stunden_verlauf-Test: erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)
	if len(result.StundenVerlauf) == 0 {
		t.Fatal("stunden_verlauf-Test: stunden_verlauf ist leer")
	}
	for _, entry := range result.StundenVerlauf {
		if len(entry.Hours) == 0 {
			t.Errorf("stunden_verlauf-Test: Location %s hat keine Stunden-Einträge", entry.LocationID)
		}
		for _, hr := range entry.Hours {
			if hr.Hour == "" {
				t.Errorf("stunden_verlauf-Test: hour-Feld ist leer")
			}
		}
	}
}

// --- AC-4: Partial-Result bei nicht existenter Location -------------------

func TestCompareRunHandler_OneLocationMissing_PartialResult(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-exists", "Existiert", 47.0, 11.0, 500)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-exists", "loc-ghost"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 (partial), got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)
	if len(result.Ranking) != 1 {
		t.Errorf("erwartet 1 ranking-Eintrag (partial), got %d", len(result.Ranking))
	}
}

// --- AC-2: Cache-Hit — identische Scores beim zweiten Request --------------

func TestCompareRunHandler_SecondRequest_ReturnsSameScore(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-x", "Ort X", 47.0, 11.0, 600)
	seedCompareLocation(t, s, "loc-y", "Ort Y", 47.5, 11.5, 700)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	makeRequest := func() []compare.RankingEntry {
		body := makeBody([]string{"loc-x", "loc-y"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
		req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
		}
		var result compare.CompareResult
		json.NewDecoder(w.Body).Decode(&result)
		return result.Ranking
	}

	r1 := makeRequest()
	r2 := makeRequest()
	if len(r1) != len(r2) {
		t.Fatalf("ranking count mismatch: first=%d, second=%d", len(r1), len(r2))
	}
	for i := range r1 {
		if r1[i].Score != r2[i].Score {
			t.Errorf("rank %d: score mismatch first=%d second=%d", i, r1[i].Score, r2[i].Score)
		}
	}
}

// --- Issue #367: sunny_hours_h in Response, kein dni_avg_wm2 ---------------

func TestCompareRunHandler_SunnyHoursH_InResponse_DniAbsent(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-ibk-a", "Innsbruck A", 47.27, 11.40, 574)
	seedCompareLocation(t, s, "loc-ibk-b", "Innsbruck B", 47.26, 11.41, 580)

	prov := fixture.NewProvider(fixtureDir())
	engine := compare.New(s, prov)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-ibk-a", "loc-ibk-b"}, todayUTC(), todayUTC(), 0, 23, "WINTERSPORT")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	rawJSON := w.Body.String()
	if strings.Contains(rawJSON, "dni_avg_wm2") {
		t.Errorf("Response enthält 'dni_avg_wm2' — muss durch 'sunny_hours_h' ersetzt sein")
	}
	if !strings.Contains(rawJSON, "sunny_hours_h") {
		t.Errorf("Response enthält kein 'sunny_hours_h'; body=%s", rawJSON)
	}
}

// --- Issue #250: Provider-Fehler → Location droppen ------------------------

func TestCompareRunHandler_ProviderError_DropLocation(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-a", "Ort A", 47.0, 11.0, 500)
	seedCompareLocation(t, s, "loc-b", "Ort B", 46.5, 13.5, 800)

	engine := compare.New(s, &errorProvider{})
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-a", "loc-b"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)
	if len(result.Ranking) != 0 {
		t.Errorf("erwartet 0 ranking-Einträge bei Provider-Fehler, got %d", len(result.Ranking))
	}
}

// --- Validierung: zu wenige Locations → 400 too_few_locations --------------

func TestCompareRunHandler_TooFewLocations_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"only-one"}, todayUTC(), todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400, got %d", w.Code)
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "too_few_locations" {
		t.Errorf("erwartet error='too_few_locations', got '%s'", errResp["error"])
	}
}

// --- Validierung: invalides date_from → 400 invalid_date_from --------------

func TestCompareRunHandler_InvalidDateFrom_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"a", "b"}, "not-a-date", todayUTC(), 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400 for invalid date_from, got %d", w.Code)
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "invalid_date_from" {
		t.Errorf("erwartet error='invalid_date_from', got '%s'", errResp["error"])
	}
}

// --- Validierung: invalides date_to → 400 invalid_date_to ------------------

func TestCompareRunHandler_InvalidDateTo_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"a", "b"}, todayUTC(), "garbage", 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400 for invalid date_to, got %d", w.Code)
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "invalid_date_to" {
		t.Errorf("erwartet error='invalid_date_to', got '%s'", errResp["error"])
	}
}

// --- AC-5: date_from > date_to → 400 invalid_date_range --------------------

func TestCompareRunHandler_DateFromAfterDateTo_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"a", "b"}, "2026-06-17", "2026-06-15", 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-5: erwartet 400, got %d: %s", w.Code, w.Body.String())
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "invalid_date_range" {
		t.Errorf("AC-5: erwartet error='invalid_date_range', got '%s'", errResp["error"])
	}
}

// --- AC-6: date_to > heute+9 → 400 date_range_too_large --------------------

func TestCompareRunHandler_DateRangeTooLarge_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	tooFar := time.Now().UTC().AddDate(0, 0, 12).Format("2006-01-02")
	body := makeBody([]string{"a", "b"}, todayUTC(), tooFar, 0, 23, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-6: erwartet 400, got %d: %s", w.Code, w.Body.String())
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "date_range_too_large" {
		t.Errorf("AC-6: erwartet error='date_range_too_large', got '%s'", errResp["error"])
	}
}

// --- hour_from > hour_to → 400 invalid_hour_range --------------------------

func TestCompareRunHandler_HourFromAfterHourTo_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"a", "b"}, todayUTC(), todayUTC(), 18, 8, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("hour_range-Test: erwartet 400, got %d: %s", w.Code, w.Body.String())
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "invalid_hour_range" {
		t.Errorf("hour_range-Test: erwartet error='invalid_hour_range', got '%s'", errResp["error"])
	}
}

// --- Validierung: invalides Profile → 400 invalid_profile ------------------

func TestCompareRunHandler_InvalidProfile_Returns400(t *testing.T) {
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"a", "b"}, todayUTC(), todayUTC(), 0, 23, "INVALID_PROFILE")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400, got %d", w.Code)
	}
	var errResp map[string]string
	json.NewDecoder(w.Body).Decode(&errResp)
	if errResp["error"] != "invalid_profile" {
		t.Errorf("erwartet error='invalid_profile', got '%s'", errResp["error"])
	}
}

// --- AC-7: hour-Filter wirkt auf stunden_verlauf ---------------------------

func TestCompareRunHandler_HourFilter_StundenVerlauf(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-ibk-c", "Innsbruck C", 47.27, 11.40, 574)
	seedCompareLocation(t, s, "loc-ibk-d", "Innsbruck D", 47.26, 11.41, 580)

	prov := fixture.NewProvider(fixtureDir())
	engine := compare.New(s, prov)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-ibk-c", "loc-ibk-d"}, todayUTC(), todayUTC(), 8, 16, "ALLGEMEIN")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-7: erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)

	for _, locEntry := range result.StundenVerlauf {
		for _, hourEntry := range locEntry.Hours {
			h := hourEntry.Hour
			if h < "08" || h > "16" {
				t.Errorf("AC-7: Location %s hat Stunde %q außerhalb [08..16]",
					locEntry.LocationID, h)
			}
		}
	}
}

// --- WinnerTagsTyped: ranking[0].tags enthalten type + label ---------------

func TestCompareRunHandler_WinnerTags_TypedFormat(t *testing.T) {
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-ibk-e", "Innsbruck E", 47.27, 11.40, 574)
	seedCompareLocation(t, s, "loc-ibk-f", "Innsbruck F", 47.26, 11.41, 580)

	prov := fixture.NewProvider(fixtureDir())
	engine := compare.New(s, prov)
	h := CompareRunHandler(engine)

	body := makeBody([]string{"loc-ibk-e", "loc-ibk-f"}, todayUTC(), todayUTC(), 0, 23, "SUMMER_TREKKING")
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("tags-Test: erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)

	if len(result.Ranking) == 0 {
		t.Fatal("tags-Test: ranking ist leer")
	}
	winner := result.Ranking[0]
	if len(winner.Tags) == 0 {
		t.Error("tags-Test: ranking[0].tags ist leer — erwartet mindestens 1 typisiertes Tag")
	}
	for _, tag := range winner.Tags {
		if tag.Type == "" {
			t.Error("tags-Test: tag.type ist leer")
		}
		if tag.Label == "" {
			t.Error("tags-Test: tag.label ist leer")
		}
	}
}
