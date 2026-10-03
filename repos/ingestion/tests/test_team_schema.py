import unittest
from uuid import UUID, uuid4

from pydantic import ValidationError

from ingestion.schemas import Team


class TeamSchemaTests(unittest.TestCase):
    def test_identity_and_normalization(self):
        team = Team(team_name=" Ginebra ", external_id="004")
        self.assertIsInstance(team.team_id, UUID)
        self.assertEqual(team.team_name, "Ginebra")
        self.assertEqual(team.external_id, "004")
        self.assertIsNone(team.logo_url)

    def test_existing_identity_and_urls_round_trip(self):
        identity = uuid4()
        team = Team(
            team_id=str(identity), team_name="Barangay Ginebra San Miguel",
            external_id="4", slug="barangay-ginebra-san-miguel",
            profile_url="https://www.pba.ph/teams/barangay-ginebra-san-miguel",
            logo_url="https://statsspace01.sgp1.digitaloceanspaces.com/organizer/teams/4/logo_L1.png",
        )
        self.assertEqual(team.team_id, identity)
        self.assertEqual(Team.model_validate_json(team.model_dump_json()), team)

    def test_invalid_fields(self):
        for patch in (
            {"team_name": " "}, {"external_id": ""}, {"external_id": 4},
            {"team_id": "invalid"}, {"slug": " "},
            {"profile_url": "not-a-url"}, {"logo_url": "ftp://example.com/logo.png"},
            {"unexpected": True},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                Team(**({"team_name": "Ginebra", "external_id": "4"} | patch))
