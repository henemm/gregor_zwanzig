<script lang="ts">
	import { browser } from '$app/environment';
	import type { Stage } from '$lib/types';
	import type * as LeafletNS from 'leaflet';

	interface Props {
		stage: Stage;
		activeWaypointId: string | null;
		onWaypointActivate: (waypointId: string) => void;
		onMapClick?: (lat: number, lon: number) => void;
		sizeKey?: unknown;
		/** Issue #963 — Map-First-Reorder: mobiler Vollbild-Container hat eine
		 * eigene (dynamisch gemessene) Höhe; die Karte muss sie füllen (100%)
		 * statt der festen 440px-Kartenhöhe der Desktop-/WaypointsPanel-Cards. */
		fillHeight?: boolean;
	}
	let { stage, activeWaypointId: _activeWaypointId, onWaypointActivate, onMapClick = undefined, sizeKey = undefined, fillHeight = false }: Props = $props();

	let mapEl: HTMLDivElement;
	let map: LeafletNS.Map | null = null;

	function makeMarkerClickHandler(waypointId: string) {
		return function handleMarkerClick() {
			onWaypointActivate(waypointId);
		};
	}

	$effect(() => {
		if (!browser || !mapEl) return;

		let aborted = false;

		(async () => {
			const L = (await import('leaflet')).default;
			await import('leaflet/dist/leaflet.css');
			const iconUrl = (await import('leaflet/dist/images/marker-icon.png')).default;
			const iconRetinaUrl = (await import('leaflet/dist/images/marker-icon-2x.png')).default;
			const shadowUrl = (await import('leaflet/dist/images/marker-shadow.png')).default;

			if (aborted || !mapEl) return;

			delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
			L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });

			map = L.map(mapEl, { zoomControl: true });

			L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
				attribution:
					'Kartendaten: © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, ' +
					'SRTM | Kartendarstellung: © <a href="http://opentopomap.org">OpenTopoMap</a> ' +
					'(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
				maxZoom: 17
			}).addTo(map);

			const waypoints = stage.waypoints;
			if (waypoints.length >= 2) {
				const latlngs = waypoints.map((w) => [w.lat, w.lon] as LeafletNS.LatLngTuple);
				L.polyline(latlngs, { color: '#c45a2a', weight: 2 }).addTo(map);
				waypoints.forEach((w, i) => {
					const marker = L.marker([w.lat, w.lon])
						.addTo(map!)
						.bindPopup(`${i + 1}. ${w.name ?? ''}`);
					marker.on('click', makeMarkerClickHandler(w.id));
				});
				map.fitBounds(L.latLngBounds(latlngs), { padding: [24, 24] });
			} else if (waypoints.length === 1) {
				const w = waypoints[0];
				const marker = L.marker([w.lat, w.lon])
					.addTo(map)
					.bindPopup(`1. ${w.name ?? ''}`);
				marker.on('click', makeMarkerClickHandler(w.id));
				map.setView([w.lat, w.lon], 12);
			} else {
				map.setView([47.0, 10.0], 5);
			}

			if (onMapClick) {
				map.on('click', (e: LeafletNS.LeafletMouseEvent) => {
					onMapClick!(e.latlng.lat, e.latlng.lng);
				});
			}
		})();

		return () => {
			aborted = true;
			map?.remove();
			map = null;
		};
	});

	$effect(() => {
		void sizeKey;
		if (map) { map.invalidateSize(); }
	});
</script>

<div
	data-testid="map-canvas"
	bind:this={mapEl}
	class="rounded border border-[var(--g-ink-faint)]/20"
	style:width="100%"
	style:height={fillHeight ? '100%' : '440px'}
></div>
