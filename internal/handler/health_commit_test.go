package handler

// TDD RED — Issue #688: /api/health muss commit-Feld zurückgeben.
// Spec: docs/specs/modules/issue_688_health_commit_field.md
//
// Diese Tests kompilieren NICHT gegen die aktuelle HealthHandler-Signatur
// (1 Parameter). RED-Zustand: Kompilierfehler.
// GREEN: HealthHandler nimmt zweiten Parameter gitCommit string.

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
)

// AC-1: GET /api/health liefert commit-Feld mit dem injizierten SHA.
func TestHealthHandlerReturnsCommitField(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	const testCommit = "abc1234def5678"
	h := HealthHandler(py.URL, testCommit)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	if body["commit"] == nil {
		t.Error("AC-1: commit-Feld fehlt in /api/health-Antwort")
	}
	if body["commit"] != testCommit {
		t.Errorf("AC-1: erwartet commit=%q, bekommen %v", testCommit, body["commit"])
	}
}

// AC-1: commit-Feld ist auch dann vorhanden, wenn Python-Core nicht erreichbar ist.
func TestHealthHandlerCommitPresentWhenPythonDown(t *testing.T) {
	const testCommit = "deadbeef12345678"
	h := HealthHandler("http://127.0.0.1:19999", testCommit)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	if body["commit"] != testCommit {
		t.Errorf("AC-1: commit-Feld muss auch bei degraded status vorhanden sein, bekommen %v", body["commit"])
	}
	if body["status"] != "degraded" {
		t.Errorf("status muss degraded sein wenn Python down, bekommen %v", body["status"])
	}
}
