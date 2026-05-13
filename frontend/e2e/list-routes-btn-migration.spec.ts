// TDD: Issue #215 Sprint 3 — Listen-Routen: Button → Btn Migration.
//
// Spec: docs/specs/modules/issue_215_sprint3_list_routes.md
//
// Verifiziert pro Datei (AC-1):
//   - `import { Btn } from '$lib/components/ui/btn/index.js'` vorhanden
//   - kein `import { Button } from '$lib/components/ui/button/...'` mehr
//   - keine `<Button>`-Tags mehr im Source

import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const FILES = [
	'frontend/src/routes/trips/+page.svelte',
	'frontend/src/routes/subscriptions/+page.svelte',
	'frontend/src/routes/locations/+page.svelte',
	'frontend/src/routes/compare/+page.svelte',
	'frontend/src/routes/gpx-upload/+page.svelte',
	'frontend/src/routes/weather/+page.svelte',
	'frontend/src/routes/+page.svelte',
];

test.describe('Issue #215 Sprint 3 — List-Routes Button→Btn', () => {
	for (const file of FILES) {
		test(`Migration (${file.split('/').slice(-2).join('/')})`, async () => {
			const content = await readFile(`/home/hem/gregor_zwanzig/${file}`, 'utf-8');
			expect(content).toContain(`import { Btn } from '$lib/components/ui/btn/index.js'`);
			expect(content).not.toContain(`import { Button } from '$lib/components/ui/button`);
			expect(content).not.toMatch(/<Button[\s>]/);
			expect(content).not.toMatch(/<\/Button>/);
		});
	}
});
