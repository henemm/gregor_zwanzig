package handler

// Issue #1895 Scheibe S1 (Epic #1230) — Kanalzuordnung je Metrik, Parität auf
// dem Ortsvergleich. Spec: docs/specs/modules/alert_metric_channels.md,
// AC-2/AC-5.
//
// RED-Bauform wie im Trip-Geschwister-File: gemessen wird ausschliesslich der
// ausgelieferte HTTP-Antwortkoerper, kein Go-Struct-Feld. Heute rot, weil
// `model.ComparePreset` das Feld nicht kennt — der Vergleich-PUT mergt den
// Schluessel zwar generisch (mergeBriefingPatch), der anschliessende
// typisierte json.Unmarshal (compare_preset.go:292-300) verwirft ihn aber
// wieder, sodass das GET ihn nie ausliefert.
//
// AC-5 bewacht deshalb NICHT einen neu geschriebenen Merge (den gibt es auf
// diesem Pfad nicht), sondern das Struct-Feld selbst: ohne Feld ueberlebt der
// Schluessel den Unmarshal nicht (Spec, AC-5 Hinweis).

import (
	"fmt"
	"net/http"
	"reflect"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func amcCompareRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	return r
}

func amcSeedPreset(t *testing.T, s *store.Store, user, id, name string) {
	t.Helper()
	preset := model.ComparePreset{
		ID:          id,
		Name:        name,
		UserID:      user,
		LocationIDs: []string{"loc-a", "loc-b", "loc-c"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.WithUser(user).SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("SaveComparePresets(%s/%s): %v", user, id, err)
	}
}

// amcPresetPutBody traegt die Pflichtfelder aus Testbequemlichkeit mit (Muster
// compare_preset_alert_channel_thresholds_test.go) und ergaenzt die zu
// pruefende Metrik-Kanal-Zuordnung.
func amcPresetPutBody(channels map[string]interface{}) map[string]interface{} {
	return map[string]interface{}{
		"name":                  "AMC-Vergleich",
		"schedule":              "manual",
		"profil":                "SUMMER_TREKKING",
		"hour_from":             8,
		"hour_to":               17,
		"location_ids":          []string{"loc-a", "loc-b", "loc-c"},
		"empfaenger":            []string{"a@example.com"},
		"alert_metric_channels": channels,
	}
}

// AC-2: Roundtrip PUT -> GET auf dem Ortsvergleich, getrennt fuer zwei Nutzer.
// Beide Presets tragen ABSICHTLICH DIESELBE ID — sonst bewiese der Test keine
// Mandantentrennung.
func TestComparePresetAlertMetricChannels_RoundtripIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	r := amcCompareRouter(s)
	const id = "cp-1895-ac2"

	amcSeedPreset(t, s, "alice", id, "Alice-Vergleich")
	amcSeedPreset(t, s, "bob", id, "Bob-Vergleich")

	alice := map[string]interface{}{"rain": map[string]interface{}{"telegram": true}}
	bob := map[string]interface{}{"wind": map[string]interface{}{"email": true}}

	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(alice)); w.Code != http.StatusOK {
		t.Fatalf("PUT alice: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "bob",
		amcPresetPutBody(bob)); w.Code != http.StatusOK {
		t.Fatalf("PUT bob: erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	gotAlice := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "alice", nil)))
	if !reflect.DeepEqual(gotAlice, alice) {
		t.Errorf("AC-2 alice: erwartet %v, bekam %v", alice, gotAlice)
	}

	gotBob := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "bob", nil)))
	if !reflect.DeepEqual(gotBob, bob) {
		t.Errorf("AC-2 bob: erwartet %v, bekam %v", bob, gotBob)
	}
}

// AC-5: Ein Vergleich-PUT, der nur EINE Metrik mitschickt, darf die uebrigen
// Metriken nicht loeschen.
func TestComparePresetAlertMetricChannels_SingleMetricPutPreservesOtherMetrics(t *testing.T) {
	s := newTestStore(t)
	r := amcCompareRouter(s)
	const id = "cp-1895-ac5"
	amcSeedPreset(t, s, "alice", id, "AC5-Vergleich")

	initial := map[string]interface{}{
		"rain": map[string]interface{}{"telegram": true},
		"wind": map[string]interface{}{"email": true},
	}
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(initial)); w.Code != http.StatusOK {
		t.Fatalf("PUT (Vorbelegung): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	// PUT aendert NUR "rain"; "wind" fehlt im Unterobjekt komplett.
	if w := amcReq(t, r, http.MethodPut, "/api/compare/presets/"+id, "alice",
		amcPresetPutBody(map[string]interface{}{
			"rain": map[string]interface{}{"telegram": false, "sms": true},
		})); w.Code != http.StatusOK {
		t.Fatalf("PUT (nur rain): erwartet 200, bekam %d: %s", w.Code, w.Body.String())
	}

	got := amcChannelsOf(t, amcBodyMap(t, amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, "alice", nil)))

	wantRain := map[string]interface{}{"telegram": false, "sms": true}
	if !reflect.DeepEqual(got["rain"], wantRain) {
		t.Errorf("AC-5: rain nicht uebernommen — erwartet %v, bekam %v", wantRain, got["rain"])
	}
	wantWind := map[string]interface{}{"email": true}
	if !reflect.DeepEqual(got["wind"], wantWind) {
		t.Errorf("AC-5: wind vom rain-PUT geloescht — erwartet %v (unangetastet), bekam %v", wantWind, got["wind"])
	}
}

