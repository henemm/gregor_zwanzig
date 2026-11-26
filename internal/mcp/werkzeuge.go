package mcp

// Werkzeuge ort_suchen, wetter (Issue #3281) und regen_nowcast (Issue #3398). Werkzeug- und Feldnamen
// sind Protokoll und bleiben unuebersetzt; Beschreibungen und Fehlertexte
// kommen aus dem Katalog (mcp.json) in der Sprache des Kontos. Die Antworten
// enthalten ausschliesslich Orts- und Wetterdaten.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/resolver"
)

// sitzung ist der Zustand eines MCP-Aufrufs: Nutzer aus dem Token, Sprache
// des Kontos.
type sitzung struct {
	h    *Handler
	ctx  context.Context
	uid  string
	lang i18n.Lang
}

func werkzeuge(lang i18n.Lang) []map[string]any {
	feld := func(typ, key string) map[string]any {
		return map[string]any{"type": typ, "description": i18n.T(lang, key, nil)}
	}
	nurLesen := map[string]any{"readOnlyHint": true, "openWorldHint": true}
	text := feld("string", "mcp.feld.text")
	text["maxLength"] = resolver.OrtsucheMaxZeichen
	felder := feld("array", "mcp.feld.felder")
	felder["items"] = map[string]any{"type": "string"}
	return []map[string]any{
		{"name": "ort_suchen", "description": i18n.T(lang, "mcp.werkzeug.ort_suchen", nil), "annotations": nurLesen,
			"inputSchema": map[string]any{"type": "object", "properties": map[string]any{"text": text},
				"required": []string{"text"}}},
		{"name": "wetter", "description": i18n.T(lang, "mcp.werkzeug.wetter", nil), "annotations": nurLesen,
			"inputSchema": map[string]any{"type": "object", "properties": map[string]any{
				"ort": feld("string", "mcp.feld.ort"), "lat": feld("number", "mcp.feld.lat"),
				"lon": feld("number", "mcp.feld.lon"), "von": feld("string", "mcp.feld.von"),
				"bis": feld("string", "mcp.feld.bis"), "felder": felder}}},
		{"name": "regen_nowcast", "description": i18n.T(lang, "mcp.werkzeug.regen_nowcast", nil), "annotations": nurLesen,
			"inputSchema": map[string]any{"type": "object", "properties": map[string]any{
				"ort": feld("string", "mcp.feld.ort"), "lat": feld("number", "mcp.feld.lat"),
				"lon": feld("number", "mcp.feld.lon")}}},
	}
}

func (s sitzung) t(key string, a i18n.Args) string { return i18n.T(s.lang, key, a) }

func jsonText(wert any) string {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	enc.Encode(wert)
	return strings.TrimSpace(b.String())
}

func (s sitzung) werkzeugAufrufen(name string, args map[string]any) (string, bool) {
	switch name {
	case "ort_suchen":
		return s.ortSuchen(args)
	case "wetter":
		return s.wetter(args)
	case "regen_nowcast":
		return s.regenNowcast(args)
	}
	return s.t("mcp.fehler.werkzeug", i18n.Args{"name": name}), true
}

func textArg(args map[string]any, name string) string {
	v, _ := args[name].(string)
	return strings.TrimSpace(v)
}

// felderArg: Feldauswahl als Liste oder Komma-Text; Namen bleiben unuebersetzt.
func felderArg(args map[string]any) []string {
	var roh []string
	switch v := args["felder"].(type) {
	case string:
		roh = strings.Split(v, ",")
	case []any:
		for _, x := range v {
			if name, ok := x.(string); ok {
				roh = append(roh, name)
			}
		}
	}
	var felder []string
	for _, name := range roh {
		if name = strings.TrimSpace(name); name != "" {
			felder = append(felder, name)
		}
	}
	return felder
}

func zahlArg(args map[string]any, name string) (float64, bool) {
	switch v := args[name].(type) {
	case float64:
		return v, !math.IsNaN(v) && !math.IsInf(v, 0)
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(v), 64)
		return f, err == nil && !math.IsNaN(f) && !math.IsInf(f, 0)
	}
	return 0, false
}

func sekundenAus(d time.Duration) int {
	s := int((d + time.Second - 1) / time.Second)
	if s < 1 {
		return 1
	}
	return s
}

