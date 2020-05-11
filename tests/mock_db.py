import os
import unittest
import uuid

import boto3


class TestWithMockAWSServices(unittest.TestCase):
    """
    This class will setup a new table for each test case and remove the table afterwards.
    """

    def run(self, result=None, **kwargs):
        # make sure that tests are run locally
        os.environ['local_test'] = "True"

        self.table = self.setup_temp_table()

        super(TestWithMockAWSServices, self).run(result)

        self.teardown_temp_table()

    def setup_temp_table(self):
        client = boto3.client(service_name="dynamodb", endpoint_url='http://localhost:8005')
        table_name = uuid.uuid4().hex

        # put name of database in environment so tests can run realistically
        os.environ['TABLE'] = f'table/{table_name}'

        client.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'pk',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'sk',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'pk',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'sk',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'lsi',
                    'AttributeType': 'S'
                },
            ],
            LocalSecondaryIndexes=[
                {
                    'IndexName': 'lsi',
                    'KeySchema': [
                        {
                            'AttributeName': 'pk',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'lsi',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )

        dynamodb = boto3.resource(service_name='dynamodb', endpoint_url='http://localhost:8005')
        table = dynamodb.Table(table_name)
        return table

    def teardown_temp_table(self):
        self.table.delete()
