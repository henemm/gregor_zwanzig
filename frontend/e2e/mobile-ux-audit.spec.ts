// Mobile-UX-Audit (#2601): alle Routen in drei Smartphone-Profilen auf
// Erreichbarkeit und Bedienbarkeit prüfen. Je Route (und je Detail-Tab,
// Anlege-Schritt und Overlay):
//   (a) horizontaler Overflow von Fenster und jedem <main>
//   (b) überstehende Elemente (overflow-x weder auto noch scroll)
//   (c) interaktive Elemente, die horizontal aus dem Viewport ragen
//   (d) interaktive Elemente, die am Seitenende unter fixen/sticky Leisten
//       liegen (nicht antippbar)
//   (e) Tap-Ziele < 24px (hart, ungekappt) bzw. 24–39px (Hinweis);
//       data-tap-equivalent (WCAG 2.5.8 „equivalent") nie hart
//   (f) Texte < 11px; Eingabefelder < 16px (iOS-Auto-Zoom)
//   (g) abgeschnittene overflow-hidden-Container, scrollbare Mini-Bereiche
//   (h) Viewport-Meta
// Prüflogik: e2e/mobile-ux-audit-check.ts (LAYOUT_CHECK, mit Selbsttest).
// Befunde werden nach jeder Route in test-results/mobile-ux/report-<projekt>
// .json/.md geschrieben (je Route HTTP-Status; Weiterleitungen mit Status und
// Ziel ausgewiesen statt geprüft); Screenshots je Route/Tab daneben.
//
// Assertion-Politik: ohne GZ_AUDIT_STRICT nur Report (Ist-Aufnahme). Mit
// GZ_AUDIT_STRICT=1 schlagen (a), (c), (d) und Tap-Ziele < 24px fehl.
// Sprache: GZ_AUDIT_LOCALE=de|en (Browser-Locale per Config, Profilsprache hier).

