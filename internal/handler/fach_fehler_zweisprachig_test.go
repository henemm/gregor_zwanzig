package handler

// Issue #2677 (i18n G3a) — Fachfehler der Go-API als {code, message} in der
// Sprache des Nutzers. Spec: docs/specs/modules/i18n_g3_go_handler_fach_2677.md
// AC-1 bis AC-4.
//
// Echte Kette wie im Router: AuthMiddleware (echte Sitzung) -> Lang ->
// QuotaPolicyMiddleware -> echte Handler, echter Store im Temp-Verzeichnis.
// Die deutschen Referenztexte liegen in testdata/wortgleich_de/ und wurden
// VOR der Umstellung aus dem Code von origin/main kopiert. Kein Mock.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const g3Secret = "test-secret-32-chars-long-enough!"

// g3Nutzer legt einen verifizierten Nutzer mit Sprache und Tarif an und
// liefert ein gueltiges Sitzungs-Cookie.
func g3Nutzer(t *testing.T, s *store.Store, id, lang, tier string) *http.Cookie {
	t.Helper()
	now := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: id, Email: id + "@example.com", Language: lang, Tier: tier,
		EmailVerifiedAt: &now, CreatedAt: now}); err != nil {
		t.Fatalf("SaveUser %s: %v", id, err)
	}
	sid, err := middleware.NewSessionID()
	if err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(id, sid); err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "gz_session", Value: middleware.SignSessionWithID(id, sid, g3Secret)}
}

// g3Router baut die Produktions-Reihenfolge mit den betroffenen Routen.
func g3Router(s *store.Store, pythonURL string) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.AuthMiddleware(g3Secret, s))
	r.Use(middleware.Lang(s))
	r.Use(QuotaPolicyMiddleware(nil, nil))
	r.Get("/api/briefings/{id}", GetBriefingHandler(s))
	r.Put("/api/briefings/{id}", UpdateBriefingHandler(s))
	r.Post("/api/briefings/{id}/send", BriefingSendHandler(pythonURL))
	r.Post("/api/trips", CreateTripHandler(s))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Post("/api/locations", CreateLocationHandler(s))
	r.Delete("/api/locations/{id}", DeleteLocationHandler(s))
	r.Post("/api/locations/resolve", ResolveLocationHandler())
	return r
}

func g3Do(h http.Handler, c *http.Cookie, method, path, body, ifMatch string) *httptest.ResponseRecorder {
	var req *http.Request
	if body == "" {
		req = httptest.NewRequest(method, path, nil)
	} else {
		req = httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	}
	if ifMatch != "" {
		req.Header.Set("If-Match", ifMatch)
	}
	req.AddCookie(c)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func g3Body(t *testing.T, w *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort ist kein JSON: %v (%s)", err, w.Body.String())
	}
	return body
}

func g3Golden(t *testing.T, name string) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", "wortgleich_de", name+".txt"))
	if err != nil {
		t.Fatalf("Golden %s fehlt: %v", name, err)
	}
	return string(data)
}

func g3SeedTrip(t *testing.T, s *store.Store, uid, id, name string) {
	t.Helper()
	trip := model.Trip{ID: id, Name: name, Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
		Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}}}
	if err := s.WithUser(uid).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func g3SeedPreset(t *testing.T, s *store.Store, uid, id string) {
	t.Helper()
	if err := s.WithUser(uid).SaveComparePreset(quotePreset(uid, id)); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
}

// g3Veraltet erzeugt einen veralteten Stempel: GET holt ihn, eine zweite
// Aenderung dazwischen macht ihn ungueltig.
func g3Veraltet(t *testing.T, h http.Handler, c *http.Cookie, id string) string {
	t.Helper()
	get := g3Do(h, c, http.MethodGet, "/api/briefings/"+id+"?kind=vergleich", "", "")
	alt := get.Header().Get("ETag")
	if get.Code != http.StatusOK || alt == "" {
		t.Fatalf("GET: Status %d, ETag %q: %s", get.Code, alt, get.Body.String())
	}
	if w := g3Do(h, c, http.MethodPut, "/api/briefings/"+id+"?kind=vergleich", `{"name":"Zwischendurch"}`, alt); w.Code != http.StatusOK {
		t.Fatalf("Zwischen-PUT: Status %d: %s", w.Code, w.Body.String())
	}
	return alt
}

