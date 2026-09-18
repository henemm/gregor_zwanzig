package handler

// TDD RED: Issue #2285 AC-3 + AC-7 (Dach-Epic #1374)
//
// Spec: docs/specs/modules/fix_2285_compare_put_merge_kernel.md
//
// AC-3: Faelschungsschutz der acht Server-Felder (id, user_id, created_at,
// letzter_versand, top_ort_letzter_versand, paused_at, archived_at, kind)
// ueber BEIDE Compare-PUT-Wege. Heutiger Stand: UpdateComparePresetHandler
// restauriert weder archived_at noch kind -- ein PUT mit gefaelschtem
// archived_at im Body wird uebernommen (RED).
//
// AC-7: Mandantentrennung -- zwei Nutzer A/B mit Vergleich gleicher ID, PUT
// nur fuer A, Bs Datei muss byte-identisch bleiben.
//
// Ausfuehrung:
//   go test ./internal/handler/... -run TestComparePresetPutServerFields -v

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// comparePresetServerFieldsFakeBody ist ein vollstaendiger, valider PUT-
// Rumpf, der zusaetzlich alle acht Server-Felder mit gefaelschten Werten
// mitschickt.
const comparePresetServerFieldsFakeBody = `{
	"name": "Preset (Faelschungsversuch)",
	"location_ids": ["loc-x"],
	"schedule": "manual",
	"profil": "ALLGEMEIN",
	"hour_from": 6,
	"hour_to": 18,
	"empfaenger": ["a@example.com"],
	"id": "evil-id",
	"user_id": "evil-user",
	"created_at": "1999-01-01T00:00:00Z",
	"letzter_versand": "1999-01-01T00:00:00Z",
	"top_ort_letzter_versand": "evil-ort",
	"paused_at": "1999-01-01T00:00:00Z",
	"archived_at": "1999-01-01T00:00:00Z",
	"kind": "route"
}`

// comparePresetPutBodyStruct liefert ein valides Basis-Preset zum direkten
// Seeden ueber den Store (umgeht die Handler-Validierung bewusst, analog
// comparePresetPutBody fuer den HTTP-Body).
func comparePresetPutBodyStruct(id, userID string) model.ComparePreset {
	return model.ComparePreset{
		ID:            id,
		Name:          "Server-Feld-Test",
		UserID:        userID,
		LocationIDs:   []string{"loc-1", "loc-2"},
		Schedule:      "daily",
		Profil:        "ALLGEMEIN",
		HourFrom:      6,
		HourTo:        18,
		ForecastHours: 48,
		Empfaenger:    []string{"test@example.com"},
	}
}

