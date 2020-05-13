from models.game_master import GameMaster
from models.player import Player
from models.squad import Squad
from tests.mock_db import TestWithMockAWSServices


class TestSquads(TestWithMockAWSServices):

    def setUp(self):
        self.player_1 = Player('player_1')
        self.player_2 = Player('player_2')

    def test_squad_exists(self):
        squad_name = 'test-squad'
        self.assertFalse(Squad(squad_name).exists())
        squad = self.player_1.create_squad(squad_name)
        self.assertTrue(squad.exists())

    def test_leave_lobby_as_squad(self):
        squad_name = 'test-squad'
        squad = self.player_1.create_squad(squad_name)
        self.assertTrue(squad.exists())

        # create a lobby, add squad and assert they are in
        game_master = GameMaster('gm')
        lobby_name = 'test-lobby'
        lobby = game_master.create_lobby(lobby_name, size=20)
        game_master.add_squad_to_lobby(lobby_name, squad)

        # get fresh lobby object, make sure everything checks out
        fresh_lobby = game_master.get_lobby(lobby.name)
        fresh_lobby.get_squads()
        self.assertIn(squad, fresh_lobby.squads)
        squad.get()
        self.assertEqual(lobby_name, squad.lobby_name)
        self.assertEqual(game_master.username, squad.lobby_owner)

        # pull squad from lobby as squad
        squad.leave_lobby()

        lobby.get_squads()
        self.assertNotIn(squad, lobby.squads)
        squad.get()
        self.assertIsNone(squad.lobby_name)
        self.assertIsNone(squad.lobby_owner)
