package handler

// Epic #138 Issue #177 — User-MetricPreset-Endpoints.
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §7
//
// Issue #342: Schema-Erweiterung um []DisplayMetric mit horizons + PATCH-Endpoint.
// Spec: docs/specs/modules/issue_342_pro_metrik_horizon_backend.md §4–§5

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1396 S1: ":=" statt "=" beim WithUser-Aufruf — Begruendung
// ausfuehrlich in trip.go:10-28 (Kommentar ueber TripsHandler).

// createPresetRequest akzeptiert sowohl Legacy- (Metrics []string +
// FriendlyIDs []string) als auch Neu-Schema-Payloads (Metrics []DisplayMetric).
// Beide werden via json.RawMessage entgegengenommen und in
// CreateMetricPresetHandler in die kanonische []DisplayMetric-Form normalisiert.
type createPresetRequest struct {
	Name        string          `json:"name"`
	Description string          `json:"description,omitempty"`
	IsDefault   bool            `json:"is_default"`
	Metrics     json.RawMessage `json:"metrics"`
	FriendlyIDs []string        `json:"friendly_ids"`
	// Issue #2792 S1a: Profil-Ampel samt alarm_ab (optional).
	Ampel map[string]interface{} `json:"ampel,omitempty"`
	// Issue #2794 S3a: Art route|vergleich, fehlend = route.
	Kind string `json:"kind,omitempty"`
}

// systemVorlagenNamen sind die Namen der 7 Systemvorlagen (Python-SSOT
// src/app/metric_catalog.py WEATHER_TEMPLATES "label"; kleingeschrieben
// zugleich die Vorlagen-IDs). Eigene Vorlagen duerfen keinen davon tragen
// (Issue #2794 S3a, AC-23).
var systemVorlagenNamen = []string{
	"Alpen-Trekking", "Wandern", "Skitouren", "Wintersport", "Radtour", "Wassersport", "Allgemein",
}

// presetNameVergeben prueft name (getrimmt, ohne Gross-/Kleinschreibung)
// gegen die Systemvorlagen und die eigenen Vorlagen derselben Art; skip ist
// der Index der gerade umbenannten Vorlage (-1 beim Anlegen).
func presetNameVergeben(presets []model.MetricPreset, name, kind string, skip int) bool {
	n := strings.ToLower(strings.TrimSpace(name))
	for _, sys := range systemVorlagenNamen {
		if strings.ToLower(sys) == n {
			return true
		}
	}
	for i, p := range presets {
		if i != skip && p.Kind == kind && strings.ToLower(strings.TrimSpace(p.Name)) == n {
			return true
		}
	}
	return false
}

func writeNameExists(w http.ResponseWriter, r *http.Request, name string) {
	WriteError(w, r, http.StatusConflict, "name_exists", i18n.Args{"variante": "vorlage", "name": name})
}

// standardVorlage liefert die Standardvorlage („Als Standard fuer neue") der
// Art kind des Nutzers von s (per WithUser aus dem Auth-Kontext gebunden),
// nil wenn keine gesetzt ist (Issue #2794 S3a, AC-25).
func standardVorlage(s *store.Store, kind string) (*model.MetricPreset, error) {
	// gz-store-scope-call: Hilfsfunktion, jeder Aufrufer reicht seinen bereits per WithUser gebundenen Store durch
	presets, err := s.LoadMetricPresets()
	if err != nil {
		return nil, err
	}
	for i := range presets {
		if presets[i].IsDefault && presets[i].Kind == kind {
			return &presets[i], nil
		}
	}
	return nil, nil
}

// displayConfigAusVorlage baut die display_config einer Neuanlage aus der
// Standardvorlage (Issue #2794 S3a, AC-25): Ampel samt alarm_ab und, beim
// Trip (mitMetriken), die Metrik-Auswahl. nil-Vorlage -> nil (Bestandsverhalten:
// Python leitet dann die Vorbelegung aus dem Profil ab). Der Vergleich fuehrt
// seine Auswahl in einem eigenen Schluesselraum (active_metrics), daher dort
// nur die Ampel (ampel.metrics.<id>.enabled traegt die Auswahl der Ampel).
func displayConfigAusVorlage(p *model.MetricPreset, mitMetriken bool) map[string]interface{} {
	if p == nil {
		return nil
	}
	dc := map[string]interface{}{}
	if mitMetriken {
		metrics := make([]interface{}, 0, len(p.Metrics))
		for _, m := range p.Metrics {
			metrics = append(metrics, map[string]interface{}{
				"metric_id": m.MetricID, "enabled": m.Enabled, "use_friendly_format": m.UseFriendlyFormat,
			})
		}
		dc["metrics"] = metrics
	}
	if p.Ampel != nil {
		dc["ampel"] = p.Ampel
	}
	if len(dc) == 0 {
		return nil
	}
	return dc
}

