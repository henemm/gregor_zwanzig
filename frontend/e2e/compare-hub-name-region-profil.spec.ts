// TDD RED — Epic #1273 Slice S2: Compare-Hub bekommt inline editierbare Felder
// für Name, Region und Aktivitätsprofil (Feature-Parität zum alten CompareEditor).
//
// Spec: docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md
//   § Acceptance Criteria AC-1 … AC-7
//
// In der RED-Phase schlagen ALLE sieben Tests fehl, weil der Hub-Kopfbereich
// (routes/compare/[id]/+page.svelte) heute den Namen nur als reinen Text-<h1>
// rendert — kein Stift-Icon, kein Eingabefeld, keine Profil-Kacheln, keine
// zugehörigen `data-testid`s. Die Tests scheitern am fehlenden Lookup der neuen
// Edit-Elemente (`compare-hub-name-edit-toggle`, `compare-hub-region-edit-toggle`,
// `compare-hub-profil-option-*`) — Timeout beim Warten. Das ist die ehrliche,
// erwartete RED-Ursache (fehlende UI, NICHT Login-Fehler). Kein Mock, echter
// Klick-Pfad, Nachweis über sichtbaren DOM + echte API-Round-Trips. Vorbild:
// compare-hub-save-chip.spec.ts (S1) + issue-758-save-indicator.spec.ts.
//
// Ausführen (Staging):
//   set -a; source /home/hem/gregor_zwanzig/.env
//   source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   cd frontend && npx playwright test \
//     --config=e2e/playwright.1273-s2.red.config.ts

import { test, expect, type Page } from '@playwright/test';

const PRESET_URL_PART = '/api/compare/presets/';

interface SeededPreset {
	presetId: string;
	locIds: string[];
	name: string;
}

/**
 * Legt zwei Orte + ein Preset an, das beide vergleicht — mit gesetztem
 * `schedule`, `empfaenger` und `profil`, damit der Datenverlust-Schutz (AC-4)
 * echte, nicht-leere Felder prüfen kann. Gibt IDs + den vergebenen Namen zurück.
 */
async function seedPreset(page: Page): Promise<SeededPreset> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 1273-S2 A ${suffix}`, 47.05, 11.05],
		[`E2E 1273-S2 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}

	const name = `E2E 1273-S2 ${suffix}`;
	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'allgemein',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00',
			display_config: { region: 'Ötztal' }
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds, name };
}

