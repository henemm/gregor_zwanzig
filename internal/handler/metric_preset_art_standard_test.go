package handler

// TDD RED — Issue #2794 S3a Teil-PR 1 (Backend), eigene Vorlagen.
// Spec: docs/specs/modules/feat_2794_s3a_reiter_wetter.md §6 „Eigene Vorlagen (Go)",
// AC-22 (ampel gespeichert, keine Zeithorizonte/Zusammenfassung),
// AC-23 (Duplikat ohne Gross-/Kleinschreibung je Art und gegen die 7
// Systemvorlagen, POST und PATCH, Meldung DE/EN),
// AC-24 (Feld kind route|vergleich, Lese-Default route, ungueltig -> 400),
// AC-25 (is_default exklusiv je Art und bei Neuanlage von Trip bzw.
// Orts-Vergleich angewendet).
//
// Kein Mock: echte Handler, echter Store auf t.TempDir(), Sprache ueber die
// echte Lang-Middleware (Accept-Language), user_id aus dem Auth-Kontext
// (middleware.ContextWithUserID), jeder datenbewegende Fall mit zwei Nutzern.
//
// Neue Felder (kind) werden bewusst NICHT ueber Struct-Felder geprueft, sondern
// ueber JSON-Antwort bzw. die gespeicherte Datei — sonst kompilierte das Paket
// im RED-Stand nicht.
//
// Annahme „Zeithorizonte nicht gesetzt" (AC-22, konsistent mit der Migration
// AC-26): der Metrik-Eintrag traegt KEINEN Schluessel "horizons"; fehlend heisst
// beim Lesen weiterhin „alle Tage" (store.migrateMetricPreset, Python-Renderer
// helpers.py: Default True wenn Feld fehlt).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// Die 7 Systemvorlagen, ermittelt aus der echten Quelle
// src/app/metric_catalog.py get_all_templates() (WEATHER_TEMPLATES, Feld
// "label"; IDs alpen-trekking, wandern, skitouren, wintersport, radtour,
// wassersport, allgemein — dieselben Schluessel wie AMPEL_TEMPLATES).
var v2794Systemvorlagen = []string{
	"Alpen-Trekking", "Wandern", "Skitouren", "Wintersport", "Radtour", "Wassersport", "Allgemein",
}

const v2794DuplikatDE = "gibt es schon. Wähle einen anderen Namen."

func v2794Router(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Lang(s))
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))
	r.Post("/api/trips", CreateTripHandler(s))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	return r
}

func v2794Anfrage(t *testing.T, h http.Handler, method, path, user, lang string, body interface{}) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *bytes.Reader
	if body == nil {
		rdr = bytes.NewReader(nil)
	} else {
		raw, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal: %v", err)
		}
		rdr = bytes.NewReader(raw)
	}
	req := httptest.NewRequest(method, path, rdr)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept-Language", lang)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), user))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

// v2794Vorlage legt eine eigene Vorlage an und liefert die Antwort als Map.
func v2794Vorlage(t *testing.T, h http.Handler, user string, body obj) (int, obj) {
	t.Helper()
	if _, ok := body["metrics"]; !ok {
		body["metrics"] = []obj{{"metric_id": "wind", "enabled": true, "use_friendly_format": false}}
	}
	w := v2794Anfrage(t, h, "POST", "/api/metric-presets", user, "de", body)
	var resp obj
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	return w.Code, resp
}

// v2794Datei liest die gespeicherte metric_presets.json eines Nutzers roh.
func v2794Datei(t *testing.T, s *store.Store, user string) []obj {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(s.DataDir, "users", user, "metric_presets.json"))
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		t.Fatalf("read presets %s: %v", user, err)
	}
	var out []obj
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("parse presets %s: %v", user, err)
	}
	return out
}

func v2794DateiRoh(t *testing.T, s *store.Store, user string) string {
	t.Helper()
	raw, _ := os.ReadFile(filepath.Join(s.DataDir, "users", user, "metric_presets.json"))
	return string(raw)
}

func v2794NachName(t *testing.T, liste []obj, name string) obj {
	t.Helper()
	for _, p := range liste {
		if p["name"] == name {
			return p
		}
	}
	t.Fatalf("Vorlage %q nicht gefunden in %v", name, liste)
	return nil
}

