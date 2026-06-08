import { env } from '$env/dynamic/private';
import type { LayoutServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

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
