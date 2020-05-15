import json
from enums import WebSocketEventType, GameMasterMessageType
from exceptions import LiveDataConnectionException
from models.game_master import GameMaster
from models.player import Player
from websockets.connection_manager import ConnectionManager
from handlers.lambda_helpers import endpoint


@endpoint()
def connection_handler(event, context):
    """
    Handler that handles connects/disconnects over the Websocket API. Authenticated with an Authorizer. Depending on
    the type of client connecting, we will save them differently in the database.
    :param event: event
    :param context: context
    :return: success message
    """
    username = event['calling_user']
    connection_id = event['requestContext'].get('connectionId')
    event_type = event['requestContext'].get('eventType')

    if event_type == WebSocketEventType.CONNECT.value:
        # connect a user to a started Lobby
        ConnectionManager().connect(connection_id, username)

    elif event_type == WebSocketEventType.DISCONNECT.value:
        # disconnect a user
        ConnectionManager().disconnect(connection_id)
    else:
        raise LiveDataConnectionException("Failed to establish connection")

    return {
        'statusCode': 200,
        'body': json.dumps({'result': 'CONNECTED'})
    }


@endpoint()
def player_location_message_handler(event, context):
    """
    Handler that handles receiving messages sent from the clients via the 'location' action Route, e.g. payload
    body must contain {'action': 'location'}. This information will be forwarded to squad members and the gamemaster
    :param event: event containing longitude and latitude of player
    :param context: context
    :return: None
    """
    player = Player(event['calling_user'])
    player.get()

    player_long = event['body']['long']
    player_lat = event['body']['lat']

    payload = dict(name=player.username, longitude=player_long, latitude=player_lat)

    # push location to squad mates
    connection_manager = ConnectionManager()
    squad_connection_ids = connection_manager.get_connected_squad_members(player)
    for connection_id in squad_connection_ids:
        connection_manager.send_to_connection(connection_id, payload)

    # push location to game master
    gamemaster_connection_id = ConnectionManager().get_game_master(player)
    connection_manager.send_to_connection(gamemaster_connection_id, payload)


@endpoint()
def gamemaster_message_handler(event, context):
    """
    Handler that receives messages sent from the game master via the 'fromgm' action Route, e.g. payload body must
    contain {'action': 'fromgm'}. This information will be forwarded to all players in the gamemaster's lobby connected
    to the Lobby session/websocket
    :param event: event containing message for devices
    :param context: context
    :return: None
    """
    gamemaster = GameMaster(event['calling_user'])
    gamemaster.get()

    message = event['body']['message']

    payload = dict(message_type=GameMasterMessageType.EXAMPLE.value,
                   message=message)

    # get all players belonging to gamemaster's lobby
    connection_manager = ConnectionManager()
    squad_connection_ids = connection_manager.get_players_in_lobby(gamemaster.lobby)
    for connection_id in squad_connection_ids:
        connection_manager.send_to_connection(connection_id, payload)
