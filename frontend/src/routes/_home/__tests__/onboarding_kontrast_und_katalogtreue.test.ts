// TDD RED — Onboarding S2, AC-17: Willkommen und Startklar-Checkliste
//   (a) zeigen ausschliesslich Texte aus dem Katalog (onboarding.*) plus Datum,
//       gemessen am GERENDERTEN Teilbaum, nicht am Quelltext;
//   (b) deklarieren Textfarben mit mindestens 4.5:1 (WCAG-AA) und nie --g-ink-4.
// Spec docs/specs/modules/onboarding_willkommen_checkliste.md; Muster
// lib/components/molecules/begriff_erklaerung_kontrast_und_tippflaeche.test.ts (S1).
//
// Gemessen wird NUR im Teilbaum der neuen Bausteine (data-testid
// "onboarding-willkommen" / "startklar-checkliste") plus dem uebersetzten CSS von
// StartklarCheckliste.svelte und EmptyKachel.svelte — die Wordmark der Seite nutzt
// --g-ink-4 als Bestand und darf diese Messung nicht verfaelschen.
//
// Vertrag an die Implementierung:
//   * Der Willkommens-Hinweis lebt in EmptyKachel.svelte (Spec: MODIFY
//     „Willkommens-Inhalt"); eigene Stile dort oder inline — eine andere Datei
//     waere fuer diese Messung unsichtbar.
//   * StartklarCheckliste.svelte deklariert Textfarbe UND Hintergrund als
//     var(--g-…)-Token, die in app.css als #rrggbb stehen (Inline-Stil oder <style>).
//   * Jede im Teilbaum deklarierte Textfarbe hat >= 4.5:1 gegen jeden dort
//     deklarierten Hintergrund, ohne eigenen Hintergrund gegen --g-card UND --g-paper.
//     (--g-accent #c45a2a erreicht auf Weiss nur ~4.3:1 und ist als Textfarbe damit raus.)
//
//   cd frontend && npm test -- src/routes/_home/__tests__/onboarding_kontrast_und_katalogtreue.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { compile } from 'svelte/compiler';
import {
	FRONTEND,
	CHECKLISTE_DATEI,
	EMPTY_KACHEL_DATEI,
	KATALOG,
	renderStartseite,
	teilbaum,
	sichtbar,
	onboardingNeu
} from '../../__tests__/onboardingSsr.ts';

const APP_CSS = readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8');

