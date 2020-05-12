from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import UserDoesNotExistException, UserDoesNotOwnSquadException, SquadAlreadyExistsException, \
    UserOwnsSquadException
from models.squad import Squad
from models.user import User


class Player(User):
    """
    A Player type of User.
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.table = DynamoDbConnector.get_table()

    def __eq__(self, other):
        """If a Player object has the same username as another Player object, they are the same Player"""
        if isinstance(other, Player):
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
        player = response.get('Item')

        if not player:
            raise UserDoesNotExistException("Player with username {} does not exist".format(self.username))

        return {
            'username': player['pk']
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
        # delete any squads the player owns and cleanup
        squads_to_delete = self.get_owned_squads()
        for squad in squads_to_delete:
            squad.delete()
        # delete player from database
        self.table.delete_item(
            Key={
                'pk': self.username,
                'sk': 'USER'
            },
        )
        # delete user from Cognito service
        self.cognito_client.delete_user(AccessToken=access_token)

    def create_squad(self, squad_name):
        """
        Creates a new squad owned by Player
        :param squad_name: name of squad to create
        :return: None
        """
        squad = Squad(squad_name)
        if squad.exists():
            raise SquadAlreadyExistsException("Squad with name {} already exists".format(squad_name))
        squad.put(owner=self.username)
        squad.add_member(self)
        return squad

    def delete_squad(self, squad):
        """
        Deletes a squad owned by Player from the database
        :param squad: Squad object of squad to delete
        :return: None
        """
        # make sure Player owns the squad and get latest members
        squad.get()
        squad.get_members()

        # cannot delete a squad that Player does not own
        if squad.owner.username != self.username:
            raise UserDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        squad.delete()

    def add_member_to_squad(self, squad, new_member):
        """
        Invite a user to join your squad. For now a user is just added instead of invited
        :param squad: Squad object of squad to invite user to
        :param new_member: Player object of user to add to squad
        :return: ID of invitation
        """
        squad.get()

        # cannot invite users to squads Player does not own
        if squad.owner.username != self.username:
            raise UserDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        # make sure user exists before adding to squad
        if not new_member.exists():
            raise UserDoesNotExistException("User with username {} does not exist".format(new_member.username))

        squad.add_member(new_member)

    def remove_member_from_squad(self, squad, member_to_remove):
        """
        Remove a member from a squad owned by Player
        :param squad: squad to remove member from
        :param member_to_remove: member to be removed
        :return: None
        """
        squad.get()

        # cannot remove members from squads Player does not own
        if squad.owner.username != self.username:
            raise UserDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        if member_to_remove == squad.owner:
            raise UserOwnsSquadException("Owner cannot be removed from the squad")

        squad.delete_member(member_to_remove)

    def get_owned_squads(self):
        """
        Retrieves all squads owned by Player
        :return: List of squads owned by Player
        """
        response = self.table.query(
            IndexName='lsi',  # lsi of squad item will be username of the owner of the squad
            KeyConditionExpression=Key('pk').eq('squad') & Key('lsi').eq(f'SQUADOWNER#{self.username}')
        )

        squads = []
        for item in response['Items']:
            # get squad and fill with information
            squad = Squad(item['sk'].split('#')[1])
            squad.get()
            squad.get_members()
            squads.append(squad)

        return squads

    def get_not_owned_squads(self):
        """
        Get squads that Player is in but does not own
        :return: list of squads Player is in but does not own
        """

        response = self.table.query(
            IndexName='lsi-2',  # lsi of squad item will be username of the owner of the squad
            KeyConditionExpression=Key('pk').eq('squad-member') & Key('lsi-2').eq(self.username)
        )

        squads = []
        for item in response['Items']:
            # get squad and fill with information
            squad = Squad(item['lsi'].split('#')[1])
            squad.get()
            squad.get_members()
            squads.append(squad)

        return squads
