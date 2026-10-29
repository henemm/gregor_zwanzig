// E2E — Issue #2347 S3c (Epic #2345, Etappe P6): Konfliktschutz im Hub mit ZWEI
// Browser-Kontexten desselben Nutzers — EINE Spec für Trip UND Ortsvergleich
// (Schleife über HUB_KINDS). Löst die Alt-Spec compare-konfliktschutz-zwei-kontexte
// ab (#2375/#2381); das Trip-Pendant (#1433) war bisher nie im CI-Stack gemessen.
//
// Spec: docs/specs/modules/feat_2347_s3c_paritaets_e2e.md
//   KS-1 / AC-1 — A ändert den Namen, B speichert danach je Reiter (Alarme,
//                 Wertebereiche, Versand [Abschnitt im Reiter Wetter-Metriken],
//                 Wetter-Metriken): erster PUT von B trägt If-Match aus dem
//                 Seitenaufbau, 412, „Nochmal speichern", Name von A UND
//                 Änderung von B stehen auf dem Server.
//   KS-2 / AC-2 — selber Tab: Reiter-Wert speichern, danach Name ändern ⇒ beides
//                 auf dem Server; der Kopf-PUT ist exakt { name } (#2381).
//   KS-3 / AC-3 — Pausieren im Hub (Übertragungsweg je kind verschieden).
//   KS-4 / AC-4 — Pausieren auf der Listenseite (/trips bzw. /compare).
//
// Warum E2E: „die fremde Änderung überlebt" wirkt erst im Zusammenspiel von
// Seitenaufbau (ETag), Reiter-Nutzlast, 412-Pfad und Go-Merge — nur im Browser mit
// zwei Kontexten messbar. Zweiter Kontext = weiterer Browser-Kontext mit DEMSELBEN
// storageState (kein zweiter Login ⇒ keine 429-Sperre). Der Orte-Fall (compare-
// eigen) steht in compare-orte-konfliktschutz-zwei-kontexte.spec.ts.
//
// kind-Zweige gibt es nur dort, wo das Produkt für den Trip eine ANDERE Form hat
// (Spec „Kind-Kontraste"): Reiter-Schreibweg/Auslöser (KS_REITER) und der
// Pausier-Übertragungsweg (KS_STATUS). Jeder Zweig prüft seine EIGENE Zusicherung.
//
// Wartebedingungen nur expect.poll / toHaveAttribute / toHaveCount / toBeVisible.
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh); Wegwerf-Objekte E2E-GZ-,
// Aufräumen im finally, Zweit-Kontexte im afterEach.

import { test, expect, type Browser, type BrowserContext, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX, HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;

let weitereKontexte: BrowserContext[] = [];

test.afterEach(async () => {
	for (const ctx of weitereKontexte) await ctx.close().catch(() => undefined);
	weitereKontexte = [];
});

/** Zweiter Kontext DESSELBEN Nutzers (gleicher storageState, kein neuer Login). */
async function kontextB(browser: Browser, baseURL: string | undefined, storageState: unknown): Promise<Page> {
	const ctx = await browser.newContext({
		baseURL,
		storageState: storageState as string,
		serviceWorkers: 'block',
		viewport: { width: 1280, height: 900 }
	});
	weitereKontexte.push(ctx);
	return ctx.newPage();
}

/** Alle PUTs auf die angegebenen Pfade (Request = abgeschickter Rumpf). */
function sammlePuts(page: Page, pfade: Set<string>): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && pfade.has(new URL(r.url()).pathname)) puts.push(r);
	});
	return puts;
}

async function serverStand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const status = async (r: Request | undefined) => (r ? (await r.response())?.status() : 0);

