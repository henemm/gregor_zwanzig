package handler

// TDD RED — Issue #2130: /api/health muss die effektive Passkey-RP-ID ausweisen.
// Spec: docs/specs/modules/passkey_rp_konfiguration.md (Abschnitt 3, Grundlage für AC-4)
//
// Diese Tests kompilieren NICHT gegen die aktuelle HealthHandler-Signatur
// (2 Parameter: pythonURL, gitCommit). RED-Zustand: Kompilierfehler.
// GREEN: HealthHandler nimmt einen dritten Parameter rpID string und schreibt
// ihn als Feld "webauthn_rpid" ins JSON.
//
// Vorbild: health_commit_test.go (nebenan, Issue #688).

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
)

// Der Selbsttest kann eine Fehlkonfiguration nur erkennen, wenn der Wert
// überhaupt herausgereicht wird — und zwar der injizierte, nicht ein Literal.
func TestHealthHandlerReturnsWebauthnRPIDField(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	const testRPID = "gregor20.henemm.com"
	h := HealthHandler(py.URL, "abc1234def5678", testRPID)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("erwartet 200, bekommen %d", w.Code)
	}

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("ungültiges JSON: %v", err)
	}

	if body["webauthn_rpid"] == nil {
		t.Fatal("Feld webauthn_rpid fehlt in der /api/health-Antwort")
	}
	if body["webauthn_rpid"] != testRPID {
		t.Errorf("erwartet webauthn_rpid=%q, bekommen %v", testRPID, body["webauthn_rpid"])
	}
	// Regressions-Anker: das bestehende commit-Feld darf nicht verschwinden.
	if body["commit"] != "abc1234def5678" {
		t.Errorf("commit-Feld verändert: %v", body["commit"])
	}
}

// Der Wert wird durchgereicht, nicht abgeleitet oder überschrieben: ein
// abweichender Eingabewert muss auch abweichend herauskommen.
func TestHealthHandlerWebauthnRPIDIsInjectedNotHardcoded(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	const testRPID = "staging.gregor20.henemm.com"
	h := HealthHandler(py.URL, "deadbeef", testRPID)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("ungültiges JSON: %v", err)
	}
	if body["webauthn_rpid"] != testRPID {
		t.Errorf("erwartet webauthn_rpid=%q, bekommen %v", testRPID, body["webauthn_rpid"])
	}
}

// Auch bei status=degraded (Python-Core nicht erreichbar) muss das Feld da sein —
// sonst könnte der Selbsttest die Fehlkonfiguration ausgerechnet dann nicht
// sehen, wenn ohnehin etwas klemmt.
func TestHealthHandlerWebauthnRPIDPresentWhenPythonDown(t *testing.T) {
	const testRPID = "gregor20.henemm.com"
	h := HealthHandler("http://127.0.0.1:19999", "deadbeef", testRPID)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("ungültiges JSON: %v", err)
	}
	if body["webauthn_rpid"] != testRPID {
		t.Errorf("webauthn_rpid muss auch bei status=degraded vorhanden sein, bekommen %v", body["webauthn_rpid"])
	}
	if body["status"] != "degraded" {
		t.Errorf("status muss degraded sein wenn Python down, bekommen %v", body["status"])
	}
}
