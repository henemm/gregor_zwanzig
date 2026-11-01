// Issue #2652 (i18n F3, Epic #2644) — AC-1: das Cockpit (`/` nach dem Login)
// spricht die Nutzersprache: Hero, Kacheln, Versand-/Alert-Karten,
// Ueberschriften, Datums- und Tagesangaben. Trip-/Ortsnamen und Kanalnamen
// (Eigennamen) bleiben. Echter SSR-Render der Seite (f3HomeListenSsr.ts, feste
// Zeit 2026-10-29T06:00+02:00); jeder Fall rendert zuerst `de` und schaltet
// dann OHNE Neuladen auf `en` — eine Mutation tr()/$t -> trFor('de', …) oder
// ein festes 'de-DE' im Datum macht ihn rot. Erwartungen aus trFor/trnFor.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/routes/_home/__tests__/cockpit_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { FAELLE, locale, trFor, trnFor } from '../../__tests__/f3HomeListenSsr.ts';
import { render, ohneKommentare } from '../../__tests__/onboardingSsr.ts';
import { deutscheReste, sichtbarerText, attributText } from '../../__tests__/f3Sprachpruefung.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const lade = async (rel: string) => await import(pathToFileURL(path.join(HERE, '..', rel)).href);
const HomeHero = (await lade('HomeHero.svelte')).default;
const { kachelActions } = await lade('kachelActions.ts');
const { homeHeroProps } = await lade('homeHeroProps.ts');
const { homeCompareTimeline, plannedBriefings, archivedTrips } = await lade('cockpitHelpers.ts');
const { vergleich, tripAktiv, tripFertig } = await import('../../__tests__/f3HomeListenSsr.ts');

afterEach(() => locale.set('de'));

