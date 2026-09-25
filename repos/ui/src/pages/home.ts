import { players, teams } from '../data'
import { metrics, playerTable } from '../components'
export function homePage(): string {
  return `<section class="hero"><div><p class="eyebrow">The league, by the numbers</p><h1>Every player.<br>Every performance.</h1><p>Explore the players and teams behind the game.</p><a class="button" href="#/stats">Explore player stats ↗</a></div><div class="hero-aside"><span class="eyebrow">League overview</span>${metrics([['Teams', teams.length], ['Players', players.length]])}<p>Demo season · Regular season</p></div></section>
  <section class="panel"><div class="section-heading"><div><p class="eyebrow">League leaders</p><h2>Leading the scoring</h2></div><a href="#/stats">All player stats →</a></div>${playerTable([...players].sort((a,b) => b.points-a.points).slice(0,3))}</section>
  <section><div class="section-heading"><div><p class="eyebrow">Around the league</p><h2>Explore teams</h2></div></div><div class="team-grid">${teams.map(t => `<a class="team-card" href="#/teams/${t.id}"><span class="badge">${t.name.split(' ').map(s => s[0]).join('')}</span><h3>${t.name}</h3><p>${t.city}</p><div class="team-record">${t.wins}–${t.losses}<span>View team →</span></div></a>`).join('')}</div></section>`
}
