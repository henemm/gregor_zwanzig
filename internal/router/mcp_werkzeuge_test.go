package router

// Werkzeuge des MCP-Konnektors „Gregor Wetter“ durch den echten Router
// (Issue #3281, Scheibe 2; AC-1, AC-2, AC-5, AC-11 bis AC-15).
// SPEC: docs/specs/modules/mcp_wetter_konnektor.md

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/model"
)

// Eingabefehler aus der Pruefung in Go (vor Bremse und Kontingent) und aus
// einer 4xx-Abweisung des Core: je Code ein Werkzeugfehler mit dem Katalogtext
// in der Kontosprache, nie der deutsche Detail-Text des Core.
func TestMCPWetter_EingabefehlerJeCodeInKontosprache(t *testing.T) {
	const coreText = "Deutscher Core-Text, der nie bei Claude ankommt"
	core := func(code string) string {
		return `{"code":"` + code + `","detail":"` + coreText + `"}`
	}
	ort := map[string]any{"lat": 50.1, "lon": 8.6}
	faelle := []struct {
		name, abweisung, schluessel string
		args                        map[string]any
	}{
		{"zeitpunkt (Go)", "", "mcp.fehler.zeitpunkt_ungueltig", map[string]any{"lat": 50.1, "lon": 8.6, "von": "morgen frueh"}},
		{"bis vor von (Go)", "", "mcp.fehler.bis_vor_von", map[string]any{"lat": 50.1, "lon": 8.6, "von": "2026-11-23T10:00", "bis": "2026-11-23T08:00"}},
		{"koordinaten (Go)", "", "mcp.fehler.koordinaten_ungueltig", map[string]any{"lat": 91.0, "lon": 8.6}},
		{"zeitraum ausserhalb (Core)", core("mcp_zeitraum_ausserhalb"), "mcp.fehler.zeitraum_ausserhalb", ort},
		{"zeitpunkt (Core)", core("mcp_zeitpunkt_ungueltig"), "mcp.fehler.zeitpunkt_ungueltig", ort},
		{"bis vor von (Core)", core("mcp_bis_vor_von"), "mcp.fehler.bis_vor_von", ort},
		{"koordinaten (Core)", core("mcp_koordinaten_ungueltig"), "mcp.fehler.koordinaten_ungueltig", ort},
		{"invalid_params (Core)", core("invalid_params"), "mcp.fehler.eingabe_ungueltig", ort},
		{"invalid_params (FastAPI)", `{"detail":[{"loc":["query","lat"],"msg":"` + coreText + `"}]}`, "mcp.fehler.eingabe_ungueltig", ort},
		{"unbekannter Code (Core)", core("etwas_neues"), "mcp.fehler.eingabe_ungueltig", ort},
	}
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	for _, f := range faelle {
		w.core.mu.Lock()
		w.core.abweisung = f.abweisung
		w.core.mu.Unlock()
		for lang, tok := range map[i18n.Lang]map[string]any{i18n.De: de, i18n.En: en} {
			want := i18n.T(lang, f.schluessel, nil)
			text, fehler := w.werkzeug(tok["access_token"].(string), "wetter", f.args)
			if !fehler || text != want || text == f.schluessel {
				t.Errorf("%s (%s): isError=%v, Text %q, erwartet %q", f.name, lang, fehler, text, want)
			}
			if strings.Contains(text, coreText) {
				t.Errorf("%s (%s): Detail-Text des Core an Claude: %q", f.name, lang, text)
			}
		}
		if i18n.T(i18n.De, f.schluessel, nil) == i18n.T(i18n.En, f.schluessel, nil) {
			t.Errorf("%s: %s nicht uebersetzt", f.name, f.schluessel)
		}
	}
}

type wetterErgebnis struct {
	Ort *struct {
		Name     string  `json:"name"`
		Land     string  `json:"land"`
		Lat      float64 `json:"lat"`
		Lon      float64 `json:"lon"`
		Zeitzone string  `json:"zeitzone"`
	} `json:"ort"`
	Zeitzone   string            `json:"zeitzone"`
	Begrenzt   bool              `json:"begrenzt"`
	Bis        string            `json:"bis"`
	Hinweis    string            `json:"hinweis"`
	Einheiten  map[string]string `json:"einheiten"`
	Stunden    []map[string]any  `json:"stunden"`
	Mehrdeutig bool              `json:"mehrdeutig"`
	Kandidaten []struct {
		Name string  `json:"name"`
		Land string  `json:"land"`
		Lat  float64 `json:"lat"`
		Lon  float64 `json:"lon"`
	} `json:"kandidaten"`
}

