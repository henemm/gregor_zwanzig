// Issue #2651 (i18n F2, Epic #2644) — AC-1, AC-2, AC-7: die Hilfeseite
// „So funktioniert Gregor" / „How Gregor works" in beiden Sprachen.
// Echter SSR-Render von routes/hilfe/+page.svelte (Pruefstand onboardingSsr.ts)
// unter `locale.set('en')` bzw. `'de'` in DERSELBEN Serverrunde:
//   * de byte-gleich zur Ausgabe vor der Umstellung (fixtures/hilfe.de.html,
//     geschrieben VOR der Umstellung),
//   * en: nach Abzug aller englischen hilfe.*-Katalogwerte bleibt kein Wort,
//     die vier Kanaele stehen in der Reihenfolge wie auf Deutsch, die
//     Befehlstabelle zeigt die englischen Befehlswoerter, die der Bot versteht
//     (Drift gegen die Python-Quelle: tests/test_hilfe_befehle_drift.py).
// Spec: docs/specs/modules/i18n_f2_hilfe_infobox_2651.md
//
//   cd frontend && npm test -- src/routes/hilfe/__tests__/hilfe_zweisprachig.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { FRONTEND, ROUTES, render, ladeKomponente, ohneKommentare, sichtbar, teilbaum } from '../../__tests__/onboardingSsr.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GOLDEN = readFileSync(path.join(HERE, 'fixtures', 'hilfe.de.html'), 'utf-8');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const EN = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/en/index.ts')).href)).en as Record<
	string,
	string
>;
const Seite = await ladeKomponente(path.join(ROUTES, 'hilfe', '+page.svelte'));

afterEach(() => locale.set('de'));

const seite = () => ohneKommentare(render(Seite, { props: { data: {} } }).body);
const KANAELE = ['hilfe.kanaele.email', 'hilfe.kanaele.telegram', 'hilfe.kanaele.sms', 'hilfe.kanaele.premium_sms'];
const DEUTSCH =
	/[äöüÄÖÜß]|\b(Etappe|Ortsvergleich|Briefings? für|Morgens|Abends|Alarme|Kanäle|Befehle|auch|HEUTE|MORGEN|JETZT|GEWITTER|STRECKE|RUHETAG|WEITER|HILFE|KUERZEL|STARTDATUM|JJJJ)\b/;

/** Englische Befehlswoerter laut Spec-Tabelle (harte Literale, nicht aus dem Katalog abgeleitet). */
const BEFEHLE_EN = [
	'TODAY',
	'TOMORROW',
	'NOW',
	'STORMS',
	'ROUTE [km]',
	'RESTDAY [N]',
	'STATUS',
	'PAUSE [2d / 12h]',
	'SKIP',
	'STOP',
	'RESUME',
	'HELP',
	'CODES',
	'STARTDATE YYYY-MM-DD',
	'REPORT [morning / evening]'
];

function enSeite(): string {
	locale.set('de');
	seite(); // erst Deutsch rendern: Sprachwechsel ohne Neuladen
	locale.set('en');
	return seite();
}

/** Linke Spalte der Befehlstabelle in Reihenfolge. */
function befehlsspalte(h: string): string[] {
	const b = teilbaum(h, 'hilfe-befehle') ?? '';
	return [...b.matchAll(/<td class="mono"[^>]*>([\s\S]*?)<\/td>/g)].map((m) => sichtbar(m[1]));
}

describe('AC-2: Deutsch byte-gleich zur Ausgabe vor der Umstellung', () => {
	test('/hilfe auf Deutsch = Golden hilfe.de.html', () => {
		locale.set('de');
		assert.equal(seite() + '\n', GOLDEN);
	});
	test('nach einem englischen Render ist Deutsch wieder byte-gleich', () => {
		locale.set('en');
		seite();
		locale.set('de');
		assert.equal(seite() + '\n', GOLDEN);
	});
});

