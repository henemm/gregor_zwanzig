package handler

// TDD RED — Issue #2391 (Scheibe S3 von #2150, Epic #2138 Multi-User).
// Spec: docs/specs/modules/forecast_go_pfad_kontingent.md (AC-2, AC-4 bis AC-7)
//
// Von den Tests geforderte, neue Produktiv-Signatur (RED-Contract):
//
//	ForecastHandler(p provider.WeatherProvider, coreURL string) http.HandlerFunc
//
// Die Core-Basis-URL reicht internal/router/router.go aus deps.Config.PythonCoreURL
// durch (Spec, Abschnitt "Router"). Bis die Signatur existiert, uebersetzt das
// gesamte Paket internal/handler nicht — das ist der ERWARTETE RED-Beleg dieser
// Datei und legt zugleich alle uebrigen Tests des Pakets lahm.
//
// AC-1, AC-3, AC-8 und AC-9 liegen Python-seitig
// (tests/tdd/test_internal_forecast_budget_reserve.py): sie messen die Buchung
// gegen die echte Zaehlerdatei, was aus `go test` heraus nicht erreichbar ist.
//
// KEIN Mock: der Python-Core wird durch einen echten httptest-Server vertreten,
// der Wetter-Provider durch eine gewoehnliche Struktur mit Aufrufzaehler. Kein
// t.Parallel() in dieser Datei — der Fail-open-Nachweis (AC-5) haengt an
// log.SetOutput, und das ist prozessglobal.

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
)

const (
	nutzerA = "nutzer-a"
	nutzerB = "nutzer-b"
	// Obergrenze fuer Retry-After: der Zaehler wird an der UTC-Tagesgrenze
	// zurueckgesetzt, mehr als ein voller Tag kann nie herauskommen.
	sekundenJeTag = 86400
)

// zaehlenderProvider ist eine echte provider.WeatherProvider-Implementierung
// mit Aufrufzaehler (KEIN unittest-artiger Mock). Der Zaehler ist der Pruefling
// der Zusicherung "KEIN Abruf": ein Handler, der 429 oder 401 antwortet und
// Open-Meteo trotzdem anzapft, waere statuscode-gruen und fachlich das genaue
// Gegenteil des Tickets.
type zaehlenderProvider struct {
	aufrufe int
}

func (z *zaehlenderProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	z.aufrufe++
	return &model.Timeseries{
		Timezone: "Europe/Berlin",
		Meta:     model.ForecastMeta{Provider: "test", Model: "test-model", GridResKm: 2},
		Data:     []model.ForecastDataPoint{},
	}, nil
}

var _ provider.WeatherProvider = (*zaehlenderProvider)(nil)

// coreStub vertritt den Python-Core. Er schreibt JEDE empfangene Query mit —
// erst dadurch ist pruefbar, was am Core tatsaechlich ANKOMMT (AC-4), statt nur
// ein vorgegebenes Urteil zu befolgen.
// Der Mutex ist keine Zierde: der httptest-Handler laeuft in einer eigenen
// Goroutine, die Zusicherungen lesen aus der Test-Goroutine. Ohne Sperre waere
// die Datei unter `go test -race` aus einem Grund rot, der nichts mit der
// Implementierung zu tun hat.
type coreStub struct {
	server   *httptest.Server
	mu       sync.Mutex
	empfitem []url.Values
	pfade    []string
}

// neuerCoreStub baut einen Core-Stub, dessen Urteil von der empfangenen user_id
// abhaengt. `abgelehnt` nennt die Kennungen, fuer die der Core
// `allowed: false` liefert.
func neuerCoreStub(t *testing.T, abgelehnt ...string) *coreStub {
	t.Helper()
	stub := &coreStub{}
	verweigert := map[string]bool{}
	for _, u := range abgelehnt {
		verweigert[u] = true
	}
	stub.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		stub.mu.Lock()
		stub.empfitem = append(stub.empfitem, r.URL.Query())
		stub.pfade = append(stub.pfade, r.URL.Path)
		stub.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if verweigert[r.URL.Query().Get("user_id")] {
			json.NewEncoder(w).Encode(map[string]interface{}{
				"allowed":       false,
				"retry_after_s": 3600,
			})
			return
		}
		json.NewEncoder(w).Encode(map[string]interface{}{"allowed": true})
	}))
	t.Cleanup(stub.server.Close)
	return stub
}

