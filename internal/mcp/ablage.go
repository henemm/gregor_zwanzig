package mcp

// Ablage des OAuth-Servers (Issue #3281, ADR-0128). Vorbild: frieda-reist
// engine/konten.py (oauth_*), dort SQLite, hier Dateien unter GZ_DATA_DIR/mcp:
//
//	clients.json  per DCR registrierte Clients
//	tokens.json   Access- und Refresh-Tokens, NUR als sha256-Hash
//
// Authorization-Codes und Client-Dokumente (CIMD) liegen nur im Speicher;
// ein Neustart verliert sie (Codes leben 5 Minuten, Dokumente werden neu
// geholt). Eine prozessweite Sperre haelt jeden Lesen-Aendern-Schreiben-Zyklus
// zusammen (es laeuft genau ein gregor-api-Prozess je Umgebung, Muster
// internal/store/sessions_lock.go); geschrieben wird atomar.

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/fsmode"
	"github.com/henemm/gregor-api/internal/store"
)

// Laufzeiten wie Frieda (OAUTH_CODE_SEKUNDEN, ACCESS_SEKUNDEN, REFRESH_TAGE).
const (
	CodeSekunden    = 300
	AccessSekunden  = 3600
	RefreshTage     = 90
	dcrAufraeumTage = 7
)

var ablageSperre sync.Mutex

type clientEintrag struct {
	ClientID     string    `json:"client_id"`
	Name         string    `json:"name"`
	RedirectURIs []string  `json:"redirect_uris"`
	Art          string    `json:"art"` // "dcr" oder "cimd"
	Erstellt     time.Time `json:"erstellt"`
}

type tokenEintrag struct {
	Art      string     `json:"art"` // "access" oder "refresh"
	UserID   string     `json:"user_id"`
	ClientID string     `json:"client_id"`
	Scope    string     `json:"scope"`
	Familie  string     `json:"familie"`
	Ablauf   time.Time  `json:"ablauf"`
	Benutzt  *time.Time `json:"benutzt,omitempty"`
}

type codeEintrag struct {
	ClientID, RedirectURI, Challenge, Scope, UserID, Familie string
	Ablauf                                                   time.Time
	Benutzt                                                  bool
}

type clientDatei struct {
	Clients map[string]clientEintrag `json:"clients"`
}

type tokenDatei struct {
	Tokens map[string]tokenEintrag `json:"tokens"` // Schluessel: Hash
}

// Ablage haelt Clients, Tokens (Dateien) sowie Codes und CIMD (Speicher).
type Ablage struct {
	dir   string
	jetzt func() time.Time
	codes map[string]codeEintrag
	cimd  map[string]clientEintrag
}

func neueAblage(dataDir string, jetzt func() time.Time) *Ablage {
	return &Ablage{dir: filepath.Join(dataDir, "mcp"), jetzt: jetzt,
		codes: map[string]codeEintrag{}, cimd: map[string]clientEintrag{}}
}

func zufall(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err) // ohne Zufall kein sicherer Token
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// hashVon: sha256 ueber Art und Wert (wie Friedas _hash mit Trenner).
func hashVon(art, wert string) string {
	s := sha256.Sum256([]byte(art + "\x1f" + wert))
	return hex.EncodeToString(s[:])
}

func (a *Ablage) lesen(name string, ziel any) error {
	roh, err := os.ReadFile(filepath.Join(a.dir, name))
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	return json.Unmarshal(roh, ziel)
}

func (a *Ablage) schreiben(name string, wert any) error {
	if err := fsmode.MkdirAll(a.dir); err != nil {
		return err
	}
	roh, err := json.MarshalIndent(wert, "", "  ")
	if err != nil {
		return err
	}
	return store.WriteFileAtomic(filepath.Join(a.dir, name), roh)
}

func (a *Ablage) clientsLesen() (clientDatei, error) {
	f := clientDatei{Clients: map[string]clientEintrag{}}
	err := a.lesen("clients.json", &f)
	if f.Clients == nil {
		f.Clients = map[string]clientEintrag{}
	}
	return f, err
}

func (a *Ablage) tokensLesen() (tokenDatei, error) {
	f := tokenDatei{Tokens: map[string]tokenEintrag{}}
	err := a.lesen("tokens.json", &f)
	if f.Tokens == nil {
		f.Tokens = map[string]tokenEintrag{}
	}
	return f, err
}

// client liefert einen registrierten oder per CIMD geladenen Client.
func (a *Ablage) client(id string) (clientEintrag, bool) {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	if c, ok := a.cimd[id]; ok {
		return c, true
	}
	f, err := a.clientsLesen()
	if err != nil {
		return clientEintrag{}, false
	}
	c, ok := f.Clients[id]
	return c, ok
}

func (a *Ablage) cimdSpeichern(c clientEintrag) {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	if len(a.cimd) > 1000 {
		a.cimd = map[string]clientEintrag{}
	}
	a.cimd[c.ClientID] = c
}

// clientRegistrieren speichert einen DCR-Client und raeumt dabei Clients ab,
// die nach einer Woche weder Code noch Token haben (wie Frieda).
func (a *Ablage) clientRegistrieren(c clientEintrag) error {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	f, err := a.clientsLesen()
	if err != nil {
		return err
	}
	t, err := a.tokensLesen()
	if err != nil {
		return err
	}
	inGebrauch := map[string]bool{}
	for _, e := range t.Tokens {
		inGebrauch[e.ClientID] = true
	}
	for _, e := range a.codes {
		inGebrauch[e.ClientID] = true
	}
	grenze := a.jetzt().Add(-dcrAufraeumTage * 24 * time.Hour)
	for id, e := range f.Clients {
		if e.Art == "dcr" && e.Erstellt.Before(grenze) && !inGebrauch[id] {
			delete(f.Clients, id)
		}
	}
	f.Clients[c.ClientID] = c
	return a.schreiben("clients.json", f)
}