import { test, expect, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { LAYOUT_CHECK, type Item, type LayoutResult } from './mobile-ux-audit-check';
import { tippeDatum } from './helpers';

const OUT_ROOT = 'test-results/mobile-ux';
const STRICT = process.env.GZ_AUDIT_STRICT === '1';
// #2601 Runde 2 (AC-16): Sprache des Laufs; die Config setzt daraus die Browser-Locale,
// hier wird die Profilsprache des Seed-Nutzers gesetzt und danach wiederhergestellt.
const AUDIT_LOCALE = process.env.GZ_AUDIT_LOCALE === 'en' ? 'en' : process.env.GZ_AUDIT_LOCALE === 'de' ? 'de' : null;

interface Finding extends Partial<LayoutResult> {
	route: string;
	view: string;
	/** HTTP-Status der ersten Antwort (bei Weiterleitung: der 30x-Status). */
	status?: number;
	/** Ziel einer Weiterleitung (Pfad), falls die Route nicht selbst geprüft wurde. */
	redirectTo?: string;
	skipped?: string;
	error?: string;
}

function slug(route: string): string {
	return route === '/' ? 'root' : route.replace(/^\//, '').replace(/[/?=&]/g, '_');
}

async function resolveIds(page: Page): Promise<{ trip: string | null; compare: string | null }> {
	let trip: string | null = null;
	let compare: string | null = null;
	const t = await page.request.get('/api/trips');
	if (t.ok()) {
		const body = (await t.json()) as { id?: string; stages?: unknown[] }[];
		const pick = body.find((x) => x.id === 'mx-audit-tour') ?? body.sort((a, b) => (b.stages?.length ?? 0) - (a.stages?.length ?? 0))[0];
		if (pick?.id) trip = pick.id;
	}
	const c = await page.request.get('/api/compare/presets');
	if (c.ok()) {
		const body = (await c.json()) as { id?: string; location_ids?: string[] }[];
		const pick = body.sort((a, b) => (b.location_ids?.length ?? 0) - (a.location_ids?.length ?? 0))[0];
		if (pick?.id) compare = pick.id;
	}
	return { trip, compare };
}

class Reporter {
	findings: Finding[] = [];
	constructor(private project: string, private suffix: string) {
		fs.mkdirSync(path.join(OUT_ROOT, project), { recursive: true });
	}
	add(f: Finding) {
		this.findings.push(f);
		this.write();
	}
	write() {
		const base = path.join(OUT_ROOT, `report-${this.project}${this.suffix}`);
		fs.writeFileSync(`${base}.json`, JSON.stringify({ project: this.project, generatedAt: new Date().toISOString(), routes: this.findings }, null, 2));
		const lines = [`# Mobile-UX-Report (${this.project}${this.suffix})`, ''];
		for (const f of this.findings) {
			const label = f.view !== 'initial' ? `${f.route} [${f.view}]` : f.route;
			if (f.error) lines.push(`- ❌ ${label}: LADEFEHLER — ${f.error}`);
			else if (f.redirectTo) lines.push(`- ↪️ ${label}: Weiterleitung (HTTP ${f.status ?? '?'}) nach ${f.redirectTo} — nicht selbst geprüft${f.skipped ? ` (${f.skipped})` : ''}`);
			else if (f.skipped) lines.push(`- ⏭️ ${label}: ${f.skipped}`);
			else {
				const n = (a?: unknown[]) => a?.length ?? 0;
				const hard = (f.pageOverflowPx ?? 0) > 1 || n(f.offscreenInteractive) + n(f.coveredInteractive) + n(f.tinyTargets) > 0;
				const warn = n(f.overflowingElements) + n(f.smallTargets) + n(f.smallText) + n(f.smallInputs) + n(f.clippedContainers) > 0;
				lines.push(
					`- ${hard ? '❌' : warn ? '⚠️' : '✅'} ${label}${f.status ? ` (HTTP ${f.status})` : ''}: overflow ${f.pageOverflowPx}px · offscreen ${n(f.offscreenInteractive)} · verdeckt ${n(f.coveredInteractive)} · tap<24 ${n(f.tinyTargets)} · tap<40 ${n(f.smallTargets)} · tap≈ ${n(f.tapEquivalent)} · text<11 ${n(f.smallText)} · input<16 ${n(f.smallInputs)} · überstehend ${n(f.overflowingElements)} · clip ${n(f.clippedContainers)} · hscroll ${n(f.scrollableRegions)}`
				);
				const detail = (name: string, arr?: Item[]) => {
					for (const it of (arr ?? []).slice(0, 6)) lines.push(`    - ${name}: \`${it.selector}\` „${it.text}" ${JSON.stringify({ ...it, selector: undefined, text: undefined })}`);
				};
				detail('offscreen', f.offscreenInteractive);
				detail('verdeckt', f.coveredInteractive);
				detail('tap<24', f.tinyTargets);
				detail('tap<40', f.smallTargets);
				detail('tap≈ (WCAG 2.5.8 equivalent)', f.tapEquivalent);
				detail('input<16', f.smallInputs);
				detail('überstehend', f.overflowingElements);
				for (const it of (f.smallText ?? []).slice(0, 4)) lines.push(`    - text<11: \`${it.selector}\` ${it.fontSize}px „${it.text}"`);
				detail('clip', f.clippedContainers);
			}
		}
		fs.writeFileSync(`${base}.md`, lines.join('\n') + '\n');
	}
	hardFailures(): string[] {
		// Fehler (Ladefehler, nicht erreichbarer Anlege-Schritt) zählen hart: nicht gemessen ist nicht grün.
		return this.findings
			.filter((f) => !!f.error || (!f.skipped && !f.redirectTo && ((f.pageOverflowPx ?? 0) > 1 || (f.offscreenInteractive?.length ?? 0) + (f.coveredInteractive?.length ?? 0) + (f.tinyTargets?.length ?? 0) > 0)))
			.map((f) => `${f.route}${f.view !== 'initial' ? `#${f.view}` : ''}${f.error ? ` (Fehler: ${f.error})` : ''}`);
	}
}

// Ganzseiten-Screenshot trotz innerem Scroll-Container: <main> und seinen
// h-screen-Rahmen kurz aufklappen, danach zurücksetzen.
async function fullShot(page: Page, file: string) {
	await page.evaluate(() => {
		const m = document.querySelector('main.mobile-scroll-pad') as HTMLElement | null;
		if (!m) return;
		m.dataset.gzPrevOverflow = m.style.overflow;
		m.style.overflow = 'visible';
		// Breite festnageln: sonst weitet überlaufender Inhalt <main> und die
		// Seite würde breiter als der Viewport aufgenommen.
		m.style.flex = `0 0 ${window.innerWidth}px`;
		m.style.width = `${window.innerWidth}px`;
		m.style.maxWidth = `${window.innerWidth}px`;
		const wrap = m.parentElement as HTMLElement | null;
		if (wrap) { wrap.dataset.gzPrevHeight = wrap.style.height; wrap.style.height = 'auto'; }
	});
	await page.screenshot({ path: file, fullPage: true });
	await page.evaluate(() => {
		const m = document.querySelector('main.mobile-scroll-pad') as HTMLElement | null;
		if (!m) return;
		m.style.overflow = m.dataset.gzPrevOverflow ?? '';
		m.style.flex = ''; m.style.width = ''; m.style.maxWidth = '';
		const wrap = m.parentElement as HTMLElement | null;
		if (wrap) wrap.style.height = wrap.dataset.gzPrevHeight ?? '';
	});
}

// Overlays (Sheets, Menüs, Dialoge): öffnen, prüfen, Screenshot, schließen.
const OVERLAYS: { route: RegExp; view: string; open: string; wait: string }[] = [
	{ route: /^\/$/, view: 'konto-sheet', open: '[data-testid="konto-kreis"]', wait: '[data-testid="konto-sheet"]' },
	{ route: /^\/trips$/, view: 'karten-menue', open: '[data-testid^="subscription-card-menu-"]', wait: '[data-testid^="subscription-action-"]' },
	{ route: /^\/compare$/, view: 'karten-menue', open: '[data-testid^="subscription-card-menu-"]', wait: '[data-testid^="subscription-action-"]' },
	{ route: /^\/trips\/[^/]+$/, view: 'sende-dialog', open: '[data-testid="subscription-hub-send"]', wait: '[role="dialog"]' },
	{ route: /^\/compare\/[^/]+$/, view: 'sende-dialog', open: '[data-testid="subscription-hub-send"]', wait: '[role="dialog"]' },
];

type Ctx = { page: Page; rep: Reporter; route: string; shot: (view: string) => string };

async function settle(page: Page) {
	await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
	await page.waitForTimeout(350);
}

/** Lädt die Route; liefert den Status der ERSTEN Antwort (bei 30x der Weiterleitungs-Status). */
async function lade(page: Page, route: string): Promise<{ status?: number; landed: string }> {
	const resp = await page.goto(route, { waitUntil: 'load', timeout: 45_000 });
	await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 0, null, { timeout: 15_000 });
	await settle(page);
	let req = resp?.request();
	while (req?.redirectedFrom()) req = req.redirectedFrom() ?? undefined;
	const status = (await req?.response())?.status() ?? resp?.status();
	return { status, landed: new URL(page.url()).pathname };
}

const ohneSchraegstrich = (p: string) => (p.length > 1 ? p.replace(/\/$/, '') : p);

async function pruefeAnsicht({ page, rep, route, shot }: Ctx, view: string) {
	rep.add({ route, view, ...(await page.evaluate(LAYOUT_CHECK)) });
	await fullShot(page, shot(view));
}

/** Detail-Tabs (Trip: übersicht/etappen/wetter/zustellung; Vergleich: übersicht/orte/wetter/zustellung). */
async function pruefeTabs(ctx: Ctx) {
	const { page } = ctx;
	const tabs = page.locator('[data-testid^="trip-detail-tab-"]:not([data-testid$="-list"]):not([data-testid*="-badge-"]), [data-testid^="compare-detail-tab-"]:not([data-testid$="-list"]):not([data-testid*="-badge-"])');
	const ids = await tabs.evaluateAll((els) => els.map((e) => e.getAttribute('data-testid') ?? ''));
	for (const id of ids) {
		const btn = page.getByTestId(id).first();
		if (!(await btn.isVisible().catch(() => false))) continue;
		await btn.scrollIntoViewIfNeeded().catch(() => {});
		await btn.click({ timeout: 5_000 }).catch(() => {});
		await settle(page);
		await pruefeAnsicht(ctx, id.replace(/^(trip|compare)-detail-tab-/, ''));
	}
}

/** Pflichtangaben von Schritt 1 eintragen (nur im Formular, nichts wird angelegt), damit Schritt 2 offen ist. */
async function schritt1Ausfuellen(page: Page, route: string) {
	if (route.startsWith('/trips/new')) {
		await page.getByTestId('trip-new-name-input-mobile').fill('E2E-GZ-Audit-Trip').catch(() => {});
		await tippeDatum(page, page.getByTestId('trip-new-date-input'), '2027-08-01').catch(() => {});
	} else if (route.startsWith('/compare/new')) {
		await page.getByTestId('compare-editor-name-mobile').fill('E2E-GZ-Audit-Vergleich').catch(() => {});
	}
	await settle(page);
}

/**
 * Pflichtangaben des gerade geöffneten Schritts vorbelegen, damit die Folgeschritte frei werden
 * (Adversary F001, AC-15) — nur im Formular, gespeichert wird nie (kein Klick auf Speichern/Aktivieren):
 *   Trip, Schritt Etappen: je Etappe die Test-GPX hochladen (wie anlegenPflicht/tripGpxHochladen;
 *     /api/gpx/parse liest nur und legt die Datei im GPX-Ordner des lokalen Seed-Nutzers ab);
 *   Vergleich, Schritt Orte: zwei VORHANDENE Orte des Nutzers aus der Bibliothek wählen (kein Ort wird angelegt).
 * Scheitert das, bleibt der Folgeschritt gesperrt und wird unten als Fehler gemeldet.
 */
async function schrittVorbelegen(page: Page, schritt: string): Promise<void> {
	if (schritt === 'etappen') {
		const eingaben = page.locator('.tn-mobile input[type="file"][accept=".gpx"]');
		for (let rest = await eingaben.count(); rest > 0; rest -= 1) {
			const geparst = page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 });
			await eingaben.first().setInputFiles(AUDIT_GPX);
			await geparst;
			await expect(eingaben).toHaveCount(rest - 1);
		}
	} else if (schritt === 'orte') {
		await page.getByTestId('compare-step2-mobile-library-btn').click({ timeout: 5_000 });
		const orte = page.locator('[data-testid^="compare-step2-mobile-lib-check-"]');
		await orte.first().waitFor({ state: 'visible', timeout: 5_000 });
		const anzahl = await orte.count();
		if (anzahl < 2) throw new Error(`nur ${anzahl} Ort(e) in der Bibliothek — Vergleich braucht zwei`);
		for (let i = 0; i < 2; i += 1) await orte.nth(i).click();
		await page.locator('button[aria-label="Schliessen"]:visible, button[aria-label="Close"]:visible').first().click();
	}
	await settle(page);
}

