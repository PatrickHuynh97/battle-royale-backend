# exceptions for generic Users
import json


class ApiException(Exception):
    tag = "Exception"
    error_code = 500

    def __init__(self, message=None, extras=None):
        tag = self.__class__.tag

        message_dict = {
            "type": tag,
            "message": message,
        }

        if extras is not None:
            message_dict.update(extras)

        self.message_dict = message_dict

        super(ApiException, self).__init__(json.dumps(message_dict))


# 500
class InternalException(ApiException):
    error_code = 500
    tag = "InternalError"


class AuthorizationException(ApiException):
    tag = "AuthorizationException"
    error_code = 500


class SignUpException(AuthorizationException):
    tag = __qualname__
    error_code = 400


class SignInException(AuthorizationException):
    tag = __qualname__
    error_code = 400


class SignOutException(AuthorizationException):
    tag = __qualname__
    error_code = 400


class UserDoesNotExistException(AuthorizationException):
    tag = __qualname__
    error_code = 404


class UserAlreadyExistsException(AuthorizationException):
    tag = __qualname__
    error_code = 400


class InvalidUsernameException(AuthorizationException):
    tag = __qualname__
    error_code = 400


class PasswordLengthException(AuthorizationException):
    tag = __qualname__
    error_code = 400


# exceptions for players
class PlayerException(ApiException):
    tag = "PlayerException"
    error_code = 500


class PlayerCannotBeDeletedException(PlayerException):
    tag = __qualname__
    error_code = 400


class PlayerDoesNotOwnSquadException(PlayerException):
    tag = __qualname__
    error_code = 400


class PlayerOwnsSquadException(PlayerException):
    tag = __qualname__
    error_code = 400


class PlayerNotInLobbyException(PlayerException):
    tag = __qualname__
    error_code = 400


# exceptions for Squads
class SquadException(ApiException):
    tag = "SquadException"
    error_code = 500


class SquadAlreadyExistsException(SquadException):
    tag = __qualname__
    error_code = 400


class SquadDoesNotExistException(SquadException):
    tag = __qualname__
    error_code = 400


class UserAlreadyMemberException(SquadException):
    tag = __qualname__
    error_code = 400


class UserCouldNotBeRemovedException(SquadException):
    tag = __qualname__
    error_code = 400


# exceptions for GameMasters
class GameMasterException(ApiException):
    tag = "GameMasterException"
    error_code = 500


class GameMasterAlreadyInLobbyException(GameMasterException):
    tag = __qualname__
    error_code = 400


class GameMasterNotInLobbyException(GameMasterException):
    tag = __qualname__
    error_code = 400


# exceptions for Lobbys
class LobbyException(ApiException):
    tag = "LobbyException"
    error_code = 500


class LobbyDoesNotExistException(LobbyException):
    tag = __qualname__
    error_code = 400


class SquadInLobbyException(LobbyException):
    tag = __qualname__
    error_code = 400


class SquadNotInLobbyException(LobbyException):
    tag = __qualname__
    error_code = 400


class LobbySettingsNotGivenException(LobbyException):
    tag = __qualname__
    error_code = 400


class SquadTooBigException(LobbyException):
    tag = __qualname__
    error_code = 400


class LobbyFullException(LobbyException):
    tag = __qualname__
    error_code = 400


class LobbyAlreadyStartedException(LobbyException):
    tag = __qualname__
    error_code = 400


class LobbyNotStartedException(LobbyException):
    tag = __qualname__
    error_code = 400


class NotEnoughSquadsException(LobbyException):
    tag = __qualname__
    error_code = 400


class PlayerAlreadyInLobbyException(LobbyException):
    tag = __qualname__
    error_code = 400


class WebSocketException(ApiException):
    pass


class LiveDataConnectionException(WebSocketException):
    pass


class WebSocketDisconnectedException(WebSocketException):
    pass


# exceptions for Tests
class TestException(ApiException):
    tag = "TestException"
    error_code = 500


class SetupError(TestException):
    tag = __qualname__
    error_code = 400