func (a *Ablage) codeAnlegen(clientID, redirectURI, challenge, scope, uid string) string {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	jetzt := a.jetzt()
	for h, c := range a.codes {
		if c.Ablauf.Before(jetzt) {
			delete(a.codes, h)
		}
	}
	code := zufall(32)
	a.codes[hashVon("code", code)] = codeEintrag{ClientID: clientID, RedirectURI: redirectURI, Challenge: challenge,
		Scope: scope, UserID: uid, Familie: zufall(8), Ablauf: jetzt.Add(CodeSekunden * time.Second)}
	return code
}

// TokenAntwort ist die Antwort von /token.
type TokenAntwort struct {
	AccessToken  string `json:"access_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
	RefreshToken string `json:"refresh_token"`
	Scope        string `json:"scope"`
}

func (a *Ablage) ausstellen(t *tokenDatei, uid, clientID, scope, familie string) TokenAntwort {
	jetzt := a.jetzt()
	for h, e := range t.Tokens {
		if e.Ablauf.Before(jetzt) {
			delete(t.Tokens, h)
		}
	}
	access, refresh := zufall(32), zufall(32)
	basis := tokenEintrag{UserID: uid, ClientID: clientID, Scope: scope, Familie: familie}
	acc, ref := basis, basis
	acc.Art, acc.Ablauf = "access", jetzt.Add(AccessSekunden*time.Second)
	ref.Art, ref.Ablauf = "refresh", jetzt.Add(RefreshTage*24*time.Hour)
	t.Tokens[hashVon("access", access)] = acc
	t.Tokens[hashVon("refresh", refresh)] = ref
	return TokenAntwort{AccessToken: access, TokenType: "Bearer", ExpiresIn: AccessSekunden, RefreshToken: refresh, Scope: scope}
}

func familieEntfernen(t *tokenDatei, familie string, nurArt string) {
	for h, e := range t.Tokens {
		if e.Familie == familie && (nurArt == "" || e.Art == nurArt) {
			delete(t.Tokens, h)
		}
	}
}

// codeEinloesen tauscht einen Code gegen Tokens (Friedas oauth_code_einloesen).
// pruefen(challenge) prueft den PKCE-Verifier, kontoOK(uid) Sperre und
// Freigabe. Jeder Versuch verbraucht den Code; ein zweites Einloesen
// widerruft alles, was aus ihm entstand.
func (a *Ablage) codeEinloesen(code, clientID, redirectURI string, pruefen func(string) bool, kontoOK func(string) bool) (TokenAntwort, bool) {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	h := hashVon("code", code)
	c, ok := a.codes[h]
	if !ok {
		return TokenAntwort{}, false
	}
	t, err := a.tokensLesen()
	if err != nil {
		return TokenAntwort{}, false
	}
	if c.Benutzt {
		familieEntfernen(&t, c.Familie, "")
		a.schreiben("tokens.json", t)
		return TokenAntwort{}, false
	}
	c.Benutzt = true
	a.codes[h] = c
	if c.Ablauf.Before(a.jetzt()) || c.ClientID != clientID || c.RedirectURI != redirectURI ||
		!pruefen(c.Challenge) || !kontoOK(c.UserID) {
		return TokenAntwort{}, false
	}
	antwort := a.ausstellen(&t, c.UserID, clientID, c.Scope, c.Familie)
	if a.schreiben("tokens.json", t) != nil {
		return TokenAntwort{}, false
	}
	return antwort, true
}

// erneuern loest einen Refresh-Token ein (Rotation). Ein schon rotierter
// Token gilt als gestohlen: die ganze Familie endet (Friedas oauth_erneuern).
func (a *Ablage) erneuern(refresh, clientID string, kontoOK func(string) bool) (TokenAntwort, bool) {
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	t, err := a.tokensLesen()
	if err != nil {
		return TokenAntwort{}, false
	}
	h := hashVon("refresh", refresh)
	e, ok := t.Tokens[h]
	if !ok || e.Art != "refresh" {
		return TokenAntwort{}, false
	}
	if e.Benutzt != nil {
		familieEntfernen(&t, e.Familie, "")
		a.schreiben("tokens.json", t)
		return TokenAntwort{}, false
	}
	jetzt := a.jetzt()
	if e.Ablauf.Before(jetzt) || e.ClientID != clientID || !kontoOK(e.UserID) {
		return TokenAntwort{}, false
	}
	e.Benutzt = &jetzt
	t.Tokens[h] = e
	familieEntfernen(&t, e.Familie, "access")
	antwort := a.ausstellen(&t, e.UserID, clientID, e.Scope, e.Familie)
	if a.schreiben("tokens.json", t) != nil {
		return TokenAntwort{}, false
	}
	return antwort, true
}

// accessNutzer liefert die Kennung zu einem gueltigen Access-Token.
func (a *Ablage) accessNutzer(access string) (string, bool) {
	if len(access) < 20 || len(access) > 200 {
		return "", false
	}
	ablageSperre.Lock()
	defer ablageSperre.Unlock()
	t, err := a.tokensLesen()
	if err != nil {
		return "", false
	}
	e, ok := t.Tokens[hashVon("access", access)]
	if !ok || e.Art != "access" || e.Ablauf.Before(a.jetzt()) || e.UserID == "" {
		return "", false
	}
	return e.UserID, true
}
