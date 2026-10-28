// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Wertebereiche"
// (geteilter CorridorEditor/CorridorEditorMobile auf Wertprops) verhält sich im
// Browser für BEIDE Hubs (Trip und Ortsvergleich) gleich — Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-4 (WW-1..WW-4)
//
// Ersetzt compare-wertebereiche-wertprops.spec.ts (#2276 S6d) und den
// Wertebereich-Teil von compare-hub-inline-edit.spec.ts (Z. 173-324):
//   AC-4 Von-Grenze, Desktop          → WW-1 (je kind)
//   AC-5 Mobil-Band-Drag              → WW-2 (je kind)
//   inline-edit AC-33 / AC-34 / F002  → WW-3a / WW-3b / WW-3c (je kind)
//   AC-6 (Trip) / AC-7 (Vergleich)    → WW-4 (bewusster kind-Kontrast)
//
// WW-4 ist ein BEWUSSTER Kontrast und wird nicht zu einer gemeinsamen Schleife
// abgeschwächt (Spec AC-4): eine beidseitig offene Grenze zeigt im Trip das
// Fehlerbanner und hält den Indikator auf „nicht gespeichert" (Alt AC-6), im
// Ortsvergleich sendet sie bewusst KEINEN PUT (Alt AC-7, F001/F005 aus #2276 S3).
// Nebeneinander in derselben Datei ist der Unterschied sichtbar.
//
// Eigen-Seed statt `.first()` auf Pool-Einträge; Stabilitätsfenster per
// expect.poll statt festem Schlaf (≥ alte Nachfristen 1,2 s / 1,5 s / 2,5 s).
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
type Bereich = [number | null, number | null];

/** kind-Tabelle: eine Wertebereichs-Zeile je kind (Trip: ROUTE_METRIC_DEFS,
 *  Vergleich: Vergleichs-Katalog) und ein gültiger Pool-Eintrag für WW-3b. */
const WW_SEL: Record<
	HubKind,
	{
		zeile: string;
		bis: number;
		pool: string;
		/** vollständiger Seed-Rumpf für eine Zeile mit `bereich` (display_config wird ersetzt). */
		seed: (bereich: Bereich) => Record<string, unknown>;
	}
> = {
	route: {
		zeile: 'wind_gust',
		bis: 70,
		pool: 'precipitation_sum',
		seed: (bereich) => ({ corridors: [{ metric: 'wind_gust', range: bereich, notify: false, mark: false }] })
	},
	vergleich: {
		zeile: 'snow_depth_cm',
		bis: 200,
		pool: 'wind_max_kmh',
		seed: (bereich) => ({
			corridors: [{ metric: 'snow_depth_cm', range: bereich, notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: bereich[0] ?? undefined, max: bereich[1] ?? undefined } },
				active_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		})
	}
};

