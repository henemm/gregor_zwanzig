package handler

// Issue #3047 Runde 7, Paket p10 (Matrixzelle orte.ortsfolge / orte.orte_auswahl): Umsortieren
// und Entfernen im Orte-Reiter speichern per Read-Modify-Write.
//
// Rumpf = was der Reiter sendet (buildComparePresetPartialPayload(id, {location_ids}), im
// Frontend-Test p10_ortsfolge_reiter_gleich_mail.test.ts byte-genau festgehalten): NUR
// location_ids. Erwartet: neue Folge auf der Platte, alle anderen Felder des Modells (inkl.
// display_config, official_warnings, Schalter) unveraendert, Kennung eines geloeschten Orts bleibt erhalten,
// der zweite Nutzer bleibt unberuehrt und kann das Preset des ersten nicht aendern.
//
//   go test ./internal/handler/ -run TestOrteReiterReihenfolgeUndEntfernenReadModifyWriteZweiNutzer

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestOrteReiterReihenfolgeUndEntfernenReadModifyWriteZweiNutzer(t *testing.T) {
	const presetJSON = `{
  "id": "%ID%", "name": "Orte p10", "kind": "vergleich",
  "location_ids": ["loc-a", "loc-b", "loc-geloescht", "loc-c"],
  "schedule": "daily", "profil": "ALLGEMEIN", "forecast_hours": 48,
  "morning_enabled": true, "morning_time": "07:00:00", "evening_enabled": false,
  "created_at": "2026-09-01T00:00:00Z", "corridors": [], "empfaenger": [],
  "hourly_enabled": true, "outlook_enabled": false, "send_telegram": true,
  "official_warnings": {"enabled": true, "sources": ["geosphere", "meteoalarm"]},
  "display_config": {"active_metrics": [{"metric_id": "wind", "aggregation": "max"}, {"metric_id": "temperature", "aggregation": "max"}]}
}`
	for _, weg := range []string{"compare", "briefing"} {
		weg := weg
		t.Run(weg, func(t *testing.T) {
			s := newTestStore(t)
			r := briefingVergleichEtagRouter(s)
			nutzerA, nutzerB := "p10-nutzer-a", "p10-nutzer-b"
			idA, idB := "p10-orte-a", "p10-orte-b"
			writeRawComparePresetFixture(t, s, nutzerA, idA, string(bytes.ReplaceAll([]byte(presetJSON), []byte("%ID%"), []byte(idA))))
			writeRawComparePresetFixture(t, s, nutzerB, idB, string(bytes.ReplaceAll([]byte(presetJSON), []byte("%ID%"), []byte(idB))))
			vorherA := ketteRohVonPlatte(t, s.DataDir, nutzerA, idA)
			dateiB := filepath.Join(s.DataDir, "users", nutzerB, "briefings", idB+".json")
			vorherB, err := os.ReadFile(dateiB)
			if err != nil {
				t.Fatal(err)
			}

			schritte := []struct {
				name, body string
				soll       []interface{}
			}{
				{"umsortieren", `{"location_ids":["loc-c","loc-a","loc-geloescht","loc-b"]}`, []interface{}{"loc-c", "loc-a", "loc-geloescht", "loc-b"}},
				{"entfernen", `{"location_ids":["loc-c","loc-geloescht","loc-b"]}`, []interface{}{"loc-c", "loc-geloescht", "loc-b"}},
			}
			for _, sch := range schritte {
				kettePut(t, r, weg, idA, nutzerA, sch.body)
				roh := ketteRohVonPlatte(t, s.DataDir, nutzerA, idA)
				if !reflect.DeepEqual(roh["location_ids"], sch.soll) {
					t.Fatalf("%s: location_ids auf der Platte %v, erwartet %v", sch.name, roh["location_ids"], sch.soll)
				}
				for k, v := range vorherA {
					if k == "location_ids" {
						continue
					}
					if !reflect.DeepEqual(roh[k], v) {
						t.Errorf("%s: Feld %q darf sich nicht aendern (Read-Modify-Write), war %#v, ist %#v", sch.name, k, v, roh[k])
					}
				}
			}

			// Zweiter Nutzer: Datei bytegleich, und er kann das Preset von A nicht schreiben.
			if nachherB, _ := os.ReadFile(dateiB); !bytes.Equal(nachherB, vorherB) {
				t.Errorf("Nutzer B: Datei darf durch die PUTs von A nicht beruehrt werden")
			}
			pfad := "/api/compare/presets/" + idA
			if weg == "briefing" {
				pfad = "/api/briefings/" + idA + "?kind=vergleich"
			}
			if w := doReq(r, http.MethodPut, pfad, `{"location_ids":["loc-b"]}`, "", nutzerB); w.Code == http.StatusOK {
				t.Errorf("Nutzer B darf das Preset von A nicht aendern, Status %d", w.Code)
			}
			var ids []string
			if raw, _ := json.Marshal(ketteRohVonPlatte(t, s.DataDir, nutzerA, idA)["location_ids"]); json.Unmarshal(raw, &ids) != nil || !reflect.DeepEqual(ids, []string{"loc-c", "loc-geloescht", "loc-b"}) {
				t.Errorf("Nutzer A: location_ids nach Fremd-PUT %v", ids)
			}
		})
	}
}
