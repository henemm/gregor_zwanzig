package handler

// Issue #2346 S4 (AC-13/AC-14, Go-Teil): der Proxy reicht `last_briefing` unveraendert durch
// und vermischt zwei Nutzer nicht. Kein Go-Produktcode fuer S4 -- dieser Test bewacht die
// Durchreiche (er ist von Anfang an gruen; das RED liegt in Python und Frontend).
// SPEC: docs/specs/modules/feat_2346_cockpit_paritaet.md

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestNextBriefingsProxy_PassesLastBriefingUnchanged_TwoUsers_2346(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		w.Header().Set("Content-Type", "application/json")
		// Gleiche Kennung bei beiden Nutzern, je eigener Zeitpunkt.
		_, _ = io.WriteString(w, `{"trips":{"gleich":{"at":null,"reason":"manual","last_briefing":"2026-10-22T05:00:00+00:00#`+uid+`"}},`+
			`"compare":{"gleich":{"at":null,"reason":"manual","last_briefing":null}}}`)
	}))
	t.Cleanup(srv.Close)
	h := NextBriefingsProxyHandler(srv.URL)

	var got [2]map[string]map[string]map[string]any
	for i, uid := range []string{"userA", "userB"} {
		w := callNextBriefings(h, "/api/next-briefings?user_id=userA", uid)
		if w.Code != http.StatusOK {
			t.Fatalf("%s: 200 erwartet, %d: %s", uid, w.Code, w.Body.String())
		}
		if err := json.Unmarshal(w.Body.Bytes(), &got[i]); err != nil {
			t.Fatalf("%s: keine gueltige JSON-Antwort: %v", uid, err)
		}
		want := "2026-10-22T05:00:00+00:00#" + uid
		if lb := got[i]["trips"]["gleich"]["last_briefing"]; lb != want {
			t.Errorf("%s: last_briefing %v statt %q (nicht durchgereicht oder fremder Nutzer)", uid, lb, want)
		}
		if lb, ok := got[i]["compare"]["gleich"]["last_briefing"]; !ok || lb != nil {
			t.Errorf("%s: compare.last_briefing muss als null erhalten bleiben, bekam %v (vorhanden=%v)", uid, lb, ok)
		}
	}
}
