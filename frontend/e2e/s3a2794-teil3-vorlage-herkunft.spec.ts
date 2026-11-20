// E2E (Staging) — Issue #3189: Herkunft eigener Wetter-Vorlagen, AC-6 (dazu AC-1 live).
// Spec: docs/specs/modules/feat_3189_vorlage_herkunft.md
// Derselbe Test-Code für Trip (route) und Orts-Vergleich (vergleich).
//
//   AC-6 — Vorlage OHNE Beschreibung aus dem Reiter Wetter speichern: die POST-Antwort trägt
//          herkunft {id, name} des Trips bzw. Vergleichs (AC-1), das Menü zeigt sofort ohne Neuladen
//          „eigene · aus <Name> gespeichert“; Testvorlage und Hub werden im finally aufgeräumt.
//          #3192 AC-8 (mit Beschreibung) bleibt in s3a2794-teil3-vorlage.spec.ts unverändert.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-vorlage-herkunft

import { test, expect } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, stand, type Json } from './s3a2794-teil3.helpers';

for (const kind of HUB_KINDS) {
	test(`#3189 AC-6 (${kind}): Vorlage ohne Beschreibung speichern, ohne Neuladen „eigene · aus <Name> gespeichert“`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking' });
		const name = `E2E-GZ-3189-${kind}-${Date.now()}`;
		let presetId: string | null = null;
		try {
			const aboName = String((await stand(page.request, kind, hub.id)).name ?? '');
			expect(aboName, 'Hub ohne Namen geseedet').not.toBe('');

			const reiter = await oeffneWetter(page, kind, hub.id);
			await reiter.getByTestId(WT.alsEigene).click();
			const dialog = page.getByTestId(WT.dialog);
			await dialog.getByTestId(WT.dialogName).fill(name);
			const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/metric-presets');
			await dialog.getByTestId(WT.dialogSpeichern).click();
			const antwort = await post;
			expect(antwort.ok(), `POST /api/metric-presets: ${antwort.status()}`).toBeTruthy();
			const body = (await antwort.json()) as Json;
			presetId = String(body.id);

			// AC-1 live: Herkunft am gespeicherten Datensatz, Name zum Speicherzeitpunkt.
			expect(body.herkunft, `POST-Antwort ohne herkunft: ${JSON.stringify(body)}`).toEqual({ id: hub.id, name: aboName });
			expect(body.description ?? '', 'Test speichert bewusst ohne Beschreibung').toBe('');
			await expect(page.getByTestId(WT.dialogErfolg)).toBeVisible({ timeout: 15_000 });

			// ohne page.reload(): Menü öffnen und die neue Zeile lesen
			await reiter.getByTestId(WT.picker).click();
			const zeile = page.getByTestId(WT.eigeneOption(presetId));
			await expect(zeile).toContainText(name);
			await expect(zeile).toContainText(`eigene · aus ${aboName} gespeichert`);
			await page.keyboard.press('Escape');

			// Gespeichert (nicht nur angezeigt): Liste per API trägt die Herkunft.
			const liste = (await (await page.request.get('/api/metric-presets')).json()) as Json[];
			const gespeichert = liste.find((p) => p.id === presetId);
			expect(gespeichert?.herkunft, 'herkunft fehlt in GET /api/metric-presets').toEqual({ id: hub.id, name: aboName });
		} finally {
			if (presetId) await page.request.delete(`/api/metric-presets/${presetId}`).catch(() => {});
			else
				for (const p of (await (await page.request.get('/api/metric-presets')).json().catch(() => [])) as Json[])
					if (p.name === name) await page.request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
