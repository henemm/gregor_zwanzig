package i18n

import (
	"context"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

type ctxKey struct{}

// FromContext liefert die Sprache der Anfrage; ohne Eintrag De.
func FromContext(ctx context.Context) Lang {
	if l, ok := ctx.Value(ctxKey{}).(Lang); ok {
		return l
	}
	return De
}

// WithLang legt die Sprache in den Kontext (unbekannte Werte werden De).
func WithLang(ctx context.Context, lang Lang) context.Context {
	return context.WithValue(ctx, ctxKey{}, Parse(string(lang)))
}

// FromRequest loest die Sprache auf (ADR-0104, Konventionen Abschnitt 1):
// gespeicherte Nutzersprache > Cookie gz_lang > Accept-Language > De.
// Ungueltige Werte (Nutzerfeld, Cookie) werden uebersprungen, nicht als De gewertet.
func FromRequest(r *http.Request, user *model.User) Lang {
	if user != nil && model.IsValidLanguage(user.Language) {
		return Lang(user.Language)
	}
	if c, err := r.Cookie(CookieName); err == nil && model.IsValidLanguage(c.Value) {
		return Lang(c.Value)
	}
	if l, ok := fromAcceptLanguage(r.Header.Get("Accept-Language")); ok {
		return l
	}
	return De
}

type langPref struct {
	primary string
	q       float64
}

// fromAcceptLanguage: Eintraege nach q absteigend (Standard 1, q=0 und
// unlesbare q ignoriert); erster Eintrag mit Hauptsprache de oder en gewinnt.
func fromAcceptLanguage(header string) (Lang, bool) {
	var prefs []langPref
	for _, entry := range strings.Split(header, ",") {
		tag, params, _ := strings.Cut(entry, ";")
		primary, _, _ := strings.Cut(strings.ToLower(strings.TrimSpace(tag)), "-")
		q, ok := parseQ(params)
		if primary == "" || !ok || q <= 0 {
			continue
		}
		prefs = append(prefs, langPref{primary, q})
	}
	sort.SliceStable(prefs, func(i, j int) bool { return prefs[i].q > prefs[j].q })
	for _, p := range prefs {
		if model.IsValidLanguage(p.primary) {
			return Lang(p.primary), true
		}
	}
	return "", false
}

func parseQ(params string) (float64, bool) {
	for _, p := range strings.Split(params, ";") {
		name, val, found := strings.Cut(strings.TrimSpace(p), "=")
		if !found || strings.TrimSpace(name) != "q" {
			continue
		}
		q, err := strconv.ParseFloat(strings.TrimSpace(val), 64)
		return q, err == nil
	}
	return 1, true
}
