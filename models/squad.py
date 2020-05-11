from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import SquadDoesNotExistException, SquadAlreadyExistsException, UserAlreadyMemberException


class SquadModel:
    """
    A Squad consisting of X members. Squad name's are unique.
    """

    def __init__(self, name: str, owner: str = None):
        self.name = name  # name of squad
        self.owner = owner  # owner of squad
        self.members = None  # list of members in squad
        self.table = DynamoDbConnector.get_table()

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
        client, table_name = DynamoDbConnector.get_client()
        # delete squad-members from database
        self.table
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

        self.owner = squad['lsi'].split('#')[1]  # owner of squad is the LSI value

        return {
            'name': self.name,
            'owner': self.owner
        }

    def add_member(self, new_member):
        """
        Add a new user to the squad
        :param new_member: PlayerModel object for player to add to squad
        :return: None
        """
        members = self.get_members()

        if new_member.username in members:
            raise UserAlreadyMemberException("User {} is already in squad {}".format(new_member, self.name))

        self.table.put_item(
            Item={
                'pk': 'squad-member',
                'sk': f'SQUADMEMBER#{new_member.username}',
                'lsi': f'SQUADNAME#{self.name}'
            }
        )

    def get_members(self):
        """
        Get all members belonging to the squad
        :return: Members belonging to the squad
        """
        members = []

        response = self.table.query(
            Select='ALL_ATTRIBUTES',
            KeyConditionExpression=Key('pk').eq('squad-member') & Key('lsi').eq(f'SQUADNAME#{self.name}')
        )

        for member in response['Items']:
            members.append(member['sk'].split('#')[1])

        self.members = members

        return members

    def delete_member(self, member_to_delete):
        """
        Delete a user from the squad
        :param member_to_delete: Username of player to delete
        :return:
        """
        # todo
