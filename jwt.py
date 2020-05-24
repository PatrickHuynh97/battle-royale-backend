# Code taken from https://github.com/awslabs/aws-support-tools/tree/master/Cognito/decode-verify-jwt

import json
import os
import time
import urllib.request
from jose import jwk, jwt
from jose.utils import base64url_decode

REGION = 'eu-central-1'
USER_POOL_ID = os.getenv('USER_POOL_ID')
USER_POOL_CLIENT_ID = os.getenv('USER_POOL_CLIENT_ID')
keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(REGION, USER_POOL_ID)
# instead of re-downloading the public keys every time
# we download them only on cold start
# https://aws.amazon.com/blogs/compute/container-reuse-in-lambda/
if not os.getenv('local_test'):
    with urllib.request.urlopen(keys_url) as f:
        response = f.read()
    keys = json.loads(response.decode('utf-8'))['keys']


def verify_token(token, id_token=False):
    # get the kid from the headers prior to verification
    headers = jwt.get_unverified_headers(token)
    kid = headers['kid']
    # search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    if key_index == -1:
        print('Public key not found in jwks.json')
        return False
    # construct the public key
    public_key = jwk.construct(keys[key_index])
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit('.', 1)
    # decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        return False
    # since we passed the verification, we can now safely
    # use the unverified claims
    claims = jwt.get_unverified_claims(token)
    # additionally we can verify the token expiration
    if time.time() > claims['exp']:
        return False
    # and the Audience  (use claims['client_id'] if verifying an access token)
    if id_token:
        if claims['aud'] != USER_POOL_CLIENT_ID:
            return False
    else:
        if claims['client_id'] != USER_POOL_CLIENT_ID:
            return False

    # now we can use the claims
    return claims
