// doc-compliance-test (liest die englischen Katalogwerte als DATEN)
//
// Issue #2647 (i18n S2) — AC-8: Glossar- und Stilregeln der englischen Texte
// (docs/reference/i18n_glossar.md, Konventionen Abschnitt 2) und Typpruefung
// des Schluessels (`@ts-expect-error`, wirksam in `npm run check`). Jede Regel
// laeuft zuerst gegen bekannt schlechte Texte (Gegenprobe), damit keine Regel
// vakuum-gruen ist. Gepruefte Werte kommen ueber `trFor('en', …)` bzw. den
// Store mit `locale.set('en')`, nie aus Literalen.
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/en_katalog_regeln.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { get } from 'svelte/store';
import { en } from '../messages/en/index.ts';
import { de } from '../messages/de/index.ts';
import { t, tn, tr, trFor, trn, locale, type MessageKey } from '../index.ts';

const keys = Object.keys(de) as MessageKey[];
const enText = (k: MessageKey) => trFor('en', k);

const TOUR = /\btours?\b/i;
const LEG = /\blegs?\b/i;
const KANAL_IN_ARBEIT = /sms|satellite/i;

/** Verstoesse eines englischen Textes gegen die Stilregeln. */
function verstoesse(key: string, wert: string): string[] {
	const v: string[] = [];
	if (TOUR.test(wert)) v.push('tour');
	if (LEG.test(wert)) v.push('leg statt stage');
	if (wert.includes('!')) v.push('Ausrufezeichen');
	if (key.startsWith('start.') && KANAL_IN_ARBEIT.test(wert)) {
		if (!/in progress/.test(wert)) v.push('SMS/Satellit ohne "in progress"');
		if (!/on request/.test(wert)) v.push('SMS/Satellit ohne "on request"');
	}
	return v;
}

after(() => locale.set('de'));

describe('Gegenprobe: die Regeln erkennen schlechte Texte', () => {
	test('tour, leg, Ausrufezeichen, SMS ohne Zusatz', () => {
		assert.deepEqual(verstoesse('x.a', 'Plan your tour'), ['tour']);
		assert.deepEqual(verstoesse('x.a', 'Each leg of the trip'), ['leg statt stage']);
		assert.deepEqual(verstoesse('x.a', 'Great!'), ['Ausrufezeichen']);
		assert.deepEqual(verstoesse('start.x', 'SMS is available'), [
			'SMS/Satellit ohne "in progress"',
			'SMS/Satellit ohne "on request"'
		]);
		assert.deepEqual(verstoesse('start.x', 'SMS is in progress or on request'), []);
		assert.deepEqual(verstoesse('x.a', 'The weather for your stage'), []);
	});
});

describe('AC-8: englische Texte', () => {
	test('jeder Schluessel hat einen eigenen englischen Wert', () => {
		assert.deepEqual(keys.filter((k) => !(k in en)), []);
	});
	test('kein englischer Wert verstoesst gegen die Stilregeln', () => {
		const befunde = keys
			.map((k) => [k, verstoesse(k, enText(k))] as const)
			.filter(([, v]) => v.length > 0)
			.map(([k, v]) => `${k}: ${v.join(', ')}`);
		assert.deepEqual(befunde, []);
	});
	test('Messaufbau nicht leer: mindestens ein start.*-Wert nennt SMS oder satellite', () => {
		assert.ok(keys.some((k) => k.startsWith('start.') && KANAL_IN_ARBEIT.test(enText(k))));
	});
	test('Fachbegriffe laut Glossar', () => {
		assert.match(enText('start.was.text'), /\bstages?\b/);
		assert.match(enText('start.was.text'), /location comparison/);
		assert.match(enText('info.wertebereiche.route'), /target ranges/);
		assert.match(enText('tip.aria.wertebereiche'), /target ranges/);
		assert.match(enText('hilfe.briefing.abends'), /Delivery tab/);
		assert.match(enText('hilfe.alarme.text'), /Alerts tab/);
		assert.match(enText('telegram_kurzstil.hinweis_aktiv'), /Layout tab/);
	});
	test('Beispiel-Schluessel der Spec (Konto/Anmeldung, Standardwerte, Onboarding)', () => {
		assert.equal(enText('start.cta.register'), 'Sign up');
		assert.equal(enText('start.cta.login'), 'Sign in');
		assert.equal(enText('start.hero.title'), 'The weather for your stage, right where you are.');
		assert.equal(enText('nav.hilfe'), 'Help');
		assert.equal(enText('standardwerte.knopf'), 'Save as defaults');
		assert.equal(enText('onboarding.willkommen.neuer_trip'), '+ New trip');
	});
	test('Bildpfade bleiben unuebersetzt', () => {
		const pfade = keys.filter((x) => x.endsWith('.src'));
		assert.ok(pfade.length > 0, 'Messaufbau: keine Bildpfade');
		for (const k of pfade) assert.equal(enText(k), trFor('de', k), k);
	});
	test('Befehlswoerter: en zeigt die englischen Protokoll-Woerter (#2651), Argumentform bleibt', () => {
		// #2651 (F2): die Hilfe zeigt je Sprache das Wort, das der Bot versteht
		// (wort_en, Drift gegen _COMMAND_SPECS: tests/test_hilfe_befehle_drift.py).
		// Die Argumentform (nach dem ersten Wort) bleibt bis auf den Datumsplatzhalter gleich.
		const befehle = keys.filter((x) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(x));
		assert.equal(befehle.length, 15);
		const arg = (s: string) => s.split(' ').slice(1).join(' ');
		for (const k of befehle) {
			assert.equal(arg(enText(k)).replace('YYYY-MM-DD', 'JJJJ-MM-TT'), arg(trFor('de', k)), k);
		}
		assert.equal(enText('hilfe.befehle.heute.befehl'), 'TODAY');
		assert.equal(enText('hilfe.befehle.weiter.befehl'), 'RESUME');
		assert.equal(enText('hilfe.befehle.status.befehl'), 'STATUS');
	});
});

describe('AC-8: Store-Zugriff und Typpruefung', () => {
	test('$t, tr, tn und trn folgen locale', () => {
		locale.set('en');
		assert.equal(get(t)('start.cta.login'), enText('start.cta.login'));
		assert.equal(tr('start.cta.login'), enText('start.cta.login'));
		assert.equal(get(tn)('aktionen.zeit.vor_minuten', 2), trn('aktionen.zeit.vor_minuten', 2));
		assert.notEqual(tr('start.cta.login'), trFor('de', 'start.cta.login'));
		locale.set('de');
		assert.equal(get(t)('start.cta.login'), trFor('de', 'start.cta.login'));
		assert.equal(tr('start.cta.login'), trFor('de', 'start.cta.login'));
	});
	test('unbekannter Schluessel ist ein Typfehler', () => {
		// @ts-expect-error unbekannter Schluessel darf nicht kompilieren
		void (() => get(t)('start.unbekannt'));
		// @ts-expect-error unbekannter Schluessel darf nicht kompilieren
		void (() => tr('start.unbekannt'));
		// @ts-expect-error unbekannter Schluessel darf nicht kompilieren
		void (() => trFor('en', 'start.unbekannt'));
	});
});
