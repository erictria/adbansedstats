export interface Tournament { tournament_id: string; tournament_name: string; league_name: string; season: string | null; games?: number }
export interface Player { player_id: string; player_name: string; photo_url: string | null; team_id: string; team_name: string; jersey_number: string | null; games: number; points_total: number; rebounds_total: number; assists_total: number; threes_total: number; fours_total: number }
export interface Team { team_id: string; team_name: string; logo_url: string | null; games: number; wins: number; losses: number; points_for: number; points_against: number; roster_count: number }
export interface Game { game_id: string; date_time_raw: string | null; venue: string | null; team_id_1: string; team_1_name: string; team_1_score: number | null; team_id_2: string; team_2_name: string; team_2_score: number | null }
export interface BoxScore { player_id: string; player_name: string; team_id: string; jersey_number: string | null; participation_status: string; minutes_raw: string | null; points: number | null; rebounds: number | null; assists: number | null; steals: number | null; blocks: number | null; turnovers: number | null; field_goals_made: number | null; field_goals_attempted: number | null; three_pointers_made: number | null; three_pointers_attempted: number | null; four_pointers_made: number | null; four_pointers_attempted: number | null; plus_minus: number | null }
export interface GameDetail extends Game { box_score: BoxScore[] }
export interface PlayerGame { game_id: string; date_time_raw: string | null; opponent_id: string; opponent_name: string; minutes_raw: string | null; points: number | null; rebounds: number | null; assists: number | null; three_pointers_made: number | null; four_pointers_made: number | null; plus_minus: number | null }
export interface PlayerDetail extends Player { games_log: PlayerGame[] }
export interface TeamDetail extends Team { roster: Player[]; games_log: Game[] }
export interface Overview { tournament: Tournament; players: Player[]; teams: Team[]; games: Game[] }

const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
export async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${base}/api${path}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Record not found.' : `Banse returned ${response.status}. Check that the API is running.`)
  return response.json() as Promise<T>
}
export const scoped = (path: string, tournamentId: string): string => `${path}?tournament_id=${encodeURIComponent(tournamentId)}`
export const average = (total: number, games: number): string => games ? (total / games).toFixed(1) : '—'
export const escapeHtml = (value: string | number | null | undefined): string => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char]!)
