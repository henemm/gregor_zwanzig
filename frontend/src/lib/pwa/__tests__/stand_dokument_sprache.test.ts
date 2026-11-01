// Issue #2652 (i18n F3, Adversary F001) — Verdrahtung der Offline-Stand-Zeile,
// dort wo sie WIRKT:
//   * Service Worker: standEinschreiben (abgelegte Kopie) und offlineListe
//     (Offline-Uebersicht) lesen die Sprache aus `<html lang>` des Dokuments,
//   * Browser: offlineStand.standZeileFuer liest die aktuelle `locale`.
// Erwartungen aus den Katalogdateien (home.json), keine Literale fuer die
// Zeitangabe (Zone/ICU der Laufzeit).
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/lib/pwa/__tests__/stand_dokument_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { standEinschreiben, offlineListe, STAND_MARKE, LISTEN_MARKE } from '../standDokument.ts';
import { standZeile, standKurz } from '../standText.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
// Browser-Modul mit Runen-Store-Import: dieselben SSR-Hooks wie die Seitentests.
await import(pathToFileURL(path.join(FRONTEND, 'src/routes/__tests__/onboardingSsr.ts')).href);
const { standZeileFuer } = await import(pathToFileURL(path.join(HERE, '..', 'offlineStand.ts')).href);
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

afterEach(() => locale.set('de'));

const katalog = (lang: string) =>
	JSON.parse(readFileSync(path.join(HERE, '../../i18n/messages', lang, 'home.json'), 'utf-8')) as Record<string, string>;
const EN = katalog('en');
const ZEIT = new Date('2026-09-05T04:12:00Z');
const dokument = (lang: string) => `<!doctype html><html lang="${lang}"><body>${STAND_MARKE}<main>x</main></body></html>`;
const offlineSeite = (lang: string) => `<!doctype html><html lang="${lang}"><body>${LISTEN_MARKE}</body></html>`;
const EINTRAG = [{ pfad: '/trips', titel: 'Trips', stand: ZEIT.toISOString() }];

describe('Service Worker: abgelegte Kopie traegt die Stand-Zeile in der Sprache des Dokuments', () => {
	test('<html lang="en"> -> „As of: … — offline, from device storage"', () => {
		const html = standEinschreiben(dokument('en'), ZEIT);
		assert.ok(!html.includes(STAND_MARKE), 'Marke nicht ersetzt');
		assert.ok(html.includes('data-testid="offline-stand"'));
		assert.ok(html.includes(`>${standZeile(ZEIT, 'en')}</div>`), html);
		assert.ok(html.includes(EN['home.stand.herkunft']));
		assert.ok(!html.includes('Gerätespeicher'), html);
	});
	test('<html lang="de"> und ohne lang -> deutsche Zeile (Bestand)', () => {
		for (const roh of [dokument('de'), `<html><body>${STAND_MARKE}</body></html>`]) {
			const html = standEinschreiben(roh, ZEIT);
			assert.ok(html.includes(`>${standZeile(ZEIT, 'de')}</div>`), html);
			assert.ok(html.includes('Stand: '));
		}
	});
});

describe('Service Worker: Offline-Uebersicht in der Sprache der Offline-Seite', () => {
	test('lang="en" -> Kurzform „As of: …" je Eintrag', () => {
		const html = offlineListe(offlineSeite('en'), EINTRAG);
		assert.ok(html.includes(`<span class="stand">${standKurz(ZEIT, 'en')}</span>`), html);
		assert.ok(html.includes('data-testid="offline-uebersicht-eintrag"'));
		assert.ok(!html.includes('Stand:'), html);
	});
	test('lang="de" -> „Stand: …"; Titel und Pfad maskiert', () => {
		const html = offlineListe(offlineSeite('de'), [{ ...EINTRAG[0], titel: 'A<b>"' }]);
		assert.ok(html.includes(`<span class="stand">${standKurz(ZEIT, 'de')}</span>`), html);
		assert.ok(html.includes('A&lt;b&gt;&quot;'), html);
	});
});

describe('Browser: Stand-Zeile bei Client-Navigation folgt der aktuellen locale', () => {
	test('erst de, dann ohne Neuladen en', () => {
		locale.set('de');
		assert.equal(standZeileFuer(ZEIT.toISOString()), standZeile(ZEIT, 'de'));
		locale.set('en');
		const en = standZeileFuer(ZEIT.toISOString());
		assert.equal(en, standZeile(ZEIT, 'en'));
		assert.ok(en.startsWith('As of:'), en);
		assert.equal(standZeileFuer(null), null);
	});
});
