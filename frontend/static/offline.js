// Issue #2961 — "Erneut versuchen" der Offline-Seite ohne Inline-Handler.
// Liegt in static/, wird damit als Programmdatei im Gerätespeicher abgelegt
// und steht ohne Netz zur Verfuegung (wie offline.html selbst).
(function () {
	var knopf = document.querySelector('[data-gz-erneut]');
	if (!knopf) return;
	knopf.addEventListener('click', function () {
		location.reload();
	});
})();
