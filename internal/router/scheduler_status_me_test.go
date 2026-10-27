package router

// TDD RED — Issue #2155 Scheibe S2 (Admin-Rolle), AC-4, AC-5.
//
// Spec: docs/specs/modules/admin_rolle_s2_status_token.md
//
// GET /api/scheduler/status/me liefert der angemeldeten Person NUR ihren
// eigenen Laufzustand des Jobs trip_reports_hourly. Der Pro-Nutzer-Zustand
// wird als echte scheduler_user_state.json VOR scheduler.New abgelegt (der
// Scheduler laedt sie beim Start) — kein Mock des Scheduler-Zustands.
//
// Belegung:
//   alice: trip_reports_hourly, Fehler "alice-fehler"
//   carol: trip_reports_hourly, Fehler "carol-geheim"  (Querleck-Nachweis)
//   bob:   KEIN trip_reports_hourly-Eintrag, aber alert_checks-Fehler
//          "bob-alert-fehler" (der Getter muss auch nach jobID filtern)
//
// Der globale Fan-out-Fehlertext (s.lastRuns) laesst sich aus dem
// Router-Paket nicht setzen — diese Zusicherung bewacht
// internal/scheduler/status_for_user_test.go.
//
// RED-Signal heute: die Route existiert nicht (404 statt 200).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func s2UserState() map[string]map[string]map[string]any {
	return map[string]map[string]map[string]any{
		"trip_reports_hourly": {
			"alice": {
				"last_run":             "2026-09-27T10:00:00Z",
				"last_status":          "error",
				"last_error":           "alice-fehler",
				"consecutive_failures": 1,
			},
			"carol": {
				"last_run":            "2026-09-27T11:00:00Z",
				"last_status":         "partial",
				"last_error":          "carol-geheim",
				"consecutive_partial": 1,
			},
		},
		"alert_checks": {
			"bob": {
				"last_run":             "2026-09-27T12:00:00Z",
				"last_status":          "error",
				"last_error":           "bob-alert-fehler",
				"consecutive_failures": 1,
			},
		},
	}
}

