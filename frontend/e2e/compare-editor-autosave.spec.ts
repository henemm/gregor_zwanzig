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
	await page.goto(`/compare/${id}/edit`);
	await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 10_000 });
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
		await page.getByTestId('compare-editor-tab-orte').click();

		const puts = collectPresetPuts(page, id);
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();

		const put = await page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		expect(put.ok(), 'PUT fehlgeschlagen: ' + put.status()).toBeTruthy();

		expect(puts.map((p) => p.url())).toHaveLength(1);
		const body = puts[0].postDataJSON() as { location_ids?: string[] };
		expect(body.location_ids).toEqual([locA]);
	});

	// ── AC-6: zwei Felder innerhalb des Debounce-Fensters → EIN konsolidierter PUT ──
	test('AC-6: zwei Änderungen (Ort + Kanal) innerhalb des Debounce-Fensters lösen genau EINEN PUT aus', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC6 A ${suffix}`, 47.2, 11.2);
		const locB = await createLocation(page, `E2E 1261 AC6 B ${suffix}`, 47.3, 11.3);
		const id = await createPresetWithLocations(page, `E2E 1261 AC6 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		const puts = collectPresetPuts(page, id);

		await page.getByTestId('compare-editor-tab-orte').click();
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();

		// Zweites Feld auf dem Versand-Tab: Morgen-Briefing-Uhrzeit. Bewusst NICHT
		// der Telegram-Kanal-Toggle — der ist ausgegraut, solange das Test-Konto
		// keine telegram_chat_id im Profil trägt (Staging-Realität, s. Memory
		// "Staging-Validator-Konto ohne Kontaktfelder"). sendEmail=true ist
		// wiz-Default (unabhängig vom Konto) → der Zeitplan-Bereich ist immer sichtbar.
		await page.getByTestId('compare-editor-tab-versand').click();
		const morningTime = page.getByTestId('report-morning-time');
		await expect(morningTime).toBeVisible({ timeout: 10_000 });
		await morningTime.fill('06:15');
		await morningTime.blur();

		// Beide Aktionen liegen weit innerhalb des 700ms-Debounce-Fensters
		// (Tab-Klick + Eingabe sind fuer Playwright im ms-Bereich) — genau EIN PUT.
		await page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		// Rest-Debounce-Fenster abwarten, falls doch zwei Timer gelaufen wären.
		await page.waitForTimeout(500);

		expect(puts.map((p) => p.url())).toHaveLength(1);
		const body = puts[0].postDataJSON() as { location_ids?: string[]; morning_time?: string };
		expect(body.location_ids).toEqual([locA]);
		expect(body.morning_time).toContain('06:15');
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
		await page.getByTestId('compare-editor-tab-orte').click();

		// t≈0: erste Geste (Ort B abwählen) → nach 700ms Debounce feuert der
		// erste Save, haengt wegen der Route-Verzoegerung ~900ms im Netz.
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();

		// t≈900ms: WÄHREND der erste PUT noch unterwegs ist, zweite Geste
		// (Ort C abwählen) — genau das vom Adversary beschriebene Fenster.
		await page.waitForTimeout(900);
		await page.getByTestId(`compare-step2-picked-remove-${locC}`).click();

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

	// ── AC-8: beforeNavigate-Flush — Änderung wird vor Verlassen gesichert ───
	test('AC-8: Änderung + sofortige Navigation → beforeNavigate-Flush speichert vor dem Verlassen', async ({
		page
	}) => {
		await page.setViewportSize({ width: 375, height: 667 }); // top-app-bar-back nur mobil sichtbar
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC8 A ${suffix}`, 47.5, 11.5);
		const locB = await createLocation(page, `E2E 1261 AC8 B ${suffix}`, 47.6, 11.6);
		const id = await createPresetWithLocations(page, `E2E 1261 AC8 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-orte').click();

		const putPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 10_000 }
		);
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();
		// Sofortige Navigation, deutlich VOR Ablauf des 700ms-Debounce-Fensters —
		// beforeNavigate muss den ausstehenden Save flushen, bevor die Navigation greift.
		await page.getByTestId('top-app-bar-back').click();

		const put = await putPromise;
		expect(put.ok(), 'PUT (Flush) fehlgeschlagen: ' + put.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.location_ids).toEqual([locA]);
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
		await page.getByTestId('compare-editor-tab-orte').click();
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'saving', {
			timeout: 2_000
		});
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 5_000
		});
	});

	// ── AC-10: manueller Speichern-Klick während laufendem Autosave ─────────
	test('AC-10: manueller Speichern-Klick während ausstehendem Autosave führt zu keinem Widerspruch', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC10 A ${suffix}`, 47.9, 11.9);
		const locB = await createLocation(page, `E2E 1261 AC10 B ${suffix}`, 48.0, 12.0);
		const id = await createPresetWithLocations(page, `E2E 1261 AC10 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-orte').click();
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();
		// Manueller Klick, während der Debounce-Timer noch läuft (idempotenter PUT).
		await page.getByTestId('compare-editor-save').click();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 8_000
		});
		await expect(page.getByTestId('save-indicator')).not.toHaveAttribute('data-state', 'error');

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.location_ids).toEqual([locA]);
	});

	// ── AC-11: "Verwerfen" nach abgeschlossenem Autosave rollt NICHT zurück ──
	test('AC-11: "Verwerfen" nach abgeschlossenem Autosave macht die Änderung NICHT rückgängig', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC11 A ${suffix}`, 48.1, 12.1);
		const locB = await createLocation(page, `E2E 1261 AC11 B ${suffix}`, 48.2, 12.2);
		const id = await createPresetWithLocations(page, `E2E 1261 AC11 ${suffix}`, [locA, locB]);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-orte').click();
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();

		// Debounce + Flush abwarten, bis der Indikator wieder idle ("gespeichert") zeigt.
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 8_000
		});

		await page.getByTestId('compare-editor-discard').click();
		const confirm = page.getByRole('button', { name: /Verwerfen|Bestätigen|Ja/ });
		await confirm.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		// Die bereits automatisch gespeicherte Änderung bleibt erhalten (kein Rollback).
		expect(preset.location_ids).toEqual([locA]);
	});

	// ── F002-Regression (Adversary CRITICAL): "Verwerfen" VOR Debounce-Ablauf ──
	// Ursache des Bugs: das ConfirmDialog-onConfirm rief `goto(...)`, was den
	// `beforeNavigate`-Wächter auslöste — der sah `hasPending === true` und
	// FLUSHTE (= speicherte) den noch nicht abgelaufenen Autosave, statt ihn zu
	// verwerfen. Fix: `compareSaveCtl.cancel()` VOR dem `goto(...)` bricht den
	// Timer ab, ohne `saveFn` aufzurufen — Nachweis hier: Geste sofort, ohne
	// jede Wartezeit auf den 700ms-Debounce, gefolgt von "Verwerfen" → NULL
	// PUT-Requests, Serverzustand exakt wie vor der Geste.
	test('F002-Regression: "Verwerfen" VOR Debounce-Ablauf speichert NICHTS', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 F002 A ${suffix}`, 49.0, 13.1);
		const locB = await createLocation(page, `E2E 1261 F002 B ${suffix}`, 49.01, 13.11);
		const id = await createPresetWithLocations(page, `E2E 1261 F002 ${suffix}`, [locA, locB]);

		const puts = collectPresetPuts(page, id);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-orte').click();

		// Sofort (weit VOR dem 700ms-Debounce-Fenster) abwählen und Verwerfen klicken.
		await page.getByTestId(`compare-step2-picked-remove-${locB}`).click();
		await page.getByTestId('compare-editor-discard').click();
		const confirm = page.getByRole('button', { name: /Verwerfen|Bestätigen|Ja/ });
		await confirm.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		// Über das ehemalige Debounce-Fenster hinaus abwarten — beweist, dass
		// wirklich NICHTS im Hintergrund nachgespeichert wurde (kein Wettlauf-Save).
		await page.waitForTimeout(1_500);

		expect(
			puts.map((p) => p.url()),
			'F002: cancel() muss den Timer vor der Navigation stoppen — kein PUT erwartet'
		).toHaveLength(0);

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.location_ids, 'F002: "Verwerfen" darf die Änderung NICHT persistieren').toEqual([
			locA,
			locB
		]);
	});

	// ── AC-14: Wertebereich-Tab löst unabhängig einen Auto-Save aus ─────────
	// (Orte-Tab bereits durch AC-5 belegt; Versand-Tab durch AC-6 und den
	// separaten Test unten.)
	test('AC-14 (Wertebereich): Warnen-Toggle im Wertebereich-Tab speichert automatisch', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC14w A ${suffix}`, 48.3, 12.3);
		const id = await createPresetWithLocations(page, `E2E 1261 AC14w ${suffix}`, [locA], {
			corridors: [{ metric: 'thunder_level', range: [null, 40], notify: true, mark: false }]
		});

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-idealwerte').click();
		await expect(page.getByTestId('corridor-editor-vergleich')).toBeVisible({ timeout: 10_000 });

		const notifyToggle = page.getByTestId('corridor-row-thunder_level').getByRole('button', { name: 'Warnen' });
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
		const corridor = (preset.corridors ?? []).find((c: { metric: string }) => c.metric === 'thunder_level');
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
		const id = await createPresetWithLocations(page, `E2E 1261 F003 ${suffix}`, [locA], {
			corridors: [{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }]
		});

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-idealwerte').click();
		await expect(page.getByTestId('corridor-editor-vergleich')).toBeVisible({ timeout: 10_000 });

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 8_000 }
		);
		await dragCorridorHandle(page, 'wind_gust', -60);
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Wertebereich-Drag) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		const corridor = (preset.corridors ?? []).find((c: { metric: string }) => c.metric === 'wind_gust');
		expect(
			corridor?.range?.[1],
			'F003: Drag-Änderung am Wertebereich-Griff muss automatisch gespeichert werden'
		).not.toBe(70);
	});

	// ── F004-Regression (Adversary CRITICAL): Layout-Tab Drag-Sortieren ─────
	// Ursache: BucketSection.svelte (geteilt) nutzt svelte-dnd-action OHNE
	// dragHandleSelector — die ganze Metrik-Zeile (Label/Meta sind plain
	// <div>/<span>) ist Drag-Griff. Der Drop feuert nur die CustomEvents
	// "consider"/"finalize", KEIN pointerdown/change/input auf einem vom
	// Gesten-Gate-Selector erfassten Element — ohne die explizite Meldung in
	// ltHandleDndReorder (CompareEditor.svelte) bliebe userTouched/editTick
	// unverändert, obwohl wiz.channelLayouts tatsächlich dirty wird.
	test('F004-Regression (Layout-Drag): Metrik-Zeile per Drag umsortieren speichert automatisch (kein Pfeil-Klick)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 F004 A ${suffix}`, 48.4, 12.4);
		const id = await createPresetWithLocations(page, `E2E 1261 F004 ${suffix}`, [locA]);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-layout').click();
		await expect(page.getByTestId('layout-editor')).toBeVisible({ timeout: 10_000 });

		// "email" ist der Default-Kanal (autoAssign befüllt "Spalten"/primary
		// beim ersten Layout-Tab-Besuch mit allen Katalog-Metriken, AC-2 #681).
		const primaryRows = page.locator(
			'[data-testid="bucket-section-primary"] [data-testid^="active-metric-row-"]'
		);
		await expect(primaryRows.first()).toBeVisible({ timeout: 10_000 });
		const rowCount = await primaryRows.count();
		expect(
			rowCount,
			'mind. 2 Metriken im "Spalten"-Bucket nötig, um per Drag umzusortieren'
		).toBeGreaterThanOrEqual(2);

		const beforeOrder = await primaryRows.evaluateAll((els) =>
			els.map((el) => el.getAttribute('data-testid'))
		);

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 8_000 }
		);
		// Drag am Label-Text der ERSTEN Zeile (NICHT am ▲/▼-Pfeil-Button!) auf
		// die Position einer späteren Zeile.
		const targetIdx = Math.min(2, rowCount - 1);
		await dragElementCenterTo(page, primaryRows.nth(0).locator('.label'), primaryRows.nth(targetIdx));
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Layout-Drag) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		const emailOrder = (preset.display_config?.channel_layouts?.email ?? [])
			.filter((m: { enabled: boolean; bucket?: string }) => m.enabled && (m.bucket ?? 'primary') === 'primary')
			.sort((a: { order?: number }, b: { order?: number }) => (a.order ?? 0) - (b.order ?? 0))
			.map((m: { metric_id: string }) => `active-metric-row-${m.metric_id}`);

		expect(
			emailOrder,
			'F004: Drag-Reihenfolge muss automatisch gespeichert werden (Server-Reihenfolge muss sich von der Ausgangsreihenfolge unterscheiden)'
		).not.toEqual(beforeOrder);
	});

	// ── AC-14: Versand-Tab löst unabhängig einen Auto-Save aus (Zeitplan) ────
	test('AC-14 (Versand): Zeitplan-Änderung im Versand-Tab speichert automatisch', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1261 AC14v A ${suffix}`, 48.4, 12.4);
		const id = await createPresetWithLocations(page, `E2E 1261 AC14v ${suffix}`, [locA]);

		await openEditor(page, id);
		await page.getByTestId('compare-editor-tab-versand').click();

		const put = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
			{ timeout: 5_000 }
		);
		const morningTime = page.getByTestId('report-morning-time');
		await expect(morningTime).toBeVisible({ timeout: 10_000 });
		await morningTime.fill('06:45');
		await morningTime.blur();
		const putRes = await put;
		expect(putRes.ok(), 'PUT (Versand) fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(String(preset.morning_time ?? '')).toContain('06:45');
	});
});
