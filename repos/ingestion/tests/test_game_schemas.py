import unittest
from uuid import uuid4

from pydantic import ValidationError
from ingestion.schemas import Game, GameStatistics


class GameSchemaTests(unittest.TestCase):
    def test_game_metadata_and_round_trip(self):
        game = Game(team_id_1=uuid4(), team_id_2=uuid4(), external_id='522',
                    venue=' Ynares Center - Antipolo ', period=4, clock='00:00',
                    team_1_score=75, team_2_score=114,
                    team_1_period_scores=[13, 23, 22, 17])
        self.assertEqual(Game.model_validate_json(game.model_dump_json()), game)
        self.assertEqual(game.venue, 'Ynares Center - Antipolo')

    def test_invalid_game(self):
        team = uuid4()
        for values in ({'team_id_2': team}, {'team_1_score': -1},
                       {'team_1_period_scores': [12, -1]}, {'clock': '12:99'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Game(**({'team_id_1': team, 'team_id_2': uuid4()} | values))

    def test_stats_and_missing_values(self):
        stats = GameStatistics(game_id=uuid4(), player_id=uuid4(), team_id=uuid4(),
                               jersey_number='00', seconds_played=754,
                               four_pointers_made=1, four_pointers_attempted=2,
                               four_pointers_percentage=50, plus_minus=-3)
        self.assertIsNone(stats.points)
        self.assertEqual(stats.jersey_number, '00')
        self.assertEqual(GameStatistics.model_validate_json(stats.model_dump_json()), stats)

    def test_invalid_stats(self):
        for values in ({'points': -1}, {'points': 1.5}, {'seconds_played': True},
                       {'free_throws_percentage': 101}, {'field_goals_percentage': float('nan')},
                       {'four_pointers_made': 3, 'four_pointers_attempted': 2}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                GameStatistics(game_id=uuid4(), player_id=uuid4(), team_id=uuid4(), **values)
