package resolver_test

// Issue #2677 (i18n G3b) — Resolver-Meldungen zweisprachig.
// Spec: docs/specs/modules/i18n_g3_go_handler_fach_2677.md — AC-5.
//
// testdata/meldungen_de.json wurde VOR der Umstellung aus den Quellzeilen von
// origin/main erzeugt (24 Meldungen laut grep "Message:"). Die Handler-Probe
// laeuft durch die echte Lang-Middleware und den echten Resolve-Handler.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/resolver"
	"github.com/henemm/gregor-api/internal/store"
)

func meldungenDe(t *testing.T) map[string]string {
	t.Helper()
	data, err := os.ReadFile("testdata/meldungen_de.json")
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatal(err)
	}
	if len(m) != 24 {
		t.Fatalf("Golden hat %d Meldungen, erwartet 24", len(m))
	}
	return m
}

// meldungenEn ist die feste englische Ankertabelle.
var meldungenEn = map[string]string{
	"fach.resolver.format":                  "The format was not recognized. Please enter a Komoot highlight URL, a Google Maps link or coordinates.",
	"fach.resolver.maps_aufloesen":          "The Google Maps link could not be resolved.",
	"fach.resolver.maps_koordinaten":        "Could not extract coordinates from the Google Maps link.",
	"fach.resolver.komoot_sammlung":         "Komoot routes and collections are not supported. Please use a Komoot highlight link.",
	"fach.resolver.komoot_url":              "Komoot URL not recognized. Please use a Komoot highlight link.",
	"fach.resolver.komoot_anfrage":          "The Komoot request could not be created.",
	"fach.resolver.komoot_api":              "Komoot API not reachable.",
	"fach.resolver.komoot_status":           "Komoot API responded with status {status}.",
	"fach.resolver.komoot_antwort":          "The Komoot response could not be read.",
	"fach.resolver.komoot_ohne_koordinaten": "The Komoot highlight contains no coordinates.",
	"fach.resolver.decimal_unbekannt":       "Could not recognize decimal coordinates.",
	"fach.resolver.decimal_parse":           "Decimal coordinates could not be parsed.",
	"fach.resolver.bereich":                 "Coordinates are outside the valid range (lat ∈ [-90,90], lon ∈ [-180,180]).",
	"fach.resolver.dms_unbekannt":           "DMS format not recognized.",
	"fach.resolver.dms_bereich":             "DMS coordinates are outside the valid range.",
	"fach.resolver.utm_unbekannt":           "UTM format not recognized.",
	"fach.resolver.utm_zone":                "UTM zone outside [1,60].",
	"fach.resolver.utm_band":                "Invalid UTM band.",
	"fach.resolver.utm_easting":             "Easting could not be parsed.",
	"fach.resolver.utm_northing":            "Northing could not be parsed.",
	"fach.resolver.utm_konvertierung":       "UTM conversion returned invalid coordinates.",
	"fach.resolver.gpx_unbekannt":           "GPX waypoint not recognized.",
	"fach.resolver.gpx_parse":               "The GPX waypoint could not be parsed.",
	"fach.resolver.gpx_bereich":             "GPX coordinates are outside the valid range.",
}

// AC-5 (Katalog): jede deutsche Meldung wortgleich zum Golden, jede englische
// laut Ankertabelle vorhanden und nicht leer.
func TestResolverMeldungenKatalogWortgleich(t *testing.T) {
	for key, de := range meldungenDe(t) {
		if !i18n.Has(key) {
			t.Errorf("%s fehlt im Katalog", key)
			continue
		}
		args := i18n.Args{}
		want := de
		if strings.Contains(de, "%d") {
			args["status"] = 503
			want = fmt.Sprintf(de, 503)
		}
		if got := i18n.T(i18n.De, key, args); got != want {
			t.Errorf("%s de %q, erwartet %q", key, got, want)
		}
		en, ok := meldungenEn[key]
		if !ok || en == "" {
			t.Errorf("%s ohne englischen Anker", key)
			continue
		}
		if got := i18n.T(i18n.En, key, nil); got != en {
			t.Errorf("%s en %q, erwartet %q", key, got, en)
		}
	}
}

