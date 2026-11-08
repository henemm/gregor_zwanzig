package handler

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
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

var nonAlphaNum = regexp.MustCompile(`[^a-z0-9]+`)

func toKebab(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	s = nonAlphaNum.ReplaceAllString(s, "-")
	s = strings.Trim(s, "-")
	return s
}

func LocationsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		locations, err := s.LoadLocations()
		if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(locations)
	}
}

func validateLocation(loc model.Location) error {
	if loc.ID == "" {
		return fmt.Errorf("id required")
	}
	// Issue #2140 Scheibe 2: die Kennung landet ueber SaveLocation in einem
	// Dateipfad — ein Trenner darin bricht aus dem Nutzerverzeichnis aus.
	if !store.ValidEntityID(loc.ID) {
		return fmt.Errorf("invalid id")
	}
	if loc.Name == "" {
		return fmt.Errorf("name required")
	}
	if loc.Lat == 0 && loc.Lon == 0 {
		return fmt.Errorf("coordinates required")
	}
	return nil
}

func CreateLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		var loc model.Location
		if err := json.NewDecoder(r.Body).Decode(&loc); err != nil {
			WriteError(w, r, 400, "bad_request", nil)
			return
		}

		// Auto-generate ID from name if not provided
		if loc.ID == "" && loc.Name != "" {
			loc.ID = toKebab(loc.Name)
		}

		if err := validateLocation(loc); err != nil {
			WriteError(w, r, 400, "validation_error", i18n.Args{"detail": err.Error()})
			return
		}

		// Issue #1082: bestehende Location unter derselben (Auto-)ID nicht
		// still überschreiben. Existenzprüfung ist user-scoped (s bereits
		// per WithUser gebunden) — keine Cross-User-Kollision.
		existing, err := s.LoadLocation(loc.ID)
		if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}
		if existing != nil {
			WriteError(w, r, 409, "conflict", nil)
			return
		}

		now := time.Now().UTC()
		loc.CreatedAt = &now

		// Issue #2482: Mengen-Quote — Validierung und Dubletten-409 (conflict)
		// oben haben Vorrang; Orte zaehlen alle (kein Archiv).
		defer s.LockQuota()()
		if !quotaAllows(w, r, s, quotaLocations) {
			return
		}

		if err := s.SaveLocation(loc); err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(loc)
	}
}

func UpdateLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		if rejectInvalidEntityID(w, r, id) {
			return
		}

		defer s.LockLocation(id)() // #2158
		existing, err := s.LoadLocation(id)
		if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}
		if existing == nil {
			WriteError(w, r, 404, "not_found", nil)
			return
		}

		var loc model.Location
		if err := json.NewDecoder(r.Body).Decode(&loc); err != nil {
			WriteError(w, r, 400, "bad_request", nil)
			return
		}

		loc.ID = id
		loc.CreatedAt = existing.CreatedAt

		if err := validateLocation(loc); err != nil {
			WriteError(w, r, 400, "validation_error", i18n.Args{"detail": err.Error()})
			return
		}

		if err := s.SaveLocation(loc); err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc)
	}
}

// PatchLocationHandler — PATCH /api/locations/{id}. Partial merge of present
// keys (at least group_id). 404 if location missing. All other fields
// (CreatedAt, ActivityProfile, …) are preserved. Issue #341 §6.
func PatchLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		if rejectInvalidEntityID(w, r, id) {
			return
		}

		defer s.LockLocation(id)() // #2158
		existing, err := s.LoadLocation(id)
		if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}
		if existing == nil {
			WriteError(w, r, 404, "not_found", nil)
			return
		}

		var patch map[string]json.RawMessage
		if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
			WriteError(w, r, 400, "bad_request", nil)
			return
		}

		if raw, ok := patch["group_id"]; ok {
			var v *string
			if err := json.Unmarshal(raw, &v); err != nil {
				WriteError(w, r, 400, "bad_request", nil)
				return
			}
			existing.GroupID = v
		}

		// Issue #1398: Kennung auf den URL-Parameter setzen, exakt wie
		// UpdateLocationHandler. SaveLocation schreibt nach loc.ID — weicht die
		// INNERE Kennung vom Dateinamen ab, landete die Aenderung sonst in
		// einem FREMDEN Ort, waehrend der angefragte unveraendert blieb. Der
		// Nutzer bekam trotzdem 200.
		existing.ID = id
		if err := s.SaveLocation(*existing); err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(existing)
	}
}

func LocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		if rejectInvalidEntityID(w, r, id) {
			return
		}
		loc, err := s.LoadLocation(id)
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		if loc == nil {
			WriteError(w, r, http.StatusNotFound, "not_found", nil)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc)
	}
}

func DeleteLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		if rejectInvalidEntityID(w, r, id) {
			return
		}

		defer s.LockLocation(id)() // #2158

		// #2815: Existenz-Check VOR der Nutzungspruefung (unbekannt -> 404,
		// nicht 409). Ein Ladefehler (kaputte Datei) faellt durch: loeschbar.
		if loc, lerr := s.LoadLocation(id); lerr == nil && loc == nil {
			WriteError(w, r, 404, "not_found", nil)
			return
		}

		// #2216: Ort in einem Ortsvergleich -> nicht loeschen, Namen melden.
		used, err := s.ComparePresetsUsingLocation(id)
		if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}
		if len(used) > 0 {
			type ref struct {
				ID   string `json:"id"`
				Name string `json:"name"`
			}
			refs := make([]ref, 0, len(used))
			for _, p := range used {
				refs = append(refs, ref{ID: p.ID, Name: p.Name})
			}
			WriteErrorWith(w, r, 409, "location_in_use", nil, map[string]any{"compare_presets": refs})
			return
		}

		if err := s.DeleteLocation(id); errors.Is(err, store.ErrNotFound) {
			WriteError(w, r, 404, "not_found", nil)
			return
		} else if err != nil {
			WriteError(w, r, 500, "store_error", nil)
			return
		}

		w.WriteHeader(204)
	}
}