// AC-1: en-Nutzer, veralteter If-Match auf kind=vergleich -> 412 englisch, kein ETag.
func TestG3PreconditionFailedAufEnglisch(t *testing.T) {
	s := store.New(t.TempDir(), "")
	c := g3Nutzer(t, s, "anna-en", "en", "premium")
	g3SeedPreset(t, s, "anna-en", "cp-g3")
	h := g3Router(s, "")
	alt := g3Veraltet(t, h, c, "cp-g3")

	w := g3Do(h, c, http.MethodPut, "/api/briefings/cp-g3?kind=vergleich", `{"name":"Spaet"}`, alt)

	if w.Code != http.StatusPreconditionFailed {
		t.Fatalf("AC-1: Status %d, erwartet 412: %s", w.Code, w.Body.String())
	}
	if et := w.Header().Get("ETag"); et != "" {
		t.Errorf("AC-1: 412 traegt ETag %q", et)
	}
	b := g3Body(t, w)
	want := "The data was changed elsewhere in the meantime. Please reload and make your change again."
	if b["code"] != "precondition_failed" || b["error"] != "precondition_failed" || b["message"] != want {
		t.Errorf("AC-1: Antwort %v, erwartet code precondition_failed, message %q", b, want)
	}
}

type g3Fall struct {
	name, golden string
	status       int
	code         string
	auslösen     func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder
}

func g3DeFaelle() []g3Fall {
	tot := "http://127.0.0.1:1"
	return []g3Fall{
		{"412", "precondition_failed", 412, "precondition_failed", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			g3SeedPreset(t, s, "bert-de", "cp-de")
			alt := g3Veraltet(t, h, c, "cp-de")
			return g3Do(h, c, http.MethodPut, "/api/briefings/cp-de?kind=vergleich", `{"name":"Spaet"}`, alt)
		}},
		{"Kennung durch Trip belegt", "id_conflict", 409, "id_conflict", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			g3SeedTrip(t, s, "bert-de", "belegt", "Trip")
			alt := newComparePresetID
			newComparePresetID = func() string { return "belegt" }
			defer func() { newComparePresetID = alt }()
			return g3Do(h, c, http.MethodPost, "/api/compare/presets", quotePresetBody("Neu"), "")
		}},
		{"Kennung durch Ortsvergleich belegt", "id_conflict_vergleich", 409, "id_conflict", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			g3SeedPreset(t, s, "bert-de", "cp-belegt")
			return g3Do(h, c, http.MethodPost, "/api/trips", quoteTripBody("cp-belegt"), "")
		}},
		{"Ort existiert", "conflict", 409, "conflict", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			quoteSeedLocations(t, s, "bert-de", 1)
			return g3Do(h, c, http.MethodPost, "/api/locations", `{"id":"seed-ort-0","name":"Ort 0","lat":47,"lon":11}`, "")
		}},
		{"Datei gesperrt", "busy", 503, "busy", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			g3SeedTrip(t, s, "bert-de", "t-lock", "Trip")
			release := p2158Fremdsperre(t, s, "bert-de", "t-lock")
			defer release()
			defer store.SetBriefingLockTimeout(100 * time.Millisecond)()
			w := g3Do(h, c, http.MethodGet, "/api/briefings/t-lock?kind=route", "", "")
			if w.Header().Get("Retry-After") != "5" {
				t.Errorf("busy: Retry-After %q, erwartet 5", w.Header().Get("Retry-After"))
			}
			return w
		}},
		{"ungueltige Briefing-Kennung", "validation_error_kennung", 400, "validation_error", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			return g3Do(h, c, http.MethodPost, "/api/briefings/.versteckt/send?kind=route", "", "")
		}},
		{"Versand ohne kind", "kind_required", 400, "kind_required", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			return g3Do(h, c, http.MethodPost, "/api/briefings/t1/send", "", "")
		}},
		{"Versanddienst nicht erreichbar", "upstream_unreachable_versand", 502, "upstream_unreachable", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			return g3Do(g3Router(s, tot), c, http.MethodPost, "/api/briefings/t1/send?kind=route", "", "")
		}},
		{"Versand nicht startbar", "proxy_error_versand", 500, "proxy_error", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			return g3Do(g3Router(s, "http://127.0.0.1\x7f"), c, http.MethodPost, "/api/briefings/t1/send?kind=route", "", "")
		}},
		{"Feld input fehlt", "bad_request_input", 400, "bad_request", func(t *testing.T, s *store.Store, h http.Handler, c *http.Cookie) *httptest.ResponseRecorder {
			return g3Do(h, c, http.MethodPost, "/api/locations/resolve", `{}`, "")
		}},
	}
}