type v2794Fehler struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func v2794Fehlerkoerper(t *testing.T, w *httptest.ResponseRecorder) v2794Fehler {
	t.Helper()
	var f v2794Fehler
	_ = json.Unmarshal(w.Body.Bytes(), &f)
	return f
}

// v2794PruefeDuplikat: 409 name_exists, Meldung in der Anfragesprache.
func v2794PruefeDuplikat(t *testing.T, w *httptest.ResponseRecorder, lang, was string) {
	t.Helper()
	if w.Code != http.StatusConflict {
		t.Errorf("%s [%s]: Status %d, erwartet 409 name_exists: %s", was, lang, w.Code, w.Body.String())
		return
	}
	f := v2794Fehlerkoerper(t, w)
	if f.Code != "name_exists" {
		t.Errorf("%s [%s]: code=%q, erwartet name_exists", was, lang, f.Code)
	}
	if lang == "de" {
		if !strings.HasPrefix(f.Message, "Eine Vorlage ‚") || !strings.HasSuffix(f.Message, v2794DuplikatDE) {
			t.Errorf("%s [de]: Meldung %q, erwartet „Eine Vorlage ‚{n}‘ %s“", was, f.Message, v2794DuplikatDE)
		}
	} else {
		if f.Message == "" || strings.Contains(f.Message, "gibt es") || strings.Contains(f.Message, "Vorlage") {
			t.Errorf("%s [en]: Meldung %q ist nicht englisch", was, f.Message)
		}
	}
}

func v2794Ampel(gelb float64, alarmAb string) obj {
	return obj{"template": "wandern", "metrics": obj{
		"gust": obj{"upper": obj{"yellow": gelb, "orange": gelb + 15, "red": gelb + 30}, "alarm_ab": alarmAb},
	}}
}

// =============================================================================
// AC-22: POST speichert die ampel, aber weder Zeithorizonte noch Zusammenfassung
// =============================================================================

func TestS3a2794_AC22_PostSpeichertAmpelOhneHorizonteUndZusammenfassung(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	ampel := v2794Ampel(42, "orange")
	code, resp := v2794Vorlage(t, h, "alice", obj{
		"name": "Mein Gipfel", "description": "Grat", "ampel": ampel,
		// Alt-Dialog schickte summary und horizons mit; beides darf nicht landen.
		"summary": "3 Metriken, 1 Abweichung",
		"metrics": []obj{
			{"metric_id": "gust", "enabled": true, "use_friendly_format": false,
				"horizons": obj{"today": true, "tomorrow": false, "day_after": false}},
			{"metric_id": "wind", "enabled": true, "use_friendly_format": true},
		},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST: %d %v", code, resp)
	}
	datei := v2794Datei(t, s, "alice")
	if len(datei) != 1 {
		t.Fatalf("erwartet 1 Vorlage in der Datei, %d", len(datei))
	}
	p := datei[0]
	if !reflect.DeepEqual(p["ampel"], interface{}(ampel)) {
		t.Errorf("AC-22: ampel nicht gespeichert: %v", p["ampel"])
	}
	if _, ok := p["summary"]; ok {
		t.Errorf("AC-22: Feld summary gespeichert: %v", p["summary"])
	}
	ms, _ := p["metrics"].([]interface{})
	if len(ms) != 2 {
		t.Fatalf("AC-22: Metrik-Auswahl verloren: %v", p["metrics"])
	}
	for _, m := range ms {
		e := m.(map[string]interface{})
		if _, ok := e["horizons"]; ok {
			t.Errorf("AC-22: Metrik %v traegt Zeithorizonte %v (erwartet: Feld fehlt = alle Tage)", e["metric_id"], e["horizons"])
		}
	}
	// Ungueltige Ampel bleibt abgelehnt (Go-Ampel-Pruefung), Datei unveraendert,
	// bob unberuehrt.
	vorher := v2794DateiRoh(t, s, "alice")
	w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", "de", obj{
		"name": "Kaputt", "metrics": []string{"gust"}, "ampel": ampelUngueltig()["oben_absteigend"]})
	if w.Code != http.StatusBadRequest || v2794Fehlerkoerper(t, w).Code != "ampel_ungueltig" {
		t.Errorf("AC-22: ungueltige Ampel: %d %s", w.Code, w.Body.String())
	}
	if v2794DateiRoh(t, s, "alice") != vorher {
		t.Error("AC-22: abgelehnte Ampel hat die Datei veraendert")
	}
	if v2794Datei(t, s, "bob") != nil {
		t.Error("AC-22: bob hat eine Vorlagen-Datei bekommen")
	}
}