async function cleanup(page: Page, presetId: string, locIds: string[]) {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

/** Frischer GET des Presets (Server-Wahrheit für die Persistenz-Prüfungen). */
async function fetchPreset(page: Page, presetId: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`${PRESET_URL_PART}${presetId}`);
	expect(res.ok(), `GET preset HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

/** Sichtbarer Treffer (Desktop- UND Mobile-Block tragen denselben testid). */
function visible(page: Page, testid: string) {
	return page.locator(`[data-testid="${testid}"]:visible`);
}

test.describe('Epic #1273 S2 — Compare-Hub Name/Region/Aktivitätsprofil inline', () => {
	// AC-1: Name über Stift-Icon ändern → sofort im Kopfbereich sichtbar +
	// nach Reload persistiert.
	test('AC-1: Name im Hub ändern → sofort sichtbar + nach Reload persistent', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		const neu = `Umbenannt ${Date.now()}`;
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await expect(
				visible(page, 'compare-hub-name-edit-toggle'),
				'AC-1: der Hub-Kopfbereich muss ein Stift-Icon zum Umbenennen rendern'
			).toBeVisible({ timeout: 10_000 });
			await visible(page, 'compare-hub-name-edit-toggle').click();

			await visible(page, 'compare-hub-name-edit').fill(neu);
			await visible(page, 'compare-hub-name-save').click();

			// Sofort sichtbar (kein Reload).
			await expect(page.getByRole('heading', { level: 1 })).toContainText(neu, { timeout: 5_000 });

			// Persistenz nach Reload.
			await page.reload();
			await expect(page.getByRole('heading', { level: 1 })).toContainText(neu, { timeout: 10_000 });
			expect((await fetchPreset(page, presetId)).name).toBe(neu);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-2: Region über Stift-Icon ändern → Unterzeile aktualisiert +
	// display_config.region nach Reload persistiert.
	test('AC-2: Region im Hub ändern → sichtbar + display_config.region persistent', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		const neu = `Zillertal ${Date.now()}`;
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await expect(
				visible(page, 'compare-hub-region-edit-toggle'),
				'AC-2: der Hub-Kopfbereich muss ein Stift-Icon zum Ändern der Region rendern'
			).toBeVisible({ timeout: 10_000 });
			await visible(page, 'compare-hub-region-edit-toggle').click();

			await visible(page, 'compare-hub-region-edit').fill(neu);
			await visible(page, 'compare-hub-region-save').click();

			// Sofort sichtbar in der Kontext-Unterzeile.
			await expect(page.getByText(neu, { exact: false }).first()).toBeVisible({ timeout: 5_000 });

			await page.reload();
			const preset = await fetchPreset(page, presetId);
			const dc = preset.display_config as { region?: string } | undefined;
			expect(dc?.region).toBe(neu);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-3: Aktivitätsprofil-Kachel anklicken → neue Kachel markiert +
	// profil nach Reload persistiert.
	test('AC-3: Aktivitätsprofil-Kachel wählen → markiert + persistent', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			const kachel = visible(page, 'compare-hub-profil-option-wandern');
			await expect(
				kachel,
				'AC-3: der Hub-Kopfbereich muss die Aktivitätsprofil-Kacheln rendern'
			).toBeVisible({ timeout: 10_000 });
			await kachel.click();

			await expect(kachel).toHaveAttribute('data-selected', 'true', { timeout: 5_000 });

			await page.reload();
			expect((await fetchPreset(page, presetId)).profil).toBe('wandern');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-4 (Datenverlust-Schutz, Teil-Edit): NUR den Namen ändern darf
	// location_ids/empfaenger/schedule/profil NICHT auf Zero-Value zurücksetzen.
	test('AC-4: nur Name ändern → location_ids/empfaenger/schedule/profil unverändert', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		const neu = `NurName ${Date.now()}`;
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await expect(
				visible(page, 'compare-hub-name-edit-toggle'),
				'AC-4: Stift-Icon zum Umbenennen muss existieren'
			).toBeVisible({ timeout: 10_000 });
			await visible(page, 'compare-hub-name-edit-toggle').click();
			await visible(page, 'compare-hub-name-edit').fill(neu);
			await visible(page, 'compare-hub-name-save').click();
			await expect(page.getByRole('heading', { level: 1 })).toContainText(neu, { timeout: 5_000 });

			// Server-Wahrheit: der Teil-Edit darf die anderen Felder nicht leeren.
			const preset = await fetchPreset(page, presetId);
			expect(preset.name).toBe(neu);
			expect((preset.location_ids as string[]).length).toBe(2);
			expect((preset.empfaenger as string[]).length).toBe(1);
			expect(preset.schedule).toBe('daily');
			expect(preset.profil).toBe('allgemein');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-5 (Datenverlust-Schutz, Cross-Tab): Header-Name ändern, danach im selben
	// Seitenaufenthalt einen Wert im Wertebereiche-Tab committen → Name bleibt neu.
	test('AC-5: Name ändern, dann Wertebereiche-Commit → Name bleibt erhalten', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		const neu = `CrossTab ${Date.now()}`;
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			// 1) Namen im Header ändern + speichern.
			await expect(
				visible(page, 'compare-hub-name-edit-toggle'),
				'AC-5: Stift-Icon zum Umbenennen muss existieren'
			).toBeVisible({ timeout: 10_000 });
			await visible(page, 'compare-hub-name-edit-toggle').click();
			await visible(page, 'compare-hub-name-edit').fill(neu);
			await visible(page, 'compare-hub-name-save').click();
			await expect(page.getByRole('heading', { level: 1 })).toContainText(neu, { timeout: 5_000 });

			// 2) Im SELBEN Seitenaufenthalt (kein Reload/goto — sonst würde der Test
			//    auch bei einer fehlerhaften In-Place-Mutation grün sein, weil ein
			//    Reload den Namen ohnehin frisch vom Server lädt, Adversary-Fund F001)
			//    per In-Page-Klick in den Wertebereiche-Tab wechseln, eine Metrik
			//    hinzufügen (löst PUT aus) und einen Wert per blur() committen.
			await page.getByTestId('compare-detail-tab-idealwerte').click();
			await expect(page.getByTestId('compare-detail-panel-idealwerte')).toBeVisible({
				timeout: 10_000
			});
			await page.getByRole('button', { name: '＋ Schneehöhe' }).click();
			const table = page.getByTestId('corridor-editor-table');
			const field = table.locator('input[type="number"]').first();
			await expect(field).toBeVisible({ timeout: 10_000 });
			await field.focus();
			await field.fill('42');
			await field.blur();
			await page.waitForTimeout(2_000);

			// 3) Der Cross-Tab-Commit darf den Namen NICHT zurückgesetzt haben.
			expect((await fetchPreset(page, presetId)).name).toBe(neu);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-6 (Mobile-Parität): identische Edit-Fähigkeit im Mobile-Viewport (≤899px).
	test('AC-6: Mobile-Viewport — Name inline editierbar wie Desktop', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		const neu = `Mobil ${Date.now()}`;
		try {
			await page.setViewportSize({ width: 375, height: 812 });
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			// Sichtbarkeitsfilter Pflicht: der Desktop-Block bleibt im DOM (CSS-hidden).
			await expect(
				visible(page, 'compare-hub-name-edit-toggle'),
				'AC-6: das Stift-Icon muss auch im Mobile-Markup sichtbar/klickbar sein'
			).toBeVisible({ timeout: 10_000 });
			await visible(page, 'compare-hub-name-edit-toggle').click();
			await visible(page, 'compare-hub-name-edit').fill(neu);
			await visible(page, 'compare-hub-name-save').click();

			// Sichtbarkeitsfilter Pflicht (anders als bei AC-1 auf Desktop-Viewport):
			// der Desktop-<h1> mit demselben Namen bleibt CSS-hidden im DOM und steht
			// im Markup VOR dem Mobile-<span> — .first() traefe ohne Filter ihn statt
			// den tatsaechlich sichtbaren Mobile-Text.
			await expect(
				page.getByText(neu, { exact: false }).and(page.locator(':visible'))
			).toBeVisible({ timeout: 5_000 });

			await page.reload();
			expect((await fetchPreset(page, presetId)).name).toBe(neu);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-7 (Fehlerfall): PUT auf 500 stubben → Fehlermeldung sichtbar, Eingabe
	// bleibt offen (kein stiller Datenverlust), H1 zeigt weiterhin den alten Namen.
	test('AC-7: PUT scheitert (500) → Fehlermeldung + Eingabe bleibt, alter Name im H1', async ({
		page
	}) => {
		const { presetId, locIds, name } = await seedPreset(page);
		const versuch = `Fehlversuch ${Date.now()}`;
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await expect(
				visible(page, 'compare-hub-name-edit-toggle'),
				'AC-7: Stift-Icon zum Umbenennen muss existieren'
			).toBeVisible({ timeout: 10_000 });

			// Den PUT auf das Preset gezielt auf 500 abwürgen.
			await page.route(`**${PRESET_URL_PART}${presetId}`, (route) => {
				if (route.request().method() === 'PUT') {
					return route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
				}
				return route.continue();
			});

			await visible(page, 'compare-hub-name-edit-toggle').click();
			await visible(page, 'compare-hub-name-edit').fill(versuch);
			await visible(page, 'compare-hub-name-save').click();

			// Fehlermeldung erscheint.
			await expect(
				visible(page, 'compare-hub-name-save-error'),
				'AC-7: ein fehlgeschlagener PUT muss eine Fehlermeldung unter dem Feld zeigen'
			).toBeVisible({ timeout: 10_000 });

			// Eingabefeld bleibt offen mit der eingetippten (nicht verlorenen) Eingabe
			// — es gibt bei fehlgeschlagenem Save bewusst KEIN Zurueckspringen in den
			// Anzeige-Modus (kein <h1>, solange isEditingName true bleibt).
			await expect(visible(page, 'compare-hub-name-edit')).toHaveValue(versuch);

			// Der SERVERSEITIG persistierte (nicht editierte) Name bleibt der alte —
			// der fehlgeschlagene PUT hat nichts geschrieben.
			expect((await fetchPreset(page, presetId)).name).toBe(name);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});
});
