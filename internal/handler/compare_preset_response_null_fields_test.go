package handler

// Issue #1244 Fix-Loop (F001 — Adversary BROKEN-Verdict): CreateComparePresetHandler
// schreibt writeJSON(..., preset) auf die lokale Kopie, bevor SaveComparePresets
// die im Store gehaltene Slice-Kopie normalisiert — die Response enthielt
// deshalb weiterhin "corridors":null. Prüft den tatsächlichen HTTP-Response-
// Body, nicht nur die geschriebene Datei.
//
// Spec: docs/specs/modules/fix_1244_null_list_fields.md
// Keine Mocks — echter httptest-Handler.

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCreateComparePresetHandler_ResponseHasEmptyCorridorsNotNull(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":         "Preset ohne Korridore",
		"location_ids": []string{"loc-1"},
		"schedule":     "manual",
		"profil":       "ALLGEMEIN",
		"hour_from":    6,
		"hour_to":      18,
		"empfaenger":   []string{"gregor-test@henemm.com"},
		// "corridors" absichtlich nicht gesetzt -> nil nach Decode.
	}
	b, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	h := CreateComparePresetHandler(s)
	req := httptest.NewRequest("POST", "/api/compare/presets", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	raw := w.Body.String()
	if strings.Contains(raw, `"corridors":null`) {
		t.Errorf("F001: response enthält \"corridors\":null, war: %s", raw)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if _, ok := resp["corridors"].([]interface{}); !ok {
		t.Errorf("F001: response.corridors ist keine Liste, war: %v", resp["corridors"])
	}
}