func (c *coreStub) url() string { return c.server.URL }

func (c *coreStub) aufrufe() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.empfitem)
}

func (c *coreStub) letzte() url.Values {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.empfitem) == 0 {
		return url.Values{}
	}
	return c.empfitem[len(c.empfitem)-1]
}

func (c *coreStub) ersterPfad() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.pfade) == 0 {
		return ""
	}
	return c.pfade[0]
}

// angemeldet baut einen Request mit gesetztem Auth-Kontext (Muster
// middleware.ContextWithUserID, genutzt von allen Handler-Tests mit Anmeldung).
func angemeldet(methode, ziel, userID string) *http.Request {
	req := httptest.NewRequest(methode, ziel, nil)
	return req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
}

// dekodiere liest den JSON-Koerper einer Antwort.
func dekodiere(t *testing.T, rec *httptest.ResponseRecorder) map[string]interface{} {
	t.Helper()
	var result map[string]interface{}
	if err := json.NewDecoder(rec.Body).Decode(&result); err != nil {
		t.Fatalf("invalid JSON response (%d): %v — Koerper: %q", rec.Code, err, rec.Body.String())
	}
	return result
}

// =============================================================================
// Bestandsfaelle: Parametervalidierung behaelt ihre 400-Erwartung
// Spec AC-7, Zusatz: "bekommen einen gueltigen Auth-Kontext gesetzt und
// behalten ihre bestehende 400-Erwartung UNVERAENDERT."
// =============================================================================

func TestForecastHandler_ValidRequest_Returns200(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test in short mode")
	}
	// GIVEN: ForecastHandler mit echtem Provider und erlaubender Reservierung
	// WHEN: GET /api/forecast?lat=39.7&lon=3.0&hours=24 mit Auth-Kontext
	// THEN: 200 OK mit gueltigem JSON
	p := openmeteo.NewProvider(openmeteo.ProviderConfig{
		BaseURL:    "https://api.open-meteo.com",
		AQURL:      "https://air-quality-api.open-meteo.com",
		TimeoutSec: 30,
		Retries:    5,
		CacheDir:   t.TempDir(),
	})
	stub := neuerCoreStub(t)
	h := ForecastHandler(p, stub.url())

	req := angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0&hours=24", nutzerA)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}

	result := dekodiere(t, rec)
	if _, ok := result["meta"]; !ok {
		t.Error("expected 'meta' key in response")
	}
	if _, ok := result["data"]; !ok {
		t.Error("expected 'data' key in response")
	}
	if _, ok := result["timezone"]; !ok {
		t.Error("expected 'timezone' key in response")
	}
}

func TestForecastHandler_MissingLat_Returns400(t *testing.T) {
	// GIVEN: ForecastHandler, angemeldeter Nutzer
	// WHEN: GET /api/forecast?lon=3.0 (lat fehlt)
	// THEN: 400 mit error=invalid_params — unveraendert gegenueber dem Bestand
	stub := neuerCoreStub(t)
	h := ForecastHandler(nil, stub.url())

	req := angemeldet("GET", "/api/forecast?lon=3.0", nutzerA)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
	if result := dekodiere(t, rec); result["error"] != "invalid_params" {
		t.Errorf("expected error='invalid_params', got '%v'", result["error"])
	}
}

func TestForecastHandler_InvalidLat_Returns400(t *testing.T) {
	// GIVEN: ForecastHandler, angemeldeter Nutzer
	// WHEN: GET /api/forecast?lat=999&lon=3.0 (lat ausserhalb [-90,90])
	// THEN: 400 mit error=invalid_params — unveraendert gegenueber dem Bestand
	stub := neuerCoreStub(t)
	h := ForecastHandler(nil, stub.url())

	req := angemeldet("GET", "/api/forecast?lat=999&lon=3.0", nutzerA)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
	if result := dekodiere(t, rec); result["error"] != "invalid_params" {
		t.Errorf("expected error='invalid_params', got '%v'", result["error"])
	}
}

