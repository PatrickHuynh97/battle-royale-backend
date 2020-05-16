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
    Handler that handles connects/disconnects over the Websocket API. Any user can connect but must authorize themselves
    after to begin receiving game data.
    :param event: event
    :param context: context
    :return: success message
    """
    connection_id = event['requestContext'].get('connectionId')
    event_type = event['requestContext'].get('eventType')

    if event_type == WebSocketEventType.CONNECT.value:
        # save anonymous user's connection_id and wait for further authorization
        ConnectionManager().connect_unauthorized(connection_id)

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
def authorize_connection_handler(event, context):
    """
    Called directly after $connect to the websocket. Authorizes a User and allows them to receive game data
    :param event: event
    :param context: context
    :return: None
    """
    from jwt import verify_token  # import here since it downloads a file each time it's run

    connection_id = event['requestContext'].get('connectionId')
    access_token = event['body']['access_token']
    connection_manager = ConnectionManager()

    # check that access token is valid, and matches that of user to be deleted
    claims = verify_token(access_token, id_token=True)

    # if access_token cannot be verified, disconnect the websocket
    if not claims:
        connection_manager.disconnect_unauthorized_connection(connection_id)

    # elevate the connection to a full connection to the respective game lobby
    ConnectionManager().authorize_connection(connection_id, claims['username'])

    return {
        'statusCode': 200,
        'body': json.dumps({'result': 'CONNECTED'})
    }


@endpoint()
def default_handler(event, context):
    """
    Handler that handles routing to a non-handled route
    :param event: event
    :param context: context
    :return: None
    """
    return {
        'statusCode': 400,
        'body': json.dumps({'result': 'NOT DEFINED ROUTE'})
    }


@endpoint()
def player_location_message_handler(event, context):
    """
    Handler that handles receiving messages sent from the clients via the 'location' action Route, e.g. payload
    body must contain {'action': 'location', 'long': ...}. This information will be forwarded to squad members and the
    gamemaster
    :param event: event containing longitude and latitude of player
    :param context: context
    :return: None
    """
    connection_manager = ConnectionManager()
    connection_id = event['requestContext'].get('connectionId')

    player = connection_manager.get_player(connection_id)
    player.get()

    player_long = event['body']['longitude']
    player_lat = event['body']['latitude']

    payload = dict(name=player.username, longitude=player_long, latitude=player_lat)

    # push location to squad mates
    connection_manager = ConnectionManager()
    squad_connection_ids = connection_manager.get_connected_squad_members(player)
    for connection_id in squad_connection_ids:
        connection_manager.send_to_connection(connection_id, payload)

    # push location to game master
    gamemaster_connection_id = ConnectionManager().get_game_master_from_player(player)
    connection_manager.send_to_connection(gamemaster_connection_id, payload)


@endpoint()
def gamemaster_message_handler(event, context):
    """
    Handler that receives messages sent from the game master via the 'fromgm' action Route, e.g. payload body must
    contain {'action': 'fromgm'}. This information will be forwarded to all players in the gamemaster's lobby, connected
    to the Lobby session/websocket
    :param event: event containing message for players in the Lobby
    :param context: context
    :return: None
    """
    connection_manager = ConnectionManager()
    connection_id = event['requestContext'].get('connectionId')

    gamemaster = connection_manager.get_game_master(connection_id)
    gamemaster.get()

    message = event['body']['message']

    # get all players belonging to gamemaster's lobby
    gamemaster.lobby.get()
    squad_connection_ids = connection_manager.get_players_in_lobby(gamemaster.lobby)
    for connection_id in squad_connection_ids:
        connection_manager.send_to_connection(connection_id, message)
