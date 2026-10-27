// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Wertebereiche"
// (geteilter CorridorEditor) speichert über GENAU EINEN Weg — EINE Zusicherung
// für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-3 (WS-1..WS-7)
//
// Ersetzt compare-wertebereiche-speichert-selbst.spec.ts (#2276 S3, nur Vergleich):
//   AC-1 zwei Metriken → ein PUT          → WS-1
//   AC-2 Regler, Loslassen außerhalb     → WS-2
//   AC-4 Reiterwechsel → Alarme          → WS-3
//   AC-5 412 → „Nochmal speichern"       → WS-4
//   AC-6 Pausieren flusht                → WS-5
//   #2375 Roundtrip Korridor-Leerung     → WS-6
//   AC-11 übrige Einstellungen bleiben   → WS-7 (in der Spec-Zuordnung nicht
//                                           eigens benannt, 1:1 übernommen)
//
// Eigen-Seed statt erstem Pool-Eintrag: je kind eine benannte Seed-Zeile und
// zwei benannte Pool-Metriken, deren Startwerte gültig sind (Trip:
// ROUTE_METRIC_DEFS, Vergleich: _COMPARE_DEFAULTS in corridorEditorState.ts).
// Kein fester Schlaf: „genau ein PUT" per Stabilitätsfenster (≥ alte 1,2-s-Nachfrist).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
const dc = (body: Stand) => (body.display_config as Stand | undefined) ?? {};

/** kind-Tabelle: Seed-Zeile, Pool-Metriken, Eigenfelder, Alarm-Auslöser, Status-Weg. */
const WS_SEL: Record<
	HubKind,
	{
		zeile: string;
		seed: Record<string, unknown>;
		/** zwei Pool-Metriken mit gültigen Startwerten (Startzustand: nicht in den Zeilen). */
		pool: [string, string];
		/** Schlüssel des Wertebereiche-Rumpfs (sortiert) — Trip: nur `corridors`
		 *  (CorridorEditor.svelte:268), Vergleich: `corridors` + `display_config`. */
		rumpfSchluessel: string[];
		/** Rumpf-Ausschnitt einer Korridor-Leerung (#2375). */
		leerRumpf: Record<string, unknown>;
		/** Felder oben im Objekt, die der Reiter schreiben darf (WS-7). */
		obenEigen: Set<string>;
		/** display_config-Schlüssel, die der Reiter schreiben darf (WS-7). */
		dcEigen: Set<string>;
		/** zweite Änderung im Alarme-Reiter (WS-3). */
		alarm: (page: Page) => Locator;
		alarmWert: (s: Stand) => unknown;
		alarmNeu: boolean;
		statusSchluessel: string[];
		statusPausiert: (rumpf: Stand) => boolean;
		istPausiert: (s: Stand) => boolean;
	}
> = {
	route: {
		zeile: 'wind_gust',
		seed: {
			official_warnings: { enabled: true },
			corridors: [{ metric: 'wind_gust', range: [30, 70], notify: false, mark: false }]
		},
		pool: ['precipitation_sum', 'temperature_max'],
		rumpfSchluessel: ['corridors'],
		leerRumpf: { corridors: [] },
		obenEigen: new Set(['corridors', 'updated_at', 'etag']),
		dcEigen: new Set(),
		alarm: (page) =>
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled,
		alarmNeu: false,
		statusSchluessel: ['paused'],
		statusPausiert: (r) => r.paused === true,
		istPausiert: (s) => Boolean(s.paused_at)
	},
	vergleich: {
		zeile: 'snow_depth_cm',
		seed: {
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
		},
		pool: ['wind_max_kmh', 'precip_sum_mm'],
		rumpfSchluessel: ['corridors', 'display_config'],
		leerRumpf: { corridors: [], display_config: { ideal_ranges: {} } },
		obenEigen: new Set(['corridors', 'display_config', 'updated_at', 'etag']),
		dcEigen: new Set(['ideal_ranges', 'active_metrics', 'metric_alert_levels']),
		alarm: (page) => page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => s.radar_alert_enabled,
		alarmNeu: true,
		statusSchluessel: ['previous_schedule', 'schedule'],
		statusPausiert: (r) => r.schedule === 'manual',
		istPausiert: (s) => s.schedule === 'manual'
	}
};

