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
    error_code = 400


class SignOutException(AuthorizationException):
    error_code = 400


class UserDoesNotExistException(AuthorizationException):
    error_code = 400


class UserAlreadyExistsException(AuthorizationException):
    tag = __qualname__
    error_code = 400


# exceptions for players
class PlayerException(ApiException):
    tag = "PlayerException"
    error_code = 500


class UserCannotBeDeletedException(PlayerException):
    tag = __qualname__
    error_code = 400


class UserDoesNotOwnSquadException(PlayerException):
    tag = __qualname__
    error_code = 400


class UserOwnsSquadException(PlayerException):
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
