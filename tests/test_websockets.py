import json
import sys
from unittest import mock
from unittest.mock import MagicMock

from enums import WebSocketEventType
from exceptions import LobbyNotStartedException
from handlers.websocket_handlers import connection_handler, authorize_connection_handler, \
    player_location_message_handler, gamemaster_message_handler
from tests.helper_functions import create_test_players, create_test_game_masters, create_test_squads
from tests.mock_db import TestWithMockAWSServices
from websockets.connection_manager import ConnectionManager


class TestWebsocketHandlers(TestWithMockAWSServices):

    def setUp(self) -> None:
        sys.modules['jwt'] = MagicMock()

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
    def create_fake_websocket_event(connection_id: str, event_type: WebSocketEventType = None, body: dict = None):
        return {
            'requestContext': {
                'connectionId': connection_id,
                'eventType': event_type.value if event_type else None
            },
            'body': json.dumps(body)
        }

    def test_unauthorized_connections(self):
        # test connecting to websocket in an unauthorized state
        connection_id = '123456'
        event = self.create_fake_websocket_event(connection_id,
                                                 event_type=WebSocketEventType.CONNECT,
                                                 body={'access_token': '123456'})
        connection_handler(event, None)

        unauthorized_connections = ConnectionManager().get_unauthorized_connections()
        self.assertIn(connection_id, unauthorized_connections)

        # disconnect the unauthorized user from websocket
        ConnectionManager().disconnect_unauthorized_connection(connection_id)

        # check that no unauthorized connections exist
        unauthorized_connections = ConnectionManager().get_unauthorized_connections()
        self.assertFalse(unauthorized_connections)

    def test_authorize_unauthorized_connection(self):
        # connect to websocket in an unauthorized state
        connection_id = '123456'
        event = self.create_fake_websocket_event(connection_id,
                                                 event_type=WebSocketEventType.CONNECT,
                                                 body={'access_token': '123456'})
        connection_handler(event, None)

        unauthorized_connections = ConnectionManager().get_unauthorized_connections()
        self.assertIn(connection_id, unauthorized_connections)

        # authorize above user as a game master in happy flow
        self.gamemaster_1.start_game(self.lobby.name)
        event = self.create_fake_websocket_event(connection_id,
                                                 body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            authorize_connection_handler(event, None)

        # gamemaster should no longer be an unauthorized connection
        unauthorized_connections = ConnectionManager().get_unauthorized_connections()
        self.assertFalse(unauthorized_connections)

        # gamemaster should have an authorized connection now
        response = self.table.get_item(
            Key={
                'pk': 'CONNECTION',
                'sk': f'GAMEMASTER#{self.gamemaster_1.username}'
            },
        )['Item']
        self.assertEqual(connection_id, response['lsi-2'])

    def test_authorize_connection_handler_lobby_not_started(self):
        connection_id = '123456'

        # try to connect to the lobby before it's started as gamemaster and player
        event = self.create_fake_websocket_event(connection_id,
                                                 body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            res = authorize_connection_handler(event, None)
        self.assertEqual(LobbyNotStartedException.error_code, res['statusCode'])

        event = self.create_fake_websocket_event(connection_id,
                                                 body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            res = authorize_connection_handler(event, None)
        self.assertEqual(LobbyNotStartedException.error_code, res['statusCode'])

    def test_connection_handler_lobby_connect(self):
        self.gamemaster_1.start_game(self.lobby.name)

        # connect to the lobby as gamemaster
        gm_connection_id = '123456'
        event = self.create_fake_websocket_event(gm_connection_id,
                                                 body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            res = authorize_connection_handler(event, None)
        self.assertEqual(200, res['statusCode'])

        # connect to the lobby as player
        p_1_connection_id = '223456'
        event = self.create_fake_websocket_event(p_1_connection_id,
                                                 body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            res = authorize_connection_handler(event, None)
        self.assertEqual(200, res['statusCode'])

    def test_get_connections(self):
        self.gamemaster_1.start_game(self.lobby.name)

        connections = ConnectionManager().get_player_connections(self.lobby)

        self.assertFalse(connections)

        # connect two players to the lobby
        p_1_connection_id = '123456'
        p_2_connection_id = '223456'
        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_2.username}):
            authorize_connection_handler(event_2, None)

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
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   body={'access_token': '123456'})
        event_3 = self.create_fake_websocket_event(gm_connection_id,
                                                   body={'access_token': '123456'})

        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_2.username}):
            authorize_connection_handler(event_2, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            authorize_connection_handler(event_3, None)

        # retrieve players in self.lobby
        res = ConnectionManager().get_players_in_lobby(self.lobby)
        self.p_1.get()
        gm = ConnectionManager().get_game_master_from_player(self.p_1)
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

        # connect players in second lobby to websocket
        new_p_1_connection_id, new_p_2_connection_id, new_p_3_connection_id, new_gm_connection_id = \
            '987', '231', '123', '091'
        event_1 = self.create_fake_websocket_event(new_p_1_connection_id,
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(new_p_2_connection_id,
                                                   body={'access_token': '123456'})
        event_3 = self.create_fake_websocket_event(new_p_3_connection_id,
                                                   body={'access_token': '123456'})
        event_4 = self.create_fake_websocket_event(new_gm_connection_id,
                                                   body={'access_token': '123456'})

        with mock.patch('jwt.verify_token', return_value={'username': new_p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': new_p_2.username}):
            authorize_connection_handler(event_2, None)
        with mock.patch('jwt.verify_token', return_value={'username': new_p_3.username}):
            authorize_connection_handler(event_3, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_2.username}):
            authorize_connection_handler(event_4, None)

        # assert players in lobby 1 are not conflicting with players in lobby 2
        res = ConnectionManager().get_players_in_lobby(self.lobby)
        self.assertTrue(len(res) == 2)
        self.assertIn(p_1_connection_id, res)
        self.assertIn(p_2_connection_id, res)
        gm = ConnectionManager().get_game_master_from_player(self.p_1)
        self.assertEqual(gm_connection_id, gm)

        res = ConnectionManager().get_players_in_lobby(new_lobby)
        self.assertTrue(len(res) == 3)
        self.assertIn(new_p_1_connection_id, res)
        self.assertIn(new_p_2_connection_id, res)
        self.assertIn(new_p_3_connection_id, res)
        new_p_1.get()
        gm = ConnectionManager().get_game_master_from_player(new_p_1)
        self.assertEqual(new_gm_connection_id, gm)

    def test_connection_handler_lobby_disconnect(self):
        self.gamemaster_1.start_game(self.lobby.name)

        # connect two players to the lobby
        p_1_connection_id = '123456'
        p_2_connection_id = '223456'
        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   body={'access_token': '123456'})
        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_2.username}):
            authorize_connection_handler(event_2, None)

        connections = ConnectionManager().get_player_connections(self.lobby)
        self.assertTrue(len(connections) == 2)

        disconnect_event = self.create_fake_websocket_event(p_1_connection_id,
                                                            event_type=WebSocketEventType.DISCONNECT)
        connection_handler(disconnect_event, None)

        connections = ConnectionManager().get_player_connections(self.lobby)
        self.assertTrue(len(connections) == 1)

    def test_location_websocket_message(self):
        # start lobby, connect two player who are in the same squad, one other player, and the game master
        self.gamemaster_1.start_game(self.lobby.name)

        p_1_connection_id = '123456'
        p_2_connection_id = '512512'
        p_4_connection_id = '223456'
        gm_connection_id = '341234'

        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   body={'access_token': '123456'})
        event_3 = self.create_fake_websocket_event(p_4_connection_id,
                                                   body={'access_token': '123456'})
        event_4 = self.create_fake_websocket_event(gm_connection_id,
                                                   body={'access_token': '123456'})

        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_2.username}):
            authorize_connection_handler(event_2, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_4.username}):
            authorize_connection_handler(event_3, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            authorize_connection_handler(event_4, None)

        # push location message through websocket from self.p_1
        long = "1231.123"
        lat = "11.123"
        player_location = dict(long=long, lat=lat)
        location_event = self.create_fake_websocket_event(p_1_connection_id, body=player_location)

        def mock_send(connection_id, data):
            # assert that player_1's location data is sent to player_4, and the data is correct
            if connection_id == p_4_connection_id:
                self.assertEqual(self.p_1.username, data['name'])
                self.assertEqual(long, data['longitude'])
                self.assertEqual(lat, data['latitude'])
            # player_1's location data should also be sent to the game master
            elif connection_id == gm_connection_id:
                pass
            else:
                self.fail()

        with mock.patch('websockets.connection_manager.ConnectionManager.send_to_connection', side_effect=mock_send):
            # player_1 pushes their location through websocket
            player_location_message_handler(location_event, None)

    def test_gamemaster_websocket_message(self):
        # start lobby, connect two player who are in the same squad, one other player, and the game master
        self.gamemaster_1.start_game(self.lobby.name)

        p_1_connection_id = '123456'
        p_2_connection_id = '512512'
        p_4_connection_id = '223456'
        gm_connection_id = '341234'

        event_1 = self.create_fake_websocket_event(p_1_connection_id,
                                                   body={'access_token': '123456'})
        event_2 = self.create_fake_websocket_event(p_2_connection_id,
                                                   body={'access_token': '123456'})
        event_3 = self.create_fake_websocket_event(p_4_connection_id,
                                                   body={'access_token': '123456'})
        event_4 = self.create_fake_websocket_event(gm_connection_id,
                                                   body={'access_token': '123456'})

        with mock.patch('jwt.verify_token', return_value={'username': self.p_1.username}):
            authorize_connection_handler(event_1, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_2.username}):
            authorize_connection_handler(event_2, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.p_4.username}):
            authorize_connection_handler(event_3, None)
        with mock.patch('jwt.verify_token', return_value={'username': self.gamemaster_1.username}):
            authorize_connection_handler(event_4, None)

        # push message to all players from the game master
        message = {'message': dict(event='bounty-started')}
        event = self.create_fake_websocket_event(gm_connection_id, body=message)

        def mock_send(connection_id, data):
            # each connection id should be in the lobby, otherwise fail the test
            if connection_id not in [p_1_connection_id, p_2_connection_id, p_4_connection_id]:
                self.fail()
            self.assertEqual(message['message'], data)

        with mock.patch('websockets.connection_manager.ConnectionManager.send_to_connection', side_effect=mock_send):
            # gamemaster pushes message to all players
            gamemaster_message_handler(event, None)
