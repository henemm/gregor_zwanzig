// gz-eigenstaendig: Block „Kanäle je Wettergröße" (alerts-tab/AlertMetricChannelsBlock.svelte) im Alarme-Reiter aller vier Flächen (Trip-Hub, Ortsvergleich-Hub, /trips/new, /compare/new) — kein Trip-/Compare-Pendant, der Baustein ist EINER und geteilt
// E2E (Staging) — Issue #1895 S3b1: Kanäle je Wettergröße.
//
// Spec: docs/specs/modules/alert_metric_channels.md
//   AC-62 (Ablauf Umschalten → Kanal wählen → Speichern → Neuladen → zurück auf
//          „wie Abo-Kanäle" in .tn-mobile UND .tn-desktop, Schalter nicht verdeckt),
//   AC-52 (Hinweis „Radar-/Regen-Alarme und amtliche Warnungen immer über die Abo-Kanäle"),
//   AC-55 (Ortsvergleich-Editor + /compare/new), AC-58 (alle vier Flächen, ein Baustein),
//   AC-54 (Trip-Hub + /trips/new).
//
// Gemessen wird am GESPEICHERTEN Stand (GET /api/trips/{id} bzw.
// /api/compare/presets/{id}, Top-Level-Feld `alert_metric_channels`), nicht nur an
// der Oberfläche — die zeigt die Wahl auch dann, wenn sie nie gesendet wurde.
//
// Kontrast (AC-62 „WCAG-AA"): im Repo nutzt KEINE E2E-Spec @axe-core/playwright
// o. ä.; deshalb wird der Kontrast hier NICHT automatisch geprüft (nichts
// erfunden). Der Block verwendet die Design-Tokens --g-ink / --g-ink-muted der
// bestehenden WCAG-geprüften Oberfläche (docs/reference/design_system.md).
//
// Sprache: Cookie gz_lang (Standard de; GZ_LANG=en für die EN-Variante). Ist am
// Konto eine Profil-Sprache gesetzt, überschreibt diese das Cookie
// (resolveLang.ts) — dann passt der Hinweistext-Check ggf. nicht.
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   (GZ_AUTH_USER/GZ_AUTH_PASS = Staging-.env /home/hem/gregor_zwanzig_staging/.env)
//   npx playwright test --config=e2e/playwright.kanal-je-wettergroesse-block.staging.config.ts

import { test, expect, type Locator, type Page } from '@playwright/test';
import {
	ANLEGE_SEL,
	anlegenPflicht,
	cleanupTracked,
	createTestLocation,
	hubApiPath,
	openHub,
	registerForCleanup,
	type HubKind
} from './helpers';

const LANG = (process.env.GZ_LANG ?? 'de') === 'en' ? 'en' : 'de';
const HINWEIS = LANG === 'en' ? /always use the alert channels/i : /immer über die Alert-Kanäle/i;
const WIE_ABO = LANG === 'en' ? /same as alert channels/i : /wie Alert-Kanäle/i;

const MOBIL = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };
// Zusätzliche Grenzfälle der Weiche bei 899 px (≤899 mobil, ≥900 Desktop).
const GRENZE_MOBIL = { width: 899, height: 844 };
const GRENZE_DESKTOP = { width: 900, height: 900 };

type Stand = Record<string, unknown>;

test.beforeEach(async ({ context, baseURL }) => {
	await context.addCookies([{ name: 'gz_lang', value: LANG, url: baseURL ?? 'https://staging.gregor20.henemm.com' }]);
});
test.afterAll(async ({ request }) => await cleanupTracked(request));

// ── Test-Objekte (eigene, mit Präfix E2E-GZ-, Aufräumen über cleanupTracked) ──

