from marshmallow import Schema, fields


class UserSchema(Schema):
    username = fields.String(required=True)


class SquadSchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    members = fields.Nested(UserSchema, many=True)


class SquadListSchema(Schema):
    squads = fields.Nested(SquadSchema, many=True)


class CoordinateSchema(Schema):
    x = fields.Float()
    y = fields.Float()


class GameZoneCoordinatesSchema(Schema):
    c1 = fields.Nested(CoordinateSchema)
    c2 = fields.Nested(CoordinateSchema)
    c3 = fields.Nested(CoordinateSchema)
    c4 = fields.Nested(CoordinateSchema)


class LobbySchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    state = fields.String(required=True)
    size = fields.Integer(required=True)
    squad_size = fields.Integer(required=True)
    game_zone_coordinates = fields.Nested(GameZoneCoordinatesSchema, allow_none=True)
    squads = fields.Nested(SquadSchema, many=True)


class LobbyPlayerState(Schema):
    name = fields.String(required=True)
    squad_name = fields.String(required=True)
    state = fields.String(required=True)


class LobbyPlayerListSchema(Schema):
    players = fields.Nested(LobbyPlayerState, many=True)
