// ESM-Hook (Issue #2283 AC-14): schneidet mit, welche Module tatsaechlich
// geladen werden, und meldet jede geladene URL ueber einen MessagePort an die
// Testdatei. Damit laesst sich „CompareTabs laedt keinen entfernten Baustein
// mehr" am echten Modulgraphen pruefen — kein Dateitext-Check.
//
// Registrierung in der Testdatei:
//   const { port1, port2 } = new MessageChannel();
//   register(url, { parentURL, data: { port: port2 }, transferList: [port2] });

let port = null;

export async function initialize(data) {
	port = data?.port ?? null;
}

export async function load(url, context, nextLoad) {
	if (port && url.startsWith('file:')) port.postMessage(url);
	return nextLoad(url, context);
}
