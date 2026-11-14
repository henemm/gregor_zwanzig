// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Alarme" speichert
// SELBST — EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife
// über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-1 (AS-1..AS-4)
//
// Ersetzt compare-alarme-speichert-selbst.spec.ts (#2276 S2, nur Vergleich):
//   AC-1                → AS-1 (je kind)
//   AC-6 Reiterwechsel  → AS-2 (je kind)
//   Pausieren-Flush     → AS-3 (je kind)
//   #2375 Roundtrip     → AS-4 (je kind)
//
// #2795 S3b Teilschritt 1b (feat_2795_s3b_teil1_zustellung.md): der Alarm-Baustein ist im Reiter
// Zustellung abgelöst (Radar und Amtliche Warnungen wohnen nur noch im Reiter Wetter, AC-31). Auslöser
// ist jetzt für BEIDE kinds dieselbe Alarm-Geste des neuen Reiters: der Schalter „Stille Stunden“
// (Alarm-Teil des EINEN Speicherers, Owner `alarme`, AC-24/AC-33). Die Chip-/PUT-/Flush-Zusicherungen
// bleiben unverändert; zusätzlich darf der Alarm-Rumpf `display_config` nie tragen (AC-32).

// Pausieren je kind: der Ortsvergleich pausiert per PUT `{schedule,
// previous_schedule}`, der Trip per PATCH `/api/trips/{id}/state` `{paused}`
// (subscriptionExec.ts setPaused). Beide Wege werden in EINEM geordneten
// Schreib-Protokoll erfasst; die Zusicherung „Alarm-Schreibvorgang VOR dem
// Status-Schreibvorgang, Status-Rumpf trägt NUR den Status" ist gemeinsam.
//
// Wartebedingungen nur expect.poll / toHaveAttribute / waitForResponse.
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;

/** Auslöser für beide kinds: Schalter „Stille Stunden“ im Reiter Zustellung (Seed: aus). */
const stilleSchalter = (page: Page): Locator =>
	page.locator('[data-testid="zustellung-tab"]:visible [data-testid="zustellung-stille-schalter"]').first();
const stilleAn = (s: Stand): boolean => Boolean(s.alert_quiet_from) && Boolean(s.alert_quiet_to);

/** kind-Tabelle: Fremdfelder des Alarm-Rumpfs, Status-Weg. */
const AS_SEL: Record<
	HubKind,
	{
		seed: Record<string, unknown>;
		/** Felder, die ein Alarm-Rumpf NIE tragen darf (#2375 Teilfeld-Nutzlast, AC-32). */
		fremd: string[];
		/** Schlüssel des Status-Rumpfs beim Pausieren (sortiert). */
		statusSchluessel: string[];
		statusPausiert: (rumpf: Stand) => boolean;
		istPausiert: (s: Stand) => boolean;
	}