func meAbruf(t *testing.T, r http.Handler, secret, userID string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status/me", nil)
	if userID != "" {
		req.AddCookie(sessionCookieFor(userID, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// meJob dekodiert die /me-Antwort und verlangt genau einen Job
// trip_reports_hourly; Rueckgabe roh je Feld (null vs. fehlend unterscheidbar).
func meJob(t *testing.T, who string, w *httptest.ResponseRecorder) map[string]json.RawMessage {
	t.Helper()
	if w.Code != http.StatusOK {
		t.Fatalf("%s GET /api/scheduler/status/me: erwartet 200, bekommen %d: %s", who, w.Code, w.Body.String())
	}
	var body struct {
		Jobs []map[string]json.RawMessage `json:"jobs"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("%s: Antwort ist kein JSON: %v — %s", who, err, w.Body.String())
	}
	if len(body.Jobs) != 1 {
		t.Fatalf("%s: erwartet genau 1 Job, bekommen %d: %s", who, len(body.Jobs), w.Body.String())
	}
	job := body.Jobs[0]
	var id string
	_ = json.Unmarshal(job["id"], &id)
	if id != "trip_reports_hourly" {
		t.Fatalf("%s: Job-id erwartet trip_reports_hourly, bekommen %q", who, id)
	}
	return job
}

// nextRunAusVollstatus liest next_run von trip_reports_hourly aus dem
// vollen Status (per Token) — /me muss denselben Wert liefern (kein zweiter
// Ermittlungsweg).
func nextRunAusVollstatus(t *testing.T, r http.Handler, secret string) string {
	t.Helper()
	w := statusAbruf(t, r, secret, str(s2Token), "")
	if w.Code != http.StatusOK {
		t.Fatalf("voller Status mit Token: erwartet 200, bekommen %d", w.Code)
	}
	var body struct {
		Jobs []struct {
			ID      string `json:"id"`
			NextRun string `json:"next_run"`
		} `json:"jobs"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("voller Status kein JSON: %v", err)
	}
	for _, j := range body.Jobs {
		if j.ID == "trip_reports_hourly" {
			return j.NextRun
		}
	}
	t.Fatalf("voller Status enthaelt keinen Job trip_reports_hourly: %s", w.Body.String())
	return ""
}

// AC-4: Zwei-Nutzer-Test — alice sieht nur ihren eigenen Lauf, bob bekommt
// last_run: null, keine Antwort traegt Daten eines anderen Nutzers.
func TestStatusMe_OnlyOwnRunState_TwoUsers(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, userState: s2UserState()})
	nextRun := nextRunAusVollstatus(t, r, secret)

	// alice
	wa := meAbruf(t, r, secret, "alice")
	jobA := meJob(t, "alice", wa)
	var lrA *struct {
		Time   string `json:"time"`
		Status string `json:"status"`
		Error  string `json:"error"`
	}
	if err := json.Unmarshal(jobA["last_run"], &lrA); err != nil || lrA == nil {
		t.Fatalf("alice: last_run muss ein Objekt sein, bekommen %s", string(jobA["last_run"]))
	}
	if lrA.Status != "error" {
		t.Errorf("alice: last_run.status erwartet %q, bekommen %q", "error", lrA.Status)
	}
	if lrA.Error != "alice-fehler" {
		t.Errorf("alice: last_run.error erwartet %q (eigener Fehlertext), bekommen %q", "alice-fehler", lrA.Error)
	}
	if lrA.Time == "" {
		t.Errorf("alice: last_run.time darf nicht leer sein")
	}
	var nrA string
	_ = json.Unmarshal(jobA["next_run"], &nrA)
	if nrA != nextRun {
		t.Errorf("alice: next_run erwartet %q (wie im vollen Status), bekommen %q", nextRun, nrA)
	}

	// bob — kein trip_reports_hourly-Eintrag => Schluessel vorhanden, Wert null.
	wb := meAbruf(t, r, secret, "bob")
	jobB := meJob(t, "bob", wb)
	raw, ok := jobB["last_run"]
	if !ok {
		t.Errorf("bob: Feld last_run muss vorhanden sein (Wert null), fehlt: %s", wb.Body.String())
	} else if strings.TrimSpace(string(raw)) != "null" {
		t.Errorf("bob: last_run erwartet null, bekommen %s", string(raw))
	}

	// Querleck: keine Antwort nennt fremde Fehlertexte oder Nutzerkennungen.
	for who, body := range map[string]string{"alice": wa.Body.String(), "bob": wb.Body.String()} {
		for _, fremd := range []string{"carol-geheim", "carol", "bob-alert-fehler"} {
			if strings.Contains(body, fremd) {
				t.Errorf("%s: /me-Antwort enthaelt fremde Angabe %q: %s", who, fremd, body)
			}
		}
		if who == "bob" && strings.Contains(body, "alice") {
			t.Errorf("bob: /me-Antwort enthaelt alice-Daten: %s", body)
		}
		for _, aggregat := range []string{`"users"`, `"failing"`, `"total"`} {
			if strings.Contains(body, aggregat) {
				t.Errorf("%s: /me-Antwort darf kein Nutzer-Aggregat %s tragen: %s", who, aggregat, body)
			}
		}
	}
}

// AC-5: ohne Sitzung 401 — gekoppelt mit "mit Sitzung 200", damit der Test
// die ROUTE bewacht und nicht nur die (heute schon greifende) Anmeldepflicht.
func TestStatusMe_NoSession_401_WithSession_200(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, userState: s2UserState()})

	if w := meAbruf(t, r, secret, ""); w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Sitzung: erwartet 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	if w := meAbruf(t, r, secret, "alice"); w.Code != http.StatusOK {
		t.Errorf("mit Sitzung: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// /me braucht KEIN Maschinen-Token und laesst sich durch ein Token auch
// nicht ohne Sitzung oeffnen (Token-Waechter haengt nur an /status).
func TestStatusMe_TokenDoesNotReplaceSession(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token, userState: s2UserState()})

	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status/me", nil)
	req.Header.Set("X-GZ-Status-Token", s2Token)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("/me nur mit Token, ohne Sitzung: erwartet 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	_ = secret
}
