import json
from enums import WebSocketEventType
from exceptions import LiveDataConnectionException
from websockets import connection_manager as cm
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
        cm.ConnectionManager().connect_unauthorized(connection_id)

    elif event_type == WebSocketEventType.DISCONNECT.value:
        # disconnect a user
        cm.ConnectionManager().disconnect(connection_id)
    else:
        raise LiveDataConnectionException("Failed to establish connection")

    return {
        'statusCode': 200,
        'body': {'result': 'CONNECTED'}
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
    connection_manager = cm.ConnectionManager()

    # check that access token is valid, and matches that of user to be deleted
    claims = verify_token(access_token, id_token=True)

    # if access_token cannot be verified, disconnect the websocket
    if not claims:
        connection_manager.disconnect_unauthorized_connection(connection_id)

    # elevate the connection to a full connection to the respective game lobby
    cm.ConnectionManager().authorize_connection(connection_id, claims['username'])

    return {
        'statusCode': 200,
        'body': {'result': 'CONNECTED'}
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
    connection_manager = cm.ConnectionManager()
    connection_id = event['requestContext'].get('connectionId')

    player_long = event['body']['longitude']
    player_lat = event['body']['latitude']

    connection_manager.push_player_location(connection_id, player_lat, player_long)


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
    connection_manager = cm.ConnectionManager()
    connection_id = event['requestContext'].get('connectionId')
    message = event['body']['value']

    connection_manager.push_game_master_message(connection_id, message)
