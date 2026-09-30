package handler

// Issue #2422 Scheibe S5 (Kette Ortsvergleich) — Go-Teil: Persistenz-Roundtrip.
//
// Spec: docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md AC-23, AC-25, AC-26.
//
//   - AC-23: der end_date-Loesch-Sentinel wirkt auf BEIDEN Schreibwegen
//     (PUT /api/compare/presets/{id} und PUT /api/briefings/{id}?kind=vergleich),
//     mit "" (Wert, den der Editor sendet) und mit null, mit ZWEI Nutzern; die
//     Datei auf der Platte wird ROH gelesen (Schluessel fehlt, kein leerer Wert).
//   - AC-25: display_config.channel_active_metrics ueberlebt PUT/GET/Platte
//     unveraendert (Schluessel, Listenreihenfolge, leerer Eintrag [] statt
//     null/fehlend, Fremdschluessel premium_sms); ein PUT ohne die Map laesst sie
//     unberuehrt.
//   - AC-26: eine Teil-Map ERSETZT die Map (Merge nur eine Ebene tief,
//     config_merge.go:18) — das Verhalten wird festgehalten, damit eine spaetere
//     Aenderung bewusst geschieht.
//
// Die Presets kommen als ROHE Dateien aus tests/fixtures/compare_kette (dieselben
// Dateien lesen die Python-Tests) und liegen im Nutzerverzeichnis; jeder Test hat
// zwei Nutzer ueber s.WithUser bzw. den Auth-Kontext, nie "default".

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"sort"
	"testing"
)

// ketteFixture liest eine Fixture-Datei relativ zu DIESER Testdatei (nie ueber
// einen festen Repo-Pfad).
func ketteFixture(t *testing.T, name string) []byte {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller fehlgeschlagen")
	}
	pfad := filepath.Join(filepath.Dir(thisFile), "..", "..", "tests", "fixtures", "compare_kette", name+".json")
	raw, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("Fixture %s: %v", name, err)
	}
	return raw
}

// ketteFixtureMitID legt die Fixture unter einer nutzereigenen Kennung ab.
func ketteFixtureMitID(t *testing.T, name, id string) []byte {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(ketteFixture(t, name), &m); err != nil {
		t.Fatalf("Fixture %s: %v", name, err)
	}
	m["id"] = id
	out, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	return out
}

// ketteRohVonPlatte liest die Preset-Datei des Nutzers ROH von der Platte.
func ketteRohVonPlatte(t *testing.T, dataDir, userID, id string) map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(dataDir, "users", userID, "briefings", id+".json"))
	if err != nil {
		t.Fatalf("Preset-Datei %s/%s: %v", userID, id, err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Preset-Datei %s/%s: %v", userID, id, err)
	}
	return m
}

// kettePut schickt einen PUT als der Nutzer ab; weg = "compare" | "briefing".
func kettePut(t *testing.T, r http.Handler, weg, id, user, body string) {
	t.Helper()
	pfad := "/api/compare/presets/" + id
	if weg == "briefing" {
		pfad = "/api/briefings/" + id + "?kind=vergleich"
	}
	w := doReq(r, http.MethodPut, pfad, body, "", user)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT %s (%s) als %s: erwartet 200, war %d: %s", pfad, weg, user, w.Code, w.Body.String())
	}
}

// AC-23 — der Sentinel loescht das Enddatum auf beiden Schreibwegen, mit "" und null.
func TestEndDateSentinelAufBeidenSchreibwegenZweiNutzer(t *testing.T) {
	const bleibt = "2026-12-31"
	for _, weg := range []string{"compare", "briefing"} {
		for _, wert := range []string{`""`, `null`} {
			weg, wert := weg, wert
			t.Run(weg+"/"+wert, func(t *testing.T) {
				s := newTestStore(t)
				r := briefingVergleichEtagRouter(s)
				idA, idB := "kette-enddate-a", "kette-enddate-b"
				writeRawComparePresetFixture(t, s, "kette-nutzer-a", idA, string(ketteFixtureMitID(t, "end_date_gesetzt", idA)))
				writeRawComparePresetFixture(t, s, "kette-nutzer-b", idB, string(ketteFixtureMitID(t, "end_date_gesetzt", idB)))

				// Vorbedingung: beide Dateien tragen das Enddatum.
				for user, id := range map[string]string{"kette-nutzer-a": idA, "kette-nutzer-b": idB} {
					if got := ketteRohVonPlatte(t, s.DataDir, user, id)["end_date"]; got != bleibt {
						t.Fatalf("Vorbedingung: %s hat end_date %v, erwartet %s", user, got, bleibt)
					}
				}

				kettePut(t, r, weg, idA, "kette-nutzer-a", `{"end_date": `+wert+`}`)

				roh := ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-a", idA)
				if v, vorhanden := roh["end_date"]; vorhanden {
					t.Errorf("%s/%s: end_date muss auf der Platte FEHLEN (kein leerer Wert), war %#v", weg, wert, v)
				}
				if got := ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-b", idB)["end_date"]; got != bleibt {
					t.Errorf("Nutzer B: end_date darf durch den PUT von Nutzer A nicht beruehrt werden, war %v", got)
				}

				// Ein PUT ganz ohne end_date erhaelt den alten Wert (Nutzer B, gleicher Weg).
				kettePut(t, r, weg, idB, "kette-nutzer-b", `{"name": "Umbenannt"}`)
				rohB := ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-b", idB)
				if rohB["end_date"] != bleibt {
					t.Errorf("PUT ohne end_date muss den alten Wert erhalten, war %v", rohB["end_date"])
				}
				if rohB["name"] != "Umbenannt" {
					t.Errorf("Vorbedingung: der PUT ohne end_date muss gewirkt haben, name=%v", rohB["name"])
				}
			})
		}
	}
}

