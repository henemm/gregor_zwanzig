import type { PageServerLoad } from './$types.js';
import type { ComparePreset } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const presetsRes = await fetch(`${API()}/api/compare/presets`, { headers }).catch(() => null);
	const rawPresets = presetsRes?.ok ? await presetsRes.json() : [];
	const all: ComparePreset[] = Array.isArray(rawPresets)
		? rawPresets
		: (rawPresets?.presets ?? []);

	// Issue #611 — archivierte Vergleiche erscheinen nicht in der aktiven Liste.
	const presets = all.filter((p) => p.archived_at == null);

	return { presets };
};
