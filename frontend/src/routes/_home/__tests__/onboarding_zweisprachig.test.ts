// Issue #2651 (i18n F2, Epic #2644) — AC-2, AC-5, AC-6: Willkommen, Leerzustand
// und Startklar-Checkliste sprechen die Nutzersprache. Echter SSR-Render
// (svelte/server, Pruefstand onboardingSsr.ts) unter `locale.set('en')` bzw.
// `'de'` in DERSELBEN Serverrunde (Sprachwechsel ohne Neuladen):
//   * de ist byte-gleich zur Ausgabe vor der Umstellung (Golden fixtures/onboarding.de.html,
//     geschrieben VOR der Umstellung),
//   * en zeigt die englischen Katalogwerte, das Testmail-Datum als `30 Oct 2026`.
// Eine Mutation tr()/$t -> trFor('de', …) oder ein festes 'de' im Datum macht
// die en-Faelle rot.
// Spec: docs/specs/modules/i18n_f2_hilfe_infobox_2651.md
//
//   cd frontend && npm test -- src/routes/_home/__tests__/onboarding_zweisprachig.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
	FRONTEND,
	CHECKLISTE_DATEI,
	EMPTY_KACHEL_DATEI,
	render,
	ladeKomponente,
	ohneKommentare,
	onboardingNeu,
	sichtbar
} from '../../__tests__/onboardingSsr.ts';
import { scanneMarkup } from '../../../lib/i18n/__tests__/hardcode_scan.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GOLDEN = readFileSync(path.join(HERE, 'fixtures', 'onboarding.de.html'), 'utf-8');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const EN = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/en/index.ts')).href)).en as Record<
	string,
	string
>;

const EmptyKachel = await ladeKomponente(EMPTY_KACHEL_DATEI);
const Checkliste = await ladeKomponente(CHECKLISTE_DATEI);

afterEach(() => locale.set('de'));

const TESTMAIL = '2026-10-30T10:00:00Z';
const profil = () => onboardingNeu({ testMailSentAt: TESTMAIL, emailVerified: true });
const html = (komp: unknown, props: Record<string, unknown>) => ohneKommentare(render(komp as never, { props: props as never }).body);
const willkommen = () => html(EmptyKachel, { willkommen: true });
const leer = () => html(EmptyKachel, {});
const checkliste = () => html(Checkliste, { profil: profil(), tripCount: 0, compareCount: 0 });

const DEUTSCH = /[äöüÄÖÜß]|\b(Willkommen|Neuer|Vergleich|Leg|deinen|ersten|starte|Testmail|gesendet|Ausblenden|Verstanden|Checkliste|bestätigt|So funktioniert)\b/;

/** Sichtbarer Text nach Abzug aller englischen onboarding.*-Werte und des Datums. */
function restwoerter(h: string): string[] {
	const werte = Object.entries(EN)
		.filter(([k]) => k.startsWith('onboarding.'))
		.map(([, v]) => v)
		.filter((v) => v.trim())
		.sort((a, b) => b.length - a.length);
	let rest = sichtbar(h);
	for (const w of werte) rest = rest.split(w).join(' ');
	rest = rest.replace(/\b\d{1,2} [A-Z][a-z]{2} \d{4}\b/g, ' ').replace(/\bGregor 20\b/g, ' ');
	return rest.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? [];
}

describe('AC-2: Deutsch byte-gleich zur Ausgabe vor der Umstellung', () => {
	test('Willkommen, Leerzustand und Checkliste (Testmail 30.10.2026) = Golden', () => {
		locale.set('de');
		assert.equal([willkommen(), leer(), checkliste()].join('\n') + '\n', GOLDEN);
	});
	test('Golden enthaelt das Datum im Format 30.10.2026 (Messaufbau)', () => {
		assert.ok(GOLDEN.includes('30.10.2026'));
		assert.ok(GOLDEN.includes('Willkommen bei Gregor 20'));
	});
});

describe('AC-6: Leerzustand eines Bestandskontos auf Englisch', () => {
	test('de -> en ohne Neuladen: Titel, Beschreibung und beide Buttons englisch', () => {
		locale.set('de');
		const vorher = sichtbar(leer());
		assert.ok(vorher.includes('Willkommen bei Gregor 20'), vorher);
		locale.set('en');
		const s = sichtbar(leer());
		assert.ok(s.includes('Welcome to Gregor 20'), s);
		assert.ok(s.includes('Create your first trip or start a location comparison.'), s);
		assert.ok(s.includes('+ New trip'), s);
		assert.ok(s.includes('+ New comparison'), s);
		assert.doesNotMatch(s, DEUTSCH);
		assert.deepEqual(restwoerter(leer()), []);
	});
	test('Buttons nutzen die vorhandenen Schluessel (ein Text, ein Schluessel)', () => {
		locale.set('en');
		const s = sichtbar(leer());
		assert.ok(s.includes(trFor('en', 'onboarding.willkommen.neuer_trip')));
		assert.ok(s.includes(trFor('en', 'onboarding.willkommen.neuer_vergleich')));
		assert.ok(s.includes(trFor('en', 'onboarding.leer.titel')));
		assert.ok(s.includes(trFor('en', 'onboarding.leer.beschreibung')));
	});
	// doc-compliance-test: Ratschen-Scanner auf dem Quelltext von EmptyKachel.svelte
	test('EmptyKachel.svelte hat keinen hartkodierten Text mehr (Ratschen-Scanner)', () => {
		assert.deepEqual(scanneMarkup(readFileSync(EMPTY_KACHEL_DATEI, 'utf-8')), []);
	});
});

describe('Willkommen und Checkliste auf Englisch (de -> en ohne Neuladen)', () => {
	test('Willkommen: nur englische Katalogtexte', () => {
		locale.set('de');
		willkommen();
		locale.set('en');
		const h = willkommen();
		assert.ok(sichtbar(h).includes(trFor('en', 'onboarding.willkommen.titel')));
		assert.doesNotMatch(sichtbar(h), DEUTSCH);
		assert.deepEqual(restwoerter(h), []);
	});
	test('Checkliste: nur englische Katalogtexte', () => {
		locale.set('de');
		checkliste();
		locale.set('en');
		const h = checkliste();
		assert.ok(sichtbar(h).includes(trFor('en', 'onboarding.checkliste.titel')));
		assert.doesNotMatch(sichtbar(h), DEUTSCH);
		assert.deepEqual(restwoerter(h), []);
	});
});

describe('AC-5: Testmail-Datum je Sprache, zwei Renderlaeufe in derselben Serverrunde', () => {
	test('en zeigt 30 Oct 2026, danach de 30.10.2026 — keine Beeinflussung', () => {
		locale.set('en');
		const en = sichtbar(checkliste());
		locale.set('de');
		const de = sichtbar(checkliste());
		assert.ok(en.includes('30 Oct 2026'), en);
		assert.ok(!en.includes('30.10.2026'), en);
		assert.ok(de.includes('30.10.2026'), de);
		assert.ok(!de.includes('Oct'), de);
	});
	test('umgekehrte Reihenfolge: de, dann en', () => {
		locale.set('de');
		const de = sichtbar(checkliste());
		locale.set('en');
		const en = sichtbar(checkliste());
		assert.ok(de.includes('30.10.2026'), de);
		assert.ok(en.includes('30 Oct 2026'), en);
	});
});
