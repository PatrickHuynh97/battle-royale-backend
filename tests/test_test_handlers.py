from handlers.schemas import SquadSchema
from handlers.test_handlers import create_test_players_and_squads_handler
from tests.helper_functions import create_test_players, create_test_game_masters, make_api_gateway_event
from tests.mock_db import TestWithMockAWSServices


class TestTestHandlers(TestWithMockAWSServices):

    def setUp(self) -> None:
        # create some players and a gamemaster
        game_master_username = ['gm-1']
        player_username = ['player-1']
        self.player_1 = create_test_players(player_username)[0]
        self.gamemaster_1 = create_test_game_masters(game_master_username)[0]

    def test_create_test_players_and_squads_handler(self):
        event, context = make_api_gateway_event(calling_user=self.player_1)
        res = create_test_players_and_squads_handler(event, context)
        squads = SquadSchema().loads(res['body'], many=True)
        self.assertEqual(3, len(squads))
        for squad in squads:
            self.assertEqual(3, len(squad['members']))
