import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Location } from '$lib/types.js';

// Issue #440 — Compare-Wizard Create-Modus.
// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §9
//
// Laedt nur die Locations-Library fuer Step 2; State bleibt leer (kein Prefill).

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;
	const res = await fetch(`${API()}/api/locations`, { headers }).catch(() => null);
	const locations: Location[] = res?.ok ? await res.json() : [];
	return { locations: Array.isArray(locations) ? locations : [] };
};
