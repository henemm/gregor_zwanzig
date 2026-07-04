import type { ApiError, Stage } from './types.js';

async function request<T>(method: string, path: string, body?: unknown, extra?: RequestInit): Promise<T> {
	const opts: RequestInit = {
		method,
		headers: { 'Content-Type': 'application/json' },
		...extra
	};
	if (body !== undefined) {
		opts.body = JSON.stringify(body);
	}
	const res = await fetch(path, opts);
	if (!res.ok) {
		// Issue #1006 — Sitzung abgelaufen (24h-TTL): zentral behandeln statt die
		// rohe {"error":"unauthorized"}-Meldung an Aufrufer durchzureichen.
		if (res.status === 401 && typeof window !== 'undefined') {
			const redirectTarget = window.location.pathname + window.location.search;
			window.location.href = `/login?expired=1&redirect=${encodeURIComponent(redirectTarget)}`;
			throw new Error('Sitzung abgelaufen — bitte neu anmelden.');
		}
		const err: ApiError = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
		throw err;
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
	put: <T>(path: string, body: unknown, extra?: RequestInit) => request<T>('PUT', path, body, extra),
	patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
	del: (path: string) => request<void>('DELETE', path)
};

export async function uploadGpx(
	file: File,
	stageDate: string,
	startHour: number
): Promise<Stage> {
	// Python FastAPI endpoint reads stage_date / start_hour from query params
	// (see api/routers/gpx.py); the file goes via multipart body.
	const form = new FormData();
	form.append('file', file);

	const params = new URLSearchParams();
	if (stageDate) params.set('stage_date', stageDate);
	params.set('start_hour', String(startHour));

	const res = await fetch(`/api/gpx/parse?${params.toString()}`, {
		method: 'POST',
		body: form
	});
	if (!res.ok) {
		const detail = await res.text();
		throw new Error(`GPX parse failed: ${detail}`);
	}
	return res.json() as Promise<Stage>;
}
