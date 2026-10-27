package handler

// Issue #2422 S3, Bein (b) Go: Roundtrip der vollstaendigen report_config ueber
// PUT /api/trips/{id} — mit ZWEI Nutzern (AC-18) sowie Minuten-Kappung, Teil-PUT
// und Erhalt von channel_layouts_per_report (AC-19).
// Spec: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md.
//
// Keine Mocks: echter Store im Tempdir, echte Handler ueber chi, Nutzerkennung
// ueber den echten Auth-Kontext (middleware.ContextWithUserID) — nie "default".
// Fixture-Pfad relativ zu DIESER Testdatei (runtime.Caller).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func rcRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	return r
}

// rcAnfrage schickt eine Anfrage als der Nutzer uid durch den Router.
func rcAnfrage(h http.Handler, methode, id, uid, body string) *httptest.ResponseRecorder {
	var req *http.Request
	if body == "" {
		req = httptest.NewRequest(methode, "/api/trips/"+id, nil)
	} else {
		req = httptest.NewRequest(methode, "/api/trips/"+id, strings.NewReader(body))
	}
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

// rcSeed legt einen Trip fuer genau diesen Nutzer an.
func rcSeed(t *testing.T, s *store.Store, uid string, trip model.Trip) {
	t.Helper()
	trip.Stages = []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
		Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}}
	if err := s.WithUser(uid).SaveTrip(&trip); err != nil {
		t.Fatalf("seed fuer %s failed: %v", uid, err)
	}
}

func rcAusBody(t *testing.T, w *httptest.ResponseRecorder, was string) map[string]interface{} {
	t.Helper()
	var trip map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &trip); err != nil {
		t.Fatalf("%s: Antwort nicht parsebar: %v (%s)", was, err, w.Body.String())
	}
	rc, ok := trip["report_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("%s: report_config fehlt in der Antwort: %s", was, w.Body.String())
	}
	return rc
}

// rcAusDatei liest den Trip-Block direkt aus der Datei des Nutzers.
func rcDatei(t *testing.T, s *store.Store, uid, id string) map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(s.WithUser(uid).BriefingsDir(), id+".json"))
	if err != nil {
		t.Fatalf("Datei von %s/%s nicht lesbar: %v", uid, id, err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Datei von %s/%s nicht parsebar: %v", uid, id, err)
	}
	return m
}

func rcDateiRC(t *testing.T, s *store.Store, uid, id string) map[string]interface{} {
	t.Helper()
	rc, ok := rcDatei(t, s, uid, id)["report_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("Datei von %s/%s hat keine report_config", uid, id)
	}
	return rc
}

func rcGleich(t *testing.T, was string, got, want map[string]interface{}) {
	t.Helper()
	if !reflect.DeepEqual(got, want) {
		g, _ := json.MarshalIndent(got, "", " ")
		w, _ := json.MarshalIndent(want, "", " ")
		t.Errorf("%s: report_config weicht ab\n--- got ---\n%s\n--- want ---\n%s", was, g, w)
	}
}

func rcBody(t *testing.T, rc map[string]interface{}) string {
	t.Helper()
	b, err := json.Marshal(map[string]interface{}{"report_config": rc})
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// rcLadeGoldenD liest den report_config-Blob (roh) aus der eingefrorenen Datei.
// Die Datei entsteht erst in /50 nach den Produktivfixes, aus der echten
// Editor-Helferkette — bis dahin ist der Test aus GENAU diesem Grund rot.
func rcLadeGoldenD(t *testing.T) map[string]interface{} {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller lieferte keinen Pfad")
	}
	path := filepath.Join(filepath.Dir(thisFile), "..", "..", "tests", "fixtures",
		"einstellung_auslieferung", "report_config_nach_speichern_golden_d.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("Golden-D-Datei fehlt — wird in /50 aus der Helferkette erzeugt (%s): %v", path, err)
	}
	var blob map[string]interface{}
	if err := json.Unmarshal(raw, &blob); err != nil {
		t.Fatalf("Golden-D-Datei nicht parsebar: %v", err)
	}
	if len(blob) == 0 {
		t.Fatalf("Golden-D-Datei ist leer (%s)", path)
	}
	return blob
}

