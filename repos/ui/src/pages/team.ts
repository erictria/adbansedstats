import { escapeHtml as e, type TeamDetail, type Tournament } from '../data'
import { gameTable, metrics, playerTable } from '../components'

export function teamPage(t: TeamDetail, tournament: Tournament): string {
  return `<a class="back-link" href="#/">← Tournament overview</a><section class="profile-heading"><div class="profile-badge">${t.logo_url ? `<img src="${e(t.logo_url)}" alt="" loading="lazy">` : e(t.team_name.slice(0,2))}</div><div><p class="eyebrow">Team profile</p><h1>${e(t.team_name)}</h1><p>${e(tournament.tournament_name)}</p></div></section>
  <section class="panel">${metrics([['Wins',t.wins],['Losses',t.losses],['Points scored',t.points_for],['Players listed',t.roster_count]])}</section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Assumed season roster</p><h2>Players and stats</h2></div></div>${playerTable(t.roster)}</section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Results</p><h2>Games</h2></div></div>${gameTable(t.games_log)}</section>`
}
