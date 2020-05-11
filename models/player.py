from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import UserDoesNotExistException, UserDoesNotOwnSquadException, SquadAlreadyExistsException
from models.squad import SquadModel
from models.user import User


class PlayerModel(User):
    """
    A Player type of User.
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.table = DynamoDbConnector.get_table()

    def get_player(self):
        """
        Gets a player from the database
        :return: Information about the player
        """
        response = self.table.get_item(
            Key={
                'pk': self.username,
                'sk': 'player-info'
            },
        )
        player = response.get('Item')

        if not player:
            raise UserDoesNotExistException("Player with username {} does not exist".format(self.username))

        return player

    def exists(self):
        """
        If player with given username exists, returns True
        :return: True if player exists, else False
        """
        try:
            self.get_player()
            return True
        except UserDoesNotExistException:
            return False

    def put_player(self):
        """
        Inserts a new player into the database
        :return: None
        """

        _ = self.table.put_item(
            Item={
                'pk': self.username,
                'sk': 'player-info',
            }
        )

    def delete_player(self, access_token):
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
                'sk': 'player-info'
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
        squad = SquadModel(squad_name)
        if squad.exists():
            raise SquadAlreadyExistsException("Squad with name {} already exists".format(squad_name))
        squad.put(owner=self.username)

    def delete_squad(self, squad_name):
        """
        Deletes a squad owned by Player from the database
        :param squad_name: name of squad to delete
        :return: None
        """
        # make sure Player owns the squad
        squad = SquadModel(squad_name)
        squad.get()

        # cannot delete a squad that Player does not own
        if squad.owner != self.username:
            raise UserDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        squad.delete()

    def add_member_to_squad(self, squad_name, new_member):
        """
        Invite a user to join your squad. For now a user is just added instead of invited
        :param squad_name: name of squad to invite user to
        :param new_member: username of User to add to squad
        :return: ID of invitation
        """
        squad = SquadModel(squad_name)
        squad.get()

        # cannot invite users to squads Player does not own
        if squad.owner != self.username:
            raise UserDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        # make sure user exists before adding to squad
        new_member = PlayerModel(new_member)
        if not new_member.exists():
            raise UserDoesNotExistException("User with username {} does not exist".format(new_member.username))

        squad.add_member(new_member)

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
            squads.append(SquadModel(item['sk'], owner=self.username))

        return squads

    def get_non_owner_squads(self):
        """
        Get squads that Player is in but does not own
        :return: list of squads Player is in but does not own
        """
        response = self.table.query(
            IndexName='lsi',  # lsi of squad item will be username of the owner of the squad
            KeyConditionExpression=Key('pk').eq('squad-member') & Key('lsi').eq(self.username)
        )

        squads = []
        for item in response['Items']:
            squads.append({
                'name': item['sk']
            })

        return squads
