package handler

// Hinweis-Mails bei sicherheitsrelevanten Kontoaenderungen (Issue #2961, GA3,
// ADR-0115): Adresswechsel (an die ALTE bestaetigte Adresse), Passkey
// hinzugefuegt/entfernt, Passwort geaendert/zurueckgesetzt, Google verknuepft.
// Text aus dem Katalog mail.hinweis.* (DE/EN), Versand ueber denselben
// Go-Mailweg wie die Google-Hinweis-Mail (Empfaengerschutz ADR-0087),
// fail-soft und mit Mengenbremse (hoechstens 5 je Nutzer und Stunde).

import (
	"html"
	"log"
	"strings"
	"sync/atomic"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Arten der Hinweis-Mail (Schluessel mail.hinweis.<art>.*).
const (
	hinweisAdresse    = "adresse"
	hinweisKennung    = "kennung"
	hinweisPasskeyNeu = "passkey_neu"
	hinweisPasskeyWeg = "passkey_weg"
	hinweisPasswort   = "passwort"
	hinweisReset      = "reset"
)

// accountNoticeLimiter: hoechstens 5 Hinweis-Mails je Nutzer und Stunde.
var accountNoticeLimiter = NewMailFloodLimiter(5, time.Hour)

// accountNoticeCfg traegt die Mail-Konfiguration fuer Handler, deren
// Signatur keine Config kennt (Passkey, Passwort, Bestaetigung). Gesetzt in
// router.New ueber SetAccountNoticeConfig; ohne sie wird nichts versendet
// (Log-Zeile, die Aenderung selbst bleibt gueltig).
var accountNoticeCfg atomic.Pointer[config.Config]

// SetAccountNoticeConfig setzt die Mail-Konfiguration der Hinweis-Mails.
func SetAccountNoticeConfig(cfg config.Config) { accountNoticeCfg.Store(&cfg) }

// buildAccountNoticeMail baut eine Hinweis-Mail: Gruss, Satz der Art, optional
// Zusatzzeilen (bereits uebersetzt), Warnung mit Link zum Passwort-Reset.
func buildAccountNoticeMail(lang i18n.Lang, publicHost, art string, args i18n.Args, extra []string) mail.Mail {
	t := func(k string, a i18n.Args) string { return i18n.T(lang, "mail.hinweis."+k, a) }
	zeilen := append([]string{t("gruss", nil), t(art+".text", args)}, extra...)
	link := strings.TrimRight(publicHost, "/") + "/forgot-password"
	const marke = "\x00LINK\x00"
	warnungPlain := t("warnung", i18n.Args{"link": link})
	warnungHTML := strings.Replace(html.EscapeString(t("warnung", i18n.Args{"link": marke})),
		html.EscapeString(marke), `<a href="`+html.EscapeString(link)+`">`+html.EscapeString(link)+`</a>`, 1)

	var htmlBody strings.Builder
	htmlBody.WriteString(`<!DOCTYPE html><html><body style="font-family:sans-serif;line-height:1.5">`)
	for _, z := range zeilen {
		htmlBody.WriteString("<p>" + html.EscapeString(z) + "</p>")
	}
	htmlBody.WriteString("<p>" + warnungHTML + "</p></body></html>")
	return mail.Mail{
		Subject:   t(art+".betreff", nil),
		PlainBody: strings.Join(zeilen, "\n\n") + "\n\n" + warnungPlain + "\n",
		HTMLBody:  htmlBody.String(),
		Lang:      lang,
	}
}

// confirmedNoticeAddress: die aktuelle bestaetigte Adresse des Kontos (leer,
// wenn das Konto unbestaetigt ist — dann geht keine Hinweis-Mail hinaus).
func confirmedNoticeAddress(u *model.User) string {
	if u == nil || u.EmailVerifiedAt == nil {
		return ""
	}
	return store.EffectiveContactAddress(u)
}

// notifyAccountChange baut und versendet eine Hinweis-Mail an to (fail-soft).
func notifyAccountChange(u *model.User, to, art string, args i18n.Args, extra []string) {
	cfg := accountNoticeCfg.Load()
	if u == nil || to == "" || cfg == nil {
		return
	}
	msg := buildAccountNoticeMail(i18n.Parse(u.Language), cfg.PublicHost, art, args, extra)
	sendAccountNotice(*cfg, u, to, msg, art)
}

// sendAccountNotice: Mengenbremse, dann asynchroner Versand (20 s Timeout).
// Test-Konten gehen ueber den Google-Weg, echte ueber den engen
// Verifikations-Sonderpfad (sendVerificationMailFn) — die alte Adresse steht
// nach einem Wechsel nicht mehr in der Allowlist verifizierter Profile.
// Fehler werden ohne Empfaenger protokolliert und brechen nichts ab.
func sendAccountNotice(cfg config.Config, u *model.User, to string, msg mail.Mail, art string) {
	if !accountNoticeLimiter.AllowAddressOnly(u.ID) {
		log.Printf("account notice %s: Mengenbremse erreicht fuer %s — nicht versendet", art, u.ID)
		return
	}
	isTestUser := mail.IsTestUser(u)
	if (isTestUser && cfg.GoogleSMTPHost == "") || (!isTestUser && cfg.SMTPHost == "") {
		log.Printf("account notice %s: SMTP nicht konfiguriert — nicht versendet", art)
		return
	}
	// Transport hier (synchron) festhalten, nicht erst in der Goroutine lesen.
	sendVerificationMail := sendVerificationMailFn
	go func() {
		done := make(chan error, 1)
		if isTestUser {
			mailCfg := mail.MailConfig{Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
				User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass, From: cfg.GoogleSMTPUser}
			fallbackCfg := mail.MailConfig{Host: cfg.FallbackSMTPHost, Port: 587,
				User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass}
			go func() { done <- mail.SendWithFallback(mailCfg, fallbackCfg, to, msg) }()
		} else {
			mailCfg := mail.MailConfig{Host: cfg.SMTPHost, Port: cfg.SMTPPort,
				User: cfg.SMTPUser, Pass: cfg.SMTPPass, From: cfg.SMTPFrom}
			go func() { done <- sendVerificationMail(mailCfg, to, msg) }()
		}
		select {
		case err := <-done:
			if err != nil {
				log.Printf("account notice %s: Versand fehlgeschlagen", art)
			}
		case <-time.After(20 * time.Second):
			log.Printf("account notice %s: Versand-Timeout (20s)", art)
		}
	}()
}

// resetRemovedLines: Zusatzzeilen der Reset-Hinweis-Mail — was entfernt wurde
// bzw. dass Passkeys/Google bestehen bleiben.
func resetRemovedLines(lang i18n.Lang, removedPasskeys int, removedGoogle, keptOther bool) []string {
	t := func(k string, a i18n.Args) string { return i18n.T(lang, "mail.hinweis.reset."+k, a) }
	var teile []string
	if removedPasskeys > 0 {
		teile = append(teile, t("passkeys", i18n.Args{"anzahl": removedPasskeys}))
	}
	if removedGoogle {
		teile = append(teile, t("google", nil))
	}
	switch {
	case len(teile) > 0:
		return []string{t("entfernt", i18n.Args{"liste": strings.Join(teile, ", ")})}
	case keptOther:
		return []string{t("bleiben", nil)}
	}
	return nil
}
