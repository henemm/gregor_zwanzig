package handler

// Wachstumsgrenzen fuer gespeicherte Nutzerdaten (Issue #2961, Spec
// security_haertung_2026_11_go_schnittstellen.md AC-10).
//
// Gemessener Bestand (alle JSON-Fixtures und data/ im Repo, 2026-11-12):
// hoechstens 15 Schluessel je Config-Map (display_config/report_config),
// alle Schluessel passen auf configKeyRe; hoechstens 13 Etappen je Trip
// (KHW-402), hoechstens 4 Wegpunkte je Etappe (GR221). Der GPX-Import legt je
// Abschnitt einen Wegpunkt an (Stunden-Segmente) — die Grenzen liegen um ein
// Vielfaches darueber.
//
// Bestandsschutz: ein bereits gespeicherter Schluessel, der nicht auf das
// Muster passt, darf weiter ueberschrieben werden; geprueft werden nur NEUE
// Schluessel. Etappen-/Wegpunkt-Grenzen greifen nur, wenn der Rumpf Etappen
// mitschickt.

import (
	"net/http"
	"regexp"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/model"
)

const (
	maxConfigSchluessel  = 200
	maxEtappenJeTrip     = 100
	maxWegpunkteJeEtappe = 500
)

var configKeyRe = regexp.MustCompile(`^[a-z0-9_.-]{1,64}$`)

var grenzeSchluessel = i18n.Args{"variante": "schluessel"}

// configMergeZulaessig: true, wenn der Merge von src in dst nur zulaessige
// neue Schluessel bringt und danach hoechstens maxConfigSchluessel Schluessel
// stehen.
func configMergeZulaessig(dst, src map[string]interface{}) bool {
	gesamt := len(dst)
	for k := range src {
		if _, alt := dst[k]; alt {
			continue
		}
		if !configKeyRe.MatchString(k) {
			return false
		}
		gesamt++
	}
	return gesamt <= maxConfigSchluessel
}

// configMergesVerletzt prueft mehrere (dst, src)-Paare; bei Verstoss ist die
// 400-Antwort geschrieben.
func configMergesVerletzt(w http.ResponseWriter, r *http.Request, paare ...[2]map[string]interface{}) bool {
	for _, p := range paare {
		if p[1] != nil && !configMergeZulaessig(p[0], p[1]) {
			WriteError(w, r, http.StatusBadRequest, "limit_exceeded", grenzeSchluessel)
			return true
		}
	}
	return false
}

// etappenGrenzeVerletzt prueft Etappen- und Wegpunktzahl; bei Verstoss ist
// die 400-Antwort geschrieben.
func etappenGrenzeVerletzt(w http.ResponseWriter, r *http.Request, stages []model.Stage) bool {
	if len(stages) > maxEtappenJeTrip {
		WriteError(w, r, http.StatusBadRequest, "limit_exceeded", i18n.Args{"variante": "etappen", "max": maxEtappenJeTrip})
		return true
	}
	for _, st := range stages {
		if len(st.Waypoints) > maxWegpunkteJeEtappe {
			WriteError(w, r, http.StatusBadRequest, "limit_exceeded", i18n.Args{"variante": "wegpunkte", "max": maxWegpunkteJeEtappe})
			return true
		}
	}
	return false
}

// presetGrenzenVerletzt prueft die freien Maps eines Ortsvergleichs nach dem
// Merge gegen den Vorstand (alt=nil bei Neuanlage).
func presetGrenzenVerletzt(w http.ResponseWriter, r *http.Request, alt *model.ComparePreset, neu model.ComparePreset) bool {
	var altDisplay, altKanaele map[string]interface{}
	if alt != nil {
		altDisplay, altKanaele = alt.DisplayConfig, alt.AlertMetricChannels
	}
	return configMergesVerletzt(w, r,
		[2]map[string]interface{}{altDisplay, neu.DisplayConfig},
		[2]map[string]interface{}{altKanaele, neu.AlertMetricChannels},
	)
}

// derefMap liefert den Wert eines optionalen Map-Zeigers (nil bleibt nil).
func derefMap(p *map[string]interface{}) map[string]interface{} {
	if p == nil {
		return nil
	}
	return *p
}
