// E2E (Staging) — Issue #1261 (b): Compare-Editor Autospeichern (Ansatz A) +
// #1234-Gesten-Gate.
//
// Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md
//   § Acceptance Criteria AC-5..AC-11, AC-14
//
// Nachweis über abgefangene Netzwerk-Requests (page.on('request')), nicht
// über Optik. Echter Klick-Pfad (Tab-Klick statt goto), echte Nutzergesten
// (kein Mock). AC-7 ist der primäre Bug-Reproduktionsnachweis (Nullsumme
// ohne Geste), analog dem #1234-Muster in weather-metrics-tab-autosave.spec.ts.
//
// Ausführen (gegen Staging, aus frontend/):
//   npx playwright test e2e/compare-editor-autosave.spec.ts --config playwright.config.ts

import { test, expect, type Page, type Request, type Locator } from '@playwright/test';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdLocationIds.push(body.id);
	return body.id as string;
}

async function createPresetWithLocations(
	page: Page,
	name: string,
	locationIds: string[],
	overrides: Record<string, unknown> = {}
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdIds.push(body.id);
	return body.id as string;
}

/** Zeichnet jeden PUT-Request auf den Compare-Preset auf. */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

async function openEditor(page: Page, id: string): Promise<void> {
	// Epic #1273 S4c: Einstieg direkt am Hub (Editor = 307-Redirect seit S3);
	// die Tab-Leiste (compare-detail-tab-list) belegt, dass der Hub geladen ist.
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });
}

/** Entfernt einen Ort über den Hub-Orte-Tab (hub-orte-row[data-loc-id] +
 * hub-orte-remove statt Wizard-Testid compare-step2-picked-remove-{id}). */
function removeOrt(page: Page, locId: string): Locator {
	return page.locator(
		`[data-testid="hub-orte-row"][data-loc-id="${locId}"] [data-testid="hub-orte-remove"]`
	);
}

/**
 * Adversary F003: der Wertebereich-Slider-Griff (`.ce-handle`, geteilte
 * CorridorEditor.svelte) ist ein plain `<div onpointerdown>`, kein Button/
 * Input — echte Maus-Drag-Sequenz (nicht `.click()`) ist der einzige Weg,
 * genau diesen Bug-Pfad zu reproduzieren.
 */
async function dragCorridorHandle(page: Page, metric: string, deltaX: number): Promise<void> {
	const handle = page.locator(`[data-testid="corridor-row-${metric}"] .ce-handle`).first();
	await expect(handle).toBeVisible({ timeout: 10_000 });
	const box = await handle.boundingBox();
	if (!box) throw new Error(`Kein boundingBox für .ce-handle (${metric}) gefunden`);
	const startX = box.x + box.width / 2;
	const startY = box.y + box.height / 2;
	await page.mouse.move(startX, startY);
	await page.mouse.down();
	await page.mouse.move(startX + deltaX, startY, { steps: 8 });
	await page.mouse.up();
}

/**
 * Adversary F004: generischer Maus-Drag von einem Element-Mittelpunkt zu
 * einem anderen — Nachweis für svelte-dnd-action-basierte Reorder-UIs (Layout-
 * Tab-Bucket-Sektionen, geteilte BucketSection.svelte), die beim Drop nur
 * CustomEvents ("consider"/"finalize") feuern, KEIN pointerdown/change/input
 * auf einem vom Gesten-Gate-Selector erfassten Element. Mehrere Zwischen-
 * schritte + kurze Wartezeiten, weil svelte-dnd-action sonst nur einen Klick
 * statt eines Drags erkennt.
 */
async function dragElementCenterTo(page: Page, from: Locator, to: Locator): Promise<void> {
	const fromBox = await from.boundingBox();
	const toBox = await to.boundingBox();
	if (!fromBox || !toBox) throw new Error('boundingBox für Drag-Quelle/-Ziel fehlt');
	const fx = fromBox.x + fromBox.width / 2;
	const fy = fromBox.y + fromBox.height / 2;
	const tx = toBox.x + toBox.width / 2;
	const ty = toBox.y + toBox.height / 2;
	await page.mouse.move(fx, fy);
	await page.mouse.down();
	await page.mouse.move(fx, (fy + ty) / 2, { steps: 8 });
	await page.waitForTimeout(120);
	await page.mouse.move(tx, ty, { steps: 8 });
	await page.waitForTimeout(120);
	await page.mouse.up();
}

