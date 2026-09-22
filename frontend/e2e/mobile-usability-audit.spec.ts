// Mobile-Usability-Audit gegen Staging — ein Durchlauf pro Browser-Projekt
// (iphone13/WebKit, chromium-390), der alle Kern-Routen auf Darstellungs-
// probleme prüft: horizontaler Page-Overflow, überstehende Elemente
// (Mini-Fenster), zu kleine Texte (<11px), abgeschnittene Fix-Höhen-
// Container, Viewport-Meta. Findings werden NACH JEDER Route in Report-Dateien
// geschrieben, damit ein Abbruch nichts verwirft.
//
// Assertion-Politik: Nur page-level horizontaler Overflow lässt den Test
// FEHLschlagen (klarer Bug). Alles andere ist Warnung im Report — der Audit
// soll Kleinkram sammeln, nicht abbrechen.
//
// Screenshots: test-results/mobile-usability/<projekt>/<route>.png
// Reports:     test-results/mobile-usability/report-<projekt>.json / .md

import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const OUT_ROOT = 'test-results/mobile-usability';

interface LayoutFinding {
	route: string;
	skipped?: string;
	pageOverflowPx?: number;
	overflowingElements?: unknown[];
	smallText?: unknown[];
	clippedContainers?: unknown[];
	viewportMeta?: string | null;
	viewportFitCover?: boolean;
	viewport?: { width: number; height: number; dpr: number };
	error?: string;
}

