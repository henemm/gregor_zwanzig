package mcp

// Autorisierung mit Zustimmungsseite (Friedas autorisieren/zustimmung). Der
// Anmeldeschritt nutzt Gregors Sitzung: ohne gz_session geht es auf
// /login?redirect=<authorize-Pfad>, die Anmeldeseite springt danach per
// Vollnavigation zurueck. Fehler vor der Pruefung der Redirect-URI gehen nie
// an die Redirect-URI.

import (
	"context"
	"html/template"
	"net/http"
	"net/url"
	"strings"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/i18n"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

var felder = []string{"response_type", "client_id", "redirect_uri", "code_challenge", "code_challenge_method", "state", "scope", "resource"}

// anfragePruefen -> (Client, "") oder (_, Katalogschluessel des Fehlers).
func (h *Handler) anfragePruefen(ctx context.Context, q url.Values) (clientEintrag, string) {
	c, ok := h.clientFinden(ctx, q.Get("client_id"))
	switch {
	case !ok:
		return c, "mcp.oauth.unbekannter_client"
	case !redirectPasst(c.RedirectURIs, q.Get("redirect_uri")):
		return c, "mcp.oauth.ruecksprung"
	case q.Get("response_type") != "code":
		return c, "mcp.oauth.nur_code"
	case q.Get("code_challenge_method") != "S256" || !challengeMuster.MatchString(q.Get("code_challenge")):
		return c, "mcp.oauth.pkce"
	case q.Get("resource") != "" && strings.TrimRight(q.Get("resource"), "/") != h.ressource():
		return c, "mcp.oauth.ressource"
	case len(q.Get("state")) > 500:
		return c, "mcp.oauth.state_lang"
	}
	return c, ""
}

func scopeVon(q url.Values) string {
	gewuenscht := map[string]bool{}
	for _, s := range strings.Fields(q.Get("scope")) {
		gewuenscht[s] = true
	}
	teile := []string{scopes[0]}
	for _, s := range scopes[1:] {
		if gewuenscht[s] {
			teile = append(teile, s)
		}
	}
	return strings.Join(teile, " ")
}

func zielMit(uri string, werte ...[2]string) string {
	u, _ := url.Parse(uri)
	q := u.Query()
	for _, w := range werte {
		if w[1] != "" {
			q.Add(w[0], w[1])
		}
	}
	u.RawQuery, u.Fragment = q.Encode(), ""
	return u.String()
}

func cspFuer(uri string) string {
	ziel := "http://localhost:* http://127.0.0.1:*"
	if !loopback(uri) {
		u, _ := url.Parse(uri)
		ziel = u.Scheme + "://" + u.Host
	}
	return "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' " + ziel +
		"; frame-ancestors 'none'; base-uri 'none'"
}

// sitzungNutzer liest die Kennung aus gz_session (Gaesteliste wie AuthMiddleware).
func (h *Handler) sitzungNutzer(r *http.Request) string {
	c, err := r.Cookie("gz_session")
	if err != nil {
		return ""
	}
	uid, sid, ok := authmw.SessionFromCookie(c.Value, h.o.SessionSecret)
	if !ok {
		return ""
	}
	if gelistet, err := h.o.Nutzer.HasSession(uid, sid); err != nil || !gelistet {
		return ""
	}
	return uid
}

func (h *Handler) herkunftOK(r *http.Request) bool {
	eigene := config.NormalizeOrigin(h.basis)
	return eigene != "" && config.NormalizeOrigin(r.Header.Get("Origin")) == eigene
}

// zurAnmeldung: 302 auf die Anmeldeseite, Ruecksprung = authorize-Pfad mit
// den geprueften OAuth-Feldern (relativ, passt durch safeRedirectPath).
func zurAnmeldung(w http.ResponseWriter, r *http.Request, q url.Values) {
	weiter := url.Values{}
	for _, f := range felder {
		if q.Get(f) != "" {
			weiter.Set(f, q.Get(f))
		}
	}
	http.Redirect(w, r, "/login?redirect="+url.QueryEscape(AuthorizePfad+"?"+weiter.Encode()), http.StatusFound)
}

// Autorisieren: GET zeigt die Zustimmung, POST erzeugt den Code.
func (h *Handler) Autorisieren(w http.ResponseWriter, r *http.Request) {
	uid := h.sitzungNutzer(r)
	lang := i18n.FromRequest(r, nil)
	if uid != "" {
		if u, err := h.o.Nutzer.LoadUser(uid); err == nil && u != nil {
			lang = i18n.FromRequest(r, u)
		}
	}
	q := r.URL.Query()
	if r.Method == http.MethodPost {
		if !h.herkunftOK(r) || r.ParseForm() != nil {
			h.fehlerseite(w, http.StatusForbidden, lang, "mcp.oauth.nicht_erlaubt", "mcp.oauth.nicht_erlaubt")
			return
		}
		q = r.PostForm
	}
	c, fehler := h.anfragePruefen(r.Context(), q)
	if fehler != "" {
		h.fehlerseite(w, http.StatusBadRequest, lang, "mcp.oauth.nicht_moeglich", fehler)
		return
	}
	if uid == "" {
		zurAnmeldung(w, r, q)
		return
	}
	konto, ok := h.konto(uid)
	if !ok {
		h.fehlerseite(w, http.StatusForbidden, lang, "mcp.oauth.nicht_moeglich", "mcp.oauth.nicht_freigegeben")
		return
	}
	redirect := q.Get("redirect_uri")
	w.Header().Set("Content-Security-Policy", cspFuer(redirect))
	if r.Method == http.MethodGet {
		h.zustimmung(w, lang, q, c, konto)
		return
	}
	iss := [2]string{"iss", h.basis}
	state := [2]string{"state", q.Get("state")}
	if q.Get("aktion") != "erlauben" {
		http.Redirect(w, r, zielMit(redirect, [2]string{"error", "access_denied"}, state, iss), http.StatusSeeOther)
		return
	}
	code := h.ablage.codeAnlegen(c.ClientID, redirect, q.Get("code_challenge"), scopeVon(q), uid)
	http.Redirect(w, r, zielMit(redirect, [2]string{"code", code}, state, iss), http.StatusSeeOther)
}

// ---------------------------------------------------------------- Seiten

type seitenDaten struct {
	Sprache, Titel, Ueberschrift, Text, Hinweis string
	Formular                                    bool
	AngemeldetAls, Darf, DarfWetter, DarfNicht  string
	WeiterZu, Warnung, Erlauben, Abbrechen      string
	Aktion                                      string
	Felder                                      [][2]string
}

var seite = template.Must(template.New("seite").Parse(`<!doctype html>
<html lang="{{.Sprache}}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{{.Titel}}</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;background:#fff;color:#111;max-width:34rem;margin:2rem auto;padding:0 1rem;line-height:1.5}
h1{font-size:1.4rem}.kasten{border:2px solid #111;border-radius:.5rem;padding:.8rem}.warnung{border:2px solid #9b0000;color:#9b0000;border-radius:.5rem;padding:.8rem}
button{font:inherit;font-weight:600;padding:.7rem 1.4rem;border-radius:.5rem;border:2px solid #111;cursor:pointer;margin-top:.6rem}
.ja{background:#111;color:#fff}.nein{background:#fff;color:#111}</style></head>
<body><main><h1>{{.Ueberschrift}}</h1>
{{if .Formular}}<p>{{.AngemeldetAls}}</p>
<p><strong>{{.Darf}}</strong></p><ul><li>{{.DarfWetter}}</li></ul><p>{{.DarfNicht}}</p>
<p class="kasten">{{.WeiterZu}}</p>{{if .Warnung}}<p class="warnung">{{.Warnung}}</p>{{end}}
<form method="post" action="{{.Aktion}}">{{range .Felder}}<input type="hidden" name="{{index . 0}}" value="{{index . 1}}">{{end}}<input type="hidden" name="aktion" value="erlauben"><button class="ja" type="submit">{{.Erlauben}}</button></form>
<form method="post" action="{{.Aktion}}">{{range .Felder}}<input type="hidden" name="{{index . 0}}" value="{{index . 1}}">{{end}}<input type="hidden" name="aktion" value="abbrechen"><button class="nein" type="submit">{{.Abbrechen}}</button></form>
{{else}}<p class="warnung">{{.Text}}</p>{{if .Hinweis}}<p>{{.Hinweis}}</p>{{end}}{{end}}
</main></body></html>`))

func seiteSenden(w http.ResponseWriter, status int, d seitenDaten) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Frame-Options", "DENY")
	if w.Header().Get("Content-Security-Policy") == "" {
		w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'")
	}
	w.WriteHeader(status)
	seite.Execute(w, d)
}

