# S3 Static Website Example

## Overview

This example demonstrates using `S3BucketResource` to create AWS S3 buckets for static website hosting. It shows how Clockwork extends beyond container management to cloud resources.

## What This Demonstrates

- **S3BucketResource**: Creating and managing S3 buckets
- **Intelligent Completion**: Let AI suggest bucket names from descriptions
- **Static Website Hosting**: Configuring S3 for website hosting
- **Versioning**: Enabling version control on buckets
- **S3 Assertions**: Validating bucket existence

## Prerequisites

### 1. Install AWS Dependencies

```bash
# Install Clockwork with AWS support
pip install clockwork[aws]

# Or with uv
uv pip install clockwork[aws]
```

### 2. Configure AWS Credentials

S3BucketResource requires valid AWS credentials. Configure them using one of these methods:

**Option A: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

**Option B: AWS Credentials File**
```bash
# Create or edit ~/.aws/credentials
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
```

**Option C: AWS CLI**
```bash
aws configure
```

### 3. Required IAM Permissions

Your AWS user/role needs these permissions:
- `s3:CreateBucket`
- `s3:DeleteBucket`
- `s3:PutBucketAcl`
- `s3:PutBucketVersioning`
- `s3:PutBucketWebsite`
- `s3:PutBucketTagging`
- `s3:HeadBucket`
- `s3:ListBucket`
- `s3:GetBucketVersioning`

## Architecture

```
S3 Static Website Setup
|
+-- docs-bucket (S3BucketResource)
|   +-- Intelligently named
|   +-- Website hosting: enabled
|   +-- Assertion: BucketExistsAssert
|
+-- website-bucket (S3BucketResource)
|   +-- Bucket: my-docs-website-example-2024
|   +-- Region: us-east-1
|   +-- Public: true
|   +-- Website: index.html, error.html
|
+-- backup-bucket (S3BucketResource)
    +-- Bucket: my-app-backups-example-2024
    +-- Region: us-west-2
    +-- Public: false
    +-- Versioning: enabled
```

## Components

### 1. Docs Bucket (Intelligent Completion)

```python
docs_bucket = S3BucketResource(
    description="static website hosting for project documentation",
    assertions=[BucketExistsAssert()],
)
```

Intelligence will:
- Generate a unique bucket name based on the description
- Configure appropriate settings for documentation hosting

### 2. Website Bucket (Explicit Configuration)

```python
website_bucket = S3BucketResource(
    name="docs-website",
    bucket_name="my-docs-website-example-2024",
    region="us-east-1",
    public=True,
    website_config={
        "index_document": "index.html",
        "error_document": "error.html",
    },
    tags={...},
)
```

Fully specified static website bucket with:
- Public access for website hosting
- Custom index and error pages
- Organizational tags

### 3. Backup Bucket (Private with Versioning)

```python
backup_bucket = S3BucketResource(
    name="backup-storage",
    bucket_name="my-app-backups-example-2024",
    region="us-west-2",
    public=False,
    versioning=True,
    tags={...},
)
```

Private bucket with:
- Versioning enabled for data protection
- Cross-region deployment (us-west-2)

## Running This Example

### Deploy the Buckets

```bash
cd examples/s3-static-site
uv run clockwork apply
```

### Verify Assertions

```bash
uv run clockwork assert
```

Expected output:
- All buckets exist
- Versioning enabled on backup bucket

### Upload Content (Optional)

After deployment, upload your static website:

```bash
# Upload index.html
aws s3 cp index.html s3://my-docs-website-example-2024/

# Upload all content from a directory
aws s3 sync ./public/ s3://my-docs-website-example-2024/
```

### Access Your Website

After uploading content, access your website at:
```
http://my-docs-website-example-2024.s3-website-us-east-1.amazonaws.com
```

### Clean Up

```bash
uv run clockwork destroy
```

Note: You must empty the bucket before destroying (or use AWS Console).

## S3 Bucket Naming

S3 bucket names must be:
- Globally unique across all AWS accounts
- 3-63 characters long
- Contain only lowercase letters, numbers, and hyphens
- Start with a letter or number

When using intelligent completion, Clockwork generates unique names that follow these rules.

## Available Assertions

### BucketExistsAssert

Validates that the S3 bucket exists in AWS.

```python
from clockwork.assertions import BucketExistsAssert

bucket = S3BucketResource(
    ...,
    assertions=[BucketExistsAssert()]
)
```

### BucketAccessibleAssert

Validates that objects can be listed in the bucket.

```python
from clockwork.assertions import BucketAccessibleAssert

bucket = S3BucketResource(
    ...,
    assertions=[BucketAccessibleAssert()]
)
```

### BucketVersioningEnabledAssert

Validates that versioning is enabled on the bucket.

```python
from clockwork.assertions import BucketVersioningEnabledAssert

bucket = S3BucketResource(
    ...,
    versioning=True,
    assertions=[BucketVersioningEnabledAssert()]
)
```

## Customization Ideas

1. **Add CloudFront**: Create a CDN distribution in front of the S3 bucket
2. **Add Route53**: Configure a custom domain for your website
3. **Add Lambda**: Create a static site generator that uploads to S3
4. **Multi-region**: Deploy buckets to multiple regions for redundancy

## Troubleshooting

### "Bucket name already exists"

S3 bucket names are globally unique. Choose a different bucket name or add a unique suffix (e.g., your AWS account ID).

### "Access Denied"

Check that:
1. AWS credentials are configured correctly
2. Your IAM user/role has the required permissions
3. The bucket policy allows your actions

### "ImportError: pulumi-aws not installed"

Install the AWS dependencies:
```bash
pip install clockwork[aws]
```

## Related Examples

- `examples/composite-resources/`: Container-based examples
- Future: CloudFront distribution example
- Future: Route53 DNS example
