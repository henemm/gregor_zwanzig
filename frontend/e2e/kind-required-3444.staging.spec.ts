// E2E (Staging) — Issue #3444 (ADR-0130): gemeinsamer Katalogtext kind_required.
// Spec: docs/specs/modules/feat_3444_gemeinsamer_katalog.md — AC-1 (Go-API, Nutzer de und en)
//
//   Versand, Alarm-Vorschau und Platzierungen ohne bzw. mit ungueltiger Briefing-Art antworten
//   mit 400, code=kind_required und dem unveraenderten Wortlaut der Kontosprache. Erwartung ist
//   das Literal aus tests/fixtures/send_detail_parity/faelle.json (kind_required = de,
//   kind_required_en = en), nicht der Katalog. Die kind-Pruefung greift im Go-Handler vor jedem
//   Nachschlagen der Kennung; die Dummy-Kennung existiert nicht, nichts wird angelegt oder versandt.
//   Der en-Test setzt die Kontosprache auf en und stellt im finally die vorherige Sprache wieder her.
//
//   cd frontend && npx playwright test --config playwright.3444.staging.config.ts

import { test, expect, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FIXTURE = path.join(
	path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'tests', 'fixtures', 'send_detail_parity', 'faelle.json'
);
const soll: Record<string, string> = JSON.parse(readFileSync(FIXTURE, 'utf8'));
const DUMMY = 'e2e-3444-gibt-es-nicht';

const FAELLE: { name: string; aufruf: (r: APIRequestContext) => ReturnType<APIRequestContext['get']> }[] = [
	{ name: 'Versand ohne kind', aufruf: (r) => r.post(`/api/briefings/${DUMMY}/send`) },
	{ name: 'Alarm-Vorschau kind=trip', aufruf: (r) => r.post(`/api/briefings/${DUMMY}/alert-preview?kind=trip`, { data: {} }) },
	{ name: 'Platzierungen ohne kind', aufruf: (r) => r.get(`/api/briefings/${DUMMY}/placements`) }
];

async function pruefeFaelle(r: APIRequestContext, text: string, sprache: string) {
	expect(text, `Fixture-Wortlaut ${sprache} fehlt: ${FIXTURE}`).toBeTruthy();
	for (const f of FAELLE) {
		const res = await f.aufruf(r);
		const body = await res.json();
		expect(res.status(), `${sprache}/${f.name}: ${JSON.stringify(body)}`).toBe(400);
		expect(body.code, `${sprache}/${f.name}`).toBe('kind_required');
		expect(body.message, `${sprache}/${f.name}: message`).toBe(text);
		expect(body.detail, `${sprache}/${f.name}: detail`).toBe(text);
	}
}

async function kontosprache(r: APIRequestContext): Promise<string> {
	const res = await r.get('/api/auth/profile');
	expect(res.ok(), `Profil lesen: HTTP ${res.status()}`).toBeTruthy();
	return ((await res.json()).language as string) || 'de';
}

test('AC-1 (de): kind_required mit deutschem Fixture-Wortlaut', async ({ page }) => {
	const vorher = await kontosprache(page.request);
	try {
		const res = await page.request.put('/api/auth/profile', { data: { language: 'de' } });
		expect(res.ok(), `Sprache de setzen: HTTP ${res.status()}`).toBeTruthy();
		await pruefeFaelle(page.request, soll['kind_required'], 'de');
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: vorher } }).catch(() => {});
	}
});

test('AC-1 (en): kind_required mit englischem Fixture-Wortlaut', async ({ page }) => {
	const vorher = await kontosprache(page.request);
	try {
		const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
		expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
		await pruefeFaelle(page.request, soll['kind_required_en'], 'en');
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: vorher } }).catch(() => {});
	}
});
