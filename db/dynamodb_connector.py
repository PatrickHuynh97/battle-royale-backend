import os
import boto3


class AWSConfigurationException(Exception):
    pass


class DynamoDbConnector:
    table = None

    @classmethod
    def get_table(cls):
        table_arn = os.getenv('TABLE')
        if table_arn is None:
            raise AWSConfigurationException("Missing environment variable $TABLE")

        table_name = table_arn.split('/')[-1]

        if not cls.table or cls.table._name != table_name:
            if not os.getenv('local_test'):
                ddb = boto3.resource('dynamodb')
            else:
                ddb = boto3.resource('dynamodb', endpoint_url='http://localhost:8005')
            cls.table = ddb.Table(table_name)
        return cls.table

    @classmethod
    def get_client(cls):
        """
        Get DynamoDB Client to get Batch Writing
        """
        table_arn = os.getenv('TABLE')

        if table_arn is None:
            raise AWSConfigurationException("Missing environment variable $TABLE")

        table_name = table_arn.split('/')[-1]

        if not cls.client:
            cls.client = boto3.client('dynamodb')

        if not cls.client:
            if not os.getenv('local_test'):
                cls.client = boto3.client('dynamodb')
            else:
                cls.client = boto3.client('dynamodb', endpoint_url='http://localhost:8005')
        return cls.client, table_name