// AC-2: de-Nutzer, jeder Fehlerfall -> message UND detail byte-gleich zum Golden.
func TestG3DeutscheTexteWortgleich(t *testing.T) {
	for _, f := range g3DeFaelle() {
		t.Run(f.name, func(t *testing.T) {
			s := store.New(t.TempDir(), "")
			c := g3Nutzer(t, s, "bert-de", "de", "premium")
			w := f.auslösen(t, s, g3Router(s, ""), c)
			if w.Code != f.status {
				t.Fatalf("Status %d, erwartet %d: %s", w.Code, f.status, w.Body.String())
			}
			b := g3Body(t, w)
			want := g3Golden(t, f.golden)
			if b["code"] != f.code || b["message"] != want || b["detail"] != want {
				t.Errorf("Antwort %v\nerwartet code %q, message=detail %q", b, f.code, want)
			}
		})
	}
}

type g3Quote struct {
	res, path string
	seed      func(t *testing.T, s *store.Store, uid string)
	body      string
}

func g3Quoten() []g3Quote {
	return []g3Quote{
		{"trips", "/api/trips", func(t *testing.T, s *store.Store, uid string) { quoteSeedTrips(t, s, uid, 3, 0) }, quoteTripBody("neu")},
		{"compare_presets", "/api/compare/presets", func(t *testing.T, s *store.Store, uid string) { quoteSeedPresets(t, s, uid, 2, 0) }, quotePresetBody("Neu")},
		{"locations", "/api/locations", func(t *testing.T, s *store.Store, uid string) { quoteSeedLocations(t, s, uid, 10) }, quoteLocationBody("Neu")},
	}
}

func g3QuoteAufrufen(t *testing.T, q g3Quote, uid, lang string) (map[string]any, int) {
	t.Helper()
	s := store.New(t.TempDir(), "")
	c := g3Nutzer(t, s, uid, lang, "free")
	q.seed(t, s, uid)
	w := g3Do(g3Router(s, ""), c, http.MethodPost, q.path, q.body, "")
	if w.Code != http.StatusConflict {
		t.Fatalf("Status %d, erwartet 409: %s", w.Code, w.Body.String())
	}
	b := g3Body(t, w)
	lim := map[string]int{"trips": 3, "compare_presets": 2, "locations": 10}[q.res]
	if b["code"] != "quota_exceeded" || b["error"] != "quota_exceeded" || b["resource"] != q.res ||
		b["limit"] != float64(lim) || b["current"] != float64(lim) {
		t.Errorf("Code/Zusatzfelder falsch: %v", b)
	}
	return b, lim
}

// AC-3: en-Nutzer im Tarif free, Kontingent erreicht -> englische Meldung mit Zahlen.
func TestG3KontingentAufEnglisch(t *testing.T) {
	en := map[string]string{
		"trips":           "You already have %d of %d trips on your plan. Archive or delete a trip to create a new one.",
		"compare_presets": "You already have %d of %d location comparisons on your plan. Archive or delete a location comparison to create a new one.",
		"locations":       "You already have %d of %d locations on your plan. Delete a location to create a new one.",
	}
	for _, q := range g3Quoten() {
		t.Run(q.res, func(t *testing.T) {
			b, lim := g3QuoteAufrufen(t, q, "anna-en", "en")
			if want := fmt.Sprintf(en[q.res], lim, lim); b["message"] != want {
				t.Errorf("message %q, erwartet %q", b["message"], want)
			}
		})
	}
}

// AC-2 (Kontingent): de-Nutzer -> Golden-Wortlaut mit den echten Zahlen.
func TestG3KontingentDeutschWortgleich(t *testing.T) {
	for _, q := range g3Quoten() {
		t.Run(q.res, func(t *testing.T) {
			b, lim := g3QuoteAufrufen(t, q, "bert-de", "de")
			want := strings.Replace(g3Golden(t, "quota_exceeded_"+q.res), "1 von 1", fmt.Sprintf("%d von %d", lim, lim), 1)
			if b["message"] != want || b["detail"] != want {
				t.Errorf("message/detail %q/%q, erwartet %q", b["message"], b["detail"], want)
			}
		})
	}
}

