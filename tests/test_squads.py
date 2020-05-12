from models.player import Player
from models.squad import Squad
from tests.mock_db import TestWithMockAWSServices


class TestSquads(TestWithMockAWSServices):

    def setUp(self):
        self.player_1 = Player('player_1')

    def test_squad_exists(self):
        squad_name = 'test-squad'
        self.assertFalse(Squad(squad_name).exists())
        squad = self.player_1.create_squad(squad_name)
        self.assertTrue(squad.exists())
