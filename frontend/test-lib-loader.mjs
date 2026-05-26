// Registriert test-lib-hooks.mjs als ESM-Resolver für $lib/* → src/lib/*.
// Verwendung:
//   node --import ./test-lib-loader.mjs --experimental-strip-types --test <file.ts>

import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve as pathResolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

register(
	pathToFileURL(pathResolve(__dirname, 'test-lib-hooks.mjs')).href,
	pathToFileURL(__dirname + '/').href
);
