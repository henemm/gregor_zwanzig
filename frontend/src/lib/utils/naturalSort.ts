/**
 * Natural sort helpers — order strings with embedded integers numerically
 * so "KHW_10" sorts AFTER "KHW_2" instead of lexicographically before it.
 *
 * Mirror of `src/core/natural_sort.py::natural_sort_key()` for the
 * SvelteKit-Frontend (Spec: docs/specs/modules/gpx_multi_import.md v1.1).
 */

/**
 * Build a sort key for a string by splitting it into alternating
 * non-digit and digit chunks. Digit chunks become integers; text chunks
 * are lower-cased so the sort is case-insensitive.
 *
 * Examples:
 *   naturalSortKey('KHW_10') -> ['khw_', 10, '']
 *   naturalSortKey('KHW_00a') -> ['khw_', 0, 'a']
 */
export function naturalSortKey(s: string): Array<string | number> {
	// /(\d+)/ with capturing group keeps numeric runs as separate parts.
	// Even indices (0, 2, ...) are non-digit text; odd indices are digit runs.
	const parts = s.split(/(\d+)/);
	return parts.map((part, i) =>
		i % 2 === 1 ? parseInt(part, 10) : part.toLowerCase()
	);
}

/**
 * Stable sort of `arr` by the natural-sort key derived from `key(item)`.
 * Returns a new array — does not mutate the input.
 */
export function naturalSort<T>(arr: T[], key: (item: T) => string): T[] {
	const decorated = arr.map((item, idx) => ({
		item,
		idx,
		sortKey: naturalSortKey(key(item))
	}));
	decorated.sort((a, b) => {
		const ka = a.sortKey;
		const kb = b.sortKey;
		const len = Math.max(ka.length, kb.length);
		for (let i = 0; i < len; i++) {
			const xa = ka[i];
			const xb = kb[i];
			if (xa === undefined && xb === undefined) continue;
			if (xa === undefined) return -1;
			if (xb === undefined) return 1;
			// Mixed string/number: compare via string repr to remain total-orderable.
			if (typeof xa !== typeof xb) {
				const sa = String(xa);
				const sb = String(xb);
				if (sa < sb) return -1;
				if (sa > sb) return 1;
				continue;
			}
			if (xa < xb) return -1;
			if (xa > xb) return 1;
		}
		return a.idx - b.idx; // stability for equal keys
	});
	return decorated.map((d) => d.item);
}
