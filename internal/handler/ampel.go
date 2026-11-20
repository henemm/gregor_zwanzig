package handler

// Issue #2792 S1a — Profil-Ampel (ADR-0106): Validierung beim Speichern.
// Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md §1. Gleiche Regeln
// wie Python app.ampel.validate_ampel: unten rot < orange < gelb, oben
// gelb < orange < rot (jeweils ueber die gesetzten Werte), untere Grenzen nie
// ueber den oberen, alarm_ab aus der Menge, Gewitter "hoch" nie gelb und nie
// schwaecher als "mittel", Gewitter-alarm_ab nie gelb (#2793), Windrichtung
// modus/sektoren (#3222). Abgelehnt wird mit Code "ampel_ungueltig".

import "encoding/json"

var ampelUnten = []string{"red", "orange", "yellow"}
var ampelOben = []string{"yellow", "orange", "red"}
var ampelRang = map[string]int{"yellow": 1, "orange": 2, "red": 3}
var ampelAlarmAb = map[string]bool{"never": true, "yellow": true, "orange": true, "red": true}

// Issue #2793 S2a (ADR-0106 P2): Gewitter-alarm_ab nie "yellow" — „leicht" ist
// fest gelb und alarmiert nie. Gleiche Regel wie Python ALARM_AB_GEWITTER.
var ampelAlarmAbGewitter = map[string]bool{"never": true, "orange": true, "red": true}

// Issue #3222 (ADR-0126): Windrichtung modus/sektoren; gleiche Mengen wie
// Python services.windrichtung.MODI/SEKTOREN (deutsche Protokoll-Token).
var ampelWindModi = map[string]bool{"aus": true, "gegenwind": true, "sektoren": true}
var ampelWindSektoren = map[string]bool{"N": true, "NO": true, "O": true, "SO": true,
	"S": true, "SW": true, "W": true, "NW": true}

// ampelWindrichtungGrund liefert "" (gueltig) oder den Grund-Code der
// Ablehnung, gleich Python app.ampel._windrichtung_grund (gleiche Reihenfolge).
// vergleich=true: Ortsvergleich, dort ist "gegenwind" unzulaessig (Orte haben
// keine Bewegungsrichtung).
func ampelWindrichtungGrund(mid string, e map[string]interface{}, vergleich bool) string {
	modus, sektoren := e["modus"], e["sektoren"]
	if modus == nil && sektoren == nil {
		return ""
	}
	if mid != "wind_direction" {
		return "nur_windrichtung"
	}
	m, _ := modus.(string)
	if modus != nil && !ampelWindModi[m] {
		return "modus_unbekannt"
	}
	if m == "gegenwind" && vergleich {
		return "gegenwind_nur_trip"
	}
	if sektoren == nil {
		return ""
	}
	liste, ok := sektoren.([]interface{})
	if !ok {
		return "sektoren_keine_liste"
	}
	gesehen := map[string]bool{}
	doppelt := false
	for _, x := range liste {
		k, ok := x.(string)
		if !ok || !ampelWindSektoren[k] {
			return "sektor_unbekannt"
		}
		doppelt = doppelt || gesehen[k]
		gesehen[k] = true
	}
	if doppelt {
		return "sektor_doppelt"
	}
	if len(liste) > 0 && m != "sektoren" {
		return "sektoren_ohne_sektormodus"
	}
	return ""
}

// ampelSeite liefert die gesetzten Werte einer Seite in Schluessel-Reihenfolge;
// ok=false bei falschem Typ oder nicht streng aufsteigender Reihenfolge.
func ampelSeite(v interface{}, keys []string) ([]float64, bool) {
	if v == nil {
		return nil, true
	}
	m, ok := v.(map[string]interface{})
	if !ok {
		return nil, false
	}
	var gesetzt []float64
	for _, k := range keys {
		raw, da := m[k]
		if !da || raw == nil {
			continue
		}
		f, ok := raw.(float64)
		if !ok {
			return nil, false
		}
		if len(gesetzt) > 0 && gesetzt[len(gesetzt)-1] >= f {
			return nil, false
		}
		gesetzt = append(gesetzt, f)
	}
	return gesetzt, true
}