// standardExklusiv nimmt das Standard-Flag allen anderen Vorlagen derselben
// Art (Issue #2794 S3a, AC-25: exklusiv je Art).
func standardExklusiv(presets []model.MetricPreset, keep int, kind string) {
	for i := range presets {
		if i != keep && presets[i].Kind == kind {
			presets[i].IsDefault = false
		}
	}
}

func newPresetID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		// Fallback auf nanosekunden-basierte ID
		return "p-" + time.Now().UTC().Format("20060102150405.000000000")
	}
	return "p-" + hex.EncodeToString(b)
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// normalizeMetricsPayload akzeptiert beide Eingabe-Formen (Legacy []string +
// friendly_ids ODER Neu []DisplayMetric) und liefert die kanonische
// []DisplayMetric-Form. Fehlende horizons-Felder werden auf {true,true,true}
// defaultet (Backward-Compat, Spec §3).
func normalizeMetricsPayload(raw json.RawMessage, friendlyIDs []string) []model.DisplayMetric {
	allTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}
	out := []model.DisplayMetric{}
	if len(raw) == 0 {
		return out
	}

	// Erst []DisplayMetric direkt versuchen (Neu-Schema).
	// Bug #349: Lokaler Decode-Struct mit *Horizons unterscheidet sicher
	// zwischen "Feld fehlt im JSON" (nil) und "explizit {false,false,false}".
	type displayMetricInput struct {
		MetricID          string          `json:"metric_id"`
		Enabled           bool            `json:"enabled"`
		UseFriendlyFormat bool            `json:"use_friendly_format"`
		Horizons          *model.Horizons `json:"horizons"`
	}
	var asInputs []displayMetricInput
	if err := json.Unmarshal(raw, &asInputs); err == nil && len(asInputs) > 0 {
		// Erkennen, ob mindestens ein metric_id gesetzt ist – sonst ist es
		// vermutlich Legacy []string und wir landen unten im Fallback.
		anyID := false
		for _, m := range asInputs {
			if m.MetricID != "" {
				anyID = true
				break
			}
		}
		if anyID {
			asStructs := make([]model.DisplayMetric, len(asInputs))
			for i, in := range asInputs {
				asStructs[i] = model.DisplayMetric{
					MetricID:          in.MetricID,
					Enabled:           in.Enabled,
					UseFriendlyFormat: in.UseFriendlyFormat,
				}
				if in.Horizons == nil {
					asStructs[i].Horizons = allTrue
				} else {
					asStructs[i].Horizons = *in.Horizons
				}
			}
			return asStructs
		}
	}

	// Fallback: Legacy []string + friendly_ids.
	friendly := map[string]bool{}
	for _, fid := range friendlyIDs {
		friendly[fid] = true
	}
	var asStrings []string
	if err := json.Unmarshal(raw, &asStrings); err == nil {
		for _, id := range asStrings {
			out = append(out, model.DisplayMetric{
				MetricID:          id,
				Enabled:           true,
				UseFriendlyFormat: friendly[id],
				Horizons:          allTrue,
			})
		}
	}
	return out
}

// GET /api/metric-presets
func ListMetricPresetsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		presets, err := s.LoadMetricPresets()
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		writeJSON(w, http.StatusOK, presets)
	}
}

// POST /api/metric-presets
func CreateMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))

		var req createPresetRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			WriteError(w, r, http.StatusBadRequest, "bad_request", nil)
			return
		}
		name := strings.TrimSpace(req.Name)
		if name == "" {
			WriteError(w, r, http.StatusBadRequest, "name_required", nil)
			return
		}
		kind := req.Kind
		if kind == "" {
			kind = model.PresetKindRoute
		}
		if bailIf(w, r, !model.ValidPresetKind(kind), http.StatusBadRequest, "bad_request") {
			return
		}
		if bailIf(w, r, req.Ampel != nil && !validateAmpel(req.Ampel), http.StatusBadRequest, "ampel_ungueltig") {
			return
		}

		defer s.LockMetricPresets()() // #2158: Lesen+Schreiben unter einer Sperre
		presets, err := s.LoadMetricPresets()
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}

		// Issue #690 / #2794 S3a: Eindeutigkeit je Nutzer und Art sowie gegen
		// die Systemvorlagen (case-insensitive, getrimmt).
		if presetNameVergeben(presets, name, kind, -1) {
			writeNameExists(w, r, name)
			return
		}

		// Wenn IsDefault=true → alle anderen derselben Art auf false (genau ein
		// Default je Art).
		if req.IsDefault {
			standardExklusiv(presets, -1, kind)
		}

		preset := model.MetricPreset{
			ID:          newPresetID(),
			Name:        name,
			Description: req.Description,
			Kind:        kind,
			IsDefault:   req.IsDefault,
			Metrics:     normalizeMetricsPayload(req.Metrics, req.FriendlyIDs),
			CreatedAt:   time.Now().UTC(),
			Ampel:       req.Ampel,
		}
		presets = append(presets, preset)

		if err := s.SaveMetricPresets(presets); err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		writeJSON(w, http.StatusCreated, preset)
	}
}