async function seedTrip(page: Page): Promise<string> {
	const id = `e2e-gz-1895-kanalblock-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
	const metricIds = ['temperature', 'wind', 'gust', 'precipitation', 'thunder'];
	const res = await page.request.post('/api/trips', {
		data: {
			id,
			name: `E2E-GZ-1895-Kanalblock-Trip-${Date.now()}`,
			alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: false,
				morning_time: '06:00:00',
				evening_time: '18:00:00'
			},
			display_config: {
				metrics: metricIds.map((metric_id, order) => ({ metric_id, enabled: true, bucket: 'primary', order })),
				metric_alert_levels: { wind_gust: 'standard', thunder: 'standard' }
			},
			// Etappe MIT Datum: Seed-Etappen ohne Vorhersage-Datum können leer rendern.
			stages: [
				{
					id: `${id}-s1`,
					name: 'Etappe 1',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-a`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${id}-b`, name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
	expect(res.ok(), `Trip-Anlage HTTP ${res.status()}`).toBeTruthy();
	registerForCleanup('trip', id);
	return id;
}

async function seedVergleich(page: Page): Promise<string> {
	const s = Date.now();
	// ≥ 3 Orte, wie in den bestehenden Setups.
	const orte = [
		await createTestLocation(page.request, { name: `1895-kb-A-${s}`, lat: 47.1, lon: 11.2 }),
		await createTestLocation(page.request, { name: `1895-kb-B-${s}`, lat: 47.2, lon: 11.3 }),
		await createTestLocation(page.request, { name: `1895-kb-C-${s}`, lat: 47.3, lon: 11.4 })
	];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `E2E-GZ-1895-Kanalblock-Vergleich-${s}`,
			location_ids: orte.map((o) => o.id),
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 18,
			empfaenger: ['urlauber@example.com'],
			morning_enabled: true,
			morning_time: '06:00:00',
			evening_enabled: false,
			evening_time: '18:00:00',
			display_config: { active_metrics: ['wind_max_kmh'] }
		}
	});
	expect(res.ok(), `Vergleich-Anlage HTTP ${res.status()}`).toBeTruthy();
	const { id } = (await res.json()) as { id: string };
	registerForCleanup('preset', id);
	return id;
}

// ── Messhilfen ───────────────────────────────────────────────────────────────

async function gespeichert(page: Page, kind: HubKind, id: string, key: string): Promise<Record<string, unknown> | null | undefined> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	const map = ((await res.json()) as Stand).alert_metric_channels as Record<string, Record<string, unknown> | null> | null | undefined;
	return map?.[key];
}

/** Sichtbar, nicht 0-groß, innerhalb des Viewports, nicht von einem anderen Element verdeckt. */
async function pruefeBedienbar(page: Page, loc: Locator, was: string): Promise<void> {
	await loc.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'nearest' }));
	await expect(loc, `${was}: nicht sichtbar`).toBeVisible();
	const bb = await loc.boundingBox();
	const vp = page.viewportSize()!;
	expect(bb, `${was}: keine Bounding-Box`).not.toBeNull();
	expect(bb!.width, `${was}: Breite 0`).toBeGreaterThan(0);
	expect(bb!.height, `${was}: Höhe 0`).toBeGreaterThan(0);
	expect(bb!.x, `${was}: links abgeschnitten`).toBeGreaterThanOrEqual(-1);
	expect(bb!.x + bb!.width, `${was}: rechts abgeschnitten (Viewport ${vp.width})`).toBeLessThanOrEqual(vp.width + 1);
	const frei = await loc.evaluate((el) => {
		const r = el.getBoundingClientRect();
		const t = document.elementFromPoint(r.x + Math.min(r.width / 2, 20), r.y + r.height / 2);
		return !!t && el.contains(t);
	});
	expect(frei, `${was}: von einem anderen Element verdeckt`).toBe(true);
}

const eigeneWahl = (zeile: Locator, key: string) => zeile.getByTestId(`kanal-eigene-${key}`);
const telegram = (zeile: Locator, key: string) => zeile.getByTestId(`kanal-schalter-${key}-telegram`);

/**
 * Block-Prüfung gemeinsam für alle Flächen: Überschrift/Hinweis (AC-52),
 * mindestens eine Zeile, Zeile steht auf „wie Abo-Kanäle", Schalter bedienbar.
 * Liefert den Speicherschlüssel der ersten Zeile.
 */
async function blockPruefen(page: Page, block: Locator): Promise<{ key: string; zeile: Locator }> {
	await expect(block, 'Block „Kanäle je Wettergröße" fehlt').toBeVisible({ timeout: 25_000 });
	await expect(block.getByTestId('kanal-hinweis-metrikfrei'), 'AC-52: Hinweis auf Abo-Kanäle fehlt').toHaveText(HINWEIS);
	const zeile = block.locator('[data-testid^="kanal-zeile-"]').first();
	await expect(zeile, 'Block ohne Zeile (Alarm-Zeilen oder Schlüssel-Endpunkt fehlen)').toBeVisible({ timeout: 15_000 });
	const key = ((await zeile.getAttribute('data-testid')) ?? '').replace('kanal-zeile-', '');
	expect(key).not.toBe('');
	await pruefeBedienbar(page, eigeneWahl(zeile, key).locator('label'), 'Umschalter „eigene Wahl"');
	return { key, zeile };
}

/** „eigene Wahl" an, Telegram an (falls nicht schon durch den Abo-Satz an). */
async function eigeneWahlMitTelegram(page: Page, zeile: Locator, key: string): Promise<void> {
	await expect(zeile.getByTestId(`kanal-erbt-${key}`), 'Ausgangslage: Zeile steht nicht auf „wie Abo-Kanäle"').toHaveText(WIE_ABO);
	await eigeneWahl(zeile, key).locator('label').click();
	const tg = telegram(zeile, key);
	await expect(tg, 'nach „eigene Wahl" fehlen die Kanal-Schalter').toBeVisible({ timeout: 10_000 });
	await pruefeBedienbar(page, tg.locator('label'), 'Kanal-Schalter Telegram');
	if (!(await tg.locator('input[type="checkbox"]').isChecked())) await tg.locator('label').click();
	await expect(tg.locator('input[type="checkbox"]')).toBeChecked();
}

// ── Hubs: voller Roundtrip (AC-62, AC-54, AC-55, AC-58) ─────────────────────

const LAYOUTS = [
	{ name: 'mobil 390 (.tn-mobile-Breite)', vp: MOBIL },
	{ name: 'Desktop 1280 (.tn-desktop-Breite)', vp: DESKTOP },
	{ name: 'Grenze 899', vp: GRENZE_MOBIL },
	{ name: 'Grenze 900', vp: GRENZE_DESKTOP }
];

for (const kind of ['route', 'vergleich'] as const) {
	const flaeche = kind === 'route' ? 'Trip-Hub' : 'Ortsvergleich-Editor';
	for (const layout of LAYOUTS) {
		test(`AC-62/${kind === 'route' ? 'AC-54' : 'AC-55'}: ${flaeche}, ${layout.name} — eigene Wahl → Speichern → Neuladen → zurück auf „wie Abo-Kanäle" → Neuladen`, async ({ page }) => {
			await page.setViewportSize(layout.vp);
			const id = kind === 'route' ? await seedTrip(page) : await seedVergleich(page);
			const blockSel = '[data-testid="kanal-block"]:visible';

			await openHub(page, kind, id, { tab: 'alarme' });
			await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
			let block = page.locator(blockSel).first();
			const { key, zeile } = await blockPruefen(page, block);
			expect(await gespeichert(page, kind, id, key), 'Vorbedingung: kein Eintrag gespeichert').toBeFalsy();

			// Umschalten + Telegram wählen → Autosave des Hubs (kein eigener Speichern-Knopf).
			await eigeneWahlMitTelegram(page, zeile, key);
			await expect
				.poll(async () => (await gespeichert(page, kind, id, key))?.telegram, {
					message: 'AC-62: Wahl wurde nicht gespeichert (alert_metric_channels fehlt im Server-Stand)',
					timeout: 20_000
				})
				.toBe(true);
			const gespeicherterEintrag = (await gespeichert(page, kind, id, key)) as Record<string, unknown>;
			for (const flag of ['email', 'telegram', 'sms', 'premium_sms']) {
				expect(typeof gespeicherterEintrag[flag], `AC-44: Flag ${flag} muss Boolean sein`).toBe('boolean');
			}

			// Neu laden: Wahl ist noch da.
			await openHub(page, kind, id, { tab: 'alarme' });
			block = page.locator(blockSel).first();
			const z2 = block.getByTestId(`kanal-zeile-${key}`);
			await expect(z2).toBeVisible({ timeout: 25_000 });
			await expect(eigeneWahl(z2, key).locator('input[type="checkbox"]'), 'nach Neuladen: „eigene Wahl" nicht mehr an').toBeChecked();
			await expect(telegram(z2, key).locator('input[type="checkbox"]'), 'nach Neuladen: Telegram nicht mehr an').toBeChecked();
			await pruefeBedienbar(page, telegram(z2, key).locator('label'), 'Kanal-Schalter Telegram nach Neuladen');

			// Zurück auf „wie Abo-Kanäle" → gespeichert als null/erbt.
			await eigeneWahl(z2, key).locator('label').click();
			await expect(z2.getByTestId(`kanal-erbt-${key}`)).toHaveText(WIE_ABO);
			await expect
				.poll(async () => await gespeichert(page, kind, id, key), {
					message: 'AC-46: Rückschalten auf „wie Abo-Kanäle" wurde nicht gespeichert',
					timeout: 20_000
				})
				.toBeFalsy();

			// Neu laden: wieder „wie Abo".
			await openHub(page, kind, id, { tab: 'alarme' });
			const z3 = page.locator(blockSel).first().getByTestId(`kanal-zeile-${key}`);
			await expect(z3).toBeVisible({ timeout: 25_000 });
			await expect(z3.getByTestId(`kanal-erbt-${key}`)).toHaveText(WIE_ABO);
			await expect(eigeneWahl(z3, key).locator('input[type="checkbox"]')).not.toBeChecked();
		});
	}
}

