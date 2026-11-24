// Issue #3319 (AC-13, Spec 1.2) — Bildergalerie der oeffentlichen Funktionsseiten.
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (AC-13)
//
// Geprueft wird die reine Logik (organisms/funktionen/galerie.ts) dort, wo sie wirkt:
//   - Reihenfolge je Seite = Reihenfolge der Bilder in der ECHT gerenderten Seite
//     (svelte/server), fuer jede Unterseite;
//   - die Uebersicht /funktionen hat KEINE Galerie: Kachel inkl. Vorschaubild ist ein
//     Link zur Unterseite, kein <button> im <a> (Spec-Changelog „Galerie nur auf Unterseiten“);
//   - Blaettern an den Raendern: NICHT umlaufend. Auf dem ersten Bild gibt es kein
//     „Zurueck“, auf dem letzten kein „Vor“ (Schaltflaeche deaktiviert, Pfeiltaste und
//     Wischen tun nichts). Begruendung: der Zaehler „n / m“ bleibt eindeutig, und wer
//     blaettert, merkt am Ende, dass er alle Bilder der Seite gesehen hat;
//   - Pfeiltasten und Wischen werden in eine Richtung uebersetzt;
//   - Beschriftungen der Bedienelemente kommen aus dem Katalog, DE und EN;
//   - ohne Klick ist keine Galerie im Markup und es wird kein zusaetzliches Bild geladen,
//     jedes Seitenbild steckt in einer Schaltflaeche mit Katalog-Beschriftung.
// Bedienung im Browser (Klick, Pfeiltaste, Esc, Fokus, 375 px):
// frontend/e2e/funktionen-oeffentlich.staging.spec.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/organisms/__tests__/funktionen_galerie.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale, trFor, type MessageKey } from '../../../i18n/index.ts';
import { de } from '../../../i18n/messages/de/index.ts';
import { en } from '../../../i18n/messages/en/index.ts';
import { FUNKTIONEN_SEITEN } from '../../../funktionen_seiten.ts';
import {
	GALERIE_TEXTE,
	galerieBilder,
	naechsterIndex,
	vorherigerIndex,
	tasteZuRichtung,
	wischRichtung,
	blaettern,
	zaehler
} from '../funktionen/galerie.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const ROUTES = path.join(FRONTEND, 'src', 'routes');
const base = pathToFileURL(FRONTEND + '/').href;
for (const h of [
	path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'),
	path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'),
	path.join(FRONTEND, 'src', 'lib', 'components', 'trip-new', '__tests__', 'ssrRunesHook.mjs')
]) {
	register(pathToFileURL(h).href, base);
}
const { render } = await import('svelte/server');

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const attr = (tag: string, a: string) => ent(tag.match(new RegExp(`\\b${a}="([^"]*)"`))?.[1] ?? '');
const bildName = (src: string) => src.split('/').pop()!.replace(/\.webp$/, '');

async function renderSeite(lang: Lang, slug: string | null): Promise<string> {
	locale.set(lang);
	try {
		const datei = slug === null ? path.join(ROUTES, 'funktionen', '+page.svelte') : path.join(ROUTES, 'funktionen', '[thema]', '+page.svelte');
		const Seite = (await import(pathToFileURL(datei).href)).default;
		const data = slug === null ? { oeffentlich: true, lang } : { oeffentlich: true, lang, slug };
		return render(Seite, { props: { data } }).body;
	} finally {
		locale.set('de');
	}
}

// Galerie nur auf den Unterseiten (AC-13, Spec-Changelog „Galerie nur auf Unterseiten“).
const SEITEN: Array<{ slug: string; schluessel: Parameters<typeof galerieBilder>[0] }> = FUNKTIONEN_SEITEN.map((s) => ({
	slug: s.slug as string,
	schluessel: s.slug
}));

