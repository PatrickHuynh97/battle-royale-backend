from marshmallow import Schema, fields


class UserSchema(Schema):
    username = fields.String(required=True)


class SquadSchema(Schema):
    name = fields.String(required=True)
    owner = fields.String(required=True)
    members = fields.Nested(UserSchema, many=True)


class SquadListSchema(Schema):
    squads = fields.Nested(SquadSchema, many=True)
