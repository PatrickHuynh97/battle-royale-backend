from db.dynamodb_connector import DynamoDbConnector
from exceptions import LobbyDoesNotExistException
from models import game_master


class Lobby:
    """
    Lobby objects stores information about a game
    """

    def __init__(self, name, owner, lobby_size=None, squad_size=None):
        self.name = name
        self.owner = owner
        self.lobby_size = lobby_size
        self.squad_size = squad_size
        self.table = DynamoDbConnector.get_table()

    def put(self):
        """
        Inserts a new lobby into the database
        :return: None
        """
        item = {
            'pk': self.name,
            'sk': f'USER#{self.owner.username}',
            'lsi': f'LOBBY',
        }
        if self.lobby_size:
            item['lobby-size'] = self.lobby_size
        if self.squad_size:
            item['squad-size'] = self.squad_size

        self.table.put_item(
            Item=item
        )

    def get(self):
        """
        Gets lobby from the database
        :return: Information about the game lobby
        """
        response = self.table.get_item(
            Key={
                'pk': self.name,
                'sk': f'USER#{self.owner.username}',
            }
        )
        lobby = response.get('Item')

        if not lobby:
            raise LobbyDoesNotExistException("Lobby with name {} does not exist".format(self.name))

        self.owner = game_master.GameMaster(lobby['sk'].split('#')[1])
        self.lobby_size = lobby.get('lobby-size')
        self.squad_size = lobby.get('squad-size')

    def exists(self):
        """
        If lobby with given name and owner exists, returns True
        :return: True if player exists, else False
        """
        try:
            self.get()
            return True
        except LobbyDoesNotExistException:
            return False

    def delete(self):
        """
        Delete a lobby from the system
        :return: None
        """

        # delete lobby from database
        self.table.delete_item(
            Key={
                'pk': self.name,
                'sk': f'USER#{self.owner.username}'
            }
        )

    def update(self, lobby_size: int = None, squad_size: int = None):
        # todo implementation
        pass
