# Vendored Three.js

- Version: Three.js `r160`
- Upstream release: `https://github.com/mrdoob/three.js/tree/r160`
- License: MIT (`https://github.com/mrdoob/three.js/blob/r160/LICENSE`)
- Vendored files: `three.module.js`, `OrbitControls.js`
- Runtime policy: local relative imports only; no CDN or runtime network fallback.

SHA-256 integrity:

| File | SHA-256 |
|---|---|
| `three.module.js` | `76dea8151bc9352aef3528b4262e249b2604f62543828328db978d060d61a495` |
| `OrbitControls.js` | `6b2f7df940a94e9aefe48466d8722c882e1430072c1dd680e978e0d70527ff00` |

`OrbitControls.js` is the upstream r160 module with its bare `three` import changed only to the local `./three.module.js` path required by the browser's self-contained ES-module loader.
