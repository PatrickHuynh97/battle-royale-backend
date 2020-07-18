from random import randint

from boto3.dynamodb.conditions import Attr

from db.dynamodb_connector import DynamoDbConnector
from enums import TestLobbyEventType
from exceptions import SetupError
from handlers.lambda_helpers import endpoint
from handlers.schemas import SquadSchema, LobbySchema, TestLobbyEventRequestSchema
from handlers.sqs_handlers import _handle_first_circle, _handle_close_circle
from models.game_master import GameMaster
from models.lobby import Lobby
from models.map import Circle
from models.player import Player
from models.squad import Squad
from helper_functions import create_test_players, create_test_squads, create_test_game_masters, make_sqs_events


@endpoint(response_schema=SquadSchema)
def create_test_players_and_squads_handler(event, context):
    """
    Handler for creating test players, and creating some squads from them. We will create 9 Players, then 3 squads
    of 3 with those 9 Players.
    """
    test_player_usernames = [f"test_player_{randint(1, 100000)}" for i in range(0, 9)]

    created_players = create_test_players(test_player_usernames)

    squad_leaders, members = created_players[:3], created_players[3:]
    created_squads = create_test_squads(created_players[:3])

    index = 0
    for squad in created_squads:
        for i in range(0, 2):
            squad.add_member(members[index])
            index += 1

    return [dict(name=squad.name,
                 owner=squad.owner.username,
                 members=[dict(username=member.username)
                          for member in squad.members])
            for squad in created_squads]


@endpoint()
def delete_test_players_and_squads_handler(event, context):
    """
    Handler for deleting test players.
    """
    _delete_test_players()


@endpoint(response_schema=LobbySchema)
def create_test_lobby_and_squads_handler(event, context):
    """
    Handler for creating a test lobby which has a few squads in it, and the calling user with a specified squads in it.
    We will create 9 Players random players with 3 squads, and also add in the calling user and their squad to the lobby.
    of 3 with those 9 Players.
    """
    squad_name = event['pathParameters']['squadname']
    test_player_usernames = [f"test_player_{randint(1, 100000)}" for i in range(0, 9)]

    # create test squad ands populate with fake players
    created_players = create_test_players(test_player_usernames)
    squad_leaders, members = created_players[:3], created_players[3:]
    created_squads = create_test_squads(created_players[:3])

    index = 0
    for squad in created_squads:
        for i in range(0, 2):
            squad.add_member(members[index])
            index += 1

    # create test game master, create lobby, and add all fake squads to it
    game_master = create_test_game_masters([f'test_game_master_{randint(1, 100000)}'])[0]
    lobby_name = f"test_lobby_{randint(1, 100000)}"
    game_zone_coordinates = [dict(latitude="56.132501", longitude="12.903200"),
                             dict(latitude="56.132757", longitude="12.897164"),
                             dict(latitude="56.130781", longitude="12.896993"),
                             dict(latitude="56.130309", longitude="12.902884")]
    final_circle = Circle(dict(centre=dict(latitude=56.130722, longitude=12.900430), radius=20 / 1000))

    lobby = game_master.create_lobby(lobby_name)
    game_master.add_squad_to_lobby(lobby_name, created_squads[0])
    game_master.add_squad_to_lobby(lobby_name, created_squads[1])
    game_master.add_squad_to_lobby(lobby_name, created_squads[2])
    game_master.add_squad_to_lobby(lobby_name, Squad(squad_name))
    game_master.update_lobby(lobby_name,
                             game_zone_coordinates=game_zone_coordinates,
                             final_circle=dict(centre=final_circle.centre,
                                               radius=final_circle.radius))
    lobby.get()
    lobby.get_squads()
    return {
        'name': lobby.name,
        'owner': lobby.owner.username,
        'state': lobby.state.value,
        'size': lobby.size,
        'squad_size': lobby.squad_size,
        'game_zone_coordinates': lobby.game_zone.coordinates,
        'current_circle': lobby.game_zone.current_circle,
        'next_circle': lobby.game_zone.next_circle,
        'squads': [dict(name=squad.name,
                        owner=squad.owner.username,
                        members=[member.username for member in squad.members])
                   for squad in lobby.squads]
    }


