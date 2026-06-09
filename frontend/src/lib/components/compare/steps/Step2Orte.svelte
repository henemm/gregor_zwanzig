<script lang="ts">
	// Issue #440 — Step 2: Smart-Import + Library + Auswahl-Counter.
	// Issue #680 — Slice 3: CE_OrteTab-Fidelity (nummerierte Picked-Liste, Region-Gruppen, Counter).
	// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
	import { getContext } from 'svelte';
	import { api } from '$lib/api';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import type { Location } from '$lib/types';

	interface Props {
		locations: Location[];
	}
	let { locations }: Props = $props();

	const ws = getContext<CompareWizardState>('compare-wizard-state');

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

	// AC-2: Counter-Text nach CE_OrteTab-Fidelity
	const counterText = $derived.by(() => {
		const n = ws.pickedIds.length;
		if (n < 2) return 'min. 2 erforderlich';
		if (n <= 5) return 'passt';
		return 'viel — Empfehlung 3–5';
	});

	const counterColor = $derived(
		ws.pickedIds.length < 2 ? 'var(--g-warn)' : 'var(--g-ink-4)'
	);

	// Picked-Orte aus der Locations-Liste aufgelöst
	const pickedLocations = $derived(
		ws.pickedIds.map((id) => locations.find((l) => l.id === id)).filter(Boolean) as Location[]
	);

	// AC-3: Bibliotheks-Grid nach Region gruppiert
	const libraryGroups = $derived.by(() => {
		const groups: Record<string, Location[]> = {};
		for (const loc of locations) {
			const groupKey = loc.region || 'Weitere';
			if (!groups[groupKey]) groups[groupKey] = [];
			groups[groupKey].push(loc);
		}
		// Sortierung: "Weitere" immer ans Ende
		const sorted: [string, Location[]][] = [];
		for (const [key, locs] of Object.entries(groups)) {
			if (key !== 'Weitere') sorted.push([key, locs]);
		}
		if (groups['Weitere']) sorted.push(['Weitere', groups['Weitere']]);
		return sorted;
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
			ws.pickedIds = [...ws.pickedIds, loc.id];
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
			ws.pickedIds = [...ws.pickedIds, loc.id];
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
		if (ws.pickedIds.includes(id)) {
			ws.pickedIds = ws.pickedIds.filter((x) => x !== id);
		} else {
			ws.pickedIds = [...ws.pickedIds, id];
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

<div data-testid="compare-wizard-step-2" style="position:relative; padding:28px 40px 60px; max-width:980px;">
	<div style="display:grid; grid-template-columns:1fr 1fr; gap:24px; margin-bottom:28px;">
		<!-- Smart-Import Panel -->
		<div>
			<div style="font-family:var(--g-font-mono); font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--g-ink-3); font-weight:600; margin-bottom:14px;">Neuen Ort hinzufügen</div>
			<div style="padding:16px 16px 14px; background:var(--g-card); border:1px solid var(--g-rule); border-radius:var(--g-r-3);">
				<div style="margin-bottom:10px;">
					<div style="font-size:11px; color:var(--g-ink-4); margin-bottom:6px;">Smart-Import · URL aus Komoot/Google Maps oder Koordinaten</div>
					<div style="display:flex; align-items:center; gap:10px;">
						<input
							data-testid="compare-step2-smart-import-input"
							type="text"
							placeholder="Komoot-URL, Google Maps oder Koordinaten"
							bind:value={importInput}
							style="flex:1; padding:8px 10px; font-size:13px; border:1px solid var(--g-rule); border-radius:var(--g-r-2); background:var(--g-paper); font-family:var(--g-font-sans); color:var(--g-ink);"
						/>
						<button
							data-testid="compare-step2-resolve-btn"
							type="button"
							disabled={resolving || !importInput.trim()}
							onclick={resolve}
							style="padding:8px 14px; font-size:13px; border:1px solid var(--g-rule); border-radius:var(--g-r-2); background:transparent; cursor:pointer; font-family:var(--g-font-sans); color:var(--g-ink); opacity:{resolving || !importInput.trim() ? '0.4' : '1'};"
						>{resolving ? '…' : 'Auflösen'}</button>
					</div>
				</div>

				{#if resolveError}
					<p style="font-size:12px; color:var(--g-danger); margin:4px 0;">{resolveError}</p>
					<!-- Fallback: manuelle Koordinaten -->
					<div style="margin-top:10px;">
						<div style="font-size:11px; color:var(--g-ink-4); margin-bottom:6px;">Koordinaten manuell eingeben:</div>
						<div style="display:flex; gap:8px; margin-bottom:6px;">
							<input
								data-testid="compare-step2-fallback-lat"
								type="number"
								step="any"
								placeholder="Breitengrad (z.B. 47.2692)"
								bind:value={fallbackLat}
								style="flex:1; padding:6px 8px; font-size:12px; border:1px solid var(--g-rule); border-radius:var(--g-r-2); background:var(--g-paper); font-family:var(--g-font-sans);"
							/>
							<input
								data-testid="compare-step2-fallback-lon"
								type="number"
								step="any"
								placeholder="Längengrad (z.B. 11.4041)"
								bind:value={fallbackLon}
								style="flex:1; padding:6px 8px; font-size:12px; border:1px solid var(--g-rule); border-radius:var(--g-r-2); background:var(--g-paper); font-family:var(--g-font-sans);"
							/>
						</div>
						<button
							data-testid="compare-step2-fallback-add-btn"
							type="button"
							disabled={adding || !fallbackLat || !fallbackLon}
							onclick={addLocationFromFallback}
							style="padding:5px 12px; font-size:12px; border-radius:var(--g-r-2); background:var(--g-accent); color:#fff; border:none; cursor:pointer; opacity:{adding || !fallbackLat || !fallbackLon ? '0.4' : '1'};"
						>{adding ? 'Wird hinzugefügt…' : 'Hinzufügen'}</button>
					</div>
				{/if}

				{#if preview}
					<div style="padding:10px 12px; background:var(--g-paper-deep); border-radius:var(--g-r-2); margin-bottom:10px; margin-top:8px;">
						<div style="font-family:var(--g-font-mono); font-size:10px; color:var(--g-ink-4); letter-spacing:0.06em; text-transform:uppercase; margin-bottom:4px;">Erkannt</div>
						<div style="font-size:13px; font-weight:600; color:var(--g-ink);">{preview.suggested_name ?? '(kein Name)'}</div>
						<div style="font-family:var(--g-font-mono); font-size:11px; color:var(--g-ink-3); margin-top:2px;">{preview.lat.toFixed(4)}, {preview.lon.toFixed(4)}{preview.elevation_m !== undefined ? ` · ${preview.elevation_m} m` : ''}</div>
					</div>
					<button
						type="button"
						disabled={adding}
						onclick={addLocation}
						style="width:100%; padding:8px; font-size:13px; border-radius:var(--g-r-2); background:var(--g-accent); color:#fff; border:none; cursor:pointer; font-family:var(--g-font-sans); opacity:{adding ? '0.4' : '1'};"
					>{adding ? 'Wird hinzugefügt…' : '＋ Zum Vergleich hinzufügen'}</button>
				{/if}
			</div>
		</div>

		<!-- Picked-Liste (rechte Spalte) — AC-1/AC-2 -->
		<div>
			<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:14px;">
				<div style="font-family:var(--g-font-mono); font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--g-ink-3); font-weight:600;">Im Vergleich · {pickedLocations.length}</div>
				<span
					data-testid="compare-step2-counter"
					style="font-family:var(--g-font-mono); font-size:10.5px; color:{counterColor}; letter-spacing:0.04em;"
				>{counterText}</span>
			</div>

			<div data-testid="compare-step2-picked-list">
				{#if pickedLocations.length === 0}
					<div style="padding:28px 18px; border:1px dashed var(--g-rule); border-radius:var(--g-r-2); text-align:center; color:var(--g-ink-3); font-size:13px; line-height:1.6;">
						Noch keine Orte.<br/>
						<span style="font-family:var(--g-font-mono); font-size:11px; color:var(--g-ink-4);">links hinzufügen oder unten auswählen</span>
					</div>
				{:else}
					<div style="display:flex; flex-direction:column; gap:6px;">
						{#each pickedLocations as loc, i (loc.id)}
							<div
								data-testid={`compare-step2-picked-item-${loc.id}`}
								style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:var(--g-card); border:1px solid var(--g-rule); border-radius:var(--g-r-2);"
							>
								<span style="width:22px; height:22px; border-radius:4px; background:var(--g-ink); color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; flex-shrink:0; font-family:var(--g-font-mono);">{i + 1}</span>
								<div style="flex:1; min-width:0;">
									<div style="font-size:13px; font-weight:600; color:var(--g-ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{loc.name}</div>
									<div style="font-family:var(--g-font-mono); font-size:10.5px; color:var(--g-ink-4); margin-top:1px;">{loc.region ?? '—'} · {loc.elevation_m ?? '–'} m</div>
								</div>
								<button
									data-testid={`compare-step2-picked-remove-${loc.id}`}
									type="button"
									onclick={() => { ws.pickedIds = ws.pickedIds.filter((x) => x !== loc.id); }}
									style="background:transparent; border:none; padding:6px; color:var(--g-ink-4); cursor:pointer; font-size:12px;"
								>✕</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Bibliothek: Region-Gruppiert (AC-3) -->
	<div data-testid="compare-step2-library">
	<div style="font-family:var(--g-font-mono); font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--g-ink-3); font-weight:600; margin-bottom:12px;">… oder aus gespeicherten Orten wählen</div>

	{#if locations.length === 0}
		<p style="font-size:13px; color:var(--g-ink-4);">Noch keine Orte gespeichert.</p>
	{:else}
		<div
			style="background:var(--g-card); border:1px solid var(--g-rule); border-radius:var(--g-r-3); padding:14px 18px;"
		>
			<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:18px;">
				{#each libraryGroups as [groupName, groupLocs] (groupName)}
					<div>
						<div style="font-family:var(--g-font-mono); font-size:10px; letter-spacing:0.10em; text-transform:uppercase; color:var(--g-ink-3); font-weight:600; padding:0 0 8px; margin-bottom:4px; border-bottom:1px solid var(--g-rule-soft);">
							{groupName} · {groupLocs.length}
						</div>
						<div style="display:flex; flex-direction:column; gap:4px;">
							{#each groupLocs as loc (loc.id)}
								{@const on = ws.pickedIds.includes(loc.id)}
								<button
									type="button"
									onclick={() => togglePick(loc.id)}
									style="display:flex; align-items:center; gap:8px; padding:6px 8px; background:{on ? 'var(--g-accent-tint)' : 'transparent'}; border:none; border-radius:var(--g-r-2); cursor:pointer; text-align:left; font-family:var(--g-font-sans);"
								>
									<span style="width:14px; height:14px; border-radius:3px; border:1.5px solid {on ? 'var(--g-accent)' : 'var(--g-rule)'}; background:{on ? 'var(--g-accent)' : 'transparent'}; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
										{#if on}
											<svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>
										{/if}
									</span>
									<span style="flex:1; font-size:12.5px; color:var(--g-ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{loc.name}</span>
								</button>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
	</div>
</div>
