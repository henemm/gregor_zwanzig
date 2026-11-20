package handler

// TDD RED — Issue #3189: Herkunft eigener Wetter-Vorlagen.
// Spec: docs/specs/modules/feat_3189_vorlage_herkunft.md
// AC-1 (herkunft {id,name} gespeichert, Name eingefroren, PATCH laesst sie stehen),
// AC-3 (zwei Nutzer getrennt, keine fremde Aufloesung, trimmen/kappen 200,
// leerer Name verwirft das Feld ohne Fehler),
// AC-5 (POST ohne herkunft erzeugt kein Feld).
//
// Kein Mock: echte Handler (chi-Router aus metric_preset_art_standard_test.go),
// echter Store auf t.TempDir(), user_id aus dem echten Auth-Kontext
// (middleware.ContextWithUserID). Das neue Feld wird ueber JSON-Antwort und die
// gespeicherte Datei geprueft, nicht ueber Struct-Felder — sonst kompilierte
// das Paket im RED-Stand nicht.

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

func h3189Router(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Lang(s))
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))
	r.Post("/api/trips", CreateTripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	return r
}

// h3189Herkunft liest das Feld herkunft aus einer Vorlage (Antwort/Datei).
func h3189Herkunft(p obj) (obj, bool) {
	raw, ok := p["herkunft"]
	if !ok || raw == nil {
		return nil, false
	}
	m, ok := raw.(map[string]interface{})
	if !ok {
		return nil, false
	}
	return obj(m), true
}

func h3189Liste(t *testing.T, h http.Handler, user string) []obj {
	t.Helper()
	w := v2794Anfrage(t, h, "GET", "/api/metric-presets", user, "de", nil)
	if w.Code != http.StatusOK {
		t.Fatalf("GET presets %s: %d %s", user, w.Code, w.Body.String())
	}
	var out []obj
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("parse list: %v", err)
	}
	return out
}

// AC-1: POST speichert herkunft {id,name}; Antwort, Liste und Datei tragen sie;
// Umbenennung des Trips aendert den eingefrorenen Namen nicht; PATCH (Name +
// Metriken) laesst herkunft unberuehrt.
func TestHerkunft3189_AC1_PostSpeichertHerkunftEingefrorenUndPatchLaesstSieStehen(t *testing.T) {
	s := newTestStore(t)
	h := h3189Router(s)

	trip := v2794NeuerTrip("gr221")
	trip["name"] = "GR221"
	if w := v2794Anfrage(t, h, "POST", "/api/trips", "anna", "de", trip); w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Trip anlegen: %d %s", w.Code, w.Body.String())
	}

	code, resp := v2794Vorlage(t, h, "anna", obj{
		"name": "Mallorca Frühling", "kind": "route",
		"herkunft": obj{"id": "gr221", "name": "GR221"},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST Vorlage: %d %v", code, resp)
	}
	hk, ok := h3189Herkunft(resp)
	if !ok {
		t.Fatalf("AC-1: POST-Antwort ohne herkunft: %v", resp)
	}
	if hk["id"] != "gr221" || hk["name"] != "GR221" {
		t.Fatalf("AC-1: herkunft in Antwort falsch: %v", hk)
	}
	if _, ok := resp["herkunft_kind"]; ok {
		t.Fatalf("AC-1: Art darf nicht doppelt gespeichert werden: %v", resp)
	}
	presetID, _ := resp["id"].(string)

	// Liste liefert die Herkunft.
	lp := v2794NachName(t, h3189Liste(t, h, "anna"), "Mallorca Frühling")
	if hk, ok := h3189Herkunft(lp); !ok || hk["name"] != "GR221" || hk["id"] != "gr221" {
		t.Fatalf("AC-1: Liste ohne korrekte herkunft: %v", lp)
	}

	// Trip umbenennen: eingefrorener Name bleibt.
	trip["name"] = "GR221 umbenannt"
	if w := v2794Anfrage(t, h, "PUT", "/api/trips/gr221", "anna", "de", trip); w.Code != http.StatusOK {
		t.Fatalf("Trip umbenennen: %d %s", w.Code, w.Body.String())
	}
	lp = v2794NachName(t, h3189Liste(t, h, "anna"), "Mallorca Frühling")
	if hk, ok := h3189Herkunft(lp); !ok || hk["name"] != "GR221" {
		t.Fatalf("AC-1: Name nach Trip-Umbenennung nicht eingefroren: %v", lp)
	}

	// PATCH Name + Metriken: herkunft bleibt.
	w := v2794Anfrage(t, h, "PATCH", "/api/metric-presets/"+presetID, "anna", "de", obj{
		"name":    "Mallorca Sommer",
		"metrics": []obj{{"metric_id": "temperature", "enabled": true, "use_friendly_format": false}},
	})
	if w.Code != http.StatusOK {
		t.Fatalf("PATCH: %d %s", w.Code, w.Body.String())
	}
	datei := v2794NachName(t, v2794Datei(t, s, "anna"), "Mallorca Sommer")
	if hk, ok := h3189Herkunft(datei); !ok || hk["id"] != "gr221" || hk["name"] != "GR221" {
		t.Fatalf("AC-1: PATCH hat herkunft veraendert/entfernt: %v", datei)
	}
}

