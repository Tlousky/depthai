import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from pathlib import Path

class S3Uploader:
    def __init__(self, bucket_name, region_name=None):
        self.bucket_name = bucket_name
        self.region_name = region_name
        
        # Load credentials from .aws/.aws_credentials file
        creds_path = Path(__file__).parent / ".aws" / ".aws_credentials"
        if creds_path.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(creds_path)
            if 'default' in config:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=config['default']['aws_access_key_id'],
                    aws_secret_access_key=config['default']['aws_secret_access_key'],
                    region_name=self.region_name
                )
            else:
                print(f"Section 'default' not found in {creds_path}. Using default boto3 chain.")
                self.s3_client = boto3.client('s3', region_name=self.region_name)
        else:
            print(f"Credentials file not found at {creds_path}. Using default boto3 chain.")
            self.s3_client = boto3.client('s3', region_name=self.region_name)

    def get_uploaded_files(self, prefix):
        """
        List all files currently in the S3 bucket under the given prefix.
        Returns a set of filenames (without the prefix).
        """
        uploaded_files = set()
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Remove prefix to get just the filename
                        key = obj['Key']
                        if key.startswith(prefix):
                            filename = key[len(prefix):]
                            uploaded_files.add(filename)
        except ClientError as e:
            print(f"Error listing objects: {e}")
        return uploaded_files

    def upload_file(self, file_path, object_name):
        """Upload a file to an S3 bucket"""
        try:
            self.s3_client.upload_file(str(file_path), self.bucket_name, object_name)
            print(f"Uploaded {file_path} to {self.bucket_name}/{object_name}")
            return True
        except FileNotFoundError:
            print(f"The file was not found: {file_path}")
            return False
        except NoCredentialsError:
            print("Credentials not available")
            return False
        except ClientError as e:
            print(f"Client error: {e}")
            return False

    def scan_and_upload(self, directory, user_uuid):
        """
        Scans the directory for video files and uploads them if they don't exist in S3.
        """
        directory = Path(directory)
        if not directory.exists():
            print(f"Directory {directory} does not exist.")
            return

        # Ensure prefix ends with a slash
        prefix = f"{user_uuid}/"
        
        print(f"Checking existing files in S3 under {prefix}...")
        existing_files = self.get_uploaded_files(prefix)
        
        # Supported video extensions
        extensions = {'.mp4', '.avi', '.mkv', '.webm'}
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                if file_path.name not in existing_files:
                    object_name = f"{prefix}{file_path.name}"
                    print(f"Uploading {file_path.name}...")
                    self.upload_file(file_path, object_name)
                else:
                    print(f"Skipping {file_path.name}, already uploaded.")
