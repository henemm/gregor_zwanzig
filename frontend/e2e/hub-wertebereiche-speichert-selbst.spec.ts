// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Wertebereiche"
// (geteilter CorridorEditor) — EINE Zusicherung für BEIDE Hubs (Trip und
// Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-3 (WS-1..WS-8)
//
// Issue #2792 S1c-3 (docs/specs/modules/feat_2792_s1_profil_ampel.md AC-22,
// AC-24, Nachtrag v1.3, PO-Entscheidung E2): die Korridor-Zeilen sind bis S3a
// NUR LESBAR. Der frühere Speicherweg des Reiters (ein PUT je Bedienfolge,
// Flush vor Reiterwechsel/Pausieren, 412 → „Nochmal speichern", Leerung) ist
// damit bewusst nicht mehr erreichbar. Die Fälle WS-1..WS-8 bleiben je Geste
// bestehen und sichern jetzt das neue Soll: der Hinweis steht oben im Reiter,
// die Bedienelemente sind gesperrt, ein Bedienversuch (auch erzwungener Klick
// bzw. Ziehen am Griff — der Griff ist ein div ohne `disabled`, dort greift
// allein der No-op-Wächter in `patch()`) sendet KEINEN PUT, und `corridors`
// (Vergleich zusätzlich `ideal_ranges`/`active_metrics`) bleiben auf dem
// Server unverändert. Wo der Altfall eine zweite, weiterhin erlaubte Schreib-
// geste hatte (WS-3 Alarm, WS-4 fremder Name, WS-5 Pausieren), bleibt sie als
// Gegenprobe erhalten. Den Konfliktschutz (412) bewacht hub-konfliktschutz-
// zwei-kontexte.spec.ts über die weiterhin bearbeitbaren Reiter.
//
// Kein fester Schlaf: „kein PUT" per Stabilitätsfenster (≥ alte 1,2-s-Nachfrist,
// deutlich über dem 700-ms-Entprell-Fenster).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
const dc = (body: Stand) => (body.display_config as Stand | undefined) ?? {};

/** Wortlaut aus AC-22 (Katalogschlüssel `wertebereiche.gesperrt.hinweis_reiter`). */
const HINWEIS_DE = 'Wird gerade umgebaut – deine Werte sind übernommen.';

