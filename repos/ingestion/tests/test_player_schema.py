import unittest
from uuid import UUID, uuid4

from pydantic import ValidationError

from ingestion.schemas import Player


class PlayerSchemaTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "player_name": " Rhon Jay Abarrientos ",
            "player_short_name": "R. Abarrientos",
            "external_id": "00150",
        }

    def test_generates_uuid_and_preserves_external_id(self):
        player = Player(**self.fields)
        self.assertIsInstance(player.player_id, UUID)
        self.assertNotEqual(player.player_id, Player(**self.fields).player_id)
        self.assertEqual(player.player_name, "Rhon Jay Abarrientos")
        self.assertEqual(player.external_id, "00150")
        self.assertIsNone(player.slug)
        self.assertIsNone(player.photo_url)

    def test_existing_identity_survives_json_round_trip(self):
        identity = uuid4()
        player = Player(
            player_id=str(identity),
            slug=" rhon-jay-abarrientos ",
            photo_url="https://statsspace01.sgp1.digitaloceanspaces.com/organizer/people/150/photo_L1.png",
            **self.fields,
        )
        self.assertEqual(player.slug, "rhon-jay-abarrientos")
        self.assertEqual(player.player_id, identity)
        self.assertEqual(Player.model_validate_json(player.model_dump_json()), player)

    def test_invalid_fields_are_rejected(self):
        for patch in (
            {"player_id": "invalid"},
            {"player_name": " "},
            {"player_short_name": ""},
            {"external_id": " "},
            {"external_id": 150},
            {"slug": " "},
            {"photo_url": "not-a-url"},
            {"photo_url": "ftp://example.com/photo.png"},
            {"unexpected": True},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                Player(**(self.fields | patch))
