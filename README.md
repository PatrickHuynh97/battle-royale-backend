# battle-royale
Battle Royale IRL Project

### Setup
Set up a python 3.7 virtual environment and run:
   > pip install -r requirements.txt

If you intend to deploy the backend stack, you will also need some serverless dependencies:
   > npm install serverless-python-requirements
   > npm install serverless-aws-documentation

### Testing
Tests are run using a local DynamoDB database to emulate performance when deployed. This local database is run inside a 
docker container. Install docker and pull the latest amazon local DynamoDB container:
  docker pull amazon/dynamodb-local

### Deployment
To deploy the backend stack, navigate to the same level as the *serverless.yml* file and run:
   > sls deploy --stage stageName

where stageName is the name of the stage are deploying, e.g. *dev*. 


