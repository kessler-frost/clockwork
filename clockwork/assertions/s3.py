"""AWS S3 bucket assertions for validating bucket state."""

from typing import TYPE_CHECKING

from .base import BaseAssertion

if TYPE_CHECKING:
    from clockwork.resources.base import Resource


class BucketExistsAssert(BaseAssertion):
    """Assert that an S3 bucket exists.

    Checks if the specified S3 bucket exists in AWS. Uses the bucket name
    from the resource or an explicit override.

    Attributes:
        bucket_name: Optional override for bucket name (defaults to resource.bucket_name)
        timeout_seconds: Maximum time to wait for check (default: 10)

    Example:
        >>> BucketExistsAssert()  # Uses resource bucket_name
        >>> BucketExistsAssert(bucket_name="my-explicit-bucket")
    """

    bucket_name: str | None = None
    timeout_seconds: int = 10

    async def check(self, resource: "Resource") -> bool:
        """Check if the S3 bucket exists.

        Args:
            resource: The S3BucketResource to validate

        Returns:
            True if bucket exists, False otherwise
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 assertions. "
                "Install with: pip install clockwork[aws]"
            )

        # Get bucket name from assertion or resource
        bucket = self.bucket_name
        if bucket is None:
            bucket = getattr(resource, "bucket_name", None)
        if bucket is None:
            return False

        # Get region from resource
        region = getattr(resource, "region", "us-east-1")

        try:
            s3 = boto3.client("s3", region_name=region)
            s3.head_bucket(Bucket=bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # 404 means bucket doesn't exist
            # 403 means bucket exists but we don't have access
            if error_code == "403":
                # Bucket exists but access denied - still counts as exists
                return True
            return False
        except Exception:
            return False


class BucketAccessibleAssert(BaseAssertion):
    """Assert that an S3 bucket is accessible (can list objects).

    Checks if the S3 bucket can be accessed and objects can be listed.
    This validates both existence and permissions.

    Attributes:
        bucket_name: Optional override for bucket name (defaults to resource.bucket_name)
        timeout_seconds: Maximum time to wait for check (default: 10)

    Example:
        >>> BucketAccessibleAssert()  # Uses resource bucket_name
        >>> BucketAccessibleAssert(bucket_name="my-accessible-bucket")
    """

    bucket_name: str | None = None
    timeout_seconds: int = 10

    async def check(self, resource: "Resource") -> bool:
        """Check if the S3 bucket is accessible.

        Args:
            resource: The S3BucketResource to validate

        Returns:
            True if bucket is accessible and can list objects, False otherwise
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 assertions. "
                "Install with: pip install clockwork[aws]"
            )

        # Get bucket name from assertion or resource
        bucket = self.bucket_name
        if bucket is None:
            bucket = getattr(resource, "bucket_name", None)
        if bucket is None:
            return False

        # Get region from resource
        region = getattr(resource, "region", "us-east-1")

        try:
            s3 = boto3.client("s3", region_name=region)
            # Try to list objects (with max 1 to minimize data transfer)
            s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
            return True
        except ClientError:
            return False
        except Exception:
            return False


class BucketVersioningEnabledAssert(BaseAssertion):
    """Assert that versioning is enabled on an S3 bucket.

    Checks if the S3 bucket has versioning enabled, which is important
    for data protection and compliance.

    Attributes:
        bucket_name: Optional override for bucket name (defaults to resource.bucket_name)
        timeout_seconds: Maximum time to wait for check (default: 10)

    Example:
        >>> BucketVersioningEnabledAssert()  # Uses resource bucket_name
    """

    bucket_name: str | None = None
    timeout_seconds: int = 10

    async def check(self, resource: "Resource") -> bool:
        """Check if versioning is enabled on the S3 bucket.

        Args:
            resource: The S3BucketResource to validate

        Returns:
            True if versioning is enabled, False otherwise
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 assertions. "
                "Install with: pip install clockwork[aws]"
            )

        # Get bucket name from assertion or resource
        bucket = self.bucket_name
        if bucket is None:
            bucket = getattr(resource, "bucket_name", None)
        if bucket is None:
            return False

        # Get region from resource
        region = getattr(resource, "region", "us-east-1")

        try:
            s3 = boto3.client("s3", region_name=region)
            response = s3.get_bucket_versioning(Bucket=bucket)
            return response.get("Status") == "Enabled"
        except ClientError:
            return False
        except Exception:
            return False