/** kind-Tabelle: Seed-Zeile, Pool-Metriken, Alarm-Auslöser, Status-Weg. */
const WS_SEL: Record<
	HubKind,
	{
		zeile: string;
		/** Von-Wert der Seed-Zeile (Anzeige im ersten Zahlenfeld). */
		von: string;
		seed: Record<string, unknown>;
		/** zwei Pool-Metriken (Startzustand: nicht in den Zeilen). */
		pool: [string, string];
		/** Ausschnitt, den der gesperrte Reiter NIE verändern darf (AC-24). */
		altfelder: (s: Stand) => Record<string, unknown>;
		/** Gegenprobe im Alarme-Reiter (WS-3). */
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
		von: '30',
		seed: {
			official_warnings: { enabled: true },
			corridors: [{ metric: 'wind_gust', range: [30, 70], notify: false, mark: false }]
		},
		pool: ['precipitation_sum', 'temperature_max'],
		altfelder: (s) => ({ corridors: s.corridors }),
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
		von: '30',
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
		altfelder: (s) => ({
			corridors: s.corridors,
			ideal_ranges: dc(s).ideal_ranges,
			active_metrics: dc(s).active_metrics
		}),
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
const zeilen = (editor: Locator) => editor.locator('[data-testid^="corridor-row-"]');

/** Öffnet den Reiter und prüft den Sperr-Hinweis (AC-22) samt sichtbarer Seed-Zeile. */
async function oeffneWertebereiche(page: Page, kind: HubKind, id: string): Promise<Locator> {
	// #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): Wertebereiche stehen im Reiter Wetter.
	await openHub(page, kind, id, { tab: 'wetter' });
	// HubKind == context-Parameter des geteilten Korridor-Editors.
	const editor = page.locator(`[data-testid="corridor-editor-${kind}"]:visible`);
	await expect(editor).toBeVisible({ timeout: 10_000 });
	await expect(editor.locator(`[data-testid="corridor-row-${WS_SEL[kind].zeile}"]`)).toBeVisible({ timeout: 10_000 });
	await expect(
		editor.locator('[data-testid="corridor-editor-gesperrt"]'),
		'AC-22: der Sperr-Hinweis steht oben im Abschnitt Wertebereiche'
	).toHaveText(HINWEIS_DE);
	return editor;
}

/** Pool-Eintrag per Namen: sichtbar, aber gesperrt (AC-22). */
async function gesperrterPoolEintrag(editor: Locator, metric: string): Promise<Locator> {
	const btn = editor.locator(`[data-testid="corridor-editor-pool-item-${metric}"]`);
	await expect(btn, `Vorbedingung: Pool zeigt ${metric}`).toBeVisible({ timeout: 10_000 });
	await expect(btn, `AC-22: „＋ ${metric}" ist gesperrt`).toBeDisabled();
	return btn;
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ws = WS_SEL[kind];

	test.describe(`Hub · Wertebereiche ist gesperrt und schreibt nichts (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// WS-1 — fängt: Hinzufügen-Knopf wieder bedienbar bzw. add() ohne No-op-Wächter.
		test(`WS-1 (${kind}): zwei Metriken hinzufügen versuchen → Knöpfe gesperrt, keine neue Zeile, KEIN PUT, Wertebereiche unverändert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = ws.altfelder(await stand(page, kind, hub.id));
				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);
				const [a, b] = [await gesperrterPoolEintrag(editor, ws.pool[0]), await gesperrterPoolEintrag(editor, ws.pool[1])];

				// erzwungener Klick: der Browser stellt auf gesperrten Knöpfen keinen Klick zu
				await a.click({ force: true });
				await b.click({ force: true });

				await bleibtBei(() => puts.length, 0, 1_200, 'WS-1: ein gesperrter Pool-Eintrag darf keinen PUT auslösen');
				await expect(zeilen(editor), 'WS-1: es darf keine neue Zeile entstehen').toHaveCount(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle');
				expect(ws.altfelder(await stand(page, kind, hub.id)), 'AC-24: Wertebereiche auf dem Server unverändert').toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-2 — fängt: patch() ohne No-op-Wächter. Der Griff ist ein div ohne
		// `disabled`, die Ziehgeste erreicht also patch() — nur der Wächter hält sie auf.
		test(`WS-2 (${kind}): Regler ziehen, Maus über dem Reiterkopf loslassen → Wert bleibt, KEIN PUT, überlebt Neuladen`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = ws.altfelder(await stand(page, kind, hub.id));
				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const row = editor.locator(`[data-testid="corridor-row-${ws.zeile}"]`);
				const vonFeld = row.locator('input[type="number"]').first();
				await expect(vonFeld).toHaveValue(ws.von);
				await expect(vonFeld, 'AC-22: das Zahlenfeld ist gesperrt').toBeDisabled();
				// #2794 S3a: der Editor steht unter der Metrik-Auswahl im Reiter Wetter — erst ins Bild holen.
				await row.scrollIntoViewIfNeeded();
				const handle = await row.locator('.ce-handle').first().boundingBox();
				const kopf = await page.locator(`[data-testid="${sel.reiter}-uebersicht"]:visible`).boundingBox();
				expect(handle, 'Vorbedingung: der Von-Griff ist sichtbar').not.toBeNull();
				expect(kopf).not.toBeNull();

				await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2);
				await page.mouse.down();
				await page.mouse.move(handle!.x + 50, handle!.y - 20, { steps: 8 });
				await page.mouse.move(kopf!.x + kopf!.width / 2, kopf!.y + kopf!.height / 2, { steps: 15 });
				await page.mouse.up();

				await bleibtBei(() => puts.length, 0, 1_200, 'WS-2: die Ziehgeste am gesperrten Regler darf keinen PUT auslösen');
				await expect(vonFeld, 'WS-2: der Regler darf sich nicht bewegt haben').toHaveValue(ws.von);
				expect(ws.altfelder(await stand(page, kind, hub.id)), 'AC-24: Wertebereiche auf dem Server unverändert').toEqual(vorher);

				const neu = await oeffneWertebereiche(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${ws.zeile}"] input[type="number"]`).first()
				).toHaveValue(ws.von, { timeout: 5_000 });
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-3 — Gegenprobe: der gesperrte Reiter hält den Reiterwechsel nicht auf,
		// die Alarm-Änderung danach wird genau einmal gespeichert, Wertebereiche bleiben.
		test(`WS-3 (${kind}): Wertebereich ändern versuchen, sofort zu „Alarme", dort Alarm ändern → genau EIN PUT (Alarm), Wertebereiche unverändert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = ws.altfelder(await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await (await gesperrterPoolEintrag(editor, ws.pool[0])).click({ force: true });
				// #2794 S3a: die Alarme stehen im Reiter Zustellung.
				await page.locator(`[data-testid="${sel.reiter}-zustellung"]:visible`).click();
				await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
				expect(puts.length, 'WS-3: der Reiterwechsel darf aus dem gesperrten Reiter nichts senden').toBe(0);

				await ws.alarm(page).click();
				await expect(ws.alarm(page)).toBeChecked({ checked: ws.alarmNeu });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtBei(() => puts.length, 1, 1_200, 'WS-3: genau EIN PUT — der der Alarm-Änderung');

				expect(ws.alarmWert(puts[0].postDataJSON() as Stand), 'der eine PUT trägt die Alarm-Änderung').toBe(ws.alarmNeu);
				const s = await stand(page, kind, hub.id);
				expect(ws.alarmWert(s)).toBe(ws.alarmNeu);
				expect(ws.altfelder(s), 'AC-24: Wertebereiche auf dem Server unverändert').toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-4 — Gegenprobe zum fremden Schreibvorgang: der gesperrte Reiter sendet
		// nichts, also gibt es weder einen Konflikt noch ein Überschreiben des fremden Namens.
		test(`WS-4 (${kind}): fremde Änderung dazwischen, dann Wertebereich ändern versuchen → KEIN PUT, kein Konflikt, fremder Name bleibt`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { puts } = zaehlePuts(page, pfad);
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const neuerPool = await gesperrterPoolEintrag(editor, ws.pool[0]);

				// GIVEN: Seite geladen, danach ändert ein anderes Gerät den Namen (ohne If-Match)
				const vorher = await stand(page, kind, hub.id);
				const fremderName = `${vorher.name} (fremd)`;
				const fremd = await page.request.put(pfad, { data: { name: fremderName } });
				expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

				// WHEN: Bedienversuch auf dem jetzt veralteten Stand
				await neuerPool.click({ force: true });
				await editor.locator(`[data-testid="corridor-row-${ws.zeile}"] .ce-remove`).click({ force: true });

				// THEN: nichts gesendet, also auch kein 412/„Nochmal speichern"
				await bleibtBei(() => puts.length, 0, 1_200, 'WS-4: der gesperrte Reiter darf keinen PUT senden');
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle');
				await expect(anzeige(page).getByRole('button', { name: 'Nochmal speichern' })).toHaveCount(0);
				await expect(zeilen(editor)).toHaveCount(1);

				const s = await stand(page, kind, hub.id);
				expect(s.name, 'der fremd gespeicherte Name darf nicht überschrieben werden').toBe(fremderName);
				expect(ws.altfelder(s), 'AC-24: Wertebereiche auf dem Server unverändert').toEqual(ws.altfelder(vorher));
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-5 — Gegenprobe Pausieren: der gesperrte Reiter hat nichts zu flushen,
		// es gibt genau EINEN Schreibvorgang, und der trägt nur den Status.
		test(`WS-5 (${kind}): Pausieren direkt nach Bedienversuch im Wertebereich → genau EIN Schreibvorgang (nur Status), Wertebereiche bleiben`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = ws.altfelder(await stand(page, kind, hub.id));
				const { alle, fertig } = protokolliereSchreiber(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				await (await gesperrterPoolEintrag(editor, ws.pool[0])).click({ force: true });
				// sofort (innerhalb des früheren Entprell-Fensters) über den Kopf-Kebab pausieren
				await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
				const pausieren = page.getByRole('menuitem', { name: 'Pausieren' });
				await expect(pausieren, 'Vorbedingung: der Hub bietet „Pausieren" an').toBeVisible();
				await pausieren.click();

				await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtBei(() => alle.length, 1, 1_200, 'WS-5: genau EIN Schreibvorgang — der Status');

				const rumpf = alle[0].postDataJSON() as Stand;
				expect(ws.statusPausiert(rumpf), 'der Schreibvorgang pausiert').toBe(true);
				expect(Object.keys(rumpf).sort(), `Pausieren-Rumpf trägt nur { ${ws.statusSchluessel.join(', ')} }`).toEqual(
					ws.statusSchluessel
				);

				const s = await stand(page, kind, hub.id);
				expect(ws.istPausiert(s), 'Server: pausiert').toBe(true);
				expect(ws.altfelder(s), 'AC-24: Wertebereiche auf dem Server unverändert').toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-8 — fängt: Markieren-Knopf wieder bedienbar; „Warnen" zurück in der Zeile (#1371).
		test(`WS-8 (${kind}): „Markieren" umlegen versuchen → gesperrt, mark unverändert, KEIN PUT, überlebt Neuladen; kein „Warnen"`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const zeileId = ws.zeile;
				const markVorher = ((await stand(page, kind, hub.id)).corridors as Array<{ metric: string; mark?: boolean }>).find(
					(k) => k.metric === zeileId
				);
				expect(markVorher, `Vorbedingung: der Seed trägt die Zeile ${zeileId}`).toBeDefined();
				const startMark = markVorher?.mark === true;

				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const zeile = editor.locator(`[data-testid="corridor-row-${zeileId}"]`);
				const markieren = zeile.getByRole('button', { name: 'Markieren' });
				const entfernen = zeile.getByRole('button', { name: '✕ entfernen' });

				// #1371: kein „Warnen"-Bedienelement; „Markieren" und „✕ entfernen" sind da — gesperrt.
				await expect(zeile.getByRole('button', { name: 'Warnen' }), 'WS-8 FAIL: „Warnen" ist wieder in der Zeile (#1371)').toHaveCount(0);
				await expect(markieren).toBeVisible();
				await expect(markieren, 'AC-22: „Markieren" ist gesperrt').toBeDisabled();
				await expect(entfernen).toBeVisible();
				await expect(entfernen, 'AC-22: „✕ entfernen" ist gesperrt').toBeDisabled();
				await expect(markieren, 'AC-22: der gespeicherte Wert wird angezeigt').toHaveAttribute('aria-pressed', String(startMark));

				await markieren.click({ force: true });
				await bleibtBei(() => puts.length, 0, 1_200, 'WS-8: der gesperrte Markieren-Knopf darf keinen PUT auslösen');
				await expect(markieren, 'WS-8: der Markieren-Wert darf sich nicht ändern').toHaveAttribute('aria-pressed', String(startMark));

				const markNachher = ((await stand(page, kind, hub.id)).corridors as Array<{ metric: string; mark?: boolean }>).find(
					(k) => k.metric === zeileId
				);
				expect(markNachher?.mark === true, 'AC-24: mark auf dem Server unverändert').toBe(startMark);

				const neu = await oeffneWertebereiche(page, kind, hub.id);
				await expect(
					neu.locator(`[data-testid="corridor-row-${zeileId}"]`).getByRole('button', { name: 'Markieren' })
				).toHaveAttribute('aria-pressed', String(startMark));
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-7 — fängt: irgendein Feld (auch `corridors`) ändert sich durch bloße
		// Bedienversuche im gesperrten Reiter. Strenger als der Altfall: auch die
		// Wertebereiche selbst gehören jetzt zu den unveränderten Feldern.
		test(`WS-7 (${kind}): Bedienversuche im gesperrten Reiter → alle Einstellungen bleiben unverändert, auch die Wertebereiche`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = await stand(page, kind, hub.id);
				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);
				const zeile = editor.locator(`[data-testid="corridor-row-${ws.zeile}"]`);

				await (await gesperrterPoolEintrag(editor, ws.pool[0])).click({ force: true });
				await zeile.getByRole('button', { name: 'Markieren' }).click({ force: true });
				await zeile.locator('.ce-clear-btn').first().click({ force: true });
				await zeile.locator('.ce-remove').click({ force: true });
				await bleibtBei(() => puts.length, 0, 1_200, 'WS-7: kein Bedienversuch darf einen PUT auslösen');

				const nachher = await stand(page, kind, hub.id);
				for (const key of Object.keys(vorher)) {
					if (key === 'updated_at' || key === 'etag') continue;
					expect(nachher[key], `Feld „${key}" hat sich im gesperrten Reiter verändert`).toEqual(vorher[key]);
				}
				const vdc = dc(vorher);
				const ndc = dc(nachher);
				for (const key of Object.keys(vdc)) {
					expect(ndc[key], `display_config.${key} hat sich verändert`).toEqual(vdc[key]);
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-6 — fängt: „✕ entfernen" wieder bedienbar bzw. remove() ohne No-op-Wächter
		// (die Leerung erreichte sonst den Server, AC-24 „nie leeren").
		test(`WS-6 (${kind}): Korridor leeren versuchen → „✕ entfernen" gesperrt, KEIN PUT, nach Neuladen steht die Zeile noch`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ws.seed });
			try {
				const vorher = ws.altfelder(await stand(page, kind, hub.id));
				const { puts } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const editor = await oeffneWertebereiche(page, kind, hub.id);

				const entfernen = editor.locator(`[data-testid="corridor-row-${ws.zeile}"] .ce-remove`);
				await expect(entfernen, 'AC-22: „✕ entfernen" ist gesperrt').toBeDisabled();
				await entfernen.click({ force: true });
				await bleibtBei(() => puts.length, 0, 1_200, 'WS-6: die Leerung darf keinen PUT auslösen');
				await expect(zeilen(editor), 'WS-6: die Zeile darf nicht verschwinden').toHaveCount(1);

				const s = await stand(page, kind, hub.id);
				expect(ws.altfelder(s), 'AC-24: Wertebereiche auf dem Server unverändert (nie geleert)').toEqual(vorher);

				await openHub(page, kind, hub.id, { tab: 'wetter' });
				const neu = page.locator(`[data-testid="corridor-editor-${kind}"]:visible`);
				await expect(neu).toBeVisible({ timeout: 10_000 });
				await expect(neu.locator(`[data-testid="corridor-row-${ws.zeile}"]`), 'nach Neuladen steht die Zeile noch').toBeVisible({
					timeout: 10_000
				});
				await expect(zeilen(neu)).toHaveCount(1);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