// ════════════════════════════════════════════════════════════════════════════
describe('AC-13: Uebersicht /funktionen hat KEINE Galerie, die Kachel inkl. Vorschaubild ist ein Link', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: keine Galerie-Schaltflaeche, kein <button> in einer Kachel, jedes Vorschaubild im Kachel-Link`, async () => {
			const html = await renderSeite(lang, null);
			assert.doesNotMatch(html, /data-testid="bild-oeffnen"|aria-haspopup="dialog"/, `${lang}: Galerie-Schaltflaeche auf der Uebersicht`);
			assert.doesNotMatch(html, /role="dialog"|data-testid="galerie"/, `${lang}: Galerie im Markup der Uebersicht`);
			const kacheln = [...html.matchAll(/<a\b[^>]*data-testid="kachel"[^>]*>([\s\S]*?)<\/a>/g)];
			assert.equal(kacheln.length, FUNKTIONEN_SEITEN.length, `${lang}: Anzahl Kacheln`);
			for (const k of kacheln) assert.doesNotMatch(k[1], /<button\b/, `${lang}: <button> in einem Kachel-Link`);
			const imgsGesamt = [...html.matchAll(/<img\b/g)].length;
			const imgsInKacheln = kacheln.reduce((n, k) => n + [...k[1].matchAll(/<img\b/g)].length, 0);
			assert.ok(imgsInKacheln >= 8, `${lang}: Vorschaubilder fehlen in den Kacheln`);
			assert.equal(imgsInKacheln, imgsGesamt, `${lang}: Vorschaubild ausserhalb des Kachel-Links`);
		});
	}
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-13: Galerie blaettert nur durch die Bilder derselben Seite, in Seitenreihenfolge', () => {
	test('Messaufbau: neun Unterseiten', () => {
		assert.equal(SEITEN.length, 9);
	});
	for (const { slug, schluessel } of SEITEN) {
		test(`${slug}: Galerie-Liste = Bilder der gerenderten Seite, gleiche Reihenfolge`, async () => {
			const html = await renderSeite('de', slug);
			const gerendert = [...html.matchAll(/<img\b[^>]*>/g)].map((m) => bildName(attr(m[0], 'src')));
			assert.deepEqual(
				galerieBilder(schluessel).map((b) => b.name),
				gerendert,
				`${slug}: Galerie weicht von der Seite ab`
			);
		});
	}
	test('Bildnamen sind je Seite eindeutig (Index eines angeklickten Bildes ist eindeutig)', () => {
		for (const { schluessel } of SEITEN) {
			const namen = galerieBilder(schluessel).map((b) => b.name);
			assert.equal(new Set(namen).size, namen.length, `${schluessel}: doppelter Bildname`);
		}
	});
	test('Seiten mit mehreren Bildern existieren (sonst waere Blaettern nicht pruefbar)', () => {
		assert.ok(galerieBilder('kanaele').length >= 3);
		assert.ok(galerieBilder('trips').length >= 4);
		assert.equal(galerieBilder('level').length, 0);
	});
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-13: Vor/Zurueck an den Raendern (nicht umlaufend)', () => {
	test('in der Mitte geht es in beide Richtungen', () => {
		assert.equal(naechsterIndex(1, 3), 2);
		assert.equal(vorherigerIndex(1, 3), 0);
	});
	test('erstes Bild: kein Zurueck, letztes Bild: kein Vor', () => {
		assert.equal(vorherigerIndex(0, 3), null);
		assert.equal(naechsterIndex(2, 3), null);
		assert.equal(naechsterIndex(0, 3), 1);
		assert.equal(vorherigerIndex(2, 3), 1);
	});
	test('ein einziges Bild: weder Vor noch Zurueck', () => {
		assert.equal(naechsterIndex(0, 1), null);
		assert.equal(vorherigerIndex(0, 1), null);
	});
	test('blaettern bleibt am Rand stehen statt umzulaufen', () => {
		assert.equal(blaettern(0, 3, 'vor'), 1);
		assert.equal(blaettern(2, 3, 'vor'), 2);
		assert.equal(blaettern(0, 3, 'zurueck'), 0);
		assert.equal(blaettern(2, 3, 'zurueck'), 1);
		assert.equal(blaettern(1, 3, null), 1);
	});
	test('Zaehler „n / m“ zaehlt ab 1', () => {
		assert.equal(zaehler(0, 3), '1 / 3');
		assert.equal(zaehler(2, 3), '3 / 3');
	});
});

describe('AC-13: Pfeiltasten und Wischen', () => {
	test('Pfeil rechts = vor, Pfeil links = zurueck, andere Tasten nichts', () => {
		assert.equal(tasteZuRichtung('ArrowRight'), 'vor');
		assert.equal(tasteZuRichtung('ArrowLeft'), 'zurueck');
		for (const k of ['Enter', ' ', 'Escape', 'ArrowUp', 'Tab', 'a']) assert.equal(tasteZuRichtung(k), null, k);
	});
	test('Wischen nach links = vor, nach rechts = zurueck', () => {
		assert.equal(wischRichtung(-80, 5), 'vor');
		assert.equal(wischRichtung(80, -5), 'zurueck');
	});
	test('kurzes oder ueberwiegend senkrechtes Wischen blaettert nicht', () => {
		assert.equal(wischRichtung(-20, 0), null);
		assert.equal(wischRichtung(-60, 120), null);
		assert.equal(wischRichtung(0, 0), null);
	});
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-13: Beschriftungen der Bedienelemente aus dem Katalog, DE und EN', () => {
	const schluessel = Object.values(GALERIE_TEXTE) as MessageKey[];
	test('alle Galerie-Schluessel sind belegt und je Sprache verschieden', () => {
		assert.ok(schluessel.length >= 6, `zu wenige Galerie-Texte: ${schluessel.length}`);
		for (const k of schluessel) {
			const d = (de as Record<string, string>)[k];
			const e = (en as Record<string, string>)[k];
			assert.ok(d && d.trim().length > 2, `de ${k} fehlt`);
			assert.ok(e && e.trim().length > 2, `en ${k} fehlt`);
			assert.notEqual(d, e, `${k}: EN ist nicht uebersetzt`);
		}
	});
	test('Platzhalter werden eingesetzt', () => {
		assert.match(trFor('de', GALERIE_TEXTE.oeffnen, { bild: 'Cockpit' }), /Cockpit/);
		assert.match(trFor('en', GALERIE_TEXTE.position, { n: 2, m: 5 }), /2.*5/);
	});
});

describe('AC-13: ohne Klick keine Galerie und kein zusaetzliches Bild; Bild ist eine Schaltflaeche', () => {
	for (const lang of SPRACHEN) {
		for (const { slug, schluessel } of SEITEN) {
			test(`${lang}/${slug}: jedes Bild in <button> mit Katalog-Beschriftung, keine offene Galerie`, async () => {
				const html = await renderSeite(lang, slug);
				const bilder = galerieBilder(schluessel);
				const imgs = [...html.matchAll(/<img\b[^>]*>/g)];
				assert.equal(imgs.length, bilder.length, `${slug}: zusaetzliches Bild ohne Klick`);
				assert.doesNotMatch(html, /role="dialog"|data-testid="galerie"/, `${slug}: Galerie ohne Klick im Markup`);
				const knoepfe = [...html.matchAll(/<button\b[^>]*data-testid="bild-oeffnen"[^>]*>\s*<img\b[^>]*>/g)];
				assert.equal(knoepfe.length, bilder.length, `${lang}/${slug}: nicht jedes Bild steckt in einer Schaltflaeche`);
				knoepfe.forEach((k, i) => {
					assert.equal(attr(k[0], 'type'), 'button');
					assert.equal(attr(k[0], 'aria-haspopup'), 'dialog');
					const alt = trFor(lang, bilder[i].alt);
					assert.equal(attr(k[0], 'aria-label'), trFor(lang, GALERIE_TEXTE.oeffnen, { bild: alt }), `${lang}/${slug}: Beschriftung Bild ${i}`);
				});
			});
		}
	}
});
