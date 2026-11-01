// E2E (Staging) — Issue #2682 (Epic #2345): Versand-Historie und „Zuletzt raus"
// in der geteilten Hub-Übersicht. EINE Zusicherung für BEIDE Hubs per Schleife über
// HUB_KINDS, dazu die Trip-Fälle von „Zuletzt raus" (das Feld gibt es nur beim Trip
// aus dem Briefing-Log; der Vergleich liest preset.letzter_versand).
//
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
//   AC-12 — ein Laden: genau EIN Aufruf an /api/briefings/{id}/briefing-history je
//           Übersicht (Kennzahl und Liste aus derselben Antwort), beide Arten.
//   AC-6  — „Zuletzt raus" ignoriert Einträge von Hand: nach einem echten
//           Test-Versand (POST /api/briefings/{id}/send?kind=route ⇒ on_demand=true)
//           steht der Eintrag in der Liste („von Hand"), die Kennzahl bleibt
//           „Noch kein Versand".
//   AC-7  — frischer Trip: „Noch kein Versand", nie ein erfundenes Datum.
//   AC-14 — Mandantentrennung mit ZWEI echten Konten: A hat einen Versand-Eintrag,
//           B nicht; B sieht in SEINER Übersicht weder Datum noch Einträge von A,
//           und der Aufruf mit As Trip-Kennung liefert B keine Daten (Go: 200 []).
//
// Zwei echte Sitzungen, kein Mock: Nutzer A = Admin-storageState der Projekt-
// Konfiguration, Nutzer B = registrierter, bestätigter Zweitnutzer im leeren Kontext
// (Vorbild hub-editor-autosave-user-isolation.spec.ts). Genau EINE Registrierung
// (Registrierungsbremse 5/h je IP), deshalb serieller Modus mit beforeAll.
//
// Der Test-Versand stellt echt zu (Kanäle des Admin-Kontos auf Staging) — gewollt:
// AC-6 verlangt „E2E mit echtem Test-Versand". Scheitert der Versand (z. B. kein
// zustellbarer Kanal ⇒ kein Log-Eintrag, trip_report_scheduler.py:1967-1974), ist
// das ein lauter Messaufbau-Fehler, kein stilles Grün.
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy) mit einer
// Staging-Config, deren testMatch diese Datei enthält.

import { test, expect, type BrowserContext, type Page, type Request } from '@playwright/test';
import {
	HUB_KINDS,
	createTestLocation,
	openHub,
	registriereBestaetigtenZweitnutzer,
	seedHub,
	type HubKind,
	type SeededHub
} from './helpers';

test.describe.configure({ mode: 'serial' });

const DESKTOP = { width: 1280, height: 900 };
const HISTORIE = /\/api\/briefings\/[^/]+\/briefing-history(\?|$)/;
const ZULETZT_RAUS = 'hub-uebersicht-stat-zuletzt-raus';

let ctxA: BrowserContext;
let ctxB: BrowserContext;
const hubsA = new Map<HubKind, SeededHub>();
let tripB: SeededHub | undefined;
let ortA: string | undefined;

test.beforeAll(async ({ browser }) => {
	ctxA = await browser.newContext();
	ortA = (await createTestLocation(ctxA.request, { name: `E2E-GZ-2682-A-${Date.now()}`, lat: 47.3, lon: 11.4 })).id;
	hubsA.set('route', await seedHub(ctxA.request, 'route'));
	hubsA.set('vergleich', await seedHub(ctxA.request, 'vergleich', { extra: { location_ids: [ortA] } }));

	// Nutzer B ausdrücklich OHNE storageState (sonst erbte er den Admin-Cookie).
	ctxB = await browser.newContext({ storageState: undefined });
	await registriereBestaetigtenZweitnutzer(ctxA.request, ctxB.request, `e2e2682${Date.now()}`, 'test1234');
	tripB = await seedHub(ctxB.request, 'route');
});

test.afterAll(async () => {
	for (const hub of hubsA.values()) await hub.aufraeumen().catch(() => {});
	await tripB?.aufraeumen().catch(() => {});
	if (ortA) await ctxA?.request.delete(`/api/locations/${ortA}`).catch(() => {});
	hubsA.clear();
	await ctxB?.close();
	await ctxA?.close();
});

/** Öffnet die Übersicht und zählt jeden Aufruf an die Versand-Historie. */
async function oeffneUndZaehle(page: Page, kind: HubKind, id: string): Promise<Request[]> {
	const aufrufe: Request[] = [];
	page.on('request', (r) => {
		if (HISTORIE.test(new URL(r.url()).pathname + new URL(r.url()).search)) aufrufe.push(r);
	});
	await page.setViewportSize(DESKTOP);
	await openHub(page, kind, id);
	const historie = page.locator(`[data-testid="briefing-history"][data-kind="${kind}"]:visible`);
	await expect(historie).toBeVisible({ timeout: 10_000 });
	// geladen = Leerzustand oder mindestens eine Zeile (kein Lade-Text mehr)
	await expect(historie.locator('[data-testid="briefing-history-empty"], [data-testid="briefing-history-entry"]').first()).toBeVisible({
		timeout: 10_000
	});
	return aufrufe;
}