func TestComparePresetPutServerFields_ForgeryProtection_BothPaths(t *testing.T) {
	for _, tc := range []struct {
		name string
		path string
	}{
		{"ComparePresetDirectPUT", "/api/compare/presets/"},
		{"BriefingVergleichPUT", "/api/briefings/"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := newTestStore(t)
			id := "cp-ac3-" + tc.name
			fixed := time.Date(2025, 3, 4, 5, 6, 7, 0, time.UTC)
			letzterVersand := fixed
			topOrt := "Original-Ort"
			archivedAt := fixed
			pausedAt := fixed
			preset := comparePresetPutBodyStruct(id, "test")
			// schedule=manual ist Voraussetzung dafuer, dass NormalizeComparePreset
			// (in SaveComparePreset) das explizit gesetzte PausedAt NICHT wieder
			// auf nil zurueckschneidet ("if p.Schedule != \"manual\" { PausedAt = nil }").
			preset.Schedule = "manual"
			preset.CreatedAt = fixed
			preset.LetzterVersand = &letzterVersand
			preset.TopOrtLetzterVersand = &topOrt
			preset.ArchivedAt = &archivedAt
			preset.PausedAt = &pausedAt
			if err := s.SaveComparePreset(preset); err != nil {
				t.Fatalf("seed SaveComparePreset: %v", err)
			}
			seeded := loadPresetOrFail(t, s, id)
			if seeded.PausedAt == nil {
				t.Fatalf("Seed-Voraussetzung verletzt: paused_at ist nil nach dem Seed")
			}

			r := briefingVergleichEtagRouter(s)
			path := tc.path + id
			if tc.name == "BriefingVergleichPUT" {
				path += "?kind=vergleich"
			}
			w := doReq(r, http.MethodPut, path, comparePresetServerFieldsFakeBody, "", "test")
			if w.Code != http.StatusOK {
				t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
			}

			after := loadPresetOrFail(t, s, id)
			// Schreib-Ziel-Nachweis: ein gefaelschtes "id" im Body, das
			// UNGEPRUEFT durchrutscht, wuerde SaveComparePreset dazu bringen,
			// eine ANDERE Datei (briefings/evil-id.json) zu schreiben --
			// briefings/<id>.json bliebe dann unveraendert und "after" waere
			// schlicht der Alt-Stand. Die name-Aenderung aus dem Faelschungs-
			// Body beweist, dass wirklich DIESE Datei beschrieben wurde,
			// bevor die eigentlichen Server-Feld-Pruefungen ueberhaupt Sinn
			// ergeben (Fatalf, nicht Errorf: sonst liefen alle folgenden
			// Assertions gegen Alt-Daten und waeren bedeutungslos-gruen).
			if after.Name != "Preset (Faelschungsversuch)" {
				t.Fatalf("PUT hat nicht in briefings/%s.json geschrieben (name=%q) -- Pruefungen liefen sonst gegen den Alt-Stand", id, after.Name)
			}
			if after.ID != id {
				t.Errorf("id gefaelscht uebernommen: got %q, want %q", after.ID, id)
			}
			if after.UserID != "test" {
				t.Errorf("user_id gefaelscht uebernommen: got %q, want %q", after.UserID, "test")
			}
			if !after.CreatedAt.Equal(fixed) {
				t.Errorf("created_at gefaelscht uebernommen: got %v, want %v", after.CreatedAt, fixed)
			}
			if after.LetzterVersand == nil || !after.LetzterVersand.Equal(fixed) {
				t.Errorf("letzter_versand gefaelscht uebernommen: got %v, want %v", after.LetzterVersand, fixed)
			}
			if after.TopOrtLetzterVersand == nil || *after.TopOrtLetzterVersand != topOrt {
				t.Errorf("top_ort_letzter_versand gefaelscht uebernommen: got %v, want %q", after.TopOrtLetzterVersand, topOrt)
			}
			if after.PausedAt == nil || !after.PausedAt.Equal(*seeded.PausedAt) {
				t.Errorf("paused_at gefaelscht uebernommen: got %v, want %v", after.PausedAt, seeded.PausedAt)
			}
			if after.ArchivedAt == nil || !after.ArchivedAt.Equal(archivedAt) {
				t.Errorf("archived_at gefaelscht uebernommen: got %v, want %v", after.ArchivedAt, archivedAt)
			}
			// kind auf DATEI-Ebene ist KEINE aussagekraeftige Pruefstelle:
			// store.SaveComparePreset erzwingt p.Kind="vergleich" unbedingt
			// (auf einer eigenen Kopie), unabhaengig davon, ob der Handler es
			// vorher restauriert -- die Datei zeigt "vergleich" selbst dann,
			// wenn die Restauration im Handler fehlt. Die Zusicherung wirkt
			// im Response-Body (VOR dem erzwungenen Store-Overwrite), also
			// wird dort geprueft.
			var responseBody struct {
				Kind string `json:"kind"`
			}
			if err := json.Unmarshal(w.Body.Bytes(), &responseBody); err != nil {
				t.Fatalf("Response-Body dekodieren: %v (%s)", err, w.Body.String())
			}
			if responseBody.Kind != "vergleich" {
				t.Errorf("kind gefaelscht uebernommen (Response-Body): got %q, want %q", responseBody.Kind, "vergleich")
			}
		})
	}
}

func TestComparePresetPutServerFields_TenantIsolation(t *testing.T) {
	s := newTestStore(t)
	id := "cp-ac7-shared-id"
	sA := s.WithUser("usera")
	sB := s.WithUser("userb")

	if err := sA.SaveComparePreset(comparePresetPutBodyStruct(id, "usera")); err != nil {
		t.Fatalf("seed A: %v", err)
	}
	if err := sB.SaveComparePreset(comparePresetPutBodyStruct(id, "userb")); err != nil {
		t.Fatalf("seed B: %v", err)
	}

	pathB := filepath.Join(sB.BriefingsDir(), id+".json")
	before, err := os.ReadFile(pathB)
	if err != nil {
		t.Fatalf("Bs Datei vor dem PUT lesen: %v", err)
	}

	r := briefingVergleichEtagRouter(s)
	// Voller, valider Rumpf (nicht der minimale {"name":...}) -- Mandanten-
	// trennung muss unabhaengig vom Merge-Kernel-Umbau bereits heute gelten;
	// ein minimaler Body wuerde am heutigen Voll-Decode-Compare-PUT (fehlende
	// Pflichtfelder) mit 400 scheitern, bevor die eigentliche Zusicherung
	// (Bs Datei bleibt unberuehrt) ueberhaupt geprueft wird.
	w := doReq(r, http.MethodPut, "/api/compare/presets/"+id, comparePresetPutBody("A hat geaendert"), "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	after, err := os.ReadFile(pathB)
	if err != nil {
		t.Fatalf("Bs Datei nach dem PUT lesen: %v", err)
	}
	if string(before) != string(after) {
		t.Errorf("Bs Datei hat sich durch As PUT veraendert (Mandantentrennung verletzt).\nvorher:  %s\nnachher: %s", before, after)
	}
}