@endpoint()
def delete_test_lobby_and_squads_handler(event, context):
    """
    Handler for deleting test lobby and all associated test players/squads in it
    """
    _delete_test_game_masters()

    _delete_test_players()


@endpoint()
def start_test_lobby(event, context):
    """
    Handler for starting a test lobby which has been created through the createTestLobbyAndSquads endpoint (
    path=/test/create-lobby-and-squads/{squadname}). Does not enqueue trigger for next circle closing. Sends websocket
    that game started to any connected players
    """
    squad_name = event['pathParameters']['squadname']
    squad = Squad(squad_name)
    squad.get()

    if not squad.lobby_name and not squad.lobby_owner:
        raise SetupError("Test lobby must be created before running this function")

    game_master = GameMaster(squad.lobby_owner)
    game_master.get()
    from unittest import mock
    with mock.patch('sqs.utils.SqsQueue.send_message'):
        game_master.start_game()


@endpoint(request_schema=TestLobbyEventRequestSchema)
def make_test_lobby_event(event, context):
    """
    Handler for making an event in a test lobby occur.
    """
    event_type = TestLobbyEventType(event['body'].get('event_type'))
    value = event['body'].get('value')

    if event_type == TestLobbyEventType.KILL_PLAYER:
        """ 
        Kills the specified player. Websocket message is sent to squad mates + game master and looks like:
        {
            "event_type": "player_dead",
            "value": {"name":"username1234", "state":"dead"}
        }
        """
        test_kill_player(player_to_kill=value)

    elif event_type == TestLobbyEventType.GENERATE_FIRST_CIRCLE:
        """
        Generates the first circle as the SqsQueue would have done. Does not enqueue message to close to next circle as
        would be done through normal flow. 
        
        """
        squad_name = event['pathParameters']['squadname']
        squad = Squad(squad_name)
        squad.get()

        lobby = Lobby(squad.lobby_name, GameMaster(squad.lobby_owner))
        lobby.get()
        from unittest import mock
        with mock.patch('sqs.utils.SqsQueue.send_message'):
            _handle_first_circle(lobby)

    elif event_type == TestLobbyEventType.CLOSE_TO_NEXT_CIRCLE:
        """
        Closes the current circle to the next circle, as the SqsQueue message would have done. Cannot be called if
        the given lobby does not have a "next_circle" to close to.
        """
        squad_name = event['pathParameters']['squadname']
        squad = Squad(squad_name)
        squad.get()

        lobby = Lobby(squad.lobby_name, GameMaster(squad.lobby_owner))
        lobby.get()

        if not lobby.game_zone.next_circle:
            raise SetupError("generate_first_circle event must be triggered before trying to close to a next circle")

        from unittest import mock
        with mock.patch('sqs.utils.SqsQueue.send_message'):
            _handle_close_circle(lobby)

    elif event_type == TestLobbyEventType.END_GAME:
        squad_name = event['pathParameters']['squadname']
        squad = Squad(squad_name)
        squad.get()

        game_master = GameMaster(squad.lobby_owner)
        game_master.get()
        game_master.end_game()


def test_kill_player(player_to_kill: str):
    player = Player(player_to_kill)
    player.dead()


def _delete_test_players():
    table = DynamoDbConnector.get_table()
    players_to_delete = table.scan(
        FilterExpression=Attr("pk").begins_with("test_player_") & Attr("sk").eq('USER')
    )
    for player in players_to_delete['Items']:
        # get squad and fill with information
        player = Player(player['pk'])
        try:
            player.delete(None)  # delete test player without access token (they do not exist in cognito anyway)
        except Exception as e:
            print(e)


def _delete_test_game_masters():
    table = DynamoDbConnector.get_table()
    gms_to_delete = table.scan(
        FilterExpression=Attr("pk").begins_with("test_game_master_") & Attr("sk").eq('USER')
    )
    for gm in gms_to_delete['Items']:
        # get squad and fill with information
        gamemaster = GameMaster(gm['pk'])
        try:
            gamemaster.delete(None)  # delete test player without access token (they do not exist in cognito anyway)
        except Exception as e:
            print(e)