const AUDIT_GPX = path.resolve('./e2e/fixtures/test-trip.gpx');

/**
 * Anlege-Schritte > 1 (/trips/new, /compare/new): alle Reiter der Mobil-Leiste der Reihe nach öffnen,
 * messen und die Pflichtangaben vorbelegen. Ein trotzdem gesperrter Schritt ist ein Fehler (im
 * Strikt-Modus rot), kein stilles Überspringen. Abbruch vor dem Speichern: nichts wird angelegt.
 */
async function pruefeSchritte(ctx: Ctx) {
	const { page } = ctx;
	await schritt1Ausfuellen(page, ctx.route);
	const reiter = page.locator('[data-testid="tn-mobile-tabbar"] [role="tab"], [data-testid="cm-mobile-tabbar"] [role="tab"]').filter({ visible: true });
	const ids = await reiter.evaluateAll((els) => els.filter((e) => e.getAttribute('aria-selected') !== 'true').map((e) => e.getAttribute('data-testid') ?? ''));
	for (const id of ids.filter(Boolean)) {
		const schritt = id.replace(/^(tn|cm)-mobile-tab-/, '');
		const view = `schritt-${schritt}`;
		const btn = page.getByTestId(id).first();
		// Sperrzustand erst jetzt lesen: er hängt an den Vorbelegungen der vorigen Schritte.
		if ((await btn.getAttribute('aria-disabled')) === 'true') {
			ctx.rep.add({ route: ctx.route, view, error: 'Schritt gesperrt — Pflichtangaben im Audit nicht vorbelegt, Schritt nicht gemessen' });
			continue;
		}
		await btn.scrollIntoViewIfNeeded().catch(() => {});
		await btn.click({ timeout: 5_000 }).catch(() => {});
		await settle(page);
		if ((await btn.getAttribute('aria-selected')) !== 'true') {
			ctx.rep.add({ route: ctx.route, view, error: 'Schritt ließ sich nicht öffnen, nicht gemessen' });
			continue;
		}
		await pruefeAnsicht(ctx, view);
		try {
			await schrittVorbelegen(page, schritt);
		} catch (err) {
			ctx.rep.add({ route: ctx.route, view: `${view}-vorbelegen`, error: err instanceof Error ? err.message.slice(0, 300) : String(err) });
		}
	}
}

