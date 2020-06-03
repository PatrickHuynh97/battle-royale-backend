import json
import os
import time
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key
from db.dynamodb_connector import DynamoDbConnector
from enums import LobbyState, PlayerState, WebSocketPushMessageType
from exceptions import PlayerNotInLobbyException, LobbyNotStartedException
from models import game_master as game_master_model
from models import player as player_model


class ConnectionManager:

    def __init__(self):
        self.table = DynamoDbConnector.get_table()

    def connect_unauthorized(self, connection_id):
        """
        Connect an anonymous, authorized user. User must then authenticate themselves after establishing this connection
        or they are forcefully disconnected. # todo cron job to clean this stuff up
        :param connection_id: Id of websocket connection
        """
        # save connection_id of unauthorized user
        _ = self.table.put_item(
            Item={
                'pk': 'CONNECTION#UNAUTHORIZED',
                'sk': connection_id,
                'lsi': str(datetime.now()),
                'lsi-2': 'UNAUTHORIZED'
            }
        )

    def get_unauthorized_connections(self):
        response = self.table.query(
            IndexName='lsi-2',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('CONNECTION#UNAUTHORIZED') & Key('lsi-2').eq('UNAUTHORIZED')
        )
        return [item['sk'] for item in response['Items']]

    def disconnect_unauthorized_connection(self, connection_id):
        """
        Disconnects an authorized user.
        :param connection_id: Id of websocket connection
        """
        # delete connection_id of unauthorized user
        _ = self.table.delete_item(
            Key={
                'pk': 'CONNECTION#UNAUTHORIZED',
                'sk': connection_id
            }
        )

    def get_player_connections(self, lobby):
        """
        Get all players currently connected to a lobby
        :return: List of active connectionIds.
        """
        response = self.table.query(
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('sk').begins_with(f'LOBBY#{lobby.unique_id}'),
        )['Items']

        return [
            dict(name=player['sk'].split('#')[3], squad=player['lsi'].split('#')[1]) for player in response
        ]

    def authorize_connection(self, connection_id, username):
        """
        Connect a User to the right game session depending on their current state.
        :param connection_id: Id of websocket connection
        :param username: username of User trying to connect to a game session
        """
        # remove unauthorized connection
        self.disconnect_unauthorized_connection(connection_id)

        # check if username is a player and they are in a lobby
        try:
            player = player_model.Player(username)
            lobby = player.get_current_lobby()  # throws UserNotInLobbyException if they're not in a lobby
            lobby.get()

            if lobby.state != LobbyState.STARTED:
                raise LobbyNotStartedException("Lobby has not started yet")

            # if the user is the owner of the lobby they are in, then they are a gamemaster
            if player.lobby.owner == player.username:
                raise PlayerNotInLobbyException

            self.handle_player_connect(player, lobby, connection_id)

        # User is not a player. Check if username belongs to a GameMaster
        except PlayerNotInLobbyException:
            try:
                gamemaster = game_master_model.GameMaster(username)
                lobby = gamemaster.get_lobby()  # throws UserNotInLobbyException if they're not in a lobby
                lobby.get()

                if lobby.state != LobbyState.STARTED:
                    raise LobbyNotStartedException("Lobby has not started yet")

                self.handle_game_master_connect(gamemaster, lobby, connection_id)

            # User is neither a Player nor a GameMaster in a started Lobby
            except PlayerNotInLobbyException:
                raise PlayerNotInLobbyException(f"User with username {username} is not in a started Lobby")

    def handle_player_connect(self, player, lobby, connection_id):
        """
        Player is connecting to a started Lobby. We use lobby unique_id in the sort key to make sure there are no
        crossovers with other lobbies that have a similar name
        :param player: player who is connecting to a started Lobby
        :param lobby: Lobby which has started
        :param connection_id: unique connection_id for websocket session
        :return:
        """
        # get current state to find which squad they are playing in
        player_state = lobby.get_player(player)
        _ = self.table.put_item(
            Item={
                'pk': 'CONNECTION',
                'sk': f'LOBBY#{lobby.unique_id}#PLAYER#{player.username}',
                'lsi': f'SQUAD#{player_state["squad_name"]}',
                'lsi-2': connection_id
            }
        )

    def handle_game_master_connect(self, gamemaster, lobby, connection_id):
        """
        If a GameMaster is connecting to a started Lobby
        :param gamemaster: gamemaster who is connecting to a started Lobby
        :param lobby: Lobby which has started
        :param connection_id: unique connection_id for websocket session
        :return:
        """
        _ = self.table.put_item(
            Item={
                'pk': 'CONNECTION',
                'sk': f'GAMEMASTER#{gamemaster.username}',
                'lsi': f'LOBBY#{lobby.unique_id}',
                'lsi-2': connection_id
            }
        )

    def disconnect(self, connection_id):
        """
        Disconnect an active connection
        :param connection_id: ID of connection to be disconnected
        """
        self.disconnect_unauthorized_connection(connection_id)

        # first retrieve connection from local secondary index
        response = self.table.query(
            IndexName='lsi-2',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('lsi-2').eq(connection_id)
        )

        # Should only be 1 result from this query, otherwise the user is not connected
        connections = response.get('Items')
        if not connections:
            return

        # fail-safe for duplicate results
        for connection in connections:
            _ = self.table.delete_item(
                Key={
                    'pk': 'CONNECTION',
                    'sk': connection['sk'],
                }
            )

    def get_connected_squad_members(self, player):
        """
        Given a player, retrieves the connection_id's of squad members connected to the lobby session
        :param player: Player to retrieve squad mates of
        :return: List of squad-mate connection_id's
        """

        response = self.table.query(
            IndexName='lsi',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('lsi').eq(f'SQUAD#{player.squad.name}')
        )['Items']

        connection_ids = []
        for squad_member in response:
            name = squad_member['sk'].split('#')[3]
            if player.username != name:
                connection_ids.append(squad_member['lsi-2'])

        return connection_ids

    def get_game_master_from_player(self, player):
        """
        Given a player, gets the connection_id of the GameMaster of their lobby if they are connected
        :param player: Player to get GameMaster connection_id of
        :return: connection_id of GameMaster if they are connected, otherwise None
        """
        response = self.table.get_item(
            Key={
                'pk': 'CONNECTION',
                'sk': f'GAMEMASTER#{player.lobby.owner.username}'
            },
        )
        gm = response.get('Item')
        if gm:
            return gm['lsi-2']
        else:
            return None

    def get_player(self, connection_id):
        """
        Get a player from the Lobby session from their connection_id
        :param connection_id: connection id of player websocket connection
        :return:
        """
        response = self.table.query(
            IndexName='lsi-2',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('lsi-2').eq(connection_id)
        )['Items']

        if not response:
            raise PlayerNotInLobbyException("No player with this connection_id is connected")

        return player_model.Player(response[0]['sk'].split('#')[3])

    def get_game_master(self, connection_id):
        """
        Get a GameMaster from the Lobby session from their connection_id
        :return: connection_id of GameMaster if they are connected, otherwise None
        """
        response = self.table.query(
            IndexName='lsi-2',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('lsi-2').eq(connection_id)
        )['Items']

        if not response:
            raise PlayerNotInLobbyException("No GameMaster with this connection_id is connected")

        return game_master_model.GameMaster(response[0]['sk'].split('#')[1])

    def get_players_in_lobby(self, lobby):
        """
        Gets all players connected to lobby session belonging to gamemaster
        :param lobby: lobby to get all players in
        :return: list of connection_id's of each player in GameMaster's lobby
        """
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('sk').begins_with(f'LOBBY#{lobby.unique_id}')
        )['Items']

        connection_ids = []
        for player in response:
            connection_ids.append(player['lsi-2'])

        return connection_ids

    def get_game_master_in_lobby(self, lobby):
        """
        Gets the GameMaster connected to lobby session
        :param lobby: lobby to get GameMaster of
        :return:connection_id of the GameMaster
        """
        response = self.table.query(
            IndexName='lsi',
            KeyConditionExpression=Key('pk').eq('CONNECTION') & Key('lsi').eq(f'LOBBY#{lobby.unique_id}')
        )['Items']
        if response:
            return response[0]['lsi-2']
        else:
            return None

    def push_player_dead(self, player):
        """
        Given a player, send a message to their GM and squad mates that they are dead, if they are connected
        :param player: Player that is now dead
        :return: None
        """
        payload = dict(event_type=WebSocketPushMessageType.PLAYER_DEAD.value,
                       value=dict(name=player.username, state=PlayerState.DEAD.value))

        gm = self.get_game_master_from_player(player)
        squad_members = self.get_connected_squad_members(player)

        if gm:
            self._send_to_connection(gm, payload)
        for member in squad_members:
            self._send_to_connection(member, payload)

    def push_circle_updates(self, circles: list, lobby):
        """
        Given a dict of circles, pushes each sequential circle data to all connected players and game master over each
        second.
        :param circles: list of circles to push. They are in order of decreasing size
        :param lobby: lobby to send circle data to
        :return: None
        """
        # for each circle, push the circle data to the game master and connected players
        connection_ids = self._get_all_connected(lobby)

        for circle in circles:
            # each second, push the next circle location to connected players
            payload = dict(event_type=WebSocketPushMessageType.CIRCLE_CLOSING.value,
                           value=circle)
            self._send_to_connections(connection_ids, payload)
            time.sleep(1)

    def push_game_state(self, lobby):
        connection_ids = self._get_all_connected(lobby)
        payload = dict(event_type=WebSocketPushMessageType.GAME_STATE.value,
                       value=lobby.state.value)
        self._send_to_connections(connection_ids, payload)

    def push_player_location(self, connection_id, player_lat, player_long):
        """
        Given a connection_id belonging to a player, and their latitude and longitude, this is then sent to their
        squad mates and the game master
        :param connection_id: connection_id belonging to player
        :param player_lat:  latitude of player
        :param player_long: longitude of player
        :return: None
        """
        player = self.get_player(connection_id)
        player.get()

        payload = dict(event_type=WebSocketPushMessageType.PLAYER_LOCATION.value,
                       value=dict(name=player.username,
                                  longitude=player_long,
                                  latitude=player_lat))

        # push location to squad mates and game master
        connection_manager = ConnectionManager()
        connection_ids = connection_manager.get_connected_squad_members(player)
        gamemaster_connection_id = ConnectionManager().get_game_master_from_player(player)
        if gamemaster_connection_id:
            connection_ids.append(gamemaster_connection_id)

        connection_manager._send_to_connections(connection_ids, payload)

    def push_game_master_message(self, connection_id, data):
        gamemaster = self.get_game_master(connection_id)
        gamemaster.get()

        # get all players belonging to gamemaster's lobby
        gamemaster.lobby.get()
        squad_connection_ids = self.get_players_in_lobby(gamemaster.lobby)
        payload = dict(event_type=WebSocketPushMessageType.GAME_MASTER_MESSAGE.value,
                       value=data)
        self._send_to_connections(squad_connection_ids, payload)

    def push_next_circle(self, lobby):
        """
        Pushes the location of a new Circle to all players and the game master
        :param lobby: Lobby of which next_circle we should push
        :return: None
        """
        connection_ids = self._get_all_connected(lobby)
        payload = dict(event_type=WebSocketPushMessageType.NEXT_CIRCLE.value,
                       value=lobby.game_zone.next_circle.to_string())
        self._send_to_connections(connection_ids, data=payload)

    def _get_all_connected(self, lobby):
        # gets all players and the GameMaster connected to the lobby
        connection_ids = self.get_players_in_lobby(lobby)
        gm = self.get_game_master_in_lobby(lobby)
        if gm:
            connection_ids.append(gm)
        return connection_ids

    def _send_to_connection(self, connection_id, data):
        """
        Send a message to a websocket client.
        :param connection_id: ID of websocket client
        :param data: data to send through websocket
        """

        websocket_url = os.environ.get('WEBSOCKET_URL')

        gateway_api = boto3.client("apigatewaymanagementapi", endpoint_url=websocket_url)
        self._send_data(gateway_api, connection_id, data)

    def _send_to_connections(self, connection_ids, data):
        """
        Send a message to a list of websocket clients.
        :param connection_ids: list containing connection_ID of each target client
        :param data: data to send through websocket
        """

        websocket_url = os.environ.get('WEBSOCKET_URL')

        gateway_api = boto3.client("apigatewaymanagementapi", endpoint_url=websocket_url)
        for connection_id in connection_ids:
            self._send_data(gateway_api, connection_id, data)

    @staticmethod
    def _send_data(gateway_api, connection_id, data):
        try:
            return gateway_api.post_to_connection(ConnectionId=connection_id,
                                                  Data=json.dumps(data).encode('utf-8'))
        except gateway_api.exceptions.GoneException:
            # if client disconnects from Websocket ungracefully, remove from database as well somehow
            ConnectionManager().disconnect(connection_id)
