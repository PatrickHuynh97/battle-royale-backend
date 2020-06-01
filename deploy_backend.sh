#!/bin/bash

# "Usage: deploy_backend.sh <environment>", e.g. deploy_backend.sh dev

set -e

ENVIRONMENT=$1

if [[ ${ENVIRONMENT} == "dev" ]]; then
    echo "Dev environment"
    DOC_BUCKET="dev-api-documentation"
elif [[ ${ENVIRONMENT} == "stage" ]]; then
    echo "Stage environment"
    DOC_BUCKET="stage-api-documentation"
elif [[ ${ENVIRONMENT} == "prod" ]]; then
    echo "Production environment"
    DOC_BUCKET="prod-api-documentation"
else
    echo "Environment has to be one of: dev | stage | prod"
    exit 1
fi

echo "#### Deploying stack ####"
sls deploy --stage ${ENVIRONMENT}

echo "#### Downloading swagger documentation ####"
aws apigateway get-export --parameters extensions='apigateway' --rest-api-id abcdefg123 --stage-name dev --export-type swagger swagger.json

echo "#### Uploading swagger documentation ####"
cd
aws s3 cp swagger.json "s3://${DOC_BUCKET}/${ENVIRONMENT}/"

exit 0