> = {
	route: {
		seed: {
			official_warnings: { enabled: true },
			alert_channels: { email: true, telegram: false, sms: false, premium_sms: false }
		},
		fremd: ['name', 'stages', 'report_config', 'display_config', 'official_warnings', 'official_alerts_enabled', 'corridors', 'paused'],
		statusSchluessel: ['paused'],
		statusPausiert: (r) => r.paused === true,
		istPausiert: (s) => Boolean(s.paused_at)
	},
	vergleich: {
		seed: { radar_alert_enabled: false, display_config: { active_metrics: ['wind_max_kmh'] } },
		fremd: ['name', 'location_ids', 'schedule', 'send_telegram', 'display_config', 'radar_alert_enabled', 'official_alerts_enabled'],
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

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');

async function oeffneAlarme(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'zustellung' }); // #2795 S3b: Alarm-Einstellungen im Reiter Zustellung
	await expect(stilleSchalter(page)).toBeVisible({ timeout: 15_000 });
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const as = AS_SEL[kind];

	// AS-1 (Alt AC-1) — fängt: $effect-Delegation im AlarmeTab und Mount-Props am Hub.
	test(`AS-1 (${kind}): Alarm ändern → genau ein PUT mit dem neuen Wert, danach „Gespeichert"`, async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const hub = await seedHub(page.request, kind, { extra: as.seed });
		try {
			const pfad = hubApiPath(kind, hub.id);
			const { puts, beantwortet } = zaehlePuts(page, pfad);
			await oeffneAlarme(page, kind, hub.id);
			expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);
			await expect(stilleSchalter(page), 'Vorbedingung: Stille Stunden stehen aus').toHaveAttribute('aria-checked', 'false');

			await stilleSchalter(page).click();
			await expect(stilleSchalter(page)).toHaveAttribute('aria-checked', 'true');

			await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
			await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(anzeige(page)).toContainText('Gespeichert');

			expect(puts.length, 'genau EIN PUT für eine Alarm-Änderung').toBe(1);
			expect(stilleAn(puts[0].postDataJSON() as Stand)).toBe(true);
			expect(stilleAn(await stand(page, kind, hub.id))).toBe(true);
		} finally {
			await hub.aufraeumen();
		}
	});

	// AS-4 (Alt #2375 Test 13 / AC-8) — fängt: ein Eigenfeld fällt aus dem
	// Alarm-Rumpf bzw. der Rumpf trägt Fremdfelder (Voll-Spread statt Teilfeld).
	test(`AS-4 (${kind}): #2375 Roundtrip — Alarm ändern → nach Neuladen steht der Wert, der Rumpf trägt keine Fremdfelder`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const hub = await seedHub(page.request, kind, { extra: as.seed });
		try {
			const pfad = hubApiPath(kind, hub.id);
			const { puts, beantwortet } = zaehlePuts(page, pfad);
			await oeffneAlarme(page, kind, hub.id);

			await stilleSchalter(page).click();
			await expect(stilleSchalter(page)).toHaveAttribute('aria-checked', 'true');
			await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
			await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			const rumpf = puts[0].postDataJSON() as Stand;
			for (const fremd of as.fremd) {
				expect(Object.keys(rumpf), `der Alarm-Rumpf darf \`${fremd}\` nicht tragen`).not.toContain(fremd);
			}

			await oeffneAlarme(page, kind, hub.id);
			await expect(stilleSchalter(page)).toHaveAttribute('aria-checked', 'true', { timeout: 10_000 });
			expect(stilleAn(await stand(page, kind, hub.id))).toBe(true);
		} finally {
			await hub.aufraeumen();
		}
	});

	// AS-2 (Alt AC-6) — fängt: Flush beim Reiterwechsel (handleValueChange) fehlt.
	// Issue #1743: Ziel ist der Reiter „Wetter-Metriken" (trägt den Versand-Abschnitt).
	test(`AS-2 (${kind}): Alarm ändern und sofort zu „Wetter-Metriken" wechseln → PUT ist beim Wechsel schon beantwortet`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const hub = await seedHub(page.request, kind, { extra: as.seed });
		try {
			const pfad = hubApiPath(kind, hub.id);
			const { puts, beantwortet } = zaehlePuts(page, pfad);
			await oeffneAlarme(page, kind, hub.id);

			await stilleSchalter(page).click();
			// sofort, innerhalb des Entprell-Fensters (700 ms), den Reiter wechseln
			// #2794 S3a: aus dem Reiter Zustellung (Alarme) in den Reiter Wetter.
			await page.locator(`[data-testid="${sel.reiter}-wetter"]:visible`).click();
			await expect(page.locator(`[data-testid="${sel.panel}-wetter"]`)).toBeVisible();

			// Der Wechsel wird erst freigegeben, NACHDEM der Alarm-PUT beantwortet ist.
			expect(beantwortet.length, 'Alarm-PUT war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);
			expect(stilleAn(beantwortet[0].postDataJSON() as Stand)).toBe(true);

			await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			expect(puts.length).toBe(1);
			expect(stilleAn(await stand(page, kind, hub.id))).toBe(true);
		} finally {
			await hub.aufraeumen();
		}
	});

	// AS-3 (Alt „Pausieren direkt nach Alarm-Änderung") — fängt: Flush vor dem
	// Statuswechsel entfernt.
	test(`AS-3 (${kind}): Pausieren direkt nach Alarm-Änderung → Alarm-Schreibvorgang VOR dem Pausieren, beide Werte bleiben`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const hub = await seedHub(page.request, kind, { extra: as.seed });
		try {
			const pfad = hubApiPath(kind, hub.id);
			const { alle, fertig } = protokolliereSchreiber(page, pfad);
			await oeffneAlarme(page, kind, hub.id);

			await stilleSchalter(page).click();
			// sofort (innerhalb der Entprellung) über den Kopf-Kebab pausieren
			await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
			const pausieren = page.getByRole('menuitem', { name: 'Pausieren' });
			await expect(pausieren, 'Vorbedingung: der Hub bietet „Pausieren" an').toBeVisible();
			await pausieren.click();

			await expect.poll(() => fertig.length, { timeout: 10_000 }).toBe(2);
			await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

			const [erster, zweiter] = alle.map((r) => r.postDataJSON() as Stand);
			expect(alle[0].method(), 'erster Schreibvorgang ist der Alarm-PUT').toBe('PUT');
			expect(stilleAn(erster), 'erster Schreibvorgang muss die Alarm-Änderung sein').toBe(true);
			// #2375: der Alarm-Rumpf trägt den Status gar nicht (Teilfeld-Nutzlast)
			for (const k of as.statusSchluessel) {
				expect(Object.keys(erster), 'erster Schreibvorgang darf noch nicht pausieren').not.toContain(k);
			}
			expect(as.statusPausiert(zweiter), 'zweiter Schreibvorgang pausiert').toBe(true);
			// #2375 (AC-6/AC-9): der Pausieren-Rumpf trägt NUR den Status.
			expect(Object.keys(zweiter).sort(), `Pausieren-Rumpf trägt nur { ${as.statusSchluessel.join(', ')} }`).toEqual(
				as.statusSchluessel
			);

			const s = await stand(page, kind, hub.id);
			expect(stilleAn(s)).toBe(true);
			expect(as.istPausiert(s), 'Server: pausiert').toBe(true);
			expect(alle.length).toBe(2);
		} finally {
			await hub.aufraeumen();
		}
	});
}
