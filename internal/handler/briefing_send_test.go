package handler_test

// Issue #2280 Scheibe S2 (Go): kind-neutraler Handversand-Endpoint
// POST /api/briefings/{id}/send?kind=route|vergleich.
//
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-1, AC-2,
// AC-3 Go-Teil, AC-13 Go-Teil, AC-14).
//
// Bauart wie briefing_preview_test.go (gleiches externes Testpaket, nutzt
// dessen Helfer newVBUpstream/newVBEnv/vbInvalidIDs/vbAssertSingleUserID):
// ECHTER Produktions-Router router.New(...) samt AuthMiddleware, Python-Core
// ist ein echter httptest-Server, der jede empfangene Anfrage mitschreibt.
// Kein Mock einer Go-Funktion — geprueft wird die tatsaechlich abgesetzte
// Upstream-Anfrage und die Antwort am Client.
//
// Fehlerform des Versandwegs ist Form A {"detail","code"} (AC-2/AC-3/AC-9,
// api_contract.md 10.1) — strikt per JSON geprueft (bsAssertSendError).
//
// Python-Ziel (Python-Teil S1): POST /api/briefings/{id}/send?kind=<kind>
// &user_id=<auth>[&report_type=...]; Status + Body werden 1:1 durchgereicht.

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	authmw "github.com/henemm/gregor-api/internal/middleware"
)

const bsPath = "/api/briefings/"

// bsAssertSendError prueft die Fehlerform A des Versandwegs strikt: der Body
// ist GENAU {"detail":<nicht-leerer Text>,"code":<wantCode>} — kein
// {"error":…}, kein Code als "Text".
func bsAssertSendError(t *testing.T, w *httptest.ResponseRecorder, wantCode string) {
	t.Helper()
	var got map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("Fehler-Body ist kein JSON-Objekt aus Strings: %v (body=%q)", err, w.Body.String())
	}
	if got["code"] != wantCode {
		t.Errorf("code %q, erwartet %q (body=%q)", got["code"], wantCode, w.Body.String())
	}
	if d := got["detail"]; d == "" || d == wantCode {
		t.Errorf("detail %q muss ein anzeigbarer Text sein (body=%q)", d, w.Body.String())
	}
	if len(got) != 2 {
		t.Errorf("Fehler-Body hat Felder %v, erwartet genau detail+code", got)
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Errorf("Content-Type %q, erwartet application/json", ct)
	}
}

// ---------------------------------------------------------------------------
// AC-2: kind Pflicht -> 400 kind_required, Python nicht erreicht
// ---------------------------------------------------------------------------

