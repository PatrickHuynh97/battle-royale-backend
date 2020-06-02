from random import randint

from handlers.lambda_helpers import endpoint
from handlers.schemas import SquadSchema
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
