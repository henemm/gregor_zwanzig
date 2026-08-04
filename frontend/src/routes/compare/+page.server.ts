import type { PageServerLoad } from './$types.js';
import type { ComparePreset } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	// Issue #1471 — Konto-Profil fuer den Sende-Dialog (tatsaechliches Versandziel).
	// Muster aus compare/new/+page.server.ts:9-26: Session-Cookie durchreichen, die
	// User-ID leitet der Go-Handler daraus ab; das Frontend baut NIE einen
	// user_id-Parameter. Fail-soft: profile = null.
	const [presetsRes, profileRes] = await Promise.all([
		fetch(`${API()}/api/compare/presets`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null)
	]);

	const profile = profileRes?.ok ? await profileRes.json() : null;
	const rawPresets = presetsRes?.ok ? await presetsRes.json() : [];
	const all: ComparePreset[] = Array.isArray(rawPresets)
		? rawPresets
		: (rawPresets?.presets ?? []);

	// Issue #611 — archivierte Vergleiche erscheinen nicht in der aktiven Liste.
	const presets = all.filter((p) => p.archived_at == null);

	return { presets, profile };
};