// AC-5 (Ausloeser): netzfreie Eingaben -> unveraenderter Code, Schluessel und
// deutsche Message wortgleich zum Golden.
func TestResolverAusloeserTragenSchluessel(t *testing.T) {
	golden := meldungenDe(t)
	faelle := []struct{ input, code, key string }{
		{"irgendwas", "unknown_format", "fach.resolver.format"},
		{"https://www.komoot.com/de-de/tour/123", "unsupported_url", "fach.resolver.komoot_sammlung"},
		{"https://www.komoot.com/de-de/user/abc", "unsupported_url", "fach.resolver.komoot_url"},
		{"95.0, 10.0", "unknown_format", "fach.resolver.bereich"},
		{"47° Nord", "unknown_format", "fach.resolver.dms_unbekannt"},
		{`95°0'0"N 10°0'0"E`, "unknown_format", "fach.resolver.dms_bereich"},
		{"61U 500000 5000000", "unknown_format", "fach.resolver.utm_zone"},
		{"32I 500000 5000000", "unknown_format", "fach.resolver.utm_band"},
		{`<trkpt lat="47.1"`, "unknown_format", "fach.resolver.gpx_unbekannt"},
		{`<trkpt lat="x" lon="1"/>`, "unknown_format", "fach.resolver.gpx_parse"},
		{`<trkpt lat="95" lon="10"/>`, "unknown_format", "fach.resolver.gpx_bereich"},
		{"http://\x7f.google.de/maps", "resolve_failed", "fach.resolver.maps_aufloesen"},
	}
	for _, f := range faelle {
		_, err := resolver.Resolve(f.input)
		re, ok := err.(*resolver.ResolveError)
		if !ok {
			t.Errorf("%q: kein ResolveError: %v", f.input, err)
			continue
		}
		if re.Code != f.code || re.Key != f.key || re.Message != golden[f.key] {
			t.Errorf("%q: Code %q Key %q Message %q, erwartet %q %q %q", f.input, re.Code, re.Key, re.Message, f.code, f.key, golden[f.key])
		}
	}
}

// AC-5 (Handler): en-Nutzer -> 422, Code unveraendert, Meldung englisch;
// de-Nutzer -> wortgleich zum Golden. Zwei Nutzer, ein Lauf.
func TestResolveHandlerMeldungJeSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	for _, u := range []model.User{{ID: "anna-en", Language: "en"}, {ID: "bert-de", Language: "de"}} {
		if err := s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}
	golden := meldungenDe(t)
	h := middleware.Lang(s)(handler.ResolveLocationHandler())
	faelle := []struct{ uid, input, code, want string }{
		{"anna-en", "https://www.komoot.com/de-de/collection/9", "unsupported_url", meldungenEn["fach.resolver.komoot_sammlung"]},
		{"anna-en", "95.0, 10.0", "unknown_format", meldungenEn["fach.resolver.bereich"]},
		{"anna-en", "irgendwas", "unknown_format", meldungenEn["fach.resolver.format"]},
		{"bert-de", "https://www.komoot.com/de-de/collection/9", "unsupported_url", golden["fach.resolver.komoot_sammlung"]},
		{"bert-de", "irgendwas", "unknown_format", golden["fach.resolver.format"]},
	}
	for _, f := range faelle {
		body, _ := json.Marshal(map[string]string{"input": f.input})
		req := httptest.NewRequest(http.MethodPost, "/api/locations/resolve", strings.NewReader(string(body)))
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), f.uid))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		var got map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &got)
		if w.Code != 422 || got["code"] != f.code || got["error"] != f.code || got["message"] != f.want ||
			!strings.HasPrefix(w.Header().Get("Content-Type"), "application/json") {
			t.Errorf("%s %q: %d %v, erwartet 422 %s %q", f.uid, f.input, w.Code, got, f.code, f.want)
		}
	}
}
