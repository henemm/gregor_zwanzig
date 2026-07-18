<script lang="ts">
	// Epic #138 Issue #177 — Dialog "Als Preset speichern". POST /api/metric-presets.
	// Issue #343 — ZEITHORIZONTE-Box: Eyebrow + Wording-Heuristik + Dot-Pattern;
	//              Save-Payload sendet metrics[] mit horizons mit (Schema #342).
	// Issue #587 — Custom Fixed-Overlay statt shadcn Dialog (screen-metrics-editor.jsx Z. 641–680).
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §6
	//       docs/specs/modules/issue_343_horizon_chip_ui.md §5

	import { api } from '$lib/api.js';
	import type { MetricPreset, Horizons, MetricEntry } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Btn, Eyebrow } from '$lib/components/atoms';
	import { computeHorizonSummary, dotsForHorizons } from '$lib/utils/horizonHelpers';
	import { buildBucketSummary, type Buckets } from '../../trip-detail/metricsEditor.ts';

	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		open: boolean;
		enabledMap: Record<string, boolean>;
		friendlyMap: Record<string, boolean>;
		horizonsMap: Record<string, Horizons>;
		catalog: MetricCatalog;
		indicatorCapable: (id: string) => boolean;
		onClose: () => void;
		onSaved: (preset: MetricPreset) => void;
		// Issue #365 — optional: bucket-bewusste Zusammenfassung (Spalten/Detail/Skala).
		buckets?: Buckets;
		// Issue #690 — client-seitige Eindeutigkeitsprüfung (case-insensitive, getrimmt).
		existingNames?: string[];
	}

	let {
		open = $bindable(false),
		enabledMap,
		friendlyMap,
		horizonsMap,
		catalog,
		indicatorCapable,
		onClose,
		onSaved,
		buckets,
		existingNames = [],
	}: Props = $props();

	// Issue #365 — Spalten/Detail/Skala-Zähler (nur wenn Buckets übergeben).
	const bucketSummary = $derived(buckets ? buildBucketSummary(buckets, friendlyMap) : null);

	let name = $state('');
	let description = $state('');
	let isDefault = $state(false);
	let saving = $state(false);
	let error: string | null = $state(null);

	const allMetrics = $derived.by(() => {
		const out: MetricEntry[] = [];
		for (const ms of Object.values(catalog)) {
			for (const m of ms) out.push(m);
		}
		return out;
	});

	const enabledMetrics = $derived(allMetrics.filter((m) => enabledMap[m.id]));
	const enabledIds = $derived(enabledMetrics.map((m) => m.id));
	const indicatorCount = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && friendlyMap[id]).length,
	);
	const rawCount = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && !friendlyMap[id]).length,
	);

	// Issue #343 — Wording-Heuristik + Dot-Pattern fuer ZEITHORIZONTE-Box
	const horizonSummary = $derived(
		computeHorizonSummary(
			enabledMetrics.map((m) => ({
				metric_id: m.id,
				horizons: horizonsMap[m.id] ?? HORIZONS_ALL,
				enabled: true,
			})),
		),
	);

	const canSubmit = $derived(name.trim().length > 0 && !saving);

	function reset() {
		name = '';
		description = '';
		isDefault = false;
		saving = false;
		error = null;
	}

	function close() {
		open = false;
		reset();
		onClose();
	}

	async function submit() {
		if (!canSubmit) return;
		saving = true;
		error = null;
		// Issue #690: Client-seitige Eindeutigkeitsprüfung (case-insensitive, getrimmt).
		const trimmedName = name.trim().toLowerCase();
		if (existingNames.some(n => n.trim().toLowerCase() === trimmedName)) {
			error = 'Ein Profil mit diesem Namen existiert bereits.';
			saving = false;
			return;
		}
		try {
			// Issue #343 — Neues Schema (#342): metrics[] mit horizons statt
			// metrics: string[] + friendly_ids: string[].
			const preset = await api.post<MetricPreset>('/api/metric-presets', {
				name: name.trim(),
				description: description.trim() || undefined,
				is_default: isDefault,
				metrics: enabledMetrics.map((m) => ({
					metric_id: m.id,
					enabled: true,
					use_friendly_format: friendlyMap[m.id] ?? false,
					horizons: horizonsMap[m.id] ?? { ...HORIZONS_ALL },
				})),
			});
			onSaved(preset);
			open = false;
			reset();
		} catch (e: unknown) {
			const errToken = (e as { error?: string })?.error;
			if (errToken === 'name_exists') {
				error = 'Ein Profil mit diesem Namen existiert bereits.';
			} else {
				error = errToken ?? 'Speichern fehlgeschlagen';
			}
		} finally {
			saving = false;
		}
	}
</script>

