package handler

// Issue #1895 Scheibe S1 (Epic #1230) — Kanalzuordnung je Metrik, Verrohrung.
// Spec: docs/specs/modules/alert_metric_channels.md, AC-1/AC-3/AC-4/AC-7.
//
// RED-Bauform: Diese Datei referenziert BEWUSST kein Go-Struct-Feld, sondern
// misst ausschliesslich den tatsaechlich ausgelieferten HTTP-Antwortkoerper.
// Dadurch kompiliert sie heute und faellt mit einer sprechenden Zusicherung
// rot durch (statt mit einem paketweiten Compile-Fehler, der die einzelnen
// ACs nicht unterscheidbar macht): Das Feld `alert_metric_channels` existiert
// weder in `model.Trip` noch im PUT-DTO `tripUpdateRequest`, ein PUT wirft es
// also still weg und das GET liefert den Schluessel nie aus.
//
// Warum die HTTP-Schicht und nicht `store.SaveTrip`: Der Read-Modify-Write-
// Merge sitzt in `internal/handler/trip.go`; der Store reicht das Struct nur
// transparent durch. Gegen den Store gemessen waeren AC-3/AC-4 strukturell
// blind (Spec, AC-3 Testnotiz).

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// amcTripRouter verdrahtet GET + PUT auf denselben Store — der Nutzer kommt
// pro Anfrage aus dem Kontext, genau wie in Produktion (AuthMiddleware).
func amcTripRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	return r
}

func amcReq(t *testing.T, r *chi.Mux, method, path, user string, body interface{}) *httptest.ResponseRecorder {
	t.Helper()
	var rdr io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal request body: %v", err)
		}
		rdr = bytes.NewReader(buf)
	}
	req := httptest.NewRequest(method, path, rdr)
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, user)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// amcBodyMap liest den ausgelieferten Antwortkoerper als generische JSON-Map —
// nicht als typisiertes Struct. Nur so ist die ABWESENHEIT eines Schluessels
// (AC-7) ueberhaupt messbar.
func amcBodyMap(t *testing.T, w *httptest.ResponseRecorder) map[string]interface{} {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("Antwortkoerper ist kein JSON-Objekt: %v — %s", err, w.Body.String())
	}
	return m
}

func amcChannelsOf(t *testing.T, m map[string]interface{}) map[string]interface{} {
	t.Helper()
	raw, ok := m["alert_metric_channels"]
	if !ok {
		t.Fatalf("Schluessel alert_metric_channels fehlt im ausgelieferten Antwortkoerper: %v", m)
	}
	sub, ok := raw.(map[string]interface{})
	if !ok {
		t.Fatalf("alert_metric_channels ist kein Objekt, sondern %#v", raw)
	}
	return sub
}

func amcSeedTrip(t *testing.T, s *store.Store, user, id, name string) {
	t.Helper()
	trip := model.Trip{
		ID:   id,
		Name: name,
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	if err := s.WithUser(user).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip(%s/%s): %v", user, id, err)
	}
}

// AC-1: Roundtrip PUT -> GET traegt die Metrik-Kanal-Zuordnung unveraendert,
// und zwar fuer zwei Nutzer getrennt. Beide Trips tragen ABSICHTLICH DIESELBE
// ID: nur so beweist der Test Mandantentrennung — bei verschiedenen IDs waere
// "keine Vermischung" trivial erfuellt und wuerde nichts bewachen.
func TestTripAlertMetricChannels_RoundtripIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	r := amcTripRouter(s)
	const id = "trip-1895-ac1"

	amcSeedTrip(t, s, "alice", id, "Alice-Tour")
	amcSeedTrip(t, s, "bob", id, "Bob-Tour")

	alice := map[string]interface{}{"rain": map[string]interface{}{"telegram": true}}
	bob := map[string]interface{}{"wind": map[string]interface{}{"email": true}}

	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "alice",
		map[string]interface{}{"alert_metric_channels": alice}); w.Code != http.StatusOK {
		t.Fatalf("PUT alice: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}
	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "bob",
		map[string]interface{}{"alert_metric_channels": bob}); w.Code != http.StatusOK {
		t.Fatalf("PUT bob: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	gotAlice := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+id, "alice", nil)))
	if !reflect.DeepEqual(gotAlice, alice) {
		t.Errorf("AC-1 alice: erwartet %v, bekam %v", alice, gotAlice)
	}

	gotBob := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+id, "bob", nil)))
	if !reflect.DeepEqual(gotBob, bob) {
		t.Errorf("AC-1 bob: erwartet %v, bekam %v", bob, gotBob)
	}
}

