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


class AuthorizationException(ApiException):
    tag = "UserException"
    error_code = 500


class SignUpException(AuthorizationException):
    error_code = 400


class SignInException(AuthorizationException):
    error_code = 400


class SignOutException(AuthorizationException):
    error_code = 400


class UserDoesNotExistException(AuthorizationException):
    error_code = 400
    pass


class UserAlreadyExistsException(AuthorizationException):
    error_code = 400
    pass


# exceptions for players
class PlayerException(ApiException):
    tag = "PlayerException"
    error_code = 500


class UserCannotBeDeletedException(PlayerException):
    error_code = 400
    pass


class UserDoesNotOwnSquadException(PlayerException):
    error_code = 400
    pass


class SquadAlreadyExistsException(PlayerException):
    error_code = 400
    pass


# exceptions for Squads
class SquadException(ApiException):
    tag = "SquadException"
    error_code = 500


class SquadDoesNotExistException(SquadException):
    error_code = 400
    pass


class SquadAlreadyExistsException(SquadException):
    error_code = 400
    pass


class UserAlreadyMemberException(SquadException):
    error_code = 400
    pass
