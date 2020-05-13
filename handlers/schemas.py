from marshmallow import Schema, fields


class UserSchema(Schema):
    username = fields.String(required=True)


class SquadSchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    members = fields.Nested(UserSchema, many=True)


class SquadListSchema(Schema):
    squads = fields.Nested(SquadSchema, many=True)


class LobbySchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    state = fields.String(required=True)
    size = fields.Integer(required=True)
    squad_size = fields.Integer(required=True)
    squads = fields.Nested(SquadSchema, many=True)


class LobbyPlayerState(Schema):
    name = fields.String(required=True)
    squad_name = fields.String(required=True)
    state = fields.String(required=True)


class LobbyPlayerListSchema(Schema):
    players = fields.Nested(LobbyPlayerState, many=True)