// DELETE /api/metric-presets/{id}
func DeleteMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		defer s.LockMetricPresets()() // #2158: Lesen+Schreiben unter einer Sperre
		presets, err := s.LoadMetricPresets()
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}

		filtered := make([]model.MetricPreset, 0, len(presets))
		found := false
		for _, p := range presets {
			if p.ID == id {
				found = true
				continue
			}
			filtered = append(filtered, p)
		}
		if !found {
			WriteError(w, r, http.StatusNotFound, "not_found", nil)
			return
		}

		if err := s.SaveMetricPresets(filtered); err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

// PATCH /api/metric-presets/{id} — Read-Modify-Write (Issue #342 §4).
//
// Alle Felder im Payload sind optional; fehlende Felder bleiben unveraendert.
// Wenn is_default=true gesetzt wird, werden alle anderen Presets exklusiv
// auf is_default=false zurueckgesetzt.
func PatchMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		defer s.LockMetricPresets()() // #2158: Lesen+Schreiben unter einer Sperre
		presets, err := s.LoadMetricPresets()
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}

		idx := -1
		for i, p := range presets {
			if p.ID == id {
				idx = i
				break
			}
		}
		if idx < 0 {
			WriteError(w, r, http.StatusNotFound, "not_found", nil)
			return
		}

		var patch struct {
			Name        *string                `json:"name,omitempty"`
			Description *string                `json:"description,omitempty"`
			IsDefault   *bool                  `json:"is_default,omitempty"`
			Metrics     *[]model.DisplayMetric `json:"metrics,omitempty"`
			// Issue #2792 S1a: ganzer Unterbaum (Spec §1), nil = unveraendert.
			Ampel *map[string]interface{} `json:"ampel,omitempty"`
			// Issue #2794 S3a: Art route|vergleich, nil = unveraendert.
			Kind *string `json:"kind,omitempty"`
		}
		if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
			WriteError(w, r, http.StatusBadRequest, "bad_request", nil)
			return
		}
		if bailIf(w, r, patch.Kind != nil && !model.ValidPresetKind(*patch.Kind), http.StatusBadRequest, "bad_request") {
			return
		}
		if bailIf(w, r, patch.Ampel != nil && !validateAmpel(*patch.Ampel), http.StatusBadRequest, "ampel_ungueltig") {
			return
		}

		existing := presets[idx]
		if patch.Kind != nil {
			existing.Kind = *patch.Kind
		}
		if patch.Name != nil {
			name := strings.TrimSpace(*patch.Name)
			if name == "" {
				WriteError(w, r, http.StatusBadRequest, "name_required", nil)
				return
			}
			existing.Name = name
		}
		// Issue #2794 S3a (AC-23/AC-24): Umbenennen und Art-Wechsel pruefen
		// dieselbe Eindeutigkeit wie das Anlegen.
		if (patch.Name != nil || patch.Kind != nil) && presetNameVergeben(presets, existing.Name, existing.Kind, idx) {
			writeNameExists(w, r, existing.Name)
			return
		}
		if patch.Description != nil {
			existing.Description = *patch.Description
		}
		if patch.IsDefault != nil {
			existing.IsDefault = *patch.IsDefault
		}
		if patch.Metrics != nil {
			existing.Metrics = *patch.Metrics
		}
		if patch.Ampel != nil {
			existing.Ampel = *patch.Ampel
		}

		if existing.IsDefault && (patch.IsDefault != nil || patch.Kind != nil) {
			standardExklusiv(presets, idx, existing.Kind)
		}
		presets[idx] = existing

		if err := s.SaveMetricPresets(presets); err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		writeJSON(w, http.StatusOK, existing)
	}
}
