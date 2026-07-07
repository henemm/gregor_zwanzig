import { env } from '$env/dynamic/private';

/** Basis-URL des Go-Backends; überschreibbar via GZ_API_BASE. */
export function apiBase(): string {
	return env.GZ_API_BASE ?? 'http://localhost:8090';
}
