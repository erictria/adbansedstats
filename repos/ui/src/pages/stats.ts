import { escapeHtml as e, type Player, type Team, type Tournament } from '../data'
import { playerTable } from '../components'

export function statsPage(tournament: Tournament, teams: Team[]): string {
  return `<section class="page-heading"><p class="eyebrow">${e(tournament.tournament_name)}</p><h1>Player stats</h1><p>Compare averages from completed games.</p></section><section class="panel"><div class="filters"><label>Search players<input id="player-search" type="search" placeholder="Search by name…"></label><label>Team<select id="team-filter"><option value="">All teams</option>${teams.map(t=>`<option value="${e(t.team_id)}">${e(t.team_name)}</option>`).join('')}</select></label><label>Sort by<select id="stat-sort"><option value="points_total">Points per game</option><option value="rebounds_total">Rebounds per game</option><option value="assists_total">Assists per game</option><option value="threes_total">Threes per game</option><option value="fours_total">Fours per game</option><option value="games">Games played</option><option value="name">Name: A–Z</option></select></label></div><p id="result-count" class="result-count" role="status"></p><div id="stats-results"></div></section><p class="table-note">GP = games played · PTS = points · REB = rebounds · AST = assists · 3PM/4PM = made three/four-point shots. Statistics other than GP are per-game averages.</p>`
}
export function bindStats(root: HTMLElement, players: Player[]): void {
  const search = root.querySelector<HTMLInputElement>('#player-search')!
  const team = root.querySelector<HTMLSelectElement>('#team-filter')!
  const sort = root.querySelector<HTMLSelectElement>('#stat-sort')!
  const results = root.querySelector<HTMLElement>('#stats-results')!
  const count = root.querySelector<HTMLElement>('#result-count')!
  function update(): void {
    const filtered = players.filter(p => p.player_name.toLowerCase().includes(search.value.trim().toLowerCase()) && (!team.value || p.team_id === team.value))
    const key = sort.value
    filtered.sort((a,b) => {
      if (key === 'name') return a.player_name.localeCompare(b.player_name)
      if (key === 'games') return b.games - a.games || a.player_name.localeCompare(b.player_name)
      const metric = key as 'points_total' | 'rebounds_total' | 'assists_total' | 'threes_total' | 'fours_total'
      return (b.games ? b[metric]/b.games : 0) - (a.games ? a[metric]/a.games : 0) || a.player_name.localeCompare(b.player_name)
    })
    results.innerHTML = playerTable(filtered)
    count.textContent = `${filtered.length} player${filtered.length === 1 ? '' : 's'}`
  }
  search.addEventListener('input', update)
  team.addEventListener('change', update)
  sort.addEventListener('change', update)
  update()
}
