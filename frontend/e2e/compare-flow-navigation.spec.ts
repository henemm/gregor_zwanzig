// gz-eigenstaendig: nur noch der Orte-Tab des Anlege-Ablaufs (Smart-Import nummeriert, Zähler „min. 2 erforderlich", Gruppen-Kopfzeilen der Bibliothek nach group_id); der Trip hat keine Orte, sondern Etappen mit GPX. Navigation und Kebab leben kind-parametrisiert in hub-list-menu/hub-kopf-aufbau/hub-tab-bar/hub-anlegen-ablauf (#2347 S4); Quelltext-Pendant step2_orte_library_grouping.test.ts.
//
// E2E (Staging) — Issue #1256 Scheibe 5: Editor-Tab „Orte" (AC-12, AC-13).
//
// #2347 S4 (docs/specs/modules/feat_2347_s4_paritaets_e2e.md): die übrigen Fälle
// dieser Datei sind an kind-parametrisierte Specs gewandert —
//   AC-25 Desktop/Mobil (Kachel öffnet Detail) → hub-list-menu LM-13 / LM-9,
//   AC-28 Breadcrumb / mobiler Zurück-Pfeil   → hub-kopf-aufbau KA-10 / KA-11,
//   AC-27 Abbrechen, AC-26/AC-29 voller Fluss → hub-anlegen-ablauf AN-8 / AN-6,
//   AC-5 Hub-Kebab (pausiert)                 → hub-list-menu LM-10,
//   KL-7 Archivieren im Hub-Kebab             → hub-list-menu LM-10b,
//   AC-30 „Bearbeiten →" wechselt inline      → hub-tab-bar HT-12,
//   Scheibe 4 AC-8 (Stundenverlauf im Editor) → hub-anlegen-ablauf AN-12,
//   ?tab=layout → ?tab=wetter-metriken        → hub-reiter-alt-kennungen-umleitung.
// Scheibe 4 AC-9 (keine Layout-Attrappe) und Fix-Loop F001 (Dirty-Indikator beim
// Öffnen) siehe Zuordnungstabelle der Spec.
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s2.staging.config.ts

import { test, expect, type Page } from '@playwright/test';

