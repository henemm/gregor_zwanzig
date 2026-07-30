package mail

// Empfaenger-Regelwerk-Paritaet Python <-> Go (Issue #1412, Scheibe S2a).
//
// Spec: docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md
// Analyse: docs/context/fix-1412-s2-regelwerk-paritaet.md, "Analysis (S2a)"
//
// Go-Pendant zu tests/test_mail_recipient_parity.py -- beide lesen dieselbe
// Falltabelle tests/fixtures/mail_recipient_parity/faelle.json. recipientBlocked
// wird DIREKT gerufen, nicht Send() -- resendBlocked/dialAndSend sind
// Host-Policies ausserhalb der Guard-Region und gehoeren symmetrisch nicht in
// die Achse (Analyse S2a). Kein Netz, kein Testflag, kein Build-Tag (waere
// eine Aufweichung von #1122).
//
// WICHTIG: dieser Laeufer aendert NICHTS an sender.go -- reines Pruefwerkzeug
// (AC-10, dort per git-diff im Python-Laeufer geprueft).
//
// ERWARTUNG in dieser Phase (TDD RED, ausnahmen: []): D1, D2, D4 (seite "go")
// und D5 (seite "beide") werden NAMENTLICH gemeldet. D3 und N1 sind reine
// PYTHON-seitige Divergenzen und fuer diesen Laeufer strukturell unsichtbar
// (Analyse S2a, "Ehrliche Grenze des Mechanismus").
//
// Pfadanker: os.Getwd()-Aufstieg bis zum Verzeichnis mit go.mod (genau eine
// im Repo). NICHT runtime.Caller(0) -- liefert unter -trimpath einen
// modulrelativen Pfad und bricht still (Analyse S2a).

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"
)

const maxRepoRootAscent = 6

func findRepoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("findRepoRoot: os.Getwd() fehlgeschlagen: %v", err)
	}
	for i := 0; i < maxRepoRootAscent; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf(
		"findRepoRoot: kein go.mod innerhalb von %d Ebenen ueber %q gefunden -- "+
			"Pfadanker verloren, der Laeufer kann die Falltabelle nicht finden.",
		maxRepoRootAscent, dir,
	)
	return ""
}

func falltabellePfad(t *testing.T) string {
	t.Helper()
	repoRoot := findRepoRoot(t)
	pfad := filepath.Join(repoRoot, "tests", "fixtures", "mail_recipient_parity", "faelle.json")
	if _, err := os.Stat(pfad); err != nil {
		t.Fatalf(
			"Falltabelle fehlt: %s -- der Laeufer haette dann keine Faelle zu "+
				"pruefen und wuerde 'nichts gefunden, alles gruen' still "+
				"durchwinken (AC-7): %v", pfad, err,
		)
	}
	return pfad
}

type parityFall struct {
	ID   string `json:"id"`
	Host string `json:"host"`
	To   string `json:"to"`
	Soll string `json:"soll"`
}

type parityAusnahme struct {
	Fall    string `json:"fall"`
	Seite   string `json:"seite"`
	Ist     string `json:"ist"`
	Scheibe string `json:"scheibe"`
	Frist   string `json:"frist"`
	Grund   string `json:"grund"`
}

type parityDaten struct {
	Faelle               []parityFall               `json:"faelle"`
	Profile              map[string]json.RawMessage `json:"profile"`
	Ausnahmen            []parityAusnahme            `json:"ausnahmen"`
	AusnahmenHoechstzahl int                          `json:"ausnahmen_hoechstzahl"`
	VerzweigungenPython  int                          `json:"verzweigungen_python"`
	VerzweigungenGo      int                          `json:"verzweigungen_go"`
}

func ladeFalltabelleOrError(pfad string) (parityDaten, error) {
	raw, err := os.ReadFile(pfad)
	if err != nil {
		return parityDaten{}, fmt.Errorf(
			"Falltabelle fehlt: %s -- der Laeufer haette dann keine Faelle zu "+
				"pruefen und wuerde 'nichts gefunden, alles gruen' still "+
				"durchwinken (AC-7): %w", pfad, err,
		)
	}
	var daten parityDaten
	if err := json.Unmarshal(raw, &daten); err != nil {
		return parityDaten{}, fmt.Errorf("ladeFalltabelle: %s ist kein gueltiges JSON: %w", pfad, err)
	}
	if len(daten.Faelle) == 0 {
		return parityDaten{}, fmt.Errorf(
			"Falltabelle %s enthaelt keine Faelle -- eine leere Fallliste "+
				"waere ein stilles Gruen ohne echte Pruefung (AC-7).", pfad,
		)
	}
	return daten, nil
}

