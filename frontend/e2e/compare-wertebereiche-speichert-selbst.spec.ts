// E2E — Issue #2276 Scheibe S3 (Epic #2345): der Reiter „Wertebereiche" im
// Ortsvergleich-Hub speichert über GENAU EINEN Weg (Speicher-Takt des
// Controllers) — ohne Wrapper `.hub-corridor-wrap` und ohne fensterweiten
// Loslassen-Handler. Nachweis am Wirkort.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md
//   AC-1 (ein PUT statt zwei), AC-2 (Loslassen außerhalb → trotzdem gespeichert,
//   über denselben einen Weg), AC-4 (Reiterwechsel Wertebereiche → Alarme),
//   AC-5 (412 → „Nochmal speichern"), AC-6 (Pausieren flusht vorher),
//   AC-11 (übrige Einstellungen bleiben)
//
// Warum E2E: die Frontend-Unit-Harness ist SSR-only (node --test +
// svelte/server), `$effect`/Ereignisse laufen dort nie. Die Verdrahtung —
// `maybeSchedule()`-Delegation in CorridorEditor(Mobile).svelte, neue Props am
// Mount in CompareTabs.svelte, generischer Flush-Guard in handleValueChange,
// Flush vor handleToggleActive, Wegfall des Wrapper-Wegs — ist nur im echten
// Browser messbar. Die Modul-Zusicherungen stehen in
// src/lib/components/shared/corridor-editor/__tests__/wertebereiche_*.test.ts.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// gespeicherten storageState aus global.setup.ts. Presets tragen das Präfix
// E2E-GZ-, damit global.teardown.ts Reste räumt; afterEach löscht sie direkt.
// Aufnahme in .github/ci_e2e_specs.txt macht die Implementierung.

