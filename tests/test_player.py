import json
import os

import botocore
from unittest import mock
from exceptions import UserAlreadyExistsException, SquadAlreadyExistsException, PlayerOwnsSquadException, \
    PlayerDoesNotOwnSquadException, UserAlreadyMemberException, LobbyNotStartedException, SquadDoesNotExistException
from handlers.player_handlers import get_owned_squads_handler, set_dead_handler, set_alive_handler, \
    get_current_lobby_handler, get_squads_handler
from handlers.schemas import LobbySchema, SquadSchema
from enums import PlayerState
from models.game_master import GameMaster
from models import player as player_model
from models.squad import Squad
from helper_functions import make_api_gateway_event, create_test_players
from tests.mock_db import TestWithMockAWSServices
os.environ['local_test'] = "True"  # must be set to prevent jwt file http GET from being called in 'handlers' import
from handlers import account_handlers, player_handlers


class TestPlayer(TestWithMockAWSServices):

    def setUp(self):
        usernames = ['username-1', 'username-2', 'username-3']
        self.player_1, self.player_2, self.player_3 = create_test_players(usernames)

    def test_create_player(self):
        # test creating a single player
        username = "test-user"
        player = player_model.Player(username)
        player.put()

        player.get()
        self.assertEqual(username, player.username)

    def test_create_duplicate_player(self):
        # test trying to create two players with same usernams
        username = "test-user"
        player = player_model.Player(username)
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
        player = player_model.Player(username)
        player.put()

        self.assertTrue(player.exists())

    def test_delete_player(self):
        username = "test-user"
        player = player_model.Player(username)
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
        player_1 = player_model.Player(username)
        player_1.put()

        player_2 = player_model.Player("player_2")
        player_2.put()

        squad_1_name = 'squad_one'
        # create squad and add player_2 in
        squad = player_1.create_squad(squad_1_name)
        player_1.add_member_to_squad(squad, player_2)

        squad2 = player_2.create_squad('squad_two')
        player_2.add_member_to_squad(squad2, player_1)

        player_1_owned_squads = player_1.get_owned_squads()
        player_2_owned_squads = player_2.get_owned_squads()

        player_1_not_owned_squads = player_1.get_not_owned_squads()
        player_2_not_owned_squads = player_2.get_not_owned_squads()

        self.assertTrue(len(player_1_owned_squads) == 1)
        self.assertTrue(len(player_2_owned_squads) == 1)
        self.assertTrue(player_1_owned_squads[0] != player_2_owned_squads[0])

        self.assertTrue(len(player_1_not_owned_squads) == 1)
        self.assertTrue(len(player_2_not_owned_squads) == 1)
        self.assertTrue(player_1_not_owned_squads[0] != player_2_not_owned_squads[0])

        self.assertTrue(len(player_1_owned_squads[0].members) == 2)
        self.assertTrue(len(player_1_not_owned_squads[0].members) == 2)
        self.assertTrue(len(player_2_owned_squads[0].members) == 2)
        self.assertTrue(len(player_2_not_owned_squads[0].members) == 2)

        self.assertTrue(player_1 in player_2_owned_squads[0].members)
        self.assertTrue(player_2 in player_1_owned_squads[0].members)

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
        with self.assertRaises(SquadDoesNotExistException):
            Squad(squad_1_name).get()
        player_2_owned_squads = player_2.get_owned_squads()

        self.assertTrue(len(player_2_owned_squads) == 1)
        self.assertTrue(len(player_2_owned_squads[0].members) == 1)
        self.assertTrue(player_2_owned_squads[0].members[0] == player_2)

    def test_create_squad(self):
        squad_name_1 = 'test-squad-1'
        squad_name_2 = 'test-squad-2'

        # create a squad
        event, context = make_api_gateway_event(path_params={'squadname': squad_name_1}, calling_user=self.player_1)
        res = player_handlers.create_squad_handler(event, context)
        self.assertEqual(200, res['statusCode'])

        squad_1 = Squad(squad_name_1)
        squad_1.get()
        self.assertEqual(self.player_1.username, squad_1.owner.username)
        self.assertEqual(squad_name_1, squad_1.name)

        # create another squad
        # create a squad
        event, context = make_api_gateway_event(path_params={'squadname': squad_name_2}, calling_user=self.player_1)
        res = player_handlers.create_squad_handler(event, context)
        self.assertEqual(200, res['statusCode'])
        squad_2 = Squad(squad_name_2)
        squad_2.get()
        self.assertEqual(self.player_1.username, squad_2.owner.username)
        self.assertEqual(squad_name_2, squad_2.name)

    def test_delete_squad(self):
        squad_name_1 = 'test-squad-1'
        squad_name_2 = 'test-squad-2'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)
        squad_2 = self.player_1.create_squad(squad_name_2)

        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                path_params=dict(squadname=squad_1.name,
                                                                 username=self.player_2.username))
        player_handlers.add_user_to_squad_handler(event, context)

        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                path_params=dict(squadname=squad_2.name,
                                                                 username=self.player_3.username))
        player_handlers.add_user_to_squad_handler(event, context)

        fresh_squad_1 = Squad(squad_name_1)
        fresh_squad_2 = Squad(squad_name_2)
        fresh_squad_1.get_members()
        fresh_squad_2.get_members()

        # squad 1 has player 1 and 2, squad 2 has players 1 and 3
        self.assertTrue(self.player_1 in fresh_squad_1.members)
        self.assertTrue(self.player_2 in fresh_squad_1.members)
        self.assertTrue(self.player_1 in fresh_squad_2.members)
        self.assertTrue(self.player_3 in fresh_squad_2.members)
        self.assertTrue(len(self.player_2.get_not_owned_squads()) == 1)
        self.assertTrue(len(self.player_3.get_not_owned_squads()) == 1)

        event, context = make_api_gateway_event(body={'name': squad_1.name},
                                                calling_user=self.player_1,
                                                path_params=dict(squadname=squad_1.name))
        player_handlers.delete_squad_handler(event, context)

        self.player_1.delete_squad(squad_1)

        self.assertFalse(Squad(squad_name_1).exists())
        self.assertTrue(len(self.player_2.get_not_owned_squads()) == 0)
        self.assertTrue(len(self.player_3.get_not_owned_squads()) == 1)
        self.assertTrue(squad_2.exists())

    def test_get_squad(self):
        squad_name_1 = 'test-squad-1'

        # create a squad
        squad_1 = self.player_1.create_squad(squad_name_1)

        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                path_params=dict(squadname=squad_1.name,
                                                                 username=self.player_2.username))
        player_handlers.add_user_to_squad_handler(event, context)

        event, context = make_api_gateway_event(calling_user=self.player_1,
                                                path_params=dict(squadname=squad_1.name))
        res = player_handlers.get_squad_handler(event, context)
        body = SquadSchema().loads(res['body'])
        self.assertTrue(len(body['members']) == 2)

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

        # try to remove owner from squad as the owner
        self.assertRaises(PlayerOwnsSquadException, self.player_1.remove_member_from_squad, squad_1, self.player_1)

    def test_remove_members_from_squad_not_owner(self):
        # create squad, add two members
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)

        # try to remove squad owner from squad, as a member that is not the owner
        self.assertRaises(PlayerOwnsSquadException, self.player_2.remove_member_from_squad, squad_1, self.player_1)

        # try to remove other member from squad, as a member that is not the owner
        self.assertRaises(PlayerDoesNotOwnSquadException, self.player_2.remove_member_from_squad, squad_1, self.player_3)

    def test_remove_members_from_squad(self):
        # create squad, add two members, assert that squad now has 2 members in it
        squad_name_1 = 'test-squad-1'
        squad_1 = self.player_1.create_squad(squad_name_1)
        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_1.add_member_to_squad(squad_1, self.player_3)
        self.assertEqual(3, len(squad_1.members))

        # as the owner, remove player_2
        self.player_1.remove_member_from_squad(squad_1, self.player_2)
        squad_1.get_members()
        self.assertTrue(self.player_2 not in squad_1.members)

        # as player_3, remove self from squad
        self.player_3.remove_member_from_squad(squad_1, self.player_3)
        squad_1.get_members()
        self.assertTrue(self.player_3 not in squad_1.members)

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

        event, context = make_api_gateway_event(calling_user=self.player_2)
        res = player_handlers.get_not_owned_squads_handler(event, context)
        squads_player_2_is_in = json.loads(res['body'])

        self.assertEqual(1, len(squads_player_2_is_in))
        self.assertEqual(squad.name, squads_player_2_is_in[0]['name'])
        self.assertEqual(squad.owner.username, squads_player_2_is_in[0]['owner'])

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

        self.assertEqual(1, len(body))
        self.assertEqual(squad_1.name, body[0]['name'])
        self.assertEqual(3, len(body[0]['members']))

    def test_get_all_squads(self):
        # player_1 creates squad, adds player_2
        squad_1_name = 'test-squad-1'
        squad_2_name = 'test-squad-2'

        squad_1 = self.player_1.create_squad(squad_1_name)
        squad_2 = self.player_2.create_squad(squad_2_name)

        self.player_1.add_member_to_squad(squad_1, self.player_2)
        self.player_2.add_member_to_squad(squad_2, self.player_1)
        self.player_1.add_member_to_squad(squad_1, self.player_3)

        event, context = make_api_gateway_event(calling_user=self.player_1, body={'username': self.player_1.username})
        res = get_squads_handler(event, context)

        self.assertEqual(200, res['statusCode'])
        squads = SquadSchema().loads(res['body'], many=True)
        for squad in squads:
            if squad['name'] == squad_1_name:
                self.assertEqual(self.player_1.username, squad['owner'])
                self.assertEqual(3, len(squad['members']))

            elif squad['name'] == squad_2_name:
                self.assertEqual(self.player_2.username, squad['owner'])
                self.assertEqual(2, len(squad['members']))

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
        with mock.patch("sqs.closing_circle_queue.CircleQueue.send_first_circle_event"):
            gamemaster.start_game()
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
        with mock.patch("sqs.closing_circle_queue.CircleQueue.send_first_circle_event"):
            gamemaster.start_game()
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
