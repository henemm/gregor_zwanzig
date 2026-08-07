package scheduler

import (
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// TierRequestHealth aggregiert offene Level-Wechsel-Anträge (Issue #1071) über
// ALLE Nutzer zu einer rein numerischen Zusammenfassung für den öffentlichen
// /api/scheduler/status-Endpoint. Issue #1555.
//
// Ein Antrag gilt als ERLEDIGT, wenn requested_tier leer ist ODER
// model.EffectiveTier(tier) dem beantragten Level entspricht — das deckt beide
// in der Praxis beobachteten Freigabe-Handhabungen ab (Feld gelöscht bzw. Feld
// stehen geblieben) und verhindert, dass ein längst erledigter Antrag für immer
// als offen gezählt wird.
//
// Datenschutz (#252): Es landet niemals eine user_id, ein display_name oder
// eine E-Mail-Adresse in der zurückgegebenen Map — nur Zahlen. Der Endpoint ist
// ohne Login erreichbar.
//
// Die 7-Tage-Überfälligkeitsschwelle wird hier bewusst NICHT kodiert: analog zu
// BriefingHealth liefert der Endpoint rohe Stunden, die Bewertung macht der
// externe Monitor (check-gregor20.sh).
func (s *Scheduler) TierRequestHealth() map[string]any {
	var (
		openCount       int
		oldestRequested time.Time
		haveOldest      bool
	)

	if s.store != nil {
		ids, _ := s.store.ListUserIDs()
		for _, uid := range ids {
			user, err := s.store.LoadUser(uid)
			if err != nil || user == nil {
				continue // fail-soft: eine kaputte user.json darf das Aggregat nicht kippen
			}
			if user.RequestedTier == "" || model.EffectiveTier(user.Tier) == user.RequestedTier {
				continue // kein Antrag bzw. bereits gewährt
			}
			openCount++
			if user.RequestedAt == nil {
				continue
			}
			requestedAt := *user.RequestedAt
			if !haveOldest || requestedAt.Before(oldestRequested) {
				oldestRequested = requestedAt
				haveOldest = true
			}
		}
	}

	oldestAgeHours := 0.0
	if haveOldest {
		oldestAgeHours = time.Since(oldestRequested).Hours()
	}

	return map[string]any{
		"open_count":            openCount,
		"oldest_open_age_hours": oldestAgeHours,
	}
}
