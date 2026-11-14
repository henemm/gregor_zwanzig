// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Englisch.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-35
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich), Sprache `en` am Konto.
//
//   Kopf, Unterzeile, Tabellenkopf (Singular/Plural), Spaltenkoepfe, Legende, Stille Stunden kommen aus
//   en/zustellung.json; kein deutscher Text aus de/zustellung.json ist im Reiter (ausserhalb des
//   Uebergangsblocks) sichtbar. Sprache wird am Ende auf `de` zurueckgesetzt.
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-englisch

import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { HUB_KINDS } from './helpers';
import { DESKTOP, MARKER, ZT, oeffneZustellung, seedZustellung } from './s3b2795-zustellung.helpers';

const KATALOG = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'i18n', 'messages');
const laden = (sprache: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(KATALOG, sprache, 'zustellung.json'), 'utf8'));

for (const kind of HUB_KINDS) {
	test(`AC-35 (${kind}): Reiter Zustellung auf Englisch — Katalogtexte en, kein deutscher Katalogtext`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const en = laden('en');
		const de = laden('de');
		const hub = await seedZustellung(page.request, kind);
		try {
			const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
			expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
			const reiter = await oeffneZustellung(page, kind, hub.id);

			const englisch = new Set(Object.values(en));
			const erklaerKey = Object.keys(de).find((k) => de[k] === 'Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.');
			expect(erklaerKey, 'Kopf-Erklaerung fehlt in de/zustellung.json').toBeTruthy();
			await expect(reiter.getByTestId(ZT.erklaer)).toHaveText(en[erklaerKey!]);
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).not.toContainText('Kanal');
			await expect(reiter.getByTestId(ZT.kanaeleKopf)).not.toContainText('über');

			const teile: string[] = [];
			for (const m of MARKER.filter((x) => x !== 'uebergang')) for (const el of await reiter.locator(`[data-abschnitt="${m}"]`).all()) teile.push(await el.innerText());
			const text = teile.join('\n');
			for (const [k, deutsch] of Object.entries(de)) {
				if (englisch.has(deutsch) || deutsch.includes('{') || deutsch.length < 6) continue;
				expect(text, `deutscher Katalogtext ${k} im englischen Reiter: „${deutsch}“`).not.toContain(deutsch);
			}
			// Datenwerte bleiben unuebersetzt, Optionen lokalisiert (AC-17): keine deutschen Stufenwoerter.
			expect(text).not.toMatch(/\b(gering|mittel|hoch)\b/);
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