func leseErgebnis(t *testing.T, text string) wetterErgebnis {
	t.Helper()
	var e wetterErgebnis
	if err := json.Unmarshal([]byte(text), &e); err != nil {
		t.Fatalf("Werkzeug-Ergebnis ist kein JSON: %v\n%s", err, text)
	}
	return e
}

func freigegebeneWelt(t *testing.T) (*mcpWelt, string) {
	t.Helper()
	w := neueMCPWelt(t, "anna")
	tok, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	return w, tok["access_token"].(string)
}

// AC-1: Frankfurt am Main, naechste 2 Stunden, Ortszeit mit Einheiten.
func TestMCPWetter_FrankfurtNaechsteZweiStunden(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "wetter", map[string]any{
		"ort": "Frankfurt am Main", "von": "2026-11-22T13:00", "bis": "2026-11-22T15:00"})
	if fehler {
		t.Fatalf("Werkzeugfehler: %s", text)
	}
	e := leseErgebnis(t, text)
	if e.Ort == nil || e.Ort.Name != "Frankfurt am Main" || e.Ort.Zeitzone != "Europe/Berlin" {
		t.Fatalf("Ortsname/Zeitzone fehlen: %s", text)
	}
	if len(e.Stunden) != 2 {
		t.Fatalf("zwei Stundeneintraege erwartet: %d", len(e.Stunden))
	}
	for _, s := range e.Stunden {
		zeit, _ := s["zeit"].(string)
		if !strings.HasSuffix(zeit, "+01:00") {
			t.Errorf("Zeit nicht in Ortszeit mit Offset: %q", zeit)
		}
		if _, ok := s["precip_1h_mm"]; !ok {
			t.Errorf("Niederschlag fehlt: %v", s)
		}
		if _, ok := s["pop_pct"]; !ok {
			t.Errorf("Niederschlagswahrscheinlichkeit fehlt: %v", s)
		}
	}
	if e.Einheiten["precip_1h_mm"] != "mm" || e.Einheiten["pop_pct"] != "%" {
		t.Errorf("Einheiten fehlen: %v", e.Einheiten)
	}
	w.core.mu.Lock()
	defer w.core.mu.Unlock()
	if len(w.core.wetter) != 1 || w.core.wetter[0].Get("lat") != "50.1106444" ||
		w.core.wetter[0].Get("von") != "2026-11-22T13:00" || w.core.wetter[0].Get("bis") != "2026-11-22T15:00" {
		t.Errorf("Core-Abruf falsch: %v", w.core.wetter)
	}
	if len(w.core.reserve) != 1 || w.core.reserve[0] != "anna" {
		t.Errorf("Kontingent nicht auf den Token-Nutzer gebucht: %v", w.core.reserve)
	}
}

// AC-2: Muenster 72 Stunden mit Sonnenminuten je Stunde.
func TestMCPWetter_MuensterSonnenminutenUeberDreiTage(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "wetter", map[string]any{"ort": "Münster", "von": "2026-11-22T00:00", "bis": "2026-11-25T00:00"})
	if fehler {
		t.Fatalf("Werkzeugfehler: %s", text)
	}
	e := leseErgebnis(t, text)
	if len(e.Stunden) != 72 || e.Einheiten["sonnenminuten"] != "min" {
		t.Fatalf("72 Stunden mit Einheit min erwartet: %d %v", len(e.Stunden), e.Einheiten)
	}
	tage := map[string]float64{}
	mitWert := 0
	for _, s := range e.Stunden {
		m, ok := s["sonnenminuten"].(float64)
		if !ok {
			continue
		}
		mitWert++
		if m < 0 || m > 60 {
			t.Errorf("Sonnenminuten ausserhalb 0..60: %v", s)
		}
		tage[s["zeit"].(string)[:10]] += m
	}
	if mitWert < 70 || len(tage) < 3 {
		t.Fatalf("Sonnenminuten je Stunde fehlen: %d Stunden, Tage %v", mitWert, tage)
	}
	summe := 0.0
	for _, v := range tage {
		summe += v
	}
	if summe <= 0 {
		t.Errorf("keine Sonne ableitbar: %v", tage)
	}
}

