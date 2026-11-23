// E2E (Staging / lokaler E2E-Stack) — Issue #3276 (Epic #3122, Spec-AC-38 zweiter Teil).
// Spec: docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md (AC-1, AC-2, AC-3, AC-5)
//
// RED-Erwartung (vor Umsetzung): im Anlege-Ablauf steht im Schritt Zustellung noch die alte
// Bedienflaeche Stundenverlauf/Ausblick (AC-3). Nach Bedienen dieser Flaechen traegt der
// POST Altschluessel (AC-1).
//
// Zwei echte Sessions (Nutzer A = storageState-Fixture, Nutzer B frisch registriert, AC-5).
// Aufraeumen: angelegte Vergleiche/Orte am Ende per API loeschen.

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation, registriereBestaetigtenZweitnutzer } from './helpers';
import { wegwerfPasswort } from './stagingZugang';

const ALTSCHLUESSEL = [
	'channel_layouts',
	'outlook_metrics',
	'outlook_metric_formats',
	'channel_active_metrics',
	'hourly_metrics',
	'hourly_metric_formats'
];

function altschluesselIn(dc: unknown): string[] {
	const o = (dc ?? {}) as Record<string, unknown>;
	return ALTSCHLUESSEL.filter((k) => Object.prototype.hasOwnProperty.call(o, k));
}

async function legeVergleichAn(page: Page, name: string, locIds: string[], dc?: Record<string, unknown>): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'allgemein',
			empfaenger: [],
			...(dc ? { display_config: dc } : {})
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	return (await res.json()).id as string;
}

test.describe('#3276 — Ortsvergleich ohne Altfelder', () => {
	test('AC-1/AC-3: Anlegen zeigt keine alte Stundenverlauf/Ausblick-Flaeche, POST ohne Altschluessel, Tabelle vorhanden', async ({
		page
	}) => {
		const suffix = Date.now();
		const l1 = await createTestLocation(page.request, { name: `E2E 3276 O1 ${suffix}`, lat: 46.5, lon: 11.8 });
		const l2 = await createTestLocation(page.request, { name: `E2E 3276 O2 ${suffix}`, lat: 46.6, lon: 11.9 });
		const vorlageId = await legeVergleichAn(page, `E2E 3276 Vorlage ${suffix}`, [l1.id, l2.id]);
		let neuId: string | undefined;
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/new?from=${vorlageId}`);
			await page.getByTestId('compare-editor-tab-wetter').click();
			await page.getByTestId('compare-editor-tab-zustellung').click();

			// AC-3: keine alte Bedienflaeche Stundenverlauf/Ausblick im Vergleich.
			await expect(page.getByTestId('weather-metrics-stundenverlauf')).toHaveCount(0);
			await expect(page.getByTestId('weather-metrics-ausblick')).toHaveCount(0);
			await expect(page.getByTestId('compare-layout-hourly-metrics')).toHaveCount(0);
			await expect(page.getByTestId('compare-layout-outlook-metrics')).toHaveCount(0);

			// AC-1: POST ohne Altschluessel.
			const postAbfang = page.waitForRequest(
				(r) => r.url().endsWith('/api/compare/presets') && r.method() === 'POST'
			);
			await page.getByRole('button', { name: 'Briefing aktivieren' }).click();
			const post = await postAbfang;
			const body = post.postDataJSON() as { display_config?: unknown };
			expect(altschluesselIn(body.display_config), 'Altschluessel im POST').toEqual([]);

			// Der angelegte Vergleich traegt die Tabelle „Was steht wo" (placements mit Zeilen).
			await page.waitForURL(/\/compare\/(?!new)[^/?]+/, { timeout: 15_000 });
			neuId = page.url().split('/compare/')[1].split(/[?#/]/)[0];
			const neu = await (await page.request.get(`/api/compare/presets/${neuId}`)).json();
			const rows = (neu.display_config?.placements?.rows ?? []) as unknown[];
			expect(rows.length, 'placements.rows leer nach Anlage').toBeGreaterThan(0);
			expect(altschluesselIn(neu.display_config), 'Altschluessel im neuen Vergleich').toEqual([]);
		} finally {
			if (neuId) await page.request.delete(`/api/compare/presets/${neuId}`);
			await page.request.delete(`/api/compare/presets/${vorlageId}`);
			await page.request.delete(`/api/locations/${l1.id}`);
			await page.request.delete(`/api/locations/${l2.id}`);
		}
	});

	test('AC-2/AC-5: Speichern im Hub sendet keinen Altschluessel, Bestand von A bleibt, B unberuehrt', async ({
		page: pageA,
		browser
	}) => {
		const suffix = Date.now();
		const alt = {
			hourly_metrics: ['temp_c'],
			outlook_metrics: ['temp_max_c'],
			channel_layouts: { email: ['temp_max_c'] }
		};
		const lA = await createTestLocation(pageA.request, { name: `E2E 3276 A ${suffix}`, lat: 46.7, lon: 11.7 });
		const idA = await legeVergleichAn(pageA, `E2E 3276 A ${suffix}`, [lA.id], { region: 'A', ...alt });

		const ctxB = await browser.newContext();
		const pageB = await ctxB.newPage();
		let idB: string | undefined;
		let lB: { id: string } | undefined;
		try {
			await registriereBestaetigtenZweitnutzer(pageA.request, pageB.request, 'e2e3276b' + suffix, wegwerfPasswort());
			lB = await createTestLocation(pageB.request, { name: `E2E 3276 B ${suffix}`, lat: 46.8, lon: 11.6 });
			idB = await legeVergleichAn(pageB, `E2E 3276 B ${suffix}`, [lB.id], { region: 'B', ...alt });
			const bVorher = await (await pageB.request.get(`/api/compare/presets/${idB}`)).json();

			// A aendert im Versand-Reiter etwas und speichert (echter UI-Speicherweg, PUT).
			const puts: Record<string, unknown>[] = [];
			pageA.on('request', (r) => {
				if (r.method() === 'PUT' && r.url().includes(`/api/compare/presets/${idA}`)) {
					puts.push((r.postDataJSON() ?? {}) as Record<string, unknown>);
				}
			});
			await pageA.goto(`/compare/${idA}`);
			await pageA.getByTestId('compare-editor-tab-zustellung').click();
			const schalter = pageA.getByRole('switch').first();
			await schalter.click();
			await expect.poll(() => puts.length, { timeout: 15_000 }).toBeGreaterThan(0);
			for (const b of puts) {
				expect(altschluesselIn(b.display_config), 'Altschluessel im PUT').toEqual([]);
			}

			const aNachher = await (await pageA.request.get(`/api/compare/presets/${idA}`)).json();
			for (const [k, v] of Object.entries(alt)) {
				expect(aNachher.display_config?.[k], `Bestand ${k} von A verloren`).toEqual(v);
			}
			const bNachher = await (await pageB.request.get(`/api/compare/presets/${idB}`)).json();
			expect(bNachher.display_config).toEqual(bVorher.display_config);
		} finally {
			if (idB) await pageB.request.delete(`/api/compare/presets/${idB}`);
			if (lB) await pageB.request.delete(`/api/locations/${lB.id}`);
			await ctxB.close();
			await pageA.request.delete(`/api/compare/presets/${idA}`);
			await pageA.request.delete(`/api/locations/${lA.id}`);
		}
	});
});