// AC-4: zwei Nutzer (en/de), parallel, je fremde Kennung -> 404 in eigener
// Sprache; die gleiche Kennung liefert jedem nur den eigenen Trip.
func TestG3ZweiNutzerNichtGefundenJeSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	cA := g3Nutzer(t, s, "anna-en", "en", "premium")
	cB := g3Nutzer(t, s, "bert-de", "de", "premium")
	g3SeedTrip(t, s, "anna-en", "a-tour", "Annas Tour")
	g3SeedTrip(t, s, "bert-de", "b-tour", "Berts Tour")
	g3SeedTrip(t, s, "anna-en", "gleich", "Anna gleich")
	g3SeedTrip(t, s, "bert-de", "gleich", "Bert gleich")
	h := g3Router(s, "")

	type fall struct {
		c              *http.Cookie
		fremd, msg, ok string
	}
	faelle := []fall{{cA, "b-tour", "Not found.", "Anna gleich"}, {cB, "a-tour", "Nicht gefunden.", "Bert gleich"}}
	var wg sync.WaitGroup
	fehler := make(chan string, 80)
	for i := 0; i < 20; i++ {
		for _, f := range faelle {
			wg.Add(1)
			go func(f fall) {
				defer wg.Done()
				w := g3Do(h, f.c, http.MethodGet, "/api/briefings/"+f.fremd+"?kind=route", "", "")
				var b map[string]any
				_ = json.Unmarshal(w.Body.Bytes(), &b)
				if w.Code != 404 || b["code"] != "not_found" || b["message"] != f.msg || strings.Contains(w.Body.String(), "Tour") {
					fehler <- fmt.Sprintf("fremd %s: %d %s", f.fremd, w.Code, w.Body.String())
				}
				w = g3Do(h, f.c, http.MethodGet, "/api/briefings/gleich?kind=route", "", "")
				if w.Code != 200 || !strings.Contains(w.Body.String(), f.ok) {
					fehler <- fmt.Sprintf("eigen gleich: %d %s", w.Code, w.Body.String())
				}
			}(f)
		}
	}
	wg.Wait()
	close(fehler)
	for f := range fehler {
		t.Errorf("AC-4: %s", f)
	}
}

// Ort noch im Ortsvergleich: Zusatzfeld compare_presets bleibt, Meldung englisch.
func TestG3OrtInVerwendungAufEnglisch(t *testing.T) {
	s := store.New(t.TempDir(), "")
	c := g3Nutzer(t, s, "anna-en", "en", "premium")
	quoteSeedLocations(t, s, "anna-en", 1)
	p := quotePreset("anna-en", "cp-ort")
	p.LocationIDs = []string{"seed-ort-0", "x"}
	if err := s.WithUser("anna-en").SaveComparePreset(p); err != nil {
		t.Fatal(err)
	}
	w := g3Do(g3Router(s, ""), c, http.MethodDelete, "/api/locations/seed-ort-0", "", "")
	if w.Code != http.StatusConflict {
		t.Fatalf("Status %d, erwartet 409: %s", w.Code, w.Body.String())
	}
	b := g3Body(t, w)
	refs, _ := b["compare_presets"].([]any)
	if b["code"] != "location_in_use" || len(refs) != 1 ||
		b["message"] != "This location is still used by at least one location comparison." {
		t.Errorf("Antwort %v", b)
	}
}

// Technische Validator-Texte bleiben als detail, message ist der Katalogtext.
func TestG3ValidierungBehaeltTechnischesDetail(t *testing.T) {
	s := store.New(t.TempDir(), "")
	c := g3Nutzer(t, s, "anna-en", "en", "premium")
	w := g3Do(g3Router(s, ""), c, http.MethodPost, "/api/trips", `{"name":"ohne id"}`, "")
	if w.Code != http.StatusBadRequest {
		t.Fatalf("Status %d: %s", w.Code, w.Body.String())
	}
	b := g3Body(t, w)
	if b["code"] != "validation_error" || b["message"] != "The input is invalid." || b["detail"] != "id required" {
		t.Errorf("Antwort %v", b)
	}
}

