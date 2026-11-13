package handler

// Mengenbremsen je Nutzer fuer interaktive Ausloeser (Issue #2961, ADR-0114
// Punkt 3). Ein gleitendes Zeitfenster je Nutzerkennung, optional mit einer
// Obergrenze gleichzeitig laufender Anfragen (geteilt ueber mehrere Bremsen).
//
// Ausgenommen sind Admins und die Kennungen aus GZ_QUOTA_EXEMPT_USER_IDS —
// dieselbe Policy wie die Mengen-Quoten (QuotaPolicyMiddleware, Issue #2482),
// gelesen aus dem Request-Kontext. Im Fixture-Modus (CI/E2E) haengt der
// Router die Bremsen gar nicht erst ein (router.go).
//
// Der Zustand liegt im Arbeitsspeicher und ueberlebt keinen Neustart —
// Neustarts sind nicht nutzergesteuert (Muster MailFloodLimiter).

import (
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/middleware"
)

// NutzerParallel zaehlt gleichzeitig laufende Anfragen je Nutzer; mehrere
// Bremsen koennen sich eine Instanz teilen.
type NutzerParallel struct {
	mu      sync.Mutex
	max     int
	laufend map[string]int
}

// NewNutzerParallel: hoechstens max gleichzeitige Anfragen je Nutzer.
func NewNutzerParallel(max int) *NutzerParallel {
	return &NutzerParallel{max: max, laufend: make(map[string]int)}
}

func (p *NutzerParallel) belegen(uid string) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.laufend[uid] >= p.max {
		return false
	}
	p.laufend[uid]++
	return true
}

func (p *NutzerParallel) freigeben(uid string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.laufend[uid] <= 1 {
		delete(p.laufend, uid)
		return
	}
	p.laufend[uid]--
}

// NutzerBremse laesst je Nutzer hoechstens limit Anfragen pro gleitendem
// Fenster zu. variante waehlt den Katalogtext fach.fehler.rate_limit_exceeded_<variante>.
type NutzerBremse struct {
	mu       sync.Mutex
	limit    int
	fenster  time.Duration
	variante string
	parallel *NutzerParallel
	jetzt    func() time.Time
	treffer  map[string][]time.Time
}

// bremsenUhr ist die Zeitquelle aller Nutzer-Bremsen; nur SetBremsenUhr
// (Testnaht) ersetzt sie.
var (
	bremsenUhrMu sync.Mutex
	bremsenUhrFn = time.Now
)

func bremsenUhr() time.Time {
	bremsenUhrMu.Lock()
	f := bremsenUhrFn
	bremsenUhrMu.Unlock()
	return f()
}

// SetBremsenUhr ersetzt die Zeitquelle der Nutzer-Bremsen (Testnaht, Muster
// store.SetBriefingLockTimeout) und liefert die Rueckstell-Funktion. Sie
// aendert keine Grenze und kann keine Bremse abschalten.
func SetBremsenUhr(f func() time.Time) (restore func()) {
	bremsenUhrMu.Lock()
	alt := bremsenUhrFn
	bremsenUhrFn = f
	bremsenUhrMu.Unlock()
	return func() {
		bremsenUhrMu.Lock()
		bremsenUhrFn = alt
		bremsenUhrMu.Unlock()
	}
}

// NewNutzerBremse baut eine Bremse; parallel darf nil sein.
func NewNutzerBremse(variante string, limit int, fenster time.Duration, parallel *NutzerParallel) *NutzerBremse {
	return &NutzerBremse{
		limit: limit, fenster: fenster, variante: variante, parallel: parallel,
		jetzt: func() time.Time { return bremsenUhr() }, treffer: make(map[string][]time.Time),
	}
}

// zulassen verbucht einen Treffer, wenn das Fenster Platz hat; sonst liefert
// es die Wartezeit bis zum Freiwerden des aeltesten Treffers.
func (b *NutzerBremse) zulassen(uid string) (bool, time.Duration) {
	b.mu.Lock()
	defer b.mu.Unlock()
	now := b.jetzt()
	grenze := now.Add(-b.fenster)
	alt := b.treffer[uid]
	i := 0
	for i < len(alt) && !alt[i].After(grenze) {
		i++
	}
	frisch := alt[i:]
	if len(frisch) >= b.limit {
		b.treffer[uid] = frisch
		return false, frisch[0].Add(b.fenster).Sub(now)
	}
	b.treffer[uid] = append(frisch, now)
	return true, 0
}

// retryAfterSekunden rundet auf volle Sekunden auf, mindestens 1.
func retryAfterSekunden(d time.Duration) string {
	s := int((d + time.Second - 1) / time.Second)
	if s < 1 {
		s = 1
	}
	return strconv.Itoa(s)
}

func (b *NutzerBremse) ablehnen(w http.ResponseWriter, r *http.Request, warten time.Duration, variante string) {
	w.Header().Set("Retry-After", retryAfterSekunden(warten))
	WriteError(w, r, http.StatusTooManyRequests, "rate_limit_exceeded", i18n.Args{"variante": variante})
}

