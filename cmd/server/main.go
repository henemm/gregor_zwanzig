package main

import (
	"fmt"
	"log"
	"net/http"
	"sort"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/egress"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/provider/fixture"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// gitCommit is injected at build time via -ldflags "-X main.gitCommit=<sha>".
var gitCommit = "dev"

// installGuards installiert die Transport-Waechter in der verbindlichen
// Reihenfolge (Issue #2142, AC-4): ZUERST coreauth.Install, DANACH
// egress.Install. egress.Install merkt sich den beim Aufruf vorgefundenen
// Transport und stellt ihn bei Uninstall zeiger-identisch wieder her; liefe
// coreauth.Install danach, ginge der Auth-Header bei einem egress.Uninstall()
// still verloren und der Python-Core wiese ab Scheibe 2 jede Anfrage mit 401
// ab. main() ruft ausschliesslich diese Funktion — die Reihenfolge steht
// damit an genau einer Stelle und ist ueber main_test.go pruefbar.
func installGuards(cfg *config.Config) {
	coreauth.Install(cfg)
	egress.Install(cfg)
}

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	// Issue #2139 — Session-Secret Fail-Fast: ein leeres, unveraendertes oder
	// zu kurzes Secret erlaubt selbst signierte Session-Cookies.
	if err := config.ValidateSessionSecret(cfg); err != nil {
		log.Fatalf("session secret invalid: %v", err)
	}

	// Issue #2142 — Core-Shared-Secret Fail-Fast: ohne Geheimnis sendet die
	// Go-API keinen Auth-Header und der Python-Core riegelt jede Anfrage ab.
	if err := config.ValidateCoreSharedSecret(cfg); err != nil {
		log.Fatalf("core shared secret invalid: %v", err)
	}

	// Issue #2142 F002 — Reihenfolge der Transport-Waechter steht an genau
	// dieser einen Stelle; installGuards() ist auch der Pruefling von
	// cmd/server/main_test.go (AC-4).
	installGuards(cfg)

	srv, cleanup, err := buildServer(cfg)
	if err != nil {
		log.Fatalf("%v", err)
	}
	defer cleanup()

	log.Printf("Go API listening on %s:%s, proxying to %s", cfg.Host, cfg.Port, cfg.PythonCoreURL)
	if err := srv.ListenAndServe(); err != nil {
		log.Printf("http server stopped: %v", err)
	}
}

// buildServer baut alles zwischen Konfiguration und Lauschen auf: Store,
// Seed-Konto, Startwarnungen, Provider, WebAuthn, Scheduler, Router und den
// http.Server mit Zeitgrenzen (Issue #2961: eigene Funktion, damit ein Test
// belegt, dass der Start genau diese Teile benutzt). cleanup beendet Reaper
// und Scheduler.
func buildServer(cfg *config.Config) (*http.Server, func(), error) {
	var stops []func()
	cleanup := func() {
		for i := len(stops) - 1; i >= 0; i-- {
			stops[i]()
		}
	}

	s := store.New(cfg.DataDir, cfg.UserID)
	// Issue #2147 Scheibe C (AC-16/AC-17): Bestandsduplikate von E-Mail-Adressen
	// nur messen, nur Zahlen ins Log; fail-soft, der Start laeuft immer weiter.
	s.LogAddressCollisions()
	telegramTokenStore := handler.NewTelegramTokenStore(cfg.DataDir)
	inviteStore := store.NewInviteStore(cfg.DataDir) // Issue #2519
	// Issue #2160 AC-15: Reaper fuer Login-OTPs, Lösch-Codes und
	// Telegram-Tokens — bewusst hier, nicht in den Konstruktoren.
	stops = append(stops, handler.StartStoreReaper(telegramTokenStore, s, time.Minute))
	// Issue #2154 Scheibe A: eine Bremse fuer den ganzen Prozess — der
	// Lernaufruf kommt immer von localhost, ein Zaehler je IP/Nummer/Konto
	// waere wirkungslos bzw. missbrauchbar (Spec D5).
	premiumSmsRateLimiter := handler.NewPremiumSmsRateLimiter(handler.DefaultPremiumSmsLinkCodeBudget)

	// Seed-Konto aus ENV-Zugangsdaten beim ersten Start. Fehler sind in
	// seedAdminUser bereits geloggt; der Start laeuft bewusst weiter (#2151 B).
	_ = seedAdminUser(s, cfg)
	// Issue #2961: privilegierte Kennungen ohne Konto sichtbar machen.
	warnPrivilegedIDsWithoutAccount(s, cfg)

	var weatherProvider provider.WeatherProvider
	if cfg.TestFixtureDir != "" {
		weatherProvider = fixture.NewProvider(cfg.TestFixtureDir)
		log.Printf("[fixture] FixtureProvider aktiv — dir: %s", cfg.TestFixtureDir)
	} else {
		weatherProvider = openmeteo.NewProvider(openmeteo.ProviderConfig{
			BaseURL:    cfg.OpenMeteoBaseURL,
			AQURL:      cfg.OpenMeteoAQURL,
			TimeoutSec: cfg.OpenMeteoTimeout,
			Retries:    cfg.OpenMeteoRetries,
			CacheDir:   cfg.CacheDir,
		})
	}

	// Issue #450 — WebAuthn/Passkey init.
	// Issue #2130: RP-ID/Origins werden in config.NewWebAuthn aus PublicHost
	// abgeleitet. Der Aufbau steht bewusst NICHT mehr hier inline — sonst waeren
	// die Tests gruen, waehrend der laufende Server weiter "localhost" sendet.
	webAuthn, err := config.NewWebAuthn(cfg)
	if err != nil {
		cleanup()
		return nil, nil, fmt.Errorf("webauthn init: %w", err)
	}
	challengeStore := handler.NewChallengeStore()

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		cleanup()
		return nil, nil, fmt.Errorf("scheduler error: %w", err)
	}
	if scheduler.SchedulerEnabled(cfg) {
		sched.Start()
	} else {
		log.Printf("[scheduler] disabled for env=%s (staging quota gate, Issue #1329)", cfg.Env)
	}
	stops = append(stops, sched.Stop)

	r := router.New(router.Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    weatherProvider,
		WebAuthn:           webAuthn,
		ChallengeStore:     challengeStore,
		Scheduler:          sched,
		TelegramTokenStore: telegramTokenStore,
		InviteStore:        inviteStore,

		PremiumSmsRateLimiter: premiumSmsRateLimiter,

		GitCommit: gitCommit,
	})

	return newHTTPServer(cfg.Host+":"+cfg.Port, r), cleanup, nil
}

