// Issue #2520 — typisierter Textkatalog + Inhalt der oeffentlichen Startseite.
// AC-1 (Inhalt), AC-6 (Kanaele), AC-7 (Bilder), AC-8 (Typ + Katalogtexte), AC-10 (Kontrast, Bausteine).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/i18n/__tests__/textkatalog.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { t } from '../index.ts';
import de from '../messages/de.json' with { type: 'json' };

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontend = join(__dirname, '..', '..', '..', '..');
const katalog = de as Record<string, string>;
const startKeys = Object.keys(katalog).filter((k) => k.startsWith('start.'));
const alleText = startKeys.map((k) => katalog[k]).join('\n');

test('AC-8: t() liefert den Katalogwert; unbekannter Schluessel ist ein Typfehler', () => {
	assert.equal(t('start.hero.title'), katalog['start.hero.title']);
	assert.ok(t('start.hero.title').length > 0);
	// @ts-expect-error unbekannter Schluessel darf nicht kompilieren
	void (() => t('start.unbekannt'));
});

test('AC-1: hyperlokale Vorhersage fuer Trip-Zeitraum und Ortsvergleich, morgens/abends + Alarme', () => {
	const k = startKeys.find((x) => /hyperlokal/i.test(katalog[x]));
	assert.ok(k, 'kein Katalogtext zur hyperlokalen Vorhersage');
	const txt = katalog[k!];
	assert.match(txt, /Etappenpunkt/);
	assert.match(txt, /Zeitraum/);
	assert.match(txt, /Ortsvergleich/);
	assert.match(txt, /morgens/);
	assert.match(txt, /abends/);
	assert.match(txt, /Alarm/);
});

test('AC-1: drei Sektionen vorhanden', () => {
	for (const k of ['start.was.title', 'start.ankommt.title', 'start.nutzen.title', 'start.hero.title']) {
		assert.ok(katalog[k]?.length > 0, `${k} fehlt`);
	}
});

test('AC-1: Empfangslage-Aussage und Begriffe (nie "Tour")', () => {
	assert.match(alleText, /unvorhersehbar/);
	assert.doesNotMatch(alleText, /\bTour/);
});

test('AC-6: SMS/Satellit nur mit "in Arbeit" und "auf Anfrage"; E-Mail Hauptkanal, Telegram erwaehnt', () => {
	for (const k of startKeys) {
		if (/sms|satellit/i.test(katalog[k])) {
			assert.match(katalog[k], /in Arbeit/, `${k}: "in Arbeit" fehlt`);
			assert.match(katalog[k], /auf Anfrage/, `${k}: "auf Anfrage" fehlt`);
		}
	}
	assert.match(katalog['start.hero.lead'], /E-Mail/);
	assert.match(alleText, /Telegram/);
	assert.ok(/sms|satellit/i.test(alleText), 'Hinweis auf SMS/Satellit mit Zusatz fehlt');
});

test('AC-7: jede referenzierte Bilddatei existiert, Alt-Texte nicht leer, >= 3 Bilder, < 200 KB', () => {
	const bilder = startKeys.filter((k) => k.endsWith('.src'));
	assert.ok(bilder.length >= 3, 'mind. drei Screenshots');
	for (const k of bilder) {
		const datei = join(frontend, 'static', katalog[k].replace(/^\//, ''));
		assert.ok(existsSync(datei), `${katalog[k]} fehlt`);
		assert.ok(readFileSync(datei).length < 200 * 1024, `${katalog[k]} zu gross`);
		const alt = katalog[k.replace(/\.src$/, '.alt')];
		assert.ok(alt && alt.trim().length > 10, `Alt-Text zu ${k} fehlt`);
		assert.doesNotMatch(alt, /sms/i);
	}
});

function lum(hex: string): number {
	const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) =>
		v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
	);
	return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

test('AC-10: Fliesstext-Token (--g-ink-2) hat >= 4.5:1 auf --g-card', () => {
	const css = readFileSync(join(frontend, 'src', 'app.css'), 'utf-8');
	const tok = (n: string) => css.match(new RegExp(`${n}:\\s*(#[0-9a-fA-F]{6})`))![1];
	const a = lum(tok('--g-ink-2')) + 0.05;
	const b = lum(tok('--g-card')) + 0.05;
	assert.ok(Math.max(a, b) / Math.min(a, b) >= 4.5);
});

// doc-compliance-test
test('AC-8/AC-10: Startseite.svelte nutzt t(), importiert Atoms, hat keinen deutschen Fliesstext im Markup', () => {
	const src = readFileSync(join(frontend, 'src', 'routes', '_start', 'Startseite.svelte'), 'utf-8');
	assert.match(src, /\$lib\/components\/atoms/);
	assert.match(src, /\bt\(/);
	const markup = src.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
	const ohneAusdruecke = markup.replace(/\{[^{}]*\}/g, '').replace(/<!--[\s\S]*?-->/g, '');
	const text = ohneAusdruecke.replace(/<[^>]*>/g, ' ').trim();
	assert.equal(text, '', `Fliesstext im Markup: "${text}"`);
});

// doc-compliance-test
test('AC-10: Layout blendet Chrome auf / fuer Ausgeloggte aus; Loader/Seite verzweigen', () => {
	const layout = readFileSync(join(frontend, 'src', 'routes', '+layout.svelte'), 'utf-8');
	assert.match(layout, /pathname === '\/'\s*&&\s*!data\.userId/);
	const seite = readFileSync(join(frontend, 'src', 'routes', '+page.svelte'), 'utf-8');
	assert.match(seite, /data\.oeffentlich/);
});