// Ankertabelle: jeder neue Schluessel fach.fehler.* mit festem de|en-Wert.
// de mit Altzustand stammt aus dem Golden (origin/main), sonst aus der Spec.
func TestG3AnkertabelleFachFehler(t *testing.T) {
	anker := []struct{ key, golden, de, en string }{
		{"fach.fehler.precondition_failed", "precondition_failed", "", "The data was changed elsewhere in the meantime. Please reload and make your change again."},
		{"fach.fehler.id_conflict", "id_conflict", "", "This ID is already used by a trip or location comparison. Please choose a different name."},
		{"fach.fehler.id_conflict_vergleich", "id_conflict_vergleich", "", "A location comparison already uses this ID. Please choose a different name."},
		{"fach.fehler.conflict", "conflict", "", "A location with this ID already exists."},
		{"fach.fehler.location_in_use", "", "Dieser Ort wird noch von mindestens einem Ortsvergleich verwendet.", "This location is still used by at least one location comparison."},
		{"fach.fehler.busy", "busy", "", "The file is locked at the moment. Please try again."},
		{"fach.fehler.validation_error_kennung", "validation_error_kennung", "", "Invalid briefing ID"},
		{"fach.fehler.proxy_error_versand", "proxy_error_versand", "", "Sending could not be started. Please try again later."},
		{"fach.fehler.upstream_unreachable_versand", "upstream_unreachable_versand", "", "The sending service is not reachable. Please try again later."},
		{"fach.fehler.bad_request_input", "bad_request_input", "", "The field 'input' is missing."},
		{"fach.fehler.upstream_unreachable", "", "Der Dienst ist nicht erreichbar.", "The service is not reachable."},
		{"fach.fehler.name_required", "", "Der Name fehlt.", "The name is required."},
		{"fach.fehler.name_exists", "", "Dieser Name ist bereits vergeben.", "This name is already in use."},
		{"fach.fehler.invalid_params", "", "Die Parameter sind ungültig.", "The parameters are invalid."},
		{"fach.fehler.budget_exceeded", "", "Das Tageskontingent für Wetterabfragen ist aufgebraucht.", "The daily quota for forecast requests is used up."},
		{"fach.fehler.provider_error", "", "Der Wetteranbieter ist nicht erreichbar.", "The weather provider is not reachable."},
		{"fach.fehler.unknown_format", "", "Das Format wurde nicht erkannt.", "The format was not recognized."},
		{"fach.fehler.unsupported_url", "", "Diese Adresse wird nicht unterstützt.", "This address is not supported."},
		{"fach.fehler.resolve_failed", "", "Die Auflösung ist fehlgeschlagen.", "The lookup failed."},
	}
	for _, a := range anker {
		de := a.de
		if a.golden != "" {
			de = g3Golden(t, a.golden)
		}
		if !i18n.Has(a.key) {
			t.Errorf("%s fehlt im Katalog", a.key)
			continue
		}
		if got := i18n.T(i18n.De, a.key, nil); got != de {
			t.Errorf("%s de %q, erwartet %q", a.key, got, de)
		}
		if got := i18n.T(i18n.En, a.key, nil); got != a.en {
			t.Errorf("%s en %q, erwartet %q", a.key, got, a.en)
		}
	}
	// Kontingent: Golden ist mit current=1, limit=1 gerendert (exakter Wortlaut).
	for _, res := range []string{"trips", "compare_presets", "locations"} {
		got := i18n.T(i18n.De, "fach.fehler.quota_exceeded_"+res, i18n.Args{"current": 1, "limit": 1})
		if want := g3Golden(t, "quota_exceeded_"+res); got != want {
			t.Errorf("quota %s de %q, erwartet %q", res, got, want)
		}
	}
	if i18n.Has("fach.fehler.quota_exceeded") {
		t.Errorf("fach.fehler.quota_exceeded ohne Variante darf es nicht geben")
	}
}

// --- G3b: Proxy und uebrige Nutzer-Handler -----------------------------------

// g3bDo ruft h durch die echte Lang-Middleware als Nutzer uid (leer = ohne Kontext).
func g3bDo(s *store.Store, h http.Handler, uid, acc, method, path string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, nil)
	if uid != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	}
	if acc != "" {
		req.Header.Set("Accept-Language", acc)
	}
	w := httptest.NewRecorder()
	middleware.Lang(s)(h).ServeHTTP(w, req)
	return w
}

func g3bPruefe(t *testing.T, fall string, w *httptest.ResponseRecorder, status int, code, msg string) {
	t.Helper()
	if w.Code != status {
		t.Fatalf("%s: Status %d, erwartet %d (%s)", fall, w.Code, status, w.Body.String())
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Errorf("%s: Content-Type %q, erwartet application/json", fall, ct)
	}
	b := g3Body(t, w)
	if b["code"] != code || b["error"] != code || b["message"] != msg {
		t.Errorf("%s: Antwort %v, erwartet code %q message %q", fall, b, code, msg)
	}
}

