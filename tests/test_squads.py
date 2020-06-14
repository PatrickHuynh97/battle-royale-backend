from exceptions import PlayerDoesNotOwnSquadException
from handlers.player_handlers import pull_squad_from_lobby_handler
from models.game_master import GameMaster
from models.player import Player
from models.squad import Squad
from helper_functions import make_api_gateway_event
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

        _lobby = self.player_1.get_current_lobby()
        self.assertEqual(lobby, _lobby)

        # get fresh lobby object, make sure everything checks out
        fresh_lobby = game_master.get_lobby()
        fresh_lobby.get_squads()
        self.assertIn(squad, fresh_lobby.squads)
        squad.get()
        self.assertEqual(lobby_name, squad.lobby_name)
        self.assertEqual(game_master.username, squad.lobby_owner)

        # try to pull squad from lobby as non-owner
        self.assertRaises(PlayerDoesNotOwnSquadException, self.player_2.pull_squad_from_lobby, squad)

        # pull squad from lobby via handler
        event, context = make_api_gateway_event(calling_user=self.player_1, path_params={'squadname': squad.name})
        pull_squad_from_lobby_handler(event, context)

        lobby.get_squads()
        self.assertNotIn(squad, lobby.squads)
        squad.get()
        self.assertIsNone(squad.lobby_name)
        self.assertIsNone(squad.lobby_owner)
