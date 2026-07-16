# OnTrack for Codex

Use this when the user asks Codex to run OnTrack, inspect what the project uses,
or open the learning dashboard.

Commands use forward slashes; they work as-is on Windows, macOS, and Linux.

## Workflow

1. Record deterministic observations and build the confirmed inventory:
   ```
   python codex/ontrack.py snapshot
   ```

2. Read `.ontrack/inventory.json` and inspect source files for specific concepts
   actually used in the project. Write inferred/possible concepts to
   `.ontrack/concepts.json`.

   Rules:
   - Use `confidence: "inferred"` only with repo-relative `where` evidence like
     `src/App.tsx:14`.
   - Use `confidence: "possible"` for weak signals with no exact file evidence.
   - `parent` must be a confirmed inventory item id from `.ontrack/inventory.json`.
   - Do not teach; provide one-line `what` and a useful `search` query.

3. Rebuild inventory after writing concepts:
   ```
   python codex/ontrack.py build
   ```

4. Start the local dashboard only when the user wants to interact with statuses.
   `serve` blocks; add `--background` to keep working while it runs (logs go to
   `.ontrack/server.out` / `.ontrack/server.err`, with the URL in `server.err`):
   ```
   python codex/ontrack.py serve --background
   ```

The dashboard writes only `.ontrack/personal.json`. Keep `PROGRESS.md`
append-only and sign implementation entries with the colored Codex signature used
there.
