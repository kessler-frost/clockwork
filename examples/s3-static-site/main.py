"""S3 Static Website Hosting Example

This example demonstrates using S3BucketResource to create an S3 bucket
configured for static website hosting. It shows how Clockwork can manage
cloud resources beyond containers.

Prerequisites:
- AWS credentials configured (via environment variables or ~/.aws/credentials)
- Install AWS dependencies: pip install clockwork[aws]
"""

from clockwork.assertions import BucketExistsAssert
from clockwork.resources import S3BucketResource

# Example 1: Intelligent completion
# Let intelligence suggest a bucket name based on the description
docs_bucket = S3BucketResource(
    description="static website hosting for project documentation",
    assertions=[BucketExistsAssert()],
)

# Example 2: Full control - explicitly configured static website
website_bucket = S3BucketResource(
    name="docs-website",
    bucket_name="my-docs-website-example-2024",
    region="us-east-1",
    public=True,
    website_config={
        "index_document": "index.html",
        "error_document": "error.html",
    },
    tags={
        "Environment": "production",
        "Project": "documentation",
        "ManagedBy": "clockwork",
    },
    assertions=[BucketExistsAssert()],
)

# Example 3: Private bucket with versioning for backups
backup_bucket = S3BucketResource(
    name="backup-storage",
    bucket_name="my-app-backups-example-2024",
    region="us-west-2",
    public=False,
    versioning=True,
    tags={
        "Environment": "production",
        "Purpose": "backups",
        "ManagedBy": "clockwork",
    },
    assertions=[BucketExistsAssert()],
)

# To deploy this example:
# cd examples/s3-static-site
# uv run clockwork apply
#
# To verify assertions:
# uv run clockwork assert
#
# To destroy:
# uv run clockwork destroy
