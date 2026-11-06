// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Wertebereiche"
// (geteilter CorridorEditor/CorridorEditorMobile auf Wertprops) verhält sich im
// Browser für BEIDE Hubs (Trip und Ortsvergleich) gleich — Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-4 (WW-1..WW-4)
//
// Issue #2792 S1c-3 (docs/specs/modules/feat_2792_s1_profil_ampel.md AC-22,
// AC-24, Nachtrag v1.3, PO-Entscheidung E2): die Korridor-Zeilen sind bis S3a
// NUR LESBAR — Desktop UND Mobil. Jeder Fall prüft jetzt dieselbe Geste wie
// vorher gegen das neue Soll: der Wertprop-Stand wird ANGEZEIGT (Vorbedingung
// je Fall), das Bedienelement ist gesperrt bzw. die Ziehgeste am Griff (ein
// div ohne `disabled`, nur der No-op-Wächter in `patch()` hält sie auf)
// verpufft, es geht KEIN PUT hinaus und der Serverstand bleibt unverändert,
// auch nach dem Neuladen.
//
// WW-4 war ein BEWUSSTER kind-Kontrast (Trip: Fehlerbanner + „nicht
// gespeichert", Vergleich: kein PUT — `maybeSchedule()` je context). Mit der
// Sperre ist eine beidseitig offene Grenze aus der Oberfläche nicht mehr
// herstellbar; beide kinds erhalten dieselbe Zusicherung (kein Banner, kein
// PUT, Serverstand bleibt). Die context-Weiche selbst ist damit in E2E nicht
// mehr erreichbar — bekannte Lücke bis S3a, im Bericht zu #2792 benannt.
//
// Stabilitätsfenster per expect.poll statt festem Schlaf (≥ alte Nachfristen
// 1,2 s / 2,5 s). Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh),
// Anmeldung über den storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-,
// Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
type Bereich = [number | null, number | null];

/** Wortlaut aus AC-22 (Katalogschlüssel `wertebereiche.gesperrt.hinweis_reiter`). */
const HINWEIS_DE = 'Wird gerade umgebaut – deine Werte sind übernommen.';

/** kind-Tabelle: eine Wertebereichs-Zeile je kind (Trip: ROUTE_METRIC_DEFS,
 *  Vergleich: Vergleichs-Katalog) und ein Pool-Eintrag für WW-3b. */
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

