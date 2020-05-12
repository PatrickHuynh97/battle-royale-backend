import json
from functools import wraps
from exceptions import ApiException


def endpoint(response_schema=None):
    """
    Adds a new endpoint to the API
    :param response_schema: A schema specifying the output of the function. If None, no validation is performed
    """

    def lambda_wrapper(func):
        @wraps(func)
        def wrapper(event, context):
            set_calling_user(event)
            try:
                result = func(event, context)
                # if API exception was raised, catch and format for Lambda
            except ApiException as e:
                return handle_api_exception(e)
            # if an error occurred in the code, make a 500 response
            except Exception as e:
                raise e

            return {
                'statusCode': 200,
                'body': response_schema().dumps(result) if response_schema else result
            }
        return wrapper
    return lambda_wrapper


def set_calling_user(event):
    # if endpoint uses authorizer, get calling user
    authorizer = event['requestContext'].get('authorizer')
    if authorizer:
        event['calling_user'] = authorizer['claims']['cognito:username']


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