func TestForecastHandler_InvalidHours_Returns400(t *testing.T) {
	// GIVEN: ForecastHandler, angemeldeter Nutzer
	// WHEN: GET /api/forecast?lat=39.7&lon=3.0&hours=9999
	// THEN: 400 mit error=invalid_params — unveraendert gegenueber dem Bestand
	stub := neuerCoreStub(t)
	h := ForecastHandler(nil, stub.url())

	req := angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0&hours=9999", nutzerA)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
	if result := dekodiere(t, rec); result["error"] != "invalid_params" {
		t.Errorf("expected error='invalid_params', got '%v'", result["error"])
	}
}

// =============================================================================
// AC-2: der Core lehnt fuer A ab und erlaubt fuer B — der Handler uebersetzt
//       das in 429 bzw. 200
// =============================================================================

func TestForecastHandler_AbgelehnteReservierung429_ErlaubteReservierung200(t *testing.T) {
	// GIVEN: Core-Stub, der fuer Nutzer A ablehnt und fuer Nutzer B erlaubt
	// WHEN: beide rufen GET /api/forecast im selben Testlauf auf
	// THEN: A bekommt 429 (+ Retry-After, kein Abruf), B bekommt 200
	stub := neuerCoreStub(t, nutzerA)
	p := &zaehlenderProvider{}
	h := ForecastHandler(p, stub.url())

	recA := httptest.NewRecorder()
	h.ServeHTTP(recA, angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0", nutzerA))

	if recA.Code != http.StatusTooManyRequests {
		t.Errorf("AC-2: bei abgelehnter Reservierung erwartet 429, bekam %d: %s",
			recA.Code, recA.Body.String())
	}
	if p.aufrufe != 0 {
		t.Errorf("AC-2: bei 429 darf KEIN Wetterabruf stattfinden, es waren %d — "+
			"ein Deckel, der trotzdem abruft, verbrennt genau das Kontingent, "+
			"das er schuetzen soll", p.aufrufe)
	}
	koerperA := dekodiere(t, recA)
	if koerperA["error"] != "budget_exceeded" {
		t.Errorf("AC-2: erwartet error='budget_exceeded', bekam '%v'", koerperA["error"])
	}
	if _, ok := koerperA["detail"]; !ok {
		t.Error("AC-2: Fehlerobjekt im Stil {\"error\":…, \"detail\":…} erwartet, 'detail' fehlt")
	}
	retryAfter := recA.Header().Get("Retry-After")
	sekunden, err := strconv.Atoi(retryAfter)
	if err != nil || sekunden <= 0 || sekunden > sekundenJeTag {
		t.Errorf("AC-2: Retry-After muss die Sekunden bis UTC-Mitternacht nennen "+
			"(0 < s <= %d), bekam %q", sekundenJeTag, retryAfter)
	}

	recB := httptest.NewRecorder()
	h.ServeHTTP(recB, angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0", nutzerB))

	if recB.Code != http.StatusOK {
		t.Errorf("AC-2 (Kern): der unbeteiligte Nutzer B muss 200 mit Vorhersage "+
			"bekommen, bekam %d: %s", recB.Code, recB.Body.String())
	}
	if p.aufrufe != 1 {
		t.Errorf("AC-2: genau der erlaubte Aufruf darf den Provider erreichen, "+
			"gezaehlt: %d", p.aufrufe)
	}
	if _, ok := dekodiere(t, recB)["data"]; !ok {
		t.Error("AC-2: die erlaubte Antwort muss die unveraenderte Vorhersage tragen ('data' fehlt)")
	}
}

// =============================================================================
// AC-4: user_id und priority kommen am Core AN — und zwar die authentifizierte
//       Kennung, nicht eine vom Client mitgeschickte
// =============================================================================

func TestForecastHandler_ReserveTraegtEchteUserIDUndPollingPriority(t *testing.T) {
	// GIVEN: ein angemeldeter Nutzer A, der in der Query eine FREMDE user_id
	//        mitschickt (Spoofing-Versuch, Muster appendUserID)
	// WHEN: der Handler beim Core reserviert
	// THEN: am Core kommen genau user_id=<A> und priority=polling an
	//
	// allow() laesst unbekannte Prioritaeten IMMER durch (forecast_budget.py:133-134,
	// fail-open). Ein Test, der nur die Stub-Antwort befolgt, bliebe bei einem
	// Tippfehler in priority gruen — deshalb wird die empfangene Query gelesen.
	stub := neuerCoreStub(t)
	p := &zaehlenderProvider{}
	h := ForecastHandler(p, stub.url())

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0&user_id=fremder-nutzer", nutzerA))

	if stub.aufrufe() != 1 {
		t.Fatalf("AC-4: genau eine Reservierungsanfrage am Core erwartet, gezaehlt %d",
			stub.aufrufe())
	}
	if pfad := stub.ersterPfad(); pfad != "/api/_internal/forecast-budget/reserve" {
		t.Errorf("AC-4: erwartet Pfad /api/_internal/forecast-budget/reserve, bekam %q", pfad)
	}

	query := stub.letzte()
	if got := query.Get("user_id"); got != nutzerA {
		t.Errorf("AC-4: am Core muss die AUTHENTIFIZIERTE Kennung %q ankommen, "+
			"bekam %q — eine vom Client mitgeschickte user_id muss entfernt "+
			"werden (Muster internal/handler/proxy.go:151-163)", nutzerA, got)
	}
	if len(query["user_id"]) != 1 {
		t.Errorf("AC-4: user_id darf genau einmal auf der Leitung stehen, bekam %v",
			query["user_id"])
	}
	if got := query.Get("priority"); got != "polling" {
		t.Errorf("AC-4: erwartet priority='polling', bekam %q — jede andere oder "+
			"unbekannte Prioritaet wird von allow() fail-open nie gedrosselt",
			got)
	}
	// Spec: "Auf der Leitung reisen NUR user_id und priority." Die Zahl der
	// gebuchten Einheiten ist eine Konstante im Python-Endpunkt; als
	// Query-Parameter liessen Handler und Gate auseinanderdriften.
	for name := range query {
		if name != "user_id" && name != "priority" {
			t.Errorf("AC-4: unerwarteter Query-Parameter %q am Core — auf der "+
				"Leitung reisen nur user_id und priority", name)
		}
	}
	if rec.Code != http.StatusOK {
		t.Errorf("erlaubte Reservierung muss 200 liefern, bekam %d: %s", rec.Code, rec.Body.String())
	}
}

// =============================================================================
// AC-5: Core nicht erreichbar bzw. Status != 200 -> fail-open 200 + WARNING
// =============================================================================

// pruefeFailOpen faehrt einen Handler gegen eine defekte Core-Lage und sichert
// 200 mit Vorhersage plus WARNING-Log zu.
func pruefeFailOpen(t *testing.T, coreURL, lage string) {
	t.Helper()
	var logPuffer bytes.Buffer
	log.SetOutput(&logPuffer)
	defer log.SetOutput(os.Stderr)

	p := &zaehlenderProvider{}
	h := ForecastHandler(p, coreURL)

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0", nutzerA))

	if rec.Code != http.StatusOK {
		t.Errorf("AC-5 (%s): fail-open — ein kaputter Zaehler darf nie einen "+
			"Abruf blockieren, erwartet 200, bekam %d: %s", lage, rec.Code, rec.Body.String())
	}
	if p.aufrufe != 1 {
		t.Errorf("AC-5 (%s): der Abruf muss trotzdem stattfinden, gezaehlt %d",
			lage, p.aufrufe)
	}
	if _, ok := dekodiere(t, rec)["data"]; !ok {
		t.Errorf("AC-5 (%s): die Antwort muss die regulaere Vorhersage tragen ('data' fehlt)", lage)
	}

	ausgabe := logPuffer.String()
	klein := strings.ToLower(ausgabe)
	if !strings.Contains(ausgabe, "WARN") {
		t.Errorf("AC-5 (%s): der verschluckte Fehler muss als WARNING sichtbar "+
			"werden (Konvention 'WARN', vgl. internal/scheduler/scheduler.go:563) "+
			"— sonst ist der Fail-open-Weg im Betrieb unbeobachtbar. Log: %q",
			lage, ausgabe)
	}
	if !strings.Contains(klein, "budget") && !strings.Contains(klein, "reserve") {
		t.Errorf("AC-5 (%s): die Warnung muss die Reservierung benennen "+
			"('budget' oder 'reserve'), sonst faellt sie im Betriebslog nicht "+
			"zuzuordnen an. Log: %q", lage, ausgabe)
	}
}

func TestForecastHandler_CoreUnerreichbar_FailOpen200(t *testing.T) {
	// GIVEN: eine Core-URL, hinter der nichts mehr lauscht
	// WHEN: ein angemeldeter Nutzer GET /api/forecast aufruft
	// THEN: 200 mit Vorhersage + WARNING-Log
	toterServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	adresse := toterServer.URL
	toterServer.Close()

	pruefeFailOpen(t, adresse, "Core unerreichbar")
}

func TestForecastHandler_CoreAntwortetNicht200_FailOpen200(t *testing.T) {
	// GIVEN: ein Core, der mit 500 antwortet
	// WHEN: ein angemeldeter Nutzer GET /api/forecast aufruft
	// THEN: 200 mit Vorhersage + WARNING-Log
	kaputt := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer kaputt.Close()

	pruefeFailOpen(t, kaputt.URL, "Core antwortet 500")
}

// =============================================================================
// AC-6: ohne Auth-Kontext 401 — und der Core wird gar nicht erst gefragt
// =============================================================================

func TestForecastHandler_OhneAuthKontext_401UndKeineReservierung(t *testing.T) {
	// GIVEN: ein Request OHNE Auth-Kontext, aber mit gueltigen lat/lon
	// WHEN: der Handler ihn verarbeitet
	// THEN: 401, der Core-Stub bekommt keinen Aufruf, der Provider auch nicht
	stub := neuerCoreStub(t)
	p := &zaehlenderProvider{}
	h := ForecastHandler(p, stub.url())

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/api/forecast?lat=39.7&lon=3.0", nil))

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("AC-6: ohne Anmeldung erwartet 401, bekam %d: %s", rec.Code, rec.Body.String())
	}
	if stub.aufrufe() != 0 {
		t.Errorf("AC-6: die Reservierung darf NICHT angefragt werden, wenn keine "+
			"echte Kennung vorliegt — sonst buchte der Core auf eine leere oder "+
			"fremde user_id (ADR-0003, ADR-0075 Punkt 4). Aufrufe: %d", stub.aufrufe())
	}
	if p.aufrufe != 0 {
		t.Errorf("AC-6: ohne Anmeldung darf kein Wetterabruf stattfinden, es waren %d", p.aufrufe)
	}
}

// =============================================================================
// AC-7: Auth-Pruefung greift VOR der Parametervalidierung
// =============================================================================

func TestForecastHandler_OhneAuthKontextUndFehlendemLat_401Statt400(t *testing.T) {
	// GIVEN: ein Request ohne Auth-Kontext UND ohne lat
	// WHEN: der Handler ihn verarbeitet
	// THEN: 401, nicht 400 — die Reihenfolge im Handler ist Auth zuerst
	stub := neuerCoreStub(t)
	p := &zaehlenderProvider{}
	h := ForecastHandler(p, stub.url())

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/api/forecast?lon=3.0", nil))

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("AC-7: die Auth-Pruefung steht VOR der Parametervalidierung — "+
			"erwartet 401, bekam %d: %s", rec.Code, rec.Body.String())
	}
	if stub.aufrufe() != 0 {
		t.Errorf("AC-7: kein Core-Aufruf bei fehlender Anmeldung, gezaehlt %d", stub.aufrufe())
	}
}