func ampelMetrikGueltig(mid string, v interface{}, vergleich bool) bool {
	e, ok := v.(map[string]interface{})
	if !ok {
		return false
	}
	if a, da := e["alarm_ab"].(string); da && mid == "thunder" && !ampelAlarmAbGewitter[a] {
		return false
	}
	unten, okU := ampelSeite(e["lower"], ampelUnten)
	oben, okO := ampelSeite(e["upper"], ampelOben)
	if !okU || !okO {
		return false
	}
	if len(unten) > 0 && len(oben) > 0 && unten[len(unten)-1] > oben[0] {
		return false
	}
	if a, da := e["alarm_ab"]; da && a != nil {
		if s, ok := a.(string); !ok || !ampelAlarmAb[s] {
			return false
		}
	}
	if en, da := e["enabled"]; da && en != nil {
		if _, ok := en.(bool); !ok {
			return false
		}
	}
	return ampelWindrichtungGrund(mid, e, vergleich) == ""
}

func ampelGewitterGueltig(v interface{}) bool {
	th, ok := v.(map[string]interface{})
	if !ok {
		return false
	}
	mittel, _ := th["mittel"].(string)
	hoch, _ := th["hoch"].(string)
	if (th["mittel"] != nil && ampelRang[mittel] == 0) || (th["hoch"] != nil && ampelRang[hoch] < 2) {
		return false
	}
	return mittel == "" || hoch == "" || ampelRang[hoch] >= ampelRang[mittel]
}

// validateAmpel prueft eine Ampel im Trip-Kontext (auch eigene Vorlagen).
func validateAmpel(v interface{}) bool {
	return validateAmpelIm(v, false)
}

// validateAmpelIm prueft eine Ampel; nil (keine Ampel = Vorlage) ist gueltig.
// vergleich=true: Ortsvergleich (Windrichtung ohne "gegenwind", #3222).
func validateAmpelIm(v interface{}, vergleich bool) bool {
	if v == nil {
		return true
	}
	a, ok := v.(map[string]interface{})
	if !ok {
		return false
	}
	if t, da := a["template"]; da && t != nil {
		if _, ok := t.(string); !ok {
			return false
		}
	}
	if m, da := a["metrics"]; da && m != nil {
		metrics, ok := m.(map[string]interface{})
		if !ok {
			return false
		}
		for mid, e := range metrics {
			if !ampelMetrikGueltig(mid, e, vergleich) {
				return false
			}
		}
	}
	if th, da := a["thunder"]; da && th != nil && !ampelGewitterGueltig(th) {
		return false
	}
	return true
}

// displayConfigAmpelUngueltig: true, wenn eine eingehende display_config eine
// ungueltige Ampel traegt. Geprueft wird nur, was der Client sendet — eine
// gespeicherte Alt-Ampel blockiert keine anderen Aenderungen. vergleich=true
// fuer Ortsvergleich-Schreibwege (#3222).
func displayConfigAmpelUngueltig(dc map[string]interface{}, vergleich bool) bool {
	a, da := dc["ampel"]
	return da && !validateAmpelIm(a, vergleich)
}

// patchAmpelUngueltig liest display_config.ampel aus einem JSON-Patch-Rumpf.
// Ein nicht lesbarer Rumpf zaehlt hier nicht (das meldet der Merge-Kernel).
func patchAmpelUngueltig(patch []byte, vergleich bool) bool {
	var p struct {
		DisplayConfig map[string]interface{} `json:"display_config"`
	}
	if err := json.Unmarshal(patch, &p); err != nil {
		return false
	}
	return displayConfigAmpelUngueltig(p.DisplayConfig, vergleich)
}