/** Overlays (Sheets, Menüs, Dialoge): öffnen, prüfen, Screenshot, schließen. */
async function pruefeOverlays({ page, rep, route, shot }: Ctx) {
	for (const ov of OVERLAYS.filter((o) => o.route.test(route))) {
		const trigger = page.locator(ov.open).first();
		if (!(await trigger.isVisible().catch(() => false))) continue;
		await trigger.scrollIntoViewIfNeeded().catch(() => {});
		await trigger.click({ timeout: 5_000 }).catch(() => {});
		const ok = await page.locator(ov.wait).first().waitFor({ state: 'visible', timeout: 5_000 }).then(() => true).catch(() => false);
		await page.waitForTimeout(400);
		rep.add({ route, view: ov.view, ...(await page.evaluate(LAYOUT_CHECK, true)), ...(ok ? {} : { error: `Overlay ${ov.view} nicht sichtbar` }) });
		await page.screenshot({ path: shot(ov.view), fullPage: false });
		await page.keyboard.press('Escape').catch(() => {});
		await page.waitForTimeout(250);
	}
}

type RouteOpts = { tabs?: boolean; schritte?: boolean; hinweis?: string };

async function auditRoute(page: Page, rep: Reporter, route: string, opts: RouteOpts = {}) {
	const project = rep['project'];
	const shot = (view: string) => path.join(OUT_ROOT, project, `${slug(route)}${view !== 'initial' ? `__${view}` : ''}.png`);
	const ctx: Ctx = { page, rep, route, shot };
	try {
		const { status, landed } = await lade(page, route);
		// Weiterleitung ausweisen (Status + Ziel), nicht als geprüfte Route zählen (AC-15).
		if (ohneSchraegstrich(landed) !== ohneSchraegstrich(route.split('?')[0])) {
			rep.add({ route, view: 'initial', status, redirectTo: landed, ...(opts.hinweis ? { skipped: opts.hinweis } : {}) });
			return;
		}
		rep.add({ route, view: 'initial', status, ...(await page.evaluate(LAYOUT_CHECK)) });
		await fullShot(page, shot('initial'));
		if (opts.tabs) await pruefeTabs(ctx);
		if (opts.schritte) await pruefeSchritte(ctx);
		await pruefeOverlays(ctx);
	} catch (err) {
		rep.add({ route, view: 'initial', error: err instanceof Error ? err.message.slice(0, 300) : String(err) });
	}
}

