export interface Team { id: string; name: string; city: string; wins: number; losses: number }
export interface Player { id: string; name: string; teamId: string; number: number; position: string; games: number; points: number; rebounds: number; assists: number }
// Fictional fixtures. Replace with datasource results when the API is available.
export const teams: Team[] = [
  { id: 'harbor', name: 'Harbor Waves', city: 'Harbor City', wins: 12, losses: 4 },
  { id: 'metro', name: 'Metro Falcons', city: 'Metro City', wins: 10, losses: 6 },
  { id: 'summit', name: 'Summit Bears', city: 'Summit City', wins: 8, losses: 8 },
]
export const players: Player[] = [
  { id: 'alex-reyes', name: 'Alex Reyes', teamId: 'harbor', number: 7, position: 'Guard', games: 16, points: 24.8, rebounds: 4.2, assists: 7.1 },
  { id: 'jordan-cruz', name: 'Jordan Cruz', teamId: 'metro', number: 12, position: 'Forward', games: 16, points: 22.3, rebounds: 8.6, assists: 3.4 },
  { id: 'sam-rivera', name: 'Sam Rivera', teamId: 'summit', number: 21, position: 'Center', games: 15, points: 18.6, rebounds: 11.2, assists: 2.1 },
  { id: 'nico-santos', name: 'Nico Santos', teamId: 'harbor', number: 3, position: 'Forward', games: 16, points: 17.4, rebounds: 6.8, assists: 2.9 },
  { id: 'eli-ramos', name: 'Eli Ramos', teamId: 'metro', number: 5, position: 'Guard', games: 14, points: 16.2, rebounds: 3.1, assists: 6.5 },
  { id: 'kai-torres', name: 'Kai Torres', teamId: 'summit', number: 9, position: 'Guard', games: 16, points: 15.9, rebounds: 4.5, assists: 5.8 },
]
export function teamFor(player: Player): Team {
  const team = teams.find(team => team.id === player.teamId)
  if (!team) throw new Error('Unknown team')
  return team
}
