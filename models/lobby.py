from datetime import datetime
from boto3.dynamodb.conditions import Key
from db.dynamodb_connector import DynamoDbConnector
from exceptions import LobbyDoesNotExistException, SquadInLobbyException, SquadNotInLobbyException, \
    SquadTooBigException, LobbyFullException, LobbyAlreadyStartedException, NotEnoughSquadsException, \
    PlayerAlreadyInLobbyException, LobbyNotStartedException, PlayerNotInLobbyException
from models import game_master
from enums import LobbyState, PlayerState
from models import squad as squad_model
from models import map
from websockets import connection_manager
import pytz


class Lobby:
    """
    Lobby objects stores information about a game
    """

    def __init__(self, name, owner):
        self.name = name
        self.owner = owner
        self.unique_id = None
        self.size = None
        self.squad_size = None
        self.state = None
        self.game_zone = None
        self.started_time = None
        self.squads = []
        self.table = DynamoDbConnector.get_table()

    def __eq__(self, other):
        """If a Player object has the same username as another Player object, they are the same Player"""
        if isinstance(other, Lobby):
            return self.name == other.name and self.owner == other.owner
        return False

    @staticmethod
    def generate_unique_id():
        """
        Generate a random alphanumeric id for the game lobby
        :return:
        """
        import random
        import string

        letters_and_digits = string.ascii_letters + string.digits
        return ''.join((random.choice(letters_and_digits) for i in range(12)))

    def put(self, size, squad_size):
        """
        Inserts a new lobby into the database
        :param size: Size of lobby.
        :param squad_size: Size of squads allowed in lobby.
        :return: None
        """
        unique_id = self.generate_unique_id()
        item = {
            'pk': self.name,
            'sk': f'OWNER#{self.owner.username}',
            'lsi': f'LOBBY',
            'lsi-2': unique_id,
            'size': size,
            'squad-size': squad_size,
            'state': LobbyState.NOT_STARTED.value
        }

        self.table.put_item(
            Item=item
        )
        self.state = LobbyState.NOT_STARTED
        self.unique_id = unique_id
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
        self.unique_id = lobby.get('lsi-2')
        self.size = int(lobby.get('size'))
        self.squad_size = int(lobby.get('squad-size'))
        self.state = LobbyState(lobby.get('state'))
        current_circle = map.Circle(lobby.get('current-circle')) if lobby.get('current-circle') else None
        next_circle = map.Circle(lobby.get('next-circle')) if lobby.get('next-circle') else None
        final_circle = map.Circle(lobby.get('final-circle')) if lobby.get('final-circle') else None
        self.game_zone = map.GameZone(lobby.get('game-zone-coordinates'),
                                      current_circle=current_circle,
                                      next_circle=next_circle,
                                      final_circle=final_circle)
        self.started_time = datetime.strptime(lobby.get('started-time'), "%Y-%m-%dT%H:%M:%S.%f%z") \
            if lobby.get('started-time') else None

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
        Delete a lobby and removes all squads in the lobby
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

    def update(self,
               size: int = None,
               squad_size: int = None,
               game_zone_coordinates: list = None,
               current_circle: dict = None,
               next_circle: dict = None,
               final_circle: dict = None):
        """
        Update lobby information
        :param size: New size of lobby
        :param squad_size: New squad size allowed in lobby
        :param game_zone_coordinates: list containing coordinates which make up the entire game zone
        :param current_circle: dict containing coordinates and radius of the current circle
        :param next_circle: dict containing coordinates and radius of the next circle
        :param final_circle: position of the final circle. If defined before game starts, each circle will be
        generated to converge towards this final position. Otherwise, circles will be completely random.
        """

        attributes_to_update = dict()
        if size:
            attributes_to_update['size'] = dict(Value=size)
            self.size = size
        if squad_size:
            attributes_to_update['squad-size'] = dict(Value=squad_size)
            self.squad_size = squad_size
        if current_circle:
            if isinstance(current_circle, map.Circle):
                attributes_to_update['current-circle'] = dict(Value=current_circle.to_dict())
            else:
                attributes_to_update['current-circle'] = dict(Value=map.Circle(current_circle).to_dict())
                current_circle = map.Circle(current_circle)
        if next_circle:
            if isinstance(next_circle, map.Circle):
                attributes_to_update['next-circle'] = dict(Value=next_circle.to_dict())
            else:
                attributes_to_update['next-circle'] = dict(Value=map.Circle(next_circle).to_dict())
                next_circle = map.Circle(next_circle)
        if final_circle:
            if isinstance(final_circle, map.Circle):
                attributes_to_update['final-circle'] = dict(Value=final_circle.to_dict())
            else:
                attributes_to_update['final-circle'] = dict(Value=map.Circle(final_circle).to_dict())
                final_circle = map.Circle(final_circle)
        if game_zone_coordinates:
            attributes_to_update['game-zone-coordinates'] = dict(
                Value=map.GameZone(game_zone_coordinates).dump_game_zone_coordinates())
            self.game_zone = map.GameZone(game_zone_coordinates,
                                          current_circle=current_circle,
                                          next_circle=next_circle,
                                          final_circle=final_circle)
        if attributes_to_update:
            self.table.update_item(
                Key={
                    'pk': self.name,
                    'sk': f'OWNER#{self.owner.username}'
                },
                AttributeUpdates=attributes_to_update)

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

        self.started_time = datetime.now(tz=pytz.utc)
        # set game as started
        self.table.update_item(
            Key={
                'pk': self.name,
                'sk': f'OWNER#{self.owner.username}'
            },
            AttributeUpdates={'state': dict(Value=LobbyState.STARTED.value),
                              'started-time': dict(Value=self.started_time.isoformat())}
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
            raise LobbyNotStartedException("Game has not been started")

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
            raise SquadInLobbyException(f"Squad with name {squad.name} is already in lobby {self.name}")

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
        :return: Returns player's squad if player is in the game lobby, otherwise False
        """
        for squad in self.squads:
            if player in squad.members:
                return squad
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

    def get_player(self, player):
        """
        Get a specific player from the game lobby
        :param: player: Player to get from the game lobby
        :return: Player object
        """
        players_in_game = self.get_players_and_states()
        for _player in players_in_game:
            if _player['name'] == player.username:
                return _player

        raise PlayerNotInLobbyException(f"User {player.username} could not be found in the lobby")

    def set_player_dead(self, player):
        """
        Set a player as dead in the game lobby. Assumes lobby.get() and lobby.get_squads() has been called
        :param player: Player to set as dead
        :return: None
        """
        if self.state != LobbyState.STARTED:
            raise LobbyNotStartedException("Lobby has not been started yet")

        # assert that player is in the lobby
        squad = self.player_in_lobby(player)

        # set the player as dead. If they are already dead, this statement has no effect
        self.table.update_item(
            Key={
                'pk': 'LOBBY',
                'sk': f'SQUAD#{squad.name}'
            },
            AttributeUpdates={f'PLAYER#{player.username}': dict(Value=PlayerState.DEAD.value)})

        # notify the game master that Player is dead through game session
        connection_manager.ConnectionManager().push_player_dead(player)

    def set_player_alive(self, player):
        """
        Set a player as alive in the game lobby. Assumes lobby.get() and lobby.get_squads() has been called
        :param player: Player to set as alive
        :return: None
        """
        if self.state != LobbyState.STARTED:
            raise LobbyNotStartedException("Lobby has not been started yet")

        # assert that player is in the lobby
        squad = self.player_in_lobby(player)

        # set the player as alive. If they are already alive, this statement has no effect
        self.table.update_item(
            Key={
                'pk': 'LOBBY',
                'sk': f'SQUAD#{squad.name}'
            },
            AttributeUpdates={f'PLAYER#{player.username}': dict(Value=PlayerState.ALIVE.value)})

    def generate_first_circle(self):
        """
        Called when the first circle is being generated
        :return: None
        """
        # generate the next circle
        self.game_zone.create_next_circle()
        self.update(next_circle=self.game_zone.next_circle)

    def close_current_circle(self):
        """
        Facilitates the closing of the current circle (if it exist) to become the next_circle. This is run on a lambda
        that has a long timeout set and runs continuously until the outer circle has become the inner circle. Once
        the circle has finished closing, the next circle will be generated automatically, and a CircleQueue SQS
        event queued to close the next circle when necessary
        :return: None
        """
        self.get()
        self.game_zone.close_to_next_circle(self)

        # once circle has finished closing, current_circle becomes next_circle, and new next_circle is created
        self.game_zone.create_next_circle()
        self.update(current_circle=self.game_zone.current_circle,
                    next_circle=self.game_zone.next_circle)
