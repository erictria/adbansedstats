# Adbansed Stats UI

Vite and TypeScript frontend for the ingested basketball statistics. Requires
Node.js 22.12 or newer.

First, start the [Banse API](../banse/README.md) on port 8000. Then:

```sh
cd repos/ui
npm install
npm run dev
```

Open the local URL printed by Vite. The development server forwards `/api`
requests to Banse at `http://127.0.0.1:8000`. For a separate production API host,
set `VITE_API_BASE_URL` to its origin when building. That host must allow browser
requests from the UI origin.

- `#/` shows the selected tournament, scoring leaders, recent results, and teams.
- `#/stats` shows tournament player averages with search, team filter, and sorting.
- `#/players/<uuid>` shows a player profile and game log.
- `#/teams/<uuid>` shows a team profile, roster, and results.
- `#/games/<uuid>` shows a game's player box score.

The tournament selector uses the API's tournament list. Only imported final games
are represented. Team roster memberships for the current import have assumed start
dates, as documented in `repos/ingestion/README.md`.

Use `npm run typecheck` and `npm run build` to validate the frontend.