// AC-18: zwei Nutzer, gleiche Trip-Kennung. A sendet die vollstaendige Golden-D-
// report_config, B eine andere. Jeder sieht (GET und Datei) exakt seinen Stand,
// unbekannte Schluessel bleiben erhalten, ein Trip nur von A ist fuer B 404 und
// bleibt unveraendert.
//
// Bewacht die Nutzertrennung an der Stelle, an der sie WIRKT: wuerde der Handler
// statt s.WithUser(<Nutzer aus Kontext>) einen festen Nutzer "default" nehmen,
// fanden beide PUTs den (unter A/B angelegten) Trip nicht mehr -> 404 -> rot.
func TestReportConfigRoundtrip_ZweiNutzer(t *testing.T) {
	golden := rcLadeGoldenD(t)

	s := newTestStore(t)
	h := rcRouter(s)
	const nutzerA, nutzerB = "roundtrip-a-ac18", "roundtrip-b-ac18"
	const gemeinsam, nurA = "gleiche-kennung-ac18", "nur-a-ac18"

	// Ausgangsstand: gleiche Kennung, je Nutzer eine ANDERE, bewusst schmale Konfiguration.
	rcSeed(t, s, nutzerA, model.Trip{ID: gemeinsam, Name: "Trip von A",
		ReportConfig: map[string]interface{}{"enabled": true, "send_email": true}})
	rcSeed(t, s, nutzerB, model.Trip{ID: gemeinsam, Name: "Trip von B",
		ReportConfig: map[string]interface{}{"enabled": true, "send_email": true}})
	rcSeed(t, s, nutzerA, model.Trip{ID: nurA, Name: "Nur A",
		ReportConfig: map[string]interface{}{"enabled": true, "morning_time": "07:00:00"}})
	nurADateiVorher, err := os.ReadFile(filepath.Join(s.WithUser(nutzerA).BriefingsDir(), nurA+".json"))
	if err != nil {
		t.Fatal(err)
	}

	// B speichert eine andere Konfiguration, inklusive unbekanntem Schluessel.
	konfigB := map[string]interface{}{
		"enabled":                  true,
		"morning_enabled":          false,
		"evening_enabled":          true,
		"morning_time":             "06:00:00",
		"evening_time":             "20:00:00",
		"send_email":               false,
		"send_telegram":            true,
		"email_format":             "compact",
		"zukunfts_schluessel_ac18": map[string]interface{}{"gehoert": "nutzer-b"},
	}

	if w := rcAnfrage(h, "PUT", gemeinsam, nutzerA, rcBody(t, golden)); w.Code != 200 {
		t.Fatalf("PUT von A: erwartet 200, war %d: %s", w.Code, w.Body.String())
	}
	if w := rcAnfrage(h, "PUT", gemeinsam, nutzerB, rcBody(t, konfigB)); w.Code != 200 {
		t.Fatalf("PUT von B: erwartet 200, war %d: %s", w.Code, w.Body.String())
	}

	// Jeder liest exakt seinen Stand — per GET UND aus der eigenen Datei.
	// (Die Zeiten im Golden-D-Blob sind volle Stunden, die Kappung aendert nichts.)
	wantA := golden
	getA := rcAnfrage(h, "GET", gemeinsam, nutzerA, "")
	if getA.Code != 200 {
		t.Fatalf("GET von A: erwartet 200, war %d", getA.Code)
	}
	rcGleich(t, "A per GET", rcAusBody(t, getA, "GET A"), wantA)
	rcGleich(t, "A aus Datei", rcDateiRC(t, s, nutzerA, gemeinsam), wantA)

	getB := rcAnfrage(h, "GET", gemeinsam, nutzerB, "")
	if getB.Code != 200 {
		t.Fatalf("GET von B: erwartet 200, war %d", getB.Code)
	}
	rc := rcAusBody(t, getB, "GET B")
	for k, v := range konfigB {
		if !reflect.DeepEqual(rc[k], v) {
			t.Errorf("B per GET: Schluessel %q = %v, erwartet %v", k, rc[k], v)
		}
	}
	if !reflect.DeepEqual(rcDateiRC(t, s, nutzerB, gemeinsam)["zukunfts_schluessel_ac18"], konfigB["zukunfts_schluessel_ac18"]) {
		t.Errorf("B: unbekannter Schluessel ging in der Datei verloren")
	}
	// A's Stand darf nichts von B enthalten (kein Durchschlagen ueber die gleiche Kennung).
	if _, da := rcDateiRC(t, s, nutzerA, gemeinsam)["zukunfts_schluessel_ac18"]; da {
		t.Errorf("A: Schluessel aus B's Konfiguration ist in A's Datei gelandet")
	}

	// Ein Trip, den nur A besitzt: fuer B weder lesbar noch aenderbar.
	if w := rcAnfrage(h, "GET", nurA, nutzerB, ""); w.Code != 404 {
		t.Errorf("GET fremder Trip durch B: erwartet 404, war %d: %s", w.Code, w.Body.String())
	}
	if w := rcAnfrage(h, "PUT", nurA, nutzerB, rcBody(t, map[string]interface{}{"enabled": false, "morning_time": "05:00:00"})); w.Code != 404 {
		t.Errorf("PUT fremder Trip durch B: erwartet 404, war %d: %s", w.Code, w.Body.String())
	}
	nurADateiNachher, err := os.ReadFile(filepath.Join(s.WithUser(nutzerA).BriefingsDir(), nurA+".json"))
	if err != nil {
		t.Fatal(err)
	}
	if string(nurADateiVorher) != string(nurADateiNachher) {
		t.Errorf("A's Trip wurde durch B's PUT veraendert\nvorher:\n%s\nnachher:\n%s", nurADateiVorher, nurADateiNachher)
	}
	if _, err := os.Stat(filepath.Join(s.WithUser(nutzerB).BriefingsDir(), nurA+".json")); err == nil {
		t.Errorf("B's PUT auf A's Trip hat eine Datei im Bestand von B angelegt")
	}
	// Und A sieht seinen Trip weiterhin unveraendert.
	if w := rcAnfrage(h, "GET", nurA, nutzerA, ""); w.Code != 200 {
		t.Errorf("GET eigener Trip durch A: erwartet 200, war %d", w.Code)
	} else if got := rcAusBody(t, w, "GET nur-A")["morning_time"]; got != "07:00:00" {
		t.Errorf("A's morning_time = %v, erwartet 07:00:00 (durch B veraendert?)", got)
	}
}

