package router

// Werkzeug regen_nowcast und Parameter felder des MCP-Konnektors durch den
// echten Router (Issue #3398, Scheibe 3; AC-5 bis AC-12).
// SPEC: docs/specs/modules/mcp_wetter_vollstaendig.md
//
// Der Core ist der httptest-Server aus mcp_welt_test.go; die Nowcast-Antworten
// stehen in internal/mcp/testdata/core_nowcast_*.json (Format des Core-Endpunkts
// aus Scheibe 2). Alles wird nur ueber JSON-RPC ausgeloest.

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/model"
)

type nowcastErgebnis struct {
	Ort *struct {
		Name string `json:"name"`
	} `json:"ort"`
	Zeitzone         string           `json:"zeitzone"`
	BeginnMin        *int             `json:"beginn_min"`
	EndeMin          *int             `json:"ende_min"`
	Intensitaet      string           `json:"intensitaet"`
	IntensitaetText  string           `json:"intensitaet_text"`
	Trocken          bool             `json:"trocken"`
	Gedrosselt       bool             `json:"gedrosselt"`
	NichtVerfuegbar  bool             `json:"nicht_verfuegbar"`
	Quelle           string           `json:"quelle"`
	Hinweis          string           `json:"hinweis"`
	Frames           []map[string]any `json:"frames"`
	SummeErsteStunde float64          `json:"summe_erste_stunde_mm"`
	Mehrdeutig       bool             `json:"mehrdeutig"`
	Kandidaten       []struct {
		Name string `json:"name"`
	} `json:"kandidaten"`
}

func leseNowcast(t *testing.T, text string) nowcastErgebnis {
	t.Helper()
	var e nowcastErgebnis
	if err := json.Unmarshal([]byte(text), &e); err != nil {
		t.Fatalf("Nowcast-Ergebnis ist kein JSON: %v\n%s", err, text)
	}
	return e
}

func (c *mcpCore) zaehleNowcast() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.nowcast)
}

