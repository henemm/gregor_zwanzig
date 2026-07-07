import type { LayoutServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: LayoutServerLoad = async ({ locals, cookies }) => {
	// Issue #642 — Anzeigename für die Seitenleiste durchreichen.
	let displayName: string | null = null;
	if (locals.userId) {
		const session = cookies.get('gz_session');
		const profile = await fetch(`${API()}/api/auth/profile`, {
			headers: { Cookie: `gz_session=${session}` }
		})
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
		displayName = profile?.display_name ?? null;
	}

	return {
		userId: locals.userId,
		displayName
	};
};
