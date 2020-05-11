import json
from functools import wraps

from exceptions import ApiException


def endpoint(func):
    @wraps(func)
    def wrapper(event, context):
        """
        Wrapper wraps all endpoints and handles pre/post-processing
        :param event: lambda event
        :param context: lambda context
        :return: post-processed result
        """
        set_calling_user(event)

        try:
            res = func(event, context)
            return {
                'statusCode': 200,
                'body': res
            }
        # if API exception was raised, catch and format for Lambda
        except ApiException as e:
            return handle_api_exception(e)
        # if an error occurred in the code, make a 500 response
        except Exception as e:
            raise e

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

    return wrapper