// =============================================================================
// AC-23: Duplikat gegen die 7 Systemvorlagen (POST), alle Schreibweisen, DE/EN
// =============================================================================

func TestS3a2794_AC23_PostGegenSystemvorlagenAbgelehnt(t *testing.T) {
	for _, kind := range []string{"route", "vergleich"} {
		s := newTestStore(t)
		h := v2794Router(s)
		for _, label := range v2794Systemvorlagen {
			for _, n := range []string{label, strings.ToLower(label), strings.ToUpper(label), "  " + label + " "} {
				for _, lang := range []string{"de", "en"} {
					w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", lang, obj{
						"name": n, "kind": kind, "metrics": []string{"wind"}})
					v2794PruefeDuplikat(t, w, lang, "POST "+kind+" „"+n+"“")
				}
			}
		}
		if got := v2794Datei(t, s, "alice"); len(got) != 0 {
			t.Errorf("AC-23 %s: Systemvorlagen-Namen wurden gespeichert: %d Vorlagen", kind, len(got))
		}
	}
}

func TestS3a2794_AC23_PostEigenesDuplikatMeldungDEEN_NutzerBFrei(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	if code, resp := v2794Vorlage(t, h, "alice", obj{"name": "Bergtag"}); code != http.StatusCreated {
		t.Fatalf("POST Bergtag: %d %v", code, resp)
	}
	for _, n := range []string{"bergtag", "BERGTAG", " Bergtag "} {
		for _, lang := range []string{"de", "en"} {
			w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", lang, obj{
				"name": n, "metrics": []string{"wind"}})
			v2794PruefeDuplikat(t, w, lang, "POST eigenes Duplikat „"+n+"“")
		}
	}
	if got := v2794Datei(t, s, "alice"); len(got) != 1 {
		t.Errorf("AC-23: Duplikat gespeichert, %d Vorlagen", len(got))
	}
	// Nutzer B darf denselben Namen (Mandantentrennung, kein "default").
	if code, resp := v2794Vorlage(t, h, "bob", obj{"name": "Bergtag"}); code != http.StatusCreated {
		t.Errorf("AC-23: bob darf „Bergtag“ anlegen, bekam %d %v", code, resp)
	}
	if _, err := os.Stat(filepath.Join(s.DataDir, "users", "default", "metric_presets.json")); err == nil {
		t.Error("AC-23: Vorlage unter users/default gelandet")
	}
}

// =============================================================================
// AC-23: PATCH-Umbenennung wird ebenso geprueft (heute ungeprueft)
// =============================================================================

func TestS3a2794_AC23_PatchUmbenennungAufDuplikatAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	if code, _ := v2794Vorlage(t, h, "alice", obj{"name": "Bergtag"}); code != http.StatusCreated {
		t.Fatal("POST Bergtag")
	}
	code, zweite := v2794Vorlage(t, h, "alice", obj{"name": "Talweg"})
	if code != http.StatusCreated {
		t.Fatal("POST Talweg")
	}
	id, _ := zweite["id"].(string)
	// bob hat „Gratweg“ — das darf alice trotzdem als Namen nehmen.
	if code, _ := v2794Vorlage(t, h, "bob", obj{"name": "Gratweg"}); code != http.StatusCreated {
		t.Fatal("POST bob Gratweg")
	}
	vorherA := v2794DateiRoh(t, s, "alice")
	vorherB := v2794DateiRoh(t, s, "bob")
	for _, n := range []string{"bergtag", "BERGTAG", "allgemein", "ALLGEMEIN", "Wandern", "alpen-trekking"} {
		for _, lang := range []string{"de", "en"} {
			w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+id, "alice", lang, obj{"name": n})
			v2794PruefeDuplikat(t, w, lang, "PATCH Umbenennung „"+n+"“")
		}
	}
	if v2794DateiRoh(t, s, "alice") != vorherA {
		t.Error("AC-23: abgelehnte Umbenennung hat die Datei von alice veraendert")
	}
	if w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+id, "alice", "de", obj{"name": "Gratweg"}); w.Code != http.StatusOK {
		t.Errorf("AC-23: Umbenennung auf bobs Namen muss erlaubt sein: %d %s", w.Code, w.Body.String())
	}
	if v2794DateiRoh(t, s, "bob") != vorherB {
		t.Error("AC-23: bob wurde veraendert")
	}
}

