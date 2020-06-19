from marshmallow import Schema, fields, validate


class SquadSchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    members = fields.List(fields.String(), required=True)


class SquadListSchema(Schema):
    squads = fields.Nested(SquadSchema, many=True, allow_none=True)


class CoordinateSchema(Schema):
    longitude = fields.Float()
    latitude = fields.Float()


class CircleSchema(Schema):
    centre = fields.Nested(CoordinateSchema)
    radius = fields.Float()


class LobbySchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    state = fields.String(required=True)
    size = fields.Integer(required=True)
    squad_size = fields.Integer(required=True)
    current_circle = fields.Nested(CircleSchema, allow_none=True, required=False)
    next_circle = fields.Nested(CircleSchema, allow_none=True, required=False)
    final_circle = fields.Nested(CircleSchema, allow_none=True, required=False)
    game_zone_coordinates = fields.Nested(CoordinateSchema, allow_none=True, many=True)
    squads = fields.Nested(SquadSchema, many=True)


class UpdateLobbySchema(Schema):
    size = fields.Integer(required=False)
    squad_size = fields.Integer(required=False)
    final_circle = fields.Nested(CircleSchema, allow_none=True, required=False)
    game_zone_coordinates = fields.Nested(CoordinateSchema, required=False, many=True)


class LobbyPlayerState(Schema):
    name = fields.String(required=True)
    squad_name = fields.String(required=True)
    state = fields.String(required=True)


class LobbyPlayerListSchema(Schema):
    players = fields.Nested(LobbyPlayerState, many=True)


class CreateLobbyRequestSchema(Schema):
    name = fields.String(required=True)
    lobby_size = fields.Integer(required=True)
    squad_size = fields.Integer(required=True)
