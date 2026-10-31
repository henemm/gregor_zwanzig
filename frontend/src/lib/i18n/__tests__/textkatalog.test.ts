// Issue #2520 — typisierter Textkatalog + Inhalt der oeffentlichen Startseite.
// AC-1 (Inhalt), AC-6 (Kanaele), AC-7 (Bilder), AC-8 (Typ + Katalogtexte), AC-10 (Kontrast, Bausteine).
// Issue #2521 S1 (ab dem Block „info.*/tip.*“ unten): AC-15 (Katalog-Vollstaendigkeit, kein Fliesstext
// ausserhalb t()), AC-17 (keine Handlungsempfehlung).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/i18n/__tests__/textkatalog.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tr } from '../index.ts';
import { de } from '../messages/de/index.ts';
import { ARIA_WORT, BEGRIFFE, INFO_TEXTE, TIP_TEXTE } from '../../components/shared/__tests__/infoboxTexte.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontend = join(__dirname, '..', '..', '..', '..');
const katalog = de as Record<string, string>;
const startKeys = Object.keys(katalog).filter((k) => k.startsWith('start.'));
const alleText = startKeys.map((k) => katalog[k]).join('\n');

test('AC-8: tr() liefert den Katalogwert; unbekannter Schluessel ist ein Typfehler', () => {
	assert.equal(tr('start.hero.title'), katalog['start.hero.title']);
	assert.ok(tr('start.hero.title').length > 0);
	// @ts-expect-error unbekannter Schluessel darf nicht kompilieren
	void (() => tr('start.unbekannt'));
});