// =============================================================================
// AC-23/AC-24: PATCH nur mit kind (Art-Wechsel) prueft die Eindeutigkeit in der
// Zielart — auch ohne Feld name im PATCH (Adversary F001).
// =============================================================================

func TestS3a2794_AC24_PatchNurKindWechselAufDuplikatInZielartAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	// alice: „Bergtag“ als vergleich; „bergtag“ (andere Schreibung) als route.
	if code, resp := v2794Vorlage(t, h, "alice", obj{"name": "Bergtag", "kind": "vergleich"}); code != http.StatusCreated {
		t.Fatalf("POST vergleich Bergtag: %d %v", code, resp)
	}
	code, route := v2794Vorlage(t, h, "alice", obj{"name": "bergtag", "kind": "route"})
	if code != http.StatusCreated {
		t.Fatalf("POST route bergtag: %d %v", code, route)
	}
	id, _ := route["id"].(string)
	// bob hat nur eine route „Bergtag“: sein Art-Wechsel ist frei, alices
	// Vergleichsvorlage gleichen Namens zaehlt fuer ihn nicht.
	code, bobRoute := v2794Vorlage(t, h, "bob", obj{"name": "Bergtag", "kind": "route"})
	if code != http.StatusCreated {
		t.Fatalf("POST bob route Bergtag: %d %v", code, bobRoute)
	}
	bobID, _ := bobRoute["id"].(string)

	vorherA := v2794DateiRoh(t, s, "alice")
	for _, lang := range []string{"de", "en"} {
		w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+id, "alice", lang, obj{"kind": "vergleich"})
		v2794PruefeDuplikat(t, w, lang, "PATCH nur kind route→vergleich auf „Bergtag“")
	}
	if v2794DateiRoh(t, s, "alice") != vorherA {
		t.Error("AC-24: abgelehnter Art-Wechsel hat die Datei von alice veraendert")
	}
	if p := v2794NachName(t, v2794Datei(t, s, "alice"), "bergtag"); p["kind"] != "route" {
		t.Errorf("AC-24: abgelehnter Art-Wechsel: kind=%v, erwartet route", p["kind"])
	}

	// bob: gleicher Name in alices Zielart stoert nicht — Wechsel erlaubt.
	w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+bobID, "bob", "de", obj{"kind": "vergleich"})
	if w.Code != http.StatusOK {
		t.Errorf("AC-24: bobs Art-Wechsel muss erlaubt sein: %d %s", w.Code, w.Body.String())
	}
	if p := v2794NachName(t, v2794Datei(t, s, "bob"), "Bergtag"); p["kind"] != "vergleich" {
		t.Errorf("AC-24: bobs Art-Wechsel nicht gespeichert: kind=%v", p["kind"])
	}
}

// =============================================================================
// AC-24: Feld kind — Lese-Default route (Store + Handler)
// =============================================================================

func TestS3a2794_AC24_BestandOhneKindWirdAlsRouteGelesen(t *testing.T) {
	s := newTestStore(t)
	for _, u := range []string{"alice", "bob"} {
		dir := filepath.Join(s.DataDir, "users", u)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
		bestand := `[{"id":"p-alt-` + u + `","name":"Alt","is_default":false,"metrics":[{"metric_id":"wind","enabled":true,"use_friendly_format":false}],"created_at":"2026-01-01T00:00:00Z"}]`
		if err := os.WriteFile(filepath.Join(dir, "metric_presets.json"), []byte(bestand), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	// Store-Ebene: geladenes Preset serialisiert kind=route.
	geladen, err := s.WithUser("alice").LoadMetricPresets()
	if err != nil || len(geladen) != 1 {
		t.Fatalf("LoadMetricPresets: %v %d", err, len(geladen))
	}
	raw, _ := json.Marshal(geladen[0])
	var m obj
	_ = json.Unmarshal(raw, &m)
	if m["kind"] != "route" {
		t.Errorf("AC-24 Store: Bestand ohne kind muss als route gelesen werden, kind=%v", m["kind"])
	}
	// Handler-Ebene: GET liefert kind=route.
	h := v2794Router(s)
	var liste []obj
	_ = json.Unmarshal(v2794Anfrage(t, h, "GET", "/api/metric-presets", "alice", "de", nil).Body.Bytes(), &liste)
	if len(liste) != 1 || liste[0]["kind"] != "route" {
		t.Errorf("AC-24 GET: erwartet kind=route, bekam %v", liste)
	}
	// Bestand zaehlt als route: „alt" als route ist Duplikat, als vergleich frei.
	w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", "de", obj{
		"name": "alt", "kind": "route", "metrics": []string{"wind"}})
	v2794PruefeDuplikat(t, w, "de", "POST route „alt“ gegen Bestand ohne kind")
	if code, resp := v2794Vorlage(t, h, "alice", obj{"name": "alt", "kind": "vergleich"}); code != http.StatusCreated {
		t.Errorf("AC-24: „alt“ als vergleich muss erlaubt sein: %d %v", code, resp)
	}
	// bob unberuehrt.
	if got := v2794Datei(t, s, "bob"); len(got) != 1 || got[0]["name"] != "Alt" {
		t.Errorf("AC-24: bob veraendert: %v", got)
	}
}