func werkzeugListe(w *mcpWelt, access string) map[string]map[string]any {
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

func schemaProperties(t *testing.T, tool map[string]any) map[string]any {
	t.Helper()
	schema, _ := tool["inputSchema"].(map[string]any)
	props, _ := schema["properties"].(map[string]any)
	return props
}

// AC-12 (Datenebene) + AC-6/AC-5 Schema: tools/list nennt regen_nowcast und felder,
// Beschreibungen sind je Sprache vorhanden und verschieden, Namen identisch.
func TestMCPNowcast_ToolsListeNenntWerkzeugUndFelder(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	lDe, lEn := werkzeugListe(w, de["access_token"].(string)), werkzeugListe(w, en["access_token"].(string))

	for _, l := range []map[string]map[string]any{lDe, lEn} {
		if l["regen_nowcast"] == nil {
			t.Fatalf("Werkzeug regen_nowcast fehlt: %v", l)
		}
		props := schemaProperties(t, l["regen_nowcast"])
		for _, name := range []string{"ort", "lat", "lon"} {
			if props[name] == nil {
				t.Errorf("regen_nowcast: Parameter %s fehlt: %v", name, props)
			}
		}
		if schemaProperties(t, l["wetter"])["felder"] == nil {
			t.Errorf("wetter: Parameter felder fehlt: %v", schemaProperties(t, l["wetter"]))
		}
	}
	for name, tool := range lDe {
		dDe, _ := tool["description"].(string)
		dEn, _ := lEn[name]["description"].(string)
		if dDe == "" || dEn == "" || dDe == dEn {
			t.Errorf("%s: Beschreibung leer oder nicht sprachrichtig: %q / %q", name, dDe, dEn)
		}
		if strings.HasPrefix(dDe, "mcp.") || strings.HasPrefix(dEn, "mcp.") {
			t.Errorf("%s: Beschreibung faellt auf den Schluessel zurueck: %q / %q", name, dDe, dEn)
		}
	}
	// felder-Beschreibung ebenfalls je Sprache.
	fDe, _ := schemaProperties(t, lDe["wetter"])["felder"].(map[string]any)
	fEn, _ := schemaProperties(t, lEn["wetter"])["felder"].(map[string]any)
	if fDe["description"] == "" || fDe["description"] == fEn["description"] {
		t.Errorf("felder: Beschreibung nicht sprachrichtig: %v / %v", fDe, fEn)
	}
	if !strings.Contains(lEn["regen_nowcast"]["description"].(string), "rain") {
		t.Errorf("englische Beschreibung von regen_nowcast erwartet: %v", lEn["regen_nowcast"]["description"])
	}
}

// AC-6: Durchreichung des Core-Nowcast, ergaenzt um Ort, Zeitzone, intensitaet_text.
func TestMCPNowcast_RegenDurchgereichtUndErgaenzt(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "regen_nowcast", map[string]any{"ort": "Frankfurt am Main"})
	if fehler {
		t.Fatalf("Werkzeugfehler: %s", text)
	}
	e := leseNowcast(t, text)
	if e.Ort == nil || e.Ort.Name != "Frankfurt am Main" || e.Zeitzone != "Europe/Berlin" {
		t.Fatalf("Ortsname/Zeitzone fehlen: %s", text)
	}
	if e.BeginnMin == nil || *e.BeginnMin != 30 || e.EndeMin == nil || *e.EndeMin != 75 {
		t.Errorf("Beginn/Ende nicht durchgereicht: %s", text)
	}
	if e.Intensitaet != "maessig" || e.IntensitaetText != i18n.T(i18n.De, "alarm.radar.intensitaet.maessig", nil) {
		t.Errorf("Intensitaet: Token %q, Text %q", e.Intensitaet, e.IntensitaetText)
	}
	if e.Quelle != "minutely_15" || len(e.Frames) != 13 || e.SummeErsteStunde != 1.5 {
		t.Errorf("Quelle/Frames/Summe nicht durchgereicht: %s", text)
	}
	if !strings.Contains(e.Frames[0]["zeit"].(string), "+01:00") {
		t.Errorf("Frame-Zeit nicht in Ortszeit: %v", e.Frames[0])
	}
	w.core.mu.Lock()
	defer w.core.mu.Unlock()
	if len(w.core.nowcast) != 1 || w.core.nowcast[0].Get("lat") != "50.1106444" || w.core.nowcast[0].Get("lon") != "8.6820917" {
		t.Errorf("Core-Abruf falsch: %v", w.core.nowcast)
	}
	if w.core.nowcast[0].Get("user_id") != "" {
		t.Errorf("Core darf keine user_id erhalten: %v", w.core.nowcast[0])
	}
	if len(w.core.reserve) != 1 || w.core.reserve[0] != "anna" {
		t.Errorf("Kontingent nicht auf den Token-Nutzer gebucht: %v", w.core.reserve)
	}
}

// AC-6/AC-12: Intensitaetstext in der Sprache des Kontos, Token unuebersetzt.
func TestMCPNowcast_IntensitaetstextJeSprache(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	tDe, _ := w.werkzeug(de["access_token"].(string), "regen_nowcast", map[string]any{"ort": "Frankfurt am Main"})
	tEn, _ := w.werkzeug(en["access_token"].(string), "regen_nowcast", map[string]any{"ort": "Frankfurt am Main"})
	eDe, eEn := leseNowcast(t, tDe), leseNowcast(t, tEn)
	if eDe.Intensitaet != "maessig" || eEn.Intensitaet != "maessig" {
		t.Errorf("Token muss unuebersetzt bleiben: %q / %q", eDe.Intensitaet, eEn.Intensitaet)
	}
	if eDe.IntensitaetText == "" || eEn.IntensitaetText == "" || eDe.IntensitaetText == eEn.IntensitaetText ||
		eEn.IntensitaetText != i18n.T(i18n.En, "alarm.radar.intensitaet.maessig", nil) {
		t.Errorf("Text nicht sprachrichtig: %q / %q", eDe.IntensitaetText, eEn.IntensitaetText)
	}
}

