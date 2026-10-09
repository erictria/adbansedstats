import './style.css'
import { api, scoped, escapeHtml as e, type GameDetail, type Overview, type PlayerDetail, type TeamDetail, type Tournament } from './data'
import { notFound } from './components'
import { homePage } from './pages/home'
import { playerPage } from './pages/player'
import { teamPage } from './pages/team'
import { gamePage } from './pages/game'
import { bindStats, statsPage } from './pages/stats'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Missing app element')
app.innerHTML = `<a class="skip-link" href="#main-content">Skip to content</a><header class="site-header"><div class="header-inner"><a class="brand" href="#/" aria-label="Adbansed Stats home"><span class="brand-mark" aria-hidden="true">A↗</span>adbansed<span class="brand-light">stats</span></a><nav aria-label="Main navigation"><a href="#/" data-page="home">Home</a><a href="#/stats" data-page="stats">Player stats</a></nav><label class="tournament-picker">Tournament<select id="tournament-select" aria-label="Tournament"></select></label></div></header><div class="data-notice" id="data-notice">Loading league data…</div><main id="main-content" tabindex="-1"></main><footer>Adbansed Stats <span>Basketball, in detail.</span></footer>`
const main = document.querySelector<HTMLElement>('#main-content')!
const picker = document.querySelector<HTMLSelectElement>('#tournament-select')!
const notice = document.querySelector<HTMLElement>('#data-notice')!
let tournaments: Tournament[] = []
let selected = ''
let overview: Overview | null = null
let request = 0

function showError(message: string): void {
  main.innerHTML = `<section class="page-heading"><h1>Data unavailable</h1><p>${e(message)}</p><button class="button" id="retry" type="button">Try again</button></section>`
  main.querySelector('#retry')?.addEventListener('click', () => { void initialize() })
}
async function initialize(): Promise<void> {
  try {
    notice.textContent = 'Loading league data…'
    tournaments = await api<Tournament[]>('/tournaments')
    if (!tournaments.length) { showError('No tournaments have been imported yet.'); return }
    const saved = sessionStorage.getItem('tournament_id')
    selected = tournaments.find(t => t.tournament_id === saved)?.tournament_id || tournaments[0]!.tournament_id
    picker.innerHTML = tournaments.map(t => `<option value="${e(t.tournament_id)}">${e(t.tournament_name)}</option>`).join('')
    picker.value = selected
    await loadTournament()
  } catch (error) { showError(error instanceof Error ? error.message : 'Could not load the API.') }
}
async function loadTournament(): Promise<void> {
  const current = ++request
  main.innerHTML = '<p class="loading" role="status">Loading tournament…</p>'
  try {
    const data = await api<Overview>(scoped('/overview', selected))
    if (current !== request) return
    overview = data
    notice.textContent = `${data.tournament.league_name} · ${data.tournament.tournament_name} · ${data.games.length} completed games imported`
    await render()
  } catch (error) { if (current === request) showError(error instanceof Error ? error.message : 'Could not load tournament.') }
}
async function render(): Promise<void> {
  if (!overview) return
  const current = ++request
  const path = location.hash.slice(1) || '/'
  const player = path.match(/^\/players\/([^/]+)$/)
  const team = path.match(/^\/teams\/([^/]+)$/)
  const game = path.match(/^\/games\/([^/]+)$/)
  let page = ''
  try {
    if (path === '/') { page = 'home'; main.innerHTML = homePage(overview) }
    else if (path === '/stats') { page = 'stats'; main.innerHTML = statsPage(overview.tournament, overview.teams); bindStats(main, overview.players) }
    else if (player) {
      main.innerHTML = '<p class="loading" role="status">Loading player…</p>'
      const detail = await api<PlayerDetail>(scoped(`/players/${encodeURIComponent(player[1]!)}`, selected))
      if (current !== request) return
      main.innerHTML = playerPage(detail, overview.tournament)
    } else if (team) {
      main.innerHTML = '<p class="loading" role="status">Loading team…</p>'
      const detail = await api<TeamDetail>(scoped(`/teams/${encodeURIComponent(team[1]!)}`, selected))
      if (current !== request) return
      main.innerHTML = teamPage(detail, overview.tournament)
    } else if (game) {
      main.innerHTML = '<p class="loading" role="status">Loading box score…</p>'
      const detail = await api<GameDetail>(scoped(`/games/${encodeURIComponent(game[1]!)}`, selected))
      if (current !== request) return
      main.innerHTML = gamePage(detail)
    } else main.innerHTML = notFound()
  } catch (error) {
    if (current !== request) return
    main.innerHTML = error instanceof Error && error.message === 'Record not found.' ? notFound(player ? 'Player' : team ? 'Team' : 'Game') : ''
    if (!main.innerHTML) showError(error instanceof Error ? error.message : 'Could not load this page.')
  }
  document.title = `${main.querySelector('h1')?.textContent ?? 'Home'} | Adbansed Stats`
  document.querySelectorAll<HTMLAnchorElement>('nav a').forEach(link => {
    if (link.dataset.page === page) link.setAttribute('aria-current', 'page')
    else link.removeAttribute('aria-current')
  })
}
picker.addEventListener('change', () => { selected = picker.value; sessionStorage.setItem('tournament_id', selected); void loadTournament() })
document.querySelector('.skip-link')!.addEventListener('click', event => { event.preventDefault(); main.focus() })
window.addEventListener('hashchange', () => { void render(); main.focus({ preventScroll: true }); window.scrollTo(0, 0) })
void initialize()