// =============================================================================
// AC-24: derselbe Name je Art einmal, nicht doppelt innerhalb einer Art
// =============================================================================

func TestS3a2794_AC24_NameJeArtEinmal_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	code, route := v2794Vorlage(t, h, "alice", obj{"name": "Bergtag", "kind": "route"})
	if code != http.StatusCreated || route["kind"] != "route" {
		t.Fatalf("AC-24: POST route: %d %v", code, route)
	}
	code, vgl := v2794Vorlage(t, h, "alice", obj{"name": "Bergtag", "kind": "vergleich"})
	if code != http.StatusCreated || vgl["kind"] != "vergleich" {
		t.Errorf("AC-24: derselbe Name als vergleich muss erlaubt sein: %d %v", code, vgl)
	}
	for _, kind := range []string{"route", "vergleich"} {
		w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", "de", obj{
			"name": "BERGTAG", "kind": kind, "metrics": []string{"wind"}})
		v2794PruefeDuplikat(t, w, "de", "POST "+kind+" „BERGTAG“")
	}
	// Ohne kind angelegt = route.
	code, ohne := v2794Vorlage(t, h, "alice", obj{"name": "Ohne Art"})
	if code != http.StatusCreated || ohne["kind"] != "route" {
		t.Errorf("AC-24: Neuanlage ohne kind muss route sein: %d %v", code, ohne)
	}
	// Gespeicherte Datei traegt kind je Vorlage.
	datei := v2794Datei(t, s, "alice")
	arten := map[string]int{}
	for _, p := range datei {
		k, _ := p["kind"].(string)
		arten[k]++
	}
	if arten["route"] != 2 || arten["vergleich"] != 1 {
		t.Errorf("AC-24: kind in der Datei: %v", arten)
	}
	// bob: beide Arten mit demselben Namen frei.
	for _, kind := range []string{"route", "vergleich"} {
		if code, resp := v2794Vorlage(t, h, "bob", obj{"name": "Bergtag", "kind": kind}); code != http.StatusCreated {
			t.Errorf("AC-24: bob %s „Bergtag“: %d %v", kind, code, resp)
		}
	}
}

// =============================================================================
// AC-24: ungueltiges kind -> 400 (POST und PATCH), nichts gespeichert
// =============================================================================

func TestS3a2794_AC24_UngueltigesKindAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	for _, kind := range []string{"foo", "Route", "compare", "trip"} {
		w := v2794Anfrage(t, h, "POST", "/api/metric-presets", "alice", "de", obj{
			"name": "X " + kind, "kind": kind, "metrics": []string{"wind"}})
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-24: POST kind=%q: Status %d, erwartet 400: %s", kind, w.Code, w.Body.String())
		}
	}
	if got := v2794Datei(t, s, "alice"); len(got) != 0 {
		t.Errorf("AC-24: Vorlage mit ungueltigem kind gespeichert: %v", got)
	}
	code, p := v2794Vorlage(t, h, "alice", obj{"name": "Gut", "kind": "route"})
	if code != http.StatusCreated {
		t.Fatalf("POST Gut: %d %v", code, p)
	}
	vorher := v2794DateiRoh(t, s, "alice")
	id, _ := p["id"].(string)
	w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+id, "alice", "de", obj{"kind": "foo"})
	if w.Code != http.StatusBadRequest {
		t.Errorf("AC-24: PATCH kind=foo: Status %d, erwartet 400: %s", w.Code, w.Body.String())
	}
	if v2794DateiRoh(t, s, "alice") != vorher {
		t.Error("AC-24: abgelehntes PATCH hat die Datei veraendert")
	}
}