// AC-7: trocken -> ausdruecklicher Hinweis in der Kontosprache.
func TestMCPNowcast_TrockenMitHinweisJeSprache(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	tDe, fDe := w.werkzeug(de["access_token"].(string), "regen_nowcast", map[string]any{"ort": "Münster"})
	tEn, fEn := w.werkzeug(en["access_token"].(string), "regen_nowcast", map[string]any{"ort": "Münster"})
	if fDe || fEn {
		t.Fatalf("Werkzeugfehler: %s / %s", tDe, tEn)
	}
	eDe, eEn := leseNowcast(t, tDe), leseNowcast(t, tEn)
	if !eDe.Trocken || eDe.Intensitaet != "trocken" || eDe.BeginnMin != nil {
		t.Errorf("trocken erwartet: %s", tDe)
	}
	if eDe.Hinweis == "" || eEn.Hinweis == "" || eDe.Hinweis == eEn.Hinweis ||
		strings.HasPrefix(eDe.Hinweis, "mcp.") || strings.HasPrefix(eEn.Hinweis, "mcp.") {
		t.Errorf("Hinweis nicht sprachrichtig: %q / %q", eDe.Hinweis, eEn.Hinweis)
	}
}

// AC-9: gedrosselt / nicht verfuegbar -> Flags und Hinweis, nicht trocken.
func TestMCPNowcast_GedrosseltUndNichtVerfuegbarMitHinweis(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	for name, args := range map[string]map[string]any{
		"nicht verfuegbar": {"lat": 40.0, "lon": -3.0},
		"gedrosselt":       {"lat": 41.0, "lon": -3.0},
	} {
		tDe, fDe := w.werkzeug(de["access_token"].(string), "regen_nowcast", args)
		tEn, fEn := w.werkzeug(en["access_token"].(string), "regen_nowcast", args)
		if fDe || fEn {
			t.Fatalf("%s: Werkzeugfehler: %s / %s", name, tDe, tEn)
		}
		eDe, eEn := leseNowcast(t, tDe), leseNowcast(t, tEn)
		if eDe.Trocken || !(eDe.Gedrosselt || eDe.NichtVerfuegbar) {
			t.Errorf("%s: Flags erwartet, nicht trocken: %s", name, tDe)
		}
		if eDe.Hinweis == "" || eEn.Hinweis == "" || eDe.Hinweis == eEn.Hinweis ||
			strings.HasPrefix(eDe.Hinweis, "mcp.") || strings.HasPrefix(eEn.Hinweis, "mcp.") {
			t.Errorf("%s: Hinweis nicht sprachrichtig: %q / %q", name, eDe.Hinweis, eEn.Hinweis)
		}
	}
}

// AC-10: mehrdeutig -> Kandidaten, unbekannt -> Werkzeugfehler, kein Radarabruf.
func TestMCPNowcast_OrtsaufloesungWieWetter(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, _ := w.werkzeug(access, "regen_nowcast", map[string]any{"ort": "Frankfurt"})
	e := leseNowcast(t, text)
	if !e.Mehrdeutig || len(e.Kandidaten) < 2 || len(e.Frames) != 0 || e.Hinweis == "" {
		t.Fatalf("Kandidatenliste ohne Nowcast erwartet: %s", text)
	}
	text, fehler := w.werkzeug(access, "regen_nowcast", map[string]any{"ort": "Xyzzyplatz"})
	if !fehler || !strings.Contains(text, "Xyzzyplatz") || !strings.Contains(text, "genauer") {
		t.Errorf("Werkzeugfehler mit Hinweis erwartet: %v %s", fehler, text)
	}
	if n := w.core.zaehleNowcast(); n != 0 {
		t.Errorf("bei mehrdeutigem/unbekanntem Ort wurde der Nowcast abgerufen: %d", n)
	}
	if reserve, _ := w.core.zaehle(); reserve != 0 {
		t.Errorf("Kontingent bei mehrdeutigem/unbekanntem Ort gebucht: %d", reserve)
	}
}