/** Kontext A benennt den Hub über den Kopf um und wartet auf den gespeicherten PUT. */
async function benenneUm(page: Page, kind: HubKind, id: string, name: string): Promise<Request> {
	const kopf = HUB_SEL[kind].kopf;
	const puts = sammlePuts(page, new Set([hubApiPath(kind, id)]));
	await page.locator(`[data-testid="${kopf}-name-edit-toggle"]:visible`).click();
	await page.locator(`[data-testid="${kopf}-name-edit"]:visible`).fill(name);
	await page.locator(`[data-testid="${kopf}-name-save"]:visible`).click();
	await expect.poll(() => status(puts[0]), { timeout: 10_000 }).toBe(200);
	return puts[0];
}

async function kebabWaehle(page: Page, punkt: 'Pausieren'): Promise<void> {
	await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
	const eintrag = page.getByRole('menuitem', { name: punkt });
	await expect(eintrag, `Vorbedingung: der Hub bietet „${punkt}" an`).toBeVisible();
	await eintrag.click();
}

interface ReiterFall {
	reiter: string;
	/** Tab-Kennung im Hub (`?tab=`) und optionaler Hash. */
	tab: string;
	hash?: string;
	seed: Record<string, unknown>;
	/** Der Speichervorgang schreibt zusätzlich auf `…/weather-config` (nur Trip-Wetter-Metriken). */
	nebenPfad?: boolean;
	bereit: (p: Page) => Promise<void>;
	aendern: (p: Page) => Promise<void>;
	pruefe: (s: Stand) => void;
}

const rc = (s: Stand) => (s.report_config as Stand | undefined) ?? {};
const dc = (s: Stand) => (s.display_config as Stand | undefined) ?? {};

