<script lang="ts">
	// Issue #440 — Step 2: Smart-Import + Library + Auswahl-Counter.
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §7
	import { getContext } from 'svelte';
	import { api } from '$lib/api';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import type { Location } from '$lib/types';

	interface Props {
		locations: Location[];
	}
	let { locations }: Props = $props();

	const state = getContext<CompareWizardState>('compare-wizard-state');

	interface ResolveResult {
		lat: number;
		lon: number;
		elevation_m?: number;
		timezone: string;
		suggested_name?: string;
		region?: string;
		source_type: string;
	}

	let importInput = $state('');
	let resolving = $state(false);
	let preview = $state<ResolveResult | null>(null);
	let resolveError = $state<string | null>(null);
	let adding = $state(false);
	let fallbackLat = $state('');
	let fallbackLon = $state('');

	// F002: $derived.by(fn) ist Svelte-5-Form für berechnete Werte mit
	// Funktions-Body. $derived(() => {...}) würde die Funktion selbst speichern,
	// nicht ihr Ergebnis.
	const counterText = $derived.by(() => {
		const n = state.pickedIds.length;
		if (n < 2) return 'min. 2 Orte nötig';
		if (n <= 5) return 'passt';
		return 'viel — Empfehlung 3–5';
	});

	async function resolve() {
		if (!importInput.trim()) return;
		resolving = true;
		resolveError = null;
		preview = null;
		try {
			preview = await api.post<ResolveResult>('/api/locations/resolve', {
				input: importInput
			});
		} catch (e: unknown) {
			resolveError = extractMsg(e) ?? 'Format nicht erkannt';
		} finally {
			resolving = false;
		}
	}

	async function addLocation() {
		if (!preview) return;
		adding = true;
		try {
			const loc = await api.post<Location>('/api/locations', {
				name: preview.suggested_name ?? importInput,
				lat: preview.lat,
				lon: preview.lon,
				elevation_m: preview.elevation_m,
				timezone: preview.timezone,
				region: preview.region
			});
			state.pickedIds = [...state.pickedIds, loc.id];
			importInput = '';
			preview = null;
		} catch (e: unknown) {
			resolveError = extractMsg(e) ?? 'Fehler beim Hinzufügen';
		} finally {
			adding = false;
		}
	}

	async function addLocationFromFallback() {
		const lat = parseFloat(fallbackLat);
		const lon = parseFloat(fallbackLon);
		if (isNaN(lat) || isNaN(lon)) return;
		adding = true;
		try {
			const loc = await api.post<Location>('/api/locations', {
				name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
				lat,
				lon
			});
			state.pickedIds = [...state.pickedIds, loc.id];
			importInput = '';
			resolveError = null;
			fallbackLat = '';
			fallbackLon = '';
		} catch (e: unknown) {
			resolveError = extractMsg(e) ?? 'Fehler beim Hinzufügen';
		} finally {
			adding = false;
		}
	}

	function togglePick(id: string) {
		if (state.pickedIds.includes(id)) {
			state.pickedIds = state.pickedIds.filter((x) => x !== id);
		} else {
			state.pickedIds = [...state.pickedIds, id];
		}
	}

	function extractMsg(e: unknown): string | null {
		if (e && typeof e === 'object') {
			const obj = e as Record<string, unknown>;
			return (
				(typeof obj.detail === 'string' && obj.detail) ||
				(typeof obj.message === 'string' && obj.message) ||
				null
			);
		}
		return null;
	}
</script>

