package handler

// Wetter-Datenweg des MCP-Konnektors (Issue #3281, Scheibe 1, AC-11).
// SPEC: docs/specs/modules/mcp_wetter_konnektor.md
//
// Kein Mock: der Python-Core wird durch einen echten httptest-Server mit
// beiden Endpunkten (Kontingent-Reservierung, MCP-Wetter) vertreten; geprueft
// wird, welche Anfragen dort tatsaechlich ankommen.

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"
	"time"
)

const mcpWetterPfad = "/api/_internal/mcp/wetter"

type mcpCoreFixture struct {
	srv           *httptest.Server
	mu            sync.Mutex
	reserve       []url.Values
	wetter        []url.Values
	reserveKaputt bool
	wetterStatus  int
	wetterBody    string
}

func neuerMCPCore(t *testing.T, abgelehnt ...string) *mcpCoreFixture {
	t.Helper()
	verweigert := map[string]bool{}
	for _, u := range abgelehnt {
		verweigert[u] = true
	}
	f := &mcpCoreFixture{wetterStatus: http.StatusOK,
		wetterBody: `{"zeitzone":"Europe/Berlin","begrenzt":false,"stunden":[{"zeit":"2026-11-22T14:00:00+01:00"}]}`}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		defer f.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case forecastReservePfad:
			f.reserve = append(f.reserve, r.URL.Query())
			if f.reserveKaputt {
				w.WriteHeader(http.StatusInternalServerError)
				return
			}
			if verweigert[r.URL.Query().Get("user_id")] {
				json.NewEncoder(w).Encode(map[string]interface{}{"allowed": false, "retry_after_s": 3600})
				return
			}
			json.NewEncoder(w).Encode(map[string]interface{}{"allowed": true})
		case mcpWetterPfad:
			f.wetter = append(f.wetter, r.URL.Query())
			w.WriteHeader(f.wetterStatus)
			w.Write([]byte(f.wetterBody))
		default:
			t.Errorf("unerwarteter Core-Pfad %s", r.URL.Path)
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func (f *mcpCoreFixture) zaehle() (reserve, wetter int) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.reserve), len(f.wetter)
}

var frankfurtAnfrage = MCPWetterAnfrage{
	Lat: 50.1106444, Lon: 8.6820917, Von: "2026-11-22T14:00", Bis: "2026-11-22T16:00",
}

func TestMCPWetter_ErlaubterAbruf_BuchtKontingentUndHoltCoreWerte(t *testing.T) {
	core := neuerMCPCore(t)

	roh, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", frankfurtAnfrage)
	if err != nil {
		t.Fatalf("Abruf fehlgeschlagen: %v", err)
	}
	var antwort map[string]interface{}
	if err := json.Unmarshal(roh, &antwort); err != nil || antwort["zeitzone"] != "Europe/Berlin" {
		t.Fatalf("Core-Antwort nicht durchgereicht: %s (%v)", roh, err)
	}
	core.mu.Lock()
	defer core.mu.Unlock()
	if len(core.reserve) != 1 || core.reserve[0].Get("user_id") != "nutzer-a" ||
		core.reserve[0].Get("priority") != "user_interactive" {
		t.Errorf("Kontingent nicht auf echte Kennung/user_interactive gebucht: %v", core.reserve)
	}
	if len(core.wetter) != 1 {
		t.Fatalf("genau ein Wetterabruf erwartet, bekam %d", len(core.wetter))
	}
	q := core.wetter[0]
	if q.Get("lat") != "50.1106444" || q.Get("lon") != "8.6820917" ||
		q.Get("von") != frankfurtAnfrage.Von || q.Get("bis") != frankfurtAnfrage.Bis {
		t.Errorf("Wetterabruf-Parameter falsch: %v", q)
	}
	if q.Has("user_id") {
		t.Errorf("der Wetterabruf liest keine Nutzerdaten und traegt keine user_id: %v", q)
	}
}

