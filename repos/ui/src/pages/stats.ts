import { players, teams } from '../data'
import { playerTable } from '../components'
export function statsPage(): string {
  return `<section class="page-heading"><p class="eyebrow">Demo season · Regular season</p><h1>Player stats</h1><p>Compare performances across the league.</p></section><section class="panel"><div class="filters">
  <label>Search players<input id="player-search" type="search" placeholder="Search by name…"></label>
  <label>Team<select id="team-filter"><option value="">All teams</option>${teams.map(t => `<option value="${t.id}">${t.name}</option>`).join('')}</select></label>
  <label>Sort by<select id="stat-sort"><option value="points">Points: high to low</option><option value="rebounds">Rebounds: high to low</option><option value="assists">Assists: high to low</option><option value="games">Games played: high to low</option><option value="name">Name: A–Z</option></select></label>
  </div><p id="result-count" class="result-count" role="status"></p><div id="stats-results"></div></section><p class="table-note">GP = games played · PTS = points · REB = rebounds · AST = assists. All statistics except GP are per-game averages.</p>`
}
export function bindStats(root: HTMLElement): void {
  const search = root.querySelector<HTMLInputElement>('#player-search')!
  const team = root.querySelector<HTMLSelectElement>('#team-filter')!
  const sort = root.querySelector<HTMLSelectElement>('#stat-sort')!
  const results = root.querySelector<HTMLElement>('#stats-results')!
  const count = root.querySelector<HTMLElement>('#result-count')!
  function update(): void {
    const filtered = players.filter(p => p.name.toLowerCase().includes(search.value.trim().toLowerCase()) && (!team.value || p.teamId === team.value))
    const key = sort.value
    filtered.sort((a,b) => {
      if (key === 'points' || key === 'rebounds' || key === 'assists' || key === 'games') return b[key]-a[key] || a.name.localeCompare(b.name)
      return a.name.localeCompare(b.name)
    })
    results.innerHTML = playerTable(filtered)
    count.textContent = `${filtered.length} player${filtered.length === 1 ? '' : 's'}`
  }
  search.addEventListener('input', update)
  team.addEventListener('change', update)
  sort.addEventListener('change', update)
  update()
}