// Auslöser je Reiter und kind: derselbe geteilte Reiter-Baustein, aber kind-eigene
// Felder/Schalter (Spec „Kind-Kontraste"; Quellen: hub-alarme-/-wertebereiche-/
// -wetter-metriken-/-versand-speichert-selbst). Der Trip hat keinen Radar-Alarm.
const KS_REITER: Record<HubKind, ReiterFall[]> = {
	route: [
		{
			reiter: 'Alarme',
			tab: 'alarme',
			seed: { official_warnings: { enabled: true } },
			bereit: async (p) => {
				await expect(p.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				await p.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first().click();
			},
			pruefe: (s) =>
				expect((s.official_warnings as { enabled?: boolean } | undefined)?.enabled, 'Alarme-Änderung von B fehlt auf dem Server').toBe(false)
		},
		{
			reiter: 'Wertebereiche',
			tab: 'wertebereiche',
			seed: { corridors: [{ metric: 'wind_gust', range: [30, 70], notify: false, mark: false }] },
			bereit: async (p) => {
				const editor = p.locator('[data-testid="corridor-editor-route"]:visible');
				await expect(editor.locator('[data-testid="corridor-row-wind_gust"]')).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				const editor = p.locator('[data-testid="corridor-editor-route"]:visible');
				await editor.locator('[data-testid="corridor-editor-pool-item-precipitation_sum"]').click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
			},
			pruefe: (s) => expect((s.corridors as unknown[]).length, 'Wertebereiche-Änderung von B fehlt auf dem Server').toBe(2)
		},
		{
			// #1743: kein eigener Reiter — Versand ist der Abschnitt `#versand` im Reiter Wetter-Metriken.
			reiter: 'Versand',
			tab: 'wetter-metriken',
			hash: 'versand',
			seed: {},
			bereit: async (p) => {
				await expect(p.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible')).toBeVisible({
					timeout: 10_000
				});
			},
			aendern: async (p) => {
				await p.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible').selectOption('08:00');
			},
			// Trip führt die Uhrzeit in report_config.
			pruefe: (s) => expect(String(rc(s).morning_time), 'Versand-Änderung von B fehlt auf dem Server').toMatch(/^08:00/)
		},
		{
			reiter: 'Wetter-Metriken',
			tab: 'wetter-metriken',
			nebenPfad: true,
			seed: {
				official_alerts_enabled: true,
				official_warnings: { enabled: true },
				display_config: { metrics: [{ metric_id: 'snow_depth', enabled: true, bucket: 'primary', order: 0 }] },
				report_config: {
					enabled: true,
					morning_enabled: true,
					evening_enabled: false,
					morning_time: '06:00:00',
					evening_time: '18:00:00',
					show_outlook: false,
					email_format: 'compact'
				}
			},
			bereit: async (p) => {
				const tab = p.locator('[data-testid="weather-metrics-tab"]:visible');
				await expect(tab.getByTestId('wm2-grundauswahl').getByRole('button', { name: /Schneehöhe/ })).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				const tab = p.locator('[data-testid="weather-metrics-tab"]:visible');
				await tab.getByTestId('wm2-grundauswahl').getByRole('button', { name: /Schneehöhe/ }).click();
			},
			pruefe: (s) =>
				expect(
					((dc(s).metrics as Array<{ metric_id: string; enabled?: boolean }> | undefined) ?? []).some(
						(m) => m.metric_id === 'snow_depth' && m.enabled
					),
					'Wetter-Metriken-Änderung von B fehlt auf dem Server'
				).toBe(false)
		}
	],
	vergleich: [
		{
			reiter: 'Alarme',
			tab: 'alarme',
			seed: { radar_alert_enabled: false, display_config: { active_metrics: ['wind_max_kmh'] } },
			bereit: async (p) => {
				await expect(p.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				const radar = p.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
				await radar.click();
				await expect(radar).toBeChecked();
			},
			pruefe: (s) => expect(s.radar_alert_enabled, 'Alarme-Änderung von B fehlt auf dem Server').toBe(true)
		},
		{
			reiter: 'Wertebereiche',
			tab: 'wertebereiche',
			seed: {
				corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
				display_config: {
					ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
					active_metrics: ['snow_depth_cm'],
					telegram_style: 'kurzform'
				}
			},
			bereit: async (p) => {
				const editor = p.locator('[data-testid="corridor-editor-vergleich"]:visible');
				await expect(editor.locator('[data-testid="corridor-row-snow_depth_cm"]')).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				const editor = p.locator('[data-testid="corridor-editor-vergleich"]:visible');
				await editor.locator('[data-testid="corridor-editor-pool-item-wind_max_kmh"]').click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
			},
			pruefe: (s) => expect((s.corridors as unknown[]).length, 'Wertebereiche-Änderung von B fehlt auf dem Server').toBe(2)
		},
		{
			reiter: 'Versand',
			tab: 'wetter-metriken',
			hash: 'versand',
			seed: {},
			bereit: async (p) => {
				await expect(p.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible')).toBeVisible({
					timeout: 10_000
				});
			},
			aendern: async (p) => {
				await p.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible').selectOption('08:00');
			},
			// Vergleich führt die Uhrzeit als Flachfeld.
			pruefe: (s) => expect(s.morning_time, 'Versand-Änderung von B fehlt auf dem Server').toBe('08:00:00')
		},
		{
			reiter: 'Wetter-Metriken',
			tab: 'wetter-metriken',
			seed: {
				official_alerts_enabled: true,
				display_config: { active_metrics: ['snow_depth_cm'], telegram_style: 'kurzform' }
			},
			bereit: async (p) => {
				await expect(
					p.locator('[data-testid="weather-metrics-tab-vergleich"]:visible [data-testid="report-show-official-alerts"]')
				).toBeVisible({ timeout: 10_000 });
			},
			aendern: async (p) => {
				await p
					.locator('[data-testid="weather-metrics-tab-vergleich"]:visible [data-testid="report-show-official-alerts"] input[type="checkbox"]')
					.click();
			},
			pruefe: (s) => expect(s.official_alerts_enabled, 'Wetter-Metriken-Änderung von B fehlt auf dem Server').toBe(false)
		}
	]
};

