"""Tests for S3BucketResource.

These tests are skipped if pulumi-aws is not installed.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

# Check if pulumi-aws is available
try:
    import pulumi_aws  # noqa: F401

    HAS_PULUMI_AWS = True
except ImportError:
    HAS_PULUMI_AWS = False

# Skip all tests if pulumi-aws is not installed
pytestmark = pytest.mark.skipif(
    not HAS_PULUMI_AWS,
    reason="pulumi-aws not installed - install with: pip install clockwork[aws]",
)


@pytest.fixture
def s3_bucket_resource():
    """Import S3BucketResource only if available."""
    from clockwork.resources import S3BucketResource

    return S3BucketResource


def test_s3_bucket_resource_basic(s3_bucket_resource):
    """Test basic S3BucketResource instantiation."""
    bucket = s3_bucket_resource(
        name="test-bucket",
        description="Test bucket",
    )

    assert bucket.name == "test-bucket"
    assert bucket.description == "Test bucket"
    assert bucket.bucket_name is None
    assert bucket.region == "us-east-1"
    assert bucket.public is False
    assert bucket.versioning is False
    assert bucket.website_config is None
    assert bucket.tags == {}


def test_s3_bucket_resource_with_bucket_name(s3_bucket_resource):
    """Test S3BucketResource with explicit bucket name."""
    bucket = s3_bucket_resource(
        name="my-bucket",
        bucket_name="my-unique-bucket-name-12345",
        region="us-west-2",
    )

    assert bucket.name == "my-bucket"
    assert bucket.bucket_name == "my-unique-bucket-name-12345"
    assert bucket.region == "us-west-2"


def test_s3_bucket_resource_full_config(s3_bucket_resource):
    """Test S3BucketResource with all parameters."""
    bucket = s3_bucket_resource(
        name="docs-bucket",
        bucket_name="my-docs-bucket-12345",
        region="eu-west-1",
        public=True,
        versioning=True,
        website_config={
            "index_document": "index.html",
            "error_document": "error.html",
        },
        tags={
            "Environment": "production",
            "Project": "docs",
        },
    )

    assert bucket.name == "docs-bucket"
    assert bucket.bucket_name == "my-docs-bucket-12345"
    assert bucket.region == "eu-west-1"
    assert bucket.public is True
    assert bucket.versioning is True
    assert bucket.website_config == {
        "index_document": "index.html",
        "error_document": "error.html",
    }
    assert bucket.tags == {
        "Environment": "production",
        "Project": "docs",
    }


def test_needs_completion_no_bucket_name(s3_bucket_resource):
    """Test needs_completion() returns True when bucket_name is None."""
    bucket = s3_bucket_resource(
        name="test-bucket",
        description="Test bucket",
    )

    assert bucket.needs_completion() is True


def test_needs_completion_with_bucket_name(s3_bucket_resource):
    """Test needs_completion() returns False when bucket_name is set."""
    bucket = s3_bucket_resource(
        name="test-bucket",
        bucket_name="my-bucket-12345",
        description="Test bucket",
    )

    assert bucket.needs_completion() is False


def test_to_pulumi_with_complete_fields(s3_bucket_resource):
    """Test to_pulumi() creates S3 Bucket resource with complete fields."""
    bucket = s3_bucket_resource(
        name="test-bucket",
        bucket_name="my-test-bucket-12345",
        region="us-east-1",
        public=False,
        versioning=True,
        tags={"Environment": "test"},
    )

    # Mock pulumi_aws.s3.Bucket to avoid actual Pulumi initialization
    with (
        patch("pulumi_aws.s3.Bucket") as mock_bucket,
        patch("pulumi_aws.s3.BucketVersioningArgs") as mock_versioning,
    ):
        mock_instance = Mock()
        mock_bucket.return_value = mock_instance
        mock_versioning.return_value = Mock()

        pulumi_resource = bucket.to_pulumi()

        # Verify the Bucket was called
        assert mock_bucket.called
        assert pulumi_resource == mock_instance


def test_to_pulumi_with_website_config(s3_bucket_resource):
    """Test to_pulumi() creates S3 Bucket with website configuration."""
    bucket = s3_bucket_resource(
        name="website-bucket",
        bucket_name="my-website-bucket-12345",
        public=True,
        website_config={
            "index_document": "index.html",
            "error_document": "error.html",
        },
    )

    with (
        patch("pulumi_aws.s3.Bucket") as mock_bucket,
        patch("pulumi_aws.s3.BucketVersioningArgs") as mock_versioning,
        patch("pulumi_aws.s3.BucketWebsiteArgs") as mock_website,
    ):
        mock_instance = Mock()
        mock_bucket.return_value = mock_instance
        mock_versioning.return_value = Mock()
        mock_website.return_value = Mock()

        pulumi_resource = bucket.to_pulumi()

        # Verify website args were created
        assert mock_website.called
        assert mock_bucket.called
        assert pulumi_resource == mock_instance


def test_to_pulumi_missing_bucket_name_raises_error(s3_bucket_resource):
    """Test to_pulumi() raises error when bucket_name is not completed."""
    bucket = s3_bucket_resource(
        name="incomplete-bucket",
        description="Bucket with missing bucket_name",
    )

    # Should raise error when required fields are not completed
    with pytest.raises(ValueError, match="Resource fields not completed"):
        bucket.to_pulumi()


def test_get_connection_context(s3_bucket_resource):
    """Test get_connection_context returns correct fields."""
    bucket = s3_bucket_resource(
        name="my-bucket",
        bucket_name="my-docs-bucket-12345",
        region="us-west-2",
        public=True,
        tags={"Environment": "production"},
    )

    context = bucket.get_connection_context()

    assert context["name"] == "my-bucket"
    assert context["type"] == "S3BucketResource"
    assert context["bucket_name"] == "my-docs-bucket-12345"
    assert context["region"] == "us-west-2"
    assert context["public"] is True
    assert context["arn"] == "arn:aws:s3:::my-docs-bucket-12345"
    assert context["tags"] == {"Environment": "production"}


def test_get_connection_context_with_website(s3_bucket_resource):
    """Test get_connection_context includes website endpoint."""
    bucket = s3_bucket_resource(
        name="website-bucket",
        bucket_name="my-website-12345",
        region="us-east-1",
        website_config={"index_document": "index.html"},
    )

    context = bucket.get_connection_context()

    assert context["bucket_name"] == "my-website-12345"
    assert (
        context["website_endpoint"]
        == "my-website-12345.s3-website-us-east-1.amazonaws.com"
    )


def test_get_connection_context_minimal(s3_bucket_resource):
    """Test get_connection_context with minimal fields."""
    bucket = s3_bucket_resource(
        name="minimal-bucket",
        bucket_name="minimal-bucket-12345",
    )

    context = bucket.get_connection_context()

    assert context["name"] == "minimal-bucket"
    assert context["type"] == "S3BucketResource"
    assert context["bucket_name"] == "minimal-bucket-12345"
    assert context["region"] == "us-east-1"
    assert context["public"] is False
    assert context["arn"] == "arn:aws:s3:::minimal-bucket-12345"
    # Empty tags should not be in context
    assert "tags" not in context
    # No website config, so no endpoint
    assert "website_endpoint" not in context


def test_s3_bucket_resource_defaults(s3_bucket_resource):
    """Test S3BucketResource default values."""
    bucket = s3_bucket_resource(description="Just a description")

    assert bucket.name is None
    assert bucket.bucket_name is None
    assert bucket.region == "us-east-1"
    assert bucket.public is False
    assert bucket.versioning is False
    assert bucket.website_config is None
    assert bucket.tags == {}


class TestS3Assertions:
    """Tests for S3 assertions."""

    @pytest.fixture
    def bucket_exists_assert(self):
        """Import BucketExistsAssert only if available."""
        try:
            from clockwork.assertions import BucketExistsAssert

            return BucketExistsAssert
        except ImportError:
            pytest.skip("boto3 not installed")

    @pytest.fixture
    def bucket_accessible_assert(self):
        """Import BucketAccessibleAssert only if available."""
        try:
            from clockwork.assertions import BucketAccessibleAssert

            return BucketAccessibleAssert
        except ImportError:
            pytest.skip("boto3 not installed")

    @pytest.fixture
    def bucket_versioning_assert(self):
        """Import BucketVersioningEnabledAssert only if available."""
        try:
            from clockwork.assertions import BucketVersioningEnabledAssert

            return BucketVersioningEnabledAssert
        except ImportError:
            pytest.skip("boto3 not installed")

    def test_bucket_exists_assert_instantiation(self, bucket_exists_assert):
        """Test BucketExistsAssert can be instantiated."""
        assertion = bucket_exists_assert()
        assert assertion.bucket_name is None
        assert assertion.timeout_seconds == 10

    def test_bucket_exists_assert_with_bucket_name(self, bucket_exists_assert):
        """Test BucketExistsAssert with explicit bucket name."""
        assertion = bucket_exists_assert(bucket_name="my-bucket")
        assert assertion.bucket_name == "my-bucket"

    def test_bucket_accessible_assert_instantiation(
        self, bucket_accessible_assert
    ):
        """Test BucketAccessibleAssert can be instantiated."""
        assertion = bucket_accessible_assert()
        assert assertion.bucket_name is None
        assert assertion.timeout_seconds == 10

    def test_bucket_versioning_assert_instantiation(
        self, bucket_versioning_assert
    ):
        """Test BucketVersioningEnabledAssert can be instantiated."""
        assertion = bucket_versioning_assert()
        assert assertion.bucket_name is None
        assert assertion.timeout_seconds == 10

    @pytest.mark.asyncio
    async def test_bucket_exists_assert_check_success(
        self, bucket_exists_assert, s3_bucket_resource
    ):
        """Test BucketExistsAssert.check() returns True when bucket exists."""
        assertion = bucket_exists_assert()
        bucket = s3_bucket_resource(
            name="test",
            bucket_name="existing-bucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.head_bucket.return_value = {}

            result = await assertion.check(bucket)
            assert result is True

    @pytest.mark.asyncio
    async def test_bucket_exists_assert_check_not_found(
        self, bucket_exists_assert, s3_bucket_resource
    ):
        """Test BucketExistsAssert.check() returns False when bucket doesn't exist."""
        from botocore.exceptions import ClientError

        assertion = bucket_exists_assert()
        bucket = s3_bucket_resource(
            name="test",
            bucket_name="nonexistent-bucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.head_bucket.side_effect = ClientError(
                {"Error": {"Code": "404"}},
                "HeadBucket",
            )

            result = await assertion.check(bucket)
            assert result is False

    @pytest.mark.asyncio
    async def test_bucket_accessible_assert_check_success(
        self, bucket_accessible_assert, s3_bucket_resource
    ):
        """Test BucketAccessibleAssert.check() returns True when can list."""
        assertion = bucket_accessible_assert()
        bucket = s3_bucket_resource(
            name="test",
            bucket_name="accessible-bucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.list_objects_v2.return_value = {"Contents": []}

            result = await assertion.check(bucket)
            assert result is True

    @pytest.mark.asyncio
    async def test_bucket_versioning_assert_check_enabled(
        self, bucket_versioning_assert, s3_bucket_resource
    ):
        """Test BucketVersioningEnabledAssert.check() when versioning enabled."""
        assertion = bucket_versioning_assert()
        bucket = s3_bucket_resource(
            name="test",
            bucket_name="versioned-bucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.get_bucket_versioning.return_value = {"Status": "Enabled"}

            result = await assertion.check(bucket)
            assert result is True

    @pytest.mark.asyncio
    async def test_bucket_versioning_assert_check_disabled(
        self, bucket_versioning_assert, s3_bucket_resource
    ):
        """Test BucketVersioningEnabledAssert.check() when versioning disabled."""
        assertion = bucket_versioning_assert()
        bucket = s3_bucket_resource(
            name="test",
            bucket_name="unversioned-bucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.get_bucket_versioning.return_value = {}

            result = await assertion.check(bucket)
            assert result is False
