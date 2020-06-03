from boto3.dynamodb.conditions import Key, Attr

from db.dynamodb_connector import DynamoDbConnector
from handlers.schemas import SquadSchema
from handlers.test_handlers import create_test_players_and_squads_handler, delete_test_players_and_squads_handler
from tests.helper_functions import create_test_players, create_test_game_masters, make_api_gateway_event
from tests.mock_db import TestWithMockAWSServices


class TestTestHandlers(TestWithMockAWSServices):

    def setUp(self) -> None:
        player_username = ['player-1']
        self.player_1 = create_test_players(player_username)[0]

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