// AC-19: Minuten-Kappung im Teil-PUT, uebrige Schluessel unveraendert, und ein
// zweiter Teil-PUT nur auf display_config.channel_layouts laesst
// channel_layouts_per_report stehen.
func TestReportConfigRoundtrip_KappungTeilPutUndPerReport(t *testing.T) {
	s := newTestStore(t)
	h := rcRouter(s)
	const nutzer, id = "roundtrip-kappung-ac19", "kappung-ac19"

	perReport := map[string]interface{}{
		"evening": map[string]interface{}{
			"email": []interface{}{
				map[string]interface{}{"metric_id": "wind", "enabled": true},
				map[string]interface{}{"metric_id": "temperature", "enabled": true},
			},
			"sms": []interface{}{
				map[string]interface{}{"metric_id": "temperature", "enabled": true},
			},
		},
	}
	seedRC := map[string]interface{}{
		"enabled":                  true,
		"morning_enabled":          true,
		"evening_enabled":          false,
		"morning_time":             "08:00:00",
		"evening_time":             "18:00:00",
		"send_email":               true,
		"send_sms":                 false,
		"send_telegram":            true,
		"email_format":             "full",
		"multi_day_trend_reports":  []interface{}{"evening"},
		"daily_summary_metrics":    []interface{}{"temperature", "wind"},
		"zukunfts_schluessel_ac19": "bleibt",
	}
	rcSeed(t, s, nutzer, model.Trip{
		ID: id, Name: "Kappung",
		DisplayConfig: map[string]interface{}{
			"channel_layouts": map[string]interface{}{
				"email": []interface{}{map[string]interface{}{"metric_id": "temperature", "enabled": true}},
			},
			"channel_layouts_per_report": perReport,
		},
		ReportConfig: seedRC,
	})

	// 1) Teil-PUT: nur morning_time mit Minuten.
	w1 := rcAnfrage(h, "PUT", id, nutzer, rcBody(t, map[string]interface{}{"morning_time": "07:30:00"}))
	if w1.Code != 200 {
		t.Fatalf("PUT 1: erwartet 200, war %d: %s", w1.Code, w1.Body.String())
	}
	erwartet := map[string]interface{}{}
	for k, v := range seedRC {
		erwartet[k] = v
	}
	erwartet["morning_time"] = "07:00:00" // gekappt auf die volle Stunde
	rcGleich(t, "PUT 1 Antwort", rcAusBody(t, w1, "PUT 1"), erwartet)
	rcGleich(t, "PUT 1 Datei", rcDateiRC(t, s, nutzer, id), erwartet)

	// 2) Teil-PUT: nur display_config.channel_layouts, OHNE per_report.
	neuesLayout := map[string]interface{}{
		"email": []interface{}{map[string]interface{}{"metric_id": "wind", "enabled": true}},
	}
	w2 := rcAnfrage(h, "PUT", id, nutzer, `{"display_config":{"channel_layouts":{"email":[{"metric_id":"wind","enabled":true}]}}}`)
	if w2.Code != 200 {
		t.Fatalf("PUT 2: erwartet 200, war %d: %s", w2.Code, w2.Body.String())
	}
	var antwort map[string]interface{}
	if err := json.Unmarshal(w2.Body.Bytes(), &antwort); err != nil {
		t.Fatal(err)
	}
	dcAntwort, _ := antwort["display_config"].(map[string]interface{})
	dcDatei, _ := rcDatei(t, s, nutzer, id)["display_config"].(map[string]interface{})
	for was, dc := range map[string]map[string]interface{}{"Antwort": dcAntwort, "Datei": dcDatei} {
		if dc == nil {
			t.Fatalf("PUT 2 %s: display_config fehlt", was)
		}
		if got, da := dc["channel_layouts_per_report"]; !da {
			t.Errorf("PUT 2 %s: channel_layouts_per_report ging verloren", was)
		} else if !reflect.DeepEqual(got, perReport) {
			t.Errorf("PUT 2 %s: channel_layouts_per_report veraendert: %v", was, got)
		}
		if !reflect.DeepEqual(dc["channel_layouts"], neuesLayout) {
			t.Errorf("PUT 2 %s: channel_layouts = %v, erwartet %v", was, dc["channel_layouts"], neuesLayout)
		}
	}
	// Der zweite PUT fasst report_config nicht an.
	rcGleich(t, "nach PUT 2 Datei", rcDateiRC(t, s, nutzer, id), erwartet)
}