// AC-13: mehrdeutiger Ort -> Kandidaten statt Wetter; mit Koordinaten Wetter.
func TestMCPWetter_MehrdeutigerOrtNenntKandidaten(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, _ := w.werkzeug(access, "wetter", map[string]any{"ort": "Frankfurt"})
	e := leseErgebnis(t, text)
	if !e.Mehrdeutig || len(e.Kandidaten) < 2 || len(e.Stunden) != 0 || e.Hinweis == "" {
		t.Fatalf("Kandidatenliste ohne Stundenwerte erwartet: %s", text)
	}
	if _, n := w.core.zaehle(); n != 0 {
		t.Errorf("bei Mehrdeutigkeit wurde Wetter abgerufen: %d", n)
	}
	k := e.Kandidaten[1]
	if k.Name != "Frankfurt (Oder)" || k.Land != "Deutschland" || !nahe(k.Lat, 52.3412273) {
		t.Errorf("Kandidat ohne Name/Land/Koordinaten: %+v", k)
	}
	text, fehler := w.werkzeug(access, "wetter", map[string]any{"lat": k.Lat, "lon": k.Lon, "ort": k.Name})
	if fehler || len(leseErgebnis(t, text).Stunden) == 0 {
		t.Fatalf("mit Koordinaten Wetter erwartet: %s", text)
	}
	w.core.mu.Lock()
	defer w.core.mu.Unlock()
	if w.core.wetter[0].Get("lat") != "52.3412273" || w.core.wetter[0].Get("lon") != "14.549452" {
		t.Errorf("Koordinaten nicht weitergegeben: %v", w.core.wetter[0])
	}
}

// AC-12: unbekannter Ort -> Werkzeugfehler mit Hinweis, keine Werte.
func TestMCPWetter_UnbekannterOrtIstWerkzeugfehler(t *testing.T) {
	w, access := freigegebeneWelt(t)
	for _, werkzeug := range []string{"wetter", "ort_suchen"} {
		feld := map[string]string{"wetter": "ort", "ort_suchen": "text"}[werkzeug]
		text, fehler := w.werkzeug(access, werkzeug, map[string]any{feld: "Xyzzyplatz"})
		if !fehler || !strings.Contains(text, "Xyzzyplatz") || !strings.Contains(text, "genauer") || strings.Contains(text, "stunden") {
			t.Errorf("%s: Werkzeugfehler mit Hinweis erwartet: %v %s", werkzeug, fehler, text)
		}
	}
	if _, n := w.core.zaehle(); n != 0 {
		t.Errorf("bei unbekanntem Ort wurde Wetter abgerufen: %d", n)
	}
}

func TestMCPOrtSuchen_LiefertKandidaten(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "ort_suchen", map[string]any{"text": "Frankfurt"})
	e := leseErgebnis(t, text)
	if fehler || len(e.Kandidaten) != 2 || e.Kandidaten[0].Name != "Frankfurt am Main" {
		t.Fatalf("Kandidaten erwartet: %v %s", fehler, text)
	}
	if !strings.Contains(text, `"zeitzone":"Europe/Berlin"`) {
		t.Errorf("Zeitzone fehlt: %s", text)
	}
}

// AC-14: 10 Tage werden auf 7 begrenzt, mit Hinweis und tatsaechlichem Ende.
func TestMCPWetter_ZehnTageWerdenBegrenzt(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "wetter", map[string]any{"lat": 50.1106444, "lon": 8.6820917, "von": "2026-11-22T00:00", "bis": "2099-12-01T00:00"})
	if fehler {
		t.Fatalf("Werkzeugfehler: %s", text)
	}
	e := leseErgebnis(t, text)
	if !e.Begrenzt || len(e.Stunden) > 168 || e.Bis == "" || !strings.Contains(e.Hinweis, "7 Tage") || !strings.Contains(e.Hinweis, e.Bis) {
		t.Fatalf("Begrenzung mit Hinweis und Ende erwartet: begrenzt=%v stunden=%d bis=%q hinweis=%q", e.Begrenzt, len(e.Stunden), e.Bis, e.Hinweis)
	}
}

// AC-11: erschoepftes Kontingent -> Werkzeugfehler mit Wartezeit, kein Abruf.
func TestMCPWetter_KontingentErschoepft(t *testing.T) {
	w, access := freigegebeneWelt(t)
	w.core.mu.Lock()
	w.core.voll["anna"] = true
	w.core.mu.Unlock()
	text, fehler := w.werkzeug(access, "wetter", map[string]any{"lat": 50.11, "lon": 8.68})
	if !fehler || !strings.Contains(text, "Tageskontingent") || !strings.Contains(text, "90 Minuten") {
		t.Fatalf("AC-11: Werkzeugfehler mit Wartezeit erwartet: %v %s", fehler, text)
	}
	if reserve, wetter := w.core.zaehle(); reserve != 1 || wetter != 0 {
		t.Errorf("AC-11: Abruf trotz erschoepftem Kontingent: reserve=%d wetter=%d", reserve, wetter)
	}
}

