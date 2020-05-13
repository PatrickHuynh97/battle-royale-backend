from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import LobbyDoesNotExistException, SquadAlreadyInLobbyException, GameMasterNotOwnLobbyException, \
    SquadNotInLobbyException, SquadTooBigException, LobbyFullException, \
    LobbyAlreadyStartedException, NotEnoughSquadsException, PlayerAlreadyInLobbyException
from models import game_master
from models.enums import LobbyState, PlayerState
from models import squad as squad_model


class Lobby:
    """
    Lobby objects stores information about a game
    """

    def __init__(self, name, owner):
        self.name = name
        self.owner = owner
        self.size = None
        self.squad_size = None
        self.state = None
        self.squads = []
        self.table = DynamoDbConnector.get_table()

    def __eq__(self, other):
        """If a Player object has the same username as another Player object, they are the same Player"""
        if isinstance(other, Lobby):
            return self.name == other.name and self.owner == other.owner
        return False

    def put(self, size, squad_size):
        """
        Inserts a new lobby into the database
        :param size: Size of lobby.
        :param squad_size: Size of squads allowed in lobby.
        :return: None
        """

        item = {
            'pk': self.name,
            'sk': f'OWNER#{self.owner.username}',
            'lsi': f'LOBBY',
            'size': size,
            'squad-size': squad_size,
            'state': LobbyState.NOT_STARTED.value
        }

        self.table.put_item(
            Item=item
        )

        self.size = size
        self.squad_size = squad_size

    def get(self):
        """
        Gets basic lobby information from the database.
        :return: None
        """
        response = self.table.get_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}',
            }
        )
        lobby = response.get('Item')

        if not lobby:
            raise LobbyDoesNotExistException("Lobby with name {} does not exist".format(self.name))

        self.owner = game_master.GameMaster(lobby['sk'].split('#')[1])
        self.size = lobby.get('size')
        self.squad_size = lobby.get('squad-size')
        self.state = LobbyState(lobby.get('state'))

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
        Delete a lobby and all squads in the lobby from the system
        :return: None
        """
        if not self.exists():
            raise LobbyDoesNotExistException

        for squad in self.squads:
            self.remove_squad(squad)

        # delete lobby from database
        self.table.delete_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}'
            }
        )

    def update(self, size: int = None, squad_size: int = None):
        """
        Update lobby information
        :param size: New size of lobby
        :param squad_size: New squad size allowed in lobby
        """

        attributes_to_update = dict()
        if size:
            attributes_to_update['size'] = dict(Value=size)
        if squad_size:
            attributes_to_update['squad-size'] = dict(Value=squad_size)

        self.table.update_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}'
            },
            AttributeUpdates=attributes_to_update)

        self.size = size
        self.squad_size = squad_size

    def start(self):
        """
        Starts a game lobby by setting state attribute to 'started' in database. A game in "finished" state can
        be started again.
        :return: None
        """
        # Check if game has started already or not
        if self.state is None:
            self.get()

        if self.state == LobbyState.STARTED:
            raise LobbyAlreadyStartedException("Game has already been started")

        # Ensure game has at least 2 squads in it
        if len(self.squads) < 2:
            raise NotEnoughSquadsException("Lobby does not have enough squads to start")

        self.table.update_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}'
            },
            AttributeUpdates={'state': dict(Value=LobbyState.STARTED.value)}
        )

        self.state = LobbyState.STARTED

    def end(self):
        """
        End a game lobby by setting state attribute in database to 'finished'
        :return: None
        """
        # Check if game has started already or not
        if self.state is None:
            self.get()

        if self.state == LobbyState.FINISHED:
            raise LobbyAlreadyStartedException("Game has already finished")

        self.table.update_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}'
            },
            AttributeUpdates={'state': dict(Value=LobbyState.FINISHED.value)}
        )

        self.state = LobbyState.FINISHED

    def add_squad(self, squad):
        """
        Adds a squad to the lobby instance. DynamoDB will not allow duplicates so no need to run self.get_squads().
        :param squad: Squad object of squad to add to the lobby
        """

        # check if squad with same name is already in lobby
        if squad in self.squads:
            raise SquadAlreadyInLobbyException(f"Squad with name {squad.name} is already in lobby {self.name}")

        # if squad is not too large for the lobby
        if len(squad.members) > self.squad_size:
            raise SquadTooBigException(f"Squad with name {self.name} is too large for the lobby")

        # if lobby is already full
        if len(self.squads) == self.size:
            raise LobbyFullException(f"Lobby with name {self.name} is full")

        # make sure players in the squad aren't already in the lobby but in another squad
        for squad_member in squad.members:
            if self.player_in_lobby(squad_member):
                raise PlayerAlreadyInLobbyException(f"Player with username {squad_member.username} is already in the "
                                                    f"lobby in squad {squad.name}")

        # squad is not in lobby so we can add them in, and create attributes for each member
        item = {
                'pk': 'LOBBY',
                'sk': f'SQUAD#{squad.name}'
            }

        # add attribute for each player in squad
        for member in squad.members:
            item[f'PLAYER#{member.username}'] = PlayerState.ALIVE.value

        self.table.put_item(
            Item=item
        )

        # set squad as in lobby
        squad.set_in_lobby(self)

        self.squads.append(squad)

    def remove_squad(self, squad):
        """
        Removes a squad from the lobby instance. No need to run self.get_squads() before calling this to ensure
        deletion as DynamoDB will silently do nothing if squad has already been removed.
        :param squad: Squad to remove
        """

        if squad not in self.squads:
            raise SquadNotInLobbyException(f"Squad with name {squad.name} is not in lobby {self.name}")

        self.table.delete_item(
            Key={
                'pk': 'LOBBY',
                'sk': f'SQUAD#{squad.name}'
            })

        self.squads.remove(squad)

        squad.set_no_lobby()

    def get_squads(self):
        """
        Get all squads in the lobby and save to object
        """
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq('LOBBY'))

        squads = []
        for item in response['Items']:
            # get squad and fill with information
            squad = squad_model.Squad(item['sk'].split('#')[1])
            squad.get()
            squad.get_members()
            squads.append(squad)

        self.squads = squads

    def player_in_lobby(self, player):
        """
        Checks if a specific player is already in the game lobby or not
        :param: player: player object
        :return: True if player is in the game lobby, otherwise False
        """
        for squad in self.squads:
            if player in squad.members:
                return True
        return False

    def get_players_and_states(self):
        """
        Get all players in the lobby, which squad they're in and their game state
        :return:
        """
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq('LOBBY'))

        lobby = response.get('Items')

        players_in_lobby = []
        for squad in lobby:
            players_in_squad = [k.split('#')[1] for k, v in squad.items() if 'PLAYER#' in k]
            for player in players_in_squad:
                players_in_lobby.append({
                    'squad_name': squad['sk'].split('#')[1],
                    'name': player,
                    'state': squad[f'PLAYER#{player}']
                })

        return players_in_lobby
