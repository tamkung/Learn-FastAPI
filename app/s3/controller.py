import json
import os
import boto3
import io
from botocore.exceptions import ClientError
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
S3_REGION_NAME = os.getenv('S3_REGION_NAME')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')

def uploadFileToS3(filename, message_id):

    session = boto3.session.Session(
        aws_access_key_id = AWS_ACCESS_KEY_ID,
        aws_secret_access_key = AWS_SECRET_ACCESS_KEY,
        region_name = S3_REGION_NAME
    )

    s3_client = session.client(
        service_name = "s3",
        endpoint_url = S3_ENDPOINT_URL
    )
        
    filename_output = "tmp/"+message_id+"/"+filename["name_file"]
    try:
        response_upload_file = s3_client.upload_file("tmp/"+filename["name_file"], S3_BUCKET_NAME, filename_output, ExtraArgs={'ContentType': filename["content_type"]})
        if os.path.exists("tmp/"+filename["name_file"]):
            os.remove("tmp/"+filename["name_file"])
        else:
            print("The file does not exist")
    except ClientError as e:
        print(str(e))
        return False
    # print(str(response_upload_file))
    return filename_output

def uploadContentImageToS3(filename, message_id):

    session = boto3.session.Session(
        aws_access_key_id = AWS_ACCESS_KEY_ID,
        aws_secret_access_key = AWS_SECRET_ACCESS_KEY,
        region_name = S3_REGION_NAME
    )

    s3_client = session.client(
        service_name = "s3",
        endpoint_url = S3_ENDPOINT_URL
    )

    filename_output = "content/"+message_id+"/"+filename["name_file"]
    try:
        response_upload_file = s3_client.upload_file("tmp/"+filename["name_file"], S3_BUCKET_NAME, filename_output, ExtraArgs={'ContentType': filename["content_type"]})
        if os.path.exists("tmp/"+filename["name_file"]):
            os.remove("tmp/"+filename["name_file"])
        else:
            print("The file does not exist")
    except ClientError as e:
        print(str(e))
        return False
    # print(str(response_upload_file))
    return filename_output
