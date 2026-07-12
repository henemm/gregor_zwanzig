package model

// Issue #458 — ComparePreset: persistiertes Konfigurations-Objekt für einen
// automatischen Orts-Vergleichs-Report. Spec:
// docs/specs/modules/issue_458_compare_preset_backend.md
//
// Profil wird als string persistiert (Persistenzformat unverändert, für
// Rückwärtskompatibilität). Der ActivityProfile-Typ lebt seit Issue #1215
// (Scheibe 3) in model (activity_profile.go); Validierung via
// model.IsValidProfile() findet im Handler statt.

import "time"

type ComparePreset struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	UserID      string   `json:"user_id"`
	LocationIDs []string `json:"location_ids"`
	// Issue #1232 Scheibe 2a: Schedule/PreviousSchedule tragen seit dem
	// Zeitplan-Reshape AUSSCHLIESSLICH noch die Pause-Semantik (#611:
	// schedule=="manual" = pausiert; PreviousSchedule konserviert den
	// Rhythmus über die Pause hinweg). Die tatsaechliche Versandzeit lebt
	// in den 5 Slot-Feldern weiter unten (MorningTime/EveningTime/EndDate).
	Schedule         string `json:"schedule"`                    // "daily"|"weekly"|"manual" — nur noch Pause-Flag
	PreviousSchedule string `json:"previous_schedule,omitempty"` // #631: konserviert Rhythmus über Pause hinweg
	Profil           string `json:"profil"`                      // ActivityProfile als string
	HourFrom         int    `json:"hour_from"`
	HourTo           int    `json:"hour_to"`
	ForecastHours    int    `json:"forecast_hours"` // 24|48|72 — Vorhersage-Horizont; Issue #764
	// Deprecated seit Issue #1232 Scheibe 2a (KL-1: Wochenrhythmus entfaellt,
	// Presets versenden taeglich). Kein neuer Schreibpfad mehr — nur noch als
	// Altdaten-Traeger fuer bereits gespeicherte "weekly"-Presets lesbar.
	Weekday              *int       `json:"weekday,omitempty"` // 0=Montag … 6=Sonntag; DEPRECATED, siehe oben
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
	// Issue #1041 Slice 1b — steuert ob der Radar-Onset-Alarm (Epic #1095) fuer
	// diesen Vergleich alle 15 Min geprueft wird. Gleiches Pointer-Pattern wie
	// OfficialAlertsEnabled, aber UMGEKEHRTER Default: nil/fehlend = AUS (nicht
	// an!). Grund: get_nowcast() ruft je Ort die volle Provider-Kette auf —
	// Netzwerkkosten skalieren mit der Ortszahl des Presets, daher bewusst
	// opt-in statt opt-out.
	RadarAlertEnabled *bool `json:"radar_alert_enabled,omitempty"`
	// Issue #1107 — steuert ob die Stundenverlauf-Sektion (Kopf + alle
	// Orts-Stundentabellen) der Compare-Mail gerendert wird. Pointer-Pattern
	// (wie OfficialAlertsEnabled): fehlt das Feld im JSON (Altdaten), decodiert
	// Go zu nil statt zum Zero-Value false. nil/true = Sektion sichtbar
	// (Default), false = komplett weggelassen.
	HourlyEnabled *bool `json:"hourly_enabled,omitempty"`
	// Issue #1170 — Alarm-Konfiguration (Epic #1095 Scheibe 3/3). Trip-identische
	// Pointer-Felder (vgl. internal/model/trip.go:98-100): nil = Feld fehlte
	// (Default in compare_alert.py greift), gesetzter Wert = bewusste Wahl.
	// metric_alert_levels lebt bewusst NICHT hier, sondern als Sub-Key in
	// DisplayConfig (analog Trip UnifiedWeatherDisplayConfig).
	AlertCooldownMinutes *int    `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom       *string `json:"alert_quiet_from,omitempty"`
	AlertQuietTo         *string `json:"alert_quiet_to,omitempty"`
	// Issue #1216 Slice 2b — steuert ob der amtliche Standalone-Alarm (Slice 2a)
	// fuer diesen Vergleich feuert. Pointer-Pattern wie OfficialAlertsEnabled:
	// fehlt das Feld im JSON (Altdaten), decodiert Go zu nil statt false; der
	// Python-Default (True = an) greift dann beim Lesen. Ein gesetzter Wert ist
	// eine bewusste Nutzer-Entscheidung. SendTelegram/SendSms sind das Kanal-
	// Opt-in (Default falsy = E-Mail-only), analog zum Trip-Alarm.
	OfficialAlertTriggersEnabled *bool `json:"official_alert_triggers_enabled,omitempty"`
	SendTelegram                 *bool `json:"send_telegram,omitempty"`
	SendSms                      *bool `json:"send_sms,omitempty"`
	// Issue #1232 Scheibe 2a — Zwei-Slot-Zeitplan (additiv auf das Trip-
	// Briefing-Modell uebertragen, docs/specs/modules/compare_preset_zeitplan.md).
	// Pointer-Pattern wie OfficialAlertsEnabled: fehlt ein Feld im JSON
	// (Altdaten), decodiert Go zu nil — das ist der Migrations-Marker fuer
	// LoadComparePresets (nil-Check auf MorningTime). MorningTime/EveningTime
	// im Format "HH:MM:SS", EndDate im Format "YYYY-MM-DD" (nil = unbegrenzt).
	MorningEnabled *bool   `json:"morning_enabled,omitempty"`
	MorningTime    *string `json:"morning_time,omitempty"`
	EveningEnabled *bool   `json:"evening_enabled,omitempty"`
	EveningTime    *string `json:"evening_time,omitempty"`
	EndDate        *string `json:"end_date,omitempty"`
	// Corridors — Issue #1231, Slice 1: additiv neben DisplayConfig["ideal_ranges"].
	// Kein omitempty (analog Trip.Corridors), konsistent zum Python-Verhalten.
	Corridors []Corridor `json:"corridors"`
}
