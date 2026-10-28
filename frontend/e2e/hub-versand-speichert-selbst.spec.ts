// E2E — Issue #2347 S3b (Epic #2345, Etappe P6): der Versand-Abschnitt
// (Reiter „Wetter-Metriken", `#versand`) speichert SELBST — EINE Zusicherung für
// BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md § AC-1, AC-2, AC-9 (VS-1..VS-8)
//
// Ersetzt compare-versand-speichert-selbst.spec.ts (#2276 S5, nur Vergleich) und
// Teile von compare-hub-versand-inline / versand-tab-vergleich / compare-editor-autosave:
//   AC-4 Uhrzeit + Reiterwechsel + Alarm          → VS-1 (je kind)
//   AC-6 412 → „Nochmal speichern"                 → VS-2 (je kind)
//   AC-7 Uhrzeit + sofort pausieren (Karte)        → VS-3 Kebab (je kind) + VS-3k Karte (vergleich)
//   AC-11 übrige Einstellungen bleiben             → VS-4 (je kind)
//   editor-autosave AC-6 (Versand-Hälfte)          → VS-5 (je kind)
//   — Laufzeit-Kontrast (Trip schreibgeschützt)    → VS-6 (route)
//   AC-5 + inline F001 + vergleich AC-3            → VS-7 (vergleich, strengste Fassung)
//   versand-tab-vergleich AC-3b                    → VS-8 (vergleich)
//
// Speicherweg je kind: der Trip schreibt `{report_config: …}` per PUT auf
// `/api/trips/{id}` (BriefingScheduleTab → baueTripSpeicherung), der Vergleich
// schreibt die Versandfelder per PUT auf `/api/compare/presets/{id}`
// (versandVergleichSpeicherung.ts). Pausieren je kind (Spec „Frage 3"): Trip per
// PATCH `/api/trips/{id}/state` `{paused}` (setPaused), Vergleich per PUT
// `{schedule, previous_schedule}` (buildToggleActivePutPayload, #2375).
//
// Wartebedingungen nur expect.poll / toHaveAttribute / waitForResponse — kein
// fester Schlaf; „genau N PUTs" als Stabilitätsfenster (Muster hub-versand-autosave-chip).
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
const rc = (s: Stand) => (s.report_config as Stand | undefined) ?? {};
const dc = (s: Stand) => (s.display_config as Stand | undefined) ?? {};

/** Datum relativ zu heute (YYYY-MM-DD) — kein festes Kalenderdatum (Spec VS-8). */
const inTagen = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);

// Versand-Schlüssel des Trip-Versand-Rumpfs (pickEigenfelder.ts VERSAND_REPORT_KEYS):
// nur diese dürfen in report_config beim Versand-Speichern NEU hinzukommen (VS-4).
const VERSAND_REPORT_KEYS = new Set([
	'enabled',
	'morning_enabled',
	'evening_enabled',
	'morning_time',
	'evening_time',
	'multi_day_trend_morning',
	'multi_day_trend_evening',
	'multi_day_trend_reports',
	'send_email',
	'send_telegram',
	'send_sms',
	'send_premium_sms',
	'telegram_style'
]);

/** kind-Tabelle (Spec „Kind-Kontraste": Feldpfad, Alarm-Auslöser, Pausier-Übertragungsweg). */
const VS_SEL: Record<
	HubKind,
	{
		/** Versandfeld im gespeicherten Stand bzw. im Versand-Rumpf. */
		morgen: (s: Stand) => unknown;
		abendAn: (s: Stand) => unknown;
		/** Alarm-Auslöser im Reiter „Alarme" (Auslöser-Tabelle hub-alarme-speichert-selbst). */
		alarmSeed: Record<string, unknown>;
		alarm: (page: Page) => Locator;
		alarmWert: (s: Stand) => unknown;
		alarmNeu: boolean;
		/** Status-Rumpf beim Pausieren (sortierte Schlüssel) und Pausiert-Prüfung. */
		statusMethode: 'PATCH' | 'PUT';
		statusSchluessel: string[];
		statusPausiert: (rumpf: Stand) => boolean;
		istPausiert: (s: Stand) => boolean;
	}