// Pausieren: der Übertragungsweg unterscheidet sich je kind ENTWURFSGEMÄSS
// (Spec Entscheidung 4/5): Trip PATCH …/state {paused} OHNE If-Match (strukturell
// kein 412), Vergleich PUT {schedule, previous_schedule} MIT If-Match (⇒ 412).
// `bestand`/`bestandSeed`: der Datenverlust-Check nach dem Pausieren gilt für BEIDE
// kinds — nur die Liste heißt je kind anders (Trip `stages`, Seed 1 Etappe;
// Vergleich `location_ids`, Seed 2 Orte; Kind-Kontraste „Pausieren im Hub"/„Orte").
const KS_STATUS: Record<
	HubKind,
	{ ersterWert: Stand; istPausiert: (s: Stand) => boolean; bestand: (s: Stand) => unknown[]; bestandSeed: number }
> = {
	route: {
		ersterWert: { paused: true },
		istPausiert: (s) => Boolean(s.paused_at),
		bestand: (s) => (s.stages as unknown[]) ?? [],
		bestandSeed: 1
	},
	vergleich: {
		ersterWert: { schedule: 'manual', previous_schedule: 'daily' },
		istPausiert: (s) => s.schedule === 'manual',
		bestand: (s) => (s.location_ids as unknown[]) ?? [],
		bestandSeed: 2
	}
};

