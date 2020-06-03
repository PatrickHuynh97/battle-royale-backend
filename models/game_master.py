from db.dynamodb_connector import DynamoDbConnector
from exceptions import UserDoesNotExistException, LobbyDoesNotExistException, LobbyAlreadyStartedException, \
    GameMasterAlreadyInLobbyException, GameMasterNotInLobbyException
from enums import LobbyState
from models import lobby as lobby_model
from models import user


class GameMaster(user.User):
    """
    A Game Master type of User.
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.table = DynamoDbConnector.get_table()
        self.lobby = None  # only set if game master is in a lobby

    def __eq__(self, other):
        """If a Game Master object has the same username as another Game Master object, they are the same Game Master"""
        if isinstance(other, GameMaster):
            return self.username == other.username
        return False

    def get(self):
        """
        Gets a GameMaster from the database
        :return: Information about the player
        """
        response = self.table.get_item(
            Key={
                'pk': self.username,
                'sk': 'USER'
            },
        )
        gm = response.get('Item')

        if not gm:
            raise UserDoesNotExistException("Game Master with username {} does not exist".format(self.username))

        self.lobby = lobby_model.Lobby(gm.get('lobby-name'), self) if gm.get('lobby-name') else None

    def exists(self):
        """
        If player with given username exists, returns True
        :return: True if player exists, else False
        """
        try:
            self.get()
            return True
        except UserDoesNotExistException:
            return False

    def put(self):
        """
        Inserts a new player into the database
        :return: None
        """

        self.table.put_item(
            Item={
                'pk': self.username,
                'sk': 'USER',
            }
        )

    def delete(self, access_token):
        """
        Delete a player from the system
        :param access_token: Access token used to verify the user is who the they say they are
        :return: None
        """

        self.get()
        if self.lobby:
            self.delete_lobby(self.lobby.name)

        # delete player from database
        self.table.delete_item(
            Key={
                'pk': self.username,
                'sk': 'USER'
            },
        )
        # delete user from Cognito service
        self.cognito_client.delete_user(AccessToken=access_token)

    def create_lobby(self, lobby_name, size=15, squad_size=4):
        """
        Create a new game lobby for Players to join
        :param lobby_name: Name of game lobby
        :param size: Number of squads allowed in the lobby. Default size is 15
        :param squad_size: Maximum size of squad allowed in the lobby. Default squad size is 4
        :return: Game lobby object
        """
        if self.lobby:
            raise GameMasterAlreadyInLobbyException("GameMaster already has an open lobby")
        lobby = lobby_model.Lobby(lobby_name, owner=self)
        lobby.put(size=size, squad_size=squad_size)
        self.set_in_lobby(lobby)
        self.lobby = lobby
        return lobby

    def delete_lobby(self, lobby_name):
        """
        Delete a lobby
        :param lobby_name: Name of game lobby to delete
        :return: None
        """
        lobby = lobby_model.Lobby(lobby_name, owner=self)
        lobby.get_squads()
        lobby.delete()
        self.set_no_lobby()
        return lobby

    def get_lobby(self):
        """
        Get a lobby owned by Game Master if they are currently in one. self.get() should be called before calling this
        :return: Game lobby object
        """
        self.get()
        if not self.lobby:
            raise GameMasterNotInLobbyException("Game Master is not currently in a Lobby")
        self.lobby.get()
        return self.lobby

    def update_lobby(self, lobby_name, size=None, squad_size=None, game_zone_coordinates=None, final_circle=None):
        """
        Update a lobby owned by Game Master
        :param lobby_name: name of lobby to update
        :param size: size of lobby
        :param squad_size: size of squads allowed in lobby
        :param game_zone_coordinates: four coordinates making up the game zone
        :param final_circle: coordinates of centre and radius of final circle
        """
        lobby = lobby_model.Lobby(lobby_name, owner=self)
        if not lobby.exists():
            raise LobbyDoesNotExistException
        lobby.update(size, squad_size, game_zone_coordinates, final_circle=final_circle)
        return lobby

    def set_in_lobby(self, lobby):
        """
        If Game Master has created a Lobby set flag
        :param lobby: lobby the Game Master has created
        :return:
        """

        self.table.update_item(
            Key={
                'pk': self.username,
                'sk': f'USER'
            },
            AttributeUpdates={'lobby-name': dict(Value=lobby.name),
                              'lobby-owner': dict(Value=self.username)})

    def set_no_lobby(self):
        """
        If Game Master has disbanded a Lobby set flag
        :return:
        """

        self.table.update_item(
            Key={
                'pk': self.username,
                'sk': f'USER'
            },
            AttributeUpdates={'lobby-name': dict(Value=None),
                              'lobby-owner': dict(Value=None)})

    def add_squad_to_lobby(self, lobby_name, squad):
        """
        Add a squad to a lobby
        :param lobby_name: name of Lobby
        :param squad: Squad object
        """
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        if lobby.state == LobbyState.STARTED:
            raise LobbyAlreadyStartedException("Cannot add squads to a started game")

        squad.get()  # get basic squad information
        squad.get_members()  # get each member

        lobby.get_squads()  # get latest list of all squads in the lobby already
        lobby.add_squad(squad)

    def remove_squad_from_lobby(self, lobby_name, squad):
        """
        Remove a squad from a Lobby
        :param lobby_name: Name of lobby
        :param squad: Squad object
        """
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        if lobby.state == LobbyState.STARTED:
            raise LobbyAlreadyStartedException("Cannot remove squads from started game")
        lobby.get_squads()
        lobby.remove_squad(squad)

    def get_squads_in_lobby(self, lobby_name):
        """
        Get list of squads in the lobby
        :param lobby_name: name of Lobby
        :return: list of squads in the lobby
        """
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        lobby.get_squads()
        return lobby.squads

    def start_game(self, lobby_name):
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        lobby.get_squads()
        lobby.start()

    def end_game(self, lobby_name):
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        lobby.end()

    def get_players_in_lobby(self, lobby_name):
        """
        Get list of players in a lobby and their state
        :param lobby_name: Name of lobby to get all players from
        :return: List of players in the lobby and their state
        """
        lobby = lobby_model.Lobby(lobby_name, self)
        lobby.get()
        return lobby.get_players_and_states()
