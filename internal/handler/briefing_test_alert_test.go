package handler_test

// Issue #3441 (S5b): Test-Alarm POST /api/briefings/{id}/test-alert?kind=route|vergleich.
// Spec: docs/specs/modules/feat_3441_test_alarm.md (AC-9, AC-13 Go-Teil).
//
// Bauart wie briefing_send_test.go: ECHTER Produktions-Router samt AuthMiddleware, der Python-Core
// ist ein httptest-Server, der jede Anfrage mitschreibt (Helfer newVBUpstream/newVBEnv aus
// briefing_preview_test.go). Geprueft wird die tatsaechlich abgesetzte Upstream-Anfrage.

import (
	"net/http"
	"testing"
)

const taPfad = "/api/briefings/t-3441/test-alert"

// AC-13: kind ist Pflicht (Whitelist route|vergleich), sonst 400 ohne Upstream.
func TestBriefingTestAlert_KindPflicht_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, c := range []struct {
		query                  string
		wantStatus, wantUpstrm int
	}{
		{"", 400, 0}, {"?kind=trip", 400, 0}, {"?kind=ROUTE", 400, 0},
		{"?kind=route", 200, 1}, {"?kind=vergleich", 200, 1},
	} {
		t.Run("kind"+c.query, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", taPfad+c.query, "alice", "")
			if w.Code != c.wantStatus {
				t.Fatalf("Status %d, erwartet %d (body=%q)", w.Code, c.wantStatus, w.Body.String())
			}
			if c.wantStatus == 400 {
				bsAssertSendError(t, w, "kind_required")
			}
			if py.count() != c.wantUpstrm {
				t.Errorf("Python-Core %d-mal erreicht, erwartet %d", py.count(), c.wantUpstrm)
			}
		})
	}
}

// AC-13: ungueltig geformte ID -> 400 validation_error, Python nicht erreicht.
func TestBriefingTestAlert_UngueltigeID_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, id := range vbInvalidIDs {
		vbAssertIDReachesValidation(t, env, id, "alice")
		py.reset()
		w := env.do(t, "POST", bsPath+id+"/test-alert?kind=route", "alice", "")
		if w.Code != http.StatusBadRequest {
			t.Errorf("ID %q: Status %d, erwartet 400 (body=%q)", id, w.Code, w.Body.String())
			continue
		}
		bsAssertSendError(t, w, "validation_error")
		if py.count() != 0 {
			t.Errorf("ID %q: Python-Core erreicht", id)
		}
	}
}

// AC-13: ohne Session 401 statt Default-Nutzer; Python nicht erreicht.
func TestBriefingTestAlert_OhneSession_401(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	w := env.do(t, "POST", taPfad+"?kind=route&user_id=alice", "", "")
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("Status %d, erwartet 401 (body=%q)", w.Code, w.Body.String())
	}
	if py.count() != 0 {
		t.Errorf("Python-Core ohne Session %d-mal erreicht", py.count())
	}
}

// AC-13: zwei Nutzer — user_id kommt aus der Anmeldung, ein Client-Wert (user_id, Empfaenger)
// wird verworfen; Weiterleitung an Python POST /api/briefings/{id}/test-alert mit kind.
func TestBriefingTestAlert_ZweiNutzer_UserIDAusAuthKontext(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice", "bob")

	for _, kind := range []string{"route", "vergleich"} {
		for _, wer := range []string{"alice", "bob"} {
			py.reset()
			w := env.do(t, "POST", taPfad+"?kind="+kind+"&user_id=alice&to=fremd@example.com", wer, "")
			if w.Code != 200 {
				t.Fatalf("%s/%s: Status %d (body=%q)", kind, wer, w.Code, w.Body.String())
			}
			call, ok := py.last()
			if !ok {
				t.Fatalf("%s/%s: Python-Core nicht erreicht", kind, wer)
			}
			if call.Method != http.MethodPost || call.Path != taPfad {
				t.Errorf("Upstream %s %q, erwartet POST %s", call.Method, call.Path, taPfad)
			}
			if call.Query.Get("kind") != kind {
				t.Errorf("Upstream-kind %q, erwartet %q", call.Query.Get("kind"), kind)
			}
			vbAssertSingleUserID(t, call, wer)
			if call.Query.Has("to") {
				t.Errorf("Client-Empfaengerwert an Python durchgereicht: %v", call.Query)
			}
		}
	}
}

// AC-9: Fehler des Python-Core (fremde ID 404, leere Kanalmenge, Kontingent) gehen 1:1 durch.
func TestBriefingTestAlert_PythonFehlerWerdenDurchgereicht(t *testing.T) {
	var next struct {
		status int
		body   string
	}
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return next.status, "application/json", next.body
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, a := range []struct {
		status int
		body   string
	}{
		{200, `{"sent_channels":["email"],"skipped_channels":[],"failed_channels":[]}`},
		{404, `{"detail":"Nicht gefunden.","code":"not_found"}`},
		{422, `{"detail":"Kein Alarm-Kanal.","code":"keine_alarm_kanaele"}`},
		{429, `{"detail":"Kontingent erschoepft.","code":"kontingent_erschoepft"}`},
	} {
		next.status, next.body = a.status, a.body
		w := env.do(t, "POST", taPfad+"?kind=vergleich", "alice", "")
		if w.Code != a.status || w.Body.String() != a.body {
			t.Errorf("Client %d %q, erwartet 1:1 %d %q", w.Code, w.Body.String(), a.status, a.body)
		}
	}
}