func TestMCPNowcast_UngueltigeEingaben(t *testing.T) {
	w, access := freigegebeneWelt(t)
	for name, args := range map[string]map[string]any{
		"nichts":       {},
		"lat zu gross": {"lat": 91.0, "lon": 8.0},
		"nur lat":      {"lat": 50.0},
	} {
		text, fehler := w.werkzeug(access, "regen_nowcast", args)
		if !fehler || text == "" {
			t.Errorf("%s: Werkzeugfehler erwartet: %v %s", name, fehler, text)
		}
	}
	text, _ := w.werkzeug(access, "regen_nowcast", map[string]any{"lat": 91.0, "lon": 8.0})
	if want := i18n.T(i18n.De, "mcp.fehler.koordinaten_ungueltig", nil); text != want {
		t.Errorf("Katalogtext zu ungueltigen Koordinaten erwartet: %q, war %q", want, text)
	}
	if n := w.core.zaehleNowcast(); n != 0 {
		t.Errorf("ungueltige Eingaben riefen den Core: %d", n)
	}
}

// AC-11: Kontingent von A erschoepft -> Fehler mit Wartehinweis ohne Core-Abruf;
// B ruft weiter ab; keine Nutzerdaten in den Antworten.
func TestMCPNowcast_KontingentUndMandantentrennungZweiKonten(t *testing.T) {
	w := neueMCPWelt(t, "anna", "bernd")
	kA := w.konto(model.User{ID: "anna", Email: "anna-geheim@beispiel.invalid", DisplayName: "Anna Geheimname"})
	kB := w.konto(model.User{ID: "bernd", Email: "bernd-geheim@beispiel.invalid", DisplayName: "Bernd Geheimname"})
	for uid, name := range map[string]string{"anna": "Alpha", "bernd": "Beta"} {
		s := w.s.WithUser(uid)
		if err := s.SaveLocation(model.Location{ID: "ort-" + uid, Name: "Geheimort " + name, Lat: 47.1, Lon: 11.2}); err != nil {
			t.Fatalf("SaveLocation: %v", err)
		}
	}
	tokA, _ := w.verbinden(kA)
	tokB, _ := w.verbinden(kB)
	accessA, accessB := tokA["access_token"].(string), tokB["access_token"].(string)
	w.core.mu.Lock()
	w.core.voll["anna"] = true
	w.core.mu.Unlock()

	text, fehler := w.werkzeug(accessA, "regen_nowcast", map[string]any{"lat": 50.11, "lon": 8.68})
	if !fehler || !strings.Contains(text, "Tageskontingent") || !strings.Contains(text, "90 Minuten") {
		t.Fatalf("AC-11: Werkzeugfehler mit Wartezeit erwartet: %v %s", fehler, text)
	}
	if n := w.core.zaehleNowcast(); n != 0 {
		t.Errorf("AC-11: Nowcast-Abruf trotz erschoepftem Kontingent: %d", n)
	}
	antworten := []string{text}
	textB, fehlerB := w.werkzeug(accessB, "regen_nowcast", map[string]any{"ort": "Frankfurt am Main"})
	if fehlerB {
		t.Fatalf("B muss weiter abrufen koennen: %s", textB)
	}
	antworten = append(antworten, textB)
	w.core.mu.Lock()
	reserve := append([]string(nil), w.core.reserve...)
	w.core.mu.Unlock()
	if len(reserve) != 2 || reserve[0] != "anna" || reserve[1] != "bernd" {
		t.Errorf("AC-11: Buchung je Aufruf auf das eigene Konto erwartet: %v", reserve)
	}
	for _, a := range antworten {
		for _, geheim := range []string{"Geheimort", "geheim@beispiel", "Geheimname", "ort-anna", "ort-bernd"} {
			if strings.Contains(a, geheim) {
				t.Errorf("AC-11: Antwort enthaelt Nutzerdaten %q: %s", geheim, a)
			}
		}
	}
}

