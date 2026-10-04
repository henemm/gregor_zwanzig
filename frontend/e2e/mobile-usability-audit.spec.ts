// Mobile-Usability-Audit gegen Staging — ein Durchlauf pro Browser-Projekt
// (iphone13/WebKit, chromium-390), der alle Kern-Routen auf Darstellungs-
// probleme prüft: horizontaler Page-Overflow, überstehende Elemente, zu
// kleine Texte (<11px), abgeschnittene Fix-Höhen-Container, scrollbare
// Mini-Bereiche, Viewport-Meta, PWA-Install-Banner. Findings werden NACH
// JEDER Route in Report-Dateien geschrieben, damit ein Abbruch nichts
// verwirft. Auf Detailseiten werden zusätzlich alle Tabs durchgeklickt und
// je Tab derselbe Layout-Check + Screenshot wiederholt.
//
// Testdaten: Staging-User mobile-audit (Setup: mobile-usability.staging.setup.ts)
// mit echtem Bestand (31 Orte, 5 Vergleichs-Presets inkl. „Le Var" 8 Orte,
// 9 Briefings) und zwei API-geseedeten Trips (ma-alpen-x, ma-tagestour).
//
// Assertion-Politik: Nur page-level horizontaler Overflow lässt den Test
// FEHLschlagen (klarer Bug). Alles andere ist Warnung im Report.
//
// Screenshots: test-results/mobile-usability/<projekt>/<route>[__<tab>].png
// Reports:     test-results/mobile-usability/report-<projekt>.json / .md

import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const OUT_ROOT = 'test-results/mobile-usability';

interface LayoutFinding {
	route: string;
	view?: string; // 'initial' oder Tab-Name
	skipped?: string;
	pageOverflowPx?: number;
	overflowingElements?: unknown[];
	scrollableRegions?: unknown[];
	smallText?: unknown[];
	clippedContainers?: unknown[];
	pwaBanner?: { present: boolean; box?: unknown; coversInteractive?: number };
	viewportMeta?: string | null;
	viewportFitCover?: boolean;
	viewport?: { width: number; height: number; dpr: number };
	error?: string;
}