// ─── AC-12: ein Laden je Übersicht, beide Arten ─────────────────────────────

for (const kind of HUB_KINDS) {
	test(`VH-1 (${kind}): Übersicht lädt die Versand-Historie genau einmal (AC-12)`, async () => {
		const page = await ctxA.newPage();
		try {
			const hub = hubsA.get(kind)!;
			const aufrufe = await oeffneUndZaehle(page, kind, hub.id);
			// kurze Ruhephase für nachlaufende Abrufe (z. B. zweiter Lader) — kein fester Schlaf auf Zustand
			await page.waitForLoadState('networkidle');
			expect(aufrufe.map((r) => r.url()), 'genau EIN Aufruf an briefing-history').toHaveLength(1);
			expect(new URL(aufrufe[0].url()).searchParams.get('kind')).toBe(kind);
			expect(aufrufe[0].url()).toContain(`/api/briefings/${hub.id}/briefing-history`);
		} finally {
			await page.close();
		}
	});
}

// ─── AC-7 / AC-6: „Zuletzt raus" des Trips ──────────────────────────────────

test('VH-2 (route): frischer Trip ⇒ „Zuletzt raus" = „Noch kein Versand", Liste leer (AC-7)', async () => {
	const page = await ctxA.newPage();
	try {
		await oeffneUndZaehle(page, 'route', hubsA.get('route')!.id);
		await expect(page.locator(`[data-testid="${ZULETZT_RAUS}"]:visible`)).toHaveText('Noch kein Versand', { timeout: 10_000 });
		await expect(page.locator('[data-testid="briefing-history-empty"]:visible')).toHaveCount(1);
	} finally {
		await page.close();
	}
});

test('VH-3 (route): echter Test-Versand ⇒ Eintrag „von Hand" in der Liste, „Zuletzt raus" bleibt „Noch kein Versand" (AC-6)', async () => {
	const id = hubsA.get('route')!.id;
	const antwort = await ctxA.request.post(`/api/briefings/${id}/send?kind=route&report_type=morning`);
	expect(antwort.ok(), `Messaufbau: Test-Versand fehlgeschlagen: ${antwort.status()} ${await antwort.text()}`).toBe(true);
	await expect
		.poll(async () => ((await (await ctxA.request.get(`/api/briefings/${id}/briefing-history?kind=route`)).json()) as unknown[]).length, {
			timeout: 30_000,
			message: 'Messaufbau: der Test-Versand hat keinen Log-Eintrag geschrieben'
		})
		.toBeGreaterThan(0);

	const page = await ctxA.newPage();
	try {
		await oeffneUndZaehle(page, 'route', id);
		const eintrag = page.locator('[data-testid="briefing-history-entry"]:visible');
		await expect(eintrag).toHaveCount(1, { timeout: 10_000 });
		await expect(eintrag).toContainText('von Hand');
		await expect(page.locator(`[data-testid="${ZULETZT_RAUS}"]:visible`)).toHaveText('Noch kein Versand');
	} finally {
		await page.close();
	}
});

// ─── AC-14: Mandantentrennung mit zwei Konten ───────────────────────────────

test('VH-4 (route): Nutzer B sieht in seiner Übersicht nichts von A; As Trip-Kennung liefert B keine Daten (AC-14)', async () => {
	const idA = hubsA.get('route')!.id;
	// Vorbedingung: A HAT einen Eintrag (aus VH-3) — sonst wäre die Prüfung vakuum.
	const beiA = (await (await ctxA.request.get(`/api/briefings/${idA}/briefing-history?kind=route`)).json()) as unknown[];
	expect(beiA.length, 'Vorbedingung: A hat einen Versand-Eintrag').toBeGreaterThan(0);

	const page = await ctxB.newPage();
	try {
		const aufrufe = await oeffneUndZaehle(page, 'route', tripB!.id);
		await expect(page.locator(`[data-testid="${ZULETZT_RAUS}"]:visible`)).toHaveText('Noch kein Versand', { timeout: 10_000 });
		await expect(page.locator('[data-testid="briefing-history-entry"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="briefing-history-empty"]:visible')).toHaveCount(1);
		for (const r of aufrufe) expect(r.url(), 'B fragt nie die Kennung von A ab').not.toContain(idA);
	} finally {
		await page.close();
	}

	// Direkter Aufruf mit As Kennung aus Bs Sitzung: Go liefert 200 [] (kein Existenz-Leck).
	const fremd = await ctxB.request.get(`/api/briefings/${idA}/briefing-history?kind=route`);
	expect(fremd.status()).toBe(200);
	expect(await fremd.json(), 'B bekommt As Einträge').toEqual([]);

	// Und As Hub-Seite ist für B nicht lesbar (Objekt gehört A).
	const hubFremd = await ctxB.request.get(`/api/trips/${idA}`);
	expect(hubFremd.status(), 'B liest As Trip').toBe(404);
});
