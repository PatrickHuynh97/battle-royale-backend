from handlers.lambda_helpers import endpoint
from handlers.schemas import SquadListSchema, LobbySchema
from models.player import Player
from models.squad import Squad


@endpoint()
def create_squad_handler(event, context):
    """
    Handler for creating a squad.
    """
    username = event['calling_user']
    squad_name = event['body']['name']

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
    user_to_add = event['body']['username']

    Player(username).add_member_to_squad(squad=Squad(squad_name),
                                         new_member=Player(user_to_add))


@endpoint()
def remove_member_from_squad_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']
    user_to_remove = event['body']['username']

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


@endpoint(response_schema=LobbySchema)
def get_current_lobby_handler(event, context):
    """
    Handler for getting the lobby the player is currently in. Omits information such as final circle location.
    """
    username = event['calling_user']

    lobby = Player(username).get_current_lobby()
    lobby.get()
    lobby.get_squads()

    return {
            'name': lobby.name,
            'owner': lobby.owner.username,
            'state': lobby.state.value,
            'size': lobby.size,
            'squad_size': lobby.squad_size,
            'game_zone_coordinates': lobby.game_zone.coordinates,
            'current_circle': lobby.current_circle,
            'next_circle': lobby.next_circle,
            'squads': [dict(name=squad.name,
                            owner=squad.owner.username,
                            members=[dict(username=member.username)
                                     for member in squad.members])
                       for squad in lobby.squads]
        }


@endpoint()
def get_current_state_handler(event, context):
    """
    Handler for getting current state of the player if they are in a Lobby
    """
    username = event['calling_user']

    state = Player(username).get_current_state()

    return dict(state=state.value)


@endpoint()
def set_dead_handler(event, context):
    """
    Handler for setting a player as dead in the current lobby they are in
    """
    username = event['calling_user']

    Player(username).dead()


@endpoint()
def set_alive_handler(event, context):
    """
    Handler for setting a player as alive in the current lobby they are in
    """
    username = event['calling_user']

    Player(username).alive()


@endpoint()
def pull_squad_from_lobby_handler(event, context):
    """
    Handler for pulling the squad the player owns and is currently in a lobby with, out of the lobby
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']
    Player(username).pull_squad_from_lobby(Squad(squad_name))
