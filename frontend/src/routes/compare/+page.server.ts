import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { ComparePreset } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const presetsRes = await fetch(`${API()}/api/compare/presets`, { headers }).catch(() => null);
	const rawPresets = presetsRes?.ok ? await presetsRes.json() : [];
	const presets: ComparePreset[] = Array.isArray(rawPresets)
		? rawPresets
		: (rawPresets?.presets ?? []);

	return { presets };
};
