package handler

// TDD RED — Issue #2281 (Epic #2345 P4), AC-3 + AC-4, Test 8.
// SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// /api/cockpit/status liefert je Briefing-Eintrag entity_type und entity_id —
// auch fuer Alt-Eintraege, die nur trip_id tragen (Lese-Regel). Echter Store,
// echte briefing_log.json, echter Handler via httptest, echter Auth-Kontext.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// cockpitNow liefert einen Zeitstempel von HEUTE (UTC) — das Cockpit zeigt nur
// Briefings, deren sent_at mit dem heutigen Datum beginnt.
func cockpitNow() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func decodeCockpitBriefings(t *testing.T, w *httptest.ResponseRecorder) []map[string]interface{} {
	t.Helper()
	var resp struct {
		Briefings []map[string]interface{} `json:"briefings"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("keine gueltige JSON-Antwort: %v (body=%s)", err, w.Body.String())
	}
	return resp.Briefings
}

func TestCockpitStatus_BriefingEntriesCarryEntityTypeAndID(t *testing.T) {
	s := newTestStore(t)
	now := cockpitNow()
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		// Alt-Eintrag nur mit trip_id
		{"trip_id": "gleich", "kind": "morning", "sent_at": now, "channels": []string{"email"}},
		// neuer Trip-Eintrag
		{"entity_id": "trip-neu", "entity_type": "trip", "trip_id": "trip-neu", "kind": "morning", "sent_at": now, "channels": []string{"email"}, "on_demand": false},
		// Compare-Eintrag mit derselben ID wie der Alt-Trip
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": now, "channels": []string{"telegram"}, "on_demand": true},
	})

	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil), "userA")
	w := httptest.NewRecorder()
	CockpitStatusHandler(s).ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	briefings := decodeCockpitBriefings(t, w)
	if len(briefings) != 3 {
		t.Fatalf("AC-3/AC-4: 3 heutige Briefings erwartet, %d bekommen: %s", len(briefings), w.Body.String())
	}
	want := []struct{ typ, id string }{
		{"trip", "gleich"},
		{"trip", "trip-neu"},
		{"compare", "gleich"},
	}
	for i, wnt := range want {
		b := briefings[i]
		if b["entity_type"] != wnt.typ {
			t.Errorf("AC-3: Briefing %d: entity_type=%v, erwartet %q (%v)", i, b["entity_type"], wnt.typ, b)
		}
		if b["entity_id"] != wnt.id {
			t.Errorf("AC-3: Briefing %d: entity_id=%v, erwartet %q (%v)", i, b["entity_id"], wnt.id, b)
		}
	}
	// Der Compare-Eintrag traegt kein trip_id — sonst wuerde das Frontend ihn
	// als Trip-Briefing in der Hero-Kachel zaehlen.
	if v, has := briefings[2]["trip_id"]; has && v != "" {
		t.Errorf("AC-3: Compare-Briefing traegt trip_id=%v im Cockpit", v)
	}
}

func TestCockpitStatus_BriefingEntitiesIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	now := cockpitNow()
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"entity_id": "x", "entity_type": "compare", "kind": "morning", "sent_at": now, "channels": []string{"email"}},
	})
	seedBriefingLog(t, s.DataDir, "userB", []map[string]interface{}{
		{"entity_id": "x", "entity_type": "trip", "trip_id": "x", "kind": "morning", "sent_at": now, "channels": []string{"email"}},
		{"entity_id": "y", "entity_type": "trip", "trip_id": "y", "kind": "evening", "sent_at": now, "channels": []string{"email"}},
	})

	reqA := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil), "userA")
	wA := httptest.NewRecorder()
	CockpitStatusHandler(s).ServeHTTP(wA, reqA)
	a := decodeCockpitBriefings(t, wA)
	if len(a) != 1 || a[0]["entity_type"] != "compare" || a[0]["entity_id"] != "x" {
		t.Errorf("userA sieht nicht genau seinen Compare-Eintrag: %s", wA.Body.String())
	}
}