<!-- Issue #587: Custom Fixed-Overlay nach screen-metrics-editor.jsx Z. 641–680.
     Ersetzt den shadcn-Dialog-Import durch position:fixed Overlay mit Blur-Backdrop. -->
{#if open}
	<!-- Overlay -->
	<div
		style="position:fixed;inset:0;background:rgba(26,26,24,0.45);backdrop-filter:blur(2px);display:flex;align-items:center;justify-content:center;z-index:100"
		onclick={close}
		role="presentation"
	>
		<!-- Dialog-Container -->
		<div
			data-testid="save-preset-dialog"
			role="dialog"
			aria-modal="true"
			style="width:520px;background:var(--g-paper);border:1px solid var(--g-rule);border-radius:6px;box-shadow:0 24px 80px rgba(26,26,24,0.25);overflow:hidden"
			onclick={(e) => e.stopPropagation()}
		>
			<!-- Header -->
			<div style="padding:18px 24px;border-bottom:1px solid var(--g-rule-soft);display:flex;justify-content:space-between;align-items:flex-start">
				<div>
					<Eyebrow>EIGENES PRESET</Eyebrow>
					<div style="font-size:18px;font-weight:600;margin-top:2px">Auswahl als Preset speichern</div>
				</div>
				<button style="background:none;border:none;font-size:18px;color:var(--g-ink-3);cursor:pointer;padding:0" onclick={close} aria-label="Schließen">×</button>
			</div>

			<!-- Body -->
			<div style="padding:18px 24px;display:flex;flex-direction:column;gap:var(--g-s-3)">
				<!-- NAME-Feld -->
				<label class="field">
					<span style="font-size:10px;font-weight:600;letter-spacing:0.08em;color:var(--g-ink-3);font-family:var(--g-font-mono);text-transform:uppercase">NAME</span>
					<input
						data-testid="save-preset-name"
						type="text"
						bind:value={name}
						maxlength="40"
						placeholder="Mein Wandern-Preset"
						autofocus
						required
						style="padding:10px 12px;font-size:15px;background:var(--g-card);border:1px solid var(--g-rule);border-radius:4px;font:inherit;width:100%;box-sizing:border-box"
					/>
				</label>

				<!-- BESCHREIBUNG-Feld -->
				<label class="field">
					<span style="font-size:10px;font-weight:600;letter-spacing:0.08em;color:var(--g-ink-3);font-family:var(--g-font-mono);text-transform:uppercase">BESCHREIBUNG · OPTIONAL</span>
					<textarea
						data-testid="save-preset-description"
						bind:value={description}
						maxlength="120"
						rows="2"
						placeholder="Optimiert für Tages-Trips"
						style="padding:10px 12px;font-size:15px;background:var(--g-card);border:1px solid var(--g-rule);border-radius:4px;font:inherit;resize:vertical;width:100%;box-sizing:border-box"
					></textarea>
				</label>

				<!-- WIRD GESPEICHERT Box — Issue #343 ZEITHORIZONTE-Block bleibt erhalten -->
				<div style="padding:12px 14px;background:var(--g-card-alt);border-radius:4px;border:1px solid var(--g-rule-soft);display:flex;flex-direction:column;gap:var(--g-s-2)" data-testid="save-preset-will-save-box">
					<Eyebrow>WIRD GESPEICHERT</Eyebrow>
					<div class="status" data-testid="save-preset-summary">
						<strong>{enabledIds.length}</strong> Metriken aktiv ·
						<strong>{rawCount}</strong> Rohwert ·
						<strong>{indicatorCount}</strong> Indikator
					</div>
					{#if bucketSummary}
						<div class="status" data-testid="save-preset-bucket-summary">
							<strong>{bucketSummary.spalten}</strong> Spalten ·
							<strong>{bucketSummary.detail}</strong> Detail ·
							<strong>{bucketSummary.skala}</strong> als Einfach
						</div>
					{/if}
					<hr />
					<Eyebrow>ZEITHORIZONTE</Eyebrow>
					<div class="horizon-summary" data-testid="save-preset-horizon-summary">
						{horizonSummary || 'Keine Metrik aktiv'}
					</div>
					{#if enabledMetrics.length > 0}
						<div class="metric-dot-grid">
							{#each enabledMetrics as m}
								<div class="metric-dot-row" data-testid="save-preset-dot-row-{m.id}">
									<span class="metric-name">{m.label}</span>
									<span class="dots">{dotsForHorizons(horizonsMap[m.id] ?? HORIZONS_ALL)}</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>

				<!-- Als Standard Checkbox -->
				<div class="field-inline">
					<Checkbox data-testid="save-preset-is-default" bind:checked={isDefault}>
						Als Standard für neue Trips
					</Checkbox>
				</div>

				{#if error}
					<div class="error" data-testid="save-preset-error">{error}</div>
				{/if}
			</div>

			<!-- Footer -->
			<div style="padding:14px 24px;border-top:1px solid var(--g-rule-soft);background:var(--g-card-alt);display:flex;justify-content:flex-end;gap:8px">
				<Btn variant="ghost" size="sm" onclick={close} disabled={saving}>Abbrechen</Btn>
				<Btn variant="primary" size="sm" data-testid="save-preset-submit" disabled={!canSubmit} onclick={submit}>
					{saving ? 'Speichern…' : 'Preset speichern'}
				</Btn>
			</div>
		</div>
	</div>
{/if}

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.field-inline {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-text-sm);
		cursor: pointer;
	}
	.will-save-box hr {
		border: none;
		border-top: 1px solid var(--g-ink-faint);
		margin: var(--g-s-1) 0;
		width: 100%;
	}
	.status {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.horizon-summary {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		font-family: var(--g-font-data);
	}
	.metric-dot-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: var(--g-s-1) var(--g-s-4);
		margin-top: var(--g-s-2);
	}
	.metric-dot-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-text-xs);
	}
	.metric-dot-row .metric-name {
		color: var(--g-ink);
	}
	.metric-dot-row .dots {
		font-family: var(--g-font-data);
		color: var(--g-ink);
		letter-spacing: 0.1em;
	}
	@media (max-width: 599px) {
		.metric-dot-grid {
			grid-template-columns: 1fr;
		}
	}
	.error {
		font-size: var(--g-text-xs);
		color: var(--g-danger);
	}
	@media (max-width: 767px) {
		/* iOS zoom guard (#272): exakt 16px. Scoped auf .field für Spezifität 0-1-1. */
		.field input[type='text'],
		.field textarea {
			font-size: 16px;
		}
	}
</style>
