import { escapeHtml as e, type Overview } from '../data'
import { gameTable, metrics, playerTable } from '../components'

export function homePage(data: Overview): string {
  const { tournament, players, teams, games } = data
  const leaders = [...players].sort((a,b) => (b.games ? b.points_total/b.games : 0) - (a.games ? a.points_total/a.games : 0)).slice(0,5)
  return `<section class="hero"><div><p class="eyebrow">${e(tournament.league_name)}</p><h1>Every player.<br>Every performance.</h1><p>Explore the box scores from ${e(tournament.tournament_name)}.</p><a class="button" href="#/stats">Explore player stats ↗</a></div><div class="hero-aside"><span class="eyebrow">Tournament overview</span>${metrics([['Teams', teams.length], ['Players', players.length], ['Final games', games.length]])}<p>Statistics cover completed games in this import.</p></div></section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Scoring leaders</p><h2>Points per game</h2></div><a href="#/stats">All player stats →</a></div>${playerTable(leaders)}</section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Results</p><h2>Recent games</h2></div></div>${gameTable(games.slice(0,5))}</section>
  <section><div class="section-heading"><div><p class="eyebrow">Tournament teams</p><h2>Explore teams</h2></div></div><div class="team-grid">${teams.map(t=>`<a class="team-card" href="#/teams/${e(t.team_id)}"><span class="badge">${t.logo_url ? `<img src="${e(t.logo_url)}" alt="" loading="lazy">` : e(t.team_name.slice(0,2))}</span><h3>${e(t.team_name)}</h3><p>${t.roster_count} players listed</p><div class="team-record">${t.wins}–${t.losses}<span>View team →</span></div></a>`).join('')}</div></section>`
}
