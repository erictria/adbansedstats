import { average, escapeHtml as e, type Game, type Player } from './data'

export function playerTable(players: Player[]): string {
  return `<div class="table-scroll"><table><caption>Player averages per game · completed games</caption><thead><tr>${['Player', 'Team', 'GP', 'PTS', 'REB', 'AST', '3PM', '4PM'].map(x => `<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${players.map(p => `<tr><th scope="row"><a href="#/players/${e(p.player_id)}">${e(p.player_name)}</a><span class="subtext">#${e(p.jersey_number || '—')}</span></th><td><a href="#/teams/${e(p.team_id)}">${e(p.team_name)}</a></td><td>${p.games}</td><td>${average(p.points_total,p.games)}</td><td>${average(p.rebounds_total,p.games)}</td><td>${average(p.assists_total,p.games)}</td><td>${average(p.threes_total,p.games)}</td><td>${average(p.fours_total,p.games)}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">No players match your filters.</td></tr>'}</tbody></table></div>`
}
export function gameTable(games: Game[]): string {
  return `<div class="table-scroll"><table><caption>Completed games</caption><thead><tr>${['Date','Matchup','Score','Venue'].map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${games.map(g=>`<tr><td><a href="#/games/${e(g.game_id)}">${e(g.date_time_raw || '—')}</a></td><td><a href="#/teams/${e(g.team_id_1)}">${e(g.team_1_name)}</a> vs <a href="#/teams/${e(g.team_id_2)}">${e(g.team_2_name)}</a></td><td><a href="#/games/${e(g.game_id)}">${e(g.team_1_score)}–${e(g.team_2_score)}</a></td><td>${e(g.venue || '—')}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">No games yet.</td></tr>'}</tbody></table></div>`
}
export function metrics(items: [string, string | number][]): string {
  return `<dl class="metrics">${items.map(([label, value])=>`<div><dt>${e(label)}</dt><dd>${e(value)}</dd></div>`).join('')}</dl>`
}
export function notFound(kind = 'Page'): string { return `<section class="page-heading"><h1>${e(kind)} not found</h1><a class="button" href="#/">Back to home</a></section>` }
