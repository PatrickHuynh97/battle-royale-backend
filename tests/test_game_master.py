import json
from unittest import mock

from exceptions import SquadInLobbyException, SquadTooBigException, LobbyFullException, \
    LobbyAlreadyStartedException, PlayerAlreadyInLobbyException
from handlers import game_master_handlers
from handlers.game_master_handlers import get_lobby_handler, update_lobby_handler
from handlers.schemas import LobbySchema, LobbyPlayerListSchema
from enums import LobbyState
from models.game_master import GameMaster
from models.player import Player
from helper_functions import make_api_gateway_event, create_test_game_masters, create_test_players, \
    create_test_squads
from tests.mock_db import TestWithMockAWSServices


class TestGameMaster(TestWithMockAWSServices):

    def setUp(self):
        # create players, game masters and squads
        game_master_usernames = ['gm-1', 'gm-2', 'gm-3']
        player_usernames = ['player-1', 'player-2', 'player-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(player_usernames)
        self.game_master_1, self.game_master_2, self.game_master_3 = create_test_game_masters(game_master_usernames)
        self.squad_1, self.squad_2, self.squad_3 = create_test_squads([self.player_1, self.player_2, self.player_3])

    def test_game_master_exists(self):
        username = "test-user"
        gm = GameMaster(username)
        gm.put()

        self.assertTrue(gm.exists())

    def test_create_lobby(self):
        # test creating a game lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)

        self.assertTrue(lobby.exists())

    def test_get_lobby(self):
        # test getting a lobby
        lobby_name = 'test-lobby'
        lobby_size = 20
        squad_size = 3
        self.game_master_1.create_lobby(lobby_name, size=lobby_size, squad_size=squad_size)

        game_zone_coordinates = [dict(longitude='1.125', latitude='12.123'),
                                 dict(longitude='4.123', latitude='12.123'),
                                 dict(longitude='4.123', latitude='12.123'),
                                 dict(longitude='12.123', latitude='12.123')]
        game_zone_coordinates_as_float = [dict(longitude=1.125, latitude=12.123),
                                          dict(longitude=4.123, latitude=12.123),
                                          dict(longitude=4.123, latitude=12.123),
                                          dict(longitude=12.123, latitude=12.123)]
        self.game_master_1.update_lobby(lobby_name,
                                        game_zone_coordinates=game_zone_coordinates)

        # get new lobby
        event, context = make_api_gateway_event(body={'name': lobby_name}, calling_user=self.game_master_1)
        res = get_lobby_handler(event, context)
        body = json.loads(res['body'])

        self.assertEqual(self.game_master_1.username, body['owner'])
        self.assertEqual(lobby_size, body['size'])
        self.assertEqual(squad_size, body['squad_size'])
        self.assertEqual(game_zone_coordinates_as_float, body['game_zone_coordinates'])

    def test_get_lobby_handler(self):
        # test getting a lobby
        lobby_name = 'test-lobby'
        lobby_size = 20
        squad_size = 3
        self.game_master_1.create_lobby(lobby_name, size=lobby_size, squad_size=squad_size)
        self.player_1.add_member_to_squad(self.squad_1, self.player_2)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)

        # update lobby settings
        game_zone_coordinates = [dict(longitude='1.12', latitude='12'),
                                 dict(longitude='4', latitude='12'),
                                 dict(longitude='4', latitude='12'),
                                 dict(longitude='12.51', latitude='12.12')]
        circle_centre = {'longitude': 1.123, 'latitude': 2.234}
        circle_radius = 30
        event, context = make_api_gateway_event(calling_user=self.game_master_1,
                                                path_params={'lobby': lobby_name},
                                                body={
                                                    'game_zone_coordinates': game_zone_coordinates,
                                                    'final_circle': {
                                                        'centre': circle_centre,
                                                        'radius': circle_radius
                                                    }
                                                })
        update_lobby_handler(event, context)

        event, context = make_api_gateway_event(calling_user=self.game_master_1,
                                                body={'name': lobby_name})
        res = game_master_handlers.get_lobby_handler(event, context)
        load = LobbySchema().loads(res['body'])

        self.assertEqual(lobby_name, load['name'])
        self.assertEqual(LobbyState.NOT_STARTED.value, load['state']),
        self.assertEqual(lobby_size, load['size'])
        self.assertEqual(self.game_master_1.username, load['owner'])
        self.assertEqual(squad_size, load['squad_size'])

        self.assertEqual(1, len(load['squads']))
        self.assertEqual(self.squad_1.name, load['squads'][0]['name'])

    def test_delete_lobby(self):
        # create a lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)

        # assert it exists
        self.assertTrue(lobby.exists())
        lobby = self.game_master_1.delete_lobby(lobby_name)

        self.assertFalse(lobby.exists())

    def test_add_squad_to_lobby(self):
        # create a lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)

        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        lobby.get_squads()
        self.assertIn(self.squad_1, lobby.squads)

        self.squad_1.get()
        self.squad_1.get_members()
        self.assertEqual(lobby_name, self.squad_1.lobby_name)
        for member in self.squad_1.members:
            member.get()
            self.assertEqual(lobby_name, member.lobby.name)

    def test_add_duplicate_squad_to_lobby(self):
        # create a lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)

        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        lobby.get_squads()
        self.assertIn(self.squad_1, lobby.squads)
        self.assertRaises(SquadInLobbyException, lobby.add_squad, self.squad_1)

        # get fresh lobby object try to add same squad into lobby
        fresh_lobby = self.game_master_1.get_lobby()
        with self.assertRaises(SquadInLobbyException):
            self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        fresh_lobby.get_squads()
        self.assertEqual(1, len(fresh_lobby.squads))
        self.assertIn(self.squad_1, fresh_lobby.squads)

    def test_add_oversized_squad_to_lobby(self):
        # create a lobby with allowed squad size of 2
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20, squad_size=2)

        # add 2 more members to squad members
        self.player_1.add_member_to_squad(self.squad_1, self.player_2)
        self.player_1.add_member_to_squad(self.squad_1, self.player_3)

        self.assertRaises(SquadTooBigException, lobby.add_squad, self.squad_1)

    def test_add_duplicate_player_to_lobby(self):
        # create a lobby
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)

        # add player_2 to player_1's squad, and add squad_1 to lobby
        self.player_1.add_member_to_squad(self.squad_1, self.player_2)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        lobby.get_squads()
        self.assertIn(self.squad_1, lobby.squads)

        # add player_2 to player_3's squad, and try to add to lobby
        self.player_3.add_member_to_squad(self.squad_3, self.player_2)
        with self.assertRaises(PlayerAlreadyInLobbyException):
            self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_3)

    def test_add_squad_full_lobby(self):
        # create a lobby with size of 2 squads
        lobby_name = 'test-lobby'
        self.game_master_1.create_lobby(lobby_name, size=2)

        # add 2 squads to the lobby
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_2)

        with self.assertRaises(LobbyFullException):
            self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_3)

    def test_remove_squad_from_lobby(self):
        # create a lobby and add two squads
        lobby_name = 'test-lobby'
        self.game_master_1.create_lobby(lobby_name, size=20)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_2)

        # get fresh lobby object and populate squads
        fresh_lobby = self.game_master_1.get_lobby()
        fresh_lobby.get_squads()
        self.assertTrue(2, len(fresh_lobby.squads))

        # remove squad
        self.game_master_1.remove_squad_from_lobby(lobby_name, self.squad_2)
        self.assertTrue(1, len(fresh_lobby.squads))

        # get fresh lobby object again and populate squads
        fresh_lobby = self.game_master_1.get_lobby()
        fresh_lobby.get_squads()
        self.assertTrue(1, len(fresh_lobby.squads))

    def test_get_squads_in_lobby(self):
        # create a lobby and add a squad
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)

        # get fresh lobby object and retrieve squads in it
        fresh_lobby = self.game_master_1.get_lobby()
        self.assertFalse(fresh_lobby.squads)
        fresh_lobby.get_squads()
        self.assertIn(self.squad_1, fresh_lobby.squads)

        # add another squad to the lobby, assert they are in
        lobby.add_squad(self.squad_2)
        lobby.get_squads()
        self.assertIn(self.squad_2, lobby.squads)

    def test_update_lobby(self):
        # create a lobby with specific settings
        lobby_name = 'test-lobby'
        lobby_size = 20
        squad_size = 3
        self.game_master_1.create_lobby(lobby_name, size=lobby_size, squad_size=squad_size)

        lobby = self.game_master_1.get_lobby()
        self.assertEqual(self.game_master_1, lobby.owner)
        self.assertEqual(lobby_size, lobby.size)
        self.assertEqual(squad_size, lobby.squad_size)

        # update lobby settings
        new_lobby_size = 15
        new_squad_size = 4
        game_zone_coordinates = [dict(longitude='1.12', latitude='12'),
                                 dict(longitude='4', latitude='12'),
                                 dict(longitude='4', latitude='12'),
                                 dict(longitude='12.51', latitude='12.12')]
        game_zone_coordinates_as_float = [dict(longitude=1.12, latitude=12),
                                          dict(longitude=4, latitude=12),
                                          dict(longitude=4, latitude=12),
                                          dict(longitude=12.51, latitude=12.12)]
        circle_centre = {'longitude': 1.123, 'latitude': 2.234}
        circle_radius = 30
        event, context = make_api_gateway_event(calling_user=self.game_master_1,
                                                path_params={'lobby': lobby_name},
                                                body={
                                                    'size': new_lobby_size,
                                                    'squad_size': new_squad_size,
                                                    'game_zone_coordinates': game_zone_coordinates,
                                                    'final_circle': {
                                                        'centre': circle_centre,
                                                        'radius': circle_radius
                                                    }
                                                })
        update_lobby_handler(event, context)

        lobby = self.game_master_1.get_lobby()
        self.assertEqual(new_lobby_size, lobby.size)
        self.assertEqual(new_squad_size, lobby.squad_size)
        self.assertEqual(game_zone_coordinates_as_float, lobby.game_zone.coordinates)

    def test_full_game_flow(self):
        # create a lobby, add some squads
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)
        lobby.add_squad(self.squad_1)
        lobby.add_squad(self.squad_2)
        lobby.add_squad(self.squad_3)

        game_zone_coordinates = [dict(latitude="56.132501", longitude="12.903200"),
                                 dict(latitude="56.132757", longitude="12.897164"),
                                 dict(latitude="56.130781", longitude="12.896993"),
                                 dict(latitude="56.130309", longitude="12.902884")]

        lobby = self.game_master_1.update_lobby(lobby_name,
                                                game_zone_coordinates=game_zone_coordinates)

        # start game
        with mock.patch("sqs.closing_circle_queue.CircleQueue.send_first_circle_event"):
            self.game_master_1.start_game(lobby.name)

        # get fresh lobby object, assert that game has been started and has a started_time
        fresh_lobby = self.game_master_1.get_lobby()
        self.assertEqual(LobbyState.STARTED, fresh_lobby.state)
        self.assertIsNotNone(fresh_lobby.started_time)

        # end game
        self.game_master_1.end_game(lobby.name)

        # get another fresh lobby object, assert that game is finished
        fresh_lobby = self.game_master_1.get_lobby()
        self.assertEqual(LobbyState.FINISHED, fresh_lobby.state)

    def test_start_finished_game_start_started_game(self):
        # create a lobby, add some squads
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_2)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_3)

        # start and end game
        with mock.patch("sqs.closing_circle_queue.CircleQueue.send_first_circle_event"):
            self.game_master_1.start_game(lobby.name)
        self.game_master_1.end_game(lobby.name)

        # assert that game is in finished state, and start it again
        lobby = self.game_master_1.get_lobby()
        self.assertEqual(LobbyState.FINISHED, lobby.state)
        with mock.patch("sqs.closing_circle_queue.CircleQueue.send_first_circle_event"):
            self.game_master_1.start_game(lobby.name)

        lobby = self.game_master_1.get_lobby()
        self.assertEqual(LobbyState.STARTED, lobby.state)

        # try to start game again
        self.assertRaises(LobbyAlreadyStartedException, self.game_master_1.start_game, lobby.name)

    def test_get_players_in_lobby_handler(self):
        # create a lobby with allowed squad size of 3
        lobby_name = 'test-lobby'
        self.game_master_1.create_lobby(lobby_name, size=20, squad_size=3)

        # add 2 more members to squad members and add to the lobby
        self.player_1.add_member_to_squad(self.squad_1, self.player_2)
        self.player_1.add_member_to_squad(self.squad_1, self.player_3)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)

        # create another squad of 3 players and add to the lobby
        squad_name = 'extra_squad'
        player_4, player_5, player_6 = create_test_players(['x', 'y', 'z'])
        squad_2 = player_4.create_squad(squad_name)
        player_4.add_member_to_squad(squad_2, player_5)
        player_4.add_member_to_squad(squad_2, player_6)
        self.game_master_1.add_squad_to_lobby(lobby_name, squad_2)

        # start game
        self.game_master_1.get_players_in_lobby(lobby_name)
        event, context = make_api_gateway_event(calling_user=self.game_master_1,
                                                path_params={'lobby': lobby_name})
        res = game_master_handlers.get_players_in_lobby_handler(event, context)
        players = LobbyPlayerListSchema().loads(res['body'])['players']
        self.assertTrue(6, len(players))

        player = Player(players[0]['name'])
        player.get()
        self.assertEqual(lobby_name, player.lobby.name)