// =============================================================================
// AC-25: is_default exklusiv JE ART (POST und PATCH), zwei Nutzer
// =============================================================================

func TestS3a2794_AC25_IsDefaultExklusivJeArt(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	mk := func(user, name, kind string, def bool) string {
		code, resp := v2794Vorlage(t, h, user, obj{"name": name, "kind": kind, "is_default": def})
		if code != http.StatusCreated {
			t.Fatalf("POST %s/%s: %d %v", user, name, code, resp)
		}
		id, _ := resp["id"].(string)
		return id
	}
	mk("alice", "Route A", "route", true)
	idB := mk("alice", "Route B", "route", false)
	mk("alice", "Ort C", "vergleich", true)
	mk("bob", "Bob Route", "route", true)
	mk("bob", "Bob Ort", "vergleich", true)
	vorherB := v2794DateiRoh(t, s, "bob")

	// Nach dem POST von „Ort C" (vergleich) muss „Route A" Standard bleiben.
	standard := func() map[string]bool {
		out := map[string]bool{}
		for _, p := range v2794Datei(t, s, "alice") {
			out[p["name"].(string)], _ = p["is_default"].(bool)
		}
		return out
	}
	if got := standard(); !got["Route A"] || !got["Ort C"] {
		t.Errorf("AC-25 POST: Standard einer anderen Art entfernt: %v", got)
	}

	// PATCH „Route B" -> Standard: „Route A" verliert ihn, „Ort C" bleibt.
	if w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+idB, "alice", "de", obj{"is_default": true}); w.Code != http.StatusOK {
		t.Fatalf("PATCH: %d %s", w.Code, w.Body.String())
	}
	got := standard()
	if got["Route A"] || !got["Route B"] || !got["Ort C"] {
		t.Errorf("AC-25 PATCH: erwartet Route A=false, Route B=true, Ort C=true, bekam %v", got)
	}

	// POST „Route D" als Standard: Route B verliert, Ort C bleibt.
	mk("alice", "Route D", "route", true)
	got = standard()
	if got["Route B"] || !got["Route D"] || !got["Ort C"] {
		t.Errorf("AC-25 POST: erwartet Route B=false, Route D=true, Ort C=true, bekam %v", got)
	}
	if v2794DateiRoh(t, s, "bob") != vorherB {
		t.Error("AC-25: Standard-Setzen bei alice hat bob veraendert")
	}
}

// =============================================================================
// AC-25: Standard wird bei Neuanlage eines Trips angewendet (Metrik-Auswahl,
// Ampel samt alarm_ab), Orts-Standard bleibt aussen vor, je Nutzer eigener.
// Annahme: Anlage ohne mitgeschickte display_config (API-/Import-Anlage) ist
// die Neuanlage, auf die der Standard wirkt.
// =============================================================================

func v2794NeuerTrip(id string) obj {
	return obj{"id": id, "name": "Neu " + id, "stages": []obj{{
		"id": "S1", "name": "D1", "date": "2026-05-01",
		"waypoints": []obj{{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}},
	}}}
}

func v2794MetrikIDs(dc map[string]interface{}) []string {
	ms, _ := dc["metrics"].([]interface{})
	var out []string
	for _, m := range ms {
		if e, ok := m.(map[string]interface{}); ok {
			if en, ok := e["enabled"].(bool); ok && !en {
				continue
			}
			if id, ok := e["metric_id"].(string); ok {
				out = append(out, id)
			}
		}
	}
	return out
}

