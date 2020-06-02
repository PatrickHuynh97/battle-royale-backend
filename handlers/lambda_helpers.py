import json
from functools import wraps
from json import JSONDecodeError

from marshmallow import ValidationError

from exceptions import ApiException


def endpoint(response_schema=None, request_schema=None):
    """
    Adds a new endpoint to the API
    :param response_schema: A schema specifying the output of the function. If None, no validation is performed
    :param request_schema: A schema specifying the required structure of the request.
    """

    def lambda_wrapper(func):
        @wraps(func)
        def wrapper(event, context):

            set_calling_user(event)

            preload_body(event, request_schema)

            try:
                result = func(event, context)
                # if API exception was raised, catch and format for Lambda
            except ApiException as e:
                return handle_api_exception(e)
            # if an error occurred in the code, make a 500 response
            except Exception as e:
                raise e

            to_return = {
                'statusCode': 200,
                'body': postload_body(result, response_schema)
            }
            return to_return
        return wrapper
    return lambda_wrapper


def postload_body(body, response_schema=None):
    # dump the body to a JSON string
    if response_schema:
        try:
            if isinstance(body, dict):
                return response_schema().dumps(body)
            elif isinstance(body, list):
                return response_schema().dumps(body, many=True)
        except ValidationError as e:
            raise ApiException("Response does not match specific response_schema", extras=e)
    else:
        try:
            return json.dumps(body)
        except Exception as e:
            raise ApiException("Response is not a valid JSON", extras=e)


def set_calling_user(event):
    # if endpoint uses authorizer, get calling user
    authorizer = event['requestContext'].get('authorizer')
    if authorizer:
        event['calling_user'] = authorizer['claims']['cognito:username']


def preload_body(event, schema):
    if event['body']:
        # if a schema is given, try to load the request with that
        if schema:
            event['body'] = schema().loads(event['body'])
        # otherwise try to load body into JSON. If it fails, do nothing.
        else:
            try:
                event['body'] = json.loads(event['body'])
            except JSONDecodeError:
                pass


def handle_api_exception(exception):
    """
    Handles an exception which was caught and raised
    :param exception: exception to handle
    :return: formatted exception for Lambda to present to frontend
    """
    return {
        'statusCode': exception.error_code,
        'body': json.dumps(exception.message_dict)
    }