func (h *Handler) fehlerseite(w http.ResponseWriter, status int, lang i18n.Lang, titel, text string) {
	d := seitenDaten{Sprache: string(lang), Titel: i18n.T(lang, titel, nil), Ueberschrift: i18n.T(lang, titel, nil),
		Text: i18n.T(lang, text, nil)}
	if status == http.StatusBadRequest {
		d.Hinweis = i18n.T(lang, "mcp.oauth.neu_verbinden", nil)
	}
	seiteSenden(w, status, d)
}

func (h *Handler) zustimmung(w http.ResponseWriter, lang i18n.Lang, q url.Values, c clientEintrag, k *model.User) {
	t := func(key string, a i18n.Args) string { return i18n.T(lang, key, a) }
	ziel, _ := url.Parse(q.Get("redirect_uri"))
	// Wer fragt: bei einem Client-Dokument dessen Host, sonst der Name, den
	// das Programm selbst angibt (darum in Anfuehrungszeichen).
	wer := c.Name
	if c.Art == "cimd" {
		if u, err := url.Parse(c.ClientID); err == nil {
			wer = u.Hostname()
		}
	}
	frage := t("mcp.oauth.frage_ohne_name", nil)
	if wer != "" {
		frage = t("mcp.oauth.frage", i18n.Args{"wer": wer})
	}
	name := k.DisplayName
	if name == "" {
		name = k.Email
	}
	if name == "" {
		name = k.ID
	}
	d := seitenDaten{Sprache: string(lang), Titel: t("mcp.oauth.titel", nil), Ueberschrift: frage, Formular: true,
		AngemeldetAls: t("mcp.oauth.angemeldet_als", i18n.Args{"name": name}), Darf: t("mcp.oauth.darf", nil),
		DarfWetter: t("mcp.oauth.darf_wetter", nil), DarfNicht: t("mcp.oauth.darf_nicht", nil),
		WeiterZu: t("mcp.oauth.weiter_zu", i18n.Args{"host": ziel.Hostname()}), Erlauben: t("mcp.oauth.erlauben", nil),
		Abbrechen: t("mcp.oauth.abbrechen", nil), Aktion: AuthorizePfad}
	if loopback(q.Get("redirect_uri")) {
		d.Warnung = t("mcp.oauth.warnung_localhost", nil)
	}
	for _, f := range felder {
		d.Felder = append(d.Felder, [2]string{f, q.Get(f)})
	}
	seiteSenden(w, http.StatusOK, d)
}