// ketteMapKeys liefert die Schluessel einer Map sortiert (nur fuer Meldungen/Vergleiche).
func ketteMapKeys(m map[string]interface{}) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// ketteCAM holt display_config.channel_active_metrics aus einer Preset-Map.
func ketteCAM(t *testing.T, preset map[string]interface{}) map[string]interface{} {
	t.Helper()
	dc, ok := preset["display_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("display_config fehlt oder ist kein Objekt: %#v", preset["display_config"])
	}
	cam, ok := dc["channel_active_metrics"].(map[string]interface{})
	if !ok {
		t.Fatalf("channel_active_metrics fehlt oder ist kein Objekt: %#v", dc["channel_active_metrics"])
	}
	return cam
}

func ketteFixtureCAM(t *testing.T, name string) map[string]interface{} {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(ketteFixture(t, name), &m); err != nil {
		t.Fatal(err)
	}
	return ketteCAM(t, m)
}

// AC-25 — display_config.channel_active_metrics ueberlebt den Roundtrip unveraendert.
func TestDisplayConfigChannelActiveMetricsRoundtripZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	r := briefingVergleichEtagRouter(s)
	idA, idB := "kette-cam-a", "kette-cam-b"
	// Ausgangslage beider Nutzer: Preset OHNE channel_active_metrics (Basis-Fixture).
	writeRawComparePresetFixture(t, s, "kette-nutzer-a", idA, string(ketteFixtureMitID(t, "basis", idA)))
	writeRawComparePresetFixture(t, s, "kette-nutzer-b", idB, string(ketteFixtureMitID(t, "basis", idB)))

	// Nutzer B bekommt eine ANDERE Map (Fixture, umgestellt), Nutzer A die Fixture-Map per PUT.
	bodyB := map[string]interface{}{"display_config": map[string]interface{}{
		"channel_active_metrics": map[string]interface{}{"sms": []interface{}{"wind_max_kmh"}},
	}}
	rawB, _ := json.Marshal(bodyB)
	kettePut(t, r, "compare", idB, "kette-nutzer-b", string(rawB))

	erwartet := ketteFixtureCAM(t, "roundtrip_channel_active_metrics")
	var koerper map[string]interface{}
	if err := json.Unmarshal(ketteFixtureMitID(t, "roundtrip_channel_active_metrics", idA), &koerper); err != nil {
		t.Fatal(err)
	}
	rawA, _ := json.Marshal(koerper)
	kettePut(t, r, "compare", idA, "kette-nutzer-a", string(rawA))

	// (1) GET liefert die Map unveraendert.
	w := doReq(r, http.MethodGet, "/api/compare/presets/"+idA, "", "", "kette-nutzer-a")
	if w.Code != http.StatusOK {
		t.Fatalf("GET: %d %s", w.Code, w.Body.String())
	}
	var geholt map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &geholt); err != nil {
		t.Fatal(err)
	}
	if got := ketteCAM(t, geholt); !reflect.DeepEqual(got, erwartet) {
		t.Errorf("GET: channel_active_metrics veraendert.\n erwartet %#v\n war      %#v", erwartet, got)
	}

	// (2) Platte roh: Schluessel, Reihenfolge, leerer Eintrag [] (nicht null/fehlend), Fremdschluessel.
	cam := ketteCAM(t, ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-a", idA))
	if !reflect.DeepEqual(cam, erwartet) {
		t.Errorf("Platte: channel_active_metrics veraendert.\n erwartet %#v\n war      %#v", erwartet, cam)
	}
	sms, vorhanden := cam["sms"]
	if !vorhanden {
		t.Fatalf("Der bewusst leere Eintrag sms fehlt auf der Platte: %#v", cam)
	}
	if liste, ok := sms.([]interface{}); !ok || liste == nil || len(liste) != 0 {
		t.Errorf("sms muss ein leeres Array [] sein (nicht null), war %#v", sms)
	}
	if _, ok := cam["premium_sms"]; !ok {
		t.Errorf("Fremdschluessel premium_sms ging verloren: %v", ketteMapKeys(cam))
	}
	if _, ok := cam["email"].([]interface{}); !ok {
		t.Errorf("email-Liste fehlt")
	}

	// (3) Ein PUT, der display_config OHNE channel_active_metrics sendet, laesst die Map unberuehrt.
	kettePut(t, r, "compare", idA, "kette-nutzer-a", `{"display_config": {"hourly_metrics": ["wind"]}}`)
	rohA := ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-a", idA)
	if !reflect.DeepEqual(ketteCAM(t, rohA), erwartet) {
		t.Errorf("PUT ohne channel_active_metrics hat die gespeicherte Map veraendert: %#v", ketteCAM(t, rohA))
	}
	if !reflect.DeepEqual(rohA["display_config"].(map[string]interface{})["hourly_metrics"], []interface{}{"wind"}) {
		t.Errorf("Vorbedingung: der PUT muss hourly_metrics geschrieben haben")
	}

	// (4) Nutzer B sieht nie die Map von A und umgekehrt.
	camB := ketteCAM(t, ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-b", idB))
	if !reflect.DeepEqual(ketteMapKeys(camB), []string{"sms"}) {
		t.Errorf("Nutzer B hat fremde Kanaele: %v", ketteMapKeys(camB))
	}
	wB := doReq(r, http.MethodGet, "/api/compare/presets/"+idA, "", "", "kette-nutzer-b")
	if wB.Code == http.StatusOK {
		t.Errorf("Nutzer B darf das Preset von A nicht lesen, Antwort war %d", wB.Code)
	}
}

// AC-26 — eine Teil-Map ERSETZT die Map (eine Ebene tiefer wird nicht gemergt).
func TestTeilMapChannelActiveMetricsErsetztDieMap(t *testing.T) {
	s := newTestStore(t)
	r := briefingVergleichEtagRouter(s)
	idA, idB := "kette-teil-a", "kette-teil-b"
	writeRawComparePresetFixture(t, s, "kette-nutzer-a", idA, string(ketteFixtureMitID(t, "roundtrip_channel_active_metrics", idA)))
	writeRawComparePresetFixture(t, s, "kette-nutzer-b", idB, string(ketteFixtureMitID(t, "roundtrip_channel_active_metrics", idB)))
	voll := ketteFixtureCAM(t, "roundtrip_channel_active_metrics")
	if len(voll) != 4 {
		t.Fatalf("Vorbedingung: Fixture hat vier Kanal-Eintraege, war %v", ketteMapKeys(voll))
	}

	for _, weg := range []string{"compare", "briefing"} {
		// Ausgangslage je Weg wiederherstellen (Nutzer A).
		writeRawComparePresetFixture(t, s, "kette-nutzer-a", idA, string(ketteFixtureMitID(t, "roundtrip_channel_active_metrics", idA)))
		kettePut(t, r, weg, idA, "kette-nutzer-a",
			`{"display_config": {"channel_active_metrics": {"telegram": ["temp_max_c"]}}}`)

		cam := ketteCAM(t, ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-a", idA))
		if !reflect.DeepEqual(ketteMapKeys(cam), []string{"telegram"}) {
			t.Errorf("%s: die Teil-Map muss die Map ERSETZEN (nur telegram), war %v", weg, ketteMapKeys(cam))
		}
		if !reflect.DeepEqual(cam["telegram"], []interface{}{"temp_max_c"}) {
			t.Errorf("%s: telegram-Eintrag falsch: %#v", weg, cam["telegram"])
		}
		// Nutzer B behaelt seine volle Map.
		if !reflect.DeepEqual(ketteCAM(t, ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-b", idB)), voll) {
			t.Errorf("%s: Nutzer B wurde durch die Teil-Map von A veraendert", weg)
		}
		// Andere display_config-Schluessel bleiben (Merge auf display_config-Ebene).
		dc := ketteRohVonPlatte(t, s.DataDir, "kette-nutzer-a", idA)["display_config"].(map[string]interface{})
		if _, ok := dc["active_metrics"]; !ok {
			t.Errorf("%s: active_metrics ging beim Teil-PUT verloren", weg)
		}
	}
}
