// TDD RED — Epic #1273 Slice S3: Die alte Bearbeiten-Route /compare/[id]/edit
// wird zu einem reinen 307-Redirect auf den Hub /compare/[id]. Kein
// CompareEditor-Rendering mehr, keine 404-Seite.
//
// Spec: docs/specs/modules/feat_1273_s3_redirect.md
//   § Acceptance Criteria AC-1
//
// RED-Ursache (vor Implementation): +page.server.ts unter edit/ lädt heute noch
// preset/locations/profile und rendert die alte CompareEditor-Seite. Ein Aufruf
// von /compare/{id}/edit landet daher NICHT auf /compare/{id}, sondern bleibt auf
// der /edit-URL und rendert `compare-editor-name` (CompareEditor) statt der
// Hub-Tab-Leiste. Beide Assertions schlagen deshalb jetzt fehl. Das ist die
// ehrliche, erwartete RED-Ursache (Route noch nicht als Redirect verdrahtet),
// KEIN Login-Fehler. Echter Server-Round-Trip gegen Staging, kein Mock.
// Vorbild: compare-hub-name-region-profil.spec.ts (S2).
//
// Ausführen (Staging):
//   set -a; source /home/hem/gregor_zwanzig/.env
//   source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   cd frontend && npx playwright test \
//     --config=e2e/playwright.1273-s3.red.config.ts

import { test, expect, type Page } from '@playwright/test';

interface SeededPreset {
	presetId: string;
	locIds: string[];
}

/** Legt zwei Orte + ein Preset an, das beide vergleicht. Gibt IDs zurück. */
async function seedPreset(page: Page): Promise<SeededPreset> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 1273-S3 A ${suffix}`, 47.05, 11.05],
		[`E2E 1273-S3 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}

	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name: `E2E 1273-S3 ${suffix}`,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'allgemein',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00'
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds };
}

async function cleanup(page: Page, presetId: string, locIds: string[]) {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

test.describe('Epic #1273 S3 — /compare/[id]/edit ist reiner Redirect auf den Hub', () => {
	// AC-1: Direkter Aufruf der Altroute /compare/{id}/edit landet per Redirect auf
	// /compare/{id}, rendert den Hub (Tab-Leiste), NICHT die alte CompareEditor-Seite.
	test('AC-1: /compare/{id}/edit → Redirect auf /compare/{id}, Hub rendert, kein CompareEditor', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			await page.goto(`/compare/${presetId}/edit`);

			// Nach dem 307-Redirect steht die URL auf /compare/{id} — ohne /edit.
			await expect(page).toHaveURL(new RegExp(`/compare/${presetId}(\\?|$)`), {
				timeout: 10_000
			});
			expect(
				page.url().includes('/edit'),
				'AC-1: nach dem Redirect darf /edit nicht mehr in der URL stehen'
			).toBe(false);

			// Der Hub rendert tatsächlich (Tab-Leiste sichtbar).
			await expect(
				page.getByTestId('compare-detail-tab-list'),
				'AC-1: der Hub (Tab-Leiste) muss nach dem Redirect rendern'
			).toBeVisible({ timeout: 10_000 });

			// Die alte CompareEditor-Seite darf NICHT gerendert werden.
			await expect(
				page.getByTestId('compare-editor-name'),
				'AC-1: die alte CompareEditor-Seite darf nach dem Redirect nicht mehr rendern'
			).toHaveCount(0);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});
});