// suchen: Mengenbremse `aufloesen`, dann Ortssuche; Fehler als Katalogtext.
func (s sitzung) suchen(text string) ([]resolver.OrtKandidat, string) {
	if ok, warten := s.h.o.Bremsen.ZulassenOrtssuche(s.ctx, s.uid); !ok {
		return nil, s.t("mcp.fehler.bremse", i18n.Args{"sekunden": sekundenAus(warten)})
	}
	k, err := s.h.o.Ortssuche(s.ctx, text, string(s.lang))
	switch {
	case errors.Is(err, resolver.ErrOrtEingabe):
		return nil, s.t("mcp.fehler.eingabe", i18n.Args{"max": resolver.OrtsucheMaxZeichen})
	case err != nil:
		return nil, s.t("mcp.fehler.ortssuche", nil)
	case len(k) == 0:
		return nil, s.t("mcp.fehler.ort_unbekannt", i18n.Args{"ort": text})
	}
	return k, ""
}

func (s sitzung) ortSuchen(args map[string]any) (string, bool) {
	k, fehler := s.suchen(textArg(args, "text"))
	if fehler != "" {
		return fehler, true
	}
	return jsonText(map[string]any{"kandidaten": k}), false
}

// eingabeTexte: Code eines handler.MCPEingabeFehler (Pruefung in Go oder
// 4xx-Abweisung des Core) -> Katalogschluessel. Der Detail-Text des Core ist
// deutsch und geht nie an Claude; unbekannte Codes -> eingabe_ungueltig.
var eingabeTexte = map[string]string{
	handler.MCPCodeZeitpunktUngueltig:   "mcp.fehler.zeitpunkt_ungueltig",
	handler.MCPCodeBisVorVon:            "mcp.fehler.bis_vor_von",
	handler.MCPCodeKoordinatenUngueltig: "mcp.fehler.koordinaten_ungueltig",
	"mcp_zeitraum_ausserhalb":           "mcp.fehler.zeitraum_ausserhalb",
	"mcp_feld_unbekannt":                "mcp.fehler.feld_unbekannt",
	"invalid_params":                    "mcp.fehler.eingabe_ungueltig",
}

// wetterFehler bildet einen Fehler von handler.MCPWetterAbrufen auf den
// Katalogtext in der Kontosprache ab.
func (s sitzung) wetterFehler(err error) string {
	var warten *handler.MCPWartenFehler
	var eingabe *handler.MCPEingabeFehler
	switch {
	case errors.As(err, &warten) && warten.Grund == handler.MCPGrundKontingent:
		return s.t("mcp.fehler.kontingent", i18n.Args{"minuten": (warten.WartenS + 59) / 60})
	case errors.As(err, &warten):
		return s.t("mcp.fehler.bremse", i18n.Args{"sekunden": warten.WartenS})
	case errors.As(err, &eingabe):
		if key, ok := eingabeTexte[eingabe.Code]; ok {
			return s.t(key, i18n.Args{"feld": eingabe.Feld, "gueltig": strings.Join(eingabe.Gueltig, ", ")})
		}
		return s.t("mcp.fehler.eingabe_ungueltig", nil)
	}
	return s.t("mcp.fehler.wetterdienst", nil)
}

// ortWaehlen: Koordinaten oder eindeutiger Ort. Ergebnis: Ort, oder ein
// fertiger Text (Fehler bzw. Kandidatenliste) mit isError. werkzeug nennt der
// Hinweis bei Mehrdeutigkeit (erneuter Aufruf desselben Werkzeugs).
func (s sitzung) ortWaehlen(args map[string]any, werkzeug string) (*resolver.OrtKandidat, string, bool) {
	ort := textArg(args, "ort")
	lat, hatLat := zahlArg(args, "lat")
	lon, hatLon := zahlArg(args, "lon")
	switch {
	case hatLat && hatLon:
		// Bereich und Zeitraum prueft handler.MCPWetterAbrufen (vor Bremse und Kontingent).
		return &resolver.OrtKandidat{Name: ort, Lat: lat, Lon: lon}, "", false
	case hatLat || hatLon || ort == "":
		return nil, s.t("mcp.fehler.ort_fehlt", nil), true
	}
	k, fehler := s.suchen(ort)
	if fehler != "" {
		return nil, fehler, true
	}
	if len(k) > 1 {
		return nil, jsonText(map[string]any{"mehrdeutig": true, "kandidaten": k,
			"hinweis": s.t("mcp.hinweis.mehrdeutig", i18n.Args{"ort": ort, "werkzeug": werkzeug})}), false
	}
	return &k[0], "", false
}