func TestMCPWetter_WetterdienstGestoert(t *testing.T) {
	w, access := freigegebeneWelt(t)
	w.core.mu.Lock()
	w.core.gestoert = true
	w.core.mu.Unlock()
	text, fehler := w.werkzeug(access, "wetter", map[string]any{"lat": 50.11, "lon": 8.68})
	if !fehler || !strings.Contains(text, "Wetterdienst") || strings.Contains(text, "provider_error") {
		t.Fatalf("Werkzeugfehler mit Katalogtext erwartet: %v %s", fehler, text)
	}
}

func TestMCPWetter_UngueltigeEingaben(t *testing.T) {
	w, access := freigegebeneWelt(t)
	for name, args := range map[string]map[string]any{
		"nichts":       {},
		"lat zu gross": {"lat": 91.0, "lon": 8.0},
		"nur lat":      {"lat": 50.0},
		"zeit":         {"lat": 50.0, "lon": 8.0, "von": "morgen frueh"},
	} {
		text, fehler := w.werkzeug(access, "wetter", args)
		if !fehler || text == "" {
			t.Errorf("%s: Werkzeugfehler erwartet: %v %s", name, fehler, text)
		}
	}
	if _, n := w.core.zaehle(); n != 0 {
		t.Errorf("ungueltige Eingaben riefen den Wetterdienst: %d", n)
	}
}

// AC-15: Sprache des Kontos fuer Beschreibungen und Fehler, Namen unuebersetzt.
func TestMCP_SpracheDesKontos(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	liste := func(access string) map[string]map[string]any {
		_, a := w.mcp(access, "tools/list", nil)
		res, _ := a["result"].(map[string]any)
		tools, _ := res["tools"].([]any)
		m := map[string]map[string]any{}
		for _, x := range tools {
			tool := x.(map[string]any)
			m[tool["name"].(string)] = tool
		}
		return m
	}
	lDe, lEn := liste(de["access_token"].(string)), liste(en["access_token"].(string))
	if len(lDe) != 3 || lDe["wetter"] == nil || lDe["ort_suchen"] == nil || lDe["regen_nowcast"] == nil || len(lEn) != 3 {
		t.Fatalf("Werkzeuge ort_suchen, wetter und regen_nowcast erwartet: %v / %v", lDe, lEn)
	}
	for name := range lDe {
		if lDe[name]["description"] == lEn[name]["description"] {
			t.Errorf("%s: Beschreibung nicht sprachrichtig", name)
		}
		sDe, _ := json.Marshal(lDe[name]["inputSchema"].(map[string]any)["required"])
		sEn, _ := json.Marshal(lEn[name]["inputSchema"].(map[string]any)["required"])
		if string(sDe) != string(sEn) {
			t.Errorf("%s: Schema-Namen differieren: %s / %s", name, sDe, sEn)
		}
	}
	if !strings.Contains(lEn["wetter"]["description"].(string), "weather") {
		t.Errorf("englische Beschreibung erwartet: %v", lEn["wetter"]["description"])
	}
	tDe, _ := w.werkzeug(de["access_token"].(string), "wetter", map[string]any{"ort": "Xyzzyplatz"})
	tEn, _ := w.werkzeug(en["access_token"].(string), "wetter", map[string]any{"ort": "Xyzzyplatz"})
	if !strings.Contains(tDe, "nicht gefunden") || !strings.Contains(tEn, "not found") {
		t.Errorf("Fehlertext nicht sprachrichtig: %q / %q", tDe, tEn)
	}
	_, iEn := w.mcp(en["access_token"].(string), "initialize", map[string]any{})
	if res, _ := iEn["result"].(map[string]any); !strings.Contains(res["instructions"].(string), "local time") {
		t.Errorf("englische Anleitung erwartet: %v", iEn)
	}
}

