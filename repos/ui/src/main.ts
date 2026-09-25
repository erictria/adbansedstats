import './style.css'
import { notFound } from './components'
import { homePage } from './pages/home'
import { playerPage } from './pages/player'
import { teamPage } from './pages/team'
import { bindStats, statsPage } from './pages/stats'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Missing app element')
app.innerHTML = `<a class="skip-link" href="#main-content">Skip to content</a><header class="site-header"><div class="header-inner"><a class="brand" href="#/" aria-label="Adbansed Stats home"><span class="brand-mark" aria-hidden="true">A↗</span>adbansed<span class="brand-light">stats</span></a><nav aria-label="Main navigation"><a href="#/" data-page="home">Home</a><a href="#/players/alex-reyes" data-page="players">Player profile</a><a href="#/teams/harbor" data-page="teams">Team profile</a><a href="#/stats" data-page="stats">Stat table</a></nav></div></header><div class="demo-notice">Demo league · Fictional players, teams, and statistics</div><main id="main-content" tabindex="-1"></main><footer>Adbansed Stats <span>Basketball, in detail.</span></footer>`
const main = document.querySelector<HTMLElement>('#main-content')!
// Hash routes work on static hosting without server-side fallback configuration.
function render(): void {
  const path = location.hash.slice(1) || '/'
  const player = path.match(/^\/players\/([^/]+)$/)
  const team = path.match(/^\/teams\/([^/]+)$/)
  let page = ''
  if (path === '/') { page = 'home'; main.innerHTML = homePage() }
  else if (path === '/stats') { page = 'stats'; main.innerHTML = statsPage(); bindStats(main) }
  else if (player) { page = 'players'; main.innerHTML = playerPage(player[1]!) }
  else if (team) { page = 'teams'; main.innerHTML = teamPage(team[1]!) }
  else { main.innerHTML = notFound() }
  document.title = `${main.querySelector('h1')?.textContent ?? 'Home'} | Adbansed Stats`
  document.querySelectorAll<HTMLAnchorElement>('nav a').forEach(link => {
    if (link.dataset.page === page) link.setAttribute('aria-current','page')
    else link.removeAttribute('aria-current')
  })
}
document.querySelector('.skip-link')!.addEventListener('click', event => { event.preventDefault(); main.focus() })
window.addEventListener('hashchange', () => { render(); main.focus({ preventScroll: true }); window.scrollTo(0,0) })
render()