func TestMCPWetter_KontingentErschoepft_FehlerMitWartezeitOhneWetterabruf(t *testing.T) {
	core := neuerMCPCore(t, "nutzer-voll")

	_, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-voll", frankfurtAnfrage)
	var warten *MCPWartenFehler
	if !errors.As(err, &warten) {
		t.Fatalf("AC-11: MCPWartenFehler erwartet, bekam %v", err)
	}
	if warten.Grund != MCPGrundKontingent || warten.WartenS != 3600 {
		t.Errorf("Grund/Wartezeit falsch: %+v", warten)
	}
	if _, n := core.zaehle(); n != 0 {
		t.Errorf("AC-11: bei erschoepftem Kontingent kein Wetterabruf, bekam %d", n)
	}
}

func TestMCPWetter_MengenbremseVorhersage_GreiftVorKontingentUndAbruf(t *testing.T) {
	core := neuerMCPCore(t)
	fest := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	defer SetBremsenUhr(func() time.Time { return fest })()
	bremsen := NeueNutzerBremsen(false, false)

	for i := 0; i < BremseAbrufJeMinute; i++ {
		if _, err := MCPWetterAbrufen(context.Background(), bremsen, core.srv.URL, "nutzer-b", frankfurtAnfrage); err != nil {
			t.Fatalf("Abruf %d innerhalb der Bremse abgelehnt: %v", i+1, err)
		}
	}
	_, err := MCPWetterAbrufen(context.Background(), bremsen, core.srv.URL, "nutzer-b", frankfurtAnfrage)
	var warten *MCPWartenFehler
	if !errors.As(err, &warten) || warten.Grund != MCPGrundBremse || warten.WartenS < 1 {
		t.Fatalf("Bremse erwartet (Grund %q, Wartezeit >= 1 s), bekam %v", MCPGrundBremse, err)
	}
	if r, w := core.zaehle(); r != BremseAbrufJeMinute || w != BremseAbrufJeMinute {
		t.Errorf("gebremster Abruf darf weder buchen noch abrufen: %d/%d", r, w)
	}
	// Ein anderer Nutzer ist davon unberuehrt.
	if _, err := MCPWetterAbrufen(context.Background(), bremsen, core.srv.URL, "nutzer-c", frankfurtAnfrage); err != nil {
		t.Errorf("Bremse von nutzer-b darf nutzer-c nicht treffen: %v", err)
	}
}

func TestMCPWetter_KontingentZaehlerGestoert_FailOpen(t *testing.T) {
	core := neuerMCPCore(t)
	core.mu.Lock()
	core.reserveKaputt = true
	core.mu.Unlock()

	if _, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", frankfurtAnfrage); err != nil {
		t.Fatalf("gestoerter Zaehler darf nicht blockieren (wie /api/forecast): %v", err)
	}
	if _, n := core.zaehle(); n != 1 {
		t.Errorf("Wetterabruf erwartet, bekam %d", n)
	}
}

func TestMCPWetter_CoreFehler_IstWetterdienstFehler(t *testing.T) {
	core := neuerMCPCore(t)
	core.mu.Lock()
	core.wetterStatus = http.StatusBadGateway
	core.mu.Unlock()

	roh, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", frankfurtAnfrage)
	if !errors.Is(err, ErrMCPWetterdienst) || roh != nil {
		t.Errorf("ErrMCPWetterdienst ohne Daten erwartet, bekam %v / %s", err, roh)
	}
}

func TestMCPWetter_OhneNutzerkennung_KeinAbruf(t *testing.T) {
	core := neuerMCPCore(t)

	if _, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "", frankfurtAnfrage); err == nil {
		t.Fatal("ohne echte Kennung darf nichts gebucht oder abgerufen werden")
	}
	if r, w := core.zaehle(); r != 0 || w != 0 {
		t.Errorf("keine Core-Anfrage erwartet, bekam %d/%d", r, w)
	}
}

