import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const resp = await fetch(`${API()}/api/auth/profile`, {
		headers: { Cookie: `gz_session=${session}` },
	}).catch(() => null);
	if (!resp?.ok) return { profile: null };
	const profile = await resp.json();
	return { profile };
};