test('AC-1: hyperlokale Vorhersage fuer Trip-Zeitraum und Ortsvergleich, morgens/abends + Alarme', () => {
	const alle = [/hyperlokal/i, /Etappenpunkt/, /Zeitraum/, /Ortsvergleich/, /morgens/, /abends/, /Alarm/];
	const k = startKeys.find((x) => alle.every((re) => re.test(katalog[x])));
	assert.ok(k, 'kein EIN Katalogtext nennt hyperlokal, Etappenpunkt, Zeitraum, Ortsvergleich, morgens, abends, Alarm');
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
	assert.match(src, /\$t\(/);
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

// doc-compliance-test
test('F001: Links zeigen exakt auf /register und /login', () => {
	const src = readFileSync(join(frontend, 'src', 'routes', '_start', 'Startseite.svelte'), 'utf-8');
	assert.match(src, /href="\/register"[^>]*>\{\$t\('start\.cta\.register'\)\}/);
	assert.match(src, /href="\/login"[^>]*>\{\$t\('start\.cta\.login'\)\}/);
});

// doc-compliance-test
test('F002: jedes img traegt den Katalog-Alt-Text', () => {
	const src = readFileSync(join(frontend, 'src', 'routes', '_start', 'Startseite.svelte'), 'utf-8');
	assert.match(src, /<img src=\{b\.src\} alt=\{b\.alt\}/);
	for (const n of ['mail', 'telegram', 'alarm']) {
		assert.match(src, new RegExp(`alt: \\$t\\('start\\.${n}\\.alt'\\)`));
	}
});

test('F004: Alarm-Alt-Text passt zum Screenshot (Sturm-/Hitzewarnung)', () => {
	assert.match(katalog['start.alarm.alt'], /Sturm/);
	assert.match(katalog['start.alarm.alt'], /Hitze/);
});

// ─────────────────────────────────────────────────────────────────────────────
// Issue #2521 S1 — Erklaer- und Infobox-Texte (Spec begriff_erklaerung_infobox.md)
//
// Die Soll-Texte stehen als LITERALE in infoboxTexte.ts (PO-freigegebener
// Wortlaut) — NICHT aus dem Katalog gelesen, sonst bestaetigt sich der Katalog
// selbst. Gelesen wird `de` als Record, nicht ueber `t()`, damit der Test nicht
// vom Typ des noch fehlenden Schluessels abhaengt.
//
// Gegenprobe (AC-15): ein leerer Wert, ein abweichender Wortlaut, ein fehlender
// oder ein zusaetzlicher Schluessel macht einen der Faelle unten rot; ebenso
// deutscher Fliesstext in einem der Bausteine ausserhalb von `t()`.
// ─────────────────────────────────────────────────────────────────────────────
const infoKeys = Object.keys(katalog).filter((k) => k.startsWith('info.'));
const tipKeys = Object.keys(katalog).filter((k) => k.startsWith('tip.'));

test('#2521 AC-15: jeder freigegebene info.*-Schluessel ist vorhanden, nicht leer und wortgleich', () => {
	for (const [key, soll] of Object.entries(INFO_TEXTE)) {
		assert.ok(katalog[key]?.trim().length > 0, `${key} fehlt oder ist leer`);
		assert.equal(katalog[key], soll, `${key}: Wortlaut weicht vom freigegebenen Text ab`);
	}
});

test('#2521 AC-15: jeder freigegebene tip.*-Schluessel ist vorhanden, nicht leer und wortgleich', () => {
	for (const [key, soll] of Object.entries(TIP_TEXTE)) {
		assert.ok(katalog[key]?.trim().length > 0, `${key} fehlt oder ist leer`);
		assert.equal(katalog[key], soll, `${key}: Wortlaut weicht vom freigegebenen Text ab`);
	}
});

test('#2521 AC-15: je Begriff ein nicht leerer Knopfname tip.aria.<begriff>, der den Begriff nennt', () => {
	const namen = new Set<string>();
	for (const b of BEGRIFFE) {
		const wert = katalog[`tip.aria.${b}`];
		assert.ok(wert?.trim().length > 0, `tip.aria.${b} fehlt oder ist leer`);
		assert.match(wert, ARIA_WORT[b], `tip.aria.${b} nennt den Begriff nicht: "${wert}"`);
		namen.add(wert);
	}
	assert.equal(namen.size, BEGRIFFE.length, 'zwei Knoepfe tragen denselben Namen (Vorlese-Hilfe unterscheidet sie nicht)');
});

test('#2521 AC-15: der Katalog enthaelt GENAU die freigegebenen info.*/tip.*-Schluessel (keine ungeprueften Texte)', () => {
	const erlaubt = new Set([
		...Object.keys(INFO_TEXTE),
		...Object.keys(TIP_TEXTE),
		...BEGRIFFE.map((b) => `tip.aria.${b}`)
	]);
	const fremd = [...infoKeys, ...tipKeys].filter((k) => !erlaubt.has(k));
	assert.deepEqual(fremd, [], 'Katalog enthaelt nicht freigegebene Schluessel (z. B. info.wegpunkte.vergleich)');
	assert.ok(infoKeys.length === Object.keys(INFO_TEXTE).length, `info.*: ${infoKeys.length} Schluessel statt 9`);
	assert.ok(tipKeys.length === 8, `tip.*: ${tipKeys.length} Schluessel statt 8 (4 Texte + 4 Knopfnamen)`);
});

test('#2521 AC-15: Texte sagen nie „Tour“ (immer Trip)', () => {
	const alle = [...infoKeys, ...tipKeys].map((k) => katalog[k]).join('\n');
	assert.ok(alle.length > 0, 'keine info.*/tip.*-Texte im Katalog — Messaufbau leer');
	assert.doesNotMatch(alle, /\bTour/);
});

test('#2521 AC-17: keine Handlungsempfehlung in info.*/tip.* (Verbotsliste)', () => {
	const verboten = /solltest|sollte\b|empfehl|besser|ratsam|am besten|musst du/i;
	for (const k of [...infoKeys, ...tipKeys]) {
		assert.doesNotMatch(katalog[k], verboten, `${k}: Empfehlungsformel im Text: "${katalog[k]}"`);
	}
	assert.ok(infoKeys.length + tipKeys.length > 0, 'keine Texte geprueft — Messaufbau leer');
});

// doc-compliance-test
test('#2521 AC-15: die neuen Bausteine tragen keinen Fliesstext ausserhalb von t() (nur das ⓘ-Zeichen ist erlaubt)', () => {
	const dateien = [
		'components/molecules/BegriffErklaerung.svelte',
		'components/molecules/Infobox.svelte',
		'components/ui/popover/popover-content.svelte'
	];
	for (const rel of dateien) {
		const datei = join(frontend, 'src', 'lib', rel);
		assert.ok(existsSync(datei), `${rel} existiert nicht`);
		const src = readFileSync(datei, 'utf-8');
		const markup = src
			.replace(/<script[\s\S]*?<\/script>/g, '')
			.replace(/<style[\s\S]*?<\/style>/g, '')
			.replace(/<!--[\s\S]*?-->/g, '');
		const ohneAusdruecke = markup.replace(/\{[^{}]*\}/g, '');
		// Allowlist (Entscheidung): das Symbol ⓘ ist ein Zeichen, keine Sprache.
		const text = ohneAusdruecke.replace(/<[^>]*>/g, ' ').replace(/ⓘ/g, '').trim();
		assert.equal(text, '', `${rel}: Fliesstext im Markup: "${text}"`);
		const code = src.replace(/<style[\s\S]*?<\/style>/g, '');
		assert.doesNotMatch(
			code,
			/(aria-label|title|alt|placeholder)="[^"{]*[A-Za-zÄÖÜäöü]{3,}[^"]*"/,
			`${rel}: deutscher Text in einem Attribut statt aus dem Katalog`
		);
	}
});
