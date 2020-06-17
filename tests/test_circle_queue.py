import json
from unittest import mock
from enums import SQSEventType, WebSocketPushMessageType
from handlers.sqs_handlers import circle_queue_handler
from models.map import Circle
from helper_functions import create_test_players, create_test_game_masters, create_test_squads, make_sqs_events
from tests.mock_db import TestWithMockAWSServices
from tests.test_classes import MockQueue


class TestCircleQueue(TestWithMockAWSServices):

    def setUp(self):
        # create players, game masters and squads
        game_master_usernames = ['gm-1']
        player_usernames = ['player-1', 'player-2', 'player-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(player_usernames)
        self.game_master_1 = create_test_game_masters(game_master_usernames)[0]
        self.squad_1, self.squad_2, self.squad_3 = create_test_squads([self.player_1, self.player_2, self.player_3])

        # create game lobby with predefined coordinates
        self.game_zone_coordinates = [dict(latitude="56.132501", longitude="12.903200"),
                                      dict(latitude="56.132757", longitude="12.897164"),
                                      dict(latitude="56.130781", longitude="12.896993"),
                                      dict(latitude="56.130309", longitude="12.902884")]
        self.final_circle = Circle(dict(centre=dict(latitude=56.130722, longitude=12.900430), radius=20 / 1000))

    def test_first_circle_event(self):
        # create a lobby, add some squads
        lobby = self.set_up_lobby()

        # start and end game
        mock_circle_queue = MockQueue()
        with mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message):
            self.game_master_1.start_game(lobby.name)

        self.assertTrue(mock_circle_queue.records)
        record = json.loads(mock_circle_queue.records[0]['body'])
        self.assertEqual(SQSEventType.FIRST_CIRCLE.value, record['event_type'])
        self.assertEqual(lobby.name, record['lobby_name'])
        self.assertEqual(lobby.owner.username, record['lobby_owner'])

        self.game_master_1.end_game(lobby.name)

    def test_sqs_handler_first_circle_event(self):
        lobby = self.set_up_lobby()

        # start game and get SQS event that would have been queued
        mock_circle_queue = MockQueue()
        with mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message):
            self.game_master_1.start_game(lobby.name)
        self.assertTrue(mock_circle_queue.records)
        sqs_events = make_sqs_events([json.loads(record['body']) for record in mock_circle_queue.records])

        # new mock queue for closing of first circle event
        mock_circle_queue = MockQueue()
        with mock.patch('websockets.connection_manager.ConnectionManager._send_to_connections') as mock_send, \
                mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message):
            circle_queue_handler(sqs_events, None)
            websocket_message = mock_send.call_args[1]['data']
            lobby.get()

            self.assertEqual(WebSocketPushMessageType.NEXT_CIRCLE.value, websocket_message['event_type'])
            self.assertEqual(lobby.game_zone.next_circle.to_dict(), websocket_message['value'])
            self.assertTrue(len(mock_circle_queue.records) == 1)

            # make sure that closing of the first circle has been scheduled
            close_circle_sqs_event = json.loads(mock_circle_queue.records[0]['body'])
            self.assertEqual(lobby.name, close_circle_sqs_event['lobby_name'])
            self.assertEqual(lobby.owner.username, close_circle_sqs_event['lobby_owner'])
            self.assertEqual(SQSEventType.CLOSE_CIRCLE.value, close_circle_sqs_event['event_type'])

    def test_sqs_handler_close_circle_event(self):
        lobby = self.set_up_lobby()

        # start game, generate first circle as it would be normally, and get SQS event of closing of first circle
        mock_circle_queue = MockQueue()
        with mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message):
            self.game_master_1.start_game(lobby.name)
        sqs_events = make_sqs_events([json.loads(record['body']) for record in mock_circle_queue.records])

        # new mock queue for closing of first circle event
        mock_circle_queue = MockQueue()
        with mock.patch('websockets.connection_manager.ConnectionManager._send_to_connections') as mock_send, \
                mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message):
            circle_queue_handler(sqs_events, None)
            lobby.get()
            first_circle = lobby.game_zone.next_circle
            # make sure that closing of the first circle has been scheduled
            close_circle_sqs_event = json.loads(mock_circle_queue.records[0]['body'])
        sqs_events = make_sqs_events([close_circle_sqs_event])

        mock_circle_queue = MockQueue()
        with mock.patch('websockets.connection_manager.ConnectionManager.push_circle_updates') as mock_push_circle, \
                mock.patch('sqs.utils.SqsQueue.send_message', side_effect=mock_circle_queue.send_message), \
                mock.patch('time.sleep'):
            circle_queue_handler(sqs_events, None)
            next_circle_close_event = json.loads(mock_circle_queue.records[0]['body'])
            intermediate_circles = mock_push_circle.call_args[0][0]
            retrieved_lobby = mock_push_circle.call_args[1]['lobby']

            # make sure that intermediate circles have same centre as the next circle and radius is getting smaller
            self.assertEqual(lobby, retrieved_lobby)
            last_radius = None
            for circle in intermediate_circles:
                self.assertEqual(first_circle.centre, circle['centre'])
                if not last_radius:
                    last_radius = circle['radius']
                else:
                    self.assertTrue(last_radius > circle['radius'])
            self.assertEqual(SQSEventType.CLOSE_CIRCLE.value, next_circle_close_event['event_type'])

            # final intermediate circle should be the same as the next_circle it is converging towards
            self.assertEqual(first_circle, Circle(intermediate_circles[-1]))

    def set_up_lobby(self):
        # create a lobby, add some squads
        lobby_name = 'test-lobby'
        lobby = self.game_master_1.create_lobby(lobby_name, size=20)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_1)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_2)
        self.game_master_1.add_squad_to_lobby(lobby_name, self.squad_3)
        self.game_master_1.update_lobby(lobby_name,
                                        game_zone_coordinates=self.game_zone_coordinates,
                                        final_circle=dict(centre=self.final_circle.centre,
                                                          radius=self.final_circle.radius))
        return lobby