// ═══ Issue #1895 Scheibe S3a — Top-Level-null, je-Metrik-null, zwei Nutzer ═══
//
// Spec: docs/specs/modules/alert_metric_channels.md, AC-36 bis AC-39.
// Gemessen wird ueber die HTTP-Schicht BEIDER Ortsvergleichs-PUT-Wege
// (`PUT /api/compare/presets/{id}` und `PUT /api/briefings/{id}?kind=vergleich`),
// beide laufen ueber applyComparePresetPatch → mergeBriefingPatch.
//
// RED heute: AC-36 — mergeBriefingPatch setzt base[k] = v auch fuer
// `"alert_metric_channels": null` und loescht damit die ganze Map.
// AC-37/AC-38 sind 🟢 HEUTE GRUEN (Mutations-Fixtures: „null-Skip auf alle
// Felder ausdehnen" muss AC-37 rot faerben).

func s3aCompareRouter(s *store.Store) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Put("/api/briefings/{id}", UpdateBriefingHandler(s))
	return r
}

// s3aPutWege sind die zwei Ortsvergleichs-PUT-Wege aus der Spec (AC-36).
var s3aPutWege = []struct{ name, pfad string }{
	{"compare_presets", "/api/compare/presets/%s"},
	{"briefings_vergleich", "/api/briefings/%s?kind=vergleich"},
}

func s3aSeedPreset(t *testing.T, s *store.Store, user, id string, kanaele map[string]interface{}) {
	t.Helper()
	aus := false
	preset := model.ComparePreset{
		ID:                  id,
		Name:                "S3a-" + user,
		UserID:              user,
		LocationIDs:         []string{"loc-a", "loc-b", "loc-c"},
		Schedule:            "manual",
		Profil:              "SUMMER_TREKKING",
		HourFrom:            8,
		HourTo:              17,
		Empfaenger:          []string{"a@example.com"},
		CreatedAt:           time.Now().UTC(),
		HourlyEnabled:       &aus,
		AlertMetricChannels: kanaele,
	}
	if err := s.WithUser(user).SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("SaveComparePresets(%s/%s): %v", user, id, err)
	}
}

func s3aGet(t *testing.T, r *chi.Mux, user, id string) map[string]interface{} {
	t.Helper()
	w := amcReq(t, r, http.MethodGet, "/api/compare/presets/"+id, user, nil)
	if w.Code != http.StatusOK {
		t.Fatalf("GET %s/%s: erwartet 200, bekam %d: %s", user, id, w.Code, w.Body.String())
	}
	return amcBodyMap(t, w)
}

func s3aPut(t *testing.T, r *chi.Mux, pfad, user string, body map[string]interface{}) {
	t.Helper()
	if w := amcReq(t, r, http.MethodPut, pfad, user, body); w.Code != http.StatusOK {
		t.Fatalf("PUT %s als %s: erwartet 200, bekam %d: %s", pfad, user, w.Code, w.Body.String())
	}
}

// AC-36: Top-Level `"alert_metric_channels": null` ist ein No-Op — auf BEIDEN
// Ortsvergleichs-PUT-Wegen (Angleichung an den Trip, handler/trip.go:375).
func TestComparePresetAlertMetricChannels_S3a_TopLevelNullIstNoOp_AC36(t *testing.T) {
	for _, weg := range s3aPutWege {
		weg := weg
		t.Run(weg.name, func(t *testing.T) {
			s := newTestStore(t)
			r := s3aCompareRouter(s)
			const id = "cp-1895-s3a-ac36"
			gespeichert := map[string]interface{}{"gust": map[string]interface{}{"email": true}}
			s3aSeedPreset(t, s, "alice", id, gespeichert)

			s3aPut(t, r, fmt.Sprintf(weg.pfad, id), "alice", amcPresetPutBody(nil))

			got, ok := s3aGet(t, r, "alice", id)["alert_metric_channels"]
			if !ok || !reflect.DeepEqual(got, gespeichert) {
				t.Errorf("AC-36 (%s): Top-Level-null muss die gespeicherte Map unveraendert lassen — erwartet %v, bekam %v (vorhanden=%v)",
					weg.name, gespeichert, got, ok)
			}
		})
	}
}