func TestS3a2794_AC25_NeuerTripUebernimmtStandardVorlageJeNutzer(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	metr := func(ids ...string) []obj {
		out := []obj{}
		for _, id := range ids {
			out = append(out, obj{"metric_id": id, "enabled": true, "use_friendly_format": false})
		}
		return out
	}
	ampelErste, ampelZweite, ampelOrt, ampelBob := v2794Ampel(30, "yellow"), v2794Ampel(45, "red"), v2794Ampel(50, "orange"), v2794Ampel(35, "orange")
	for _, v := range []struct {
		user, name, kind string
		def              bool
		ampel            obj
		metrics          []obj
	}{
		{"alice", "Erste", "route", false, ampelErste, metr("wind")},
		{"alice", "Zweite", "route", false, ampelZweite, metr("gust", "precipitation")},
		{"alice", "Ortsstandard", "vergleich", true, ampelOrt, metr("temperature")},
		{"bob", "Bobs Standard", "route", true, ampelBob, metr("temperature", "thunder")},
	} {
		code, resp := v2794Vorlage(t, h, v.user, obj{"name": v.name, "kind": v.kind, "is_default": v.def, "ampel": v.ampel, "metrics": v.metrics})
		if code != http.StatusCreated {
			t.Fatalf("POST %s/%s: %d %v", v.user, v.name, code, resp)
		}
		if v.name == "Zweite" {
			// „Als Standard für neue Trips" bei der zweiten setzen (AC-25 Given).
			id, _ := resp["id"].(string)
			if w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+id, "alice", "de", obj{"is_default": true}); w.Code != http.StatusOK {
				t.Fatalf("PATCH Zweite: %d %s", w.Code, w.Body.String())
			}
		}
	}

	for _, fall := range []struct {
		user    string
		ampel   obj
		metrics []string
	}{
		{"alice", ampelZweite, []string{"gust", "precipitation"}},
		{"bob", ampelBob, []string{"temperature", "thunder"}},
	} {
		w := v2794Anfrage(t, h, "POST", "/api/trips", fall.user, "de", v2794NeuerTrip("t-neu"))
		if w.Code != http.StatusCreated {
			t.Fatalf("POST /api/trips %s: %d %s", fall.user, w.Code, w.Body.String())
		}
		trip, err := s.WithUser(fall.user).LoadTrip("t-neu")
		if err != nil || trip == nil {
			t.Fatalf("LoadTrip %s: %v", fall.user, err)
		}
		if !reflect.DeepEqual(trip.DisplayConfig["ampel"], interface{}(fall.ampel)) {
			t.Errorf("AC-25 %s: neuer Trip traegt nicht die Ampel des Trip-Standards: %v", fall.user, trip.DisplayConfig["ampel"])
		}
		if got := v2794MetrikIDs(trip.DisplayConfig); !reflect.DeepEqual(got, fall.metrics) {
			t.Errorf("AC-25 %s: Metrik-Auswahl des neuen Trips %v, erwartet %v", fall.user, got, fall.metrics)
		}
	}
}

// =============================================================================
// AC-25: Standard wird bei Neuanlage eines Orts-Vergleichs angewendet; ein
// Trip-Standard wirkt dort nicht, Nutzer ohne Orts-Standard bekommt nichts.
// =============================================================================

func TestS3a2794_AC25_NeuerVergleichUebernimmtOrtsStandard(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	ampelRoute, ampelOrt := v2794Ampel(45, "red"), v2794Ampel(50, "orange")
	for _, v := range []struct {
		user, name, kind string
		ampel            obj
	}{
		{"alice", "Tripstandard", "route", ampelRoute},
		{"alice", "Ortsstandard", "vergleich", ampelOrt},
		{"bob", "Nur Trip", "route", ampelRoute},
	} {
		code, resp := v2794Vorlage(t, h, v.user, obj{"name": v.name, "kind": v.kind, "is_default": true, "ampel": v.ampel})
		if code != http.StatusCreated {
			t.Fatalf("POST %s/%s: %d %v", v.user, v.name, code, resp)
		}
	}
	anlegen := func(user string) map[string]interface{} {
		w := v2794Anfrage(t, h, "POST", "/api/compare/presets", user, "de", validPresetBody())
		if w.Code != http.StatusCreated {
			t.Fatalf("POST /api/compare/presets %s: %d %s", user, w.Code, w.Body.String())
		}
		var resp struct {
			ID string `json:"id"`
		}
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		cp, err := s.WithUser(user).LoadComparePreset(resp.ID)
		if err != nil || cp == nil {
			t.Fatalf("LoadComparePreset %s: %v", user, err)
		}
		return cp.DisplayConfig
	}
	if dc := anlegen("alice"); !reflect.DeepEqual(dc["ampel"], interface{}(ampelOrt)) {
		t.Errorf("AC-25: neuer Orts-Vergleich von alice traegt nicht die Ampel des Orts-Standards: %v", dc["ampel"])
	}
	if dc := anlegen("bob"); dc["ampel"] != nil {
		t.Errorf("AC-25: bob hat keinen Orts-Standard, Trip-Standard darf nicht wirken: %v", dc["ampel"])
	}
}
