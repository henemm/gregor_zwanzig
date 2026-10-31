// Package i18n ist der Go-Weg der Zweisprachigkeit (ADR-0104, Issue #2675):
// eingebettete Kataloge je Sprache und Bereich, T/Tn mit {name}-Platzhaltern,
// Sprachaufloesung je Anfrage und das Fehlerobjekt {code, message}.
//
// Es gibt keinen globalen Sprachzustand: die Sprache reist im Request-Kontext
// (WithLang/FromContext) oder als Parameter.
package i18n

// Lang ist eine der zwei Sprachen der Anwendung.
type Lang string

const (
	De Lang = "de"
	En Lang = "en"
)

// CookieName ist das Sprach-Cookie (Konventionen Abschnitt 1).
const CookieName = "gz_lang"

// Args sind die Platzhalter-Werte eines Textes ({name} -> Args["name"]).
type Args map[string]any

// Default ist der eingebettete Standardkatalog.
var Default *Catalog

func init() {
	c, err := NewCatalog(embedded)
	if err != nil {
		// Ein kaputter Einbettungs-Stand ist ein Programmierfehler.
		panic(err)
	}
	Default = c
}

// Parse: "en" -> En, alles andere -> De.
func Parse(s string) Lang {
	if s == string(En) {
		return En
	}
	return De
}

// T liefert den Text zu key in lang aus dem Standardkatalog.
func T(lang Lang, key string, args Args) string { return Default.T(lang, key, args) }

// Tn waehlt key+".one" bei count==1, sonst key+".other"; {count} ist implizit.
func Tn(lang Lang, key string, count int, args Args) string {
	return Default.Tn(lang, key, count, args)
}

// Has meldet, ob key im de-Katalog vorhanden ist.
func Has(key string) bool { return Default.Has(key) }

// ErrorBody baut das Fehlerobjekt aus dem Standardkatalog (siehe Catalog.ErrorBody).
func ErrorBody(lang Lang, code string, args Args) map[string]any {
	return Default.ErrorBody(lang, code, args)
}
