from db.dynamodb_connector import DynamoDbConnector
from exceptions import UserDoesNotExistException
from models.lobby import Lobby
from models.user import User


class GameMaster(User):
    """
    A Game Master type of User.
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.table = DynamoDbConnector.get_table()

    def __eq__(self, other):
        """If a Game Master object has the same username as another Game Master object, they are the same Game Master"""
        if isinstance(other, GameMaster):
            return self.username == other.username
        return False

    def get(self):
        """
        Gets a player from the database
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

        return {
            'username': gm['pk']
        }

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

        # delete player from database
        self.table.delete_item(
            Key={
                'pk': self.username,
                'sk': 'USER'
            },
        )
        # delete user from Cognito service
        self.cognito_client.delete_user(AccessToken=access_token)

    def create_lobby(self, lobby_name, lobby_size=None, squad_size=None):
        """
        Create a new game lobby for Players to join
        :param lobby_name: Name of game lobby
        :param lobby_size: Number of squads allowed in the lobby
        :param squad_size: Size of squad allowed in the lobby
        :return: Game lobby object
        """
        lobby = Lobby(lobby_name, owner=self, lobby_size=lobby_size, squad_size=squad_size)
        lobby.put()
        return lobby

    def get_lobby(self, lobby_name):
        """
        Get a lobby owned by Game Master
        :param lobby_name: name of lobby to get
        :return: Game lobby object
        """
        lobby = Lobby(lobby_name, owner=self)
        lobby.get()
        return lobby