/** Profilsprache des Seed-Nutzers für den Lauf setzen (AC-16); liefert die Wiederherstellung. */
async function setzeProfilsprache(page: Page): Promise<() => Promise<void>> {
	if (!AUDIT_LOCALE) return async () => {};
	const prof = await page.request.get('/api/auth/profile');
	expect(prof.ok(), `Profil lesen: HTTP ${prof.status()}`).toBeTruthy();
	// Ausgangswert unverändert übernehmen (Adversary F003). Die API kennt keinen „leeren" Zustand:
	// GET liefert die wirksame Sprache (leer gespeichert => "de", model.User.Lang), PUT lehnt "" ab
	// (model.IsValidLanguage). Der gelesene Wert IST damit der wiederherstellbare Ausgangszustand.
	const vorher = ((await prof.json()) as { language?: string }).language;
	expect(vorher === 'de' || vorher === 'en', `Profilsprache vorher unbekannt: ${String(vorher)}`).toBeTruthy();
	const res = await page.request.put('/api/auth/profile', { data: { language: AUDIT_LOCALE } });
	expect(res.ok(), `Profilsprache ${AUDIT_LOCALE} setzen: HTTP ${res.status()}`).toBeTruthy();
	return async () => {
		const zurueck = await page.request.put('/api/auth/profile', { data: { language: vorher } });
		expect(zurueck.ok(), `Profilsprache ${vorher} wiederherstellen: HTTP ${zurueck.status()}`).toBeTruthy();
		const nachher = ((await (await page.request.get('/api/auth/profile')).json()) as { language?: string }).language;
		expect(nachher, 'Profilsprache nach dem Lauf = Ausgangszustand').toBe(vorher);
	};
}