import { test, expect, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufräumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}Wertebereiche speichert selbst ${Date.now()}`,
			// Seed-Orte aus global.setup.ts — mit Orten ist der Vergleich „aktiv",
			// der Kebab bietet dann „Pausieren" an.
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['wertebereiche-selbst@example.com'],
			radar_alert_enabled: false,
			send_telegram: true,
			send_sms: false,
			alert_cooldown_minutes: 45,
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

/** Zählt die PUTs auf genau diesen Vergleich (Request = abgeschickter Rumpf). */
function zaehlePuts(page: Page, id: string): { puts: Request[]; beantwortet: Request[] } {
	const pfad = `/api/compare/presets/${id}`;
	const puts: Request[] = [];
	const beantwortet: Request[] = [];
	const trifft = (r: Request) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad;
	page.on('request', (r) => {
		if (trifft(r)) puts.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) beantwortet.push(r);
	});
	return { puts, beantwortet };
}

async function oeffneWertebereiche(page: Page, id: string) {
	await page.goto(`/compare/${id}?tab=wertebereiche`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-wertebereiche"]:visible').click();
	const editor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
	await expect(editor).toBeVisible({ timeout: 10_000 });
	await expect(editor.locator('[data-testid="corridor-row-snow_depth_cm"]')).toBeVisible({ timeout: 10_000 });
	return editor;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const korridore = (body: Record<string, unknown>) => (body.corridors as Array<{ metric: string; range: unknown[] }>) ?? [];

test.describe('Issue #2276 S3: Reiter „Wertebereiche" im Vergleich speichert über genau einen Weg', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1 — fängt: Wrapper-Weg (onclick am .hub-corridor-wrap) wieder aktiv ⇒
	// jeder Klick speichert sofort einzeln ⇒ zwei PUTs statt einem.
	test('AC-1: zwei Metriken schnell hintereinander hinzufügen → genau EIN PUT mit beiden, danach „Gespeichert"', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);
		expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

		// beide Klicks innerhalb des Entprell-Fensters (700 ms)
		await editor.locator('.ce-pool-btn').first().click();
		await editor.locator('.ce-pool-btn').first().click();
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(3, { timeout: 5_000 });

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		// kurze Nachfrist: ein zweiter, verspäteter PUT (reaktiver Weg nach dem Wrapper-Weg) wäre jetzt sichtbar
		await page.waitForTimeout(1_200);

		expect(puts.length, 'genau EIN PUT für eine Bedienfolge im Entprell-Fenster').toBe(1);
		expect(korridore(puts[0].postDataJSON()).length, 'der eine PUT trägt beide neuen Metriken').toBe(3);
		expect(korridore(await serverStand(page, id)).length).toBe(3);
	});

	// AC-2 — fängt: schedule() im reaktiven Pfad entfernt (ohne Wrapper-Ersatz) ⇒
	// nach Loslassen außerhalb kommt kein PUT. Zusätzlich: nicht zwei Wege.
	test('AC-2: Regler ziehen, Maus über dem Tab-Kopf loslassen → gespeichert, genau EIN PUT, überlebt Neuladen', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);
		const row = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		const handle = await row.locator('.ce-handle').first().boundingBox();
		const kopf = await page.locator('[data-testid="compare-detail-tab-uebersicht"]').boundingBox();
		expect(handle).not.toBeNull();
		expect(kopf).not.toBeNull();

		await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2);
		await page.mouse.down();
		await page.mouse.move(handle!.x + 50, handle!.y - 20, { steps: 8 });
		await page.mouse.move(kopf!.x + kopf!.width / 2, kopf!.y + kopf!.height / 2, { steps: 15 });
		await page.mouse.up();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await page.waitForTimeout(1_200);
		expect(puts.length, 'Loslassen außerhalb darf keinen zweiten, eigenen Speicherweg auslösen').toBe(1);

		const minWert = await row.locator('input[type="number"]').first().inputValue();
		expect(minWert, 'Vorbedingung: der Regler hat sich bewegt').not.toBe('30');
		await page.reload();
		await page.waitForLoadState('networkidle');
		const neu = await oeffneWertebereiche(page, id);
		await expect(
			neu.locator('[data-testid="corridor-row-snow_depth_cm"] input[type="number"]').first()
		).toHaveValue(minWert, { timeout: 5_000 });
	});

	// AC-4 — fängt: generischer Flush-Guard ohne 'idealwerte' ⇒ der Alarm-Vorgang
	// verdrängt die Wertebereich-Änderung vom einen Platz des Controllers.
	test('AC-4: Wertebereich ändern, sofort zu „Alarme", dort Radar an → BEIDE Änderungen gespeichert', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);

		await editor.locator('.ce-pool-btn').first().click();
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
		// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
		await page.locator('[data-testid="compare-detail-tab-alarme"]:visible').click();
		await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
		expect(beantwortet.length, 'die Wertebereich-Änderung war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);

		const radar = page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
		await radar.click();
		await expect(radar).toBeChecked();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const [erster, zweiter] = puts.map((r) => r.postDataJSON());
		expect(korridore(erster).length, 'erster PUT = Wertebereich-Änderung').toBe(2);
		expect(zweiter.radar_alert_enabled).toBe(true);
		const stand = await serverStand(page, id);
		expect(korridore(stand).length, 'die Wertebereich-Änderung ging beim Reiterwechsel verloren').toBe(2);
		expect(stand.radar_alert_enabled).toBe(true);
	});

	// AC-5 — fängt: 412 als generischer Fehler (setError) bzw. Rollback auch bei 412.
	//
	// Issue #2375 (Test 12 / AC-1 / AC-13): der Seitenaufbau übernimmt den ETag
	// (+page.server.ts gibt `etag` zurück, +page.svelte ruft
	// adoptEtagFromPageLoad). Deshalb trägt schon die ERSTE Speicherung nach dem
	// Laden If-Match — der frühere Umweg „erst selbst speichern, um den ETag zu
	// bekommen" (CI-Befund PR #2374) entfällt. Und weil der Reiter nur noch seine
	// Eigenfelder sendet, überlebt die fremde Änderung (Name) das „Nochmal
	// speichern" — bis #2375 bewusst nicht zugesichert, jetzt Zusicherung.
	test('AC-5: fremde Änderung dazwischen → erster PUT 412 → „Nochmal speichern" → gespeichert, fremder Name bleibt', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);

		// GIVEN: Seite geladen, danach ändert ein anderes Gerät den Namen (ohne If-Match)
		const vorher = await serverStand(page, id);
		const fremderName = `${vorher.name} (fremd)`;
		const fremd = await page.request.put(`/api/compare/presets/${id}`, { data: { name: fremderName } });
		expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

		// WHEN: erste eigene Änderung auf dem jetzt veralteten Stand
		await editor.locator('.ce-pool-btn').first().click();
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });

		// THEN: echter 412 schon beim ERSTEN PUT → „Nochmal speichern", keine Rücknahme
		await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		expect(puts.length, 'Vorbedingung: der erste PUT wurde gesendet').toBe(1);
		expect(
			await puts[0].headerValue('if-match'),
			'der erste PUT nach dem Laden muss If-Match aus dem Seitenaufbau tragen (#2375 Punkt 2)'
		).toBeTruthy();
		expect((await puts[0].response())?.status(), 'der Server muss den veralteten Stand ablehnen').toBe(412);
		const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
		await expect(nochmal).toBeVisible();
		await expect(editor.locator('[data-testid^="corridor-row-"]'), 'bei 412 kein Zurückspringen').toHaveCount(2);

		// WHEN: „Nochmal speichern" → THEN: gespeichert, beide Änderungen auf dem Server
		await nochmal.click();
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2);
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		expect(puts.length, 'der Wiederholungs-PUT wurde gesendet').toBe(2);
		expect((await puts[1].response())?.status(), 'der Wiederholungs-PUT muss durchgehen').toBe(200);
		expect(Object.keys(puts[1].postDataJSON()).sort(), 'der Wiederholungs-PUT trägt nur Eigenfelder').toEqual([
			'corridors',
			'display_config'
		]);

		const stand = await serverStand(page, id);
		expect(korridore(stand).length, 'der Wiederholungs-PUT muss die Änderung tragen').toBe(2);
		expect(stand.name, '„Nochmal speichern" darf den fremd gespeicherten Namen nicht überschreiben (#2375)').toBe(
			fremderName
		);
	});

	// AC-6 — fängt: flush() vor handleToggleActive entfernt.
	test('AC-6: Pausieren direkt nach Wertebereich-Änderung → Wertebereich-PUT zuerst, beide Werte bleiben', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);

		await editor.locator('.ce-pool-btn').first().click();
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
		// sofort (innerhalb der Entprellung) über den Kopf-Kebab pausieren
		await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
		await page.getByRole('menuitem', { name: 'Pausieren' }).click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const [erster, zweiter] = puts.map((r) => r.postDataJSON());
		expect(korridore(erster).length, 'erster PUT muss die Wertebereich-Änderung sein').toBe(2);
		// #2375: der Wertebereiche-PUT trägt `schedule` gar nicht mehr (Teilfeld-Nutzlast)
		expect(Object.keys(erster), 'erster PUT darf noch nicht pausieren').not.toContain('schedule');
		expect(zweiter.schedule).toBe('manual');
		// Issue #2375 (AC-6/AC-9): der Pausieren-PUT trägt nur den Status — er
		// kann den Wertebereich weder mitschicken noch zurückschreiben.
		expect(Object.keys(zweiter).sort(), 'Pausieren-PUT trägt nur { schedule, previous_schedule }').toEqual([
			'previous_schedule',
			'schedule'
		]);

		const stand = await serverStand(page, id);
		expect(stand.schedule).toBe('manual');
		expect(korridore(stand).length).toBe(2);
		expect(puts.length).toBe(2);
	});

	// AC-11 — fängt: Teil-Nutzlast / fehlendes Bestandsfeld im Wertebereiche-PUT.
	test('AC-11: Korridor ändern → nach Neuladen sind alle übrigen Einstellungen unverändert', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		const { beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);

		await editor.locator('.ce-pool-btn').first().click();
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const nachher = await serverStand(page, id);
		const KORRIDOR_OBEN = new Set(['corridors', 'display_config', 'updated_at', 'etag']);
		for (const key of Object.keys(vorher)) {
			if (KORRIDOR_OBEN.has(key)) continue;
			expect(nachher[key], `Feld „${key}" hat sich durch das Wertebereiche-Speichern verändert`).toEqual(vorher[key]);
		}
		const vdc = (vorher.display_config as Record<string, unknown>) ?? {};
		const ndc = (nachher.display_config as Record<string, unknown>) ?? {};
		const KORRIDOR_DC = new Set(['ideal_ranges', 'active_metrics', 'metric_alert_levels']);
		for (const key of Object.keys(vdc)) {
			if (KORRIDOR_DC.has(key)) continue;
			expect(ndc[key], `display_config.${key} hat sich verändert`).toEqual(vdc[key]);
		}
		expect(korridore(nachher).length, 'nur der Wertebereich weicht ab').toBe(2);
	});

	// Issue #2375 Test 13 / AC-8 — fängt: Leerung erreicht den Server nicht, weil
	// die Teilfeld-Nutzlast `corridors: []` bzw. `ideal_ranges: {}` weglässt
	// (der Go-Merge ließe dann den alten Wert stehen).
	test('#2375 Roundtrip: Korridor-Leerung → PUT trägt corridors [] und ideal_ranges {} → nach Neuladen leer', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const editor = await oeffneWertebereiche(page, id);

		await editor.locator('[data-testid="corridor-row-snow_depth_cm"] .ce-remove').click();
		await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(0, { timeout: 5_000 });
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const rumpf = puts.at(-1)!.postDataJSON() as Record<string, unknown>;
		expect(rumpf.corridors, 'Leerung muss als [] gesendet werden').toEqual([]);
		expect(
			(rumpf.display_config as Record<string, unknown>).ideal_ranges,
			'geleerte Ideal-Ranges müssen als {} gesendet werden'
		).toEqual({});

		const stand = await serverStand(page, id);
		expect(korridore(stand).length, 'die Korridor-Leerung hat den Server nicht erreicht').toBe(0);
		expect(
			Object.keys(((stand.display_config as Record<string, unknown>).ideal_ranges as object) ?? {}),
			'die Ideal-Ranges wurden nicht geleert'
		).toEqual([]);

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-wertebereiche"]:visible').click();
		const neu = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(neu).toBeVisible({ timeout: 10_000 });
		await expect(neu.locator('[data-testid^="corridor-row-"]'), 'nach Neuladen muss die Leerung stehen').toHaveCount(0);
	});
});
