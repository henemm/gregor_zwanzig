package handler

// TDD RED — Issue #2281 (Epic #2345 P4), AC-3 + AC-4, Test 8.
// SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// /api/archive/stats zaehlt Briefings nach "<typ>:<kennung>" (BriefingCountByEntity,
// gleiche Schluesselform wie die Alarme seit #1467). Gleiche ID bei Trip und
// Ortsvergleich ergibt zwei getrennte Zaehler; Alt-Eintraege zaehlen als trip.

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestArchiveStats_SameIDTripAndCompare_CountedSeparately(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "trip", "trip_id": "gleich", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
	})

	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "userA")
	w := httptest.NewRecorder()
	ArchiveStatsHandler(s).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}

	briefings, _ := decodeCounts(t, w)
	if briefings["trip:gleich"] != 2 {
		t.Errorf("AC-3: briefings[trip:gleich]=%v, erwartet 2 (body=%s)", briefings["trip:gleich"], w.Body.String())
	}
	if briefings["compare:gleich"] != 1 {
		t.Errorf("AC-3: briefings[compare:gleich]=%v, erwartet 1 (body=%s)", briefings["compare:gleich"], w.Body.String())
	}
	if len(briefings) != 2 {
		t.Errorf("AC-3: genau 2 Briefing-Schluessel erwartet, bekommen %v", briefings)
	}
	if _, has := briefings["gleich"]; has {
		t.Errorf("AC-3: nackter Schluessel \"gleich\" darf nicht mehr vorkommen: %v", briefings)
	}
	if _, has := briefings[""]; has {
		t.Errorf("AC-3: leerer Sammeltopf fuer Compare-Eintraege: %v", briefings)
	}
}

func TestArchiveStats_BriefingCountsIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
	})
	seedBriefingLog(t, s.DataDir, "userB", []map[string]interface{}{
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": "2026-06-11T18:00:00Z", "channels": []string{"telegram"}},
	})

	for _, c := range []struct {
		uid  string
		want float64
	}{{"userA", 1}, {"userB", 2}} {
		req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), c.uid)
		w := httptest.NewRecorder()
		ArchiveStatsHandler(s).ServeHTTP(w, req)
		briefings, _ := decodeCounts(t, w)
		if briefings["compare:gleich"] != c.want || len(briefings) != 1 {
			t.Errorf("%s: briefings=%v, erwartet nur compare:gleich=%v", c.uid, briefings, c.want)
		}
	}
}
