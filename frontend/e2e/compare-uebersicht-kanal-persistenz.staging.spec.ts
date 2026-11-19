// gz-eigenstaendig: Kanal-Spalten der transponierten Vergleichs-Uebersicht (Orte = Spalten) in der Karte „Was steht wo“ -- erlaubte Compare-Eigenheit; Trip-Pendant: layout-tab-route.spec.ts, kanal-abwahl-bleibt-reversibel.staging.spec.ts
// E2E (Staging) — #1703 Scheibe 8: kanal-eigene Uebersichts-Auswahl ueberlebt Speichern und Neuladen.
// ACs: AC-S8-4, AC-S8-6, AC-S8-10, AC-S8-11, Rollback. Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die Kanal-Reiter sind aus dem Reiter Zustellung
// entfernt; die Wirkung heisst heute: Haken je Kanal-Spalte der Karte „Was steht wo“ (Reiter Wetter), gespeichert in
// `display_config.placements` — `channel_active_metrics` ist Altfeld und bleibt unberuehrt.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/compare-uebersicht-kanal-persistenz.staging.spec.ts

import { test, expect } from '@playwright/test';
import { folge, gespeichertAn, haken, oeffneKarte, seedAbo, stand, tabelle, tabelleGespeichert, zeile } from './was-steht-wo.helpers';

const KANAELE = ['email', 'telegram', 'sms'] as const;

test.describe('#1703 S8: Kanal-eigene Uebersichts-Auswahl ueberlebt Speichern und Neuladen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test('AC-S8-10/AC-S8-4: drei nacheinander editierte Kanaele bleiben ALLE erhalten, eine globale Abwahl schreibt durch', async ({ page }) => {
		const abo = await seedAbo(page.request, 'vergleich');
		try {
			let karte = await oeffneKarte(page, 'vergleich', abo.id);
			const zeilen = await folge(karte);
			expect(zeilen.length, 'Messaufbau: mindestens vier Zeilen').toBeGreaterThanOrEqual(4);
			const altfeld = (await stand(page.request, 'vergleich', abo.id)).display_config.channel_active_metrics ?? null;
			for (const [i, k] of KANAELE.entries()) {
				const gespeichert = tabelleGespeichert(page, abo.id);
				await haken(karte, zeilen[i], k).click();
				await gespeichert;
			}
			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			const p = (await tabelle(page.request, 'vergleich', abo.id)).placements;
			for (const [i, k] of KANAELE.entries()) {
				await expect(haken(karte, zeilen[i], k), `AC-S8-10: ${k} verloren`).not.toBeChecked();
				expect(gespeichertAn(p, zeilen[i], k), `AC-S8-10: ${k} nicht gespeichert`).toBe(false);
			}
			expect((await stand(page.request, 'vergleich', abo.id)).display_config.channel_active_metrics ?? null, 'Altfeld unberuehrt').toEqual(altfeld);

			const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/compare/presets/${abo.id}`), { timeout: 20_000 });
			await page.locator(`[data-testid="wetter-zeile-entfernen-${zeilen[3]}"]:visible`).first().click();
			expect((await put).ok()).toBeTruthy();
			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			await expect(zeile(karte, zeilen[3]), 'AC-S8-4: global abgewaehlt').toHaveCount(0);
			expect(((await tabelle(page.request, 'vergleich', abo.id)).placements.rows as Array<{ metric_id: string }>).map((r) => r.metric_id), 'AC-S8-4: aus der gespeicherten Tabelle').not.toContain(zeilen[3]);
		} finally {
			await abo.aufraeumen();
		}
	});

	test('AC-S8-11/AC-S8-6: eine bewusst geleerte SMS-Spalte bleibt leer, ein wieder eingeschalteter Wert steht allein', async ({ page }) => {
		const abo = await seedAbo(page.request, 'vergleich');
		try {
			let karte = await oeffneKarte(page, 'vergleich', abo.id);
			const zeilen = await folge(karte);
			const bedienbar: string[] = [];
			for (const m of zeilen) {
				const h = haken(karte, m, 'sms');
				if ((await h.count()) && (await h.isEnabled()) && (await h.isChecked())) bedienbar.push(m);
			}
			expect(bedienbar.length, 'Messaufbau').toBeGreaterThan(1);
			for (const m of bedienbar) {
				const gespeichert = tabelleGespeichert(page, abo.id);
				await haken(karte, m, 'sms').click();
				await gespeichert;
			}
			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			for (const m of bedienbar) await expect(haken(karte, m, 'sms'), `AC-S8-11: ${m} faellt auf die Grundauswahl zurueck`).not.toBeChecked();
			const gespeichert = tabelleGespeichert(page, abo.id);
			await haken(karte, bedienbar[0], 'sms').click();
			await gespeichert;
			await page.reload();
			karte = await oeffneKarte(page, 'vergleich', abo.id);
			await expect(haken(karte, bedienbar[0], 'sms')).toBeChecked();
			for (const m of bedienbar.slice(1)) await expect(haken(karte, m, 'sms'), `AC-S8-6: ${m} mit eingeschaltet`).not.toBeChecked();
		} finally {
			await abo.aufraeumen();
		}
	});

	test('Rollback: scheitert der PUT der Tabelle, springt der Haken auf den gespeicherten Stand zurueck und eine Meldung steht da', async ({ page }) => {
		const abo = await seedAbo(page.request, 'vergleich');
		try {
			const karte = await oeffneKarte(page, 'vergleich', abo.id);
			const m = (await folge(karte))[0];
			await expect(haken(karte, m, 'email')).toBeChecked();
			await page.route(`**/api/briefings/${abo.id}/placements**`, (route) =>
				route.request().method() === 'PUT' ? route.fulfill({ status: 500, json: { error: 'boom' } }) : route.continue()
			);
			await haken(karte, m, 'email').click();
			await expect(karte.getByTestId('was-steht-wo-meldung'), 'Meldung bei gescheitertem Speichern').toBeVisible({ timeout: 15_000 });
			await expect(haken(karte, m, 'email'), 'Haken springt auf den gespeicherten Stand').toBeChecked({ timeout: 15_000 });
			expect((await tabelle(page.request, 'vergleich', abo.id)).stored, 'nichts gespeichert').toBe(false);
		} finally {
			await abo.aufraeumen();
		}
	});
});
