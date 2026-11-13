package handler

// Orte je Sofortvergleich hoechstens die Tarif-Quote des Nutzers (Issue #2961,
// ADR-0117 Punkt 4). Jeder Ort kostet beim Vergleich eine Abruf-Einheit; die
// Grenze haelt eine einzelne Anfrage im Rahmen dessen, was der Nutzer
// ueberhaupt anlegen darf. Admin- und Ausnahme-Konten sind wie bei den
// Mengen-Quoten unbegrenzt (userQuota, quota.go).

import (
	"net/http"
	"strings"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// VergleichOrteGrenze prueft location_ids vor dem Weiterreichen an den Core.
// "*" zaehlt alle gespeicherten Orte des Nutzers, sonst die verschiedenen,
// nicht leeren Kennungen der Liste. Ueberschreitung -> 422 limit_exceeded.
func VergleichOrteGrenze(s *store.Store, next http.Handler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		uid := middleware.UserIDFromContext(r.Context())
		if uid == "" {
			WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
			return
		}
		q, err := userQuota(r.Context(), s, uid)
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		if q == nil {
			next.ServeHTTP(w, r)
			return
		}
		anzahl, err := vergleichOrteAnzahl(s, uid, r.URL.Query().Get("location_ids"))
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
			return
		}
		if anzahl > q.Locations {
			WriteErrorWith(w, r, http.StatusUnprocessableEntity, "limit_exceeded",
				i18n.Args{"variante": "orte_vergleich", "max": q.Locations},
				map[string]any{"limit": q.Locations, "current": anzahl})
			return
		}
		next.ServeHTTP(w, r)
	}
}

func vergleichOrteAnzahl(s *store.Store, uid, ids string) (int, error) {
	if strings.TrimSpace(ids) == "*" {
		us := s.WithUser(uid)
		locs, err := us.LoadLocations()
		return len(locs), err
	}
	verschieden := map[string]struct{}{}
	for _, id := range strings.Split(ids, ",") {
		if id = strings.TrimSpace(id); id != "" {
			verschieden[id] = struct{}{}
		}
	}
	return len(verschieden), nil
}