// AC-5: felder wird an den Core durchgereicht (Ergebnis kommt aus dem Core).
func TestMCPWetter_FelderWerdenAnDenCoreDurchgereicht(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, fehler := w.werkzeug(access, "wetter", map[string]any{
		"lat": 50.1106444, "lon": 8.6820917, "felder": []any{"wind_chill_c", "t2m_c"}})
	if fehler {
		t.Fatalf("Werkzeugfehler: %s", text)
	}
	w.core.mu.Lock()
	defer w.core.mu.Unlock()
	if len(w.core.wetter) != 1 {
		t.Fatalf("ein Core-Abruf erwartet: %v", w.core.wetter)
	}
	gesendet := strings.Join(w.core.wetter[0]["felder"], ",")
	if !strings.Contains(gesendet, "wind_chill_c") || !strings.Contains(gesendet, "t2m_c") {
		t.Errorf("felder nicht an den Core durchgereicht: %v", w.core.wetter[0])
	}
}

// AC-5: unbekanntes Feld (Core 422 mcp_feld_unbekannt) -> Werkzeugfehler mit
// Katalogtext in der Kontosprache, nie der Core-Text.
func TestMCPWetter_UnbekanntesFeldKatalogtextJeSprache(t *testing.T) {
	const coreText = "Deutscher Core-Text, der nie bei Claude ankommt"
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	w.core.mu.Lock()
	w.core.abweisung = `{"code":"mcp_feld_unbekannt","detail":"` + coreText + `"}`
	w.core.mu.Unlock()
	args := map[string]any{"lat": 50.1, "lon": 8.6, "felder": []any{"gibt_es_nicht"}}
	tDe, fDe := w.werkzeug(de["access_token"].(string), "wetter", args)
	tEn, fEn := w.werkzeug(en["access_token"].(string), "wetter", args)
	if !fDe || !fEn {
		t.Fatalf("Werkzeugfehler erwartet: %v %v", fDe, fEn)
	}
	for lang, text := range map[i18n.Lang]string{i18n.De: tDe, i18n.En: tEn} {
		if text == "" || strings.Contains(text, coreText) || strings.Contains(text, "mcp.fehler.") {
			t.Errorf("%s: Katalogtext erwartet, kein Core-Text/Schluessel: %q", lang, text)
		}
		if text == i18n.T(lang, "mcp.fehler.eingabe_ungueltig", nil) {
			t.Errorf("%s: spezifischer Text zu unbekanntem Feld erwartet, nicht der allgemeine: %q", lang, text)
		}
	}
	if tDe == tEn {
		t.Errorf("Fehlertext nicht sprachrichtig: %q", tDe)
	}
}

// Adversary F002 (AC-11): die Mengenbremse `vorhersage` greift auch fuer
// regen_nowcast, vor Kontingent und Core-Abruf.
func TestMCPNowcast_MengenbremseVorhersage(t *testing.T) {
	fest := time.Date(2026, 11, 26, 12, 0, 0, 0, time.UTC)
	defer handler.SetBremsenUhr(func() time.Time { return fest })()
	w, access := freigegebeneWelt(t)
	args := map[string]any{"lat": 50.11, "lon": 8.68}
	for i := 0; i < handler.BremseAbrufJeMinute; i++ {
		if text, fehler := w.werkzeug(access, "regen_nowcast", args); fehler {
			t.Fatalf("Abruf %d innerhalb der Bremse abgelehnt: %s", i+1, text)
		}
	}
	text, fehler := w.werkzeug(access, "regen_nowcast", args)
	if !fehler || !strings.Contains(text, "Sekunden") {
		t.Fatalf("Werkzeugfehler mit Wartehinweis erwartet: %v %s", fehler, text)
	}
	if n := w.core.zaehleNowcast(); n != handler.BremseAbrufJeMinute {
		t.Errorf("gebremster Aufruf darf den Core nicht rufen: %d Abrufe", n)
	}
	if reserve, _ := w.core.zaehle(); reserve != handler.BremseAbrufJeMinute {
		t.Errorf("gebremster Aufruf darf kein Kontingent buchen: %d", reserve)
	}
}

