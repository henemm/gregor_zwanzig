// TDD RED — E2E (Staging), Issue #1727 S5e (B): die Konto-Seite beschriftet
// den Scheduler-Tick ehrlich und behauptet keinen Termin, den es nicht gibt.
//
// Spec: docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md
//   AC-4  sichtbarer Text "Nächste Prüfung" statt "Nächster"
//   AC-9  kein Termin -> "—", kein aus dem Nullwert abgeleitetes Datum
//
// WARUM IM BROWSER UND NICHT PER GREP: Die Beschriftung ist statisches Markup
// (`account/+page.svelte:599`), die Formatierung entsteht erst beim Rendern.
// Ein Dateiinhalt-Check auf `+page.svelte` ist als Nachweis ausdruecklich
// untersagt (Spec AC-4; CLAUDE.md "Test-Politik") — er belegt kein Verhalten.
//
// WAS HIER BEWUSST NICHT GEPRUEFT WIRD: der Zonenwechsel (AC-7). Auf Staging
// startet der Scheduler nie (`scheduler_gate.go:11-13`, `env=staging`, Issue
// #1329 — geteiltes Open-Meteo-Kontingent), `/api/scheduler/status` liefert
// dort fuer alle zehn Jobs dauerhaft `next_run: "0001-01-01T00:00:00Z"`. Es
// gibt also keinen echten Termin, gegen den zwei Zonen vergleichbar waeren;
// der lokale E2E-Stack faehrt aus demselben Grund ohne Scheduler
// (`ci-stack.sh:57`), und Prod-Testlaeufe sind verboten. Ein Stub im Browser
// hilft nicht, weil die Seite serverseitig laedt (`+page.server.ts:23`).
// Der Zonenwechsel ist deshalb im Unit-Test belegt (AC-5, konkrete Sollwerte);
// das Nachholen im Browser ist Issue #1972. Diese Datei behauptet ihn NICHT.
//
// Genau dieser Umstand macht aber AC-9 hier besonders gut pruefbar: der
// Nullwert liegt auf Staging ECHT an, nicht gestellt.
//
// RED-Grund (gemessen 2026-08-19): Staging traegt den alten Stand und zeigt
// "Nächster: 01.01., 01:05" — die alte Beschriftung UND der durchformatierte
// Nullwert. Die krumme Uhrzeit stammt daher, dass Wien im Jahr 1 eine Ortszeit
// von +01:05 gegenueber UTC hatte.
//
// Ausfuehren (aus frontend/, gegen Staging):
//   npx playwright test --config=e2e/playwright.konto-naechste-pruefung.staging.config.ts

import { test, expect, type Browser, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_STATE = path.join(__dirname, 'playwright', '.auth', 'staging-1727-s5e.json');
const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';

/** Die Zeile im Bereich "Deine Reports", die den naechsten Lauf zeigt.
 *  Bewusst gegen BEIDE Beschriftungen gematcht (alt "Nächster:", neu
 *  "Nächste Prüfung:") — sonst faende der Test im RED-Zustand gar nichts und
 *  meldete "Element nicht da" statt des tatsaechlichen Ist-Textes. */
async function schedulerZeile(page: Page): Promise<string> {
	const zeile = page
		.locator('#system-status span')
		.filter({ hasText: /(Nächste Prüfung|Nächster):/ })
		.first();
	await expect(zeile, 'Zeile mit dem naechsten Lauf im Bereich "Deine Reports"').toBeVisible({
		timeout: 20_000
	});
	return (await zeile.innerText()).trim();
}

/** Konto-Seite in einem Browser-Kontext mit fest gesetzter Zeitzone oeffnen.
 *  `browser.newContext()` erbt die `use`-Optionen der Config NICHT — Basis-URL,
 *  nginx-Zugang und Anmeldezustand muessen hier explizit mitgegeben werden.
 *
 *  Die Zone wird gesetzt, obwohl AC-7 hier nicht geprueft wird: AC-4 und AC-9
 *  muessen in JEDER Zone gelten, und ein zonenabhaengiges Ergebnis waere ein
 *  Befund. */
async function kontoSeiteInZone(browser: Browser, timezoneId: string): Promise<string> {
	const ctx = await browser.newContext({
		baseURL: BASE,
		timezoneId,
		storageState: AUTH_STATE,
		ignoreHTTPSErrors: true,
		httpCredentials: {
			username: process.env.GZ_VALIDATOR_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
		}
	});
	try {
		const page = await ctx.newPage();
		await page.goto('/account', { waitUntil: 'domcontentloaded' });
		return await schedulerZeile(page);
	} finally {
		await ctx.close();
	}
}

test.describe('#1727 S5e — Konto-Seite: ehrliche Beschriftung und kein Fantasie-Termin', () => {
	test.beforeAll(() => {
		assertNotProdBaseURL(BASE);
	});

	test('AC-4: die Zeile heisst "Nächste Prüfung", nicht "Nächster"', async ({ browser }) => {
		const text = await kontoSeiteInZone(browser, 'Europe/Vienna');

		expect(
			text,
			`Sichtbarer Text der Scheduler-Zeile: ${JSON.stringify(text)} — erwartet die ` +
				`Beschriftung "Nächste Prüfung:". "Nächster:" gibt den generischen ` +
				`stuendlichen Poll-Tick faelschlich als Versandtermin aus.`
		).toContain('Nächste Prüfung:');
		expect(
			text,
			`Die alte Beschriftung "Nächster:" steht noch in ${JSON.stringify(text)}.`
		).not.toMatch(/Nächster:/);
	});

	test('AC-9: ohne echten Termin steht ein Gedankenstrich, kein abgeleitetes Datum', async ({
		browser
	}) => {
		// Staging liefert echt den Go-Nullwert (siehe Kopf) — der Fall ist hier
		// nicht gestellt, sondern der Normalzustand dieser Umgebung.
		const wien = await kontoSeiteInZone(browser, 'Europe/Vienna');
		const newYork = await kontoSeiteInZone(browser, 'America/New_York');

		for (const [zone, wert] of [
			['Europe/Vienna', wien],
			['America/New_York', newYork]
		] as const) {
			expect(
				wert,
				`In ${zone}: ${JSON.stringify(wert)} — erwartet "Nächste Prüfung: —". Eine ` +
					`Uhrzeit an dieser Stelle ist der durchformatierte Nullwert und behauptet ` +
					`einen Termin, den der Scheduler nie gesetzt hat.`
			).not.toMatch(/\d{1,2}:\d{2}/);
			expect(wert, `In ${zone} fehlt der Gedankenstrich: ${JSON.stringify(wert)}`).toContain('—');
		}

		// Zonenunabhaengig: dieselbe Aussage in beiden Zonen. Waere sie es nicht,
		// haenge die Nullwert-Erkennung an der Zone — das waere ein Befund.
		expect(
			newYork,
			`Wien zeigt ${JSON.stringify(wien)}, New York ${JSON.stringify(newYork)} — die ` +
				`Erkennung "kein Termin" darf nicht von der Browser-Zone abhaengen.`
		).toBe(wien);
	});
});