/** Zählt die PUTs auf genau dieses Objekt (abgeschickt bzw. beantwortet). */
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

/** Geordnetes Protokoll: PUT auf das Objekt ODER PATCH auf seinen Status-Unterpfad. */
function protokolliereSchreiber(page: Page, pfad: string): { alle: Request[]; fertig: Request[] } {
	const alle: Request[] = [];
	const fertig: Request[] = [];
	const trifft = (r: Request) => {
		const p = new URL(r.url()).pathname;
		return (r.method() === 'PUT' && p === pfad) || (r.method() === 'PATCH' && p === `${pfad}/state`);
	};
	page.on('request', (r) => {
		if (trifft(r)) alle.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) fertig.push(r);
	});
	return { alle, fertig };
}

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
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

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const korridore = (body: Stand) => (body.corridors as Array<{ metric: string; range: unknown[] }>) ?? [];

async function oeffneWertebereiche(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wertebereiche' });
	// HubKind == context-Parameter des geteilten Korridor-Editors.
	const editor = page.locator(`[data-testid="corridor-editor-${kind}"]:visible`);
	await expect(editor).toBeVisible({ timeout: 10_000 });
	await expect(editor.locator(`[data-testid="corridor-row-${WS_SEL[kind].zeile}"]`)).toBeVisible({ timeout: 10_000 });
	return editor;
}

