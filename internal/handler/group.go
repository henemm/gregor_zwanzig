package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// GroupsHandler — GET /api/groups → 200, list sorted by order (LoadGroups
// already returns sorted). Issue #341 §5.
func GroupsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		groups, err := s.LoadGroups()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(groups)
	}
}

// CreateGroupHandler — POST /api/groups. ID from toKebab(name) when empty,
// name required, order = max(order)+1 when 0/unset. Issue #341 §5.
func CreateGroupHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		var g model.Group
		if err := json.NewDecoder(r.Body).Decode(&g); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		if g.Name == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": "name required",
			})
			return
		}

		if g.ID == "" {
			g.ID = toKebab(g.Name)
		}

		existing, err := s.LoadGroups()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		if g.Order == 0 {
			maxOrder := -1
			for _, x := range existing {
				if x.Order > maxOrder {
					maxOrder = x.Order
				}
			}
			g.Order = maxOrder + 1
		}

		if err := s.SaveGroup(g); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(g)
	}
}

// UpdateGroupHandler — PATCH /api/groups/{id}. Merges only present keys
// (name, default_profile, order). 404 if group missing. Issue #341 §5.
func UpdateGroupHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		groups, err := s.LoadGroups()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		var existing *model.Group
		for i := range groups {
			if groups[i].ID == id {
				existing = &groups[i]
				break
			}
		}
		if existing == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var patch map[string]json.RawMessage
		if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		updated := *existing
		if raw, ok := patch["name"]; ok {
			var v string
			if err := json.Unmarshal(raw, &v); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"bad_request"}`))
				return
			}
			updated.Name = v
		}
		if raw, ok := patch["default_profile"]; ok {
			var v *string
			if err := json.Unmarshal(raw, &v); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"bad_request"}`))
				return
			}
			updated.DefaultProfile = v
		}
		if raw, ok := patch["order"]; ok {
			var v int
			if err := json.Unmarshal(raw, &v); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"bad_request"}`))
				return
			}
			updated.Order = v
		}

		if err := s.SaveGroup(updated); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(updated)
	}
}

// DeleteGroupHandler — DELETE /api/groups/{id}. Removes the group and nulls
// group_id on all member locations (Read-Modify-Write). 204. Issue #341 §5.
func DeleteGroupHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		if err := s.DeleteGroup(id); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		locations, err := s.LoadLocations()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		for _, loc := range locations {
			if loc.GroupID == nil || *loc.GroupID != id {
				continue
			}
			existing, lerr := s.LoadLocation(loc.ID)
			if lerr != nil || existing == nil {
				continue
			}
			existing.GroupID = nil
			if serr := s.SaveLocation(*existing); serr != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(500)
				w.Write([]byte(`{"error":"store_error"}`))
				return
			}
		}

		w.WriteHeader(204)
	}
}
