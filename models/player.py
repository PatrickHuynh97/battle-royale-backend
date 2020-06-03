from boto3.dynamodb.conditions import Key

from db.dynamodb_connector import DynamoDbConnector
from exceptions import UserDoesNotExistException, PlayerDoesNotOwnSquadException, SquadAlreadyExistsException, \
    PlayerOwnsSquadException, PlayerNotInLobbyException, SquadInLobbyException
from models import squad as squad_model
from models import user
from models import lobby as lobby_model
from models import game_master as game_master_model
from enums import PlayerState


class Player(user.User):
    """
    A Player type of User.
    """

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.lobby = None  # only has a value if the player is in the lobby
        self.squad = None  # has the Squad that the player is in a lobby with
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

        self.lobby = lobby_model.Lobby(player.get('lobby-name'),
                                       game_master_model.GameMaster(player.get('lobby-owner')))
        self.squad = squad_model.Squad(player.get('squad'))

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
                'in-game': False,
                'lobby-name': None,
                'lobby-owner': None
            }
        )

    def delete(self, access_token):
        """
        Delete a player from the system
        :param access_token: Access token used to verify the user is who the they say they are
        :return: None
        """
        self.get()
        if self.lobby.name:
            raise SquadInLobbyException("User cannot be deleted whilst in a Lobby")

        # delete any squads the player owns and cleanup
        squads_to_delete = self.get_owned_squads()
        for squad in squads_to_delete:
            squad.delete()

        # leave any squads the player does not own
        squads_to_leave = self.get_not_owned_squads()
        for squad in squads_to_leave:
            squad.remove_member(self)

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
        squad = squad_model.Squad(squad_name)
        if squad.exists():
            raise SquadAlreadyExistsException("Squad with name {} already exists".format(squad_name))
        squad.put(owner=self)
        return squad

    def delete_squad(self, squad):
        """
        Deletes a squad owned by Player from the database
        :param squad: Squad object of squad to delete
        :return: None
        """
        # make sure Player owns the squad and get latest members
        if squad.in_lobby():
            raise SquadInLobbyException("Squad cannot be edited whilst in a Lobby")

        squad.get_members()

        # cannot delete a squad that Player does not own
        if squad.owner.username != self.username:
            raise PlayerDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        squad.delete()

    def add_member_to_squad(self, squad, new_member):
        """
        Invite a user to join your squad. For now a user is just added instead of invited
        :param squad: Squad object of squad to invite user to
        :param new_member: Player object of user to add to squad
        :return: ID of invitation
        """
        if squad.in_lobby():
            raise SquadInLobbyException("Squad cannot be edited whilst in a Lobby")

        # cannot invite users to squads Player does not own
        if squad.owner.username != self.username:
            raise PlayerDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

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
        if squad.in_lobby():
            raise SquadInLobbyException("Squad cannot be edited whilst in a Lobby")

        # cannot remove members from squads Player does not own
        if squad.owner.username != self.username:
            raise PlayerDoesNotOwnSquadException("User does not own squad with name {}".format(squad.name))

        if member_to_remove == squad.owner:
            raise PlayerOwnsSquadException("Owner cannot be removed from the squad")

        squad.remove_member(member_to_remove)

    def leave_squad(self, squad):
        """
        Remove Player from a squad that they do not own
        :param squad: Squad to remove Player from
        :return: None
        """
        squad.get()
        squad.get_members()
        if squad.owner == self:
            raise PlayerOwnsSquadException("User cannot leave a squad they own")

        squad.remove_member(self)

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
            squad = squad_model.Squad(item['sk'].split('#')[1])
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
            # only get squads which calling player does not own
            if item['lsi'].split('#')[3] != self.username:
                # get squad and fill with information
                squad = squad_model.Squad(item['lsi'].split('#')[1])
                squad.get()
                squad.get_members()
                squads.append(squad)

        return squads

    def pull_squad_from_lobby(self, squad):
        """
        Pull as squad owner by Player from a lobby
        :param: squad: Squad to pull from current lobby
        :return: None
        """
        if squad.owner != self:
            raise PlayerDoesNotOwnSquadException(f"User {self.username} is not the owner of squad {squad.name}")

        squad.leave_lobby()

    def set_in_lobby(self, lobby, squad):
        """
        If player is in a squad, that squad is in a game lobby, set flag on player to show this
        :param lobby: Lobby object of lobby player is in which has started
        :param squad: squad object of lobby player is in the lobby with
        :return:
        """

        self.table.update_item(
            Key={
                'pk': self.username,
                'sk': f'USER'
            },
            AttributeUpdates={'lobby-name': dict(Value=lobby.name),
                              'lobby-owner': dict(Value=lobby.owner.username),
                              'squad': dict(Value=squad.name)})

    def set_no_lobby(self):
        """
        If player is in a squad, that squad is in a game lobby, set flag on player to show this
        :param lobby: Lobby object of lobby player is in which has started
        :return:
        """

        self.table.update_item(
            Key={
                'pk': self.username,
                'sk': f'USER'
            },
            AttributeUpdates={'lobby-name': dict(Value=None),
                              'lobby-owner': dict(Value=None),
                              'squad': dict(Value=None)})

    def get_current_lobby(self):
        """
        Get current game lobby if player is in an active game
        :return: Game lobby information
        """
        self.get()
        if self.lobby.name and self.lobby.owner:
            return lobby_model.Lobby(self.lobby.name, game_master_model.GameMaster(self.lobby.owner.username))
        else:
            raise PlayerNotInLobbyException("Player is not currently in a Lobby")

    def get_current_state(self):
        """
        If the Player is in a lobby that has started, get their current state
        :return: Player GameState
        """
        current_lobby = self.get_current_lobby()
        player_state = current_lobby.get_player(self)
        return PlayerState(player_state['state'])

    def dead(self):
        """
        Set player as dead if they are in a lobby that has started
        :return:
        """
        current_lobby = self.get_current_lobby()
        current_lobby.get()  # get basic information about lobby
        current_lobby.get_squads()
        current_lobby.set_player_dead(self)

    def alive(self):
        """
        Set player as alive if they are in a lobby that has started
        :return:
        """
        current_lobby = self.get_current_lobby()
        current_lobby.get()  # get basic information about lobby
        current_lobby.get_squads()
        current_lobby.set_player_alive(self)