func g3bTot(t *testing.T) string {
	srv := httptest.NewServer(http.NewServeMux())
	srv.Close()
	return srv.URL
}

// Go-eigene Proxy-Fehler in Nutzersprache; zwei Nutzer (en/de) in einem Lauf.
func TestG3bProxyFehlerJeSprache(t *testing.T) {
	s := store.New(t.TempDir(), "")
	mustSaveUser(t, s, model.User{ID: "anna-en", Language: "en"})
	mustSaveUser(t, s, model.User{ID: "bert-de", Language: "de"})
	tot := g3bTot(t)
	for _, u := range []struct{ id, core, upstream string }{
		{"anna-en", "The core service is not reachable right now. Please try again later.", "The service is not reachable."},
		{"bert-de", "Der Kern-Dienst ist gerade nicht erreichbar. Bitte versuche es später erneut.", "Der Dienst ist nicht erreichbar."},
	} {
		w := g3bDo(s, ProxyHandler(tot, "/api/x"), u.id, "", http.MethodGet, "/api/x")
		g3bPruefe(t, "core_unavailable "+u.id, w, 503, "core_unavailable", u.core)
		w = g3bDo(s, StagesWeatherProxyHandler(tot), u.id, "", http.MethodGet, "/api/trips/t1/stages/weather")
		g3bPruefe(t, "upstream_unreachable "+u.id, w, 502, "upstream_unreachable", u.upstream)
	}
	w := g3bDo(s, NextBriefingsProxyHandler(tot), "", "en", http.MethodGet, "/api/next-briefings")
	g3bPruefe(t, "next-briefings ohne Nutzer", w, 401, "unauthorized", "Please sign in.")
}

// Python-Antworten gehen unveraendert durch (Status, Body).
func TestG3bProxyReichtPythonDurch(t *testing.T) {
	s := store.New(t.TempDir(), "")
	mustSaveUser(t, s, model.User{ID: "anna-en", Language: "en"})
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusConflict)
		w.Write([]byte(`{"detail":"Python sagt nein","code":"py_code"}`))
	}))
	defer py.Close()
	w := g3bDo(s, StagesWeatherProxyHandler(py.URL), "anna-en", "", http.MethodGet, "/api/trips/t1/stages/weather")
	if w.Code != http.StatusConflict || w.Body.String() != `{"detail":"Python sagt nein","code":"py_code"}` {
		t.Errorf("Python-Antwort veraendert: %d %s", w.Code, w.Body.String())
	}
}

// Klartext-http.Error der Nutzer-Handler wird JSON mit Code (Telegram, Premium-SMS-Code, Export).
func TestG3bNutzerHandlerKlartextWirdJSON(t *testing.T) {
	s := store.New(t.TempDir(), "")
	ts := NewTelegramTokenStore(t.TempDir())
	faelle := []struct {
		name          string
		h             http.Handler
		uid, acc      string
		status        int
		code, message string
	}{
		{"telegram-status ohne Nutzer", GetTelegramStatusHandler(s), "", "en", 401, "unauthorized", "Please sign in."},
		{"telegram-status unbekannt", GetTelegramStatusHandler(s), "geist", "en", 404, "not_found", "Not found."},
		{"telegram-link ohne Bot", GetTelegramLinkHandler(s, ts, ""), "geist", "de", 500, "service_unavailable", "Der Dienst ist gerade nicht verfügbar."},
		{"telegram-link unbekannt", GetTelegramLinkHandler(s, ts, "bot"), "geist", "en", 404, "not_found", "Not found."},
		{"link-code GET ohne Nutzer", GetPremiumSmsLinkCodeHandler(s), "", "en", 401, "unauthorized", "Please sign in."},
		{"link-code POST ohne Nutzer", PostPremiumSmsLinkCodeHandler(s, 4), "", "de", 401, "unauthorized", "Bitte melde dich an."},
		{"export ohne Nutzer", ExportUserDataHandler(s), "", "en", 401, "unauthorized", "Please sign in."},
	}
	for _, f := range faelle {
		w := g3bDo(s, f.h, f.uid, f.acc, http.MethodGet, "/x")
		g3bPruefe(t, f.name, w, f.status, f.code, f.message)
	}
}