/** de rendern, dann ohne Neuladen auf en schalten und erneut rendern. */
function enNachDe(fall: string): string {
	locale.set('de');
	FAELLE[fall]();
	locale.set('en');
	return FAELLE[fall]();
}
const en = (k: string, p?: Record<string, string | number>) => trFor('en', k, p);
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: "${teil}"\n${text}`);

describe('AC-1: Cockpit mit aktivem Trip auf Englisch', () => {
	test('Hero, Schnellaktionen, Versand- und Alert-Karte, Archiv-Abschnitt', () => {
		const html = enNachDe('cockpit_trip');
		const s = sichtbarerText(html);
		for (const k of [
			'home.hero.naechster_versand', 'home.hero.kanaele', 'home.hero.oeffnen.trip',
			'home.hero.schnell_eingreifen', 'home.hero.schnellaktionen', 'home.cockpit.titel',
			'home.aktion.pausentag', 'home.aktion.zeitplan', 'home.trip.keine_briefings_geplant',
			'home.cockpit.ausserdem', 'home.cockpit.alle_vergleiche', 'home.abschnitt.einrichten',
			'home.abschnitt.fruehere_trips', 'home.cockpit.alle_anzeigen', 'bausteine.versand.heute',
			'bausteine.alarme.titel'
		]) hat(s, en(k));
		hat(s, en('home.trip.live_tag', { tag: 2, gesamt: 3 }));
		hat(s, en('home.trip.tag_von', { tag: 2, gesamt: 3 }));
		hat(s, trnFor('en', 'home.alarm.aenderungen', 2));
		hat(s, trnFor('en', 'home.alarm.aenderungen', 1));
		hat(s, trnFor('en', 'home.cockpit.nebenher', 1));
		hat(s, trnFor('en', 'home.archiv.mehrtages', 1));
		hat(s, trnFor('en', 'listen.anzahl.etappen', 2));
		hat(s, en('home.cockpit.eyebrow', { datum: 'Thu, 29 October 2026' }));
		hat(s, '28 Oct 2026 → 30 Oct 2026');
		assert.deepEqual(deutscheReste(s), []);
		assert.deepEqual(deutscheReste(attributText(html)), []);
	});
	test('Trip-, Orts- und Kanalnamen bleiben unveraendert', () => {
		const s = sichtbarerText(enNachDe('cockpit_trip'));
		for (const name of ['GR20 Nord', 'Korsika', 'Hüttenvergleich Stubai', 'Dolomiten Höhenweg', 'Email', 'Telegram']) hat(s, name);
	});
	test('Monatskuerzel der Archiv-Karte englisch (Sep 2026), deutsch bleibt Sep 2026 / Mär', () => {
		locale.set('en');
		const fertig = { ...tripFertig(), stages: [{ id: 'm', name: 'M', date: '2026-03-02', waypoints: [] }] };
		assert.equal(archivedTrips([fertig], new Date('2026-10-29T06:00:00+02:00'))[0].dates, 'Mar 2026');
		locale.set('de');
		assert.equal(archivedTrips([fertig], new Date('2026-10-29T06:00:00+02:00'))[0].dates, 'Mär 2026');
	});
});

describe('AC-1: Cockpit mit Ortsvergleich und Planungsmodus auf Englisch', () => {
	test('Vergleichs-Hero: Pille, Zeitplan, Oeffnen-Link, Timeline, Alerts leer', () => {
		const html = enNachDe('cockpit_vergleich');
		const s = sichtbarerText(html);
		for (const k of [
			'home.vergleich.aktiv_automatisch', 'home.vergleich.zeitplan', 'home.zeitplan.taeglich',
			'home.hero.oeffnen.vergleich', 'home.aktion.orte_bearbeiten', 'home.alarm.leer',
			'home.abschnitt.kein_trip', 'bausteine.alarme.keine'
		]) hat(s, en(k));
		hat(s, trnFor('en', 'home.hero.orte_verglichen', 3));
		hat(s, en('home.timeline.zuletzt', { zeit: '' }).trim());
		hat(s, en('home.timeline.naechster', { zeit: '' }).trim());
		assert.deepEqual(deutscheReste(s), []);
		assert.deepEqual(deutscheReste(attributText(html)), []);
	});
	test('Planungsmodus: Hinweis-Banner, Weiter einrichten, Schnell anlegen', () => {
		const html = enNachDe('cockpit_planung');
		const s = sichtbarerText(html);
		for (const k of ['home.planung.kein_trip', 'home.abschnitt.weiter_einrichten', 'home.abschnitt.neu_starten', 'home.planung.naechster_trip'])
			hat(s, en(k));
		assert.deepEqual(deutscheReste(s), []);
		assert.deepEqual(deutscheReste(attributText(html)), []);
	});
});

describe('AC-1: Bausteine und Helfer des Cockpits (de -> en ohne Neuladen)', () => {
	test('HomeHero: Oeffnen-Link je kind und Beschriftungen reagieren auf den Sprachwechsel', () => {
		const props = { kind: 'vergleich', id: 'x', name: 'N', href: '/compare/x', channels: ['Email'] };
		locale.set('de');
		const vorher = sichtbarerText(ohneKommentare(render(HomeHero, { props }).body));
		hat(vorher, 'Vergleich öffnen →');
		locale.set('en');
		const s = sichtbarerText(ohneKommentare(render(HomeHero, { props }).body));
		hat(s, en('home.hero.oeffnen.vergleich'));
		hat(s, en('home.hero.naechster_versand'));
		assert.deepEqual(deutscheReste(s), []);
	});
	test('Kachel-Aktion, Hero-Untertitel (Plural), Timeline, Briefing-Zeilen', () => {
		locale.set('de');
		assert.deepEqual(kachelActions(), [{ id: 'edit', label: 'Bearbeiten' }]);
		locale.set('en');
		assert.deepEqual(kachelActions(), [{ id: 'edit', label: en('home.kachel.bearbeiten') }]);
		const ein = { ...vergleich(), location_ids: ['a'], display_config: {} };
		assert.equal(homeHeroProps('vergleich', ein, null).subtitle, trnFor('en', 'home.hero.orte_verglichen', 1));
		const zeilen = homeCompareTimeline(vergleich(), null);
		assert.equal(zeilen[0].kind, en('listen.typ.vergleich'));
		assert.ok(zeilen[0].when.startsWith(en('home.timeline.zuletzt', { zeit: '' })), zeilen[0].when);
		assert.ok(zeilen[0].etappe.startsWith(en('bausteine.vergleich.orte_anzahl', { anzahl: 3 })), zeilen[0].etappe);
		const rows = plannedBriefings(tripAktiv().report_config);
		assert.deepEqual(rows.map((r: { kind: string }) => r.kind), [en('home.timeline.morgen'), en('home.timeline.abend')]);
	});
});