// ── Anlegen-Seiten: Block sichtbar + bedienbar in .tn-/.cm-mobile und -desktop ──

/** Reiterkette bis „Alarme" (jeder Besuch schaltet den nächsten frei). */
async function zumAlarmeReiter(page: Page, kind: HubKind, mobil: boolean): Promise<void> {
	const sel = ANLEGE_SEL[kind];
	if (kind === 'vergleich' && !mobil) {
		// Desktop-Vergleich: Weiter-Knöpfe (Muster compare-neu-kanal-anlegen).
		await page.getByTestId('compare-editor-continue-wetter-metriken').click();
		await page.getByTestId('compare-editor-continue-wertebereiche').click();
		await page.getByTestId('compare-editor-continue-alarme').click();
		return;
	}
	for (const reiter of ['wetter-metriken', 'wertebereiche', 'alarme']) {
		await sel.reiter(page, reiter, mobil).click({ force: true });
	}
}

const ANLEGE_LAYOUTS = [
	{ mobil: true, vp: MOBIL, name: 'mobil' },
	{ mobil: false, vp: DESKTOP, name: 'Desktop' }
] as const;

for (const kind of ['route', 'vergleich'] as const) {
	const praefix = kind === 'route' ? (m: boolean) => (m ? '.tn-mobile' : '.tn-desktop') : (m: boolean) => (m ? '.cm-mobile' : '.cm-desktop');
	for (const l of ANLEGE_LAYOUTS) {
		test(`AC-58/AC-62: Anlege-Seite ${ANLEGE_SEL[kind].url}, ${praefix(l.mobil)} (${l.name}) — Block sichtbar, bedienbar, Wahl landet im angelegten Objekt`, async ({ page }) => {
			const s = Date.now();
			// Vergleich: ≥ 3 Orte VOR dem Öffnen (Bibliothek lädt beim goto).
			const orte =
				kind === 'vergleich'
					? [
							await createTestLocation(page.request, { name: `1895-kb-neu-A-${s}`, lat: 47.1, lon: 11.2 }),
							await createTestLocation(page.request, { name: `1895-kb-neu-B-${s}`, lat: 47.2, lon: 11.3 }),
							await createTestLocation(page.request, { name: `1895-kb-neu-C-${s}`, lat: 47.3, lon: 11.4 })
						]
					: undefined;
			await anlegenPflicht(page, kind, {
				name: `E2E-GZ-1895-Kanalblock-Neu-${s}`,
				mobil: l.mobil,
				viewport: l.vp,
				orte
			});
			await zumAlarmeReiter(page, kind, l.mobil);

			const scope = page.locator(praefix(l.mobil));
			const block = scope.getByTestId('kanal-block');
			const { key, zeile } = await blockPruefen(page, block);
			await eigeneWahlMitTelegram(page, zeile, key);

			// Abschluss: Trip „Speichern", Vergleich „Briefing aktivieren" direkt nach Alarme (kein Versand-Schritt seit #1743).
			const abschluss = ANLEGE_SEL[kind].abschluss(page, l.mobil);
			await expect(abschluss, 'Abschluss-Knopf bleibt gesperrt').toBeEnabled({ timeout: 20_000 });
			const antwort = page.waitForResponse(
				(r) => r.request().method() === 'POST' && new URL(r.url()).pathname === ANLEGE_SEL[kind].postPfad,
				{ timeout: 30_000 }
			);
			await abschluss.click();
			const res = await antwort;
			expect(res.ok(), `Anlage HTTP ${res.status()}`).toBeTruthy();
			const rumpf = res.request().postDataJSON() as Stand;
			expect(Object.keys(rumpf), 'AC-54/55: Anlege-Payload trägt alert_metric_channels nicht').toContain('alert_metric_channels');
			const angelegt = (await res.json()) as { id: string };
			registerForCleanup(kind === 'route' ? 'trip' : 'preset', angelegt.id);

			await expect
				.poll(async () => (await gespeichert(page, kind, angelegt.id, key))?.telegram, {
					message: 'AC-54/55: angelegtes Objekt trägt die Wahl nicht',
					timeout: 20_000
				})
				.toBe(true);
		});
	}
}