function abschluss(rep: Reporter) {
	const hard = rep.hardFailures();
	if (STRICT) expect(hard, 'harte Mobile-Befunde (siehe report)').toEqual([]);
	else test.info().annotations.push({ type: 'hard-findings', description: hard.join(', ') || 'keine' });
}

const EDITOR_HINWEIS = 'Editor-Tabs werden auf der Detailseite geprüft';

test('angemeldete Routen', async ({ page }, testInfo) => {
	const rep = new Reporter(testInfo.project.name, '');
	const zurueck = await setzeProfilsprache(page);
	try {
		const { trip, compare } = await resolveIds(page);
		const routes: ({ route: string } & RouteOpts)[] = [{ route: '/' }, { route: '/trips' }];
		if (trip) routes.push({ route: `/trips/${trip}`, tabs: true }, { route: `/trips/${trip}/edit`, hinweis: EDITOR_HINWEIS });
		else rep.add({ route: '/trips/[id]', view: 'initial', skipped: 'kein Trip' });
		routes.push({ route: '/trips/new', schritte: true }, { route: '/compare' });
		if (compare) routes.push({ route: `/compare/${compare}`, tabs: true }, { route: `/compare/${compare}/edit`, hinweis: EDITOR_HINWEIS });
		else rep.add({ route: '/compare/[id]', view: 'initial', skipped: 'kein Vergleich' });
		routes.push({ route: '/compare/new', schritte: true }, { route: '/locations' }, { route: '/archiv' }, { route: '/account' }, { route: '/admin' }, { route: '/hilfe' }, { route: '/gpx-upload' });
		for (const r of routes) await auditRoute(page, rep, r.route, r);
	} finally {
		await zurueck();
	}
	abschluss(rep);
});

test.describe('öffentliche Routen', () => {
	test.use({ storageState: { cookies: [], origins: [] } });
	test('Startseite, login/register/forgot, Passwort/Bestätigung/Magic-Link', async ({ page }, testInfo) => {
		const rep = new Reporter(testInfo.project.name, '-public');
		const routes = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/verify-email', '/magic-link', '/magic-link/verify'];
		for (const route of routes) await auditRoute(page, rep, route);
		abschluss(rep);
	});
});
