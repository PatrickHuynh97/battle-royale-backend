from unittest import mock

from boto3.dynamodb.conditions import Attr

from enums import TestLobbyEventType, PlayerState, LobbyState
from handlers.schemas import SquadSchema
from handlers.test_handlers import create_test_players_and_squads_handler, delete_test_players_and_squads_handler, \
    create_test_lobby_and_squads_handler, delete_test_lobby_and_squads_handler, start_test_lobby, make_test_lobby_event
from helper_functions import create_test_players, make_api_gateway_event
from tests.mock_db import TestWithMockAWSServices


class TestTestHandlers(TestWithMockAWSServices):

    def setUp(self) -> None:
        player_username = ['player-1', 'player-2']
        self.player_1, self.player_2 = create_test_players(player_username)

    def test_create_test_players_and_squads_handler(self):
        event, context = make_api_gateway_event(calling_user=self.player_1)
        res = create_test_players_and_squads_handler(event, context)
        squads = SquadSchema().loads(res['body'], many=True)

        self.assertEqual(3, len(squads))
        for squad in squads:
            self.assertEqual(3, len(squad['members']))

    def test_delete_test_players_and_squads_handler(self):
        event, context = make_api_gateway_event(calling_user=self.player_1)
        res = create_test_players_and_squads_handler(event, context)
        squads = SquadSchema().loads(res['body'], many=True)
        self.assertEqual(3, len(squads))

        event, context = make_api_gateway_event(calling_user=self.player_1)
        delete_test_players_and_squads_handler(event, context)
        players_to_delete = self.table.scan(
            FilterExpression=Attr("pk").begins_with("test_player_") & Attr("sk").eq('USER')
        )
        # should be no users in the database with a name that begins with test_player_
        self.assertFalse(players_to_delete['Items'])

    def test_test_lobby_and_squads_handler(self):
        squad_1 = self.player_1.create_squad('test-squad-1')
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        event, context = make_api_gateway_event(calling_user=self.player_1, path_params=dict(squadname=squad_1.name))
        res = create_test_lobby_and_squads_handler(event, context)
        self.assertEqual(200, res['statusCode'])

        event, context = make_api_gateway_event(calling_user=self.player_1)
        delete_test_lobby_and_squads_handler(event, context)
        players_to_delete = self.table.scan(
            FilterExpression=Attr("pk").begins_with("test_player_") & Attr("sk").eq('USER')
        )
        # should be no users in the database with a name that begins with test_player_
        self.assertFalse(players_to_delete['Items'])

        players_to_delete = self.table.scan(
            FilterExpression=Attr("pk").begins_with("test_game_master_") & Attr("sk").eq('USER')
        )
        # should be no users in the database with a name that begins with test_player_
        self.assertFalse(players_to_delete['Items'])

    def test_start_test_lobby(self):
        # create squad and call endpoint to create test lobby
        squad_1 = self.player_1.create_squad('test-squad-1')
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        event, context = make_api_gateway_event(calling_user=self.player_1, path_params=dict(squadname=squad_1.name))
        res = create_test_lobby_and_squads_handler(event, context)
        self.assertEqual(200, res['statusCode'])

        res = start_test_lobby(event, context)
        self.assertEqual(200, res['statusCode'])

    def __call_test_lobby_and_start(self):
        # create squad and call endpoint to create test lobby
        squad_1 = self.player_1.create_squad('test-squad-1')
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        event, context = make_api_gateway_event(calling_user=self.player_1, path_params=dict(squadname=squad_1.name))
        res = create_test_lobby_and_squads_handler(event, context)

        event, context = make_api_gateway_event(calling_user=self.player_1, path_params=dict(squadname=squad_1.name))
        start_test_lobby(event, context)
        return res, squad_1

    def test_kill_player_event(self):
        # create squad and call endpoint to create test lobby
        test_lobby, squad = self.__call_test_lobby_and_start()

        # assert that player is in ALIVE state
        current_state = self.player_2.get_current_state()
        self.assertEqual(PlayerState.ALIVE, current_state)

        body = dict(event_type=TestLobbyEventType.KILL_PLAYER.value, value=self.player_2.username)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        res = make_test_lobby_event(event, context)
        self.assertEqual(200, res['statusCode'])

        # check that player_2 is now in DEAD state
        current_state = self.player_2.get_current_state()
        self.assertEqual(PlayerState.DEAD, current_state)

    def test_generate_first_circle_event(self):
        # create squad and call endpoint to create test lobby
        test_lobby, squad = self.__call_test_lobby_and_start()
        squad.get()

        body = dict(event_type=TestLobbyEventType.GENERATE_FIRST_CIRCLE.value)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        res = make_test_lobby_event(event, context)
        self.assertEqual(200, res['statusCode'])

        # retrieve lobby and assert that there is now a next_circle
        self.player_2.get()
        lobby = self.player_2.lobby
        lobby.get()
        self.assertIsNotNone(lobby.game_zone.next_circle)

    def test_close_circle_event(self):
        # create squad and call endpoint to create test lobby
        test_lobby, squad = self.__call_test_lobby_and_start()

        # should not be able to close circle without having one generated beforehand
        body = dict(event_type=TestLobbyEventType.CLOSE_TO_NEXT_CIRCLE.value)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        res = make_test_lobby_event(event, context)
        self.assertEqual(400, res['statusCode'])

        body = dict(event_type=TestLobbyEventType.GENERATE_FIRST_CIRCLE.value)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        res = make_test_lobby_event(event, context)
        self.assertEqual(200, res['statusCode'])

        self.player_2.get()
        lobby = self.player_2.lobby
        lobby.get()
        first_circle = lobby.game_zone.next_circle

        body = dict(event_type=TestLobbyEventType.CLOSE_TO_NEXT_CIRCLE.value)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        with mock.patch('time.sleep'):
            res = make_test_lobby_event(event, context)
        self.assertEqual(200, res['statusCode'])
        lobby.get()
        current_circle = lobby.game_zone.current_circle
        next_circle = lobby.game_zone.next_circle

        self.assertEqual(first_circle, current_circle)
        self.assertNotEqual(first_circle, next_circle)

        # make sure second circle has a smaller radius than first one
        self.assertLess(next_circle.radius, current_circle.radius)

    def test_end_game_event(self):
        # create squad and call endpoint to create test lobby
        test_lobby, squad = self.__call_test_lobby_and_start()

        # should not be able to close circle without having one generated beforehand
        body = dict(event_type=TestLobbyEventType.END_GAME.value)
        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                body=body,
                                                path_params=dict(squadname=squad.name))
        res = make_test_lobby_event(event, context)

        self.assertEqual(200, res['statusCode'])

        self.player_2.get()
        lobby = self.player_2.lobby
        lobby.get()
        self.assertEqual(LobbyState.FINISHED, lobby.state)
