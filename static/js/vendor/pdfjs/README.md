# PDF.js (vendored)

Vendored, not installed via a package manager — this project has no
client-side build step (`tools/dependency_fit.py` — see its own
`no-client-build` check). These are the pre-built, minified ES-module
distribution files from the `pdfjs-dist` npm package, used exactly as
downloaded, loaded via plain `<script type="module">` — no bundler, no
transform step.

- **Source:** `https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-6.2.108.tgz`
- **Version:** 6.2.108
- **License:** Apache-2.0 (see `LICENSE` in this directory, copied
  verbatim from the package)
- **Files taken:** `build/pdf.min.mjs` (the core library) and
  `build/pdf.worker.min.mjs` (the parsing/rendering worker script PDF.js
  requires to run off the main thread) — nothing else from the package.
  Deliberately NOT vendored: `pdf_viewer.mjs`/`pdf_viewer.css` (PDF.js's
  own pre-built UI/toolbar) — CLAUDE-P40-VW7A-QA's own explicit
  requirement is that the CONTROLS live in Archiosk's own top menu, not
  a second toolbar pasted over the document, so only the low-level
  rendering API (`getDocument`, page `getViewport`/`render` to a
  `<canvas>`) is used; `static/js/pdf_viewer.js` (this repo's own code)
  is the only thing driving it.

## Updating

Re-run the same extraction against a newer `pdfjs-dist` tarball,
replacing both `.mjs` files and this README's version/source lines.
Verify the low-level API surface this repo's own `static/js/
pdf_viewer.js` calls (`getDocument`, `PDFPageProxy.getViewport`,
`PDFPageProxy.render`, `PDFDocumentProxy.numPages`) hasn't changed
signature before shipping an update.