// mitOrt: Core-Antwort lesen und um den Ort ergaenzen; bei Fehler fertiger Text mit isError.
func (s sitzung) mitOrt(roh json.RawMessage, err error, ort *resolver.OrtKandidat) (map[string]any, string, bool) {
	if err != nil {
		return nil, s.wetterFehler(err), true
	}
	var daten map[string]any
	if json.Unmarshal(roh, &daten) != nil {
		return nil, s.t("mcp.fehler.wetterdienst", nil), true
	}
	zone, _ := daten["zeitzone"].(string)
	if ort.Zeitzone != "" {
		zone = ort.Zeitzone
	}
	daten["ort"] = ortAusgabe{Name: ort.Name, Land: ort.Land, Lat: ort.Lat, Lon: ort.Lon, Zeitzone: zone}
	return daten, "", false
}

type ortAusgabe struct {
	Name     string  `json:"name,omitempty"`
	Land     string  `json:"land,omitempty"`
	Lat      float64 `json:"lat"`
	Lon      float64 `json:"lon"`
	Zeitzone string  `json:"zeitzone,omitempty"`
}

func (s sitzung) wetter(args map[string]any) (string, bool) {
	von, bis := textArg(args, "von"), textArg(args, "bis")
	ort, text, fehler := s.ortWaehlen(args, "wetter")
	if ort == nil {
		return text, fehler
	}
	roh, err := handler.MCPWetterAbrufen(s.ctx, s.h.o.Bremsen, s.h.o.CoreURL, s.uid,
		handler.MCPWetterAnfrage{Lat: ort.Lat, Lon: ort.Lon, Von: von, Bis: bis, Felder: felderArg(args)})
	daten, text, fehler := s.mitOrt(roh, err, ort)
	if daten == nil {
		return text, fehler
	}
	if begrenzt, _ := daten["begrenzt"].(bool); begrenzt {
		ende, _ := daten["bis"].(string)
		daten["hinweis"] = s.t("mcp.hinweis.begrenzt", i18n.Args{"ende": ende})
	}
	return jsonText(daten), false
}

// intensitaetTexte: stabiler Token des Core -> Anzeigetext (Katalog, gleiche
// Schluessel wie der Radar-Alarm im Python-Kern).
var intensitaetTexte = map[string]string{
	"trocken": "alarm.radar.intensitaet.trocken", "leicht": "alarm.radar.intensitaet.leicht",
	"maessig": "alarm.radar.intensitaet.maessig", "stark": "alarm.radar.intensitaet.stark",
	"gewitter": "alarm.radar.intensitaet.gewitter", "hagel_gewitter": "alarm.radar.intensitaet.hagel_gewitter",
}

// nowcastHinweis: Hinweistext zur Datenlage; Drosselung und Ausfall vor "trocken".
func (s sitzung) nowcastHinweis(daten map[string]any) string {
	flag := func(name string) bool { b, _ := daten[name].(bool); return b }
	switch {
	case flag("gedrosselt"):
		return s.t("mcp.hinweis.nowcast_gedrosselt", nil)
	case flag("nicht_verfuegbar"):
		return s.t("mcp.hinweis.nowcast_nicht_verfuegbar", nil)
	case flag("trocken"):
		return s.t("mcp.hinweis.nowcast_trocken", nil)
	case flag("ueber_horizont_hinaus"):
		return s.t("mcp.hinweis.nowcast_ueber_horizont", nil)
	}
	return ""
}

func (s sitzung) regenNowcast(args map[string]any) (string, bool) {
	ort, text, fehler := s.ortWaehlen(args, "regen_nowcast")
	if ort == nil {
		return text, fehler
	}
	roh, err := handler.MCPNowcastAbrufen(s.ctx, s.h.o.Bremsen, s.h.o.CoreURL, s.uid, ort.Lat, ort.Lon)
	daten, text, fehler := s.mitOrt(roh, err, ort)
	if daten == nil {
		return text, fehler
	}
	token, _ := daten["intensitaet"].(string)
	if key, ok := intensitaetTexte[token]; ok {
		daten["intensitaet_text"] = s.t(key, nil)
	}
	if hinweis := s.nowcastHinweis(daten); hinweis != "" {
		daten["hinweis"] = hinweis
	}
	return jsonText(daten), false
}