func TestMCPOrtssucheBremse_DreissigJeMinuteDannWartezeit(t *testing.T) {
	fest := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	defer SetBremsenUhr(func() time.Time { return fest })()
	bremsen := NeueNutzerBremsen(false, false)

	for i := 0; i < BremseAufloesenJeMinute; i++ {
		if ok, _ := bremsen.ZulassenOrtssuche(context.Background(), "nutzer-a"); !ok {
			t.Fatalf("Ortssuche %d innerhalb der Bremse abgelehnt", i+1)
		}
	}
	ok, warten := bremsen.ZulassenOrtssuche(context.Background(), "nutzer-a")
	if ok || warten != time.Minute {
		t.Errorf("31. Ortssuche: Ablehnung mit 60 s Wartezeit erwartet, bekam %v/%v", ok, warten)
	}
	if ok, _ := bremsen.ZulassenOrtssuche(context.Background(), "nutzer-b"); !ok {
		t.Error("Bremse gilt je Nutzer")
	}
	// Fixture-Modus (aus=true) bremst nicht.
	if ok, _ := NeueNutzerBremsen(true, false).ZulassenOrtssuche(context.Background(), "nutzer-a"); !ok {
		t.Error("ausgeschaltete Bremsen duerfen nicht ablehnen")
	}
}

func (f *mcpCoreFixture) setze(status int, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.wetterStatus, f.wetterBody = status, body
}

// F002: Eingabefehler werden vor jeder Buchung erkannt — weder Bremse noch
// Kontingent noch Core-Abruf.
func TestMCPWetter_UngueltigerZeitraum_OhneBuchungUndAbruf(t *testing.T) {
	fest := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	defer SetBremsenUhr(func() time.Time { return fest })()
	faelle := []struct {
		name, von, bis, code string
	}{
		{"kein ISO", "morgen frueh", "", MCPCodeZeitpunktUngueltig},
		{"bis kein ISO", "2026-11-22T14:00", "uebermorgen", MCPCodeZeitpunktUngueltig},
		{"bis vor von", "2026-11-22T14:00:00+01:00", "2026-11-22T13:00:00+01:00", MCPCodeBisVorVon},
		{"von gleich bis", "2026-11-22T14:30", "2026-11-22T14:30", MCPCodeBisVorVon},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			core := neuerMCPCore(t)
			bremsen := NeueNutzerBremsen(false, false)
			a := MCPWetterAnfrage{Lat: 50.1106444, Lon: 8.6820917, Von: f.von, Bis: f.bis}
			_, err := MCPWetterAbrufen(context.Background(), bremsen, core.srv.URL, "nutzer-a", a)
			var eingabe *MCPEingabeFehler
			if !errors.Is(err, ErrMCPZeitraum) || !errors.As(err, &eingabe) || eingabe.Code != f.code {
				t.Fatalf("ErrMCPZeitraum mit Code %q erwartet, bekam %v", f.code, err)
			}
			if r, w := core.zaehle(); r != 0 || w != 0 {
				t.Errorf("Eingabefehler darf nicht buchen oder abrufen: %d/%d", r, w)
			}
			// Die Bremse hat keinen Treffer verbucht: volles Kontingent frei.
			for i := 0; i < BremseAbrufJeMinute; i++ {
				if ok, _ := bremsen.ZulassenVorhersage(context.Background(), "nutzer-a"); !ok {
					t.Fatalf("Eingabefehler hat die Bremse belastet (Treffer %d abgelehnt)", i+1)
				}
			}
		})
	}
}

// Ohne Offset gilt die Ortszeit (Berlin): 13:30Z = 14:30 Ortszeit liegt NACH
// 14:00 Ortszeit — als UTC gelesen laege es davor.
func TestMCPWetter_ZeitOhneOffsetGiltAlsOrtszeit(t *testing.T) {
	core := neuerMCPCore(t)
	a := MCPWetterAnfrage{Lat: 50.1106444, Lon: 8.6820917,
		Von: "2026-11-22T14:00", Bis: "2026-11-22T13:30:00Z"}
	if _, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", a); err != nil {
		t.Fatalf("14:00 Berlin bis 13:30Z (= 14:30 Berlin) ist gueltig: %v", err)
	}
}