func ladeFalltabelle(t *testing.T, pfad string) parityDaten {
	t.Helper()
	daten, err := ladeFalltabelleOrError(pfad)
	if err != nil {
		t.Fatalf("%v", err)
	}
	return daten
}

func baueDatenwurzel(t *testing.T, profile map[string]json.RawMessage) string {
	t.Helper()
	dataDir := t.TempDir()
	for userID, inhalt := range profile {
		userDir := filepath.Join(dataDir, "users", userID)
		if err := os.MkdirAll(userDir, 0755); err != nil {
			t.Fatalf("baueDatenwurzel: %v", err)
		}
		if err := os.WriteFile(filepath.Join(userDir, "user.json"), inhalt, 0644); err != nil {
			t.Fatalf("baueDatenwurzel: %v", err)
		}
	}
	return dataDir
}

const minBegruendung = 15

var unwortRe = regexp.MustCompile(`[^\p{L}\p{N}]+`)

func begruendungsLaenge(grund string) int {
	return len([]rune(unwortRe.ReplaceAllString(grund, "")))
}

func bewerteFall(fallID, soll, gemessen string, ausnahmen []parityAusnahme, heute time.Time) string {
	for _, ausnahme := range ausnahmen {
		if begruendungsLaenge(ausnahme.Grund) < minBegruendung {
			continue
		}
		frist, err := time.Parse("2006-01-02", ausnahme.Frist)
		if err != nil {
			return fmt.Sprintf("%s: Ausnahme (%s) hat eine unlesbare Frist %q: %v",
				fallID, ausnahme.Seite, ausnahme.Frist, err)
		}
		if frist.Before(heute) {
			return fmt.Sprintf(
				"%s: Ausnahme (%s) ist am %s abgelaufen (Frist ueberschritten) -- "+
					"Ausnahme erneuern oder entfernen (AC-6).",
				fallID, ausnahme.Seite, ausnahme.Frist,
			)
		}
		if gemessen == soll {
			return fmt.Sprintf(
				"%s: Ausnahme (%s) behauptet ist=%q, gemessen wird aber bereits "+
					"soll=%q -- Divergenz aufgeloest, Ausnahme entfernen (AC-3).",
				fallID, ausnahme.Seite, ausnahme.Ist, soll,
			)
		}
		if ausnahme.Ist == gemessen {
			return ""
		}
		return fmt.Sprintf(
			"%s: Ausnahme (%s) behauptet ist=%q, gemessen wurde aber %q -- "+
				"Ausnahme stimmt nicht mehr mit der Wirklichkeit ueberein (AC-3).",
			fallID, ausnahme.Seite, ausnahme.Ist, gemessen,
		)
	}
	if gemessen != soll {
		return fmt.Sprintf(
			"%s: soll=%q, gemessen=%q -- unentschuldigte Divergenz ohne gueltige "+
				"Ausnahme (AC-2).", fallID, soll, gemessen,
		)
	}
	return ""
}

func deckelUeberschritten(daten parityDaten) bool {
	return len(daten.Ausnahmen) > daten.AusnahmenHoechstzahl
}

func goEntscheidung(t *testing.T, host, to, dataDir string) string {
	t.Helper()
	t.Setenv("GZ_DATA_DIR", dataDir)
	if err := recipientBlocked(host, to); err != nil {
		return "block"
	}
	return "allow"
}

func pruefeFalltabelle(t *testing.T, daten parityDaten) ([]string, map[string]string) {
	t.Helper()
	dataDir := baueDatenwurzel(t, daten.Profile)

	var befunde []string
	ergebnisse := make(map[string]string, len(daten.Faelle))
	for _, fall := range daten.Faelle {
		gemessen := goEntscheidung(t, fall.Host, fall.To, dataDir)
		ergebnisse[fall.ID] = gemessen

		var zugehoerige []parityAusnahme
		for _, a := range daten.Ausnahmen {
			if a.Fall == fall.ID && (a.Seite == "go" || a.Seite == "beide") {
				zugehoerige = append(zugehoerige, a)
			}
		}
		if befund := bewerteFall(fall.ID, fall.Soll, gemessen, zugehoerige, time.Now()); befund != "" {
			befunde = append(befunde, befund)
		}
	}
	return befunde, ergebnisse
}

func TestEntscheidungsparitaet(t *testing.T) {
	daten := ladeFalltabelle(t, falltabellePfad(t))
	befunde, _ := pruefeFalltabelle(t, daten)
	if len(befunde) > 0 {
		sort.Strings(befunde)
		t.Fatalf("Go-Laeufer meldet Abweichungen:\n%s", strings.Join(befunde, "\n"))
	}
}