/** Pool-Eintrag per Namen (Eigen-Seed), mit Sichtbarkeits-Vorbedingung. */
async function poolEintrag(editor: Locator, metric: string): Promise<Locator> {
	const btn = editor.locator(`[data-testid="corridor-editor-pool-item-${metric}"]`);
	await expect(btn, `Vorbedingung: Pool bietet ${metric} an`).toBeVisible({ timeout: 10_000 });
	return btn;
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ws = WS_SEL[kind];

	test.describe(`Hub · Wertebereiche speichert über genau einen Weg (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// WS-1 (Alt AC-1) — fängt: zweiter Speicherweg (Wrapper) ⇒ zwei PUTs statt einem.
		test(`WS-1 (${kind}): zwei Metriken schnell hintereinander hinzufügen → genau EIN PUT mit beiden, danach „Gespeichert"`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);
				const [a, b] = [await poolEintrag(editor, ws.pool[0]), await poolEintrag(editor, ws.pool[1])];

				// beide Klicks innerhalb des Entprell-Fensters (700 ms)
				await a.click();
				await b.click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(3, { timeout: 5_000 });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect(anzeige(page)).toContainText('Gespeichert');
				await bleibtBei(() => puts.length, 1, 1_200, 'genau EIN PUT für eine Bedienfolge im Entprell-Fenster');

				expect(korridore(puts[0].postDataJSON() as Stand).length, 'der eine PUT trägt beide neuen Metriken').toBe(3);
				expect(korridore(await stand(page, kind, hub.id)).length).toBe(3);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-2 (Alt AC-2) — fängt: kein PUT nach Loslassen außerhalb bzw. zwei Wege.
		test(`WS-2 (${kind}): Regler ziehen, Maus über dem Reiterkopf loslassen → gespeichert, genau EIN PUT, überlebt Neuladen`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const row = editor.locator(`[data-testid="corridor-row-${ws.zeile}"]`);
				const handle = await row.locator('.ce-handle').first().boundingBox();
				const kopf = await page.locator(`[data-testid="${sel.reiter}-uebersicht"]:visible`).boundingBox();
				expect(handle).not.toBeNull();
				expect(kopf).not.toBeNull();

				await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2);
				await page.mouse.down();
				await page.mouse.move(handle!.x + 50, handle!.y - 20, { steps: 8 });
				await page.mouse.move(kopf!.x + kopf!.width / 2, kopf!.y + kopf!.height / 2, { steps: 15 });
				await page.mouse.up();

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtBei(() => puts.length, 1, 1_200, 'Loslassen außerhalb darf keinen zweiten, eigenen Speicherweg auslösen');

				const minWert = await row.locator('input[type="number"]').first().inputValue();
				expect(minWert, 'Vorbedingung: der Regler hat sich bewegt').not.toBe('30');
				const neu = await oeffneWertebereiche(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ws.zeile}"] input[type="number"]`).first()
				).toHaveValue(minWert, { timeout: 5_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-3 (Alt AC-4) — fängt: Flush-Guard ohne 'wertebereiche' ⇒ der
		// Alarm-Vorgang verdrängt die Wertebereich-Änderung.
		test(`WS-3 (${kind}): Wertebereich ändern, sofort zu „Alarme", dort Alarm ändern → BEIDE Änderungen gespeichert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await (await poolEintrag(editor, ws.pool[0])).click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
				// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
				await page.locator(`[data-testid="${sel.reiter}-alarme"]:visible`).click();
				await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
				expect(beantwortet.length, 'die Wertebereich-Änderung war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);

				await ws.alarm(page).click();
				await expect(ws.alarm(page)).toBeChecked({ checked: ws.alarmNeu });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const [erster, zweiter] = puts.map((r) => r.postDataJSON() as Stand);
				expect(korridore(erster).length, 'erster PUT = Wertebereich-Änderung').toBe(2);
				expect(ws.alarmWert(zweiter)).toBe(ws.alarmNeu);
				const s = await stand(page, kind, hub.id);
				expect(korridore(s).length, 'die Wertebereich-Änderung ging beim Reiterwechsel verloren').toBe(2);
				expect(ws.alarmWert(s)).toBe(ws.alarmNeu);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-4 (Alt AC-5) — fängt: 412 als generischer Fehler bzw. Rücknahme bei 412.
		// Issue #2375: der Seitenaufbau übernimmt den ETag ⇒ schon der ERSTE PUT
		// trägt If-Match; der Reiter sendet nur Eigenfelder ⇒ der fremde Name überlebt.
		test(`WS-4 (${kind}): fremde Änderung dazwischen → erster PUT 412 → „Nochmal speichern" → gespeichert, fremder Name bleibt`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { puts, beantwortet } = zaehlePuts(page, pfad);
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const neuerPool = await poolEintrag(editor, ws.pool[0]);

				// GIVEN: Seite geladen, danach ändert ein anderes Gerät den Namen (ohne If-Match)
				const vorher = await stand(page, kind, hub.id);
				const fremderName = `${vorher.name} (fremd)`;
				const fremd = await page.request.put(pfad, { data: { name: fremderName } });
				expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

				// WHEN: erste eigene Änderung auf dem jetzt veralteten Stand
				await neuerPool.click();
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
				expect(Object.keys(puts[1].postDataJSON() as Stand).sort(), 'der Wiederholungs-PUT trägt nur Eigenfelder').toEqual(
					ws.rumpfSchluessel
				);

				const s = await stand(page, kind, hub.id);
				expect(korridore(s).length, 'der Wiederholungs-PUT muss die Änderung tragen').toBe(2);
				expect(s.name, '„Nochmal speichern" darf den fremd gespeicherten Namen nicht überschreiben (#2375)').toBe(
					fremderName
				);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-5 (Alt AC-6) — fängt: flush() vor dem Statuswechsel entfernt.
		test(`WS-5 (${kind}): Pausieren direkt nach Wertebereich-Änderung → Wertebereich-Schreibvorgang zuerst, beide Werte bleiben`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const { alle, fertig } = protokolliereSchreiber(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await (await poolEintrag(editor, ws.pool[0])).click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(2, { timeout: 5_000 });
				// sofort (innerhalb der Entprellung) über den Kopf-Kebab pausieren
				await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
				const pausieren = page.getByRole('menuitem', { name: 'Pausieren' });
				await expect(pausieren, 'Vorbedingung: der Hub bietet „Pausieren" an').toBeVisible();
				await pausieren.click();

				await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const [erster, zweiter] = alle.map((r) => r.postDataJSON() as Stand);
				expect(alle[0].method(), 'erster Schreibvorgang ist der Wertebereich-PUT').toBe('PUT');
				expect(korridore(erster).length, 'erster Schreibvorgang muss die Wertebereich-Änderung sein').toBe(2);
				// #2375: der Wertebereiche-Rumpf trägt den Status gar nicht (Teilfeld-Nutzlast)
				for (const k of ws.statusSchluessel) {
					expect(Object.keys(erster), 'erster Schreibvorgang darf noch nicht pausieren').not.toContain(k);
				}
				expect(ws.statusPausiert(zweiter), 'zweiter Schreibvorgang pausiert').toBe(true);
				// #2375 (AC-6/AC-9): der Pausieren-Rumpf trägt NUR den Status.
				expect(Object.keys(zweiter).sort(), `Pausieren-Rumpf trägt nur { ${ws.statusSchluessel.join(', ')} }`).toEqual(
					ws.statusSchluessel
				);

				const s = await stand(page, kind, hub.id);
				expect(ws.istPausiert(s), 'Server: pausiert').toBe(true);
				expect(korridore(s).length).toBe(2);
				expect(alle.length).toBe(2);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-7 (Alt AC-11) — fängt: Teil-Nutzlast / fehlendes Bestandsfeld im PUT.
		test(`WS-7 (${kind}): Korridor ändern → alle übrigen Einstellungen bleiben unverändert`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = await stand(page, kind, hub.id);
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await (await poolEintrag(editor, ws.pool[0])).click();
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const nachher = await stand(page, kind, hub.id);
				for (const key of Object.keys(vorher)) {
					if (ws.obenEigen.has(key)) continue;
					expect(nachher[key], `Feld „${key}" hat sich durch das Wertebereiche-Speichern verändert`).toEqual(vorher[key]);
				}
				const vdc = dc(vorher);
				const ndc = dc(nachher);
				for (const key of Object.keys(vdc)) {
					if (ws.dcEigen.has(key)) continue;
					expect(ndc[key], `display_config.${key} hat sich verändert`).toEqual(vdc[key]);
				}
				expect(korridore(nachher).length, 'nur der Wertebereich weicht ab').toBe(2);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-6 (Alt #2375 Test 13 / AC-8) — fängt: Leerung erreicht den Server nicht,
		// weil die Teilfeld-Nutzlast die leere Liste weglässt.
		test(`WS-6 (${kind}): #2375 Roundtrip — Korridor-Leerung → PUT trägt die Leerung → nach Neuladen leer`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await editor.locator(`[data-testid="corridor-row-${ws.zeile}"] .ce-remove`).click();
				await expect(editor.locator('[data-testid^="corridor-row-"]')).toHaveCount(0, { timeout: 5_000 });
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const rumpf = puts.at(-1)!.postDataJSON() as Stand;
				// Trip: { corridors: [] }; Vergleich zusätzlich display_config.ideal_ranges {}.
				expect(rumpf, 'Leerung muss als [] (bzw. {} für ideal_ranges) gesendet werden').toMatchObject(ws.leerRumpf);
				expect(rumpf.corridors, 'Leerung muss als [] gesendet werden').toEqual([]);

				const s = await stand(page, kind, hub.id);
				expect(korridore(s).length, 'die Korridor-Leerung hat den Server nicht erreicht').toBe(0);
				expect(Object.keys((dc(s).ideal_ranges as object) ?? {}), 'die Ideal-Ranges wurden nicht geleert').toEqual([]);

				await openHub(page, kind, hub.id, { tab: 'wertebereiche' });
				const neu = page.locator(`[data-testid="corridor-editor-${kind}"]:visible`);
				await expect(neu).toBeVisible({ timeout: 10_000 });
				await expect(neu.locator('[data-testid^="corridor-row-"]'), 'nach Neuladen muss die Leerung stehen').toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
