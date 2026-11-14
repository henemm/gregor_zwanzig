// Gemeinsame Helfer der Playwright-Specs `s3b2795-zustellung-*.spec.ts` — Issue #2795 S3b, Teilschritt 1b
// (Neubau Reiter „Zustellung“). Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md
//
// Keine .spec.ts-Datei. Enthaelt:
//   - ZT: die testids des neuen Reiters (VERTRAG fuer die Umsetzung — der Developer setzt genau diese),
//   - Seed je Kontext (Trip `route` / Orts-Briefing `vergleich`) mit festen Zustellungs-Feldern,
//   - Lesen des gespeicherten Abo-Zustands und des Profils per API,
//   - Warten auf den naechsten Schreibvorgang des Reiters (Trip: PUT /api/trips/{id},
//     Orte: PUT /api/compare/presets/{id}).
// Daten nur Wegwerf (Praefix E2E-GZ-), kein fester Schlaf, kein networkidle, nie gegen Produktion.

import { expect, type APIRequestContext, type Locator, type Page, type Request } from '@playwright/test';
import { createTestLocation, hubApiPath, openHub, seedHub, HUB_SEL, type HubKind, type SeededHub } from './helpers';

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

export const DESKTOP = { width: 1280, height: 900 };
export const MOBIL = { width: 390, height: 844 };

export const KANAELE = ['email', 'telegram', 'sms', 'premium_sms'] as const;
export type KanalId = (typeof KANAELE)[number];

/** testids des Reiters Zustellung (gleich fuer route und vergleich). */
export const ZT = {
	tab: 'zustellung-tab', // Wurzel, traegt data-context="route"|"vergleich"
	titel: 'zustellung-titel',
	erklaer: 'zustellung-erklaer',
	// Briefing-Zeiten (Karte mit id="versand", data-abschnitt="briefing-zeiten")
	karte: (slot: 'morgen' | 'abend') => `zustellung-${slot}-karte`,
	zeit: (slot: 'morgen' | 'abend') => `zustellung-${slot}-zeit`, // molecules/UhrzeitFeld (Minuten-Granularitaet)
	zeitFehler: (slot: 'morgen' | 'abend') => `zustellung-${slot}-zeit-fehler`,
	schalter: (slot: 'morgen' | 'abend') => `zustellung-${slot}-schalter`, // role=switch, aria-checked
	unterzeile: (slot: 'morgen' | 'abend') => `zustellung-${slot}-unterzeile`,
	schnellwahl: 'zustellung-schnellwahl', // darf NICHT existieren (V11)
	// Laufzeit
	laufzeit: 'zustellung-laufzeit',
	laufzeitSatz: 'zustellung-laufzeit-satz',
	etappenOeffnen: 'zustellung-etappen-oeffnen',
	laufzeitOffen: 'zustellung-laufzeit-offen', // Segment-Option „Bis auf Weiteres“ (aria-pressed/aria-checked)
	laufzeitBisDatum: 'zustellung-laufzeit-bis-datum',
	laufzeitDatum: 'zustellung-laufzeit-datum', // molecules/DatumFeld
	// Warnboxen (role="alert")
	warnBriefing: 'zustellung-warnung-briefing',
	warnAlarme: 'zustellung-warnung-alarme',
	// Kanal-Tabelle
	kanaeleKopf: 'zustellung-kanaele-kopf',
	kanaeleUnterzeile: 'zustellung-kanaele-unterzeile',
	tabelle: 'zustellung-kanal-tabelle',
	zeile: (k: KanalId) => `zustellung-kanal-${k}`,
	status: (k: KanalId) => `zustellung-kanal-${k}-status`,
	hinweis: (k: KanalId) => `zustellung-kanal-${k}-hinweis`,
	konto: (k: KanalId) => `zustellung-kanal-${k}-konto`, // „Im Konto … →“ (Link ins Konto)
	briefing: (k: KanalId) => `zustellung-kanal-${k}-briefing`, // role=switch
	alarm: (k: KanalId) => `zustellung-kanal-${k}-alarm`, // role=switch (nur wenn bedienbar)
	alarmGesperrt: (k: KanalId) => `zustellung-kanal-${k}-alarm-gesperrt`, // „gesperrt: {Grund}“
	dringlichkeit: (k: KanalId) => `zustellung-kanal-${k}-dringlichkeit`, // Zelle: „–“ oder Segment
	dringlichkeitOption: (k: KanalId, w: 'LOW' | 'MODERATE' | 'HIGH') => `zustellung-kanal-${k}-dringlichkeit-${w}`,
	legende: 'zustellung-legende',
	// Stille Stunden + Anpassen
	stilleSchalter: 'zustellung-stille-schalter',
	stilleVon: 'zustellung-stille-von', // UhrzeitFeld
	stilleBis: 'zustellung-stille-bis',
	stilleUnterzeile: 'zustellung-stille-unterzeile',
	anpassen: 'zustellung-anpassen', // <details>; summary = „Anpassen“
	cooldown: 'zustellung-cooldown', // Minutenfeld (input)
	// Uebergangsblock
	uebergang: 'zustellung-uebergang'
} as const;