function slug(route: string): string {
	return route === '/' ? 'root' : route.replace(/^\//, '').replace(/\//g, '_');
}

// Layout-Gesundheits-Check, läuft im Browser (initial + nach jedem Tab-Wechsel).
const LAYOUT_CHECK = () => {
	const visible = (el: Element) => {
		const cs = getComputedStyle(el);
		if (cs.display === 'none' || cs.visibility === 'hidden') return false;
		return el.getClientRects().length > 0;
	};
	const selOf = (el: Element) => {
		const dt = el.closest('[data-testid]');
		if (dt) return `[data-testid="${dt.getAttribute('data-testid')}"] ${el.tagName.toLowerCase()}`;
		if (el.id) return `#${el.id}`;
		const cls = (el.getAttribute('class') ?? '').trim().split(/\s+/)[0];
		return cls ? `${el.tagName.toLowerCase()}.${cls}` : el.tagName.toLowerCase();
	};
	const snip = (el: Element, n = 60) => (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, n);
	const box = (el: Element) => {
		const r = el.getBoundingClientRect();
		return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
	};

	const doc = document.documentElement;
	const se = document.scrollingElement ?? doc;
	const pageOverflowPx = Math.max(0, se.scrollWidth - window.innerWidth);

	// (b) Überstehende Elemente (overflow-x weder auto noch scroll).
	const overflowingElements: unknown[] = [];
	for (const el of Array.from(doc.querySelectorAll('*'))) {
		const cs = getComputedStyle(el);
		if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') continue;
		if (el.scrollWidth > el.clientWidth + 1 && visible(el) && overflowingElements.length < 15) {
			overflowingElements.push({
				selector: selOf(el),
				scrollWidth: el.scrollWidth,
				clientWidth: el.clientWidth,
				box: box(el),
				text: snip(el)
			});
		}
	}

	// (f) Scrollbare Mini-Bereiche (bewusst scrollbar, aber abgeschnitten).
	const scrollableRegions: unknown[] = [];
	for (const el of Array.from(doc.querySelectorAll('body *'))) {
		const cs = getComputedStyle(el);
		if (cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') continue;
		if (el.scrollWidth > el.clientWidth + 1 && visible(el) && scrollableRegions.length < 15) {
			scrollableRegions.push({
				selector: selOf(el),
				scrollWidth: el.scrollWidth,
				clientWidth: el.clientWidth,
				box: box(el),
				text: snip(el)
			});
		}
	}

	// (c) Zu kleine Texte (<11px, sichtbar, keine Icons/SVG).
	const smallText: unknown[] = [];
	const walker = document.createTreeWalker(doc, NodeFilter.SHOW_TEXT);
	let node: Node | null;
	while ((node = walker.nextNode())) {
		const text = (node.textContent ?? '').trim();
		if (text.length === 0) continue;
		const el = node.parentElement;
		if (!el) continue;
		if (el.closest('svg, script, style, [class*="icon"], [class*="Icon"]')) continue;
		const cs = getComputedStyle(el);
		const fontSize = parseFloat(cs.fontSize);
		if (fontSize > 0 && fontSize < 11 && visible(el) && smallText.length < 15) {
			smallText.push({ selector: selOf(el), fontSize, text: text.slice(0, 60) });
		}
	}

	// (d) Abgeschnittene Fix-Höhen-Container.
	const clippedContainers: unknown[] = [];
	for (const el of Array.from(doc.querySelectorAll('body *'))) {
		const cs = getComputedStyle(el);
		if (cs.overflowY !== 'hidden') continue;
		if (el.scrollHeight > el.clientHeight + 4 && visible(el) && clippedContainers.length < 15) {
			clippedContainers.push({
				selector: selOf(el),
				scrollHeight: el.scrollHeight,
				clientHeight: el.clientHeight,
				box: box(el),
				text: snip(el)
			});
		}
	}

	// (g) PWA-Install-Banner (wird NICHT geschlossen): vorhanden, Box, wie
	// viele Interaktivelemente darunter liegen.
	let pwaBanner: { present: boolean; box?: unknown; coversInteractive?: number } = { present: false };
	const bannerCands = Array.from(doc.querySelectorAll('body div, body aside, body section')).filter(
		(el) => /Startbildschirm/.test(el.textContent ?? '') && visible(el) && el.getBoundingClientRect().height < 400
	);
	if (bannerCands.length > 0) {
		const banner = bannerCands.reduce((a, b) => (a.getBoundingClientRect().width <= b.getBoundingClientRect().width ? a : b));
		const b = banner.getBoundingClientRect();
		let covered = 0;
		for (const el of Array.from(doc.querySelectorAll('body a, body button'))) {
			if (!visible(el)) continue;
			const r = el.getBoundingClientRect();
			const cx = r.x + r.width / 2;
			const cy = r.y + r.height / 2;
			if (cx >= b.x && cx <= b.x + b.width && cy >= b.y && cy <= b.y + b.height) covered++;
		}
		pwaBanner = { present: true, box: box(banner), coversInteractive: covered };
	}

	// (e) Meta-Checks.
	const vp = document.querySelector('meta[name="viewport"]');
	const vpContent = vp?.getAttribute('content') ?? null;
	return {
		pageOverflowPx,
		overflowingElements,
		scrollableRegions,
		smallText,
		clippedContainers,
		pwaBanner,
		viewportMeta: vpContent,
		viewportFitCover: /viewport-fit\s*=\s*cover/.test(vpContent ?? ''),
		viewport: { width: window.innerWidth, height: window.innerHeight, dpr: window.devicePixelRatio },
	};
};

type LayoutResult = ReturnType<typeof LAYOUT_CHECK>;

/** Löst die Ziel-Detail-Routen über die API auf (Basic-Auth + storageState). */
async function resolveDetailRoutes(
	page: import('@playwright/test').Page,
	playwright: import('@playwright/test').Playwright
): Promise<{ trip: string | null; compare: string | null }> {
	// GZ_AUDIT_BASE erlaubt einen lokalen Lauf gegen den Preview-Server
	// (http://localhost:4173) — guards (prodUrlGuard) greifen unverändert.
	const base = process.env.GZ_AUDIT_BASE ?? 'https://staging.gregor20.henemm.com';
	const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
	let trip: string | null = null;
	let compare: string | null = null;
	try {
		const ctx = await playwright.request.newContext({
			baseURL: base,
			ignoreHTTPSErrors: true,
			httpCredentials: { username: user, password: pass },
			storageState: process.env.GZ_AUDIT_STORAGE ?? 'playwright/.auth/staging-mobile-usability.json',
		});
		const tripsRes = await ctx.get('/api/trips');
		if (tripsRes.ok()) {
			const body = (await tripsRes.json()) as { id?: string; name?: string }[];
			if (Array.isArray(body)) {
				// Bevorzugt: die API-geseedeten Audit-Trips (meiste Etappen).
				const audit = body.filter((t) => /^ma-/.test(t.id ?? '') || /Mobile Audit/.test(t.name ?? ''));
				const pick = audit.find((t) => t.id === 'ma-alpen-x') ?? audit[0] ?? body[0];
				if (pick?.id) trip = `/trips/${pick.id}`;
			}
		}
		const presetsRes = await ctx.get('/api/compare/presets');
		if (presetsRes.ok()) {
			const body = (await presetsRes.json()) as { id?: string; name?: string; location_ids?: string[] }[];
			if (Array.isArray(body) && body.length > 0) {
				// Bevorzugt: „Le Var" (8 Orte) oder „Zillertal" (5) — die größten Presets.
				const big = body
					.slice()
					.sort((a, b) => (b.location_ids?.length ?? 0) - (a.location_ids?.length ?? 0));
				const pick = big[0] ?? body[0];
				if (pick?.id) compare = `/compare/${pick.id}`;
			}
		}
		await ctx.dispose();
	} catch {
		trip = trip ?? null;
	}
	return { trip, compare };
}

test('mobile-usability audit aller Kern-Routen', async ({ page, playwright }, testInfo) => {
	const project = testInfo.project.name;
	const shotDir = path.join(OUT_ROOT, project);
	fs.mkdirSync(shotDir, { recursive: true });

	const { trip: tripHref, compare: compareHref } = await resolveDetailRoutes(page, playwright);
	const routes = ['/', '/trips'];
	if (tripHref) {
		routes.push(tripHref, `${tripHref}/edit`);
	} else {
		routes.push('/trips/__skipped__', '/trips/__skipped__/edit');
	}
	routes.push('/trips/new', '/compare', '/compare/new');
	if (compareHref) {
		routes.push(compareHref);
	} else {
		routes.push('/compare/__skipped__');
	}
	routes.push('/archiv', '/locations', '/account', '/settings', '/subscriptions');

	// Tab-Interaktionspläne pro Detailroute (Tab-Testids im Seiten-Code verankert).
	const tabsFor = (route: string): string[] => {
		if (/^\/trips\/[^/]+$/.test(route)) {
			return ['stages', 'weather', 'alerts', 'alarme', 'briefings', 'preview'];
		}
		if (/^\/compare\/[^/]+$/.test(route)) {
			return ['orte', 'wetter-metriken', 'idealwerte', 'alarme', 'versand', 'vorschau'];
		}
		return [];
	};
	const tabPrefix = (route: string) => (route.startsWith('/trips/') ? 'trip-detail-tab-' : 'compare-detail-tab-');

	const findings: LayoutFinding[] = [];
	const overflowRoutes: string[] = [];

	const writeReports = () => {
		fs.writeFileSync(
			path.join(OUT_ROOT, `report-${project}.json`),
			JSON.stringify({ project, generatedAt: new Date().toISOString(), routes: findings }, null, 2)
		);
		const lines = [`# Mobile-Usability-Report (${project})`, ''];
		for (const f of findings) {
			const label = f.view && f.view !== 'initial' ? `${f.route} [${f.view}]` : f.route;
			if (f.error) {
				lines.push(`- ❌ ${label}: LADEFEHLER — ${f.error}`);
			} else if (f.skipped) {
				lines.push(`- ⏭️ ${label}: übersprungen — ${f.skipped}`);
			} else {
				const ow = (f.overflowingElements as unknown[])?.length ?? 0;
				const sr = (f.scrollableRegions as unknown[])?.length ?? 0;
				const st = (f.smallText as unknown[])?.length ?? 0;
				const cc = (f.clippedContainers as unknown[])?.length ?? 0;
				const bad = (f.pageOverflowPx ?? 0) > 1;
				lines.push(
					`- ${bad ? '❌' : ow + sr + st + cc > 0 ? '⚠️' : '✅'} ${label}: page-overflow ${f.pageOverflowPx}px, ` +
						`${ow} überstehende, ${sr} scrollbare Regionen, ${st} Texte <11px, ${cc} Clipps, ` +
						`pwa-banner=${f.pwaBanner?.present ? `ja (deckt ${f.pwaBanner.coversInteractive} Interaktive)` : 'nein'}`
				);
			}
		}
		fs.writeFileSync(path.join(OUT_ROOT, `report-${project}.md`), lines.join('\n') + '\n');
	};

	const record = (route: string, view: string, result: LayoutResult) => {
		const finding: LayoutFinding = { route, view, ...result };
		findings.push(finding);
		if (result.pageOverflowPx > 1) overflowRoutes.push(`${route}${view !== 'initial' ? `#${view}` : ''}`);
	};

	const settle = async () => {
		await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
		await page.waitForTimeout(400);
	};

	for (const route of routes) {
		try {
			if (route.includes('__skipped__')) {
				findings.push({
					route,
					skipped: route.startsWith('/trips') ? 'kein Trip per API auflösbar' : 'kein Vergleich per API auflösbar',
				});
				writeReports();
				continue;
			}
			await page.goto(route, { waitUntil: 'load', timeout: 45_000 });
			// Svelte-Hydration abwarten: Body muss gerenderten Inhalt haben.
			await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 0, null, {
				timeout: 15_000,
			});
			await settle();

			record(route, 'initial', await page.evaluate(LAYOUT_CHECK));
			await page.screenshot({ path: path.join(shotDir, `${slug(route)}.png`), fullPage: true });

			// Tab-Interaktion auf Detailseiten: klicken, warten, Check + Screenshot.
			const prefix = tabPrefix(route);
			for (const tab of tabsFor(route)) {
				const tabBtn = page.getByTestId(`${prefix}${tab}`);
				if ((await tabBtn.count()) === 0) continue;
				const visible = await tabBtn.first().isVisible().catch(() => false);
				if (!visible) continue;
				await tabBtn.first().click();
				await settle();
				record(route, tab, await page.evaluate(LAYOUT_CHECK));
				await page.screenshot({ path: path.join(shotDir, `${slug(route)}__${tab}.png`), fullPage: true });
			}
		} catch (err) {
			findings.push({ route, error: err instanceof Error ? err.message.slice(0, 300) : String(err) });
		}
		writeReports();
	}

	// Harte Assertion nur auf Page-Level-H-Overflow; Warnungen bleiben im Report.
	if (overflowRoutes.length > 0) {
		throw new Error(
			`Page-level horizontaler Overflow (>1px) auf: ${overflowRoutes.join(', ')} — Details in report-${project}.md`
		);
	}
	expect(overflowRoutes, 'kein page-level horizontaler Overflow').toEqual([]);
});
