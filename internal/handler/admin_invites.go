package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const inviteNoteMaxLen = 200

// AdminInvite ist die Admin-Sicht auf eine Einladung (Issue #2519): nie
// token_hash oder Token-Klartext.
type AdminInvite struct {
	ID        string     `json:"id"`
	Tier      string     `json:"tier"`
	Note      string     `json:"note"`
	Status    string     `json:"status"`
	CreatedAt time.Time  `json:"created_at"`
	CreatedBy string     `json:"created_by"`
	UsedBy    string     `json:"used_by"`
	UsedAt    *time.Time `json:"used_at"`
	RevokedAt *time.Time `json:"revoked_at"`
}

func adminInviteDTO(i model.Invite) AdminInvite {
	return AdminInvite{
		ID: i.ID, Tier: i.Tier, Note: i.Note, Status: i.Status(),
		CreatedAt: i.CreatedAt, CreatedBy: i.CreatedBy,
		UsedBy: i.UsedBy, UsedAt: i.UsedAt, RevokedAt: i.RevokedAt,
	}
}

// AdminCreateInviteHandler: POST /api/admin/invites (Schutz: requireAdmin).
// Der Link mit dem Token wird nur in dieser Antwort ausgeliefert.
func AdminCreateInviteHandler(inv *store.InviteStore, publicHost string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Tier string `json:"tier"`
			Note string `json:"note"`
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
		if utf8.RuneCountInString(body.Note) > inviteNoteMaxLen {
			adminError(w, http.StatusBadRequest, "note_too_long")
			return
		}
		created, token, err := inv.Create(body.Tier, body.Note, middleware.UserIDFromContext(r.Context()))
		if err != nil {
			log.Printf("admin invites: create failed: %v", err)
			adminError(w, http.StatusInternalServerError, "store_error")
			return
		}
		log.Printf("admin invites: created %s tier=%s by=%s", created.ID, created.Tier, created.CreatedBy)
		adminJSON(w, http.StatusCreated, map[string]any{
			"invite": adminInviteDTO(created),
			"link":   strings.TrimRight(publicHost, "/") + "/register?invite=" + token,
		})
	}
}

// AdminListInvitesHandler: GET /api/admin/invites.
func AdminListInvitesHandler(inv *store.InviteStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		all := inv.List()
		out := make([]AdminInvite, 0, len(all))
		for _, i := range all {
			out = append(out, adminInviteDTO(i))
		}
		adminJSON(w, http.StatusOK, map[string]any{"invites": out})
	}
}

// AdminRevokeInviteHandler: POST /api/admin/invites/{id}/revoke.
func AdminRevokeInviteHandler(inv *store.InviteStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		switch err := inv.Revoke(id); err {
		case nil:
		case store.ErrInviteNotFound:
			adminError(w, http.StatusNotFound, "not_found")
			return
		case store.ErrInviteUsed:
			adminError(w, http.StatusConflict, "invite_used")
			return
		default:
			log.Printf("admin invites: revoke %s failed: %v", id, err)
			adminError(w, http.StatusInternalServerError, "store_error")
			return
		}
		log.Printf("admin invites: revoked %s", id)
		for _, i := range inv.List() {
			if i.ID == id {
				adminJSON(w, http.StatusOK, adminInviteDTO(i))
				return
			}
		}
		adminError(w, http.StatusInternalServerError, "store_error")
	}
}

// InviteCheckHandler: POST /api/auth/invite/check mit {"token":"..."},
// oeffentlich (rate-limited im Router). Der Token steht bewusst im Body, nie in
// der URL (Access-Log). 200 {tier} nur bei offener Einladung, sonst neutral 404.
func InviteCheckHandler(inv *store.InviteStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Token string `json:"token"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 4096)
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			adminError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		if i, ok := inv.Peek(body.Token); ok {
			adminJSON(w, http.StatusOK, map[string]string{"tier": i.Tier})
			return
		}
		adminError(w, http.StatusNotFound, "invite_invalid")
	}
}