func TestAusnahmenDeckelImAusgeliefertenStandNichtUeberschritten(t *testing.T) {
	daten := ladeFalltabelle(t, falltabellePfad(t))
	if deckelUeberschritten(daten) {
		t.Fatalf(
			"%d Ausnahmen ueberschreiten den Deckel (%d).",
			len(daten.Ausnahmen), daten.AusnahmenHoechstzahl,
		)
	}
}

func TestAC4DeckelUeberschreitungWirdErkannt(t *testing.T) {
	var ausnahmen []parityAusnahme
	for i := 0; i < 7; i++ {
		ausnahmen = append(ausnahmen, parityAusnahme{
			Fall: fmt.Sprintf("F%d", i), Seite: "go", Ist: "block", Scheibe: "S2b",
			Frist: "2026-10-28", Grund: fmt.Sprintf("ausreichend lange Begruendung Nummer %d", i),
		})
	}
	daten := parityDaten{AusnahmenHoechstzahl: 6, Ausnahmen: ausnahmen}
	if !deckelUeberschritten(daten) {
		t.Fatal("7 Ausnahmen bei Deckel 6 haetten als Ueberschreitung erkannt werden muessen.")
	}
}

func TestAC2UnentschuldigteDivergenzWirdBenannt(t *testing.T) {
	befund := bewerteFall("F-TEST", "allow", "block", nil, time.Date(2026, 7, 30, 0, 0, 0, 0, time.UTC))
	if befund == "" || !strings.Contains(befund, "F-TEST") {
		t.Fatalf("Unentschuldigte Divergenz wurde nicht benannt: %q", befund)
	}
}

func TestAC3AufgeloesteAusnahmeVerlangtEntfernen(t *testing.T) {
	ausnahme := parityAusnahme{
		Fall: "F-TEST", Seite: "go", Ist: "block", Scheibe: "S2b",
		Frist: "2026-10-28", Grund: "ausreichend lange Begruendung fuer den Test",
	}
	befund := bewerteFall("F-TEST", "allow", "allow", []parityAusnahme{ausnahme}, time.Date(2026, 7, 30, 0, 0, 0, 0, time.UTC))
	if befund == "" || !strings.Contains(strings.ToLower(befund), "entfernen") {
		t.Fatalf("Aufgeloeste Ausnahme haette 'entfernen' verlangen muessen: %q", befund)
	}
}

func TestAC5ZuKurzeBegruendungZaehltNicht(t *testing.T) {
	ausnahme := parityAusnahme{
		Fall: "F-TEST", Seite: "go", Ist: "block", Scheibe: "S2b",
		Frist: "2026-10-28", Grund: "zu kurz",
	}
	befund := bewerteFall("F-TEST", "allow", "block", []parityAusnahme{ausnahme}, time.Date(2026, 7, 30, 0, 0, 0, 0, time.UTC))
	if befund == "" || !strings.Contains(befund, "F-TEST") {
		t.Fatalf("Zu kurze Begruendung haette wie fehlende Ausnahme behandelt werden muessen: %q", befund)
	}
}

func TestAC6AbgelaufeneFristBrichtAb(t *testing.T) {
	ausnahme := parityAusnahme{
		Fall: "F-TEST", Seite: "go", Ist: "block", Scheibe: "S2b",
		Frist: "2026-01-01", Grund: "ausreichend lange Begruendung fuer den Test",
	}
	befund := bewerteFall("F-TEST", "allow", "block", []parityAusnahme{ausnahme}, time.Date(2026, 7, 30, 0, 0, 0, 0, time.UTC))
	if befund == "" || !strings.Contains(strings.ToLower(befund), "abgelaufen") {
		t.Fatalf("Abgelaufene Frist haette benannt werden muessen: %q", befund)
	}
}

func TestAC7FehlendeFalltabelleBrichtLautAb(t *testing.T) {
	pfad := filepath.Join(t.TempDir(), "nicht-vorhanden.json")
	_, err := ladeFalltabelleOrError(pfad)
	if err == nil {
		t.Fatal("Fehlende Falltabelle haette einen Fehler liefern muessen.")
	}
	if !strings.Contains(err.Error(), "fehlt") {
		t.Fatalf("Fehlermeldung nennt nicht 'fehlt': %v", err)
	}
}

func TestAC7LeereFalllisteBrichtLautAb(t *testing.T) {
	pfad := filepath.Join(t.TempDir(), "faelle.json")
	if err := os.WriteFile(pfad, []byte(`{"faelle": [], "profile": {}, "ausnahmen": []}`), 0644); err != nil {
		t.Fatalf("Setup: %v", err)
	}
	_, err := ladeFalltabelleOrError(pfad)
	if err == nil {
		t.Fatal("Leere Fallliste haette einen Fehler liefern muessen.")
	}
	if !strings.Contains(err.Error(), "keine Faelle") {
		t.Fatalf("Fehlermeldung nennt nicht 'keine Faelle': %v", err)
	}
}

