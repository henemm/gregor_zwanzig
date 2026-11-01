// Issue #2647 (i18n S2) — AC-5 (Golden): die deutschen Texte sind nach dem
// Umzug in die Bereichsdateien byte-gleich zum Stand vor diesem Paket.
// `fixtures/de_katalog_vor_i18n.json` ist die unveraenderte Kopie der alten
// `messages/de.json` (vor dem Loeschen gesichert). Verglichen wird die
// vereinigte `de`-Karte, die auch die Oberflaeche nutzt, und die deutsche
// Ausgabe von `trFor('de', …)` bzw. `tr(…)` mit Standard-Locale.
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/deutsch_unveraendert.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { de } from '../messages/de/index.ts';
import { tr, trFor, type MessageKey } from '../index.ts';

const GOLDEN = JSON.parse(
	readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'de_katalog_vor_i18n.json'), 'utf-8')
) as Record<string, string>;

/** Neue Schluessel dieses Pakets (nicht im Bestand). */
const NEU_IN_S2 = ['aktionen.zeit.vor_minuten.one', 'aktionen.zeit.vor_minuten.other', 'aktionen.zeit.gerade_eben'];
/** Neue Schluessel spaeterer Pakete (je Paket ein Eintrag, nur ergaenzen). */
const NEU_IN_FOLGEPAKETEN = [
	// #2648 (S3) Sprachumschalter und Konto-Sprache
	'konto.sprache.titel',
	'konto.sprache.option_de',
	'konto.sprache.option_en',
	'konto.sprache.gespeichert',
	'konto.sprache.fehler',
	'konto.sprache.umschalter_label',
	// #2650 (F1) Auth-Routen: Bereich auth.json (79 Schluessel)
	'auth.anmelden',
	'auth.oder',
	'auth.zurueck_login',
	'auth.feld.benutzername',
	'auth.feld.username_platzhalter',
	'auth.feld.passwort',
	'auth.feld.email',
	'auth.feld.email_adresse',
	'auth.fehler.zu_viele_versuche',
	'auth.login.untertitel',
	'auth.login.registriert_hinweis',
	'auth.login.sitzung_abgelaufen',
	'auth.login.google_fehler_verknuepfung',
	'auth.login.google_fehler_allgemein',
	'auth.login.email_nicht_bestaetigt',
	'auth.login.erneut_gesendet',
	'auth.login.erneut_senden',
	'auth.login.ungueltige_daten',
	'auth.login.pflichtfelder',
	'auth.login.passkey_anmelden',
	'auth.login.passkey_nicht_unterstuetzt',
	'auth.login.passkey_abgebrochen',
	'auth.login.passkey_fehlgeschlagen',
	'auth.login.google_knopf',
	'auth.login.zu_registrieren',
	'auth.login.zu_passwort_vergessen',
	'auth.login.zu_magic_link',
	'auth.register.titel',
	'auth.register.untertitel',
	'auth.register.passwort_bestaetigen',
	'auth.register.einladung_gueltig',
	'auth.register.einladung_unbekannt',
	'auth.register.einladung_ungueltig',
	'auth.register.datenschutz_hinweis',
	'auth.register.datenschutz_link',
	'auth.register.google_knopf',
	'auth.register.zu_login',
	'auth.register.passwoerter_ungleich',
	'auth.register.email_vergeben',
	'auth.register.benutzername_vergeben',
	'auth.register.fehler_einladung_ungueltig',
	'auth.register.fehler_email_ungueltig',
	'auth.register.fehler_pflichtfelder',
	'auth.register.fehler_allgemein',
	'auth.forgot.titel',
	'auth.forgot.erfolg',
	'auth.forgot.knopf',
	'auth.forgot.fehler_benutzername',
	'auth.reset.titel',
	'auth.reset.erfolg',
	'auth.reset.zum_login',
	'auth.reset.token_platzhalter',
	'auth.reset.passwort_platzhalter',
	'auth.reset.knopf',
	'auth.reset.fehler_pflichtfelder',
	'auth.reset.fehler_passwort_kurz',
	'auth.reset.fehler_token_abgelaufen',
	'auth.reset.fehler_token_ungueltig',
	'auth.magic.titel',
	'auth.magic.untertitel',
	'auth.magic.gesendet',
	'auth.magic.profil_hinweis',
	'auth.magic.knopf',
	'auth.magic.fehler_email_pflicht',
	'auth.code.titel',
	'auth.code.untertitel',
	'auth.code.feld',
	'auth.code.neu_anfordern',
	'auth.code.fehler_pflicht',
	'auth.code.fehler_zu_viele',
	'auth.code.fehler_ungueltig',
	'auth.bestaetigen.titel',
	'auth.bestaetigen.erfolg',
	'auth.bestaetigen.zur_app',
	'auth.bestaetigen.unvollstaendig',
	'auth.bestaetigen.fehler_ungueltig_link',
	'auth.bestaetigen.fehler_adresse_vergeben',
	'auth.bestaetigen.fehler_abgelaufen',
	'auth.bestaetigen.fehler_ungueltig',
	// #2660 (F11) Bausteine und TypeScript-Texte: aktionen/bausteine/fehler (114 Schluessel)
	'aktionen.abbrechen',
	'aktionen.weitere',
	'aktionen.zurueck_zu',
	'aktionen.senden',
	'aktionen.schliessen',
	'bausteine.senden_dialog.titel',
	'bausteine.senden_dialog.berichtsart',
	'bausteine.senden_dialog.morgen',
	'bausteine.senden_dialog.abend',
	'bausteine.dialog.schliessen',
	'bausteine.wordmark.home',
	'bausteine.etappe.pausentag',
	'bausteine.etappe.pause',
	'bausteine.etappe.km',
	'bausteine.etappe.wegpunkte',
	'bausteine.etappe.hoehe',
	'bausteine.etappe.eta',
	'bausteine.etappe.wegpunkt',
	'bausteine.vergleich.orte_anzahl',
	'bausteine.setup.fortschritt',
	'bausteine.setup.weiter_bei',
	'bausteine.setup.bereit',
	'bausteine.alarme.titel',
	'bausteine.alarme.ausgeloest',
	'bausteine.alarme.keine',
	'bausteine.alarme.schwellen',
	'bausteine.alarme.leer',
	'bausteine.metriken.nicht_im_briefing',
	'bausteine.metriken.weitere',
	'bausteine.metriken.aktuell_aus',
	'bausteine.metriken.einklappen',
	'bausteine.metriken.ausklappen',
	'bausteine.metriken.plus_spalte',
	'bausteine.metriken.plus_detail',
	'bausteine.metriken.spalten',
	'bausteine.metriken.detail',
	'bausteine.metriken.horizont_slots',
	'bausteine.metriken.im_score',
	'bausteine.metriken.nicht_im_score',
	'bausteine.kontext.trip',
	'bausteine.kontext.ort',
	'bausteine.kontext.abo',
	'bausteine.kontext.trip_text',
	'bausteine.kontext.ort_text',
	'bausteine.kontext.abo_text',
	'bausteine.versand.heute',
	'bausteine.versand.was_geht_raus',
	'bausteine.versand.alle_kanaele_ok',
	'bausteine.profil.wetter_profil',
	'bausteine.profil.vorlage_hinweis',
	'bausteine.profil.eigen_marke',
	'bausteine.profil.eigenes',
	'bausteine.profil.auswahl_sichern',
	'bausteine.profil.als_profil_speichern',
	'bausteine.profil.wintersport',
	'bausteine.profil.wandern',
	'bausteine.profil.summer_trekking',
	'bausteine.profil.allgemein',
	'bausteine.profil.standard_wintersport',
	'bausteine.profil.standard_wandern',
	'bausteine.profil.standard_summer_trekking',
	'bausteine.profil.standard_metriken',
	'bausteine.abo.keine_kanaele',
	'bausteine.abo.naechster',
	'bausteine.abo.zuletzt',
	'bausteine.abo.setup_unvollstaendig',
	'bausteine.abo.etappen',
	'bausteine.horizont.alle_drei',
	'bausteine.horizont.nur_heute_morgen',
	'bausteine.horizont.nur_heute',
	'bausteine.horizont.nur_morgen_uebermorgen',
	'bausteine.horizont.sonstige',
	'bausteine.horizont.heute',
	'bausteine.horizont.morgen',
	'bausteine.horizont.uebermorgen',
	'bausteine.horizont.uebermorgen_kurz',
	'bausteine.checkliste.route',
	'bausteine.checkliste.etappen',
	'bausteine.checkliste.wetter',
	'bausteine.checkliste.layout',
	'bausteine.checkliste.reports',
	'bausteine.checkliste.vergleich',
	'bausteine.checkliste.orte',
	'bausteine.checkliste.wertebereiche',
	'bausteine.checkliste.versand',
	'bausteine.risiko.rot',
	'bausteine.risiko.gelb',
	'bausteine.risiko.gruen',
	'fehler.verbindung.zeitlimit',
	'fehler.verbindung.schreiben_offline',
	'fehler.sitzung.abgelaufen',
	'fehler.speichern.allgemein',
	'fehler.download.fehlgeschlagen',
	'fehler.versand.unklar',
	'fehler.versand.laeuft_bereits',
	'fehler.versand.fehlgeschlagen',
	'fehler.versand.abgelehnt',
	'fehler.versand.orte_fehlten',
	'fehler.ort.in_verwendung',
	'fehler.code.etag_mismatch',
	'fehler.code.not_found',
	'fehler.code.unauthorized',
	'fehler.code.forbidden',
	'fehler.code.store_error',
	'fehler.code.validation_error',
	'fehler.code.bad_request',
	'fehler.code.invalid_request',
	'fehler.code.internal_error',
	'fehler.code.kind_required',
	'fehler.code.rate_limit_exceeded',
	'fehler.code.service_unavailable',
	'fehler.code.core_unavailable',
	'fehler.code.nothing_to_set',
	'fehler.code.proxy_error',
];

test('AC-5: das Golden enthaelt die 112 Bestandsschluessel', () => {
	assert.equal(Object.keys(GOLDEN).length, 112);
});

test('AC-5: jeder Bestandsschluessel ist mit byte-gleichem Wert in der de-Karte', () => {
	const karte = de as Record<string, string>;
	const abweichend = Object.keys(GOLDEN).filter((k) => karte[k] !== GOLDEN[k]);
	assert.deepEqual(abweichend, []);
});

test('AC-5: die de-Karte enthaelt ausser dem Bestand nur die neuen Schluessel dieses und der Folgepakete', () => {
	const extra = Object.keys(de).filter((k) => !(k in GOLDEN)).sort();
	assert.deepEqual(extra, [...NEU_IN_S2, ...NEU_IN_FOLGEPAKETEN].sort());
});

test('AC-5: trFor(de) und tr() mit Standard-Locale liefern die Bestandstexte unveraendert', () => {
	for (const [k, v] of Object.entries(GOLDEN)) {
		assert.equal(trFor('de', k as MessageKey), v, k);
		assert.equal(trFor(undefined, k as MessageKey), v, k);
		assert.equal(tr(k as MessageKey), v, k);
	}
});