test.describe('Issue #1261 (b): Compare-Editor Autospeichern', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-5: echte Geste (Ort abwählen) speichert automatisch, kein Klick ───
	test('AC-5: Ort abwählen speichert automatisch (debounced PUT), kein Speichern-Klick', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC5 A ${suffix}`, 47.0, 11.0);
		const locB = await createLocation(page, `E2E 1261 AC5 B ${suffix}`, 47.1, 11.1);
		const id = await createPresetWithLocations(page, `E2E 1261 AC5 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-orte').click();

		const puts = collectPresetPuts(page, id);
		await removeOrt(page, locB).click();

		const put = await page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		expect(put.ok(), 'PUT fehlgeschlagen: ' + put.status()).toBeTruthy();

		expect(puts.map((p) => p.url())).toHaveLength(1);
		const body = puts[0].postDataJSON() as { location_ids?: string[] };
		expect(body.location_ids).toEqual([locA]);
	});

	// ── AC-6: zwei Aktionen → genau ZWEI PUTs, beide persistent ──────────────
	// Epic #1273 S4c: Hub feuert pro Aktion EINEN PUT (hubPutQueue, kein Merge).
	test('AC-6: zwei Aktionen (Ort + Versand-Zeit) lösen genau ZWEI PUTs aus, beide persistent', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC6 A ${suffix}`, 47.2, 11.2);
		const locB = await createLocation(page, `E2E 1261 AC6 B ${suffix}`, 47.3, 11.3);
		const id = await createPresetWithLocations(page, `E2E 1261 AC6 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		const puts = collectPresetPuts(page, id);

		// Aktion 1: Ort abwählen → ein PUT (Wartepromise VOR dem Klick registrieren).
		await page.getByTestId('compare-detail-tab-orte').click();
		const put1 = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		await removeOrt(page, locB).click();
		await put1;

		// Aktion 2: Morgen-Uhrzeit ändern → weiterer PUT. Volle Stunde (Input
		// step={3600}, VTSchedulePlan); Telegram-Toggle ist ohne chat_id ausgegraut.
		await page.getByTestId('compare-detail-tab-versand').click();
		const morningTime = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morningTime).toBeVisible({ timeout: 10_000 });
		const put2 = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		await morningTime.fill('05:00');
		await morningTime.blur();
		await put2;

		// Rest-Fenster abwarten, um ein etwaiges Doppel-Feuer pro Aktion zu fangen.
		await page.waitForTimeout(700);
		expect(
			puts.length,
			'genau ein PUT je Nutzeraktion (kein Doppel-Feuer über die hubPutQueue)'
		).toBe(2);

		// Endzustand: beide Änderungen sind serverseitig persistent.
		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.location_ids).toEqual([locA]);
		expect(String(preset.morning_time ?? '')).toContain('05:00');
	});

	// ── F001-Regression (Adversary CRITICAL): Re-Armierung während laufendem Autosave ──
	// Ursache des Bugs: der Auto-Save-`$effect` liest `dirty` (ein `$derived`-
	// Boolean). Ein Svelte-5-`$effect` läuft NICHT erneut, wenn der gelesene
	// `$derived`-Wert wertgleich bleibt — zwei Änderungen kurz hintereinander
	// liefern beide `dirty === true`. Ohne Re-Armierung (editTick-Fix in
	// CompareEditor.svelte) würde die zweite Änderung NIE einen neuen
	// `schedule()`-Aufruf auslösen und beim Wegnavigieren still verloren gehen
	// (`hasPending` bereits `false`, `beforeNavigate` flusht nichts).
	// Künstliche Netzwerk-Latenz auf den PUT erzwingt deterministisch das
	// "erster Save noch im Netz unterwegs, während zweite Geste passiert"-Fenster.
	test('F001-Regression: Änderung während laufendem Autosave re-armiert und geht nicht verloren', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 F001 A ${suffix}`, 48.9, 13.0);
		const locB = await createLocation(page, `E2E 1261 F001 B ${suffix}`, 48.91, 13.01);
		const locC = await createLocation(page, `E2E 1261 F001 C ${suffix}`, 48.92, 13.02);
		const id = await createPresetWithLocations(page, `E2E 1261 F001 ${suffix}`, [locA, locB, locC]);

		await page.route(`**/api/compare/presets/${id}`, async (route) => {
			if (route.request().method() === 'PUT') {
				await new Promise((r) => setTimeout(r, 900));
			}
			await route.continue();
		});

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-orte').click();

		// t≈0: erste Geste (Ort B abwählen) → nach 700ms Debounce feuert der
		// erste Save, haengt wegen der Route-Verzoegerung ~900ms im Netz.
		await removeOrt(page, locB).click();

		// t≈900ms: WÄHREND der erste PUT noch unterwegs ist, zweite Geste
		// (Ort C abwählen) — genau das vom Adversary beschriebene Fenster.
		await page.waitForTimeout(900);
		await removeOrt(page, locC).click();

		// Ausreichend Zeit für beide Debounce-Fenster + Route-Verzögerung.
		await page.waitForTimeout(4_000);

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(
			preset.location_ids,
			'F001: die zweite Änderung (Ort C abwählen) darf NICHT verloren gehen'
		).toEqual([locA]);
	});

	// ── AC-7: KERN-Bug-Reproduktion — keine Geste → NULL PUTs ────────────────
	test('AC-7: Editor öffnen ohne jede Geste, wegnavigieren → KEIN PUT (Gesten-Gate-Nachweis)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC7 ${suffix}`, 47.4, 11.4);
		const id = await createPresetWithLocations(page, `E2E 1261 AC7 ${suffix}`, [locA]);

		const puts = collectPresetPuts(page, id);
		await openEditor(page, id);
		await page.waitForLoadState('networkidle');

		// > 700ms Debounce-Fenster abwarten OHNE jede Interaktion — deckt auch
		// Hydrations-Effekte der geteilten Tabs ab (CorridorEditor-Dual-Write).
		await page.waitForTimeout(1_500);

		await page.goto(`/compare/${id}`);
		await page.waitForTimeout(500);

		expect(puts.map((p) => p.url()), 'kein PUT ohne echte Nutzergeste erwartet').toHaveLength(0);
	});

	// ── AC-8: Änderung + sofortige Navigation → kein Datenverlust ────────────
	// Epic #1273 S4c: Hub persistiert pro Aktion sofort → „beforeNavigate-Flush"
	// gegenstandslos; geprüft bleibt: kein Datenverlust (echte Race, s.u.).
	test('AC-8: Änderung + sofortige Navigation → Wert bleibt persistent (kein Datenverlust)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC8 A ${suffix}`, 47.5, 11.5);
		const locB = await createLocation(page, `E2E 1261 AC8 B ${suffix}`, 47.6, 11.6);
		const id = await createPresetWithLocations(page, `E2E 1261 AC8 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-orte').click();

		// Echte Race: Ort entfernen und SOFORT wegnavigieren, OHNE await auf den PUT
		// — schnitte die Navigation den Save ab, ginge die Änderung verloren. Danach
		// per API-GET-Polling beweisen, dass sie ankam (s. F001-Race-Test oben).
		await removeOrt(page, locB).click();
		await page.goto('/compare');

		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${id}`);
					return (await r.json()).location_ids as string[];
				},
				{
					message: 'AC-8: die Änderung darf trotz sofortiger Navigation nicht verloren gehen',
					timeout: 8_000
				}
			)
			.toEqual([locA]);
	});

	// ── AC-9: Statuspille durchläuft "wird gespeichert" → "gespeichert" ──────
	test('AC-9: SaveIndicator durchläuft "wird gespeichert" → "gespeichert" ohne Speichern-Klick', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC9 A ${suffix}`, 47.7, 11.7);
		const locB = await createLocation(page, `E2E 1261 AC9 B ${suffix}`, 47.8, 11.8);
		const id = await createPresetWithLocations(page, `E2E 1261 AC9 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-orte').click();
		await removeOrt(page, locB).click();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'saving', {
			timeout: 2_000
		});
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 5_000
		});
	});

	// ── AC-10: Autospeichern schließt ohne Fehler ab ────────────────────────
	// Epic #1273 S4c: Der Hub hat keinen manuellen Speichern-Button mehr; es
	// bleibt der Nachweis, dass die automatische Speicherung sauber (idle, kein
	// error) abschließt und persistiert.
	test('AC-10: Autospeichern schließt ohne Fehler ab und persistiert', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC10 A ${suffix}`, 47.9, 11.9);
		const locB = await createLocation(page, `E2E 1261 AC10 B ${suffix}`, 48.0, 12.0);
		const id = await createPresetWithLocations(page, `E2E 1261 AC10 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-orte').click();
		await removeOrt(page, locB).click();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 8_000
		});
		await expect(page.getByTestId('save-indicator')).not.toHaveAttribute('data-state', 'error');

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.location_ids).toEqual([locA]);
	});

	// Epic #1273 S4c: Die früheren AC-11 + F002 (Verwerfen-Button) wurden entfernt
	// — der Hub hat keinen Verwerfen-Button (Autosave-Modell), die Interaktion
	// existiert nicht mehr (Spec § „Einzelfallprüfung", analog versand-tab AC-8).

	// ── AC-14: Wertebereich-Tab löst unabhängig einen Auto-Save aus ─────────
	// (Orte-Tab bereits durch AC-5 belegt; Versand-Tab durch AC-6 und den
	// separaten Test unten.)
	test('AC-14 (Wertebereich): Warnen-Toggle im Wertebereich-Tab speichert automatisch', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC14w A ${suffix}`, 48.3, 12.3);
		// Der Hub-CorridorEditor (vergleich) kennt nur Compare-Metrik-Keys, nicht
		// Route-Keys — gust_max_kmh ist alarm-fähig + Range (Warnen + Slider).
		const id = await createPresetWithLocations(page, `E2E 1261 AC14w ${suffix}`, [locA], {
			corridors: [{ metric: 'gust_max_kmh', range: [null, 40], notify: true, mark: false }]
		});

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-idealwerte').click();
		await expect(page.getByTestId('corridor-editor-vergleich')).toBeVisible({ timeout: 10_000 });

		const notifyToggle = page.getByTestId('corridor-row-gust_max_kmh').getByRole('button', { name: 'Warnen' });
		await expect(notifyToggle).toHaveAttribute('aria-pressed', 'true');

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		await notifyToggle.click();
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Wertebereich) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		const corridor = (preset.corridors ?? []).find((c: { metric: string }) => c.metric === 'gust_max_kmh');
		expect(corridor?.notify).toBe(false);
	});

	// ── F003-Regression (Adversary CRITICAL): Slider-GRIFF ziehen (nicht Button-Klick) ──
	// Ursache: `.ce-handle` (Wertebereich-Slider-Griff in der geteilten
	// CorridorEditor.svelte) ist ein plain `<div onpointerdown>`, kein
	// Standard-Formularelement — der Gesten-Gate-Selector matchte ihn nicht,
	// `userTouched`/`editTick` blieben unverändert, Autosave feuerte nie. Der
	// Button-Test oben ("Warnen") deckt F003 NICHT ab, weil "Warnen" ein
	// echter `<button>` ist (bereits vom Selector erkannt) — nur der Drag am
	// Griff selbst reproduziert den Bug.
	test('F003-Regression (Wertebereich): Slider-Griff ZIEHEN speichert automatisch (kein Button-Klick)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 F003 A ${suffix}`, 48.36, 12.36);
		// Compare-Metrik-Key (s. AC-14): gust_max_kmh = Range-Metrik mit .ce-handle.
		const id = await createPresetWithLocations(page, `E2E 1261 F003 ${suffix}`, [locA], {
			corridors: [{ metric: 'gust_max_kmh', range: [null, 70], notify: true, mark: false }]
		});

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-idealwerte').click();
		await expect(page.getByTestId('corridor-editor-vergleich')).toBeVisible({ timeout: 10_000 });

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 8_000 }
		);
		await dragCorridorHandle(page, 'gust_max_kmh', -60);
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Wertebereich-Drag) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		const corridor = (preset.corridors ?? []).find((c: { metric: string }) => c.metric === 'gust_max_kmh');
		expect(
			corridor?.range?.[1],
			'F003: Drag-Änderung am Wertebereich-Griff muss automatisch gespeichert werden'
		).not.toBe(70);
	});

	// Epic #1273 S4c: Die F004-Regression (Layout-Tab Drag-Sortieren) wurde
	// entfernt — der Hub-Layout-Tab ist view-only (keine DnD; layout-editor/
	// bucket-section-* leben nur im Wizard). Diese Abdeckung liegt im Wizard-
	// migrierten sortable-list-shared.spec.ts. dragElementCenterTo bleibt Helper.

	// ── AC-14: Versand-Tab löst unabhängig einen Auto-Save aus (Zeitplan) ────
	test('AC-14 (Versand): Zeitplan-Änderung im Versand-Tab speichert automatisch', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC14v A ${suffix}`, 48.4, 12.4);
		const id = await createPresetWithLocations(page, `E2E 1261 AC14v ${suffix}`, [locA]);

		await openEditor(page, id);
		await page.getByTestId('compare-detail-tab-versand').click();

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		// Volle Stunde: report-morning-time-Input trägt step={3600} (VTSchedulePlan).
		const morningTime = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morningTime).toBeVisible({ timeout: 10_000 });
		await morningTime.fill('05:00');
		await morningTime.blur();
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Versand) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(String(preset.morning_time ?? '')).toContain('05:00');
	});
});
