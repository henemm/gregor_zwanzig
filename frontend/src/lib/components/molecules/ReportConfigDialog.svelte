<script lang="ts">
	// Issues #477 + #486 — ReportConfigDialog-Molecule.
	//
	// Kapselt das Report-Konfigurations-Formular (Zeiten, Kanäle, Schwellwerte)
	// und befreit /trips/+page.svelte von ui/dialog, ui/checkbox, ui/select.
	// Die ui/-Importe leben innerhalb dieser Molecule weiter (Known Limitation
	// aus der Spec — Atom-Pendants für Checkbox/Select existieren noch nicht).
	//
	// Spec: docs/specs/modules/trips_atomic_kebab.md (Schritt 3)

	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import { Btn } from '$lib/components/atoms';
	import type { Trip } from '$lib/types.js';

	export interface ReportConfig {
		morning_time: string;
		evening_time: string;
		enabled: boolean;
		send_email: boolean;
		send_sms: boolean;
		send_telegram: boolean;
		alert_on_changes: boolean;
		change_threshold_temp_c: number;
		change_threshold_wind_kmh: number;
		change_threshold_precip_mm: number;
		show_compact_summary: boolean;
		wind_exposition_min_elevation_m: number | null;
		multi_day_trend_reports: string[];
	}

	interface Props {
		open: boolean;
		trip: Trip | null;
		config: ReportConfig;
		loading?: boolean;
		saving?: boolean;
		error?: string | null;
		onSave: () => void;
		onClose: () => void;
	}

	let {
		open,
		trip,
		config = $bindable(),
		loading = false,
		saving = false,
		error = null,
		onSave,
		onClose
	}: Props = $props();

	function getHour(timeStr: string): number {
		return parseInt(timeStr.split(':')[0], 10);
	}

	function setHour(timeStr: string, hour: number): string {
		const parts = timeStr.split(':');
		parts[0] = String(hour).padStart(2, '0');
		return parts.join(':');
	}
</script>

<Dialog.Root
	{open}
	onOpenChange={(o) => { if (!o) onClose(); }}
>
	<Dialog.Content class="max-h-[85vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Report-Konfiguration — {trip?.name ?? ''}</Dialog.Title>
			<Dialog.Description>Zeiten und Kanäle für automatische Wetterreports</Dialog.Description>
		</Dialog.Header>

		{#if loading}
			<p class="py-4 text-sm text-muted-foreground">Lade Konfiguration…</p>
		{:else}
			<div class="space-y-5 py-2">
				<!-- Times -->
				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-1">
						<label class="text-sm font-medium" for="morning-hour">Morgen-Report (Stunde)</label>
						<Select
							id="morning-hour"
							class="w-full"
							value={getHour(config.morning_time)}
							onchange={(e) => {
								config.morning_time = setHour(config.morning_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</Select>
					</div>
					<div class="space-y-1">
						<label class="text-sm font-medium" for="evening-hour">Abend-Report (Stunde)</label>
						<Select
							id="evening-hour"
							class="w-full"
							value={getHour(config.evening_time)}
							onchange={(e) => {
								config.evening_time = setHour(config.evening_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</Select>
					</div>
				</div>

				<!-- Enabled -->
				<div class="flex items-center gap-3 text-sm font-medium">
					<Checkbox bind:checked={config.enabled}>Reports aktiv</Checkbox>
				</div>

				<!-- Channels -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Kanäle</p>
					<div class="space-y-2 text-sm">
						<div><Checkbox bind:checked={config.send_email}>E-Mail senden</Checkbox></div>
						<div><Checkbox bind:checked={config.send_telegram}>Telegram senden</Checkbox></div>
					</div>
				</div>

				<!-- Options -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Optionen</p>
					<div class="space-y-2 text-sm">
						<div><Checkbox bind:checked={config.alert_on_changes}>Alert bei Änderungen</Checkbox></div>
						<div><Checkbox bind:checked={config.show_compact_summary}>Kompakte Zusammenfassung anzeigen</Checkbox></div>
					</div>
				</div>

				<!-- Thresholds -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Änderungs-Schwellwerte</p>
					<div class="grid grid-cols-3 gap-3">
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-temp">Temperatur (°C)</label>
							<input
								id="thresh-temp"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={config.change_threshold_temp_c}
							/>
						</div>
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-wind">Wind (km/h)</label>
							<input
								id="thresh-wind"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={config.change_threshold_wind_kmh}
							/>
						</div>
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-precip">Niederschlag (mm)</label>
							<input
								id="thresh-precip"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={config.change_threshold_precip_mm}
							/>
						</div>
					</div>
				</div>

				{#if error}
					<p class="text-sm text-destructive">{error}</p>
				{/if}
			</div>
		{/if}

		<Dialog.Footer>
			<Btn variant="outline" onclick={onClose}>Abbrechen</Btn>
			<Btn variant="primary" onclick={onSave} disabled={loading || saving}>
				{saving ? 'Speichern…' : 'Speichern'}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
