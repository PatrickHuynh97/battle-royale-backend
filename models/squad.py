from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import SquadDoesNotExistException, SquadAlreadyExistsException, UserAlreadyMemberException
from models import player


class Squad:
    """
    A Squad consisting of X members. Squad name's are unique.
    """

    def __init__(self, name: str, owner: str = None):
        self.name = name  # name of squad
        self.owner = owner  # owner of squad
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
        Inserts a new player into the database
        :return: None
        """
        if self.exists():
            raise SquadAlreadyExistsException

        _ = self.table.put_item(
            Item={
                'pk': 'squad',
                'sk': f'SQUADNAME#{self.name}',
                'lsi': f'SQUADOWNER#{owner}',
            }
        )

    def delete(self):
        """
        Delete a squad and all squad-members from database
        :return: None
        """
        # remove squad members
        for member in self.members:
            self.delete_member(member)

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

        return {
            'name': self.name,
            'owner': self.owner
        }

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

        for member in self.members:
            if member.username == new_member.username:
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

    def delete_member(self, member_to_delete):
        """
        Delete a user from the squad
        :param member_to_delete: Username of player to delete
        :return:
        """
        res = self.table.delete_item(
            Key={
                'pk': 'squad-member',
                'sk': f'SQUAD#{self.name}#MEMBER#{member_to_delete.username}',
            }
        )
        self.members.remove(member_to_delete)