function zaehlePuts(page: Page, pfad: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
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

/** „Kein PUT": die PUT-Zahl bleibt über ein Fenster deutlich jenseits der 700-ms-Entprellung bei 0. */
async function keinPut(puts: Request[], message: string, ms = 1_200): Promise<void> {
	await bleibtStabil(() => puts.length, (n) => n === 0, ms, message);
	expect(puts.length, message).toBe(0);
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
	const hinweis = mobil ? 'corridor-editor-mobile-gesperrt' : 'corridor-editor-gesperrt';
	await expect(editor.locator(`[data-testid="${hinweis}"]`), 'AC-22: Sperr-Hinweis oben im Reiter').toHaveText(HINWEIS_DE);
	return editor;
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ww = WW_SEL[kind];

	test.describe(`Hub · Wertebereiche auf Wertprops, nur lesbar (${kind})`, () => {
		// WW-1 — fängt: das Prop-Bündel erreicht den Baustein nicht (Anzeige falsch)
		// bzw. das Zahlenfeld ist wieder bearbeitbar.
		test(`WW-1 (${kind}): Von-Grenze zeigt den gespeicherten Wert, ist gesperrt, Tippen → KEIN PUT, überlebt Neuladen`, async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

				const vonFeld = editor.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first();
				await expect(vonFeld, 'AC-22: der gespeicherte Wert wird angezeigt').toHaveValue('30');
				await expect(vonFeld, 'AC-22: das Zahlenfeld ist gesperrt').toBeDisabled();
				await vonFeld.click({ force: true });
				await page.keyboard.type('55');

				await keinPut(puts, 'WW-1: ein gesperrtes Zahlenfeld darf keinen PUT auslösen');
				await expect(vonFeld).toHaveValue('30');
				expect(bereichVon(await stand(page, kind, hub.id), ww.zeile)).toEqual([30, ww.bis]);

				const neu = await oeffne(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first()
				).toHaveValue('30', { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-2 — fängt: der Mobil-Baustein ohne No-op-Wächter (Griff-Drag schreibt)
		// bzw. Stepper wieder bedienbar.
		test(`WW-2 (${kind}): Mobil — Band-Drag am Von-Griff → Wert bleibt, Stepper gesperrt, KEIN PUT, überlebt Neuladen`, async ({ page }) => {
			await page.setViewportSize({ width: 390, height: 844 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id, true);

				const karte = editor.locator(`[data-testid="corridor-mobile-row-${ww.zeile}"]`);
				const vonWert = karte.locator('.cem-bound').first().locator('.cem-step-num');
				await expect(vonWert, 'AC-22: der gespeicherte Wert wird angezeigt').toHaveText('30');
				const stepper = karte.locator('.cem-step-btn');
				await expect(stepper.first(), 'Vorbedingung: Stepper vorhanden').toBeVisible();
				for (const knopf of await stepper.all()) await expect(knopf, 'AC-22: Stepper gesperrt').toBeDisabled();

				const band = karte.locator(`[data-testid="corridor-mobile-band-${ww.zeile}"]`);
				const griff = await band.locator('.cem-handle').first().boundingBox();
				const spur = await band.boundingBox();
				expect(griff, 'Vorbedingung: der Von-Griff ist sichtbar').not.toBeNull();
				expect(spur).not.toBeNull();

				await page.mouse.move(griff!.x + griff!.width / 2, griff!.y + griff!.height / 2);
				await page.mouse.down();
				await page.mouse.move(spur!.x + spur!.width * 0.4, griff!.y + griff!.height / 2, { steps: 10 });
				await page.mouse.up();

				await keinPut(puts, 'WW-2: die Ziehgeste am gesperrten Mobil-Regler darf keinen PUT auslösen');
				await expect(vonWert, 'WW-2: der Von-Wert darf sich nicht bewegt haben').toHaveText('30');
				expect(bereichVon(await stand(page, kind, hub.id), ww.zeile)).toEqual([30, ww.bis]);

				const neu = await oeffne(page, kind, hub.id, true);
				await expect(
					neu.locator(`[data-testid="corridor-mobile-row-${ww.zeile}"] .cem-bound`).first().locator('.cem-step-num')
				).toHaveText('30', { timeout: 10_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3a (Alt compare-hub-inline-edit AC-33) — Zahlenfeld im eingebetteten
		// Editor: gesperrt, kein PUT, kein Redirect in einen Alt-Editor.
		test(`WW-3a (${kind}): Zahlenfeld im eingebetteten Editor ist gesperrt — Verlassen löst KEINEN PUT aus (kein Redirect)`, async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, null]) });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				const minInput = editor.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first();
				await expect(minInput).toHaveValue('30');
				await expect(minInput, 'AC-22: das Zahlenfeld ist gesperrt').toBeDisabled();
				await minInput.click({ force: true });
				await page.keyboard.type('45');
				await minInput.blur();

				await keinPut(puts, 'WW-3a: das gesperrte Zahlenfeld darf beim Verlassen keinen PUT auslösen');
				await expect(minInput).toHaveValue('30');
				expect(bereichVon(await stand(page, kind, hub.id), ww.zeile)).toEqual([30, null]);
				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3b (Alt compare-hub-inline-edit AC-34) — „Metrik hinzufügen": sichtbar,
		// gesperrt, keine neue Zeile, kein PUT.
		test(`WW-3b (${kind}): „Metrik hinzufügen" im eingebetteten Editor ist gesperrt — keine neue Zeile, KEIN PUT`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, null]) });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				const poolBtn = editor.locator(`[data-testid="corridor-editor-pool-item-${ww.pool}"]`);
				await expect(poolBtn, `Vorbedingung: Pool zeigt ${ww.pool}`).toBeVisible({ timeout: 10_000 });
				await expect(poolBtn, 'AC-22: „Metrik hinzufügen" ist gesperrt').toBeDisabled();

				await poolBtn.click({ force: true });
				await keinPut(puts, 'WW-3b: der gesperrte Pool-Eintrag darf keinen PUT auslösen');
				await expect(editor.locator('[data-testid^="corridor-row-"]'), 'WW-3b: keine neue Zeile').toHaveCount(1);
				expect(
					((await stand(page, kind, hub.id)).corridors as Array<{ metric: string }>).map((c) => c.metric),
					'AC-24: Server-Korridore unverändert'
				).toEqual([ww.zeile]);
				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3c (Alt compare-hub-inline-edit F002) — Band-Handle-Drag mit Loslassen
		// AUSSERHALB des Editors: der No-op-Wächter hält die Geste auf, nichts geschrieben.
		test(`WW-3c (${kind}): Band-Handle-Drag mit Loslassen über dem Reiterkopf → Wert bleibt, KEIN PUT, überlebt Neuladen`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: ww.seed([30, ww.bis]) });
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				const row = editor.locator(`[data-testid="corridor-row-${ww.zeile}"]`);
				await expect(row.locator('input[type="number"]').first()).toHaveValue('30');
				const handleBox = await row.locator('.ce-handle').first().boundingBox();
				expect(handleBox, 'Band-Handle ohne BoundingBox').not.toBeNull();
				// Loslass-Ziel bewusst AUSSERHALB des Editors: der Reiterkopf oben.
				const headerBox = await page.locator(`[data-testid="${sel.reiter}-uebersicht"]:visible`).boundingBox();
				expect(headerBox, 'Reiterkopf ohne BoundingBox').not.toBeNull();

				await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2);
				await page.mouse.down();
				await page.mouse.move(handleBox!.x + 50, handleBox!.y - 20, { steps: 8 });
				await page.mouse.move(headerBox!.x + headerBox!.width / 2, headerBox!.y + headerBox!.height / 2, { steps: 15 });
				await page.mouse.up();

				await keinPut(puts, 'WW-3c: die Ziehgeste am gesperrten Regler darf keinen PUT auslösen');
				await expect(row.locator('input[type="number"]').first(), 'WW-3c: der Regler darf sich nicht bewegt haben').toHaveValue('30');
				expect(bereichVon(await stand(page, kind, hub.id), ww.zeile)).toEqual([30, ww.bis]);

				const neu = await oeffne(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ww.zeile}"] input[type="number"]`).first()
				).toHaveValue('30', { timeout: 5_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-4 — früherer kind-Kontrast (s. Kopf): das „×" auf der einzigen
		// gesetzten Grenze ist gesperrt; die Zeile wird NICHT beidseitig offen, kein
		// Fehlerbanner, kein PUT, der Indikator bleibt „Gespeichert", Serverstand bleibt.
		test(`WW-4 (${kind}): beidseitig offene Grenze herstellen versuchen → „×" gesperrt, kein Fehlerbanner, KEIN PUT, Serverstand unverändert`, async ({
			page
		}) => {
			await page.setViewportSize({ width: 1280, height: 900 });
			// Ausgangslage [null, bis]: „Von" ist offen, ein „×" auf „Bis" machte die Zeile beidseitig offen.
			const hub = await seedHub(page.request, kind, { extra: ww.seed([null, ww.bis]) });
			try {
				const vorher = bereichVon(await stand(page, kind, hub.id), ww.zeile);
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffne(page, kind, hub.id);
				const zeile = editor.locator(`[data-testid="corridor-row-${ww.zeile}"]`);
				await expect(zeile.locator('.ce-clear-btn')).toHaveCount(1);
				await expect(zeile.locator('.ce-clear-btn'), 'AC-22: „×" ist gesperrt').toBeDisabled();
				await zeile.locator('.ce-clear-btn').click({ force: true });

				await keinPut(puts, 'WW-4: der gesperrte Reiter darf keinen Zwischenstand senden', 2_500);
				await expect(editor.locator('[data-testid="corridor-editor-error"]'), 'WW-4: kein Fehlerbanner').toHaveCount(0);
				await expect(zeile.locator('input[type="number"]').first(), 'WW-4: die Bis-Grenze bleibt gesetzt').toHaveValue(
					String(ww.bis)
				);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle');
				expect(
					bereichVon(await stand(page, kind, hub.id), ww.zeile),
					'der zuletzt gespeicherte Serverstand muss unverändert sein'
				).toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
