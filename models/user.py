import os
import boto3
from botocore.exceptions import ClientError
from exceptions import SignInException, SignUpException, SignOutException, UserDoesNotExistException


class User:
    """
    A single User of the BattleRoyale application
    """

    def __init__(self):
        # connect to user_management client
        self.cognito_client = boto3.client("cognito-idp", region_name="eu-central-1")

        # Pool ID and secret which must be used to connect to Cognito
        self.USER_POOL_ID = os.getenv('USER_POOL_ID')
        self.USER_POOL_CLIENT_ID = os.getenv('USER_POOL_CLIENT_ID')

    def sign_up(self, username: str, password: str, email: str):
        """
        Sign up a user

        :param username: Username of new user.
        :param password: Password of new user.
        :param email: Email address of new user.
        :return: Confirmation message of successful sign up
        """
        try:
            # sign a user up to the service
            self.cognito_client.sign_up(
                ClientId=self.USER_POOL_CLIENT_ID,
                Username=username,
                Password=password,
                UserAttributes=[
                    {
                        'Name': 'email',
                        'Value': email
                    },
                ]
            )
            # confirm user as an admin (instead of via email/SMS)
            res = self.cognito_client.admin_confirm_sign_up(
                UserPoolId=self.USER_POOL_ID,
                Username=username
            )
            if res['ResponseMetadata']['HTTPStatusCode'] == 200:
                return {'message': 'Sign-up successful'}
            else:
                raise SignUpException("Cognito sign in failed")
        except self.cognito_client.exceptions.InvalidPasswordException:
            raise SignUpException(message="Invalid password")
        except Exception as e:
            raise SignUpException(message='Failed Cognito sign up')

    def sign_in(self, username: str, password: str):
        """
        Log user in with username and password

        :param username: username of user to log in
        :param password: password of user
        :return: idToken to be used for API calls, in the Authentication header of requests to graphQl_endpoint
        """

        try:
            # authenticate user and get access token
            res = self.cognito_client.initiate_auth(
                ClientId=self.USER_POOL_CLIENT_ID,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            if res['ResponseMetadata']['HTTPStatusCode'] == 200:
                return {'id_token': res["AuthenticationResult"]['IdToken'],
                        'access_token': res["AuthenticationResult"]['AccessToken'],
                        'refresh_token': res['AuthenticationResult']['RefreshToken']}
            else:
                raise SignInException(message="Cognito sign in failed")
        except self.cognito_client.exceptions.NotAuthorizedException:
            raise SignInException(message="Incorrect Username or Password")
        except ClientError:
            raise UserDoesNotExistException(message="User {} does not exist".format(username))

    def sign_out(self, access_token: str):
        """
        Function signs user out of all devices

        :param access_token: access token given during authentication (sign_in) process

        :return: confirmation message
        """
        # authenticate user and get access token
        res = self.cognito_client.global_sign_out(
            AccessToken=access_token
        )

        if res['ResponseMetadata']['HTTPStatusCode'] == 200:
            return {'message': 'Sign-out successful'}
        else:
            raise SignOutException('Failed to sign out')