<div data-testid="compare-wizard-step-2" class="space-y-6">
	<div class="grid grid-cols-[1fr_1fr] gap-6">
		<!-- Smart-Import Panel -->
		<div class="space-y-3">
			<p class="text-xs font-mono uppercase tracking-wide text-[var(--g-ink-muted)]">
				Smart-Import
			</p>
			<div class="flex gap-2">
				<input
					data-testid="compare-step2-smart-import-input"
					type="text"
					class="flex-1 border rounded px-3 py-2 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
					placeholder="Komoot-URL, Google Maps oder Koordinaten"
					bind:value={importInput}
				/>
				<button
					data-testid="compare-step2-resolve-btn"
					type="button"
					disabled={resolving || !importInput.trim()}
					onclick={resolve}
					class="px-3 py-2 rounded border border-[var(--g-ink-faint)] text-sm hover:border-[var(--g-accent)] disabled:opacity-40"
				>
					{resolving ? '…' : 'Auflösen'}
				</button>
			</div>

			{#if resolveError}
				<p class="text-xs text-[var(--g-danger)]">{resolveError}</p>
			{/if}

			{#if resolveError}
				<div class="space-y-2 mt-2">
					<p class="text-xs text-[var(--g-ink-muted)]">Koordinaten manuell eingeben:</p>
					<div class="flex gap-2">
						<input
							data-testid="compare-step2-fallback-lat"
							type="number"
							step="any"
							placeholder="Breitengrad (z.B. 47.2692)"
							bind:value={fallbackLat}
							class="flex-1 border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
						/>
						<input
							data-testid="compare-step2-fallback-lon"
							type="number"
							step="any"
							placeholder="Längengrad (z.B. 11.4041)"
							bind:value={fallbackLon}
							class="flex-1 border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
						/>
					</div>
					<button
						data-testid="compare-step2-fallback-add-btn"
						type="button"
						disabled={adding || !fallbackLat || !fallbackLon}
						onclick={addLocationFromFallback}
						class="px-3 py-1 text-xs rounded bg-[var(--g-accent)] text-white disabled:opacity-40"
					>
						{adding ? 'Wird hinzugefügt…' : 'Hinzufügen'}
					</button>
				</div>
			{/if}

			{#if preview}
				<div class="p-3 rounded bg-[var(--g-ink-faint)]/10 text-sm space-y-1">
					<p class="font-medium">{preview.suggested_name ?? '(kein Name)'}</p>
					<p class="text-[var(--g-ink-muted)]">
						{preview.lat.toFixed(4)}, {preview.lon.toFixed(4)}
					</p>
					{#if preview.elevation_m !== undefined}
						<p class="text-[var(--g-ink-muted)]">Höhe: {preview.elevation_m} m</p>
					{/if}
					<p class="text-[var(--g-ink-muted)]">Zeitzone: {preview.timezone}</p>
					<button
						type="button"
						disabled={adding}
						onclick={addLocation}
						class="mt-2 px-3 py-1 text-xs rounded bg-[var(--g-accent)] text-white disabled:opacity-40"
					>
						{adding ? 'Wird hinzugefügt…' : 'Hinzufügen'}
					</button>
				</div>
			{/if}
		</div>

		<!-- Library-Liste -->
		<div class="space-y-2">
			<p class="text-xs font-mono uppercase tracking-wide text-[var(--g-ink-muted)]">
				Gespeicherte Orte
			</p>
			{#if locations.length === 0}
				<p class="text-sm text-[var(--g-ink-muted)]">Noch keine Orte gespeichert.</p>
			{:else}
				<ul data-testid="compare-step2-library" class="space-y-1">
					{#each locations as loc (loc.id)}
						<li class="flex items-center gap-2">
							<input
								type="checkbox"
								id={`loc-${loc.id}`}
								checked={state.pickedIds.includes(loc.id)}
								onchange={() => togglePick(loc.id)}
								class="rounded"
							/>
							<label for={`loc-${loc.id}`} class="text-sm cursor-pointer">{loc.name}</label>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>

	<!-- Counter -->
	<div
		data-testid="compare-step2-counter"
		class={`text-sm font-medium ${
			state.pickedIds.length < 2
				? 'text-[var(--g-danger)]'
				: state.pickedIds.length <= 5
					? 'text-[var(--g-good)]'
					: 'text-[var(--g-ink-muted)]'
		}`}
	>
		{state.pickedIds.length}
		{state.pickedIds.length === 1 ? 'Ort' : 'Orte'} ausgewählt —
		{counterText}
	</div>
</div>
