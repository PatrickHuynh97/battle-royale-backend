from boto3.dynamodb.conditions import Attr

from handlers.schemas import SquadSchema
from handlers.test_handlers import create_test_players_and_squads_handler, delete_test_players_and_squads_handler, \
    create_test_lobby_and_squads_handler, delete_test_lobby_and_squads_handler
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