export const MARKER = ['abschnittskopf', 'briefing-zeiten', 'laufzeit', 'kanaele', 'stille-stunden', 'uebergang'] as const;

export const tid = (wurzel: Page | Locator, id: string): Locator => wurzel.locator(`[data-testid="${id}"]:visible`).first();

/** Fester Zustellungs-Stand fuer beide Kontexte (Morgen 07:00 an, Abend 18:00 an, Stille 22–06, Cooldown 45). */
function zustellungsFelder(kind: HubKind): Json {
	const alarm = {
		alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00'
	};
	if (kind === 'route') {
		return {
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: true,
				morning_time: '07:00:00',
				evening_time: '18:00:00',
				send_email: true,
				send_telegram: false,
				send_sms: false,
				send_premium_sms: false,
				telegram_style: 'rich',
				show_outlook: true
			},
			display_config: { ampel: { template: 'wandern' }, telegram_kurzform: false },
			...alarm
		};
	}
	return {
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:00:00',
		send_telegram: false,
		send_sms: false,
		send_premium_sms: false,
		display_config: { ampel: { template: 'wandern' }, telegram_style: 'rich' },
		...alarm
	};
}

/** Seed je Kontext mit festem Zustellungs-Stand; `extra` ueberschreibt Felder (z.B. send_email, end_date). */
export async function seedZustellung(request: APIRequestContext, kind: HubKind, extra: Json = {}): Promise<SeededHub> {
	if (kind === 'route') {
		return seedHub(request, kind, {
			extra: {
				...zustellungsFelder(kind),
				stages: [
					{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }, { id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 1200 }] },
					{ id: 's2', name: 'Tag 2', date: '2027-08-04', waypoints: [{ id: 'c', name: 'c', lat: 42.08, lon: 9.0, elevation_m: 900 }, { id: 'd', name: 'd', lat: 42.12, lon: 9.0, elevation_m: 1100 }] }
				],
				...extra
			}
		});
	}
	const orte: string[] = [];
	for (let i = 0; i < 2; i++) orte.push((await createTestLocation(request, { lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 })).id);
	const hub = await seedHub(request, kind, { extra: { location_ids: orte, ...zustellungsFelder(kind), ...extra } });
	return {
		...hub,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await request.delete(`/api/locations/${o}`).catch(() => {});
		}
	};
}

