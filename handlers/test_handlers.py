from random import randint

from boto3.dynamodb.conditions import Key, Attr

from db.dynamodb_connector import DynamoDbConnector
from handlers.lambda_helpers import endpoint
from handlers.schemas import SquadSchema
from models.player import Player
from tests.helper_functions import create_test_players, create_test_squads


@endpoint(response_schema=SquadSchema)
def create_test_players_and_squads_handler(event, context):
    """
    Handler for creating test players, and creating some squads from them. We will create 9 Players, then 3 squads
    of 3 with those 9 Players.
    """
    test_player_usernames = [f"test_player_{randint(1,100000)}" for i in range(0, 9)]

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