// Adversary F003 (AC-5): Kette Core-Rumpf (feld, gueltig) -> Go-Parser -> Text
// in der Kontosprache, der den unbekannten und die gueltigen Namen nennt.
func TestMCPWetter_UnbekanntesFeldNenntGueltigeNamenJeSprache(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	w.core.mu.Lock()
	w.core.abweisung = `{"code":"mcp_feld_unbekannt","detail":"Core-Text","feld":"gibt_es_nicht","gueltig":["t2m_c","wind_chill_c"]}`
	w.core.mu.Unlock()
	args := map[string]any{"lat": 50.1, "lon": 8.6, "felder": "gibt_es_nicht"}
	for lang, access := range map[i18n.Lang]string{i18n.De: de["access_token"].(string), i18n.En: en["access_token"].(string)} {
		text, fehler := w.werkzeug(access, "wetter", args)
		want := i18n.T(lang, "mcp.fehler.feld_unbekannt", i18n.Args{"feld": "gibt_es_nicht", "gueltig": "t2m_c, wind_chill_c"})
		if !fehler || text != want {
			t.Errorf("%s: Text mit unbekanntem und gueltigen Namen erwartet: %q, war %q", lang, want, text)
		}
		for _, name := range []string{"gibt_es_nicht", "t2m_c", "wind_chill_c"} {
			if !strings.Contains(text, name) {
				t.Errorf("%s: %q fehlt im Text %q", lang, name, text)
			}
		}
	}
}

// Adversary F004 (AC-12): Hinweis "ueber den Horizont hinaus" je Sprache.
func TestMCPNowcast_UeberHorizontHinweisJeSprache(t *testing.T) {
	w := neueMCPWelt(t, "anna", "emma")
	de, _ := w.verbinden(w.konto(model.User{ID: "anna", Language: "de"}))
	en, _ := w.verbinden(w.konto(model.User{ID: "emma", Language: "en"}))
	args := map[string]any{"lat": 42.0, "lon": 9.0}
	tDe, _ := w.werkzeug(de["access_token"].(string), "regen_nowcast", args)
	tEn, _ := w.werkzeug(en["access_token"].(string), "regen_nowcast", args)
	eDe, eEn := leseNowcast(t, tDe), leseNowcast(t, tEn)
	if eDe.Hinweis != i18n.T(i18n.De, "mcp.hinweis.nowcast_ueber_horizont", nil) ||
		eEn.Hinweis != i18n.T(i18n.En, "mcp.hinweis.nowcast_ueber_horizont", nil) || eDe.Hinweis == eEn.Hinweis {
		t.Errorf("Horizont-Hinweis nicht sprachrichtig: %q / %q", eDe.Hinweis, eEn.Hinweis)
	}
}

// Adversary F005 (AC-10/12): der Mehrdeutigkeits-Hinweis nennt das aufgerufene Werkzeug.
func TestMCPNowcast_MehrdeutigHinweisNenntRegenNowcast(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, _ := w.werkzeug(access, "regen_nowcast", map[string]any{"ort": "Frankfurt"})
	e := leseNowcast(t, text)
	if !strings.Contains(e.Hinweis, "regen_nowcast") || strings.Contains(e.Hinweis, "wetter ") {
		t.Errorf("Hinweis muss regen_nowcast nennen: %q", e.Hinweis)
	}
}

// Adversary F008: Drosselung geht im Hinweis vor "trocken" (nie Entwarnung ohne Daten).
func TestMCPNowcast_GedrosseltHinweisVorTrocken(t *testing.T) {
	w, access := freigegebeneWelt(t)
	text, _ := w.werkzeug(access, "regen_nowcast", map[string]any{"lat": 43.0, "lon": 9.0})
	if e := leseNowcast(t, text); e.Hinweis != i18n.T(i18n.De, "mcp.hinweis.nowcast_gedrosselt", nil) {
		t.Errorf("Drosselungs-Hinweis erwartet: %q", e.Hinweis)
	}
}
