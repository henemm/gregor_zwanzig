package model

// Issue #3319 AC-3 — Drift-Schutz: die oeffentlich gezeigten Level-Zahlen
// stehen ausschliesslich in frontend/src/lib/level_grenzen.json. Dieser Test
// bindet die Datei an die echten Go-Grenzen (quotaTable, SmsAllowed,
// PremiumSmsAllowed). Gegenprobe: eine verfaelschte Tabelle muss Abweichungen
// melden, sonst waere der Vergleich vakuum-gruen.
// Spec: docs/specs/modules/oeffentliche_doku_3319.md
//
//   go test ./internal/model/ -run TestLevelGrenzen -v

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"testing"
)

type levelEintrag struct {
	Trips                     *int  `json:"trips"`
	Ortsvergleiche            *int  `json:"ortsvergleiche"`
	Orte                      *int  `json:"orte"`
	SmsProTag                 *int  `json:"sms_pro_tag"`
	PremiumSmsProTag          *int  `json:"premium_sms_pro_tag"`
	PremiumSmsAntwortenProTag *int  `json:"premium_sms_antworten_pro_tag"`
	AlarmeProTag              *int  `json:"alarme_pro_tag"`
	Email                     *bool `json:"email"`
	Telegram                  *bool `json:"telegram"`
}

var levelNamen = []string{"free", "standard", "premium"}

func levelDateiPfad(t *testing.T) string {
	t.Helper()
	_, hier, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("Testdatei-Pfad nicht ermittelbar")
	}
	return filepath.Join(filepath.Dir(hier), "..", "..", "frontend", "src", "lib", "level_grenzen.json")
}

func ladeLevelGrenzen(t *testing.T) map[string]levelEintrag {
	t.Helper()
	roh, err := os.ReadFile(levelDateiPfad(t))
	if err != nil {
		t.Fatalf("Level-Datei nicht lesbar: %v", err)
	}
	var d map[string]levelEintrag
	if err := json.Unmarshal(roh, &d); err != nil {
		t.Fatalf("Level-Datei ist kein gueltiges JSON-Objekt: %v", err)
	}
	return d
}

// levelAbweichungen vergleicht die Datei mit Quoten-Tabelle und Kanal-Gates.
func levelAbweichungen(d map[string]levelEintrag, quoten map[string]Quota, sms, premiumSms func(string) bool) []string {
	var befunde []string
	if len(d) != len(levelNamen) {
		befunde = append(befunde, fmt.Sprintf("Level-Datei hat %d statt %d Level", len(d), len(levelNamen)))
	}
	zahl := func(level, feld string, p *int, soll int) {
		if p == nil {
			befunde = append(befunde, fmt.Sprintf("%s.%s fehlt", level, feld))
		} else if *p != soll {
			befunde = append(befunde, fmt.Sprintf("%s.%s: Datei %d, Code %d", level, feld, *p, soll))
		}
	}
	for _, level := range levelNamen {
		e, ok := d[level]
		if !ok {
			befunde = append(befunde, "Level fehlt: "+level)
			continue
		}
		q := quoten[level]
		zahl(level, "trips", e.Trips, q.Trips)
		zahl(level, "ortsvergleiche", e.Ortsvergleiche, q.ComparePresets)
		zahl(level, "orte", e.Orte, q.Locations)
		if e.SmsProTag == nil || (*e.SmsProTag > 0) != sms(level) {
			befunde = append(befunde, fmt.Sprintf("%s.sms_pro_tag passt nicht zu SmsAllowed=%v", level, sms(level)))
		}
		if e.PremiumSmsProTag == nil || (*e.PremiumSmsProTag > 0) != premiumSms(level) {
			befunde = append(befunde, fmt.Sprintf("%s.premium_sms_pro_tag passt nicht zu PremiumSmsAllowed=%v", level, premiumSms(level)))
		}
		if e.Email == nil || !*e.Email {
			befunde = append(befunde, level+".email muss true sein")
		}
		if e.Telegram == nil || !*e.Telegram {
			befunde = append(befunde, level+".telegram muss true sein")
		}
	}
	sort.Strings(befunde)
	return befunde
}

func TestLevelGrenzenStimmenMitGoUeberein(t *testing.T) {
	d := ladeLevelGrenzen(t)
	if b := levelAbweichungen(d, quotaTable, SmsAllowed, PremiumSmsAllowed); len(b) > 0 {
		t.Fatalf("Level-Datei weicht vom Go-Code ab:\n%v", b)
	}
}

func TestLevelGrenzenGegenprobeVerfaelschteWerte(t *testing.T) {
	d := ladeLevelGrenzen(t)
	verfaelscht := map[string]Quota{}
	for k, v := range quotaTable {
		verfaelscht[k] = v
	}
	q := verfaelscht["standard"]
	q.Trips++
	verfaelscht["standard"] = q
	if b := levelAbweichungen(d, verfaelscht, SmsAllowed, PremiumSmsAllowed); len(b) == 0 {
		t.Fatal("Gegenprobe: verfaelschte Trip-Grenze wurde nicht erkannt")
	}
	immerPremiumSms := func(string) bool { return true }
	if b := levelAbweichungen(d, quotaTable, SmsAllowed, immerPremiumSms); len(b) == 0 {
		t.Fatal("Gegenprobe: verfaelschtes Premium-SMS-Gate wurde nicht erkannt")
	}
}