function zaehlePuts(page: Page, pfad: string): { puts: Request[]; beantwortet: Request[] } {
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

/** Stabilitätsfenster: `lies()` muss `ms` lang `ok` erfüllen (statt festem Schlaf). */
async function bleibtStabil<T>(
	lies: () => T | Promise<T>,
	ok: (v: T) => boolean,
	ms: number,
	message: string
): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			async () => {
				const v = await lies();
				if (!ok(v)) {
					seit = 0;
					return `verletzt: ${String(v)}`;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : 'wartet';
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

function bereichVon(body: Stand, metric: string): Bereich | null {
	const k = (body.corridors ?? []) as Array<{ metric: string; range: Bereich }>;
	return k.find((c) => c.metric === metric)?.range ?? null;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');

async function oeffne(page: Page, kind: HubKind, id: string, mobil = false): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wertebereiche' });
	const testid = mobil ? `corridor-editor-mobile-${kind}` : `corridor-editor-${kind}`;
	const editor = page.locator(`[data-testid="${testid}"]:visible`);
	await expect(editor).toBeVisible({ timeout: 10_000 });
	const zeile = mobil ? `corridor-mobile-row-${WW_SEL[kind].zeile}` : `corridor-row-${WW_SEL[kind].zeile}`;
	await expect(editor.locator(`[data-testid="${zeile}"]`)).toBeVisible({ timeout: 10_000 });
	return editor;
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ww = WW_SEL[kind];

	test.describe(`Hub · Wertebereiche auf Wertprops (${kind})`, () => {
		// WW-1 (Alt AC-4) — fängt: das Prop-Bündel erreicht den Baustein nicht
		// (Geste verpufft) oder der Speicherweg feuert doppelt.
		test(`WW-1 (${kind}): Von-Grenze ändern → genau EIN PUT, überlebt Neuladen`, async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

				const vonFeld = editor.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first();
				await expect(vonFeld).toHaveValue('30');
				await vonFeld.fill('55');

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtStabil(() => puts.length, (n) => n === 1, 1_200, 'genau EIN PUT für eine Bedienfolge im Entprell-Fenster');

				expect(bereichVon(await stand(page, kind, hub.id), ww.zeile)).toEqual([55, ww.bis]);

				const neu = await oeffne(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first()
				).toHaveValue('55', { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-2 (Alt AC-5) — fängt: der Dual-Handle-Drag im Mobil-Baustein läuft ins
		// Leere, weil der Wert nicht zurückgemeldet wird.
		test(`WW-2 (${kind}): Mobil — Band-Drag am Von-Griff → gespeichert, genau EIN PUT, überlebt Neuladen`, async ({ page }) => {
			await page.setViewportSize({ width: 390, height: 844 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id, true);

				const karte = editor.locator(`[data-testid="corridor-mobile-row-${ww.zeile}"]`);
				const vonWert = karte.locator('.cem-bound').first().locator('.cem-step-num');
				await expect(vonWert).toHaveText('30');

				const band = karte.locator(`[data-testid="corridor-mobile-band-${ww.zeile}"]`);
				const griff = await band.locator('.cem-handle').first().boundingBox();
				const spur = await band.boundingBox();
				expect(griff, 'Vorbedingung: der Von-Griff ist sichtbar').not.toBeNull();
				expect(spur).not.toBeNull();

				await page.mouse.move(griff!.x + griff!.width / 2, griff!.y + griff!.height / 2);
				await page.mouse.down();
				await page.mouse.move(spur!.x + spur!.width * 0.4, griff!.y + griff!.height / 2, { steps: 10 });
				await page.mouse.up();

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtStabil(() => puts.length, (n) => n === 1, 1_200, 'genau EIN PUT für eine Ziehbewegung');

				const bereich = bereichVon(await stand(page, kind, hub.id), ww.zeile);
				expect(bereich, 'der Von-Wert muss sich durch den Drag verändert haben').not.toEqual([30, ww.bis]);
				expect(bereich![1], 'der Bis-Wert darf sich NICHT mitbewegt haben').toBe(ww.bis);
				const angezeigt = await vonWert.textContent();

				const neu = await oeffne(page, kind, hub.id, true);
				await expect(
					neu.locator(`[data-testid="corridor-mobile-row-${ww.zeile}"] .cem-bound`).first().locator('.cem-step-num')
				).toHaveText(angezeigt!.trim(), { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3a (Alt compare-hub-inline-edit AC-33) — Zahlenfeld-Bearbeitung im
		// eingebetteten Editor löst einen PUT aus, kein Redirect.
		test(`WW-3a (${kind}): Zahlenfeld-Bearbeitung im eingebetteten Editor löst PUT aus (kein Redirect)`, async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, null]) });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const editor = await oeffne(page, kind, hub.id);
				const minInput = editor.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first();
				await minInput.fill('45');

				const putPromise = page.waitForResponse(
					(res) => new URL(res.url()).pathname === pfad && res.request().method() === 'PUT'
				);
				await minInput.blur();
				const putRes = await putPromise;
				expect(putRes.ok(), 'PUT nach Idealwert-Bearbeitung fehlgeschlagen: ' + putRes.status()).toBeTruthy();
				const putBody = putRes.request().postDataJSON() as Stand;
				expect(bereichVon(putBody, ww.zeile)?.[0]).toBe(45);

				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3b (Alt compare-hub-inline-edit AC-34) — „Metrik hinzufügen" legt eine
		// neue Zeile an und persistiert per PUT (Eigen-Seed statt `.first()`).
		test(`WW-3b (${kind}): „Metrik hinzufügen" im eingebetteten Editor legt eine neue Zeile an und persistiert per PUT`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, null]) });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const editor = await oeffne(page, kind, hub.id);
				const poolBtn = editor.locator(`[data-testid="corridor-editor-pool-item-${ww.pool}"]`);
				await expect(poolBtn, `Vorbedingung: Pool bietet ${ww.pool} an`).toBeVisible({ timeout: 10_000 });

				const putPromise = page.waitForResponse(
					(res) => new URL(res.url()).pathname === pfad && res.request().method() === 'PUT'
				);
				await poolBtn.click();
				const putRes = await putPromise;
				expect(putRes.ok(), 'PUT nach Metrik-Hinzufügen fehlgeschlagen: ' + putRes.status()).toBeTruthy();
				const putBody = putRes.request().postDataJSON() as { corridors: Array<{ metric: string }> };
				expect(putBody.corridors.length).toBeGreaterThan(1);
				expect(putBody.corridors.map((c) => c.metric), 'der PUT trägt die gewählte Metrik').toContain(ww.pool);

				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3c (Alt compare-hub-inline-edit F002, Adversary HIGH): Band-Handle-Drag
		// mit Loslassen AUSSERHALB des Editors darf keinen stillen Datenverlust erzeugen.
		test(`WW-3c (${kind}): Band-Handle-Drag mit Loslassen über dem Reiterkopf persistiert trotzdem, überlebt Neuladen`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const editor = await oeffne(page, kind, hub.id);
				const row = editor.locator(`[data-testid="corridor-row-${ww.zeile}"]`);
				const handleBox = await row.locator('.ce-handle').first().boundingBox();
				expect(handleBox, 'Band-Handle ohne BoundingBox').not.toBeNull();
				// Loslass-Ziel bewusst AUSSERHALB des Editors: der Reiterkopf oben.
				const headerBox = await page.locator(`[data-testid="${sel.reiter}-uebersicht"]:visible`).boundingBox();
				expect(headerBox, 'Reiterkopf ohne BoundingBox').not.toBeNull();

				const putPromise = page.waitForResponse(
					(res) => new URL(res.url()).pathname === pfad && res.request().method() === 'PUT'
				);
				await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2);
				await page.mouse.down();
				await page.mouse.move(handleBox!.x + 50, handleBox!.y - 20, { steps: 8 });
				await page.mouse.move(headerBox!.x + headerBox!.width / 2, headerBox!.y + headerBox!.height / 2, { steps: 15 });
				await page.mouse.up();

				const putRes = await putPromise;
				expect(
					putRes.ok(),
					'PUT nach Band-Handle-Drag mit Loslassen außerhalb des Editors fehlgeschlagen (F002-Regression): ' + putRes.status()
				).toBeTruthy();

				const draggedValue = await row.locator('input[type="number"]').first().inputValue();
				expect(draggedValue, 'Vorbedingung: der Regler hat sich bewegt').not.toBe('30');

				const neu = await oeffne(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first()
				).toHaveValue(draggedValue, { timeout: 5_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-4 — BEWUSSTER kind-Kontrast (Spec AC-4, Alt AC-6/AC-7), nicht wegschleifen:
		// der geteilte Baustein entscheidet in `maybeSchedule()` je context
		// (CorridorEditor.svelte:303-329). Trip: ungültiger Stand ⇒ setUnsavedInput,
		// Fehlerbanner + Indikator „dirty". Vergleich: ungültiger Zwischenstand wird
		// bewusst NICHT gesendet (kein PUT), Serverstand bleibt.
		test(`WW-4 (${kind}): beidseitig offene Grenze → ${kind === 'route' ? 'Fehlerbanner UND nicht „Gespeichert"' : 'kein PUT, Serverstand unverändert'}`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			// Ausgangslage [null, bis]: „Von" ist offen, ein „×" auf „Bis" macht die Zeile beidseitig offen.
			const hub = await seedHub(page.request, kind, { extra: ww.seed([null, ww.bis]) });
			try {
				const vorher = bereichVon(await stand(page, kind, hub.id), ww.zeile);
				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				const zeile = editor.locator(`[data-testid="corridor-row-${ww.zeile}"]`);
				await expect(zeile.locator('.ce-clear-btn')).toHaveCount(1);
				await zeile.locator('.ce-clear-btn').click();

				await expect(editor.locator('[data-testid="corridor-editor-error"]')).toBeVisible({ timeout: 10_000 });
				if (kind === 'route') {
					// Trip-Zweig (Alt AC-6): Indikator „dirty" und springt NICHT auf „Gespeichert",
					// solange der Fehler steht (Fenster ≥ alte 1,5-s-Nachfrist).
					await expect(anzeige(page)).toHaveAttribute('data-state', 'dirty', { timeout: 10_000 });
					await bleibtStabil(
						() => anzeige(page).getAttribute('data-state'),
						(s) => s !== 'idle',
						1_500,
						'der Indikator darf bei stehendem Fehler nicht auf „Gespeichert" springen'
					);
					await expect(editor.locator('[data-testid="corridor-editor-error"]')).toBeVisible();
				} else {
					// Vergleichs-Zweig (Alt AC-7): deutlich über dem 700-ms-Entprell-Fenster
					// darf kein PUT kommen (Fenster ≥ alte 2,5-s-Nachfrist).
					await bleibtStabil(
						() => puts.length,
						(n) => n === 0,
						2_500,
						'der Vergleich darf keinen ungültigen Zwischenstand senden'
					);
					expect(puts.length, 'der Vergleich darf keinen ungültigen Zwischenstand senden').toBe(0);
					expect(
						bereichVon(await stand(page, kind, hub.id), ww.zeile),
						'der zuletzt gespeicherte Serverstand muss unverändert sein'
					).toEqual(vorher);
				}
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