// NutzerBremsen buendelt die Bremsen der Router-Routen (Issue #2961).
// aus=true (Fixture-Modus des CI-Stacks) laesst jede Route ungebremst.
type NutzerBremsen struct {
	aus           bool
	aufloesen     *NutzerBremse
	testnachricht *NutzerBremse
	versand       *NutzerBremse
	vergleich     *NutzerBremse
	etappenwetter *NutzerBremse
	vorschau      *NutzerBremse
	gpx           *NutzerBremse
}

// Grenzwerte der Bremsen (Spec security_haertung_2026_11_go_schnittstellen.md).
const (
	BremseAufloesenJeMinute     = 30
	BremseTestnachrichtJeStunde = 10
	BremseVersandJeStunde       = 20
	BremseAbrufJeMinute         = 60
	BremseAbrufParallel         = 4
	BremseGpxJeStunde           = 30
)

// BremseStagingFaktor vervielfacht auf Staging (GZ_ENV=staging) alle Grenzen
// — Fenster UND Gleichzeitigkeit —, damit E2E-Laeufe und Validator-Skripte
// ohne Eintrag in GZ_QUOTA_EXEMPT_USER_IDS nicht in die Bremse laufen.
const BremseStagingFaktor = 10

// NeueNutzerBremsen baut alle Bremsen. Der Handversand (drei Routen) teilt
// sich EIN Kontingent; die schweren Lesewege teilen sich die Obergrenze
// gleichzeitiger Anfragen, haben aber je ein eigenes Minutenfenster.
// aus=true: Fixture-Modus, keine Bremse. staging=true: Grenzen mal
// BremseStagingFaktor. Produktion: Grenzen wie dokumentiert.
func NeueNutzerBremsen(aus, staging bool) *NutzerBremsen {
	f := 1
	if staging {
		f = BremseStagingFaktor
	}
	parallel := NewNutzerParallel(BremseAbrufParallel * f)
	return &NutzerBremsen{
		aus:           aus,
		aufloesen:     NewNutzerBremse("aufloesen", BremseAufloesenJeMinute*f, time.Minute, nil),
		testnachricht: NewNutzerBremse("testnachricht", BremseTestnachrichtJeStunde*f, time.Hour, nil),
		versand:       NewNutzerBremse("versand", BremseVersandJeStunde*f, time.Hour, nil),
		vergleich:     NewNutzerBremse("abruf", BremseAbrufJeMinute*f, time.Minute, parallel),
		etappenwetter: NewNutzerBremse("abruf", BremseAbrufJeMinute*f, time.Minute, parallel),
		vorschau:      NewNutzerBremse("abruf", BremseAbrufJeMinute*f, time.Minute, parallel),
		gpx:           NewNutzerBremse("gpx", BremseGpxJeStunde*f, time.Hour, nil),
	}
}

func (n *NutzerBremsen) legeUm(b *NutzerBremse, h http.HandlerFunc) http.HandlerFunc {
	if n.aus {
		return h
	}
	return b.Wrap(h)
}

// Aufloesen: POST /api/locations/resolve.
func (n *NutzerBremsen) Aufloesen(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.aufloesen, h)
}

// Testnachricht: POST /api/notify/test.
func (n *NutzerBremsen) Testnachricht(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.testnachricht, h)
}

// Versand: Handversand (Trip, Ortsvergleich, kind-neutral) — gemeinsames Kontingent.
func (n *NutzerBremsen) Versand(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.versand, h)
}

// Vergleich: GET /api/compare.
func (n *NutzerBremsen) Vergleich(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.vergleich, h)
}

// Etappenwetter: GET /api/trips/{id}/stages/weather.
func (n *NutzerBremsen) Etappenwetter(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.etappenwetter, h)
}

// Vorschau: SMS-Vorschau und beide Alarm-Vorschau-Routen (gemeinsam).
func (n *NutzerBremsen) Vorschau(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.vorschau, h)
}

// Gpx: POST /api/gpx/parse.
func (n *NutzerBremsen) Gpx(h http.HandlerFunc) http.HandlerFunc {
	return n.legeUm(n.gpx, h)
}

// Wrap legt die Bremse um einen Handler.
func (b *NutzerBremse) Wrap(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		uid := middleware.UserIDFromContext(r.Context())
		// Ohne Kennung entscheidet der Handler selbst (401); Admins und die
		// Ausnahme-Liste sind unbegrenzt.
		if uid == "" || quotaUnlimited(r.Context(), uid) {
			next(w, r)
			return
		}
		if b.parallel != nil {
			if !b.parallel.belegen(uid) {
				b.ablehnen(w, r, time.Second, "parallel")
				return
			}
			defer b.parallel.freigeben(uid)
		}
		if ok, warten := b.zulassen(uid); !ok {
			b.ablehnen(w, r, warten, b.variante)
			return
		}
		next(w, r)
	}
}
