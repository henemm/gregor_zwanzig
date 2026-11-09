// Gemeinsamer Aufbau der Klickpfad-Buendel zu Issue #1703 Scheibe 8
// (kanal-eigene Metrikauswahl der Vergleichs-UEBERSICHTSTABELLE).
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md § Testauflage.
//
// 🔴 #1423-Lehre: NIE `count() === 0 -> weiter`. Der Metrik-Block ist waehrend
// des Katalog-Ladens bewusst aus dem DOM entfernt (WeatherMetricsTab.svelte:
// 1204-1207) — eine Momentaufnahme macht daraus ein stilles "gibt es nicht".
// `oeffneUebersicht()` wartet das Ladeende per `waitFor({state:'attached'})`
// ab; erst danach darf eine LEERE Liste behauptet werden.
// 🔴 Scope-Pflicht: der Reiter mountet WeatherV2Reihenfolge DREIMAL
// (Uebersicht/Stundenverlauf/Ausblick) mit denselben `wm2-*`-Testids — alles
// hier haengt am Block `[data-testid="layout-tab"][data-context="vergleich"]`.
//
// #2794 S3a: Grundauswahl (Reiter Wetter) und Kanal-Karte (Reiter Zustellung) liegen in
// getrennten Reitern — siehe `KanalFlaeche.reiter`, `zuGrundauswahl`, `zuKanalKarte`.
//
// Alle Buendel ausfuehren (aus frontend/, NACH Merge + Staging-Deploy) —
// die Config nimmt Hub- UND Anlege-Pfad auf:
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=e2e/playwright.compare-uebersicht-kanal.staging.config.ts

import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { createTestLocation, registerForCleanup } from './helpers';

export type KanalId = 'email' | 'telegram' | 'sms';

/** Nur Groessen mit EINER Auswertung — ihre Grundauswahl-Zeile ist die einfache
 *  Kaestchen-Zeile mit `input[data-metric-key]` (Temperatur/gefuehlte Temperatur
 *  waeren mehroptionale Gruppen, #1411). NEUN > Telegram-Budget 7 (AC-S8-13). */
export const EINFACHE_METRIKEN = [
	'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'pop_max_pct', 'thunder_level_max',
	'sunny_hours_h', 'cloud_avg_pct', 'uv_index_max', 'visibility_min_m'
];

/** Kappungs-Aussage je Kanal (ltChannels.ts::ltCapNoteText) — zugleich Beleg,
 *  dass ein Reiterwechsel angekommen und gerendert ist. */
const KANAL_HINWEIS: Record<KanalId, RegExp> = {
	email: /keine Begrenzung/,
	telegram: /^Telegram: \d+ Metriken · /,
	sms: /Fließtext, \d+ Zeichen$/
};

/** Eigener Test-Vergleich (nie ein fremder!) mit fest gesetzter Grundauswahl. */
export async function createUebersichtPreset(
	request: APIRequestContext, name: string, activeMetrics: string[]
): Promise<string> {
	const loc = await createTestLocation(request, { name: `${name}-ort` });
	const res = await request.post('/api/compare/presets', {
		data: {
			name: `E2E-GZ-${name}`, location_ids: [loc.id], schedule: 'manual', profil: 'wandern',
			hour_from: 7, hour_to: 18, empfaenger: ['urlauber@example.com'],
			display_config: { active_metrics: activeMetrics }
		}
	});
	expect(res.ok(), `Preset-Anlage fehlgeschlagen: HTTP ${res.status()}`).toBeTruthy();
	const body = await res.json();
	registerForCleanup('preset', body.id);
	return body.id as string;
}

/** #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): die Grundauswahl steht im Reiter
 *  `wetter`, die Kanal-Karte (Layout/Reihenfolge) im Reiter `zustellung`. Im Hub ist
 *  jeweils nur EIN Reiter-Inhalt gemountet — die Flaeche kennt daher zwei Reiter und
 *  wechselt per echtem Klick. Die Locatoren sind seitenweit und loesen erst beim
 *  Zugriff auf, gelten also nach jedem Reiterwechsel neu.
 *  Achtung: ein Reiterwechsel flusht eine ausstehende Aenderung (eigener PUT) — wo
 *  Grundauswahl- und Kanal-Geste frueher im selben Entprell-Fenster lagen, entstehen
 *  jetzt zwei PUTs (Begruendung wie MS-2 in hub-wetter-metriken-speichert-selbst). */