func TestMCPWetter_UngueltigeKoordinaten_OhneBuchung(t *testing.T) {
	for _, a := range []MCPWetterAnfrage{
		{Lat: math.NaN(), Lon: 8}, {Lat: 91, Lon: 8}, {Lat: 50, Lon: -181},
	} {
		core := neuerMCPCore(t)
		_, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", a)
		if !errors.Is(err, ErrMCPKoordinaten) {
			t.Errorf("%v/%v: ErrMCPKoordinaten erwartet, bekam %v", a.Lat, a.Lon, err)
		}
		if r, w := core.zaehle(); r != 0 || w != 0 {
			t.Errorf("ungueltige Koordinaten duerfen nicht buchen: %d/%d", r, w)
		}
	}
}

// F002: ein 4xx des Core ist ein Eingabefehler mit Code und Text des Core,
// kein Stoerfall des Wetterdienstes.
func TestMCPWetter_Core422_IstEingabefehlerMitCodeUndText(t *testing.T) {
	core := neuerMCPCore(t)
	core.setze(http.StatusUnprocessableEntity,
		`{"detail":"Der Zeitraum liegt ausserhalb der Vorhersage.","code":"mcp_zeitraum_ausserhalb"}`)

	_, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", frankfurtAnfrage)
	var eingabe *MCPEingabeFehler
	if !errors.Is(err, ErrMCPZeitraum) || !errors.As(err, &eingabe) {
		t.Fatalf("ErrMCPZeitraum erwartet, bekam %v", err)
	}
	if eingabe.Code != "mcp_zeitraum_ausserhalb" || eingabe.Detail != "Der Zeitraum liegt ausserhalb der Vorhersage." {
		t.Errorf("Code/Text des Core nicht durchgereicht: %+v", eingabe)
	}
	if errors.Is(err, ErrMCPWetterdienst) {
		t.Error("ein Eingabefehler ist kein Wetterdienst-Fehler")
	}
}

func TestMCPWetter_CoreAntwortOhneJSON_IstWetterdienstFehler(t *testing.T) {
	core := neuerMCPCore(t)
	core.setze(http.StatusOK, "<html>kein json</html>")

	roh, err := MCPWetterAbrufen(context.Background(), nil, core.srv.URL, "nutzer-a", frankfurtAnfrage)
	if !errors.Is(err, ErrMCPWetterdienst) || roh != nil {
		t.Errorf("ErrMCPWetterdienst ohne Daten erwartet, bekam %v / %s", err, roh)
	}
}

// Konten aus der Quoten-Policy (Admin, Ausnahme-Liste) sind auch ohne Route
// ungebremst — Kontext aus der echten QuotaPolicyMiddleware.
func TestMCPOrtssucheBremse_AusnahmeKontoUngebremst(t *testing.T) {
	fest := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	defer SetBremsenUhr(func() time.Time { return fest })()
	var ctx context.Context
	mw := QuotaPolicyMiddleware(nil, map[string]struct{}{"nutzer-frei": {}})
	mw(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { ctx = r.Context() })).
		ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, "/", nil))
	bremsen := NeueNutzerBremsen(false, false)

	for i := 0; i <= BremseAufloesenJeMinute; i++ {
		if ok, _ := bremsen.ZulassenOrtssuche(ctx, "nutzer-frei"); !ok {
			t.Fatalf("Ausnahme-Konto bei Treffer %d gebremst", i+1)
		}
	}
	for i := 0; i < BremseAufloesenJeMinute; i++ {
		bremsen.ZulassenOrtssuche(ctx, "nutzer-normal")
	}
	if ok, _ := bremsen.ZulassenOrtssuche(ctx, "nutzer-normal"); ok {
		t.Error("ein Konto ausserhalb der Policy muss gebremst werden")
	}
}
