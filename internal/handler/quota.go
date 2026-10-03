package handler

// Mengen-Quoten je Tier (Issue #2482, Sammel-Issue #2153, Epic #2138).
// Spec: docs/specs/modules/mengen_quoten_je_tier.md
//
// EIN geteilter Helfer (quotaAllows) fuer alle Neuanlage-Wege: Trip-,
// Ortsvergleichs- und Orts-Anlage sowie das Wiederherstellen aus dem Archiv.
// POST /api/briefings delegiert an die Trip-/Preset-Create-Handler und erbt
// die Pruefung damit.
//
// Ablauf im Aufrufer (feste Reihenfolge): Validierung/Dublette -> defer
// s.LockQuota()() -> ggf. Neuanlage-Feststellung -> quotaAllows -> defer
// s.LockBriefing(id)() -> Speichern. Zaehlen und Speichern liegen damit
// gemeinsam unter dem Per-User-Quoten-Lock (AC-8), und der Quoten-Lock wird
// immer VOR LockBriefing genommen (Deadlock-Vermeidung).
//
// Admin- und Ausnahme-Menge kommen ueber den Request-Kontext
// (QuotaPolicyMiddleware im Router), NICHT ueber die Handler-Signatur: so
// erreicht die Policy jeden Weg, der denselben Request weiterreicht (auch den
// internen Aufruf aus CreateBriefingHandler), ohne die bestehenden
// Aufrufstellen umzubauen. Fehlt die Policy im Kontext, ist niemand
// ausgenommen (fail-closed).

import (
	"context"
	"fmt"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type quotaPolicyKey struct{}

// QuotaPolicyMiddleware legt die Menge der unbegrenzten Konten (Admin aus
// GZ_ADMIN_USER_IDS plus Ausnahme-Liste GZ_QUOTA_EXEMPT_USER_IDS) in den
// Request-Kontext. Sie verleiht KEINE Admin-Rechte — die Rolle wird weiterhin
// ausschliesslich aus der Admin-Menge abgeleitet (profileRole, RequireAdmin).
func QuotaPolicyMiddleware(admins, exempt map[string]struct{}) func(http.Handler) http.Handler {
	unlimited := make(map[string]struct{}, len(admins)+len(exempt))
	for id := range admins {
		unlimited[id] = struct{}{}
	}
	for id := range exempt {
		unlimited[id] = struct{}{}
	}
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), quotaPolicyKey{}, unlimited)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// quotaUnlimited: true genau dann, wenn die Kennung in der Policy-Menge steht.
func quotaUnlimited(ctx context.Context, userID string) bool {
	if userID == "" {
		return false
	}
	set, _ := ctx.Value(quotaPolicyKey{}).(map[string]struct{})
	_, ok := set[userID]
	return ok
}

// quotaBeforeSave ist eine Test-Naht (Muster profileUpdateBeforeFreshReload,
// auth.go): im Betrieb nil. Wird zwischen Zaehlen und Speichern INNERHALB des
// Per-User-Quoten-Locks aufgerufen.
var quotaBeforeSave func()

// quotaResource benennt eine quotierte Ressource (Wert des Felds "resource").
type quotaResource string

const (
	quotaTrips          quotaResource = "trips"
	quotaComparePresets quotaResource = "compare_presets"
	quotaLocations      quotaResource = "locations"
)

func (res quotaResource) limit(q model.Quota) int {
	switch res {
	case quotaTrips:
		return q.Trips
	case quotaComparePresets:
		return q.ComparePresets
	default:
		return q.Locations
	}
}

