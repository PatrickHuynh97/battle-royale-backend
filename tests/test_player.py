import json
import os

import botocore
from unittest import mock
from exceptions import UserAlreadyExistsException, SquadAlreadyExistsException, PlayerOwnsSquadException, \
    PlayerDoesNotOwnSquadException, UserAlreadyMemberException, LobbyNotStartedException
from handlers.player_handlers import get_owned_squads_handler, set_dead_handler, set_alive_handler, \
    get_current_lobby_handler
from handlers.schemas import LobbySchema
from enums import PlayerState
from models.game_master import GameMaster
from models.player import Player
from models.squad import Squad
from tests.helper_functions import make_api_gateway_event, create_test_players
from tests.mock_db import TestWithMockAWSServices
os.environ['local_test'] = "True"  # must be set to prevent jwt file http GET from being called in 'handlers' import
from handlers import account_handlers


class TestPlayer(TestWithMockAWSServices):

    def setUp(self):
        usernames = ['username-1', 'username-2', 'username-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(usernames)

    def test_create_player(self):
        # test creating a single player
        username = "test-user"
        player = Player(username)
        player.put()

        player.get()
        self.assertEqual(username, player.username)

    def test_create_duplicate_player(self):
        # test trying to create two players with same usernams
        username = "test-user"
        player = Player(username)
        player.put()

        self.assertTrue(player.exists())

        # go through handler to create duplicate
        event, context = make_api_gateway_event(body={'username': username})
        res = account_handlers.sign_up_handler(event, context)
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
            if operation_name == 'Query' or operation_name == 'DeleteItem' or operation_name == 'GetItem':
                return orig(self, operation_name, kwarg)
            else:
                pass

        with mock.patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call):
            player.delete('dummy_token')
        self.assertFalse(player.exists())

    def test_delete_player_with_squads(self):
        username = "test-user"
        player_1 = Player(username)
        player_1.put()

        player_2 = Player("player_2")
        player_2.put()

        # create squad and add player_2 in
        squad = player_1.create_squad('squad_one')
        player_1.add_member_to_squad(squad, player_2)

        self.assertTrue(len(player_1.get_owned_squads()) == 1)
        self.assertTrue(len(player_2.get_not_owned_squads()) == 1)

        orig = botocore.client.BaseClient._make_api_call

        # mock calls to cognito identify provider whilst allowing calls to DynamoDB
        def mock_make_api_call(self, operation_name, kwarg):
            if operation_name == 'Query' or operation_name == 'DeleteItem' or operation_name == 'GetItem':
                return orig(self, operation_name, kwarg)
            else:
                pass

        with mock.patch('botocore.client.BaseClient._make_api_call', new=mock_make_api_call):
            player_1.delete('dummy_token')

        # assert that player_1 was deleted and the squad they owned disbanded
        self.assertFalse(player_1.exists())
        self.assertTrue(len(player_2.get_not_owned_squads()) == 0)

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
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.delete_squad(squad_1)

        self.assertFalse(squad_1.exists())

    def test_delete_squad_not_owner(self):
        squad_name_1 = 'test-squad-1'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.assertRaises(PlayerDoesNotOwnSquadException, self.player_2.delete_squad, squad_1)

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

    def test_add_duplicate_members_to_squad(self):
        # create squad, add member
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.assertEqual(2, len(squad_1.members))

        # try to add player_2 again
        self.assertRaises(UserAlreadyMemberException, self.player_1.add_member_to_squad, squad_1, self.player_2)

    def test_remove_owner_from_squad(self):
        # create squad, add one members
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # try to remove owner from squad
        self.assertRaises(PlayerOwnsSquadException, self.player_1.remove_member_from_squad, squad_1, self.player_1)

    def test_remove_members_from_squad_not_owner(self):
        # create squad, add one members
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # try to remove players as Player who is not owner
        self.assertRaises(PlayerDoesNotOwnSquadException, self.player_2.remove_member_from_squad, squad_1, self.player_1)

    def test_remove_members_from_squad(self):
        # create squad, add two members, assert that squad now has 2 members in it
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

    def test_leave_squad(self):
        # player_1 creates squad, adds player_2 and player_3
        squad_name_1 = 'test-squad-1'
        squad = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad, self.player_2)
        self.player_1.add_member_to_squad(squad, self.player_3)

        # get fresh squad object to verify
        fresh_squad = Squad(squad_name_1)
        fresh_squad.get()
        fresh_squad.get_members()
        self.assertEqual(self.player_1, fresh_squad.owner)
        self.assertIn(self.player_1, fresh_squad.members)
        self.assertIn(self.player_2, fresh_squad.members)
        self.assertIn(self.player_3, fresh_squad.members)

        # player_1 cannot leave squad as they own it
        self.assertRaises(PlayerOwnsSquadException, self.player_1.leave_squad, fresh_squad)

        # player 3 leaves squad
        self.player_3.leave_squad(fresh_squad)

        # get fresh squad object again
        fresh_squad = Squad(squad_name_1)
        fresh_squad.get()
        fresh_squad.get_members()
        self.assertIn(self.player_1, fresh_squad.members)
        self.assertIn(self.player_2, fresh_squad.members)
        self.assertNotIn(self.player_3, fresh_squad.members)

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

    def test_get_current_lobby_handler(self):
        # create squad, and add to lobby
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

        # create gamemaster, create lobby, and add squad_1 in
        actual_lobby_name = 'test-lobby'
        gamemaster = GameMaster('gm')
        lobby = gamemaster.create_lobby(actual_lobby_name)
        gamemaster.add_squad_to_lobby(actual_lobby_name, squad_1)

        event, context = make_api_gateway_event(calling_user=self.player_1)
        retrieved_lobby = get_current_lobby_handler(event, context)
        data = LobbySchema().loads(retrieved_lobby['body'])
        self.assertEqual(lobby.name, data['name'])

    def test_get_current_state(self):
        # create squad, and add to lobby
        squad_1 = self.player_1.create_squad('test-squad-1')
        squad_2 = self.player_3.create_squad('test-squad-2')
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # create gamemaster, create lobby, and add squad_1 in
        lobby_name = 'test-lobby'
        gamemaster = GameMaster('gm')
        gamemaster.create_lobby(lobby_name)
        gamemaster.add_squad_to_lobby(lobby_name, squad_1)
        gamemaster.add_squad_to_lobby(lobby_name, squad_2)

        state = self.player_1.get_current_state()
        self.assertEqual(PlayerState.ALIVE, state)

        # start game, kill player
        gamemaster.start_game(lobby_name)
        self.player_1.dead()

        state = self.player_1.get_current_state()
        self.assertEqual(PlayerState.DEAD, state)

    def test_set_dead_set_alive(self):
        # create two squads
        squad_name_1 = 'test-squad-1'
        squad_name_2 = 'test-squad-2'

        squad_1 = self.player_1.create_squad(squad_name_1)
        squad_2 = self.player_3.create_squad(squad_name_2)
        self.player_1.add_member_to_squad(squad_1, self.player_2)

        # create gamemaster, create lobby, and both squads in
        actual_lobby_name = 'test-lobby'
        gamemaster = GameMaster('gm')
        lobby = gamemaster.create_lobby(actual_lobby_name)
        gamemaster.add_squad_to_lobby(actual_lobby_name, squad_1)
        gamemaster.add_squad_to_lobby(actual_lobby_name, squad_2)

        # try to set player as dead before the game is started
        with self.assertRaises(LobbyNotStartedException):
            self.player_1.dead()

        # start game, mark player_1 as dead through handler
        gamemaster.start_game(lobby.name)
        event, context = make_api_gateway_event(calling_user=self.player_1)
        set_dead_handler(event, context)
        self.player_1.dead()

        # get all players, check that player_1 is dead and all other players are alive
        players = gamemaster.get_players_in_lobby(lobby.name)
        for player in players:
            if player['name'] == self.player_1.username:
                self.assertEqual(PlayerState.DEAD.value, player['state'])
            else:
                self.assertEqual(PlayerState.ALIVE.value, player['state'])

        # revive player_1, assert that everyone is alive again
        event, context = make_api_gateway_event(calling_user=self.player_1)
        set_alive_handler(event, context)

        players = gamemaster.get_players_in_lobby(lobby.name)
        for player in players:
            self.assertEqual(PlayerState.ALIVE.value, player['state'])