// AC-5: Token von A wirkt nur als A; keine Antwort enthaelt Nutzerdaten.
func TestMCP_MandantentrennungZweiNutzer(t *testing.T) {
	w := neueMCPWelt(t, "anna", "bernd")
	kA := w.konto(model.User{ID: "anna", Email: "anna-geheim@beispiel.invalid", DisplayName: "Anna Geheimname"})
	kB := w.konto(model.User{ID: "bernd", Email: "bernd-geheim@beispiel.invalid", DisplayName: "Bernd Geheimname"})
	for uid, name := range map[string]string{"anna": "Alpha", "bernd": "Beta"} {
		s := w.s.WithUser(uid)
		if err := s.SaveTrip(&model.Trip{ID: "trip-" + uid, Name: "Geheimtrip " + name}); err != nil {
			t.Fatalf("SaveTrip: %v", err)
		}
		if err := s.SaveLocation(model.Location{ID: "ort-" + uid, Name: "Geheimort " + name, Lat: 47.1, Lon: 11.2}); err != nil {
			t.Fatalf("SaveLocation: %v", err)
		}
	}
	tokA, _ := w.verbinden(kA)
	accessA := tokA["access_token"].(string)

	var antworten []string
	for _, m := range []string{"initialize", "tools/list"} {
		rec, _ := w.mcp(accessA, m, map[string]any{})
		antworten = append(antworten, rec.Body.String())
	}
	for _, args := range []map[string]any{{"ort": "Frankfurt am Main"}, {"ort": "Frankfurt"}, {"ort": "Xyzzyplatz"}, {"lat": 50.11, "lon": 8.68}} {
		text, _ := w.werkzeug(accessA, "wetter", args)
		antworten = append(antworten, text)
	}
	text, _ := w.werkzeug(accessA, "ort_suchen", map[string]any{"text": "Frankfurt"})
	antworten = append(antworten, text)
	for _, a := range antworten {
		for _, geheim := range []string{"Geheimtrip", "Geheimort", "geheim@beispiel", "Geheimname", "trip-anna", "ort-bernd"} {
			if strings.Contains(a, geheim) {
				t.Errorf("AC-5: Antwort enthaelt Nutzerdaten %q: %s", geheim, a)
			}
		}
	}

	// B schickt das Token von A (mit eigenem Cookie): es wirkt nur als A.
	req, _ := http.NewRequest(http.MethodPost, "/api/mcp", strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"wetter","arguments":{"lat":50.11,"lon":8.68}}}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+accessA)
	req.AddCookie(kB)
	if rec := w.anfrage(req); rec.Code != http.StatusOK {
		t.Fatalf("Aufruf mit A-Token: %d", rec.Code)
	}
	w.core.mu.Lock()
	for _, uid := range w.core.reserve {
		if uid != "anna" {
			t.Errorf("AC-5: Abruf mit A-Token buchte auf %q", uid)
		}
	}
	w.core.mu.Unlock()
	// Ein Sitzungs-Cookie ist kein Bearer-Token.
	req, _ = http.NewRequest(http.MethodPost, "/api/mcp", strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"ping"}`))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(kB)
	if rec := w.anfrage(req); rec.Code != http.StatusUnauthorized {
		t.Errorf("Cookie ohne Bearer-Token: %d", rec.Code)
	}
}

// Protokoll wie Frieda: Versionen, ping, Benachrichtigung, unbekannte Methode.
func TestMCP_Protokoll(t *testing.T) {
	w, access := freigegebeneWelt(t)
	_, a := w.mcp(access, "initialize", map[string]any{"protocolVersion": "1999-01-01"})
	res, _ := a["result"].(map[string]any)
	info, _ := res["serverInfo"].(map[string]any)
	if res["protocolVersion"] != "2025-11-25" || info["name"] != "gregor-wetter" || res["instructions"] == "" {
		t.Errorf("initialize: %v", a)
	}
	if _, a := w.mcp(access, "gibt/es/nicht", nil); a["error"].(map[string]any)["code"] != float64(-32601) {
		t.Errorf("unbekannte Methode: %v", a)
	}
	req, _ := http.NewRequest(http.MethodPost, "/api/mcp", strings.NewReader(`{"jsonrpc":"2.0","method":"notifications/initialized"}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+access)
	if rec := w.anfrage(req); rec.Code != http.StatusAccepted {
		t.Errorf("Benachrichtigung: %d", rec.Code)
	}
	req, _ = http.NewRequest(http.MethodPost, "/api/mcp", strings.NewReader(`kein json`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+access)
	if rec := w.anfrage(req); rec.Code != http.StatusBadRequest || !strings.Contains(rec.Body.String(), "-32700") {
		t.Errorf("kein JSON: %d %s", rec.Code, rec.Body.String())
	}
	req, _ = http.NewRequest(http.MethodGet, "/api/mcp", nil)
	req.Header.Set("Authorization", "Bearer "+access)
	if rec := w.anfrage(req); rec.Code != http.StatusMethodNotAllowed || rec.Header().Get("Allow") != "POST" {
		t.Errorf("GET mit Token: %d %q", rec.Code, rec.Header().Get("Allow"))
	}
}