> = {
	route: {
		morgen: (s) => rc(s).morning_time,
		abendAn: (s) => rc(s).evening_enabled,
		alarmSeed: { official_warnings: { enabled: true } },
		alarm: (page) =>
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled,
		alarmNeu: false,
		statusMethode: 'PATCH',
		statusSchluessel: ['paused'],
		statusPausiert: (r) => r.paused === true,
		istPausiert: (s) => Boolean(s.paused_at)
	},
	vergleich: {
		morgen: (s) => s.morning_time,
		abendAn: (s) => s.evening_enabled,
		alarmSeed: { radar_alert_enabled: false },
		alarm: (page) => page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => s.radar_alert_enabled,
		alarmNeu: true,
		statusMethode: 'PUT',
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

/** Geordnetes Protokoll ALLER Schreibvorgänge auf das Objekt: PUT auf das Objekt
 *  ODER PATCH auf seinen Status-Unterpfad (Trip-Pausieren). */
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
const abschnitt = (page: Page) => page.locator('[data-testid="versand-abschnitt"]:visible');
const morgenUhrzeit = (page: Page) => abschnitt(page).locator('[data-testid="report-morning-time"]:visible');

async function oeffneVersand(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'wetter-metriken', hash: 'versand' });
	await expect(abschnitt(page)).toBeVisible({ timeout: 10_000 });
	await expect(morgenUhrzeit(page)).toBeVisible({ timeout: 10_000 });
}

