# Adbansed Stats UI

Vite and TypeScript frontend with strict type checking.

Requires Node.js 22.12 or newer. If you use nvm, run `nvm use` in this directory.

```sh
cd repos/ui
npm install
npm run dev
```

Open the local URL printed by Vite.

- `npm run typecheck` checks TypeScript without producing files.
- `npm run build` checks TypeScript and builds the site into `dist/`.
- `npm run preview` serves the production build locally after building.

The page starts in `src/main.ts`, with styles in `src/style.css`.

## Pages

- `#/` — Home with league overview, scoring leaders, and team links.
- `#/players/alex-reyes` — Player profile with season averages and team link.
- `#/teams/harbor` — Team profile with record and linked roster.
- `#/stats` — Player stat table with name search, team filter, and sorting.

Each page lives in `src/pages/`. Hash routing supports direct links, refreshes,
back/forward navigation, and static hosting without server rewrite rules.
Unknown routes and profile IDs show a not-found page.

`src/data.ts` contains fictional basketball fixtures; no live data is connected yet.
