from typing import List, Optional, Union

import boto3
from botocore.config import Config


class S3Client:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: Optional[str],
        verify: Union[bool, str],
        addressing_style: str,
        connect_timeout: int,
        read_timeout: int,
    ) -> None:
        config = Config(
            s3={"addressing_style": addressing_style},
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            retries={"max_attempts": 1},
        )
        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            verify=verify,
            config=config,
        )

    def list_keys(self, bucket: str, prefix: str) -> List[str]:
        keys: List[str] = []
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = self._client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []) or []:
                key = item.get("Key")
                if key:
                    keys.append(key)
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
        return keys

    def download(self, bucket: str, key: str, dest_path: str) -> None:
        self._client.download_file(bucket, key, dest_path)

    def upload(self, bucket: str, key: str, src_path: str) -> None:
        self._client.upload_file(src_path, bucket, key)

    def delete(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)