async function kebabWaehle(page: Page, punkt: 'Pausieren' | 'Fortsetzen'): Promise<void> {
	await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
	const eintrag = page.getByRole('menuitem', { name: punkt });
	await expect(eintrag, `Vorbedingung: der Hub bietet „${punkt}" an`).toBeVisible();
	await eintrag.click();
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const vs = VS_SEL[kind];

	test.describe(`Hub · Versand speichert selbst (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// VS-1 (Alt AC-4) — fängt: Flush beim Reiterwechsel fehlt ⇒ der Alarm-Vorgang
		// verdrängt die Versand-Änderung vom einen Speicher-Platz.
		test(`VS-1 (${kind}): Uhrzeit ändern, sofort zu „Alarme", dort Alarm ändern → BEIDE Änderungen gespeichert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: vs.alarmSeed });
			try {
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneVersand(page, kind, hub.id);

				await morgenUhrzeit(page).selectOption('09:00');
				// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
				await page.locator(`[data-testid="${sel.reiter}-alarme"]:visible`).click();
				await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
				expect(beantwortet.length, 'die Versand-Änderung war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);
				expect(String(vs.morgen(beantwortet[0].postDataJSON() as Stand)), 'der erste PUT trägt die Versand-Änderung').toMatch(
					/^09:00/
				);

				await expect(vs.alarm(page), 'Vorbedingung: Alarm-Auslöser steht auf dem Gegenwert').toBeChecked({
					checked: !vs.alarmNeu
				});
				await vs.alarm(page).click();
				await expect(vs.alarm(page)).toBeChecked({ checked: vs.alarmNeu });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const s = await stand(page, kind, hub.id);
				expect(String(vs.morgen(s)), 'die Versand-Änderung ging beim Reiterwechsel verloren').toMatch(/^09:00/);
				expect(vs.alarmWert(s)).toBe(vs.alarmNeu);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VS-2 (Alt AC-6) — fängt: 412 als generischer Fehler (setError statt
		// conflict) bzw. Rücknahme der Oberfläche bei 412. Der Fall speichert ZUERST
		// selbst (die Seite kennt danach den ETag, #2375), dann der Fremdschreiber.
		test(`VS-2 (${kind}): fremde Änderung dazwischen → echter 412, „Nochmal speichern" → gespeichert, Wert bleibt`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { puts, beantwortet } = zaehlePuts(page, pfad);
				await oeffneVersand(page, kind, hub.id);

				// GIVEN: eigene erste Änderung gespeichert
				await morgenUhrzeit(page).selectOption('08:00');
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				// An der Oberfläche vorbei: fremde Änderung ohne If-Match (anderes Gerät)
				const vorher = await stand(page, kind, hub.id);
				const fremderName = `${vorher.name} (fremd)`;
				const fremd = await page.request.put(pfad, { data: { ...vorher, name: fremderName } });
				expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

				// WHEN: zweite Versand-Änderung auf dem jetzt veralteten Stand
				await morgenUhrzeit(page).selectOption('09:00');

				// THEN: echter 412 → „Nochmal speichern", keine Rücknahme in der Oberfläche
				await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
				expect(puts.length, 'Vorbedingung: der zweite PUT wurde gesendet').toBe(2);
				expect((await puts[1].response())?.status(), 'der Server muss den veralteten Stand ablehnen').toBe(412);
				await expect(morgenUhrzeit(page), 'bei 412 darf die Oberfläche nicht zurückspringen').toHaveValue('09:00');
				const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
				await expect(nochmal).toBeVisible();

				// WHEN: „Nochmal speichern" → THEN: gespeichert, Wert bleibt sichtbar und auf dem Server
				await nochmal.click();
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect(anzeige(page)).toContainText('Gespeichert');
				await expect.poll(() => puts.length, { timeout: 10_000, message: 'der Wiederholungs-PUT wurde gesendet' }).toBe(3);
				expect((await puts[2].response())?.status(), 'der Wiederholungs-PUT muss durchgehen').toBe(200);
				await expect(morgenUhrzeit(page)).toHaveValue('09:00');

				const s = await stand(page, kind, hub.id);
				expect(String(vs.morgen(s)), 'der Wiederholungs-PUT muss die Änderung tragen').toMatch(/^09:00/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VS-3 (Alt AC-7, Einstiegspunkt Kebab) — fängt: der Flush vor dem
		// Statuswechsel fehlt (Trip: tripSaveCtl.flush() in sendStateUpdate; Vergleich:
		// saveController.flush() in handleToggleActive über toggleActiveFromParent).
		test(`VS-3 (${kind}): Uhrzeit ändern und sofort über den Kebab pausieren → Feld-Schreibvorgang VOR dem Status, beide im Server-Stand`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { alle, fertig } = protokolliereSchreiber(page, pfad);
				await oeffneVersand(page, kind, hub.id);

				// Kein Warten zwischen den beiden Aktionen — die Änderung steht noch im
				// Entprell-Fenster, wenn der Status-Schreibvorgang losgeht.
				await morgenUhrzeit(page).selectOption('10:00');
				await kebabWaehle(page, 'Pausieren');

				await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const [feld, status] = alle;
				expect(feld.method(), 'erster Schreibvorgang ist der Versand-PUT').toBe('PUT');
				expect(String(vs.morgen(feld.postDataJSON() as Stand)), 'erster Schreibvorgang trägt die neue Uhrzeit').toMatch(/^10:00/);
				expect(status.method(), `Status-Schreibweg des kind: ${vs.statusMethode}`).toBe(vs.statusMethode);
				const statusRumpf = status.postDataJSON() as Stand;
				expect(vs.statusPausiert(statusRumpf), 'zweiter Schreibvorgang pausiert').toBe(true);
				expect(Object.keys(statusRumpf).sort(), `Status-Rumpf trägt nur { ${vs.statusSchluessel.join(', ')} }`).toEqual(
					vs.statusSchluessel
				);

				const s = await stand(page, kind, hub.id);
				expect(vs.istPausiert(s), 'Server: pausiert').toBe(true);
				expect(String(vs.morgen(s)), 'das Pausieren hat die ausstehende Versand-Änderung überschrieben').toMatch(/^10:00/);
				expect(alle.length).toBe(2);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VS-3k (Alt AC-7, Einstiegspunkt Aktivierungs-Karte) — nur vergleich: die
		// Karte `compare-hub-activation-card` ist Slot von VersandTab nur im
		// Vergleich-Hub (CompareTabs.svelte hubActivationCard) und läuft über
		// `handleToggleActive` direkt, nicht über den Kebab (Spec „Kind-Kontraste",
		// Zeile Pausieren). Der Trip-Hub hat keine Karte; sein Pausieren ist VS-3.
		if (kind === 'vergleich') {
			test(`VS-3k (${kind}): Uhrzeit ändern und sofort über die Aktivierungs-Karte pausieren → die Änderung ist im gespeicherten Stand`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind);
				try {
					const { alle, fertig } = protokolliereSchreiber(page, hubApiPath(kind, hub.id));
					await oeffneVersand(page, kind, hub.id);
					const cta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
					await expect(cta).toHaveText('Pausieren');

					await morgenUhrzeit(page).selectOption('10:00');
					await cta.click();

					await expect(cta).toHaveText('Aktivieren', { timeout: 10_000 });
					await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
					await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					expect(String(vs.morgen(alle[0].postDataJSON() as Stand)), 'der Feld-PUT geht VOR dem Pausier-PUT').toMatch(/^10:00/);
					expect(vs.statusPausiert(alle[1].postDataJSON() as Stand)).toBe(true);

					const s = await stand(page, kind, hub.id);
					expect(vs.istPausiert(s), 'Vorbedingung: der Vergleich ist pausiert').toBe(true);
					expect(String(vs.morgen(s)), 'der Pausier-PUT hat die ausstehende Versand-Änderung überschrieben').toMatch(/^10:00/);
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// VS-4 (Alt AC-11) — fängt: Teil-Nutzlast bzw. fehlendes Bestandsfeld im
		// Versand-PUT (Legacy-Alarmfelder, Wertebereiche, Etappen, Name).
		test(`VS-4 (${kind}): Uhrzeit ändern → alle übrigen Einstellungen bleiben nach dem Neuladen unverändert`, async ({ page }) => {
			// Seed je kind mit Nicht-Startwerten (Datenmodell unterscheidet sich, Spec
			// „Kind-Kontraste" Feldpfad): Vergleich wie die Alt-Spec (Legacy-Restfelder,
			// Wertebereiche, Region, Kurzstil, Enddatum); Trip mit vollständigem
			// report_config (seedHub ersetzt flach) samt Nicht-Versand-Schlüsseln,
			// Alarm-Feldern und Etappen aus dem Seed.
			const extra: Record<string, unknown> =
				kind === 'vergleich'
					? {
							official_alerts_enabled: true,
							radar_alert_enabled: false,
							send_telegram: true,
							send_sms: false,
							end_date: inTagen(60),
							alert_cooldown_minutes: 45,
							alert_quiet_from: '22:00',
							alert_quiet_to: '07:00',
							corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
							display_config: {
								region: 'Tirol',
								ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
								active_metrics: ['snow_depth_cm'],
								telegram_style: 'kurzform'
							}
						}
					: {
							official_alerts_enabled: true,
							official_warnings: { enabled: true },
							alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
							region: 'Korsika',
							report_config: {
								enabled: true,
								morning_enabled: true,
								evening_enabled: false,
								morning_time: '06:00:00',
								evening_time: '18:00:00',
								show_outlook: false,
								email_format: 'compact'
							},
							display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] }
						};
			const hub = await seedHub(page.request, kind, { extra });
			try {
				const vorher = await stand(page, kind, hub.id);
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneVersand(page, kind, hub.id);

				await morgenUhrzeit(page).selectOption('08:00');
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const nachher = await stand(page, kind, hub.id);
				expect(String(vs.morgen(nachher)), 'nur die Uhrzeit weicht ab').toMatch(/^08:00/);
				if (kind === 'vergleich') {
					// Vergleich (Alt AC-11 1:1): Legacy-Restfelder ausdrücklich, dann jedes
					// Oberfeld außer morning_time/display_config/updated_at/etag.
					expect(nachher.alert_cooldown_minutes, 'der Versand-PUT hat den Cooldown genullt').toBe(45);
					expect(nachher.alert_quiet_from, 'der Versand-PUT hat die Stillen Stunden genullt').toBe('22:00');
					expect(nachher.alert_quiet_to, 'der Versand-PUT hat die Stillen Stunden genullt').toBe('07:00');
					const OBEN = new Set(['morning_time', 'display_config', 'updated_at', 'etag']);
					for (const key of Object.keys(vorher)) {
						if (OBEN.has(key)) continue;
						expect(nachher[key], `Feld „${key}" hat sich durch das Versand-Speichern verändert`).toEqual(vorher[key]);
					}
					const vdc = dc(vorher);
					const ndc = dc(nachher);
					expect(ndc.region, 'die Region darf beim Versand-Speichern nicht leer werden').toEqual(vdc.region);
					expect(ndc.ideal_ranges, 'die Wertebereiche dürfen nicht verloren gehen').toEqual(vdc.ideal_ranges);
					expect(ndc.telegram_style, 'der Kurzstil darf nicht verloren gehen').toEqual(vdc.telegram_style);
					expect((ndc.active_metrics as unknown[])?.length, 'die Metrik-Auswahl darf nicht leer werden').toBe(
						(vdc.active_metrics as unknown[]).length
					);
				} else {
					// Trip (Feldpfad report_config, Spec VS-4): jedes Oberfeld außer
					// report_config/updated_at/etag gleich (Name, Etappen, Alarm-Felder,
					// Metriken); in report_config bleibt jeder schon gespeicherte Schlüssel
					// außer morning_time gleich, neu dürfen nur Versand-Schlüssel hinzukommen.
					// Oberstes `morning_time` ist das ABGELEITETE Flach-Feld aus report_config
					// (internal/model/trip.go, Issue #1250 S4, store.normalizeTrip) — es folgt
					// der Uhrzeit und wird darum ausdrücklich auf den neuen Wert geprüft.
					expect(String(nachher.morning_time), 'Flach-Feld folgt report_config.morning_time').toMatch(/^08:00/);
					const OBEN = new Set(['report_config', 'morning_time', 'updated_at', 'etag']);
					for (const key of Object.keys(vorher)) {
						if (OBEN.has(key)) continue;
						expect(nachher[key], `Feld „${key}" hat sich durch das Versand-Speichern verändert`).toEqual(vorher[key]);
					}
					const v = rc(vorher);
					const n = rc(nachher);
					for (const key of Object.keys(v)) {
						if (key === 'morning_time') continue;
						expect(n[key], `report_config.${key} hat sich durch das Versand-Speichern verändert`).toEqual(v[key]);
					}
					for (const key of Object.keys(n)) {
						if (key in v) continue;
						expect(VERSAND_REPORT_KEYS.has(key), `report_config.${key} ist neu hinzugekommen, gehört aber nicht dem Versand`).toBe(
							true
						);
					}
				}

				await oeffneVersand(page, kind, hub.id);
				await expect(morgenUhrzeit(page), 'die Uhrzeit überlebt das Neuladen').toHaveValue('08:00');
			} finally {
				await hub.aufraeumen();
			}
		});

		// VS-5 (Versand-Hälfte aus Alt compare-editor-autosave AC-6) — fängt:
		// Doppel-Feuer je Aktion bzw. eine zweite Aktion, die nicht gespeichert wird.
		test(`VS-5 (${kind}): zwei Versand-Aktionen nacheinander (Uhrzeit, dann Abend-Slot) → genau ZWEI PUTs, beide persistent`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind);
			try {
				const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneVersand(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Abschnitts speichert nichts').toBe(0);

				// Aktion 1: Morgen-Uhrzeit
				await morgenUhrzeit(page).selectOption('05:00');
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				// Aktion 2: Abend-Slot einschalten (Seed: aus)
				const abend = abschnitt(page).locator('[data-testid="evening-master-switch"] input[type="checkbox"]');
				await expect(abend, 'Vorbedingung: Abend-Slot ist aus').not.toBeChecked();
				await abend.click();
				await expect(abend).toBeChecked();
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				await bleibtBei(() => puts.length, 2, 1_500, 'genau ein PUT je Nutzeraktion (kein Doppel-Feuer)');

				const s = await stand(page, kind, hub.id);
				expect(String(vs.morgen(s)), 'Aktion 1 ist persistent').toMatch(/^05:00/);
				expect(vs.abendAn(s), 'Aktion 2 ist persistent').toBe(true);
			} finally {
				await hub.aufraeumen();
			}
		});

		// VS-6 — nur route: die Laufzeit des Trips ist schreibgeschützt und ergibt
		// sich aus den Etappen (VTLaufzeitRoute.svelte); das Datenmodell des
		// Vergleichs hat stattdessen ein eigenes, editierbares Enddatum (VS-7/VS-8).
		// Spec „Kind-Kontraste", Zeile Laufzeit / Enddatum.
		if (kind === 'route') {
			test(`VS-6 (${kind}): Laufzeit schreibgeschützt „endet <letztes Etappendatum>", „Etappen öffnen →" wechselt in die Etappen, kein PUT`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind);
				try {
					const pfad = hubApiPath(kind, hub.id);
					const { puts } = zaehlePuts(page, pfad);
					await oeffneVersand(page, kind, hub.id);

					const laufzeit = abschnitt(page).locator('[data-testid="briefings-laufzeit"]');
					await expect(laufzeit).toBeVisible();
					// Seed-Etappe `s1` am 2027-08-01 (helpers.seedHub) ⇒ deutsches Datum.
					await expect(laufzeit).toContainText('Läuft mit der Trip · endet 01.08.2027');
					await expect(laufzeit.locator('input')).toHaveCount(0);
					await bleibtBei(() => puts.length, 0, 1_500, 'das Öffnen des Versand-Abschnitts speichert nichts');

					await laufzeit.getByRole('button', { name: 'Etappen öffnen →' }).click();
					await expect(page.locator(`[data-testid="${sel.panel}-etappen"]`)).toBeVisible({ timeout: 10_000 });
					await expect(page).toHaveURL(sel.hubUrl(hub.id));
					await bleibtBei(() => puts.length, 0, 1_500, '„Etappen öffnen →" darf keinen PUT auslösen');
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// VS-7 / VS-8 — nur vergleich: editierbares Enddatum (`VTLaufzeitVergleich`,
		// Sentinel end_date=""). Der Trip hat kein eigenes Enddatum-Feld (VS-6).
		// Spec „Kind-Kontraste", Zeile Laufzeit / Enddatum.
		if (kind === 'vergleich') {
			// VS-7 (Alt AC-5 + inline F001 + versand-tab-vergleich AC-3, strengste
			// Fassung) — fängt: Wegfall des Wrapper-`onclick` ohne Ersatz (reiner
			// Button-Klick ohne change-/focusout-Ereignis) und `""` statt fehlend.
			test(`VS-7 (${kind}): „Bis auf Weiteres" (reiner Klick) bei gesetztem Enddatum → Sentinel "" gesendet, Enddatum fehlt im Server-Stand`, async ({
				page
			}) => {
				const enddatum = inTagen(30);
				const hub = await seedHub(page.request, kind, { extra: { end_date: enddatum } });
				try {
					const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
					await oeffneVersand(page, kind, hub.id);
					const bisDatum = abschnitt(page).locator('[data-testid="compare-versand-enddate-date"]');
					await expect(bisDatum, 'Vorbedingung: „Bis Datum" ist gewählt').toHaveAttribute('aria-selected', 'true');
					await expect(abschnitt(page).locator('[data-testid="compare-versand-enddate-input"]')).toHaveValue(enddatum);

					await abschnitt(page).locator('[data-testid="compare-versand-enddate-open"]').click();

					await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
					await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					expect((puts[0].postDataJSON() as Stand).end_date, 'Schreibrichtung ist der Lösch-Sentinel ""').toBe('');
					// Der Server normalisiert "" zu nil, `omitempty` lässt das Feld beim
					// Lesen weg — bewusst toBeUndefined(), nie toBeFalsy() (ließe '' durch).
					expect((await stand(page, kind, hub.id)).end_date, 'der reine Klick muss das Enddatum löschen').toBeUndefined();

					await oeffneVersand(page, kind, hub.id);
					await expect(abschnitt(page).locator('[data-testid="compare-versand-enddate-open"]')).toHaveAttribute(
						'aria-selected',
						'true',
						{ timeout: 10_000 }
					);
					await expect(abschnitt(page).locator('.vt-laufzeit-hint')).toContainText('ohne Enddatum');
				} finally {
					await hub.aufraeumen();
				}
			});

			// VS-8 (Alt versand-tab-vergleich AC-3b) — fängt: Datum wird nicht persistiert.
			test(`VS-8 (${kind}): „Bis Datum" + Datum setzen → Enddatum persistiert und überlebt das Neuladen`, async ({ page }) => {
				const ziel = inTagen(45);
				const hub = await seedHub(page.request, kind);
				try {
					const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
					await oeffneVersand(page, kind, hub.id);
					await expect(abschnitt(page).locator('[data-testid="compare-versand-enddate-open"]')).toHaveAttribute(
						'aria-selected',
						'true'
					);

					await abschnitt(page).locator('[data-testid="compare-versand-enddate-date"]').click();
					await abschnitt(page).locator('[data-testid="compare-versand-enddate-input"]').fill(ziel);

					await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
					await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					expect((await stand(page, kind, hub.id)).end_date).toBe(ziel);

					await oeffneVersand(page, kind, hub.id);
					await expect(abschnitt(page).locator('[data-testid="compare-versand-enddate-date"]')).toHaveAttribute(
						'aria-selected',
						'true',
						{ timeout: 10_000 }
					);
					await expect(abschnitt(page).locator('[data-testid="compare-versand-enddate-input"]')).toHaveValue(ziel);
				} finally {
					await hub.aufraeumen();
				}
			});
		}
	});
}