describe('AC-1: /hilfe auf Englisch', () => {
	test('Titel und Abschnittstitel englisch', () => {
		const s = sichtbar(enSeite());
		assert.ok(s.includes('How Gregor works'), s);
		for (const k of ['hilfe.briefing.titel', 'hilfe.alarme.titel', 'hilfe.kanaele.titel', 'hilfe.befehle.titel']) {
			assert.ok(s.includes(trFor('en', k)), k);
		}
	});
	test('kein deutsches Restwort: nach Abzug aller englischen hilfe.*-Werte bleibt nichts', () => {
		const h = enSeite();
		const werte = Object.entries(EN)
			.filter(([k]) => k.startsWith('hilfe.'))
			.map(([, v]) => v)
			.sort((a, b) => b.length - a.length);
		assert.ok(werte.length >= 40, 'Messaufbau: zu wenige hilfe.*-Werte');
		let rest = sichtbar(h);
		for (const w of werte) rest = rest.split(w).join(' ');
		assert.deepEqual(rest.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? [], [], rest);
		assert.doesNotMatch(sichtbar(h), DEUTSCH);
	});
	test('vier Kanaele (E-Mail, Telegram, SMS, Premium SMS) in derselben Reihenfolge wie auf Deutsch', () => {
		locale.set('de');
		const de = sichtbar(teilbaum(seite(), 'hilfe-kanaele') ?? '');
		const posDe = KANAELE.map((k) => de.indexOf(trFor('de', k)));
		locale.set('en');
		const en = sichtbar(teilbaum(seite(), 'hilfe-kanaele') ?? '');
		const posEn = KANAELE.map((k) => en.indexOf(trFor('en', k)));
		for (const [i, k] of KANAELE.entries()) {
			assert.ok(posDe[i] >= 0, `de: ${k} fehlt`);
			assert.ok(posEn[i] >= 0, `en: ${k} fehlt`);
		}
		assert.deepEqual([...posDe].sort((a, b) => a - b), posDe);
		assert.deepEqual([...posEn].sort((a, b) => a - b), posEn);
		for (const name of ['Email', 'Telegram', 'SMS', 'Premium SMS (Garmin inReach)']) assert.ok(en.includes(name), name);
	});
	test('Befehlstabelle zeigt die englischen Befehlswoerter samt Argumentform', () => {
		assert.deepEqual(befehlsspalte(enSeite()), BEFEHLE_EN);
	});
	test('Befehlstabelle auf Deutsch bleibt bei den deutschen Woertern', () => {
		locale.set('en');
		seite();
		locale.set('de');
		const de = befehlsspalte(seite());
		assert.equal(de.length, BEFEHLE_EN.length);
		assert.deepEqual(de.slice(0, 3), ['HEUTE', 'MORGEN', 'JETZT']);
		assert.ok(de.includes('STARTDATUM JJJJ-MM-TT'));
	});
	test('englische Beschreibungen nennen keinen deutschen Alias und kein CANCEL', () => {
		const b = sichtbar(teilbaum(enSeite(), 'hilfe-befehle') ?? '');
		assert.doesNotMatch(b, /ABBRUCH|CANCEL|\(also /);
	});
});

describe('AC-7: Allowlist ohne Eintraege dieses Pakets', () => {
	// doc-compliance-test: liest die Allowlist als Daten
	test('kein Eintrag fuer routes/hilfe/, Infobox, BegriffErklaerung, infoboxKeys', () => {
		const liste: string[] = JSON.parse(readFileSync(path.join(FRONTEND, 'src/lib/i18n/hardcode_allowlist.json'), 'utf-8'));
		const verboten = [
			'routes/hilfe/',
			'routes/hilfe/+page.svelte',
			'lib/components/molecules/Infobox.svelte',
			'lib/components/molecules/BegriffErklaerung.svelte',
			'lib/components/shared/infoboxKeys.ts',
			'lib/components/molecules/'
		];
		assert.deepEqual(liste.filter((e) => verboten.includes(e)), []);
	});
});
