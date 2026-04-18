<script lang="ts">
	import type { Stage } from '$lib/types.js';
	import { uploadGpx } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import UploadIcon from '@lucide/svelte/icons/upload';

	interface Props {
		tripName: string;
		stages: Stage[];
		mode: 'create' | 'edit';
	}
	let { tripName = $bindable(), stages = $bindable(), mode }: Props = $props();

	const newId = (): string => crypto.randomUUID().slice(0, 8);
	const today = (): string => new Date().toISOString().slice(0, 10);

	let uploading = $state(false);
	let uploadProgress = $state('');
	let uploadError = $state('');
	let dragOver = $state(false);

	async function handleFiles(files: FileList | File[]) {
		const fileArray = Array.from(files).filter(f => f.name.endsWith('.gpx'));
		if (fileArray.length === 0) return;

		uploading = true;
		uploadError = '';
		const total = fileArray.length;

		for (let i = 0; i < fileArray.length; i++) {
			const file = fileArray[i];
			uploadProgress = `Lade ${i + 1} von ${total} Dateien...`;
			try {
				const stage = await uploadGpx(file, today(), 8);
				stages.push(stage);
			} catch (e) {
				uploadError += `${file.name}: ${e instanceof Error ? e.message : 'Fehler'}\n`;
			}
		}

		if (!tripName && fileArray.length > 0) {
			tripName = fileArray[0].name.replace(/\.gpx$/i, '');
		}

		uploading = false;
		uploadProgress = '';
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) {
			handleFiles(e.dataTransfer.files);
		}
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragOver = true;
	}

	function onDragLeave() {
		dragOver = false;
	}

	function onFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files) {
			handleFiles(input.files);
		}
	}

	function addManualStage() {
		stages.push({
			id: newId(),
			name: `Etappe ${stages.length + 1}`,
			date: today(),
			waypoints: []
		});
	}

	let fileInput: HTMLInputElement;
</script>

<div class="space-y-6">
	<div>
		<Label for="wizard-trip-name">Trip Name</Label>
		<Input
			id="wizard-trip-name"
			data-testid="trip-name-input"
			placeholder="Name des Trips"
			bind:value={tripName}
		/>
	</div>

	<div
		data-testid="gpx-drop-zone"
		role="button"
		tabindex="0"
		class="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
			{dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/30 hover:border-primary/50'}"
		ondrop={onDrop}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		onclick={() => fileInput.click()}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); }}
	>
		<UploadIcon class="mx-auto mb-2 size-8 text-muted-foreground" />
		<p class="font-medium">GPX-Dateien hierher ziehen</p>
		<p class="text-sm text-muted-foreground mt-1">oder klicken zum Auswaehlen</p>
		<input
			bind:this={fileInput}
			type="file"
			accept=".gpx"
			multiple
			class="hidden"
			onchange={onFileInput}
		/>
	</div>

	{#if uploading}
		<p class="text-sm text-muted-foreground">{uploadProgress}</p>
	{/if}

	{#if uploadError}
		<p class="text-sm text-destructive whitespace-pre-line">{uploadError}</p>
	{/if}

	{#if stages.length > 0}
		<p class="text-sm text-muted-foreground">{stages.length} Etappe(n) geladen</p>
	{/if}

	<div class="flex items-center gap-3">
		<span class="text-sm text-muted-foreground">oder</span>
		<Button variant="outline" onclick={addManualStage}>Manuell anlegen</Button>
	</div>
</div>
