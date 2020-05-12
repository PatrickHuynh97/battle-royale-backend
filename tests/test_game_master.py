import json
from unittest import mock

import botocore

from exceptions import UserAlreadyExistsException, SquadAlreadyExistsException, UserOwnsSquadException, \
    UserDoesNotOwnSquadException
from handlers.authorization_handlers import sign_up_handler
from models.game_master import GameMaster
from models.player import Player
from models.squad import Squad
from tests.helper_functions import make_api_gateway_event, create_test_game_masters
from tests.mock_db import TestWithMockAWSServices


class TestGameMaster(TestWithMockAWSServices):

    def setUp(self):
        usernames = ['username-1', 'username-2', 'username-3']
        self.game_master_1, self.game_master_2, self.game_master_3 = create_test_game_masters(usernames)

    def test_game_master_exists(self):
        username = "test-user"
        gm = GameMaster(username)
        gm.put()

        self.assertTrue(gm.exists())

    def test_create_lobby(self):
        # test creating a game lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name)

        self.assertTrue(lobby.exists())

    def test_get_lobby(self):
        # test getting a lobby
        lobby_name = 'test-lobby'
        lobby_size = 20
        squad_size = 3
        self.game_master_1.create_lobby(lobby_name, lobby_size=lobby_size, squad_size=squad_size)

        lobby = self.game_master_1.get_lobby(lobby_name)
        self.assertEqual(self.game_master_1, lobby.owner)
        self.assertEqual(lobby_size, lobby.lobby_size)
        self.assertEqual(squad_size, lobby.squad_size)

    def test_delete_lobby(self):
        # create a lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name)

        # assert it exists
        self.assertTrue(lobby.exists())
        lobby.delete()

        self.assertFalse(lobby.exists())