/** Alle Schreibvorgänge eines Kontexts auf das Objekt (PUT) und seinen Status-Unterpfad (PATCH). */
function sammleSchreiber(page: Page, pfad: string): { puts: Request[]; patches: Request[] } {
	const puts: Request[] = [];
	const patches: Request[] = [];
	page.on('request', (r) => {
		const p = new URL(r.url()).pathname;
		if (r.method() === 'PUT' && p === pfad) puts.push(r);
		if (r.method() === 'PATCH' && p === `${pfad}/state`) patches.push(r);
	});
	return { puts, patches };
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];

	test.describe(`Hub · Konfliktschutz mit zwei Kontexten (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// KS-1 (Alt Test 9) — je Reiter. Fängt: Vollobjekt-Nutzlast mit stalem Namen,
		// fehlendes If-Match, 412 als generischer Fehler, „Nochmal speichern" ohne frischen Stempel.
		for (const fall of KS_REITER[kind]) {
			test(`KS-1 (${kind}, ${fall.reiter}): A ändert den Namen, B speichert danach → 412 mit If-Match → „Nochmal speichern" → Name von A UND Änderung von B`, async ({
				page,
				browser,
				baseURL,
				storageState
			}) => {
				const hub = await seedHub(page.request, kind, { extra: fall.seed });
				try {
					const pfad = hubApiPath(kind, hub.id);
					const pfade = new Set([pfad, ...(fall.nebenPfad ? [`${pfad}/weather-config`] : [])]);
					const schritte = pfade.size; // PUTs je vollständigem Speichervorgang

					// B lädt ZUERST — sein Stand ist danach veraltet
					const b = await kontextB(browser, baseURL, storageState);
					const putsB = sammlePuts(b, pfade);
					await openHub(b, kind, hub.id, { tab: fall.tab, hash: fall.hash });
					await fall.bereit(b);

					// A ändert den Namen
					await openHub(page, kind, hub.id);
					const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
					await benenneUm(page, kind, hub.id, nameA);

					// B speichert seine Reiter-Änderung
					await fall.aendern(b);
					await expect(anzeige(b)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
					expect(putsB.length, 'Vorbedingung: B hat genau EINEN PUT gesendet (der Vorgang bricht beim ersten ab)').toBe(1);
					expect(
						await putsB[0].headerValue('if-match'),
						'AC-1: der erste PUT nach dem Laden muss If-Match aus dem Seitenaufbau tragen'
					).toBeTruthy();
					expect(await status(putsB[0]), 'AC-1: der veraltete Stand muss mit 412 abgelehnt werden').toBe(412);
					if (fall.nebenPfad) {
						// Trip-Wetter-Metriken: der Vorgang beginnt auf der Neben-Ressource.
						expect(new URL(putsB[0].url()).pathname, 'abgelehnt wird der ERSTE PUT des Vorgangs (weather-config)').toBe(
							`${pfad}/weather-config`
						);
					}

					// „Nochmal speichern"
					await anzeige(b).getByRole('button', { name: 'Nochmal speichern' }).click();
					await expect(anzeige(b)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					await expect.poll(() => putsB.length, { timeout: 10_000, message: 'der Wiederholungs-Vorgang wurde gesendet' }).toBe(1 + schritte);
					for (const r of putsB.slice(1)) {
						expect(await status(r), `der Wiederholungs-PUT ${new URL(r.url()).pathname} muss durchgehen`).toBe(200);
						expect(Object.keys(r.postDataJSON() as Stand), 'der Wiederholungs-PUT darf `name` nicht tragen').not.toContain('name');
					}

					const stand = await serverStand(page, kind, hub.id);
					expect(stand.name, 'der Name von A ging beim „Nochmal speichern" von B verloren').toBe(nameA);
					fall.pruefe(stand);
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// KS-2 (Alt Test 10, #2381) — selber Tab. Fängt: Kopf-Edit sendet Vollobjekt aus alter Baseline.
		test(`KS-2 (${kind}, #2381): Reiter-Wert speichern, danach im selben Tab den Namen ändern → beides auf dem Server, Kopf-PUT = { name }`, async ({
			page
		}) => {
			const fall = KS_REITER[kind][0]; // Alarme: kleinster Reiter-Schreibweg
			const hub = await seedHub(page.request, kind, { extra: fall.seed });
			try {
				await openHub(page, kind, hub.id, { tab: fall.tab });
				await fall.bereit(page);
				await fall.aendern(page);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect
					.poll(async () => {
						try {
							fall.pruefe(await serverStand(page, kind, hub.id));
							return 'gespeichert';
						} catch {
							return 'offen';
						}
					}, { timeout: 10_000 })
					.toBe('gespeichert');

				const neuerName = `${E2E_TEST_PREFIX}Umbenannt ${Date.now()}`;
				const kopfPut = await benenneUm(page, kind, hub.id, neuerName);
				expect(kopfPut.postDataJSON(), 'der Kopf-PUT darf nur { name } tragen').toEqual({ name: neuerName });

				const stand = await serverStand(page, kind, hub.id);
				expect(stand.name).toBe(neuerName);
				fall.pruefe(stand); // Kopf-Edit hat den eben gespeicherten Alarm-Wert zurückgeschrieben (#2381)?
			} finally {
				await hub.aufraeumen();
			}
		});

		// KS-3 (Alt Test 11a) — Pausieren im Hub. Übertragungsweg je kind verschieden
		// (KS_STATUS, Spec Entscheidung 4): jeder Zweig prüft seine EIGENE Zusicherung.
		test(`KS-3 (${kind}): A ändert den Namen, B pausiert im Hub → Name von A bleibt, Status gesetzt, Status-Körper trägt nur den Status`, async ({
			page,
			browser,
			baseURL,
			storageState
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const b = await kontextB(browser, baseURL, storageState);
				const schreiberB = sammleSchreiber(b, pfad);
				await openHub(b, kind, hub.id);

				await openHub(page, kind, hub.id);
				const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
				await benenneUm(page, kind, hub.id, nameA);

				await kebabWaehle(b, 'Pausieren');

				if (kind === 'vergleich') {
					// Vergleich: PUT {schedule, previous_schedule} MIT If-Match ⇒ 412 ⇒ „Nochmal speichern".
					await expect.poll(() => status(schreiberB.puts[0]), { timeout: 10_000 }).toBe(412);
					expect(await schreiberB.puts[0].headerValue('if-match'), 'AC-1: If-Match aus dem Seitenaufbau').toBeTruthy();
					// F002: auch der ERSTE Status-PUT trägt nur den Status — sonst würde ein Spread der
					// veralteten Baseline im Einzel-Tab (gültiger Stempel) mit 200 angenommen (#2381-Klasse).
					expect(Object.keys(schreiberB.puts[0].postDataJSON()).sort(), 'erster Status-PUT trägt nur den Status').toEqual([
						'previous_schedule',
						'schedule'
					]);
					await expect(anzeige(b)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
					await anzeige(b).getByRole('button', { name: 'Nochmal speichern' }).click();
					await expect(anzeige(b)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					expect(schreiberB.puts.length, 'der Wiederholungs-PUT wurde gesendet').toBe(2);
					expect(await status(schreiberB.puts[1])).toBe(200);
					expect(Object.keys(schreiberB.puts[1].postDataJSON()).sort(), 'Status-PUT trägt nur den Status').toEqual([
						'previous_schedule',
						'schedule'
					]);
				} else {
					// Trip: PATCH …/state {paused} OHNE If-Match — strukturell kein 412, kein PUT auf den Trip aus B.
					await expect.poll(() => status(schreiberB.patches[0]), { timeout: 10_000 }).toBe(200);
					expect(schreiberB.patches[0].postDataJSON(), 'der Trip-Status-Abruf trägt genau { paused: true }').toEqual(
						KS_STATUS.route.ersterWert
					);
					expect(await schreiberB.patches[0].headerValue('if-match'), 'Trip-Pausieren geht bewusst ohne If-Match').toBeFalsy();
					await expect(anzeige(b)).not.toHaveAttribute('data-state', 'conflict');
					expect(schreiberB.puts.length, 'Pausieren darf keinen PUT auf den veralteten Trip senden').toBe(0);
				}

				const stand = await serverStand(page, kind, hub.id);
				expect(KS_STATUS[kind].istPausiert(stand), `${sel.kopf}: Status ist nicht pausiert`).toBe(true);
				expect(stand.name, 'Pausieren im Hub hat den Namen von A überschrieben').toBe(nameA);
				// Datenverlust-Check für BEIDE kinds (kein kind-Zweig): Etappen bzw. Orte bleiben vollständig.
				expect(KS_STATUS[kind].bestand(stand).length, 'Pausieren darf keine Etappen/Orte verlieren').toBe(
					KS_STATUS[kind].bestandSeed
				);
			} finally {
				await hub.aufraeumen();
			}
		});

		// KS-4 (Alt Test 11b) — Pausieren auf der Listenseite. Beide Listen rufen
		// setPaused(kind, …): Status-Teilkörper, bewusst ohne If-Match (Spec Entscheidung 5).
		test(`KS-4 (${kind}): A ändert den Namen, B pausiert auf der Listenseite ${sel.liste.url} → Status-Körper trägt nur den Status, Name von A bleibt`, async ({
			page,
			browser,
			baseURL,
			storageState
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const b = await kontextB(browser, baseURL, storageState);
				const schreiberB = sammleSchreiber(b, pfad);
				await b.goto(sel.liste.url);
				const zeile = b.locator(`[data-testid="${sel.liste.zeile(hub.id)}"]:visible`).first();
				await expect(zeile).toBeVisible({ timeout: 10_000 });

				await openHub(page, kind, hub.id);
				const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
				await benenneUm(page, kind, hub.id, nameA);

				await zeile.locator(`[data-testid="${sel.liste.menue}"]:visible`).first().click();
				await b.getByRole('menuitem', { name: 'Pausieren' }).click();

				// Übertragungsweg je kind: Trip PATCH …/state, Vergleich PUT (Spec Entscheidung 5).
				const abruf = kind === 'route' ? schreiberB.patches : schreiberB.puts;
				await expect.poll(() => status(abruf[0]), { timeout: 10_000 }).toBe(200);
				expect(abruf[0].postDataJSON(), 'der Listen-Menüpunkt darf nur den Status senden').toEqual(KS_STATUS[kind].ersterWert);

				const stand = await serverStand(page, kind, hub.id);
				expect(KS_STATUS[kind].istPausiert(stand), 'Status ist nicht pausiert').toBe(true);
				expect(stand.name, 'Pausieren auf der Listenseite hat den Namen von A überschrieben').toBe(nameA);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
