import { teamFor, type Player } from './data'
export function playerTable(players: Player[]): string {
  return `<div class="table-scroll"><table><caption>Player averages per game · Demo season</caption>
  <thead><tr>${['Player', 'Team', 'GP', 'PTS', 'REB', 'AST'].map(label => `<th scope="col">${label}</th>`).join('')}</tr></thead>
  <tbody>${players.map(p => `<tr><th scope="row"><a href="#/players/${p.id}">${p.name}</a><span class="subtext">${p.position}</span></th><td><a href="#/teams/${p.teamId}">${teamFor(p).name}</a></td><td>${p.games}</td><td>${p.points.toFixed(1)}</td><td>${p.rebounds.toFixed(1)}</td><td>${p.assists.toFixed(1)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">No players match your filters.</td></tr>'}</tbody></table></div>`
}
export function metrics(items: [string, string | number][]): string {
  return `<dl class="metrics">${items.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl>`
}
export function notFound(kind = 'Page'): string {
  return `<section class="page-heading"><p class="eyebrow">Not found</p><h1>${kind} not found</h1><a class="button" href="#/">Back to home</a></section>`
}