func TestBriefingSend_KindPflicht_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	cases := []struct {
		name, query  string
		wantStatus   int
		wantUpstream int
		wantCode     string
	}{
		{"kind fehlt", "", 400, 0, "kind_required"},
		{"kind leer", "?kind=", 400, 0, "kind_required"},
		{"kind falsch trip", "?kind=trip", 400, 0, "kind_required"},
		{"kind falsch compare", "?kind=compare", 400, 0, "kind_required"},
		{"kind Grossschreibung", "?kind=ROUTE", 400, 0, "kind_required"},
		// Positiv-Kontrolle: Route + Zaehler greifen ueberhaupt.
		{"Kontrolle route", "?kind=route", 200, 1, ""},
		{"Kontrolle vergleich", "?kind=vergleich", 200, 1, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", bsPath+"t-2280/send"+c.query, "alice", "")
			if w.Code != c.wantStatus {
				t.Errorf("Status %d, erwartet %d (body=%q)", w.Code, c.wantStatus, w.Body.String())
			}
			if c.wantCode != "" {
				bsAssertSendError(t, w, c.wantCode)
			}
			if got := py.count(); got != c.wantUpstream {
				t.Errorf("Python-Core %d-mal erreicht, erwartet %d — ohne gueltiges kind darf nichts versendet werden",
					got, c.wantUpstream)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-3: ungueltig geformte ID -> 400, Python nicht erreicht
// ---------------------------------------------------------------------------

func TestBriefingSend_UngueltigeID_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, id := range vbInvalidIDs {
		vbAssertIDReachesValidation(t, env, id, "alice")
		for _, kind := range []string{"route", "vergleich"} {
			t.Run(kind+"/"+id, func(t *testing.T) {
				py.reset()
				w := env.do(t, "POST", bsPath+id+"/send?kind="+kind, "alice", "")
				if w.Code != http.StatusBadRequest {
					t.Errorf("Status %d, erwartet 400 bei ungueltiger ID %q (body=%q)", w.Code, id, w.Body.String())
				}
				bsAssertSendError(t, w, "validation_error")
				if got := py.count(); got != 0 {
					t.Errorf("Python-Core %d-mal erreicht — ungueltige ID darf nicht weitergereicht werden", got)
				}
			})
		}
	}
	// Positiv-Kontrolle: gueltige ID erreicht Python (sonst waere 400 kein Beleg).
	py.reset()
	if w := env.do(t, "POST", bsPath+"t-2280/send?kind=route", "alice", ""); w.Code != 200 || py.count() != 1 {
		t.Errorf("Kontrolle: gueltige ID liefert %d / Upstream %d, erwartet 200 / 1 (body=%q)",
			w.Code, py.count(), w.Body.String())
	}
}

// ---------------------------------------------------------------------------
// AC-3 / AC-14: Zwei Nutzer — user_id kommt aus der Anmeldung, Client-Wert
// wird verworfen. Nutzer B schmuggelt ?user_id=alice, Python sieht bob.
// ---------------------------------------------------------------------------

func TestBriefingSend_ZweiNutzer_UserIDAusAuthKontext(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice", "bob")

	for _, kind := range []string{"route", "vergleich"} {
		t.Run(kind, func(t *testing.T) {
			// Nutzer A (alice) — Bezugsmessung.
			py.reset()
			if w := env.do(t, "POST", bsPath+"t-alice/send?kind="+kind, "alice", ""); w.Code != 200 {
				t.Fatalf("alice: Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
			}
			ca, ok := py.last()
			if !ok {
				t.Fatal("alice: Python-Core nicht erreicht")
			}
			vbAssertSingleUserID(t, ca, "alice")

			// Nutzer B (bob) gibt sich per Query als alice aus.
			py.reset()
			w := env.do(t, "POST", bsPath+"t-alice/send?kind="+kind+"&user_id=alice", "bob", "")
			if w.Code != 200 {
				t.Fatalf("bob: Status %d, erwartet 200 (Weitergabe an Python, das ueber Eigentum entscheidet; body=%q)",
					w.Code, w.Body.String())
			}
			cb, ok := py.last()
			if !ok {
				t.Fatal("bob: Python-Core nicht erreicht")
			}
			vbAssertSingleUserID(t, cb, "bob")
		})
	}
}

// ---------------------------------------------------------------------------
// AC-1 / AC-14: gueltige Anfrage wird an Python /api/briefings/{id}/send
// weitergereicht (POST, kind, user_id, report_type bei route); Status, Body
// und Content-Type gehen 1:1 zurueck — Erfolg wie Fehler.
// ---------------------------------------------------------------------------

func TestBriefingSend_WeiterleitungUndDurchreichen(t *testing.T) {
	type resp struct {
		status int
		body   string
	}
	var next resp
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return next.status, "application/json", next.body
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	cases := []struct {
		name, kind, extra string
		upstream          resp
	}{
		{"route Erfolg", "route", "&report_type=morning",
			resp{200, `{"status":"ok","kind":"route","id":"t-2280","sent":true,"report_type":"morning"}`}},
		{"vergleich Erfolg", "vergleich", "",
			resp{200, `{"status":"ok","kind":"vergleich","id":"t-2280","sent":true,"fehlende_orte":[]}`}},
		{"route no_channels", "route", "",
			resp{422, `{"detail":"Kein Kanal wirksam.","code":"no_channels"}`}},
		{"vergleich channels_unreachable", "vergleich", "",
			resp{422, `{"detail":"Kein Kanal erreichbar.","code":"channels_unreachable"}`}},
		{"vergleich not_found", "vergleich", "",
			resp{404, `{"detail":"Nicht gefunden.","code":"not_found"}`}},
		{"route already_in_progress", "route", "",
			resp{409, `{"detail":"Laeuft bereits.","code":"already_in_progress"}`}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			py.reset()
			next = c.upstream
			w := env.do(t, "POST", bsPath+"t-2280/send?kind="+c.kind+c.extra, "alice", "")

			if w.Code != c.upstream.status {
				t.Errorf("Client-Status %d, erwartet durchgereicht %d (body=%q)", w.Code, c.upstream.status, w.Body.String())
			}
			if w.Body.String() != c.upstream.body {
				t.Errorf("Client-Body %q, erwartet 1:1 %q", w.Body.String(), c.upstream.body)
			}
			if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
				t.Errorf("Content-Type %q, erwartet application/json", ct)
			}

			call, ok := py.last()
			if !ok {
				t.Fatal("Python-Core nicht erreicht")
			}
			if py.count() != 1 {
				t.Errorf("Python-Core %d-mal erreicht, erwartet genau 1", py.count())
			}
			if call.Method != http.MethodPost {
				t.Errorf("Upstream-Methode %s, erwartet POST", call.Method)
			}
			if call.Path != "/api/briefings/t-2280/send" {
				t.Errorf("Upstream-Pfad %q, erwartet /api/briefings/t-2280/send", call.Path)
			}
			if got := call.Query.Get("kind"); got != c.kind {
				t.Errorf("Upstream-kind %q, erwartet %q", got, c.kind)
			}
			vbAssertSingleUserID(t, call, "alice")
			if c.extra != "" {
				if got := call.Query.Get("report_type"); got != "morning" {
					t.Errorf("Upstream-report_type %q, erwartet morning (bei route durchreichen)", got)
				}
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Fix-Loop 1 F-ADV2: report_type gilt nur fuer kind=route — bei
// kind=vergleich erreicht er den Python-Core NICHT (Kontroll-Bein route).
// ---------------------------------------------------------------------------

func TestBriefingSend_ReportTypeNurBeiRoute(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	cases := []struct {
		kind     string
		wantHas  bool
		wantSeen string
	}{
		{"vergleich", false, ""},
		{"route", true, "evening"},
	}
	for _, c := range cases {
		t.Run(c.kind, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", bsPath+"t-2280/send?kind="+c.kind+"&report_type=evening", "alice", "")
			if w.Code != 200 {
				t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
			}
			call, ok := py.last()
			if !ok {
				t.Fatal("Python-Core nicht erreicht")
			}
			if got := call.Query.Has("report_type"); got != c.wantHas {
				t.Errorf("kind=%s: report_type im Upstream vorhanden=%v, erwartet %v (query=%v)",
					c.kind, got, c.wantHas, call.Query)
			}
			if got := call.Query.Get("report_type"); got != c.wantSeen {
				t.Errorf("kind=%s: Upstream-report_type %q, erwartet %q", c.kind, got, c.wantSeen)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-14: Upstream-Versand ueberlebt den Client-Abbruch (context.WithoutCancel)
// — gemessen ueber den echten Router, am Upstream, wo die Zusicherung wirkt.
// ---------------------------------------------------------------------------

func TestBriefingSend_ClientAbbruchBrichtUpstreamNichtAb(t *testing.T) {
	entered := make(chan struct{}, 1)
	result := make(chan string, 1)
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case entered <- struct{}{}:
		default:
		}
		select {
		case <-time.After(400 * time.Millisecond):
			result <- "completed"
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		case <-r.Context().Done():
			result <- "canceled"
		}
	}))
	t.Cleanup(py.Close)
	env := newVBEnv(t, py.URL, "alice")

	for _, kind := range []string{"route", "vergleich"} {
		t.Run(kind, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			req := httptest.NewRequest(http.MethodPost, bsPath+"t-2280/send?kind="+kind, nil).WithContext(ctx)
			req.AddCookie(&http.Cookie{
				Name:  "gz_session",
				Value: authmw.SignSessionWithID("alice", vbSessionID("alice"), env.secret),
			})
			rec := httptest.NewRecorder()
			done := make(chan struct{})
			go func() {
				defer close(done)
				env.router.ServeHTTP(rec, req)
			}()

			select {
			case <-entered:
			case <-done:
				t.Fatalf("Handler kehrte zurueck, ohne Python zu erreichen (Status %d, body=%q)",
					rec.Code, rec.Body.String())
			case <-time.After(3 * time.Second):
				t.Fatal("Upstream wurde nicht betreten — Handler hat nicht weitergeleitet")
			}
			cancel() // Browser/nginx legt auf.

			var got string
			select {
			case got = <-result:
			case <-time.After(3 * time.Second):
				t.Fatal("Upstream hat weder abgeschlossen noch einen Abbruch beobachtet")
			}
			<-done
			if got != "completed" {
				t.Errorf("Client-Abbruch hat den Upstream-Versand abgebrochen (%q) — erwartet completed (context.WithoutCancel)", got)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-13: Alt-Routen sind Delegates — fuer dieselbe Python-Antwort liefern
// POST /api/trips/{id}/send und POST /api/compare/presets/{id}/send exakt
// denselben Status, Body und Content-Type wie der neue Endpoint.
// ---------------------------------------------------------------------------

func TestBriefingSend_AltRoutenDelegateGleichheit(t *testing.T) {
	type resp struct {
		status int
		body   string
	}
	var next resp
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return next.status, "application/json", next.body
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	answers := []resp{
		{200, `{"status":"ok","kind":"route","id":"x-2280","sent":true}`},
		{422, `{"detail":"Kein Kanal wirksam.","code":"no_channels"}`},
		{422, `{"detail":"Keine Wetterdaten.","code":"no_weather"}`},
		{409, `{"detail":"Laeuft bereits.","code":"already_in_progress"}`},
		{404, `{"detail":"Nicht gefunden.","code":"not_found"}`},
	}
	pairs := []struct {
		name, alt, neu string
	}{
		{"Trip", "/api/trips/x-2280/send?report_type=evening", bsPath + "x-2280/send?kind=route&report_type=evening"},
		{"Ortsvergleich", "/api/compare/presets/x-2280/send", bsPath + "x-2280/send?kind=vergleich"},
	}
	for _, p := range pairs {
		for _, a := range answers {
			t.Run(p.name+"/"+http.StatusText(a.status), func(t *testing.T) {
				next = a
				py.reset()
				wa := env.do(t, "POST", p.alt, "alice", "")
				if py.count() != 1 {
					t.Fatalf("Alt-Route erreichte Python %d-mal, erwartet 1 (Kalibrierung)", py.count())
				}
				py.reset()
				wn := env.do(t, "POST", p.neu, "alice", "")
				if py.count() != 1 {
					t.Errorf("Neuer Endpoint erreichte Python %d-mal, erwartet 1", py.count())
				}
				if wa.Code != wn.Code {
					t.Errorf("Status Alt %d != Neu %d", wa.Code, wn.Code)
				}
				if wa.Body.String() != wn.Body.String() {
					t.Errorf("Body Alt %q != Neu %q", wa.Body.String(), wn.Body.String())
				}
				if wa.Header().Get("Content-Type") != wn.Header().Get("Content-Type") {
					t.Errorf("Content-Type Alt %q != Neu %q",
						wa.Header().Get("Content-Type"), wn.Header().Get("Content-Type"))
				}
			})
		}
	}
}

// ---------------------------------------------------------------------------
// AC-9 / AC-13 / AC-14: Python-Core nicht erreichbar -> 502 in Form A, fuer
// den neuen Endpoint UND beide Alt-Delegates (alle ueber forwardSend).
// ---------------------------------------------------------------------------

func TestBriefingSend_UpstreamUnerreichbar_502FormA(t *testing.T) {
	tot := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	totURL := tot.URL
	tot.Close() // Port ist zu: jede Verbindung scheitert.
	env := newVBEnv(t, totURL, "alice")

	for _, path := range []string{
		bsPath + "t-2280/send?kind=route",
		bsPath + "t-2280/send?kind=vergleich",
		"/api/trips/t-2280/send",
		"/api/compare/presets/t-2280/send",
	} {
		t.Run(path, func(t *testing.T) {
			w := env.do(t, "POST", path, "alice", "")
			if w.Code != http.StatusBadGateway {
				t.Fatalf("Status %d, erwartet 502 (body=%q)", w.Code, w.Body.String())
			}
			bsAssertSendError(t, w, "upstream_unreachable")
		})
	}
}

// ---------------------------------------------------------------------------
// F002 (Adversary): Alt-Trip-Route reicht die Client-Query (report_type)
// unveraendert an Python weiter — gemessen an der Upstream-Anfrage.
// ---------------------------------------------------------------------------

func TestBriefingSend_AltTripRouteReichtReportTypeDurch(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	w := env.do(t, "POST", "/api/trips/t-2280/send?report_type=morning", "alice", "")
	if w.Code != 200 {
		t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
	}
	call, ok := py.last()
	if !ok {
		t.Fatal("Python-Core nicht erreicht")
	}
	if call.Path != "/api/scheduler/trips/t-2280/send" {
		t.Errorf("Upstream-Pfad %q, erwartet /api/scheduler/trips/t-2280/send", call.Path)
	}
	if got := call.Query["report_type"]; len(got) != 1 || got[0] != "morning" {
		t.Errorf("Upstream-report_type %v, erwartet genau [morning] (query=%v)", got, call.Query)
	}
	vbAssertSingleUserID(t, call, "alice")
}

// ---------------------------------------------------------------------------
// F003 (Adversary): Anfrage an Python laesst sich nicht bauen (Python-URL mit
// Steuerzeichen) -> 500 proxy_error in Form A, fuer alle vier Versand-Pfade.
// ---------------------------------------------------------------------------

func TestBriefingSend_AnfrageNichtBaubar_500ProxyError(t *testing.T) {
	env := newVBEnv(t, "http://127.0.0.1\x7f", "alice")

	for _, path := range []string{
		bsPath + "t-2280/send?kind=route",
		bsPath + "t-2280/send?kind=vergleich",
		"/api/trips/t-2280/send",
		"/api/compare/presets/t-2280/send",
	} {
		t.Run(path, func(t *testing.T) {
			w := env.do(t, "POST", path, "alice", "")
			if w.Code != http.StatusInternalServerError {
				t.Fatalf("Status %d, erwartet 500 (body=%q)", w.Code, w.Body.String())
			}
			bsAssertSendError(t, w, "proxy_error")
		})
	}
}

// ---------------------------------------------------------------------------
// F004 (Adversary): kind_required-Wortlaut Go == Python. Beide Seiten pruefen
// per Verhalten gegen die geteilte Fixture tests/fixtures/send_detail_parity/
// faelle.json (Python-Gegenstueck: test_ac2_kind_required_text_gleich_der_go_
// fassung in tests/tdd/test_briefings_send_endpoint.py). Kein Quelltext-Read.
// ---------------------------------------------------------------------------

func bsRepoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("os.Getwd: %v", err)
	}
	for i := 0; i < 8; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		dir = filepath.Dir(dir)
	}
	t.Fatal("bsRepoRoot: kein go.mod gefunden — Fixture nicht auffindbar")
	return ""
}

func TestBriefingSend_KindRequiredTextGleichPythonFassung(t *testing.T) {
	pfad := filepath.Join(bsRepoRoot(t), "tests", "fixtures", "send_detail_parity", "faelle.json")
	raw, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("Geteilte Fixture fehlt: %s: %v", pfad, err)
	}
	var soll map[string]string
	if err := json.Unmarshal(raw, &soll); err != nil {
		t.Fatalf("%s ist kein JSON-Objekt aus Strings: %v", pfad, err)
	}
	if soll["kind_required"] == "" {
		t.Fatalf("%s: kind_required leer — Paritaetsnachweis waere wirkungslos", pfad)
	}

	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")
	w := env.do(t, "POST", bsPath+"t-2280/send", "alice", "")

	var got map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("Body kein JSON: %v (%q)", err, w.Body.String())
	}
	if w.Code != http.StatusBadRequest || got["detail"] != soll["kind_required"] {
		t.Errorf("Status %d detail %q, erwartet 400 mit %q (Python-Wortlaut)",
			w.Code, got["detail"], soll["kind_required"])
	}
	if py.count() != 0 {
		t.Errorf("Python-Core %d-mal erreicht, erwartet 0 (Go meldet kind_required selbst)", py.count())
	}
}
