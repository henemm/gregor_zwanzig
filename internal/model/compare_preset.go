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
	Schedule             string     `json:"schedule"`                     // "daily"|"weekly"|"manual"
	PreviousSchedule     string     `json:"previous_schedule,omitempty"`  // #631: konserviert Rhythmus über Pause hinweg
	Profil               string     `json:"profil"`                       // ActivityProfile als string
	HourFrom             int        `json:"hour_from"`
	HourTo               int        `json:"hour_to"`
	ForecastHours        int        `json:"forecast_hours"` // 24|48|72 — Vorhersage-Horizont; Issue #764
	Weekday              *int       `json:"weekday,omitempty"` // 0=Montag … 6=Sonntag; nur relevant wenn Schedule="weekly"; nil=kein Wert gesetzt (Default 4=Freitag wird in Store/Handler gesetzt)
	Empfaenger           []string   `json:"empfaenger"`
	LetzterVersand       *time.Time `json:"letzter_versand,omitempty"`
	TopOrtLetzterVersand *string    `json:"top_ort_letzter_versand,omitempty"`
	CreatedAt            time.Time  `json:"created_at"`
	// Issue #611 — manuell ins Archiv verschoben. nil = aktiv, gesetzt = archiviert.
	ArchivedAt *time.Time `json:"archived_at,omitempty"`
	// Issue #582 — Frontend-Konfiguration (Region, channel_layouts, ideal_ranges u.a.).
	// omitempty: Altdaten ohne Feld bleiben nil; kein Schema-Bruch.
	DisplayConfig map[string]interface{} `json:"display_config,omitempty"`
	// Issue #1040 — steuert ob die #1034-Official-Alert-Quellen fuer diesen
	// Vergleich abgefragt werden. Pointer-Pattern (wie Weekday *int): fehlt das
	// Feld im JSON (Altdaten), decodiert Go zu nil statt zum Zero-Value false.
	// nil/true = Quellen werden abgefragt (Default), false = strukturell kein Fetch.
	OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
	// Issue #1107 — steuert ob die Stundenverlauf-Sektion (Kopf + alle
	// Orts-Stundentabellen) der Compare-Mail gerendert wird. Pointer-Pattern
	// (wie OfficialAlertsEnabled): fehlt das Feld im JSON (Altdaten), decodiert
	// Go zu nil statt zum Zero-Value false. nil/true = Sektion sichtbar
	// (Default), false = komplett weggelassen.
	HourlyEnabled *bool `json:"hourly_enabled,omitempty"`
}