/** Gespeicherter Abo-Zustand per API. */
export async function stand(request: APIRequestContext, kind: HubKind, id: string): Promise<Json> {
	const r = await request.get(hubApiPath(kind, id));
	expect(r.ok(), `GET ${hubApiPath(kind, id)}: ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Profil des angemeldeten Kontos (Quelle der Kanal-Zustaende). */
export async function profil(request: APIRequestContext): Promise<Json> {
	const r = await request.get('/api/auth/profile');
	expect(r.ok(), `GET /api/auth/profile: ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Ist ein Kanal laut Profil sendebereit (Erwartungswert fuer die Tabelle, Spec §2)? */
export function sendebereit(p: Json, k: KanalId): boolean {
	if (k === 'email') return !!p.mail_to;
	if (k === 'telegram') return !!p.telegram_chat_id;
	if (k === 'sms') return !!p.sms_to && p.sms_allowed !== false && p.sms_verified === true;
	return p.premium_sms_allowed === true && p.premium_sms_reply_state === 'fresh';
}

/** Uhrzeit eines Trip/Preset-Stands als HH:MM (Trip: report_config, Orte: Top-Level). */
export function gespeicherteZeit(kind: HubKind, s: Json, slot: 'morgen' | 'abend'): string {
	const feld = slot === 'morgen' ? 'morning_time' : 'evening_time';
	return String((kind === 'route' ? s.report_config?.[feld] : s[feld]) ?? '').slice(0, 5);
}

/** Ist das ein Schreibvorgang des Reiters Zustellung? */
export function istZustellungSchreiben(kind: HubKind, id: string): (r: Request) => boolean {
	return (r) => r.method() === 'PUT' && new URL(r.url()).pathname === hubApiPath(kind, id);
}

/** Wartet auf die (erfolgreiche) Antwort des naechsten Schreibvorgangs; liefert den gesendeten Rumpf. */
export async function warteAufSpeichern(page: Page, kind: HubKind, id: string): Promise<Json> {
	const pruef = istZustellungSchreiben(kind, id);
	const antwort = await page.waitForResponse((r) => pruef(r.request()), { timeout: 20_000 });
	expect(antwort.ok(), `Speichern ${antwort.request().url()}: HTTP ${antwort.status()}`).toBeTruthy();
	return antwort.request().postDataJSON();
}

/** Oeffnet den Hub im Reiter Zustellung und wartet, bis der Reiter steht. */
export async function oeffneZustellung(page: Page, kind: HubKind, id: string, hash?: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'zustellung', hash });
	const panel = page.locator(`[data-testid="${HUB_SEL[kind].panel}-zustellung"]:visible`).first();
	const reiter = panel.getByTestId(ZT.tab);
	await expect(reiter).toBeVisible({ timeout: 15_000 });
	await expect(reiter).toHaveAttribute('data-context', kind);
	await expect(reiter.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
	return reiter;
}

/** Schalter (role=switch) auf `an` bringen, falls noetig. */
export async function schalte(schalter: Locator, an: boolean): Promise<void> {
	const ist = (await schalter.getAttribute('aria-checked')) === 'true';
	if (ist !== an) await schalter.click();
	await expect(schalter).toHaveAttribute('aria-checked', an ? 'true' : 'false');
}

/** Klappt „Anpassen“ (natives <details>) auf, falls zu, und liefert das Cooldown-Minutenfeld. */
export async function cooldownFeld(reiter: Locator): Promise<Locator> {
	const auf = reiter.getByTestId(ZT.anpassen);
	if (!(await auf.evaluate((d) => (d as HTMLDetailsElement).open))) await auf.locator('summary').click();
	const feld = auf.getByTestId(ZT.cooldown);
	await expect(feld).toBeVisible();
	return feld;
}

/** Schalter „Amtliche Warnungen“ bzw. „Radar-Alarm“ — seit #2794 S3a nur im Reiter Wetter (AC-31). */
export const warnungenSchalter = (page: Page): Locator =>
	page.locator('[data-testid="wetter-tab"]:visible [data-testid="wetter-warnungen-schalter"]').first();
export const radarSchalter = (page: Page): Locator =>
	page.locator('[data-testid="wetter-tab"]:visible [data-testid="wetter-radar-schalter"]').first();

/** Oeffnet den Hub im Reiter Wetter und wartet auf den Schalter „Amtliche Warnungen“. */
export async function oeffneWetterWarnungen(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'wetter' });
	await expect(warnungenSchalter(page)).toBeVisible({ timeout: 15_000 });
}

/** Angezeigte Uhrzeit eines UhrzeitFelds als „HH:MM“ (Segmente ohne Leerraum). */
export async function angezeigteZeit(feld: Locator): Promise<string> {
	const t = (await feld.locator('[data-slot="uhrzeit-feld-eingabe"]').innerText()).replace(/\s+/g, '');
	const m = t.match(/(\d{2}):?(\d{2})/);
	return m ? `${m[1]}:${m[2]}` : t;
}