// AC-3: Name getrimmt, auf 200 Zeichen gekappt; leerer Name oder leere id
// verwirft das Feld ohne Fehler.
func TestHerkunft3189_AC3_NameGetrimmtGekapptLeerVerworfen(t *testing.T) {
	s := newTestStore(t)
	h := h3189Router(s)

	code, resp := v2794Vorlage(t, h, "anna", obj{
		"name": "Getrimmt", "kind": "vergleich",
		"herkunft": obj{"id": "cmp-1", "name": "   Mallorca Nord  "},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST: %d %v", code, resp)
	}
	if hk, ok := h3189Herkunft(resp); !ok || hk["name"] != "Mallorca Nord" || hk["id"] != "cmp-1" {
		t.Fatalf("AC-3: Name nicht getrimmt gespeichert: %v", resp)
	}

	lang := strings.Repeat("ä", 250)
	code, resp = v2794Vorlage(t, h, "anna", obj{
		"name": "Gekappt", "kind": "route",
		"herkunft": obj{"id": "t-1", "name": lang},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST lang: %d %v", code, resp)
	}
	hk, ok := h3189Herkunft(resp)
	if !ok {
		t.Fatalf("AC-3: langer Name hat herkunft verworfen statt gekappt: %v", resp)
	}
	if n, _ := hk["name"].(string); len([]rune(n)) != 200 {
		t.Fatalf("AC-3: Name nicht auf 200 Zeichen gekappt, Laenge %d", len([]rune(n)))
	}

	for i, leer := range []obj{
		{"id": "t-2", "name": "   "},
		{"id": "", "name": "GR221"},
	} {
		name := []string{"LeerName", "LeerID"}[i]
		code, resp = v2794Vorlage(t, h, "anna", obj{"name": name, "kind": "route", "herkunft": leer})
		if code != http.StatusCreated {
			t.Fatalf("AC-3: leere herkunft darf keinen Fehler liefern (%s): %d %v", name, code, resp)
		}
		if _, ok := h3189Herkunft(resp); ok {
			t.Fatalf("AC-3: leere herkunft nicht verworfen (%s): %v", name, resp)
		}
		if _, ok := h3189Herkunft(v2794NachName(t, v2794Datei(t, s, "anna"), name)); ok {
			t.Fatalf("AC-3: leere herkunft in Datei gelandet (%s)", name)
		}
	}
}

// AC-5: POST ohne herkunft erzeugt kein Feld (weder Antwort noch Datei).
func TestHerkunft3189_AC5_PostOhneHerkunftErzeugtKeinFeld(t *testing.T) {
	s := newTestStore(t)
	h := h3189Router(s)

	code, resp := v2794Vorlage(t, h, "anna", obj{"name": "Anlegemodus", "kind": "route"})
	if code != http.StatusCreated {
		t.Fatalf("POST: %d %v", code, resp)
	}
	if _, ok := resp["herkunft"]; ok {
		t.Fatalf("AC-5: Antwort traegt herkunft ohne Eingabe: %v", resp)
	}
	if strings.Contains(v2794DateiRoh(t, s, "anna"), "herkunft") {
		t.Fatalf("AC-5: Datei traegt herkunft ohne Eingabe: %s", v2794DateiRoh(t, s, "anna"))
	}
	// Positivkontrolle (sonst waere der Test auch bei fehlender Funktion gruen):
	// mit herkunft entsteht das Feld.
	code, resp = v2794Vorlage(t, h, "anna", obj{
		"name": "Mit Herkunft", "kind": "route", "herkunft": obj{"id": "gr221", "name": "GR221"},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST mit herkunft: %d %v", code, resp)
	}
	if _, ok := h3189Herkunft(resp); !ok {
		t.Fatalf("AC-5 Positivkontrolle: POST mit herkunft ohne Feld: %v", resp)
	}
}

// AC-3: zwei Nutzer — jeder sieht nur seine Vorlagen samt Herkunft; B mit
// gleicher Herkunft-id laesst A unberuehrt; die id wird nicht fremd aufgeloest.
func TestHerkunft3189_AC3_ZweiNutzerGetrennt(t *testing.T) {
	s := newTestStore(t)
	h := h3189Router(s)

	if code, resp := v2794Vorlage(t, h, "anna", obj{
		"name": "Annas Vorlage", "kind": "route", "herkunft": obj{"id": "gr221", "name": "GR221"},
	}); code != http.StatusCreated {
		t.Fatalf("POST anna: %d %v", code, resp)
	}

	if l := h3189Liste(t, h, "bernd"); len(l) != 0 {
		t.Fatalf("AC-3: Nutzer B sieht fremde Vorlagen: %v", l)
	}

	code, resp := v2794Vorlage(t, h, "bernd", obj{
		"name": "Bernds Vorlage", "kind": "route", "herkunft": obj{"id": "gr221", "name": "Bernds Trip"},
	})
	if code != http.StatusCreated {
		t.Fatalf("POST bernd: %d %v", code, resp)
	}
	// Name ist der vom Client gelieferte, nicht aus fremdem Bestand aufgeloest.
	if hk, ok := h3189Herkunft(resp); !ok || hk["name"] != "Bernds Trip" {
		t.Fatalf("AC-3: herkunft von B falsch: %v", resp)
	}

	la := h3189Liste(t, h, "anna")
	if len(la) != 1 {
		t.Fatalf("AC-3: A hat %d Vorlagen, erwartet 1: %v", len(la), la)
	}
	if hk, ok := h3189Herkunft(la[0]); !ok || hk["name"] != "GR221" || hk["id"] != "gr221" {
		t.Fatalf("AC-3: A's herkunft durch B veraendert: %v", la[0])
	}
	lb := h3189Liste(t, h, "bernd")
	if len(lb) != 1 || lb[0]["name"] != "Bernds Vorlage" {
		t.Fatalf("AC-3: B sieht nicht genau seine Vorlage: %v", lb)
	}
	if hk, ok := h3189Herkunft(lb[0]); !ok || hk["name"] != "Bernds Trip" {
		t.Fatalf("AC-3: B's herkunft in Liste falsch: %v", lb[0])
	}
}
