from handlers.lambda_helpers import endpoint
from handlers.schemas import LobbySchema, LobbyPlayerListSchema, UpdateLobbySchema
from models.game_master import GameMaster
from models.squad import Squad


@endpoint()
def create_lobby_handler(event, context):
    """
    Handler for creating a lobby.
    """
    username = event['calling_user']
    body = event['body']
    lobby_name = body['name']
    lobby_size = body.get('lobby_size')
    squad_size = body.get('squad_size')
    game_master = GameMaster(username)
    game_master.get()
    game_master.create_lobby(lobby_name=lobby_name, size=lobby_size, squad_size=squad_size)


@endpoint(response_schema=LobbySchema)
def get_lobby_handler(event, context):

    """
    Handler for getting a lobby, information about the lobby, and all squads in the lobby.
    """
    username = event['calling_user']
    gamemaster = GameMaster(username)
    gamemaster.get()
    lobby = gamemaster.get_lobby()
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
            'final_circle': lobby.final_circle,
            'squads': [dict(name=squad.name,
                            owner=squad.owner.username,
                            members=[dict(username=member.username)
                                     for member in squad.members])
                       for squad in lobby.squads]
        }


@endpoint()
def delete_lobby_handler(event, context):
    """
    Handler for deleting a lobby.
    """
    username = event['calling_user']
    lobby_name = event['body']['name']

    GameMaster(username).delete_lobby(lobby_name)


@endpoint()
def add_squad_to_lobby_handler(event, context):
    """
    Handler for adding a squad to the Lobby.
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']
    squad_name = event['body']['squad_name']

    GameMaster(username).add_squad_to_lobby(lobby_name, Squad(squad_name))


@endpoint()
def remove_squad_from_lobby_handler(event, context):
    """
    Handler for removing a squad from the lobby.
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']
    squad_name = event['body']['squad_name']

    GameMaster(username).remove_squad_from_lobby(lobby_name, Squad(squad_name))


@endpoint(response_schema=LobbyPlayerListSchema)
def get_players_in_lobby_handler(event, context):

    """
    Handler for getting every player in the Lobby and their current state
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']

    players = GameMaster(username).get_players_in_lobby(lobby_name)

    return dict(players=players)


@endpoint(request_schema=UpdateLobbySchema)
def update_lobby_handler(event, context):
    """
    Handler for updating lobby settings, such as lobby size, squad size, game zone coordinates
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']

    body = event['body']

    GameMaster(username).update_lobby(lobby_name,
                                      size=body.get('size'),
                                      squad_size=body.get('squad_size'),
                                      game_zone_coordinates=body.get('game_zone_coordinates'),
                                      final_circle=body.get('final_circle'))


@endpoint()
def start_lobby_handler(event, context):
    """
    Handler for starting the lobby
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']

    GameMaster(username).start_game(lobby_name)


@endpoint()
def end_lobby_handler(event, context):
    """
    Handler for ending the lobby
    """
    username = event['calling_user']
    lobby_name = event['pathParameters']['lobby']

    GameMaster(username).end_game(lobby_name)