function slug(route: string): string {
	return route === '/' ? 'root' : route.replace(/^\//, '').replace(/\//g, '_');
}

/** Liest den ersten Link auf ein Detail-Objekt aus einer Übersichtsseite. */
async function firstDetailHref(page: import('@playwright/test').Page, listUrl: string, hrefRe: RegExp): Promise<string | null> {
	try {
		await page.goto(listUrl, { waitUntil: 'load', timeout: 30_000 });
		await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
		const href = await page.evaluate((reSrc) => {
			const re = new RegExp(reSrc);
			for (const a of document.querySelectorAll('a[href]')) {
				const h = a.getAttribute('href') ?? '';
				if (re.test(h)) return h;
			}
			return null;
		}, hrefRe.source);
		return href;
	} catch {
		return null;
	}
}

/**
 * Löst die ersten Detail-IDs (Trip, Compare-Preset) auf. Primär über die API
 * (Basic-Auth + storageState), Fallback: Link-Scan der Übersichtsseiten.
 * 'new' wird bei beiden Wegen ausgeschlossen — es ist kein Detail-Objekt.
 */
async function resolveDetailRoutes(page: import('@playwright/test').Page, playwright: import('@playwright/test').Playwright): Promise<{ trip: string | null; compare: string | null }> {
	const base = 'https://staging.gregor20.henemm.com';
	const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
	let trip: string | null = null;
	let compare: string | null = null;
	try {
		const ctx = await playwright.request.newContext({
			baseURL: base,
			ignoreHTTPSErrors: true,
			httpCredentials: { username: user, password: pass },
			storageState: 'playwright/.auth/staging-mobile-usability.json',
		});
		const trips = await ctx.get('/api/trips');
		if (trips.ok()) {
			const body = (await trips.json()) as { id?: string }[];
			if (Array.isArray(body) && body.length > 0 && body[0].id) trip = `/trips/${body[0].id}`;
		}
		const presets = await ctx.get('/api/compare/presets');
		if (presets.ok()) {
			const body = (await presets.json()) as { id?: string }[];
			if (Array.isArray(body) && body.length > 0 && body[0].id) compare = `/compare/${body[0].id}`;
		}
		await ctx.dispose();
	} catch {
		// Fallback unten.
	}
	if (!trip) trip = await firstDetailHref(page, '/trips', /^\/trips\/(?!new$)[^/]+$/);
	if (!compare) compare = await firstDetailHref(page, '/compare', /^\/compare\/(?!new$)[^/]+$/);
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

	const findings: LayoutFinding[] = [];
	let overflowRoutes: string[] = [];

	const writeReports = () => {
		fs.writeFileSync(
			path.join(OUT_ROOT, `report-${project}.json`),
			JSON.stringify({ project, generatedAt: new Date().toISOString(), routes: findings }, null, 2)
		);
		const lines = [`# Mobile-Usability-Report (${project})`, ''];
		for (const f of findings) {
			const label = f.route;
			if (f.error) {
				lines.push(`- ❌ ${label}: LADEFEHLER — ${f.error}`);
			} else if (f.skipped) {
				lines.push(`- ⏭️ ${label}: übersprungen — ${f.skipped}`);
			} else {
				const ow = (f.overflowingElements as unknown[])?.length ?? 0;
				const st = (f.smallText as unknown[])?.length ?? 0;
				const cc = (f.clippedContainers as unknown[])?.length ?? 0;
				const bad = (f.pageOverflowPx ?? 0) > 1;
				lines.push(
					`- ${bad ? '❌' : ow + st + cc > 0 ? '⚠️' : '✅'} ${label}: page-overflow ${f.pageOverflowPx}px, ` +
						`${ow} überstehende Elemente, ${st} Texte <11px, ${cc} Fix-Höhen-Clipps, ` +
						`viewport-fit=cover=${f.viewportFitCover}`
				);
			}
		}
		fs.writeFileSync(path.join(OUT_ROOT, `report-${project}.md`), lines.join('\n') + '\n');
	};

	for (const route of routes) {
		const finding: LayoutFinding = { route };
		try {
			if (route.includes('__skipped__')) {
				finding.skipped =
					route.startsWith('/trips') ? 'kein Trip in der Übersicht vorhanden' : 'kein Vergleich in der Übersicht vorhanden';
				findings.push(finding);
				writeReports();
				continue;
			}
			await page.goto(route, { waitUntil: 'load', timeout: 45_000 });
			// Svelte-Hydration abwarten: Netzwerk ruhig + Body hat gerenderten Inhalt.
			await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
			await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 0, null, {
				timeout: 15_000,
			});
			await page.waitForTimeout(400);

			const result = await page.evaluate(() => {
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
				const snip = (el: Element, n = 60) =>
					(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, n);

				const doc = document.documentElement;
				const se = document.scrollingElement ?? doc;
				const pageOverflowPx = Math.max(0, se.scrollWidth - window.innerWidth);

				const overflowingElements: unknown[] = [];
				let overflowTotal = 0;
				for (const el of Array.from(doc.querySelectorAll('*'))) {
					const cs = getComputedStyle(el);
					if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') continue;
					if (el.scrollWidth > el.clientWidth + 1) {
						overflowTotal++;
						if (overflowingElements.length < 15 && visible(el)) {
							const r = el.getBoundingClientRect();
							overflowingElements.push({
								selector: selOf(el),
								scrollWidth: el.scrollWidth,
								clientWidth: el.clientWidth,
								box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
								text: snip(el)
							});
						}
					}
				}

				const smallText: unknown[] = [];
				let smallTotal = 0;
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
					if (fontSize > 0 && fontSize < 11 && visible(el)) {
						smallTotal++;
						if (smallText.length < 15) {
							smallText.push({ selector: selOf(el), fontSize, text: text.slice(0, 60) });
						}
					}
				}

				const clippedContainers: unknown[] = [];
				for (const el of Array.from(doc.querySelectorAll('body *'))) {
					const cs = getComputedStyle(el);
					if (cs.overflowY !== 'hidden') continue;
					if (el.scrollHeight > el.clientHeight + 4 && visible(el)) {
						const r = el.getBoundingClientRect();
						clippedContainers.push({
							selector: selOf(el),
							scrollHeight: el.scrollHeight,
							clientHeight: el.clientHeight,
							box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
							text: snip(el)
						});
						if (clippedContainers.length >= 15) break;
					}
				}

				const vp = document.querySelector('meta[name="viewport"]');
				const vpContent = vp?.getAttribute('content') ?? null;
				return {
					pageOverflowPx,
					overflowTotal,
					overflowingElements,
					smallTotal,
					smallText,
					clippedContainers,
					viewportMeta: vpContent,
					viewportFitCover: /viewport-fit\s*=\s*cover/.test(vpContent ?? ''),
					viewport: { width: window.innerWidth, height: window.innerHeight, dpr: window.devicePixelRatio },
				};
			});

			Object.assign(finding, result);
			if (result.pageOverflowPx > 1) overflowRoutes.push(route);
			await page.screenshot({ path: path.join(shotDir, `${slug(route)}.png`), fullPage: true });
		} catch (err) {
			finding.error = err instanceof Error ? err.message.slice(0, 300) : String(err);
		}
		findings.push(finding);
		writeReports();
	}

	// Harte Assertion nur auf Page-Level-H-Overflow; Warnungen bleiben im Report.
	if (overflowRoutes.length > 0) {
		throw new Error(`Page-level horizontaler Overflow (>1px) auf: ${overflowRoutes.join(', ')} — Details in report-${project}.md`);
	}
	expect(overflowRoutes, 'kein page-level horizontaler Overflow').toEqual([]);
});
