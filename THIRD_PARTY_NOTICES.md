# Third-party components

NoteForge uses third-party software. Its source archive includes dependency manifests and lockfiles; dependency source and licence texts remain available from their respective upstream projects.

| Component | Purpose | Upstream licence / source |
| --- | --- | --- |
| ddvk/rmapi | Separate cloud CLI built in the API Docker image | AGPL-3.0; https://github.com/ddvk/rmapi |
| PyMuPDF | PDF validation, annotation overlay and rasterisation | AGPL-3.0 / commercial licensing; https://github.com/pymupdf/PyMuPDF |
| rmc | v6 stroke-to-SVG conversion | MIT; https://github.com/ricklupton/rmc |
| rmscene | reMarkable scene format parser | https://github.com/ricklupton/rmscene |
| CairoSVG | SVG-to-PDF rendering | LGPL; https://github.com/Kozea/CairoSVG |
| Next.js / React / Tailwind CSS | Web application | MIT; corresponding upstream projects |
| shadcn/ui conventions / Radix Slot / CVA | Local UI primitives and composition | MIT; corresponding upstream projects |
| FastAPI / SQLAlchemy / Alembic | API and persistence | MIT; corresponding upstream projects |
| OpenAI Python SDK | Responses API client | Apache-2.0; https://github.com/openai/openai-python |

These dependencies retain their own licences. No licence has been selected for NoteForge's own source. Review the applicable upstream terms before redistributing container images or providing a hosted service. In particular, do not assume that every bundled dependency is permissively licensed.

The Docker build pins rmapi to commit `aa60dac8a8dbb1b4eb6a25f2caf2f3daea573373` and compiles its unmodified source in a separate build stage. The application invokes it as a subprocess. No third-party source code is copied into this source archive.
