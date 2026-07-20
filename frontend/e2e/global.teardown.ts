// #1329 Maßnahme B: Sicherheitsnetz-Gegenstück zu `global.setup.ts`.
//
// Spec: docs/specs/modules/fix_1329_e2e_data_hygiene.md, AC-1/AC-2/AC-3.
//
// Läuft als `globalTeardown` NACH Abschluss der gesamten Suite — Playwright
// führt globalTeardown unabhängig vom Testergebnis aus (auch bei fehlgeschlagenen
// Tests/Abbrüchen, AC-2). Fegt Presets → Trips → Orte mit reserviertem Präfix
// `E2E-GZ-` real vom Server, statt sich auf den modul-internen (worker-lokalen)
// `helpers.ts`-Cleanup-Set zu verlassen, das über mehrere Test-Dateien/Worker
// hinweg nicht geteilt wird.

import { request as playwrightRequest, type APIRequestContext, type APIResponse, type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'node:path';
import { assertNotProdBaseURL, assertNotProdApiProxyTarget } from './prodUrlGuard';
import { PROD_API_PROXY_TARGET } from './apiProxyTarget';
import { E2E_TEST_PREFIX } from './helpers';

type NamedItem = { id?: string; name?: string };

function resolveActiveProjectUse(config: FullConfig): Record<string, unknown> {
	// Nimmt die "tests"-Projekt-Konfiguration (falls vorhanden), sonst das
	// erste Projekt — das "setup"-Projekt trägt i.d.R. keine relevante
	// baseURL/storageState/httpCredentials-Kombination.
	const project =
		config.projects.find((p) => p.name !== 'setup') ?? config.projects[0];
	return (project?.use ?? {}) as Record<string, unknown>;
}

function resolveStorageStatePath(config: FullConfig, use: Record<string, unknown>): string | undefined {
	const storageState = use.storageState;
	if (typeof storageState !== 'string') return undefined;
	const candidate = path.isAbsolute(storageState)
		? storageState
		: path.resolve(config.rootDir ?? process.cwd(), storageState);
	return fs.existsSync(candidate) ? candidate : undefined;
}

async function sweepPrefix(apiContext: APIRequestContext): Promise<void> {
	const presetsRes = await apiContext.get('/api/compare/presets').catch(() => undefined);
	const tripsRes = await apiContext.get('/api/trips').catch(() => undefined);
	const locationsRes = await apiContext.get('/api/locations').catch(() => undefined);

	const presetIds = await matchingIds(presetsRes, E2E_TEST_PREFIX);
	const tripIds = await matchingIds(tripsRes, E2E_TEST_PREFIX);
	const locationIds = await matchingIds(locationsRes, E2E_TEST_PREFIX);

	// Reihenfolge: Presets/Trips (referenzierend) VOR Orten (referenziert) —
	// behebt die 409-Waisen aus Root-Cause #3/#4 (Kontext-Dokument #1329).
	for (const id of presetIds) await deleteQuiet(apiContext, `/api/compare/presets/${id}`);
	for (const id of tripIds) await deleteQuiet(apiContext, `/api/trips/${id}`);
	for (const id of locationIds) await deleteQuiet(apiContext, `/api/locations/${id}`);
}

async function matchingIds(res: APIResponse | undefined, prefix: string): Promise<string[]> {
	if (!res || !res.ok()) return [];
	try {
		const body = (await res.json()) as NamedItem[];
		if (!Array.isArray(body)) return [];
		return body.filter((item) => item.name?.startsWith(prefix) && item.id).map((item) => item.id as string);
	} catch {
		return [];
	}
}

async function deleteQuiet(apiContext: APIRequestContext, urlPath: string): Promise<void> {
	try {
		const res = await apiContext.delete(urlPath);
		if (!res.ok() && res.status() !== 404) {
			console.error(`[global.teardown] DELETE ${urlPath} -> HTTP ${res.status()}`);
		}
	} catch (err) {
		console.error(`[global.teardown] DELETE ${urlPath} threw:`, err);
	}
}

export default async function globalTeardown(config: FullConfig): Promise<void> {
	const use = resolveActiveProjectUse(config);
	const baseURL = typeof use.baseURL === 'string' ? use.baseURL : '';

	// Guard zuerst — niemals gegen Prod räumen (Teardown darf hart abbrechen,
	// das Sicherheitsnetz selbst muss aber nie die Suite crashen lassen).
	try {
		assertNotProdBaseURL(baseURL);
		let host = '';
		try {
			host = new URL(baseURL).hostname;
		} catch {
			/* leere/ungültige baseURL -> kein lokaler Proxy-Check nötig */
		}
		// Der /api-Proxy-Check ist nur relevant, wenn die Suite lokal gegen
		// einen SvelteKit-Dev-Server läuft (frontend/playwright.config.ts) —
		// die reinen Staging-Configs sprechen die Staging-Domain direkt an
		// und haben keinen lokalen Proxy (s. global.setup.ts vs. *.staging.setup.ts).
		if (host === 'localhost' || host === '127.0.0.1') {
			await assertNotProdApiProxyTarget(process.env.GZ_API_BASE ?? PROD_API_PROXY_TARGET);
		}
	} catch (err) {
		console.error('[global.teardown] Prod-Guard abgebrochen — kein Räumlauf:', err);
		return;
	}

	const contextOptions: Parameters<typeof playwrightRequest.newContext>[0] = {
		baseURL,
		ignoreHTTPSErrors: true
	};
	if (use.httpCredentials) {
		contextOptions.httpCredentials = use.httpCredentials as { username: string; password: string };
	}
	const storageStatePath = resolveStorageStatePath(config, use);
	if (storageStatePath) {
		contextOptions.storageState = storageStatePath;
	}

	let apiContext: APIRequestContext | undefined;
	try {
		apiContext = await playwrightRequest.newContext(contextOptions);
		await sweepPrefix(apiContext);
	} catch (err) {
		// Teardown darf die Suite niemals hart abbrechen lassen.
		console.error('[global.teardown] Räumlauf fehlgeschlagen:', err);
	} finally {
		await apiContext?.dispose().catch(() => {});
	}
}
