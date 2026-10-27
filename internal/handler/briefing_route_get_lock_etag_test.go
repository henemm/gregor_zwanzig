package handler

// TDD RED: Issue #2285 AC-4 (Dach-Epic #1374)
//
// Spec: docs/specs/modules/fix_2285_compare_put_merge_kernel.md
//
// GET /api/briefings/{id}?kind=route soll denselben ETag liefern wie
// GET /api/trips/{id} (dieselbe Datei, BriefingFingerprint ist kind-neutral).
// Heutiger Stand: der route-Zweig von GetBriefingHandler ruft weder
// s.LockBriefing noch setETagHeader -- der Response traegt gar keinen
// ETag-Header (RED).
//
// Ausfuehrung:
//   go test ./internal/handler/... -run TestBriefingRouteGetLockEtag -v

import (
	"net/http"
	"testing"
)

func TestBriefingRouteGetLockEtag_MatchesTripETag_AndIfMatchWorks(t *testing.T) {
	s := newTestStore(t)
	id := "trip-ac4-route"
	seedTrip(t, s, id, "Route ETag Test")

	r := briefingVergleichEtagRouter(s)

	wTrip := doReq(r, http.MethodGet, "/api/trips/"+id, "", "", "")
	if wTrip.Code != http.StatusOK {
		t.Fatalf("GET /api/trips/{id} expected 200, got %d: %s", wTrip.Code, wTrip.Body.String())
	}
	etTrip := mustETag(t, wTrip)

	wBriefing := doReq(r, http.MethodGet, "/api/briefings/"+id+"?kind=route", "", "", "")
	if wBriefing.Code != http.StatusOK {
		t.Fatalf("GET /api/briefings/{id}?kind=route expected 200, got %d: %s", wBriefing.Code, wBriefing.Body.String())
	}
	etBriefing := wBriefing.Header().Get("ETag")
	if etBriefing == "" {
		t.Errorf("AC-4: GET /api/briefings/{id}?kind=route liefert keinen ETag-Header (route-Zweig fehlt Sperre+ETag)")
	} else if etBriefing != etTrip {
		t.Errorf("AC-4: ETag-Parität verletzt: trip=%q briefing-route=%q", etTrip, etBriefing)
	}

	// If-Match-Symmetrie: der PUT-Weg delegiert bereits an UpdateTripHandler
	// und traegt vollen ETag-Schutz -- hier als Regressionsschutz mitgeprueft.
	wPutGood := doReq(r, http.MethodPut, "/api/briefings/"+id+"?kind=route", `{"name":"neu"}`, etTrip, "")
	if wPutGood.Code != http.StatusOK {
		t.Errorf("PUT mit korrektem If-Match erwartet 200, got %d: %s", wPutGood.Code, wPutGood.Body.String())
	}

	wPutBad := doReq(r, http.MethodPut, "/api/briefings/"+id+"?kind=route", `{"name":"neu2"}`, `"falsch"`, "")
	if wPutBad.Code != http.StatusPreconditionFailed {
		t.Errorf("PUT mit falschem If-Match erwartet 412, got %d: %s", wPutBad.Code, wPutBad.Body.String())
	}
}
