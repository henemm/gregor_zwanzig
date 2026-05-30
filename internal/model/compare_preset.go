package model

// Issue #458 — ComparePreset: persistiertes Konfigurations-Objekt für einen
// automatischen Orts-Vergleichs-Report. Spec:
// docs/specs/modules/issue_458_compare_preset_backend.md
//
// Profil wird als string gespeichert (kein Import von internal/compare), um
// einen Import-Zyklus zu vermeiden — internal/compare importiert internal/model.
// Validierung via compare.IsValidProfile() findet im Handler statt.

import "time"

type ComparePreset struct {
	ID                   string     `json:"id"`
	Name                 string     `json:"name"`
	UserID               string     `json:"user_id"`
	LocationIDs          []string   `json:"location_ids"`
	Schedule             string     `json:"schedule"` // "daily"|"weekly"|"manual"
	Profil               string     `json:"profil"`   // ActivityProfile als string
	HourFrom             int        `json:"hour_from"`
	HourTo               int        `json:"hour_to"`
	Empfaenger           []string   `json:"empfaenger"`
	LetzterVersand       *time.Time `json:"letzter_versand,omitempty"`
	TopOrtLetzterVersand *string    `json:"top_ort_letzter_versand,omitempty"`
	CreatedAt            time.Time  `json:"created_at"`
}
