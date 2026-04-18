import type { ApiError, Stage } from './types.js';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const opts: RequestInit = {
		method,
		headers: { 'Content-Type': 'application/json' }
	};
	if (body !== undefined) {
		opts.body = JSON.stringify(body);
	}
	const res = await fetch(path, opts);
	if (!res.ok) {
		const err: ApiError = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
		throw err;
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
	put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
	del: (path: string) => request<void>('DELETE', path)
};

export async function uploadGpx(
	file: File,
	stageDate: string,
	startHour: number
): Promise<Stage> {
	const form = new FormData();
	form.append('file', file);
	form.append('stage_date', stageDate);
	form.append('start_hour', String(startHour));

	const res = await fetch('/api/gpx/parse', { method: 'POST', body: form });
	if (!res.ok) {
		const detail = await res.text();
		throw new Error(`GPX parse failed: ${detail}`);
	}
	return res.json() as Promise<Stage>;
}