export type KanalReiter = 'wetter' | 'zustellung';

export interface KanalFlaeche {
	page: Page;
	/** Panel des Reiters Zustellung (Kanal-Karte). */
	panel: Locator;
	layout: Locator;
	reihenfolge: Locator;
	/** Grundauswahl im Reiter Wetter — vorher `zuGrundauswahl(f)` aufrufen. */
	grundauswahl: Locator;
	/** Wechselt per Klick in den Reiter und wartet dessen Inhalt ab. */
	reiter: (ziel: KanalReiter) => Promise<void>;
}

/** Reiterwechsel im Vergleichs-Hub und Bereitschaft des Ziel-Inhalts. */
async function hubReiter(page: Page, ziel: KanalReiter): Promise<void> {
	await page.getByTestId(`compare-detail-tab-${ziel}`).click();
	const panel = page.getByTestId(`compare-detail-panel-${ziel}`);
	await expect(panel).toBeVisible({ timeout: 15_000 });
	if (ziel === 'wetter') {
		await panel.getByTestId('weather-metrics-vergleich-list').waitFor({ state: 'attached', timeout: 25_000 });
	} else {
		await panel
			.locator('[data-testid="layout-tab"][data-context="vergleich"]')
			.getByTestId('weather-metrics-vergleich-reihenfolge')
			.waitFor({ state: 'attached', timeout: 25_000 });
	}
}

/** Oeffnet die Kanal-Karte (Reiter Zustellung) und wartet das Katalog-Laden ab (s. Kopf). */
export async function oeffneUebersicht(page: Page, presetId: string): Promise<KanalFlaeche> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto(`/compare/${presetId}?tab=zustellung`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 20_000 });
	await hubReiter(page, 'zustellung');
	const panel = page.getByTestId('compare-detail-panel-zustellung');
	const layout = panel.locator('[data-testid="layout-tab"][data-context="vergleich"]');
	const reihenfolge = layout.getByTestId('weather-metrics-vergleich-reihenfolge');
	const grundauswahl = page.getByTestId('compare-detail-panel-wetter').getByTestId('weather-metrics-vergleich-list');
	return { page, panel, layout, reihenfolge, grundauswahl, reiter: (ziel) => hubReiter(page, ziel) };
}

/** In den Reiter Wetter (Grundauswahl). */
export async function zuGrundauswahl(f: KanalFlaeche): Promise<void> {
	await f.reiter('wetter');
}

/** Zurueck in den Reiter Zustellung (Kanal-Karte). */
export async function zuKanalKarte(f: KanalFlaeche): Promise<void> {
	await f.reiter('zustellung');
}

/** Aktive, sortierbare Liste des offenen Kanal-Reiters. */
export function aktiveMetriken(f: KanalFlaeche): Promise<(string | null)[]> {
	return f.reihenfolge.locator('[data-testid="wm2-reihenfolge-row"]')
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
}

/** Gruppe "Aus in diesem Kanal" (ADR-0050 Regel 4). */
export function ausMetriken(f: KanalFlaeche): Promise<(string | null)[]> {
	return f.reihenfolge.locator('[data-testid="wm2-aus-row"]')
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
}

/** Kanal umschalten — und den Wechsel an seiner WIRKUNG abwarten. */
export async function waehleKanal(f: KanalFlaeche, kanal: KanalId): Promise<void> {
	await f.layout.getByTestId(`channel-tab-${kanal}`).click();
	await expect(f.layout.getByTestId('lt-cap-note')).toHaveText(KANAL_HINWEIS[kanal], { timeout: 10_000 });
}

/** Klick, der speichern MUSS: wartet den echten PUT ab. Der Speicher-Anzeiger
 *  taugt nicht — er steht schon VOR der Geste auf "idle". Erst danach ist ein
 *  GET auf den gespeicherten Stand belastbar. */