// detail ist der deutsche Text der 409-Antwort. Nur "Trip"/"Trips" (AC-15).
func (res quotaResource) detail(current, limit int) string {
	switch res {
	case quotaTrips:
		return fmt.Sprintf("Du hast bereits %d von %d Trips in deinem Tarif. Archiviere oder lösche einen Trip, um einen neuen anzulegen.", current, limit)
	case quotaComparePresets:
		return fmt.Sprintf("Du hast bereits %d von %d Ortsvergleichen in deinem Tarif. Archiviere oder lösche einen Ortsvergleich, um einen neuen anzulegen.", current, limit)
	default:
		return fmt.Sprintf("Du hast bereits %d von %d Orten in deinem Tarif. Lösche einen Ort, um einen neuen anzulegen.", current, limit)
	}
}

// userQuota liefert die Grenzen des Nutzers. nil = unbegrenzt (Admin/Ausnahme).
// Fehlt die user.json oder ist der Tarif unbekannt -> free (fail-closed). Ein
// echter Ladefehler (unlesbare/kaputte user.json) wird NICHT als free gewertet,
// sondern als Fehler zurueckgegeben — sonst bekaeme z. B. ein Premium-Nutzer
// eine falsche Free-Grenze.
func userQuota(ctx context.Context, s *store.Store, userID string) (*model.Quota, error) {
	if quotaUnlimited(ctx, userID) {
		return nil, nil
	}
	u, err := s.LoadUser(userID)
	if err != nil {
		return nil, err
	}
	tier := ""
	if u != nil {
		tier = u.Tier
	}
	q := model.QuotaFor(tier)
	return &q, nil
}

// quotaAllows prueft, ob der Nutzer aus dem Auth-Kontext EINE weitere aktive
// Instanz von res anlegen darf. Der Aufrufer MUSS s.LockQuota() halten (und
// zwar vor einem LockBriefing) und unmittelbar nach true speichern, noch
// innerhalb des Locks. Bei false ist die Antwort (409 quota_exceeded bzw.
// 500) bereits geschrieben.
//
// Zaehlregel: Trips und Ortsvergleiche nur nicht archivierte, Orte alle.
func quotaAllows(w http.ResponseWriter, r *http.Request, s *store.Store, res quotaResource) bool {
	// Geprueft wird fuer genau das Konto, in das gespeichert wird: den an
	// den Auth-Kontext gebundenen Store (im Betrieb setzt AuthMiddleware die
	// Kennung immer; us.UserID == Kennung aus dem Kontext).
	us := s.WithUser(middleware.UserIDFromContext(r.Context()))
	q, err := userQuota(r.Context(), s, us.UserID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
		return false
	}
	if q == nil {
		return true
	}

	current := 0
	switch res {
	case quotaTrips:
		var trips []model.Trip
		trips, err = us.LoadTrips()
		for _, t := range trips {
			if t.ArchivedAt == nil {
				current++
			}
		}
	case quotaComparePresets:
		var presets []model.ComparePreset
		presets, err = us.LoadComparePresets()
		for _, p := range presets {
			if p.ArchivedAt == nil {
				current++
			}
		}
	default:
		var locs []model.Location
		locs, err = us.LoadLocations()
		current = len(locs)
	}
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
		return false
	}

	limit := res.limit(*q)
	if current >= limit {
		writeJSON(w, http.StatusConflict, map[string]interface{}{
			"error":    "quota_exceeded",
			"detail":   res.detail(current, limit),
			"resource": string(res),
			"limit":    limit,
			"current":  current,
		})
		return false
	}
	if quotaBeforeSave != nil {
		quotaBeforeSave()
	}
	return true
}

// profileQuota ist die Profil-Sicht der Grenzen; nil-Felder = unbegrenzt.
type profileQuota struct {
	Trips          *int `json:"trips"`
	ComparePresets *int `json:"compare_presets"`
	Locations      *int `json:"locations"`
}

func toProfileQuota(q *model.Quota) *profileQuota {
	if q == nil {
		return &profileQuota{}
	}
	t, c, l := q.Trips, q.ComparePresets, q.Locations
	return &profileQuota{Trips: &t, ComparePresets: &c, Locations: &l}
}