function token(name: string): string {
	const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
	assert.ok(m, `Token --${name} ist in app.css nicht als #rrggbb definiert`);
	return m![1];
}
function luminanz(hex: string): number {
	const k = (i: number) => {
		const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
		return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * k(0) + 0.7152 * k(1) + 0.0722 * k(2);
}
function kontrast(a: string, b: string): number {
	const [h, d] = [luminanz(a), luminanz(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}
function tokensFuer(stil: string, eigenschaft: RegExp): string[] {
	const re = new RegExp(`(?:^|[;{\\s"])${eigenschaft.source}\\s*:\\s*var\\(--(g-[a-z0-9-]+)\\)`, 'g');
	return [...stil.matchAll(re)].map((m) => m[1]);
}
function komponentenCss(datei: string): string {
	if (!existsSync(datei)) return '';
	const quelle = readFileSync(datei, 'utf-8');
	return compile(quelle, { generate: 'server', filename: datei }).css?.code ?? '';
}
function inlineStile(html: string): string {
	return [...html.matchAll(/style="([^"]*)"/g)].map((m) => m[1]).join(';\n');
}

/** Startseite eines neuen Nutzers in allen Text-Zustaenden (ohne/mit Testmail, Tarif mit SMS). */
function teilbaeume(): { name: string; html: string }[] {
	const zustaende = [
		onboardingNeu(),
		onboardingNeu({ testMailSentAt: '2026-10-16T10:00:00Z', telegramVerknuepft: true, emailVerified: true, smsAllowed: true, premiumSmsAllowed: true })
	];
	const aus: { name: string; html: string }[] = [];
	for (const [i, o] of zustaende.entries()) {
		const html = renderStartseite({ onboarding: o, trips: [], presets: [] });
		for (const id of ['onboarding-willkommen', 'startklar-checkliste']) {
			const t = teilbaum(html, id);
			assert.ok(t, `${id} fehlt im Zustand ${i} — Messaufbau leer`);
			aus.push({ name: `${id}#${i}`, html: t! });
		}
	}
	return aus;
}

describe('AC-17: gerenderte Texte stammen vollstaendig aus dem Katalog', () => {
	test('nach Abzug aller onboarding.*-Katalogtexte und Datumswerte bleibt kein Wort uebrig', () => {
		const werte = Object.entries(KATALOG)
			.filter(([k]) => k.startsWith('onboarding.'))
			.map(([, v]) => v)
			.filter((v) => v.trim().length > 0)
			.sort((a, b) => b.length - a.length);
		assert.ok(werte.length > 0, 'keine onboarding.*-Texte im Katalog — Messaufbau leer');
		for (const { name, html } of teilbaeume()) {
			let rest = sichtbar(html);
			for (const w of werte) rest = rest.split(w).join(' ');
			rest = rest.replace(/\b\d{2}\.\d{2}\.\d{4}\b/g, ' ');
			const woerter = rest.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? [];
			assert.deepEqual(woerter, [], `${name}: Text ausserhalb des Katalogs: "${rest.trim()}"`);
		}
	});
	test('Gegenprobe: ein hart codierter Text wird erkannt', () => {
		// #2651: „Willkommen bei Gregor 20“ ist seit F2 Katalogtext (onboarding.leer.titel).
		let rest = sichtbar('<p>Hart codierter Hinweis ohne Katalog</p>');
		for (const w of Object.entries(KATALOG).filter(([k]) => k.startsWith('onboarding.')).map(([, v]) => v)) {
			if (w.trim()) rest = rest.split(w).join(' ');
		}
		assert.ok((rest.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? []).length > 0);
	});
});

describe('AC-17: Kontrast mindestens 4.5:1, nie --g-ink-4', () => {
	test('StartklarCheckliste deklariert Textfarbe und Hintergrund als var(--g-…)', () => {
		assert.ok(existsSync(CHECKLISTE_DATEI), 'StartklarCheckliste.svelte existiert nicht');
		const html = renderStartseite({ onboarding: onboardingNeu(), trips: [], presets: [] });
		const c = teilbaum(html, 'startklar-checkliste') ?? '';
		const stil = `${inlineStile(c)}\n${komponentenCss(CHECKLISTE_DATEI)}`;
		assert.ok(tokensFuer(stil, /color/).length > 0, 'keine Textfarbe als var(--g-…) deklariert');
		assert.ok(tokensFuer(stil, /background(?:-color)?/).length > 0, 'kein Hintergrund als var(--g-…) deklariert');
	});

	test('jede deklarierte Textfarbe in Willkommen/Checkliste hat >= 4.5:1 auf ihrem Hintergrund', () => {
		let geprueft = 0;
		const jeBaustein = { willkommen: 0, checkliste: 0 };
		for (const { name, html } of teilbaeume()) {
			const stil = `${inlineStile(html)}\n${name.startsWith('startklar') ? komponentenCss(CHECKLISTE_DATEI) : komponentenCss(EMPTY_KACHEL_DATEI)}`;
			const farben = tokensFuer(stil, /color/);
			const eigene = tokensFuer(stil, /background(?:-color)?/);
			const gruende = eigene.length > 0 ? eigene : ['g-card', 'g-paper'];
			for (const f of farben) {
				for (const g of gruende) {
					const k = kontrast(token(f), token(g));
					assert.ok(k >= 4.5, `${name}: --${f} auf --${g} hat nur ${k.toFixed(2)}:1`);
					geprueft++;
					jeBaustein[name.startsWith('startklar') ? 'checkliste' : 'willkommen']++;
				}
			}
		}
		assert.ok(jeBaustein.checkliste > 0, 'Checkliste: keine Textfarbe gemessen');
		assert.ok(jeBaustein.willkommen > 0, 'Willkommen: keine Textfarbe gemessen (Stile in EmptyKachel.svelte oder inline deklarieren)');
		assert.ok(geprueft > 0, 'keine einzige Textfarbe gemessen — Messaufbau leer');
	});

	test('kein --g-ink-4 in Willkommen, Checkliste oder deren Komponenten-CSS', () => {
		for (const { name, html } of teilbaeume()) {
			assert.ok(!html.includes('--g-ink-4'), `${name}: --g-ink-4 (2.85:1) im gerenderten Teilbaum`);
		}
		for (const datei of [CHECKLISTE_DATEI, EMPTY_KACHEL_DATEI]) {
			assert.ok(!komponentenCss(datei).includes('--g-ink-4'), `${path.basename(datei)}: --g-ink-4 im CSS`);
		}
	});

	test('Gegenprobe Messaufbau: --g-ink-4 auf Weiss faellt unter 4.5:1, --g-ink-2 nicht', () => {
		assert.ok(kontrast(token('g-ink-4'), token('g-card')) < 4.5);
		assert.ok(kontrast(token('g-ink-2'), token('g-card')) >= 4.5);
		assert.deepEqual(tokensFuer('background-color: var(--g-card); color: var(--g-ink-2)', /color/), ['g-ink-2']);
	});
});
