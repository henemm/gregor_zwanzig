package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// AdminUser ist die Admin-Sicht auf ein Konto (Issue #2155 S3). Bewusst ein
// eigenes DTO statt model.User: nie password_hash, Passkeys, Token-/Code-Felder.
// Kein omitempty: alle Felder sind immer vorhanden (Vertrag fuer die S4-UI).
type AdminUser struct {
	ID                string         `json:"id"`
	Email             string         `json:"email"`
	DisplayName       string         `json:"display_name"`
	Tier              string         `json:"tier"`
	RequestedTier     string         `json:"requested_tier"`
	RequestedAt       *time.Time     `json:"requested_at"`
	EmailVerifiedAt   *time.Time     `json:"email_verified_at"`
	CreatedAt         time.Time      `json:"created_at"`
	Disabled          bool           `json:"disabled"`
	IsTestUser        bool           `json:"is_test_user"`
	LastTripReportRun map[string]any `json:"last_trip_report_run"`
	// Heutiger Open-Meteo-Verbrauch (UTC-Tag), 0 bei fehlender Zaehlerdatei. Issue #2475.
	OpenMeteoCallsToday int `json:"open_meteo_calls_today"`
}

func adminUserDTO(u *model.User, sched *scheduler.Scheduler) AdminUser {
	return AdminUser{
		ID:                u.ID,
		Email:             u.Email,
		DisplayName:       u.DisplayName,
		Tier:              u.Tier,
		RequestedTier:     u.RequestedTier,
		RequestedAt:       u.RequestedAt,
		EmailVerifiedAt:   u.EmailVerifiedAt,
		CreatedAt:         u.CreatedAt,
		Disabled:          u.Disabled,
		IsTestUser:        model.IsTestAccount(u),
		LastTripReportRun: sched.LastTripReportRun(u.ID),

		OpenMeteoCallsToday: sched.UserForecastCalls(u.ID),
	}
}

func adminJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(body)
}

func adminError(w http.ResponseWriter, status int, code string) {
	adminJSON(w, status, map[string]string{"error": code})
}

// adminTargetUser loest {id} auf ein existierendes Konto auf. Ungueltige ID
// (Path-Traversal) und unbekanntes Konto liefern JSON-404; false = beantwortet.
func adminTargetUser(w http.ResponseWriter, r *http.Request, s *store.Store) (*model.User, bool) {
	id := chi.URLParam(r, "id")
	if !store.ValidUserID(id) {
		adminError(w, http.StatusNotFound, "not_found")
		return nil, false
	}
	u, err := s.LoadUser(id)
	if err != nil {
		log.Printf("admin users: load %s failed: %v", id, err)
		adminError(w, http.StatusInternalServerError, "store_error")
		return nil, false
	}
	if u == nil {
		adminError(w, http.StatusNotFound, "not_found")
		return nil, false
	}
	return u, true
}

// AdminListUsersHandler: GET /api/admin/users (Schutz: requireAdmin im Router).
func AdminListUsersHandler(s *store.Store, sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ids, err := s.ListUserIDs()
		if err != nil {
			adminError(w, http.StatusInternalServerError, "store_error")
			return
		}
		users := make([]AdminUser, 0, len(ids))
		for _, id := range ids {
			u, err := s.LoadUser(id)
			if err != nil || u == nil {
				log.Printf("admin users: skip unreadable user %s: %v", id, err)
				continue
			}
			users = append(users, adminUserDTO(u, sched))
		}
		adminJSON(w, http.StatusOK, map[string]any{"users": users})
	}
}

// AdminSetUserTierHandler: PUT /api/admin/users/{id}/tier. Exakte Whitelist,
// kein EffectiveTier-Fallback.
func AdminSetUserTierHandler(s *store.Store, sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		u, ok := adminTargetUser(w, r, s)
		if !ok {
			return
		}
		var body struct {
			Tier string `json:"tier"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			adminError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		switch body.Tier {
		case "free", "standard", "premium":
		default:
			adminError(w, http.StatusBadRequest, "invalid_tier")
			return
		}
		if err := s.SetUserTierAdmin(u.ID, body.Tier); err != nil {
			log.Printf("admin users: set tier %s failed: %v", u.ID, err)
			adminError(w, http.StatusInternalServerError, "store_error")
			return
		}
		adminRespondUser(w, s, sched, u.ID)
	}
}

// AdminSetUserDisabledHandler: PUT /api/admin/users/{id}/disabled.
// Sperren-Reihenfolge (ADR-0080): Flag setzen, dann ClearSessions, dann
// Read-after-Write. Scheitert ClearSessions: 500, Flag bleibt (sicherer Zustand).
func AdminSetUserDisabledHandler(s *store.Store, sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		u, ok := adminTargetUser(w, r, s)
		if !ok {
			return
		}
		var body struct {
			Disabled *bool `json:"disabled"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Disabled == nil {
			adminError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		if *body.Disabled && u.ID == middleware.UserIDFromContext(r.Context()) {
			adminError(w, http.StatusConflict, "cannot_disable_self")
			return
		}
		if err := s.SetUserDisabled(u.ID, *body.Disabled); err != nil {
			log.Printf("admin users: set disabled %s failed: %v", u.ID, err)
			adminError(w, http.StatusInternalServerError, "store_error")
			return
		}
		if *body.Disabled {
			if err := s.ClearSessions(u.ID); err != nil {
				log.Printf("admin users: clear sessions %s failed: %v", u.ID, err)
				adminError(w, http.StatusInternalServerError, "store_error")
				return
			}
		}
		adminRespondUser(w, s, sched, u.ID)
	}
}

// adminRespondUser antwortet mit dem frisch gelesenen Listeneintrag
// (Read-after-Write: zeigt den Ist-Zustand).
func adminRespondUser(w http.ResponseWriter, s *store.Store, sched *scheduler.Scheduler, id string) {
	u, err := s.LoadUser(id)
	if err != nil || u == nil {
		adminError(w, http.StatusInternalServerError, "store_error")
		return
	}
	adminJSON(w, http.StatusOK, adminUserDTO(u, sched))
}
