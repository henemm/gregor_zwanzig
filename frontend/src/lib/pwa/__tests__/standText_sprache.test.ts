// Issue #2652 (i18n F3, Epic #2644) — AC-6: die Offline-Stand-Zeile spricht
// die Sprache, die der Aufrufer uebergibt (Service Worker: `<html lang>` des
// abgelegten Dokuments; Browser: `get(locale)`). standText.ts selbst kennt
// KEINEN Svelte-Store (Service-Worker-tauglich): der Test importiert nur das
// Modul und die Katalogdateien, nie `$lib/i18n/index.ts`.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/lib/pwa/__tests__/standText_sprache.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { standZeile, standKurz, formatiereStandZeit, standSpracheAusHtml } from '../standText.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const katalog = (lang: string) =>
	JSON.parse(readFileSync(path.join(HERE, '../../i18n/messages', lang, 'home.json'), 'utf-8')) as Record<string, string>;
const EN = katalog('en');

// 5. September 06:12 Wiener Sommerzeit (= 04:12 UTC).
const ZEIT = new Date('2026-09-05T04:12:00Z');

describe('AC-6: Stand-Zeile englisch', () => {
	test('beginnt mit "As of:" und endet mit "offline, from device storage"', () => {
		const z = standZeile(ZEIT, 'en');
		assert.ok(z.startsWith('As of:'), z);
		assert.ok(z.endsWith('offline, from device storage'), z);
		assert.ok(z.endsWith(EN['home.stand.herkunft']), z);
		assert.equal(z, `As of: ${formatiereStandZeit(ZEIT, 'en')} — ${EN['home.stand.herkunft']}`);
	});
	test('Kurzform englisch, Zeitstempel en-GB (24 h, ohne deutsches Monatsformat)', () => {
		assert.equal(standKurz(ZEIT, 'en'), `As of: ${formatiereStandZeit(ZEIT, 'en')}`);
		assert.equal(formatiereStandZeit(ZEIT, 'en'), ZEIT.toLocaleString('en-GB', {
			day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
		}));
	});
	test('de und en nacheinander im selben Lauf beeinflussen sich nicht', () => {
		const en = standZeile(ZEIT, 'en');
		const de = standZeile(ZEIT, 'de');
		assert.notEqual(en, de);
		assert.equal(standZeile(ZEIT, 'en'), en);
	});
});

describe('AC-6: Deutsch wortgleich (Bestand)', () => {
	test('Stand: … — offline, aus dem Gerätespeicher (auch ohne Sprachangabe)', () => {
		const zeit = formatiereStandZeit(ZEIT);
		assert.equal(zeit, ZEIT.toLocaleString('de-AT', {
			day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
		}));
		assert.equal(standZeile(ZEIT), `Stand: ${zeit} — offline, aus dem Gerätespeicher`);
		assert.equal(standZeile(ZEIT, 'de'), standZeile(ZEIT));
		assert.equal(standKurz(ZEIT, 'de'), `Stand: ${zeit}`);
	});
});

describe('Service Worker: Sprache aus <html lang> des abzulegenden Dokuments', () => {
	test('en, de und Fallback de', () => {
		assert.equal(standSpracheAusHtml('<!doctype html><html lang="en" data-x="1"><head>'), 'en');
		assert.equal(standSpracheAusHtml('<html lang="de">'), 'de');
		assert.equal(standSpracheAusHtml('<html>'), 'de');
		assert.equal(standSpracheAusHtml('<html lang="fr">'), 'de');
	});
});