// ── Scheibe 5 (AC-12, AC-13): Editor-Tab "Orte" — Fidelity-Verifikation ────
//
// AC-12 (Regressionsanker, bereits heute grün): Smart-Import, min-2-
// Validierung und nummerierte Auswahlliste sind unverändert funktionsfähig.
// AC-13 (GREEN seit Phase 6): die Bibliothek gruppierte vor Phase 6 nach
// `loc.region` (Lawinenwarnregion, vom Smart-Import-Resolver nie befüllt)
// statt nach der App-eigenen Group-Entity (`group_id`/`GET /api/groups`,
// Issue #301) — s. step2_orte_library_grouping.test.ts für den
// Quelltext-Beleg. Der Test unten beweist die Behebung auf DOM-Ebene: ein
// Ort mit gesetzter group_id erscheint jetzt unter seiner Gruppen-Kopfzeile.
test.describe('Issue #1256 Scheibe 5: Editor-Tab "Orte" Fidelity (AC-12, AC-13)', () => {
	let createdGroupIds: string[] = [];

	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test.afterEach(async ({ page }) => {
		for (const id of createdGroupIds) {
			try {
				await page.request.delete(`/api/groups/${id}`);
			} catch {
				/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
			}
		}
		createdGroupIds = [];
	});

	async function openNewCompareOrteTab(page: Page, editorName: string): Promise<void> {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]:visible').fill(editorName);
		await page.locator('[data-testid="compare-editor-continue-orte"]:visible').click();
		await expect(page.locator('[data-testid="compare-wizard-step-2"]:visible')).toBeVisible({
			timeout: 10_000
		});
	}

	// ── AC-12: Smart-Import-Flow + Picked-Nummerierung sichtbar ─────────────
	test('AC-12: Smart-Import legt einen Ort an, der nummeriert (1) in der Picked-Liste erscheint', async ({
		page
	}) => {
		const suffix = Date.now();
		await openNewCompareOrteTab(page, `E2E S5 SmartImport ${suffix}`);

		const locName = `E2E S5 SmartImport-Ort ${suffix}`;
		await page.locator('[data-testid="compare-step2-smart-import-input"]:visible').fill('47.2692, 11.4041');
		await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();

		const nameInput = page.locator('[data-testid="compare-step2-name-input"]:visible');
		await expect(nameInput).toBeVisible({ timeout: 15_000 });
		await nameInput.fill(locName);
		await page.locator('button:has-text("Zum Vergleich hinzufügen"):visible').click();

		const pickedList = page.locator('[data-testid="compare-step2-picked-list"]:visible');
		const pickedItem = pickedList.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toHaveCount(1, { timeout: 10_000 });
		// Nummerierung "1" ist Teil des Picked-Items (Soll: screen-compare-editor.jsx:258).
		await expect(pickedItem.first()).toContainText('1');
		await expect(pickedItem.first()).toContainText(locName);

		const locId = await pickedItem
			.first()
			.getAttribute('data-testid')
			.then((tid) => tid?.replace('compare-step2-picked-item-', ''));
		if (locId) await page.request.delete(`/api/locations/${locId}`);
	});

	// ── AC-12: min-2-Validierungs-Copy bei genau 1 gewähltem Ort ─────────────
	test('AC-12: Counter zeigt "min. 2 erforderlich" solange nur 1 Ort gewählt ist', async ({ page }) => {
		const suffix = Date.now();
		await openNewCompareOrteTab(page, `E2E S5 MinTwo ${suffix}`);

		const locName = `E2E S5 MinTwo-Ort ${suffix}`;
		await page.locator('[data-testid="compare-step2-smart-import-input"]:visible').fill('47.1015, 11.2958');
		await page.locator('[data-testid="compare-step2-resolve-btn"]:visible').click();
		const nameInput = page.locator('[data-testid="compare-step2-name-input"]:visible');
		await expect(nameInput).toBeVisible({ timeout: 15_000 });
		await nameInput.fill(locName);
		await page.locator('button:has-text("Zum Vergleich hinzufügen"):visible').click();

		const pickedItem = page
			.locator('[data-testid="compare-step2-picked-list"]:visible')
			.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toHaveCount(1, { timeout: 10_000 });

		const counter = page.locator('[data-testid="compare-step2-counter"]:visible');
		await expect(counter).toHaveText('min. 2 erforderlich');

		const locId = await pickedItem
			.first()
			.getAttribute('data-testid')
			.then((tid) => tid?.replace('compare-step2-picked-item-', ''));
		if (locId) await page.request.delete(`/api/locations/${locId}`);
	});

	// ── AC-13 (GREEN seit Phase 6): Bibliothek gruppiert nach Group-Entity ──
	test('AC-13: Bibliothek zeigt einen gespeicherten Ort unter seiner Gruppen-Kopfzeile (group_id), NICHT unter "Weitere"', async ({
		page
	}) => {
		const suffix = Date.now();
		const groupName = `E2E S5 Gruppe ${suffix}`;

		const groupRes = await page.request.post('/api/groups', { data: { name: groupName } });
		expect(groupRes.ok(), 'Gruppen-Anlage fehlgeschlagen: ' + groupRes.status()).toBeTruthy();
		const group = await groupRes.json();
		createdGroupIds.push(group.id);

		const locName = `E2E S5 Gruppen-Ort ${suffix}`;
		const locRes = await page.request.post('/api/locations', {
			data: { name: locName, lat: 47.05, lon: 11.05, group_id: group.id }
		});
		expect(locRes.ok(), 'Location-Anlage fehlgeschlagen: ' + locRes.status()).toBeTruthy();
		const loc = await locRes.json();

		await openNewCompareOrteTab(page, `E2E S5 GruppenLib ${suffix}`);

		const libraryPanel = page.locator('[data-testid="compare-step2-library"]:visible');
		await expect(libraryPanel).toBeVisible({ timeout: 10_000 });

		// Gruppen-Kopfzeile "Gruppe · N" (Soll: screen-compare-editor.jsx:277)
		// mit dem ECHTEN Gruppennamen unseres Test-Orts — vor Phase 6 landete der
		// Ort stattdessen ungruppiert unter "Weitere" (loc.region wird nie gesetzt).
		await expect(libraryPanel.getByText(`${groupName} · 1`)).toBeVisible({ timeout: 10_000 });

		await page.request.delete(`/api/locations/${loc.id}`);
	});
});
