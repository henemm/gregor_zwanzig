package i18n

import (
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"log"
	"path"
	"regexp"
	"sort"
	"strings"
	"sync"
)

//go:embed messages
var embedded embed.FS

var (
	keyRe         = regexp.MustCompile(`^[a-z0-9_.]+$`)
	bereichRe     = regexp.MustCompile(`^[a-z0-9_]+$`)
	placeholderRe = regexp.MustCompile(`\{([a-z0-9_]+)\}`)
)

// Catalog haelt alle Texte je Sprache. Nach NewCatalog unveraenderlich; nur
// das Fallback-Log (logged) wird beschrieben und ist nebenlaeufig sicher.
type Catalog struct {
	texts  map[Lang]map[string]string
	areas  map[Lang]map[string][]string // Sprache -> Bereich -> Schluessel
	logged sync.Map
}

// NewCatalog laedt alle messages/<lang>/<bereich>.json aus fsys und prueft
// jeden Schluessel (Zeichen, 2-4 Segmente, Praefix <bereich>.).
func NewCatalog(fsys fs.FS) (*Catalog, error) {
	c := &Catalog{
		texts: map[Lang]map[string]string{De: {}, En: {}},
		areas: map[Lang]map[string][]string{De: {}, En: {}},
	}
	err := fs.WalkDir(fsys, "messages", func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		return c.loadFile(fsys, p)
	})
	if err != nil {
		return nil, err
	}
	return c, nil
}

func (c *Catalog) loadFile(fsys fs.FS, p string) error {
	parts := strings.Split(p, "/")
	if len(parts) != 3 || path.Ext(p) != ".json" {
		return fmt.Errorf("i18n: %s: erwartet messages/<lang>/<bereich>.json", p)
	}
	lang, bereich := Lang(parts[1]), strings.TrimSuffix(parts[2], ".json")
	if (lang != De && lang != En) || !bereichRe.MatchString(bereich) {
		return fmt.Errorf("i18n: %s: unbekannte Sprache oder ungueltiger Bereich", p)
	}
	data, err := fs.ReadFile(fsys, p)
	if err != nil {
		return fmt.Errorf("i18n: %s: %w", p, err)
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		return fmt.Errorf("i18n: %s: kein flaches {\"schluessel\": \"Text\"}: %w", p, err)
	}
	keys := make([]string, 0, len(m))
	for k, v := range m {
		if err := checkKey(k, bereich); err != nil {
			return fmt.Errorf("i18n: %s: %w", p, err)
		}
		c.texts[lang][k] = v
		keys = append(keys, k)
	}
	sort.Strings(keys)
	c.areas[lang][bereich] = keys
	return nil
}

func checkKey(k, bereich string) error {
	segs := strings.Count(k, ".") + 1
	if !keyRe.MatchString(k) || segs < 2 || segs > 4 || !strings.HasPrefix(k, bereich+".") {
		return fmt.Errorf("ungueltiger Schluessel %q (nur [a-z0-9_.], 2-4 Segmente, Praefix %s.)", k, bereich)
	}
	for _, s := range strings.Split(k, ".") {
		if s == "" {
			return fmt.Errorf("ungueltiger Schluessel %q (leeres Segment)", k)
		}
	}
	return nil
}

// Has meldet, ob key im de-Katalog vorhanden ist.
func (c *Catalog) Has(key string) bool {
	_, ok := c.texts[De][key]
	return ok
}

// T liefert den Text zu key: lang, sonst de (mit einmaligem Log), sonst key.
func (c *Catalog) T(lang Lang, key string, args Args) string {
	return fill(c.lookup(Parse(string(lang)), key), args)
}

// Tn waehlt die Pluralform und setzt {count}; args des Aufrufers bleiben unberuehrt.
func (c *Catalog) Tn(lang Lang, key string, count int, args Args) string {
	form := ".other"
	if count == 1 {
		form = ".one"
	}
	merged := make(Args, len(args)+1)
	for k, v := range args {
		merged[k] = v
	}
	merged["count"] = count
	return c.T(lang, key+form, merged)
}

func (c *Catalog) lookup(lang Lang, key string) string {
	if t, ok := c.texts[lang][key]; ok {
		return t
	}
	if _, seen := c.logged.LoadOrStore(key, true); !seen {
		log.Printf("i18n fallback: %s", key)
	}
	if t, ok := c.texts[De][key]; ok {
		return t
	}
	return key
}

func fill(text string, args Args) string {
	if len(args) == 0 {
		return text
	}
	return placeholderRe.ReplaceAllStringFunc(text, func(m string) string {
		if v, ok := args[m[1:len(m)-1]]; ok {
			return fmt.Sprint(v)
		}
		return m
	})
}

func placeholders(text string) string {
	set := map[string]bool{}
	for _, m := range placeholderRe.FindAllStringSubmatch(text, -1) {
		set[m[1]] = true
	}
	names := make([]string, 0, len(set))
	for n := range set {
		names = append(names, n)
	}
	sort.Strings(names)
	return strings.Join(names, ",")
}

// Parity prueft je Bereich gleiche Schluesselmengen und Platzhalter in de und
// en sowie, dass ein Fehlercode in hoechstens einem Fehler-Bereich steht.
func (c *Catalog) Parity() error {
	var errs []string
	for _, pair := range [][2]Lang{{De, En}, {En, De}} {
		a, b := pair[0], pair[1]
		for bereich, keys := range c.areas[a] {
			if _, ok := c.areas[b][bereich]; !ok {
				errs = append(errs, fmt.Sprintf("Bereich %s fehlt in %s", bereich, b))
			}
			for _, k := range keys {
				if _, ok := c.texts[b][k]; !ok {
					errs = append(errs, fmt.Sprintf("Schluessel %s fehlt in %s", k, b))
				}
			}
		}
	}
	for k, de := range c.texts[De] {
		if en, ok := c.texts[En][k]; ok && placeholders(de) != placeholders(en) {
			errs = append(errs, fmt.Sprintf("Schluessel %s: Platzhalter de {%s} != en {%s}", k, placeholders(de), placeholders(en)))
		}
	}
	errs = append(errs, c.duplicateCodes()...)
	if len(errs) == 0 {
		return nil
	}
	sort.Strings(errs)
	return errors.New("i18n Paritaet: " + strings.Join(errs, "; "))
}

func (c *Catalog) duplicateCodes() []string {
	var errs []string
	seen := map[string]string{}
	for _, lang := range []Lang{De, En} {
		for k := range c.texts[lang] {
			for _, p := range errorPrefixes {
				code, ok := strings.CutPrefix(k, p)
				if !ok {
					continue
				}
				if prev, dup := seen[code]; dup && prev != p {
					errs = append(errs, fmt.Sprintf("Fehlercode %s doppelt in %s und %s", code, prev, p))
				}
				seen[code] = p
			}
		}
	}
	return errs
}