func TestAC7FixtureDatenwurzelFehltWirdErkannt(t *testing.T) {
	dataDir := t.TempDir()
	ergebnis := goEntscheidung(t, "smtp.resend-fixture.test", "paritaet-fixture@henemm.com", dataDir)
	if ergebnis != "block" {
		t.Fatalf(
			"Ohne geladene Fixture-Datenwurzel haette dieser Fall 'block' liefern "+
				"muessen, gemessen wurde aber %q -- der Selbstnachweis waere wirkungslos.",
			ergebnis,
		)
	}
}

var guardRegionFuncs = []string{
	"recipientBlocked",
	"rawContainsTestMailbox",
	"loadResendAllowlist",
	"splitRecipientField",
	"normalizedAddrForGuard",
	"isReservedTestDomain",
	"maskAddrForLog",
}

var decisionTokenRe = regexp.MustCompile(`\bif\b|&&|\|\|`)

func extractFuncBody(text, name string) (string, bool) {
	marker := "func " + name + "("
	idx := strings.Index(text, marker)
	if idx < 0 {
		return "", false
	}
	braceStart := strings.Index(text[idx:], "{")
	if braceStart < 0 {
		return "", false
	}
	braceStart += idx
	depth := 0
	for i := braceStart; i < len(text); i++ {
		switch text[i] {
		case '{':
			depth++
		case '}':
			depth--
			if depth == 0 {
				return text[idx : i+1], true
			}
		}
	}
	return "", false
}

func stripGoComments(text string) string {
	zeilen := strings.Split(text, "\n")
	for i, zeile := range zeilen {
		if k := strings.Index(zeile, "//"); k >= 0 {
			zeilen[i] = zeile[:k]
		}
	}
	return strings.Join(zeilen, "\n")
}

func zaehleGuardRegion(sourceText string) (anzahl int, fehlend []string) {
	for _, name := range guardRegionFuncs {
		body, ok := extractFuncBody(sourceText, name)
		if !ok {
			fehlend = append(fehlend, name)
			continue
		}
		anzahl += len(decisionTokenRe.FindAllString(stripGoComments(body), -1))
	}
	return anzahl, fehlend
}

func TestVerzweigungsratscheGoRegionGefundenUndZahlStimmt(t *testing.T) {
	repoRoot := findRepoRoot(t)
	quelle, err := os.ReadFile(filepath.Join(repoRoot, "internal", "mail", "sender.go"))
	if err != nil {
		t.Fatalf("sender.go nicht lesbar: %v", err)
	}
	gezaehlt, fehlend := zaehleGuardRegion(string(quelle))
	if len(fehlend) > 0 {
		t.Fatalf(
			"Selbstnachweis 'Region gefunden': folgende Guard-Funktionen wurden in "+
				"sender.go NICHT gefunden: %v -- Region verloren, die Ratsche "+
				"prueft nichts mehr (AC-7).", fehlend,
		)
	}
	daten := ladeFalltabelle(t, falltabellePfad(t))
	if gezaehlt != daten.VerzweigungenGo {
		t.Fatalf(
			"Go-Guard-Region hat jetzt %d Entscheidungspunkte (Fixture: %d) -- "+
				"neue Verzweigung ohne abdeckenden Fall? Fixture-Zahl nach "+
				"Pruefung anpassen (AC-9).", gezaehlt, daten.VerzweigungenGo,
		)
	}
}

func TestVerzweigungsratscheErkenntWachstum(t *testing.T) {
	alt := "func recipientBlocked(host, to string) error {\n\tif a {\n\t\treturn nil\n\t}\n\treturn nil\n}\n"
	neu := "func recipientBlocked(host, to string) error {\n\tif a && b {\n\t\treturn nil\n\t}\n\treturn nil\n}\n"
	altAnzahl, _ := zaehleGuardRegion(alt)
	neuAnzahl, _ := zaehleGuardRegion(neu)
	if neuAnzahl <= altAnzahl {
		t.Fatalf("Eine zusaetzliche Bedingung wurde nicht als Wachstum erkannt (alt=%d neu=%d).", altAnzahl, neuAnzahl)
	}
}

func TestAC7FehlendeRegionBrichtLautAb(t *testing.T) {
	synth := "func andereFunktion() error {\n\tif true {\n\t\treturn nil\n\t}\n\treturn nil\n}\n"
	_, fehlend := zaehleGuardRegion(synth)
	if len(fehlend) != len(guardRegionFuncs) {
		t.Fatalf("Erwartet: alle %d Guard-Funktionen fehlen im synthetischen Text, gefunden fehlend=%v", len(guardRegionFuncs), fehlend)
	}
}
