import json

from enums import WebSocketEventType
from exceptions import LobbyNotStartedException
from handlers.websocket_handlers import connection_handler
from tests.helper_functions import create_test_players, create_test_game_masters, create_test_squads
from tests.mock_db import TestWithMockAWSServices
from websockets.connection_manager import ConnectionManager


class TestWebsocketHandlers(TestWithMockAWSServices):

    def setUp(self) -> None:
        # create some players and a gamemaster
        game_master_usernames = ['gm-1', 'gm-2']
        player_usernames = ['player-1', 'player-2', 'player-3', 'player-4', 'player-5', 'player-6']
        self.p_1, self.p_2, self.p_3, self.p_4, self.p_5, self.p_6 = create_test_players(player_usernames)
        self.gamemaster_1, self.gamemaster_2 = create_test_game_masters(game_master_usernames)

        # create some squads, add 1 extra player to each
        self.squad_1, self.squad_2, self.squad_3 = create_test_squads([self.p_1, self.p_2, self.p_3])
        self.p_1.add_member_to_squad(self.squad_1, self.p_4)
        self.p_2.add_member_to_squad(self.squad_2, self.p_5)
        self.p_3.add_member_to_squad(self.squad_3, self.p_6)

        lobby_name = 'test-lobby'
        self.lobby = self.gamemaster_1.create_lobby(lobby_name)
        self.gamemaster_1.add_squad_to_lobby(lobby_name, self.squad_1)
        self.gamemaster_1.add_squad_to_lobby(lobby_name, self.squad_2)
        self.gamemaster_1.add_squad_to_lobby(lobby_name, self.squad_3)

    @staticmethod
    def create_fake_websocket_event(connection_id: str, event_type: WebSocketEventType = None, calling_user=None,
                                    body: dict = None):
        return {
            'requestContext': {
                'connectionId': connection_id,
                'eventType': event_type.value if event_type else None,
                'authorizer': {'claims': {'cognito:username': calling_user.username}}

            },
            'body': json.dumps(body)
        }

    def test_connection_handler_lobby_not_started(self):
        connection_id = '123456'

        # try to connect to the lobby before it's started as gamemaster and player
        event = self.create_fake_websocket_event(connection_id,
                                                 WebSocketEventType.CONNECT,
                                                 calling_user=self.gamemaster_1)
        res = connection_handler(event, None)
        self.assertEqual(LobbyNotStartedException.error_code, res['statusCode'])

        event = self.create_fake_websocket_event(connection_id,
                                                 WebSocketEventType.CONNECT,
                                                 calling_user=self.p_1)
        res = connection_handler(event, None)
        self.assertEqual(LobbyNotStartedException.error_code, res['statusCode'])

    def test_connection_handler_lobby_connect(self):
        self.gamemaster_1.start_game(self.lobby.name)

        # connect to the lobby as gamemaster
        gm_connection_id = '123456'
        event = self.create_fake_websocket_event(gm_connection_id,
                                                 WebSocketEventType.CONNECT,
                                                 calling_user=self.gamemaster_1)
        res = connection_handler(event, None)
        self.assertEqual(200, res['statusCode'])

        p_1_connection_id = '223456'
        event = self.create_fake_websocket_event(p_1_connection_id,
                                                 WebSocketEventType.CONNECT,
                                                 calling_user=self.p_1)
        res = connection_handler(event, None)
        self.assertEqual(200, res['statusCode'])

    def test_get_connections(self):
        self.gamemaster_1.start_game(self.lobby.name)

        connections = ConnectionManager().get_player_connections(self.lobby)

        self.assertFalse(connections)

        # connect two players to the lobby
        p_1_connection_id = '123456'
        p_2_connection_id = '223456'
        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_1)
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_2)
        connection_handler(event_1, None)
        connection_handler(event_2, None)

        connections = ConnectionManager().get_player_connections(self.lobby)

        self.assertTrue(len(connections) == 2)
        for connection in connections:
            if self.p_1.username == connection['name']:
                self.assertEqual(self.squad_1.name, connection['squad'])
            if self.p_2.username == connection['squad']:
                self.assertEqual(self.squad_2.name, connection['squad'])

    def test_get_test_player_and_gamemaster_connections(self):
        self.gamemaster_1.start_game(self.lobby.name)

        # connect two players and gamemaster_1 to the lobby
        p_1_connection_id = '123456'
        p_2_connection_id = '223456'
        gm_connection_id = '341234'

        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_1)
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_2)
        event_3 = self.create_fake_websocket_event(gm_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.gamemaster_1)

        connection_handler(event_1, None)
        connection_handler(event_2, None)
        connection_handler(event_3, None)

        # retrieve players in self.lobby
        res = ConnectionManager().get_players_in_lobby(self.lobby)
        self.p_1.get()
        gm = ConnectionManager().get_game_master(self.p_1)
        self.assertIn(p_1_connection_id, res)
        self.assertIn(p_2_connection_id, res)
        self.assertEqual(gm_connection_id, gm)

        # create new lobby with different game master, start lobby and connect players to websocket
        new_p_1, new_p_2, new_p_3 = create_test_players(['x', 'y', 'z'])

        new_squad_1 = new_p_1.create_squad('new-squad-1')
        new_squad_2 = new_p_3.create_squad('new-squad-2')
        new_p_1.add_member_to_squad(new_squad_1, new_p_2)
        new_lobby = self.gamemaster_2.create_lobby('test-lobby-2', squad_size=2)
        self.gamemaster_2.add_squad_to_lobby(new_lobby.name, new_squad_1)
        self.gamemaster_2.add_squad_to_lobby(new_lobby.name, new_squad_2)
        self.gamemaster_2.start_game(new_lobby.name)

        new_p_1_connection_id, new_p_2_connection_id, new_p_3_connection_id, new_gm_connection_id = \
            '987', '231', '123', '091'
        # connect players in second lobby websocket
        event_1 = self.create_fake_websocket_event(new_p_1_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=new_p_1)
        event_2 = self.create_fake_websocket_event(new_p_2_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=new_p_2)
        event_3 = self.create_fake_websocket_event(new_p_3_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=new_p_3)
        event_4 = self.create_fake_websocket_event(new_gm_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.gamemaster_2)

        connection_handler(event_1, None)
        connection_handler(event_2, None)
        connection_handler(event_3, None)
        connection_handler(event_4, None)

        # assert players in lobby 1 are not conflicting with players in lobby 2
        res = ConnectionManager().get_players_in_lobby(self.lobby)
        self.assertTrue(len(res) == 2)
        self.assertIn(p_1_connection_id, res)
        self.assertIn(p_2_connection_id, res)
        gm = ConnectionManager().get_game_master(self.p_1)
        self.assertEqual(gm_connection_id, gm)

        res = ConnectionManager().get_players_in_lobby(new_lobby)
        self.assertTrue(len(res) == 3)
        self.assertIn(new_p_1_connection_id, res)
        self.assertIn(new_p_2_connection_id, res)
        self.assertIn(new_p_3_connection_id, res)
        new_p_1.get()
        gm = ConnectionManager().get_game_master(new_p_1)
        self.assertEqual(new_gm_connection_id, gm)

    def test_connection_handler_lobby_disconnect(self):
        self.gamemaster_1.start_game(self.lobby.name)

        # connect two players to the lobby
        p_1_connection_id = '123456'
        p_2_connection_id = '223456'
        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_1)
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   WebSocketEventType.CONNECT,
                                                   calling_user=self.p_2)
        connection_handler(event_1, None)
        connection_handler(event_2, None)

        connections = ConnectionManager().get_player_connections(self.lobby)
        self.assertTrue(len(connections) == 2)

        disconnect_event = self.create_fake_websocket_event(p_1_connection_id,
                                                 WebSocketEventType.DISCONNECT,
                                                 calling_user=self.p_1)
        connection_handler(disconnect_event, None)

        connections = ConnectionManager().get_player_connections(self.lobby)
        self.assertTrue(len(connections) == 1)

    def test_location_websocket_message(self):
        # todo
        pass
