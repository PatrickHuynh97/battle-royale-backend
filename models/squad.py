from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import SquadDoesNotExistException, SquadAlreadyExistsException, UserAlreadyMemberException, \
    UserCouldNotBeRemovedException
from models import player
from models import lobby as lobby_model


class Squad:
    """
    A Squad consisting of X members. Squad name's are unique.
    """

    def __init__(self, name: str, owner: str = None):
        self.name = name  # name of squad
        self.owner = owner  # owner of squad
        self.lobby_name = None  # will have a value if squad is in a lobby
        self.lobby_owner = None  # will have a value if squad is in a lobby
        self.members = []  # list of members in squad
        self.table = DynamoDbConnector.get_table()

    def __eq__(self, other):
        """
        If a Player object has the same username as another Player object, they are the same Player
        """
        if isinstance(other, Squad):
            return self.name == other.name
        return False

    def put(self, owner):
        """
        Inserts a new Squad into the database and adds the owner to it
        :return: None
        """
        if self.exists():
            raise SquadAlreadyExistsException

        _ = self.table.put_item(
            Item={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}',
                'lsi': f'SQUADOWNER#{owner.username}',
                'lobby-name': None
            }
        )
        self.owner = owner
        self.add_member(owner)

    def delete(self):
        """
        Delete a squad and all squad-members from database
        :return: None
        """
        # remove squad members
        for member in self.members:
            self.remove_member(member)

        # delete squad from database
        self.table.delete_item(
            Key={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}'
            },
        )

    def exists(self):
        """
        If player with given username exists, returns True
        :return: True if player exists, else False
        """
        try:
            self.get()
            return True
        except SquadDoesNotExistException:
            return False

    def get(self):
        """
        Gets a squad from the database
        :return: Information about the squad
        """
        response = self.table.get_item(
            Key={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}'
            },
        )
        squad = response.get('Item')

        if not squad:
            raise SquadDoesNotExistException("Squad with name {} does not exist".format(self.name))

        self.owner = player.Player(squad['lsi'].split('#')[1])  # owner of squad is the LSI value
        self.lobby_name = squad.get('lobby-name')
        self.lobby_owner = squad.get('lobby-owner')

    def get_members(self):
        """
        Get all members belonging to the squad and save to object
        :return: Members belonging to the squad
        """

        response = self.table.query(
            IndexName='lsi',
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('squad-member') & Key('lsi').eq(f'SQUADNAME#{self.name}')
        )

        for member in response['Items']:
            squad_member = player.Player(member['sk'].split('#')[3])
            if squad_member not in self.members:
                self.members.append(squad_member)

    def add_member(self, new_member):
        """
        Add a new user to the squad
        :param new_member: PlayerModel object for player to add to squad
        :return: None
        """
        self.get_members()

        if new_member in self.members:
            raise UserAlreadyMemberException("User {} is already in squad {}".format(new_member, self.name))

        # add member in database
        self.table.put_item(
            Item={
                'pk': 'squad-member',
                'sk': f'SQUAD#{self.name}#MEMBER#{new_member.username}',
                'lsi': f'SQUADNAME#{self.name}',
                'lsi-2': new_member.username
            }
        )

        self.members.append(new_member)

    def remove_member(self, member_to_remove):
        """
        Delete a user from the squad
        :param member_to_remove: Username of player to delete
        :return:
        """
        res = self.table.delete_item(
            Key={
                'pk': 'squad-member',
                'sk': f'SQUAD#{self.name}#MEMBER#{member_to_remove.username}',
            }
        )
        if res['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise UserCouldNotBeRemovedException("Failed to delete player")

    def leave_lobby(self):
        """
        Leave a lobby that a GameMaster has added you to. Requires basic squad information (squad.get())
        :return: None
        """
        lobby = lobby_model.Lobby(self.lobby_name, self.lobby_owner)
        lobby.get_squads()
        lobby.remove_squad(self)
        self.set_no_lobby()

    def set_in_lobby(self, lobby):
        """
        If squad is in a lobby, set flag to show this. Set flag for each player in the squad as well.
        :param lobby: Lobby object of lobby squad is in
        :return: None
        """

        self.table.update_item(
            Key={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}',
            },
            AttributeUpdates={'lobby-name': dict(Value=lobby.name),
                              'lobby-owner': dict(Value=lobby.owner.username)})

        # set each player in squad as in lobby
        for player in self.members:
            player.set_in_lobby(lobby, self)

    def set_no_lobby(self):
        """
        If squad is not a lobby, set lobby-name to None
        """

        self.table.update_item(
            Key={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}',
            },
            AttributeUpdates={'lobby-name': dict(Value=None),
                              'lobby-owner': dict(Value=None)})

        # set each player in squad as in lobby
        for player in self.members:
            player.set_no_lobby()

    def in_lobby(self):
        """
        Returns True if the squad is in a lobby
        :return: True if squad is in a lobby, otherwise False
        """
        self.get()
        if self.lobby_name:
            return True
        else:
            return False
