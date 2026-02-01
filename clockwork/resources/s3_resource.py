"""AWS S3 Bucket resource for cloud storage with optional intelligent completion."""

from typing import Any

from pydantic import Field

try:
    import pulumi_aws as aws

    HAS_PULUMI_AWS = True
except ImportError:
    HAS_PULUMI_AWS = False
    aws = None

from .base import Resource


class S3BucketResource(Resource):
    """AWS S3 Bucket resource - manages S3 buckets with intelligence completion.

    This resource allows you to define S3 buckets with just a description.
    Intelligence will complete missing fields including bucket_name and
    appropriate configuration based on the use case.

    Attributes:
        description: What the bucket is for - intelligence uses this to complete fields
        name: Pulumi resource name (optional - intelligently generated if not provided)
        bucket_name: Globally unique S3 bucket name (optional - intelligently generated)
        region: AWS region for the bucket (default: us-east-1)
        public: Whether the bucket should be publicly accessible (default: False)
        versioning: Enable versioning on the bucket (default: False)
        website_config: Static website hosting configuration (optional)
        tags: Tags to apply to the bucket (default: empty dict)

    Examples:
        # Minimal - intelligence completes everything:
        >>> bucket = S3BucketResource(
        ...     description="static website hosting for documentation"
        ... )
        # Intelligence generates: name="docs-website", bucket_name="docs-website-xyz123"

        # Full control - no intelligence:
        >>> bucket = S3BucketResource(
        ...     name="my-bucket",
        ...     bucket_name="my-unique-bucket-name-123",
        ...     region="us-west-2",
        ...     public=True,
        ...     website_config={
        ...         "index_document": "index.html",
        ...         "error_document": "error.html"
        ...     }
        ... )
    """

    description: str | None = None
    name: str | None = Field(
        None,
        description="Pulumi resource name - must be unique within the stack",
        examples=["docs-bucket", "app-assets", "backup-storage"],
    )
    bucket_name: str | None = Field(
        None,
        description="Globally unique S3 bucket name - must be DNS-compliant",
        examples=[
            "my-company-docs-2024",
            "app-static-assets-prod",
            "backup-storage-xyz123",
        ],
    )
    region: str = Field(
        default="us-east-1",
        description="AWS region where the bucket will be created",
        examples=["us-east-1", "us-west-2", "eu-west-1"],
    )
    public: bool = Field(
        default=False,
        description="Whether the bucket should be publicly readable",
    )
    versioning: bool = Field(
        default=False,
        description="Enable versioning to keep multiple versions of objects",
    )
    website_config: dict | None = Field(
        None,
        description="Static website hosting configuration",
        examples=[
            {"index_document": "index.html", "error_document": "error.html"},
            {"index_document": "index.html"},
        ],
    )
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Tags to apply to the bucket for organization and billing",
        examples=[
            {"Environment": "production", "Project": "docs"},
            {"Team": "engineering"},
        ],
    )

    def needs_completion(self) -> bool:
        """Returns True if any critical field needs intelligent completion.

        The bucket_name field is the primary field requiring completion since
        it must be globally unique across all AWS accounts.

        Returns:
            bool: True if bucket_name is None, False otherwise
        """
        return self.bucket_name is None

    def to_pulumi(self):
        """Create Pulumi AWS S3 Bucket resource.

        Uses pulumi_aws to create and manage the S3 bucket. All fields should
        be populated by intelligent completion before this is called.

        Returns:
            aws.s3.Bucket: Pulumi S3 bucket resource instance

        Raises:
            ImportError: If pulumi-aws is not installed
            ValueError: If required fields are not completed
        """
        if not HAS_PULUMI_AWS:
            raise ImportError(
                "pulumi-aws is required for S3BucketResource. "
                "Install with: pip install clockwork[aws]"
            )

        # All fields should be populated by intelligent completion
        if self.bucket_name is None:
            raise ValueError(
                f"Resource fields not completed. bucket_name={self.bucket_name}"
            )

        # Use name or bucket_name as the Pulumi resource name
        resource_name = self.name or self.bucket_name

        # Build website configuration if provided
        website_args = None
        if self.website_config:
            website_args = aws.s3.BucketWebsiteArgs(
                index_document=self.website_config.get("index_document"),
                error_document=self.website_config.get("error_document"),
            )

        # Build versioning configuration
        versioning_args = aws.s3.BucketVersioningArgs(
            enabled=self.versioning,
        )

        # Check if we have temporary compile options (from _compile_with_opts)
        if hasattr(self, "_temp_compile_opts"):
            opts = self._temp_compile_opts
        else:
            opts = self._build_dependency_options()

        # Create the S3 bucket
        bucket = aws.s3.Bucket(
            resource_name,
            bucket=self.bucket_name,
            acl="public-read" if self.public else "private",
            versioning=versioning_args,
            website=website_args,
            tags=self.tags if self.tags else None,
            opts=opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = bucket

        return bucket

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this S3 bucket resource.

        Returns shareable fields that other resources can use when connected.
        This includes bucket name, region, public status, and website endpoint
        if configured for static hosting.

        Returns:
            Dict with shareable fields:
                - name: Resource name
                - type: Resource class name (S3BucketResource)
                - bucket_name: The S3 bucket name
                - region: AWS region
                - public: Whether the bucket is public
                - website_endpoint: Website URL if website hosting is enabled
                - arn: The bucket ARN pattern

        Example:
            >>> bucket = S3BucketResource(
            ...     name="docs",
            ...     bucket_name="my-docs-bucket",
            ...     region="us-east-1",
            ...     website_config={"index_document": "index.html"}
            ... )
            >>> bucket.get_connection_context()
            {
                'name': 'docs',
                'type': 'S3BucketResource',
                'bucket_name': 'my-docs-bucket',
                'region': 'us-east-1',
                'public': False,
                'website_endpoint': 'my-docs-bucket.s3-website-us-east-1.amazonaws.com',
                'arn': 'arn:aws:s3:::my-docs-bucket'
            }
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
            "bucket_name": self.bucket_name,
            "region": self.region,
            "public": self.public,
        }

        if self.bucket_name:
            context["arn"] = f"arn:aws:s3:::{self.bucket_name}"

            # Add website endpoint if website hosting is configured
            if self.website_config:
                context["website_endpoint"] = (
                    f"{self.bucket_name}.s3-website-{self.region}.amazonaws.com"
                )

        if self.tags:
            context["tags"] = self.tags

        return context