// AC-3: Ein Teil-PUT, der das Feld gar nicht enthaelt, darf die zuvor
// gespeicherte Zuordnung nicht loeschen (Top-Level-Erbe, BUG-DATALOSS-GR221).
func TestTripAlertMetricChannels_PreservedWhenPutOmitsField(t *testing.T) {
	s := newTestStore(t)
	r := amcTripRouter(s)
	const id = "trip-1895-ac3"
	amcSeedTrip(t, s, "alice", id, "AC3-Tour")

	want := map[string]interface{}{"rain": map[string]interface{}{"telegram": true}}
	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "alice",
		map[string]interface{}{"alert_metric_channels": want}); w.Code != http.StatusOK {
		t.Fatalf("PUT (Vorbelegung): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	// Zweiter PUT OHNE das Feld — nur der Name aendert sich.
	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "alice",
		map[string]interface{}{"name": "AC3-Tour (umbenannt)"}); w.Code != http.StatusOK {
		t.Fatalf("PUT (ohne Feld): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	body := amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+id, "alice", nil))
	if got := amcChannelsOf(t, body); !reflect.DeepEqual(got, want) {
		t.Errorf("AC-3: Teil-PUT ohne Feld hat die Zuordnung veraendert — erwartet %v, bekam %v", want, got)
	}
	if body["name"] != "AC3-Tour (umbenannt)" {
		t.Errorf("AC-3 Gegenprobe: Name wurde nicht uebernommen, bekam %v", body["name"])
	}
}

// AC-4: Ein PUT, der nur EINE Metrik mitschickt, darf die uebrigen Metriken
// nicht loeschen (Feld-Level-Merge via mergeConfigMap statt Blind-Replace).
func TestTripAlertMetricChannels_SingleMetricPutPreservesOtherMetrics(t *testing.T) {
	s := newTestStore(t)
	r := amcTripRouter(s)
	const id = "trip-1895-ac4"
	amcSeedTrip(t, s, "alice", id, "AC4-Tour")

	initial := map[string]interface{}{
		"rain": map[string]interface{}{"telegram": true},
		"wind": map[string]interface{}{"email": true},
	}
	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "alice",
		map[string]interface{}{"alert_metric_channels": initial}); w.Code != http.StatusOK {
		t.Fatalf("PUT (Vorbelegung): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	// PUT aendert NUR "rain"; "wind" fehlt im Unterobjekt komplett.
	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+id, "alice", map[string]interface{}{
		"alert_metric_channels": map[string]interface{}{
			"rain": map[string]interface{}{"telegram": false, "sms": true},
		},
	}); w.Code != http.StatusOK {
		t.Fatalf("PUT (nur rain): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	got := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+id, "alice", nil)))

	wantRain := map[string]interface{}{"telegram": false, "sms": true}
	if !reflect.DeepEqual(got["rain"], wantRain) {
		t.Errorf("AC-4: rain nicht uebernommen — erwartet %v, bekam %v", wantRain, got["rain"])
	}
	wantWind := map[string]interface{}{"email": true}
	if !reflect.DeepEqual(got["wind"], wantWind) {
		t.Errorf("AC-4: wind vom rain-PUT geloescht — erwartet %v (unangetastet), bekam %v", wantWind, got["wind"])
	}
}

// AC-7: Ein Trip ohne das Feld liefert den Schluessel gar nicht aus
// (omitempty) — Bestandstrips bleiben byte-gleich, das Feld ist neutral.
// Gegenprobe im selben Test: mit gesetztem Feld MUSS der Schluessel da sein,
// sonst waere die Abwesenheits-Zusicherung auch bei komplett fehlendem
// Feature erfuellt und wuerde nichts bewachen.
func TestTripAlertMetricChannels_OmittedFromJSONWhenUnset(t *testing.T) {
	s := newTestStore(t)
	r := amcTripRouter(s)
	const bare = "trip-1895-ac7-bare"
	const filled = "trip-1895-ac7-filled"
	amcSeedTrip(t, s, "alice", bare, "AC7-ohne")
	amcSeedTrip(t, s, "alice", filled, "AC7-mit")

	body := amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+bare, "alice", nil))
	if _, present := body["alert_metric_channels"]; present {
		t.Errorf("AC-7: Trip ohne Zuordnung liefert den Schluessel trotzdem aus: %v", body["alert_metric_channels"])
	}

	if w := amcReq(t, r, http.MethodPut, "/api/trips/"+filled, "alice", map[string]interface{}{
		"alert_metric_channels": map[string]interface{}{"rain": map[string]interface{}{"telegram": true}},
	}); w.Code != http.StatusOK {
		t.Fatalf("PUT (Gegenprobe): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}
	filledBody := amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/trips/"+filled, "alice", nil))
	if _, present := filledBody["alert_metric_channels"]; !present {
		t.Errorf("AC-7 Gegenprobe: gesetzte Zuordnung wird nicht ausgeliefert — die Abwesenheits-Pruefung oben waere wertlos")
	}
}