export async function klickUndSpeichere(f: KanalFlaeche, ziel: Locator): Promise<void> {
	const antwort = f.page.waitForResponse(
		(r) => r.request().method() === 'PUT' && r.url().includes('/api/compare/presets/'), { timeout: 25_000 }
	);
	await ziel.click();
	expect((await antwort).ok(), 'PUT auf den Vergleich fehlgeschlagen').toBeTruthy();
}

/** "Aus in diesem Kanal" (kanal-eigene Abwahl, NICHT die Grundauswahl). */
export async function ausSchalten(f: KanalFlaeche, metrik: string): Promise<void> {
	await klickUndSpeichere(f, f.reihenfolge
		.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${metrik}"]`)
		.getByRole('button', { name: 'Aus', exact: true }));
	await expect.poll(() => ausMetriken(f), { timeout: 10_000 }).toContain(metrik);
}

/** Wie `ausSchalten`, aber OHNE Speicher-Erwartung — fuer die Anlege-Seite
 *  `/compare/new`: dort gibt es kein PUT je Geste, der Vergleich existiert noch
 *  gar nicht. Gespeichert wird dort genau einmal, per POST beim „Briefing
 *  aktivieren" (compare-neu-kanal-anlegen.staging.spec.ts). Die Zusicherung
 *  bleibt dieselbe: die Groesse muss in der Aus-Gruppe ANKOMMEN — ein blosser
 *  Klick ohne diese Wirkung waere kein Nachweis. */
export async function ausSchaltenOhneSpeichern(f: KanalFlaeche, metrik: string): Promise<void> {
	await f.reihenfolge
		.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${metrik}"]`)
		.getByRole('button', { name: 'Aus', exact: true }).click();
	await expect.poll(() => ausMetriken(f), { timeout: 10_000 }).toContain(metrik);
}

/** Gegenstueck: aus der Aus-Gruppe zurueck in die aktive Liste (AC-S8-5). */
export async function einSchalten(f: KanalFlaeche, metrik: string): Promise<void> {
	await klickUndSpeichere(f, f.reihenfolge
		.locator(`[data-testid="wm2-aus-row"][data-metric-id="${metrik}"]`)
		.getByRole('button', { name: 'Ein', exact: true }));
	await expect.poll(() => aktiveMetriken(f), { timeout: 10_000 }).toContain(metrik);
}

let katalogPaare: Map<string, string> | null = null;

/** GESPEICHERTER Stand eines Kanals als Auswahl-Schluessel. `null` = Schluessel
 *  FEHLT (nie editiert), `[]` = bewusste Leerauswahl (AC-S8-11) — genau diese
 *  Unterscheidung ist die Zusicherung und an der Anzeige nicht ablesbar.
 *  Uebersetzt {metric_id, aggregation} (#1373) ueber den Katalog zurueck. */
export async function gespeicherteKanalAuswahl(
	request: APIRequestContext, presetId: string, kanal: KanalId
): Promise<string[] | null> {
	if (!katalogPaare) {
		const kres = await request.get('/api/compare/metrics');
		expect(kres.ok(), `GET /api/compare/metrics HTTP ${kres.status()}`).toBeTruthy();
		const kat = (await kres.json()) as { metrics: { key: string; metric_id?: string; aggregation?: string }[] };
		katalogPaare = new Map(kat.metrics.map((m) => [`${m.metric_id}|${m.aggregation}`, m.key]));
	}
	const res = await request.get(`/api/compare/presets/${presetId}`);
	expect(res.ok(), `GET Preset HTTP ${res.status()}`).toBeTruthy();
	const preset = (await res.json()) as { display_config?: Record<string, unknown> };
	const roh = (preset.display_config?.channel_active_metrics as Record<string, unknown>)?.[kanal];
	if (!Array.isArray(roh)) return null;
	return roh.map((e) => (typeof e === 'string' ? e : katalogPaare!.get(`${e.metric_id}|${e.aggregation}`) ?? JSON.stringify(e)));
}
