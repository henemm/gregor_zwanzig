package handler

// Issue #3122 B2b (Spec feat_3122_was_steht_wo Teil A Nr. 1, ADR-0077): der
// PUT der Tabelle speichert placements ungeprueft -- unbekannte und
// reservierte Schluessel (places.premium_sms, kuenftige Zeilen- und
// Kopf-Felder, version 2) stehen danach wertgleich in der Abo-Datei und
// kommen ueber die Go-Lesewege wertgleich zurueck. Echter Handler, echter
// Store, echte Dateien.
//
//   go test -count=1 ./internal/handler/ -run Placements

import (
	"encoding/json"
	"net/http"
	"reflect"
	"testing"
)

const placementsMitUnbekanntem = `{"version": 2, "zukunft_oben": {"a": [1, 2.5, "x"]},
  "rows": [{"metric_id": "wind", "places": {"premium_sms": false, "sms": true, "neu_stelle": true},
            "formats": {"email": "raw", "neu_stelle": "fein"}, "zukunft_zeile": "x"},
           {"metric_id": "gibt_es_nicht"}, "kaputt", 7,
           {"metric_id": "gust", "places": {"premium_sms": true}}],
  "outlook_reports": ["evening", "spaeter"]}`

func TestPlacements3122B2bPutBehaeltUnbekannteFelder(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			kern := neuerKern(t)
			r := placementsRouter(s, kern.srv.URL)
			seedPlacementsB2(t, s, "b2b-a")
			id := f.praefix + "b2b-a"
			var soll map[string]interface{}
			if err := json.Unmarshal([]byte(placementsMitUnbekanntem), &soll); err != nil {
				t.Fatal(err)
			}

			w := doReq(r, http.MethodPut, placementsPfad(id, f.kind), placementsMitUnbekanntem, "", "b2b-a")
			if w.Code != http.StatusOK {
				t.Fatalf("PUT placements: %d %s", w.Code, w.Body.String())
			}
			var antwort map[string]interface{}
			_ = json.Unmarshal(w.Body.Bytes(), &antwort)
			if !reflect.DeepEqual(antwort["placements"], soll) {
				t.Errorf("PUT-Antwort placements %#v", antwort["placements"])
			}
			platte := roheDatei(t, aboDatei(s, "b2b-a", id))["display_config"].(map[string]interface{})["placements"]
			if !reflect.DeepEqual(platte, soll) {
				t.Fatalf("Abo-Datei placements nicht wertgleich:\nsoll %#v\nist  %#v", soll, platte)
			}

			g := doReq(r, http.MethodGet, "/api/briefings/"+id+"?kind="+f.kind, "", "", "b2b-a")
			if g.Code != http.StatusOK {
				t.Fatalf("GET briefing: %d %s", g.Code, g.Body.String())
			}
			var abo map[string]interface{}
			if err := json.Unmarshal(g.Body.Bytes(), &abo); err != nil {
				t.Fatal(err)
			}
			dc, _ := abo["display_config"].(map[string]interface{})
			if !reflect.DeepEqual(dc["placements"], soll) {
				t.Errorf("GET briefing placements nicht wertgleich: %#v", dc["placements"])
			}
			if p := doReq(r, http.MethodGet, placementsPfad(id, f.kind), "", "", "b2b-a"); p.Code != http.StatusOK || kern.zahl() != 1 {
				t.Errorf("GET placements: %d, Kern-Aufrufe %d", p.Code, kern.zahl())
			}
			nachGet := roheDatei(t, aboDatei(s, "b2b-a", id))["display_config"].(map[string]interface{})["placements"]
			if !reflect.DeepEqual(nachGet, soll) {
				t.Errorf("Lesen hat placements veraendert: %#v", nachGet)
			}
		})
	}
}
