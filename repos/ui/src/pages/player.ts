import { players, teamFor } from '../data'
import { metrics, notFound } from '../components'
export function playerPage(id: string): string {
  const p = players.find(p => p.id === id)
  if (!p) return notFound('Player')
  const team = teamFor(p)
  return `<a class="back-link" href="#/stats">← Player stats</a><section class="profile-heading"><div class="profile-badge">${p.number}</div><div><p class="eyebrow">Player profile</p><h1>${p.name}</h1><p>${p.position} · #${p.number} · <a href="#/teams/${team.id}">${team.name}</a></p></div></section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Demo season · Regular season</p><h2>Season averages</h2></div></div>${metrics([['Points / game',p.points.toFixed(1)],['Rebounds / game',p.rebounds.toFixed(1)],['Assists / game',p.assists.toFixed(1)],['Games played',p.games]])}</section>
  <section class="panel detail-panel"><h2>Player details</h2><dl class="details"><div><dt>Team</dt><dd><a href="#/teams/${team.id}">${team.name}</a></dd></div><div><dt>Position</dt><dd>${p.position}</dd></div><div><dt>Jersey number</dt><dd>${p.number}</dd></div></dl></section>`
}
