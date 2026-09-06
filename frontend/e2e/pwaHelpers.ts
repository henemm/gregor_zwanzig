// Hilfsmittel fuer die PWA-Nachweise (Issue #2128, Epic #2127).
//
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
//
// Kein Test — wird von e2e/pwa-*.spec.ts benutzt. Alle Auskuenfte kommen aus
// echten Browser-Schnittstellen (`navigator.serviceWorker`, `caches`), nicht
// aus nachgebauten Doppeln.

import type { Page } from '@playwright/test';

export type CacheEntry = { cacheName: string; url: string; contentType: string };

/** Pfad der von global.setup.ts geschriebenen Anmeldung (relativ zu frontend/). */
export const AUTH_STATE = 'playwright/.auth/admin.json';

/**
 * Laedt `path`, wartet auf einen aktiven Service Worker und darauf, dass er die
 * Seite tatsaechlich kontrolliert. Ohne `clients.claim()` uebernimmt der Worker
 * erst beim naechsten Seitenaufruf — darum das Neuladen als zweiter Schritt.
 */
export async function activateServiceWorker(page: Page, path = '/'): Promise<void> {
	await page.goto(path);
	await page.waitForFunction(
		async () => {
			if (!('serviceWorker' in navigator)) return false;
			const reg = await navigator.serviceWorker.getRegistration();
			return !!reg?.active;
		},
		undefined,
		{ timeout: 30_000 }
	);
	const controlled = await page.evaluate(() => !!navigator.serviceWorker.controller);
	if (!controlled) {
		await page.reload();
		await page.waitForFunction(() => !!navigator.serviceWorker.controller, undefined, {
			timeout: 30_000
		});
	}
}

/** Namen aller Speicher im Gerätespeicher (CacheStorage). */
export async function cacheNames(page: Page): Promise<string[]> {
	return page.evaluate(() => caches.keys());
}

/** Jeder abgelegte Eintrag aus jedem Speicher, mit seinem Inhaltstyp. */
export async function readCacheEntries(page: Page): Promise<CacheEntry[]> {
	return page.evaluate(async () => {
		const out: { cacheName: string; url: string; contentType: string }[] = [];
		for (const cacheName of await caches.keys()) {
			const cache = await caches.open(cacheName);
			for (const request of await cache.keys()) {
				const response = await cache.match(request);
				out.push({
					cacheName,
					url: request.url,
					contentType: response?.headers.get('content-type') ?? ''
				});
			}
		}
		return out;
	});
}

/** Speicher- und Registrierungs-Stand in EINEM Zug gelesen (kein Zwischenstand). */
export async function storageAndRegistrationCount(
	page: Page
): Promise<{ caches: number; registrations: number }> {
	return page.evaluate(async () => ({
		caches: (await caches.keys()).length,
		registrations: (await navigator.serviceWorker.getRegistrations()).length
	}));
}

/**
 * Erzwingt einen echten Update-Durchlauf: dieselbe Worker-Datei unter einer
 * anderen Skript-URL registrieren. Der Browser sieht eine geaenderte Skript-URL
 * fuer denselben Geltungsbereich, installiert den Worker neu und feuert
 * `updatefound` auf der bestehenden Registrierung — genau der Weg, den auch
 * eine echte neue Programmversion nimmt.
 *
 * Rueckgabe: die neue Skript-URL (zum Vergleich der Kontrolle).
 */
export async function triggerServiceWorkerUpdate(page: Page): Promise<string> {
	const scriptUrl = `/service-worker.js?gz-e2e=${Date.now()}`;
	await page.evaluate(async (url) => {
		await navigator.serviceWorker.register(url);
	}, scriptUrl);
	await page.waitForFunction(
		async () => {
			const reg = await navigator.serviceWorker.getRegistration();
			return !!reg?.waiting;
		},
		undefined,
		{ timeout: 30_000 }
	);
	return scriptUrl;
}

/** Skript-URL des Workers, der die Seite gerade kontrolliert. */
export async function controllingScriptUrl(page: Page): Promise<string | null> {
	return page.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null);
}
