import json
from handlers.player_handlers import get_owned_squads_handler
from tests.helper_functions import make_api_gateway_event, create_test_players
from tests.mock_db import TestWithMockAWSServices


class TestHandlers(TestWithMockAWSServices):

    def setUp(self):
        usernames = ['username-1', 'username-2', 'username-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(usernames)

    def test_get_owned_squad(self):
        # create squad, add two more members, assert that squad now has 2 members in it
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

        # go through handler to create duplicate
        event, context = make_api_gateway_event(calling_user=self.player_1, body={'username': self.player_1.username})
        res = get_owned_squads_handler(event, context)
        body = json.loads(res['body'])

        self.assertEqual(1, len(body['squads']))
        self.assertEqual(squad_1.name, body['squads'][0]['name'])
        self.assertEqual(3, len(body['squads'][0]['members']))
