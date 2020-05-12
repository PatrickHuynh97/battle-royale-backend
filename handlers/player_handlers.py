from handlers.lambda_helpers import endpoint
from handlers.schemas import SquadListSchema
from models.player import Player
from models.squad import Squad


@endpoint()
def create_squad_handler(event, context):
    """
    Handler for creating a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']

    Player(username).create_squad(squad_name=squad_name)


@endpoint()
def delete_squad_handler(event, context):
    """
    Handler for deleting a squad.
    """
    username = event['calling_user']
    squad_name = event['body']['name']

    Player(username).delete_squad(squad=Squad(squad_name))


@endpoint()
def add_user_to_squad_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']
    user_to_add = event['body']['member']

    Player(username).add_member_to_squad(squad=Squad(squad_name),
                                         new_member=Player(user_to_add))


@endpoint()
def remove_member_from_squad_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']
    user_to_remove = event['body']['member']

    Player(username).remove_member_from_squad(squad=Squad(squad_name),
                                              member_to_remove=Player(user_to_remove))


@endpoint(response_schema=SquadListSchema)
def get_owned_squads_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']

    squads = Player(username).get_owned_squads()

    return {
        'squads': [
            dict(name=squad.name,
                 owner=squad.owner.username,
                 members=[dict(username=member.username) for member in squad.members])
        ] for squad in squads
    }


@endpoint(response_schema=SquadListSchema)
def get_not_owned_squads_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']

    squads = Player(username).get_not_owned_squads()

    return {
        'squads': [
            dict(name=squad.name,
                 owner=squad.owner.username,
                 members=[dict(username=member.username) for member in squad.members])
        ] for squad in squads
    }
