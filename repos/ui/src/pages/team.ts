import { players, teams } from '../data'
import { metrics, notFound, playerTable } from '../components'
export function teamPage(id: string): string {
  const t = teams.find(t => t.id === id)
  if (!t) return notFound('Team')
  const roster = players.filter(p => p.teamId === id)
  return `<a class="back-link" href="#/">← League overview</a><section class="profile-heading"><div class="profile-badge">${t.name.split(' ').map(s => s[0]).join('')}</div><div><p class="eyebrow">Team profile</p><h1>${t.name}</h1><p>${t.city} · Demo season</p></div></section>
  <section class="panel">${metrics([['Wins',t.wins],['Losses',t.losses],['Win percentage',`${(100*t.wins/(t.wins+t.losses)).toFixed(1)}%`],['Players listed',roster.length]])}</section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">Meet the team</p><h2>Roster & player stats</h2></div></div>${playerTable(roster)}</section>`
}