// Issue #2961: Server-Zeitgrenzen gegen langsame bzw. haengende Verbindungen.
// Bewusst KEIN WriteTimeout: der Versand und die Proxys zum Python-Kern
// duerfen bis zu 300 s laufen (proxy.go sendProxyTimeout, nginx 330 s, Spec
// fix_2124_versand_nginx_timeout.md) — ein WriteTimeout braeche sie ab.
// ReadTimeout begrenzt nur das Einlesen von Kopf und Rumpf (GPX-Upload bis
// 10 MB auch ueber langsame Mobilverbindungen) und beendet keine laufende
// Bearbeitung.
const (
	serverReadHeaderTimeout = 10 * time.Second
	serverReadTimeout       = 2 * time.Minute
	serverIdleTimeout       = 2 * time.Minute
)

func newHTTPServer(addr string, h http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           h,
		ReadHeaderTimeout: serverReadHeaderTimeout,
		ReadTimeout:       serverReadTimeout,
		IdleTimeout:       serverIdleTimeout,
	}
}

// warnPrivilegedIDsWithoutAccount schreibt beim Start je eine Warnzeile fuer
// jede Kennung aus GZ_ADMIN_USER_IDS / GZ_QUOTA_EXEMPT_USER_IDS, zu der es kein
// Konto (keine lesbare user.json) gibt (Issue #2961, ADR-0113). Eine solche
// Kennung ist ein Rechte-Platzhalter, der nicht frei herumliegen soll.
func warnPrivilegedIDsWithoutAccount(s *store.Store, cfg *config.Config) {
	lists := []struct{ env, raw string }{
		{"GZ_ADMIN_USER_IDS", cfg.AdminUserIDs},
		{"GZ_QUOTA_EXEMPT_USER_IDS", cfg.QuotaExemptUserIDs},
	}
	for _, l := range lists {
		ids := make([]string, 0)
		for id := range config.ParseAdminUserIDs(l.raw) {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		for _, id := range ids {
			if u, err := s.LoadUser(id); err == nil && u != nil {
				continue
			}
			log.Printf("WARN [auth] %s nennt %q, dazu existiert kein Konto", l.env, id)
		}
	}
}

// seedAdminUser legt beim ersten Start das Betreiber-Konto aus den
// ENV-Zugangsdaten an (Issue #2151 Scheibe B). Reihenfolge bewusst: nur bei
// gesetzter Kennung (GZ_USER_ID), gesetztem Passwort und noch nicht
// existierendem Konto — ohne GZ_USER_ID entsteht kein Konto mehr (kein
// stiller Rueckfall auf "default"). Ein Fehlschlag von SaveUser wird geloggt
// und zurueckgegeben, beendet den Server aber nicht.
func seedAdminUser(s *store.Store, cfg *config.Config) error {
	if cfg.UserID == "" || cfg.AuthPass == "" {
		return nil
	}
	// Issue #2961: UserExists meldet seither auch einen Ordner ohne user.json
	// als belegt. Fuer die Betreiberkennung zaehlt hier allein die user.json
	// (eine unlesbare Datei wird nie ueberschrieben).
	existing, err := s.LoadUser(cfg.UserID)
	if err != nil {
		log.Printf("Seed user '%s' skipped: %v", cfg.UserID, err)
		return err
	}
	if existing != nil {
		return nil
	}
	hash, _ := bcrypt.GenerateFromPassword([]byte(cfg.AuthPass), bcrypt.DefaultCost)
	now := time.Now()
	if err := s.SaveUser(model.User{
		ID:           cfg.UserID,
		PasswordHash: string(hash),
		CreatedAt:    now,
		// Issue #2271: seit der Scharfschaltung stellt issueSession nur noch
		// fuer bestaetigte Adressen ein Merkmal aus. Dieses Konto entsteht
		// aus ENV-Zugangsdaten des Betreibers, hat gar keine per Mail
		// erhobene Adresse und koennte sich deshalb NIE bestaetigen — ohne
		// diesen Zeitstempel sperrt ein frischer Stack (CI-Wegwerfwurzel,
		// Neuinstallation) seinen eigenen Admin aus. Gemessen: ohne die
		// Zeile antwortet POST /api/auth/login mit 403 email_not_verified.
		EmailVerifiedAt: &now,
	}); err != nil {
		log.Printf("Seed user '%s' failed: %v", cfg.UserID, err)
		return err
	}
	log.Printf("Seed user '%s' created", cfg.UserID)
	return nil
}
