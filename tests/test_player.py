import json
from unittest import mock

import botocore

from exceptions import UserAlreadyExistsException, SquadAlreadyExistsException, UserOwnsSquadException, \
    UserDoesNotOwnSquadException
from handlers.authorization_handlers import sign_up_handler
from models.player import Player
from models.squad import Squad
from tests.helper_functions import make_api_gateway_event, create_test_players
from tests.mock_db import TestWithMockAWSServices


class TestPlayer(TestWithMockAWSServices):

    def setUp(self):
        usernames = ['username-1', 'username-2', 'username-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(usernames)

    def test_create_player(self):
        # test creating a single player
        username = "test-user"
        player = Player(username)
        player.put()

        res = player.get()
        self.assertEqual(username, res['username'])

    def test_create_duplicate_player(self):
        # test trying to create two players with same usernams
        username = "test-user"
        player = Player(username)
        player.put()

        self.assertTrue(player.exists())

        # go through handler to create duplicate
        event, context = make_api_gateway_event(body={'username': username})
        res = sign_up_handler(event, context)
        body = json.loads(res['body'])

        # assert that a duplicate player was not created
        self.assertEqual(400, res['statusCode'])
        self.assertEqual(UserAlreadyExistsException.tag, body['type'])

    def test_player_exists(self):
        username = "test-user"
        player = Player(username)
        player.put()

        self.assertTrue(player.exists())

    def test_delete_player(self):
        username = "test-user"
        player = Player(username)
        player.put()

        self.assertTrue(player.exists())

        orig = botocore.client.BaseClient._make_api_call

        # mock calls to cognito identify provider whilst allowing calls to DynamoDB
        def mock_make_api_call(self, operation_name, kwarg):
            if operation_name == 'Query' or operation_name == 'DeleteItem':
                return orig(self, operation_name, kwarg)
            else:
                pass

        with mock.patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call):
            player.delete('dummy_token')
        self.assertFalse(player.exists())

    def test_create_squad(self):
        squad_name_1 = 'test-squad-1'
        squad_name_2 = 'test-squad-2'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)
        squad_1.get()
        self.assertEqual(self.player_1.username, squad_1.owner.username)
        self.assertEqual(squad_name_1, squad_1.name)

        # create another squad
        squad_2 = self.player_1.create_squad(squad_name_2)
        squad_2.get()
        self.assertEqual(self.player_1.username, squad_2.owner.username)
        self.assertEqual(squad_name_2, squad_2.name)

    def test_delete_squad(self):
        squad_name_1 = 'test-squad-1'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.delete_squad(squad_1)

        self.assertFalse(squad_1.exists())

    def test_delete_squad_not_owner(self):
        squad_name_1 = 'test-squad-1'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.assertRaises(UserDoesNotOwnSquadException, self.player_2.delete_squad, squad_1)

    def test_create_duplicate_squad(self):
        squad_name = 'test-squad-1'

        # create single squad
        squad = self.player_1.create_squad(squad_name)
        self.assertTrue(squad.exists())

        # try to create another squad with the same name
        self.assertRaises(SquadAlreadyExistsException, self.player_1.create_squad, squad_name)

    def test_get_owned_squads(self):
        squad_name_1 = 'test-squad-1'
        squad_name_2 = 'test-squad-2'

        # create two squads
        squad_1 = self.player_1.create_squad(squad_name_1)
        squad_1.get()
        squad_2 = self.player_1.create_squad(squad_name_2)
        squad_2.get()

        # assert that player owns two squads
        squads = self.player_1.get_owned_squads()
        self.assertTrue(2, len(squads))

    def test_add_members_to_squad(self):
        # create squad, add two members, assert that squad now has 2 members in it
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

        # get fresh squad object to verify
        fresh_squad_1 = Squad(squad_name_1)
        fresh_squad_1.get()
        fresh_squad_1.get_members()
        self.assertEqual(self.player_1, fresh_squad_1.owner)
        self.assertIn(self.player_1, fresh_squad_1.members)
        self.assertIn(self.player_2, fresh_squad_1.members)
        self.assertIn(self.player_3, fresh_squad_1.members)

    def test_remove_owner_from_squad(self):
        # create squad, add one members
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # try to remove owner from squad
        self.assertRaises(UserOwnsSquadException, self.player_1.remove_member_from_squad, squad_1, self.player_1)

    def test_remove_members_from_squad_not_owner(self):
        # create squad, add one members
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # try to remove players as Player who is not owner
        self.assertRaises(UserDoesNotOwnSquadException, self.player_2.remove_member_from_squad, squad_1, self.player_1)

    def test_remove_members_from_squad(self):
        # create squad, add two members, assert that squad now has 2 members in it
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

        # delete player_3 from squad, assert that player_3 was removed and other players were not touched
        self.player_1.remove_member_from_squad(squad_1, self.player_3)
        self.assertIn(self.player_1, squad_1.members)
        self.assertIn(self.player_2, squad_1.members)
        self.assertNotIn(self.player_3, squad_1.members)

    def test_get_not_owned_squads(self):
        # player_1 creates squad, adds player_2
        squad_name = 'test-squad-1'
        squad = self.player_1.create_squad(squad_name)
        self.player_1.add_member_to_squad(squad, self.player_2)

        # assert that both players are in the squad, and player_2 is not the owner
        squad.get_members()
        self.assertIn(self.player_1, squad.members)
        self.assertIn(self.player_2, squad.members)
        self.assertNotEqual(squad.owner, self.player_2)

        squads_player_2_is_in = self.player_2.get_not_owned_squads()

        self.assertEqual(1, len(squads_player_2_is_in))
        self.assertEqual(squad, squads_player_2_is_in[0])