// AC-37: fuer ein ANDERES Top-Level-Feld bleibt `null` ueberschreibend. Feld:
// `hourly_enabled` (Pointer, gespeichert `false`). Die Vorbedingung haelt fest,
// dass `null` den Wert vor S3a tatsaechlich veraendert — sonst waere die
// Gegenprobe wertlos.
func TestComparePresetAlertMetricChannels_S3a_NullFuerAnderesFeldBleibtUeberschreibend_AC37(t *testing.T) {
	for _, weg := range s3aPutWege {
		weg := weg
		t.Run(weg.name, func(t *testing.T) {
			s := newTestStore(t)
			r := s3aCompareRouter(s)
			const id = "cp-1895-s3a-ac37"
			s3aSeedPreset(t, s, "alice", id, map[string]interface{}{"gust": map[string]interface{}{"email": true}})

			vorher, ok := s3aGet(t, r, "alice", id)["hourly_enabled"]
			if !ok || vorher != false {
				t.Fatalf("Vorbedingung AC-37: hourly_enabled muss gespeichert false sein, bekam %v (vorhanden=%v)", vorher, ok)
			}

			body := amcPresetPutBody(map[string]interface{}{"gust": map[string]interface{}{"email": true}})
			body["hourly_enabled"] = nil
			s3aPut(t, r, fmt.Sprintf(weg.pfad, id), "alice", body)

			if nachher, ok := s3aGet(t, r, "alice", id)["hourly_enabled"]; ok && nachher != nil {
				t.Errorf("AC-37 (%s): `hourly_enabled: null` muss den Bestandswert wie vor S3a ueberschreiben (base[k] = v), bekam %v",
					weg.name, nachher)
			}
		})
	}
}

// AC-38: `{"gust": null}` wird als null persistiert, andere Metriken bleiben.
func TestComparePresetAlertMetricChannels_S3a_JeMetrikNullWirdPersistiert_AC38(t *testing.T) {
	for _, weg := range s3aPutWege {
		weg := weg
		t.Run(weg.name, func(t *testing.T) {
			s := newTestStore(t)
			r := s3aCompareRouter(s)
			const id = "cp-1895-s3a-ac38"
			s3aSeedPreset(t, s, "alice", id, map[string]interface{}{
				"gust":          map[string]interface{}{"email": true},
				"precipitation": map[string]interface{}{"telegram": true},
			})

			s3aPut(t, r, fmt.Sprintf(weg.pfad, id), "alice",
				amcPresetPutBody(map[string]interface{}{"gust": nil}))

			got := amcChannelsOf(t, s3aGet(t, r, "alice", id))
			gust, vorhanden := got["gust"]
			if !vorhanden || gust != nil {
				t.Errorf("AC-38 (%s): `gust` muss als null persistiert sein, bekam %v (vorhanden=%v)", weg.name, gust, vorhanden)
			}
			want := map[string]interface{}{"telegram": true}
			if !reflect.DeepEqual(got["precipitation"], want) {
				t.Errorf("AC-38 (%s): andere Metriken bleiben unveraendert — erwartet %v, bekam %v", weg.name, want, got["precipitation"])
			}
		})
	}
}

// AC-39: zwei Nutzer mit DERSELBEN Preset-ID. B schickt Top-Level-null und
// je-Metrik-null; A bleibt vollstaendig unveraendert, B behaelt seine Map
// (Top-Level-null) bzw. persistiert nur den eigenen null-Eintrag.
func TestComparePresetAlertMetricChannels_S3a_ZweiNutzerIsoliert_AC39(t *testing.T) {
	for _, weg := range s3aPutWege {
		weg := weg
		t.Run(weg.name, func(t *testing.T) {
			s := newTestStore(t)
			r := s3aCompareRouter(s)
			const id = "cp-1895-s3a-ac39"
			alice := map[string]interface{}{"gust": map[string]interface{}{"sms": true}}
			bob := map[string]interface{}{"gust": map[string]interface{}{"email": true}, "cape": map[string]interface{}{"telegram": true}}
			s3aSeedPreset(t, s, "alice", id, alice)
			s3aSeedPreset(t, s, "bob", id, bob)

			s3aPut(t, r, fmt.Sprintf(weg.pfad, id), "bob", amcPresetPutBody(nil))
			if got := amcChannelsOf(t, s3aGet(t, r, "bob", id)); !reflect.DeepEqual(got, bob) {
				t.Errorf("AC-39 (%s): Bobs Top-Level-null muss Bobs Map erhalten — erwartet %v, bekam %v", weg.name, bob, got)
			}

			s3aPut(t, r, fmt.Sprintf(weg.pfad, id), "bob", amcPresetPutBody(map[string]interface{}{"gust": nil}))

			if got := amcChannelsOf(t, s3aGet(t, r, "alice", id)); !reflect.DeepEqual(got, alice) {
				t.Errorf("AC-39 (%s): Alices Daten muessen unveraendert bleiben — erwartet %v, bekam %v", weg.name, alice, got)
			}
			gotBob := amcChannelsOf(t, s3aGet(t, r, "bob", id))
			if g, ok := gotBob["gust"]; !ok || g != nil {
				t.Errorf("AC-39 (%s): Bobs `gust` muss null sein, bekam %v", weg.name, g)
			}
			if !reflect.DeepEqual(gotBob["cape"], bob["cape"]) {
				t.Errorf("AC-39 (%s): Bobs `cape` muss bleiben — erwartet %v, bekam %v", weg.name, bob["cape"], gotBob["cape"])
			}
		})
	}
}
