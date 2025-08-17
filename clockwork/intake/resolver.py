"""
Module and Provider Resolution for Clockwork

This module provides functionality to resolve module and provider references,
handle version pinning, download and cache modules/providers, and integrate
with the intake phase for complete configuration resolution.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.request import urlopen, Request
import subprocess
import re

from pydantic import BaseModel, Field, validator

from ..models import IR, Module, Provider, Variable


# =============================================================================
# Resolver Models
# =============================================================================

class ResolutionError(Exception):
    """Exception raised when resolution fails."""
    
    def __init__(self, message: str, module_name: str = None, provider_name: str = None):
        self.message = message
        self.module_name = module_name
        self.provider_name = provider_name
        
        error_msg = f"Resolution error: {message}"
        if module_name:
            error_msg += f" for module '{module_name}'"
        if provider_name:
            error_msg += f" for provider '{provider_name}'"
            
        super().__init__(error_msg)


class CacheEntry(BaseModel):
    """Cache entry for downloaded modules/providers."""
    source: str
    version: str
    checksum: str
    download_time: datetime
    local_path: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if cache entry is expired."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        return self.download_time < cutoff


class ResolutionResult(BaseModel):
    """Result of module/provider resolution."""
    name: str
    source: str
    resolved_version: str
    local_path: str
    checksum: str
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False


class VersionConstraint(BaseModel):
    """Version constraint specification."""
    operator: str  # ">=", "<=", "==", "~>", "^"
    version: str
    
    @validator('operator')
    def validate_operator(cls, v):
        """Validate version operator."""
        valid_operators = [">=", "<=", "==", "~>", "^", ">", "<"]
        if v not in valid_operators:
            raise ValueError(f"Invalid operator: {v}. Must be one of {valid_operators}")
        return v


# =============================================================================
# Cache Management
# =============================================================================

class CacheManager:
    """Manages local cache for downloaded modules and providers."""
    
    def __init__(self, cache_dir: str = ".clockwork/cache"):
        """Initialize cache manager."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "index.json"
        self._load_index()
    
    def _load_index(self):
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    self.index = {k: CacheEntry.model_validate(v) for k, v in data.items()}
            except (json.JSONDecodeError, Exception):
                # If index is corrupted, start fresh
                self.index = {}
        else:
            self.index = {}
    
    def _save_index(self):
        """Save cache index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                serializable_index = {k: v.model_dump() for k, v in self.index.items()}
                json.dump(serializable_index, f, indent=2, default=str)
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to save cache index: {e}")
    
    def get_cache_key(self, source: str, version: str) -> str:
        """Generate cache key for source and version."""
        # Normalize source URL/path and create hash-based key
        normalized = source.lower().strip().rstrip('/')
        key_input = f"{normalized}#{version}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]
    
    def get(self, source: str, version: str) -> Optional[CacheEntry]:
        """Get cache entry if it exists and is valid."""
        cache_key = self.get_cache_key(source, version)
        entry = self.index.get(cache_key)
        
        if entry and Path(entry.local_path).exists():
            # Verify checksum
            if self._verify_checksum(entry.local_path, entry.checksum):
                return entry
            else:
                # Remove corrupted entry
                self.remove(source, version)
        
        return None
    
    def put(self, source: str, version: str, local_path: str, 
            checksum: str, metadata: Dict[str, Any] = None) -> CacheEntry:
        """Add entry to cache."""
        cache_key = self.get_cache_key(source, version)
        entry = CacheEntry(
            source=source,
            version=version,
            checksum=checksum,
            download_time=datetime.now(),
            local_path=local_path,
            metadata=metadata or {}
        )
        
        self.index[cache_key] = entry
        self._save_index()
        return entry
    
    def remove(self, source: str, version: str):
        """Remove entry from cache."""
        cache_key = self.get_cache_key(source, version)
        if cache_key in self.index:
            entry = self.index[cache_key]
            # Remove local files
            try:
                if Path(entry.local_path).exists():
                    if Path(entry.local_path).is_dir():
                        shutil.rmtree(entry.local_path)
                    else:
                        Path(entry.local_path).unlink()
            except Exception:
                pass  # Ignore file removal errors
            
            del self.index[cache_key]
            self._save_index()
    
    def cleanup_expired(self, max_age_hours: int = 24):
        """Remove expired cache entries."""
        expired_keys = []
        for key, entry in self.index.items():
            if entry.is_expired(max_age_hours):
                expired_keys.append(key)
        
        for key in expired_keys:
            entry = self.index[key]
            self.remove(entry.source, entry.version)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = 0
        for entry in self.index.values():
            try:
                if Path(entry.local_path).exists():
                    if Path(entry.local_path).is_dir():
                        total_size += sum(f.stat().st_size for f in Path(entry.local_path).rglob('*') if f.is_file())
                    else:
                        total_size += Path(entry.local_path).stat().st_size
            except Exception:
                pass
        
        return {
            "total_entries": len(self.index),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
            "entries": [
                {
                    "source": entry.source,
                    "version": entry.version,
                    "download_time": entry.download_time.isoformat(),
                    "path": entry.local_path
                }
                for entry in self.index.values()
            ]
        }
    
    def clear(self):
        """Clear entire cache."""
        try:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.index = {}
            self._save_index()
        except Exception as e:
            raise ResolutionError(f"Failed to clear cache: {e}")
    
    def _verify_checksum(self, file_path: str, expected_checksum: str) -> bool:
        """Verify file/directory checksum."""
        try:
            actual_checksum = self._calculate_checksum(file_path)
            return actual_checksum == expected_checksum
        except Exception:
            return False
    
    def _calculate_checksum(self, path: str) -> str:
        """Calculate checksum for file or directory."""
        path_obj = Path(path)
        if path_obj.is_file():
            return self._file_checksum(path)
        elif path_obj.is_dir():
            return self._directory_checksum(path)
        else:
            raise ValueError(f"Path does not exist: {path}")
    
    def _file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _directory_checksum(self, dir_path: str) -> str:
        """Calculate collective checksum of directory contents."""
        sha256_hash = hashlib.sha256()
        
        # Sort files for consistent hash
        for file_path in sorted(Path(dir_path).rglob('*')):
            if file_path.is_file():
                # Include relative path in hash
                rel_path = file_path.relative_to(dir_path)
                sha256_hash.update(str(rel_path).encode())
                
                # Include file content
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()


# =============================================================================
# Version Management
# =============================================================================

class VersionManager:
    """Handles version constraint parsing and resolution."""
    
    @staticmethod
    def parse_constraint(constraint_str: str) -> VersionConstraint:
        """Parse version constraint string (e.g., '>=1.0.0', '~>2.1.0')."""
        constraint_str = constraint_str.strip()
        
        # Pattern matching for different operators
        patterns = [
            (r'^>=(.+)$', '>='),
            (r'^<=(.+)$', '<='),
            (r'^==(.+)$', '=='),
            (r'^~>(.+)$', '~>'),
            (r'^\^(.+)$', '^'),
            (r'^>(.+)$', '>'),
            (r'^<(.+)$', '<'),
            (r'^(.+)$', '=='),  # Default to exact match
        ]
        
        for pattern, operator in patterns:
            match = re.match(pattern, constraint_str)
            if match:
                version = match.group(1).strip()
                return VersionConstraint(operator=operator, version=version)
        
        raise ValueError(f"Invalid version constraint: {constraint_str}")
    
    @staticmethod
    def satisfies_constraint(version: str, constraint: VersionConstraint) -> bool:
        """Check if version satisfies constraint."""
        try:
            # Handle special case for local versions
            if version == "local" or constraint.version == "local":
                return version == constraint.version
            
            return VersionManager._compare_versions(version, constraint.version, constraint.operator)
        except Exception:
            return False
    
    @staticmethod
    def _compare_versions(version1: str, version2: str, operator: str) -> bool:
        """Compare two semantic versions."""
        def parse_version(v: str) -> Tuple[int, int, int]:
            """Parse semantic version string."""
            parts = v.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch)
        
        v1 = parse_version(version1)
        v2 = parse_version(version2)
        
        if operator == '==':
            return v1 == v2
        elif operator == '>=':
            return v1 >= v2
        elif operator == '<=':
            return v1 <= v2
        elif operator == '>':
            return v1 > v2
        elif operator == '<':
            return v1 < v2
        elif operator == '~>':
            # Pessimistic version constraint (compatible within minor version)
            return v1[0] == v2[0] and v1[1] == v2[1] and v1[2] >= v2[2]
        elif operator == '^':
            # Caret constraint (compatible within major version)
            return v1[0] == v2[0] and v1 >= v2
        else:
            return False
    
    @staticmethod
    def resolve_best_version(available_versions: List[str], constraint: str = None) -> str:
        """Resolve best version from available versions given constraint."""
        if not available_versions:
            raise ValueError("No versions available")
        
        # Handle special case for local versions
        if constraint == "local" and "local" in available_versions:
            return "local"
        
        if not constraint:
            # Return latest version (assume sorted)
            return max(available_versions, key=lambda v: VersionManager._version_sort_key(v))
        
        constraint_obj = VersionManager.parse_constraint(constraint)
        compatible_versions = [
            v for v in available_versions 
            if VersionManager.satisfies_constraint(v, constraint_obj)
        ]
        
        if not compatible_versions:
            # For local constraint, if no exact match but local available, use it
            if constraint == "local" and available_versions:
                return available_versions[0]
            raise ValueError(f"No compatible versions found for constraint '{constraint}'")
        
        # Return latest compatible version
        return max(compatible_versions, key=lambda v: VersionManager._version_sort_key(v))
    
    @staticmethod
    def _version_sort_key(version: str) -> Tuple[int, int, int]:
        """Generate sort key for version comparison."""
        try:
            parts = version.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except (ValueError, IndexError):
            # For non-semantic versions, fall back to string comparison
            return (0, 0, 0)


# =============================================================================
# Source Resolvers
# =============================================================================

class SourceResolver(ABC):
    """Abstract base class for source resolvers."""
    
    @abstractmethod
    def can_resolve(self, source: str) -> bool:
        """Check if this resolver can handle the given source."""
        pass
    
    @abstractmethod
    def list_versions(self, source: str) -> List[str]:
        """List available versions for the source."""
        pass
    
    @abstractmethod
    def download(self, source: str, version: str, destination: str) -> str:
        """Download source to destination and return path."""
        pass
    
    @abstractmethod
    def get_metadata(self, source: str, version: str = None) -> Dict[str, Any]:
        """Get metadata for the source."""
        pass


class GitResolver(SourceResolver):
    """Resolver for Git repositories."""
    
    def can_resolve(self, source: str) -> bool:
        """Check if source is a Git repository."""
        git_patterns = [
            r'^https?://github\.com/',
            r'^https?://gitlab\.com/',
            r'^https?://bitbucket\.org/',
            r'^git@',
            r'\.git$'
        ]
        return any(re.match(pattern, source, re.IGNORECASE) for pattern in git_patterns)
    
    def list_versions(self, source: str) -> List[str]:
        """List Git tags as versions."""
        try:
            # Use git ls-remote to list tags
            cmd = ['git', 'ls-remote', '--tags', source]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise ResolutionError(f"Failed to list Git tags: {result.stderr}")
            
            versions = []
            for line in result.stdout.strip().split('\n'):
                if line and 'refs/tags/' in line:
                    tag = line.split('refs/tags/')[-1]
                    # Filter out annotated tag references (^{})
                    if not tag.endswith('^{}'):
                        versions.append(tag)
            
            return sorted(versions, key=VersionManager._version_sort_key, reverse=True)
            
        except subprocess.TimeoutExpired:
            raise ResolutionError(f"Timeout listing versions for Git repository: {source}")
        except Exception as e:
            raise ResolutionError(f"Failed to list Git versions: {e}")
    
    def download(self, source: str, version: str, destination: str) -> str:
        """Clone Git repository at specific version."""
        try:
            dest_path = Path(destination)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Clone with specific tag/branch
            cmd = [
                'git', 'clone', 
                '--depth', '1', 
                '--branch', version,
                source, 
                str(dest_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise ResolutionError(f"Failed to clone Git repository: {result.stderr}")
            
            # Remove .git directory to save space
            git_dir = dest_path / '.git'
            if git_dir.exists():
                shutil.rmtree(git_dir)
            
            return str(dest_path)
            
        except subprocess.TimeoutExpired:
            raise ResolutionError(f"Timeout downloading Git repository: {source}")
        except Exception as e:
            raise ResolutionError(f"Failed to download Git repository: {e}")
    
    def get_metadata(self, source: str, version: str = None) -> Dict[str, Any]:
        """Get Git repository metadata."""
        return {
            "type": "git",
            "source": source,
            "version": version,
            "fetched_at": datetime.now().isoformat()
        }


class LocalResolver(SourceResolver):
    """Resolver for local file system paths."""
    
    def can_resolve(self, source: str) -> bool:
        """Check if source is a local path."""
        return (
            source.startswith('./') or 
            source.startswith('../') or 
            source.startswith('/') or
            source.startswith('file://')
        )
    
    def list_versions(self, source: str) -> List[str]:
        """Local sources only have 'local' version."""
        return ["local"]
    
    def download(self, source: str, version: str, destination: str) -> str:
        """Copy local source to destination."""
        try:
            # Handle file:// URLs
            if source.startswith('file://'):
                source = source[7:]
            
            source_path = Path(source).resolve()
            dest_path = Path(destination)
            
            if not source_path.exists():
                raise ResolutionError(f"Local source does not exist: {source_path}")
            
            dest_path.mkdir(parents=True, exist_ok=True)
            
            if source_path.is_file():
                shutil.copy2(source_path, dest_path / source_path.name)
                return str(dest_path / source_path.name)
            elif source_path.is_dir():
                shutil.copytree(source_path, dest_path / source_path.name, dirs_exist_ok=True)
                return str(dest_path / source_path.name)
            else:
                raise ResolutionError(f"Invalid local source: {source_path}")
            
        except Exception as e:
            raise ResolutionError(f"Failed to copy local source: {e}")
    
    def get_metadata(self, source: str, version: str = None) -> Dict[str, Any]:
        """Get local source metadata."""
        source_path = Path(source)
        return {
            "type": "local",
            "source": str(source_path.resolve()),
            "version": version or "local",
            "exists": source_path.exists(),
            "is_file": source_path.is_file() if source_path.exists() else None,
            "is_dir": source_path.is_dir() if source_path.exists() else None
        }


class RegistryResolver(SourceResolver):
    """Resolver for module registries (HTTP-based)."""
    
    def can_resolve(self, source: str) -> bool:
        """Check if source is a registry URL."""
        return (
            source.startswith('http://') or 
            source.startswith('https://') or
            '/' in source and not self._is_git_like(source)
        )
    
    def _is_git_like(self, source: str) -> bool:
        """Check if source looks like a Git URL."""
        git_indicators = ['github.com', 'gitlab.com', 'bitbucket.org', '.git']
        return any(indicator in source.lower() for indicator in git_indicators)
    
    def list_versions(self, source: str) -> List[str]:
        """List versions from registry API."""
        try:
            # Try different registry API patterns
            api_urls = [
                f"{source}/versions",
                f"{source}/api/versions",
                f"{source}.json"
            ]
            
            for api_url in api_urls:
                try:
                    response = self._http_request(api_url)
                    data = json.loads(response)
                    
                    # Handle different response formats
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        if 'versions' in data:
                            return data['versions']
                        elif 'tags' in data:
                            return data['tags']
                        elif 'releases' in data:
                            return [r.get('version', r.get('tag_name', str(i))) 
                                   for i, r in enumerate(data['releases'])]
                    
                except Exception:
                    continue
            
            # Default to single version if API not available
            return ["latest"]
            
        except Exception as e:
            raise ResolutionError(f"Failed to list registry versions: {e}")
    
    def download(self, source: str, version: str, destination: str) -> str:
        """Download from registry."""
        try:
            dest_path = Path(destination)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Try different download URL patterns
            download_urls = [
                f"{source}/download/{version}",
                f"{source}/releases/{version}/download",
                f"{source}/{version}.tar.gz",
                f"{source}/{version}.zip",
                source  # Direct download
            ]
            
            for download_url in download_urls:
                try:
                    content = self._http_request(download_url, return_bytes=True)
                    
                    # Determine if it's an archive
                    if download_url.endswith('.tar.gz') or self._is_tarball(content):
                        return self._extract_tarball(content, dest_path)
                    elif download_url.endswith('.zip') or self._is_zip(content):
                        return self._extract_zip(content, dest_path)
                    else:
                        # Save as single file
                        filename = Path(download_url).name or "module_content"
                        file_path = dest_path / filename
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        return str(file_path)
                        
                except Exception:
                    continue
            
            raise ResolutionError(f"Failed to download from any URL pattern")
            
        except Exception as e:
            raise ResolutionError(f"Failed to download from registry: {e}")
    
    def get_metadata(self, source: str, version: str = None) -> Dict[str, Any]:
        """Get registry metadata."""
        try:
            metadata_urls = [
                f"{source}/metadata",
                f"{source}/info",
                f"{source}.json"
            ]
            
            for url in metadata_urls:
                try:
                    response = self._http_request(url)
                    data = json.loads(response)
                    data.update({
                        "type": "registry",
                        "source": source,
                        "version": version,
                        "fetched_at": datetime.now().isoformat()
                    })
                    return data
                except Exception:
                    continue
            
            # Default metadata
            return {
                "type": "registry",
                "source": source,
                "version": version,
                "fetched_at": datetime.now().isoformat()
            }
            
        except Exception:
            return {
                "type": "registry",
                "source": source,
                "version": version,
                "error": "Failed to fetch metadata"
            }
    
    def _http_request(self, url: str, return_bytes: bool = False) -> Union[str, bytes]:
        """Make HTTP request with timeout and user agent."""
        try:
            req = Request(url)
            req.add_header('User-Agent', 'Clockwork-Resolver/1.0')
            
            with urlopen(req, timeout=30) as response:
                content = response.read()
                return content if return_bytes else content.decode('utf-8')
                
        except Exception as e:
            raise ResolutionError(f"HTTP request failed for {url}: {e}")
    
    def _is_tarball(self, content: bytes) -> bool:
        """Check if content is a tarball."""
        return content.startswith(b'\x1f\x8b') or content.startswith(b'BZh')
    
    def _is_zip(self, content: bytes) -> bool:
        """Check if content is a ZIP file."""
        return content.startswith(b'PK\x03\x04')
    
    def _extract_tarball(self, content: bytes, dest_path: Path) -> str:
        """Extract tarball content."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            
            with tarfile.open(tmp_file.name, 'r:*') as tar:
                tar.extractall(dest_path)
            
            return str(dest_path)
    
    def _extract_zip(self, content: bytes, dest_path: Path) -> str:
        """Extract ZIP content."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            
            with zipfile.ZipFile(tmp_file.name, 'r') as zip_file:
                zip_file.extractall(dest_path)
            
            return str(dest_path)


# =============================================================================
# Core Resolvers
# =============================================================================

class ModuleResolver:
    """Resolves module sources with version pinning and caching."""
    
    def __init__(self, cache_manager: CacheManager = None):
        """Initialize module resolver."""
        self.cache_manager = cache_manager or CacheManager()
        self.source_resolvers = [
            GitResolver(),
            LocalResolver(),
            RegistryResolver()
        ]
    
    def resolve(self, module: Module) -> ResolutionResult:
        """Resolve a module and return resolution result."""
        try:
            # Check cache first
            cache_entry = self.cache_manager.get(module.source, module.version or "latest")
            if cache_entry and not cache_entry.is_expired():
                return ResolutionResult(
                    name=module.name,
                    source=module.source,
                    resolved_version=cache_entry.version,
                    local_path=cache_entry.local_path,
                    checksum=cache_entry.checksum,
                    metadata=cache_entry.metadata,
                    cached=True
                )
            
            # Find appropriate resolver
            resolver = self._get_resolver(module.source)
            if not resolver:
                raise ResolutionError(f"No resolver found for module source: {module.source}")
            
            # List available versions
            available_versions = resolver.list_versions(module.source)
            if not available_versions:
                raise ResolutionError(f"No versions found for module: {module.name}")
            
            # Resolve version
            resolved_version = VersionManager.resolve_best_version(
                available_versions, 
                module.version
            )
            
            # Download to temporary location
            temp_dir = tempfile.mkdtemp(prefix=f"clockwork_module_{module.name}_")
            try:
                local_path = resolver.download(module.source, resolved_version, temp_dir)
                
                # Calculate checksum
                checksum = self.cache_manager._calculate_checksum(local_path)
                
                # Get metadata
                metadata = resolver.get_metadata(module.source, resolved_version)
                
                # Move to cache
                cache_dir = self.cache_manager.cache_dir / "modules" / module.name / resolved_version
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                if Path(local_path).is_file():
                    final_path = cache_dir / Path(local_path).name
                    shutil.move(local_path, final_path)
                else:
                    final_path = cache_dir / "content"
                    if final_path.exists():
                        shutil.rmtree(final_path)
                    shutil.move(local_path, final_path)
                
                # Update cache
                self.cache_manager.put(
                    module.source, 
                    resolved_version, 
                    str(final_path), 
                    checksum, 
                    metadata
                )
                
                return ResolutionResult(
                    name=module.name,
                    source=module.source,
                    resolved_version=resolved_version,
                    local_path=str(final_path),
                    checksum=checksum,
                    metadata=metadata,
                    cached=False
                )
                
            finally:
                # Clean up temp directory
                if Path(temp_dir).exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        except Exception as e:
            if isinstance(e, ResolutionError):
                raise
            else:
                raise ResolutionError(f"Failed to resolve module '{module.name}': {e}")
    
    def _get_resolver(self, source: str) -> Optional[SourceResolver]:
        """Get appropriate source resolver for the given source."""
        for resolver in self.source_resolvers:
            if resolver.can_resolve(source):
                return resolver
        return None
    
    def resolve_dependencies(self, modules: Dict[str, Module]) -> List[ResolutionResult]:
        """Resolve multiple modules and their dependencies."""
        results = []
        resolved = set()
        
        def resolve_recursive(module_name: str, module: Module):
            if module_name in resolved:
                return
            
            # Resolve current module
            result = self.resolve(module)
            results.append(result)
            resolved.add(module_name)
            
            # Check for dependencies in module metadata
            dependencies = result.metadata.get('dependencies', [])
            for dep_name in dependencies:
                if dep_name in modules and dep_name not in resolved:
                    resolve_recursive(dep_name, modules[dep_name])
        
        # Resolve all modules
        for name, module in modules.items():
            resolve_recursive(name, module)
        
        return results


class ProviderResolver:
    """Resolves provider sources with version compatibility checking."""
    
    def __init__(self, cache_manager: CacheManager = None):
        """Initialize provider resolver."""
        self.cache_manager = cache_manager or CacheManager()
        self.source_resolvers = [
            GitResolver(),
            LocalResolver(),
            RegistryResolver()
        ]
    
    def resolve(self, provider: Provider) -> ResolutionResult:
        """Resolve a provider and return resolution result."""
        try:
            # Check cache first
            cache_entry = self.cache_manager.get(provider.source, provider.version or "latest")
            if cache_entry and not cache_entry.is_expired():
                # Verify compatibility
                if self._check_compatibility(provider, cache_entry.metadata):
                    return ResolutionResult(
                        name=provider.name,
                        source=provider.source,
                        resolved_version=cache_entry.version,
                        local_path=cache_entry.local_path,
                        checksum=cache_entry.checksum,
                        metadata=cache_entry.metadata,
                        cached=True
                    )
            
            # Find appropriate resolver
            resolver = self._get_resolver(provider.source)
            if not resolver:
                raise ResolutionError(f"No resolver found for provider source: {provider.source}")
            
            # List available versions
            available_versions = resolver.list_versions(provider.source)
            if not available_versions:
                raise ResolutionError(f"No versions found for provider: {provider.name}")
            
            # Resolve version with compatibility checking
            resolved_version = self._resolve_compatible_version(
                provider, available_versions, resolver
            )
            
            # Download to temporary location
            temp_dir = tempfile.mkdtemp(prefix=f"clockwork_provider_{provider.name}_")
            try:
                local_path = resolver.download(provider.source, resolved_version, temp_dir)
                
                # Calculate checksum
                checksum = self.cache_manager._calculate_checksum(local_path)
                
                # Get metadata and validate compatibility
                metadata = resolver.get_metadata(provider.source, resolved_version)
                if not self._check_compatibility(provider, metadata):
                    raise ResolutionError(f"Provider version {resolved_version} is not compatible")
                
                # Move to cache
                cache_dir = self.cache_manager.cache_dir / "providers" / provider.name / resolved_version
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                if Path(local_path).is_file():
                    final_path = cache_dir / Path(local_path).name
                    shutil.move(local_path, final_path)
                else:
                    final_path = cache_dir / "content"
                    if final_path.exists():
                        shutil.rmtree(final_path)
                    shutil.move(local_path, final_path)
                
                # Update cache
                self.cache_manager.put(
                    provider.source, 
                    resolved_version, 
                    str(final_path), 
                    checksum, 
                    metadata
                )
                
                return ResolutionResult(
                    name=provider.name,
                    source=provider.source,
                    resolved_version=resolved_version,
                    local_path=str(final_path),
                    checksum=checksum,
                    metadata=metadata,
                    cached=False
                )
                
            finally:
                # Clean up temp directory
                if Path(temp_dir).exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        except Exception as e:
            if isinstance(e, ResolutionError):
                raise
            else:
                raise ResolutionError(f"Failed to resolve provider '{provider.name}': {e}")
    
    def _get_resolver(self, source: str) -> Optional[SourceResolver]:
        """Get appropriate source resolver for the given source."""
        for resolver in self.source_resolvers:
            if resolver.can_resolve(source):
                return resolver
        return None
    
    def _resolve_compatible_version(self, provider: Provider, 
                                   available_versions: List[str], 
                                   resolver: SourceResolver) -> str:
        """Resolve version with compatibility checking."""
        if not provider.version:
            # Find latest compatible version
            for version in sorted(available_versions, key=VersionManager._version_sort_key, reverse=True):
                metadata = resolver.get_metadata(provider.source, version)
                if self._check_compatibility(provider, metadata):
                    return version
            # If no compatible version found, return latest
            return max(available_versions, key=VersionManager._version_sort_key)
        else:
            # Use version manager to resolve specific version
            return VersionManager.resolve_best_version(available_versions, provider.version)
    
    def _check_compatibility(self, provider: Provider, metadata: Dict[str, Any]) -> bool:
        """Check if provider version is compatible with requirements."""
        # Basic compatibility checks
        
        # Check if required configuration keys are supported
        required_config = set(provider.config.keys())
        supported_config = set(metadata.get('supported_config', []))
        
        if required_config and supported_config:
            unsupported = required_config - supported_config
            if unsupported:
                return False
        
        # Check minimum version requirements
        min_version = metadata.get('min_clockwork_version')
        if min_version:
            # For now, assume compatible (could check against current Clockwork version)
            pass
        
        return True
    
    def validate_config(self, provider: Provider, resolved_metadata: Dict[str, Any]) -> bool:
        """Validate provider configuration against schema."""
        try:
            config_schema = resolved_metadata.get('config_schema', {})
            if not config_schema:
                return True  # No schema to validate against
            
            # Basic validation (could be enhanced with jsonschema)
            required_fields = config_schema.get('required', [])
            for field in required_fields:
                if field not in provider.config:
                    raise ResolutionError(f"Required configuration field '{field}' missing for provider '{provider.name}'")
            
            # Type validation
            properties = config_schema.get('properties', {})
            for field, value in provider.config.items():
                if field in properties:
                    expected_type = properties[field].get('type')
                    if expected_type == 'string' and not isinstance(value, str):
                        raise ResolutionError(f"Configuration field '{field}' must be a string")
                    elif expected_type == 'number' and not isinstance(value, (int, float)):
                        raise ResolutionError(f"Configuration field '{field}' must be a number")
                    elif expected_type == 'boolean' and not isinstance(value, bool):
                        raise ResolutionError(f"Configuration field '{field}' must be a boolean")
            
            return True
            
        except Exception as e:
            if isinstance(e, ResolutionError):
                raise
            else:
                raise ResolutionError(f"Configuration validation failed: {e}")


# =============================================================================
# Main Resolver Class
# =============================================================================

class Resolver:
    """Main resolver class that coordinates module and provider resolution."""
    
    def __init__(self, cache_dir: str = ".clockwork/cache"):
        """Initialize resolver with cache manager."""
        self.cache_manager = CacheManager(cache_dir)
        self.module_resolver = ModuleResolver(self.cache_manager)
        self.provider_resolver = ProviderResolver(self.cache_manager)
    
    def resolve_ir(self, ir: IR) -> Dict[str, Any]:
        """Resolve all modules and providers in an IR and return resolution results."""
        try:
            results = {
                "modules": {},
                "providers": {},
                "resolved_at": datetime.now().isoformat(),
                "cache_stats": self.cache_manager.get_stats()
            }
            
            # Resolve modules
            if ir.modules:
                module_results = self.module_resolver.resolve_dependencies(ir.modules)
                for result in module_results:
                    results["modules"][result.name] = result.model_dump()
            
            # Resolve providers
            for provider in ir.providers:
                provider_result = self.provider_resolver.resolve(provider)
                results["providers"][provider.name] = provider_result.model_dump()
                
                # Validate provider configuration
                self.provider_resolver.validate_config(provider, provider_result.metadata)
            
            return results
            
        except Exception as e:
            if isinstance(e, ResolutionError):
                raise
            else:
                raise ResolutionError(f"Failed to resolve IR: {e}")
    
    def cleanup_cache(self, max_age_hours: int = 24):
        """Clean up expired cache entries."""
        self.cache_manager.cleanup_expired(max_age_hours)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_stats()
    
    def clear_cache(self):
        """Clear entire cache."""
        self.cache_manager.clear()


# =============================================================================
# Integration with Parser
# =============================================================================

def resolve_references(ir: IR, resolver: Resolver = None) -> IR:
    """Resolve module and provider references in an IR."""
    if resolver is None:
        resolver = Resolver()
    
    try:
        # Resolve all references
        resolution_results = resolver.resolve_ir(ir)
        
        # Update IR metadata with resolution information
        ir.metadata.update({
            "resolution_completed": True,
            "resolution_timestamp": datetime.now().isoformat(),
            "resolved_modules": list(resolution_results["modules"].keys()),
            "resolved_providers": list(resolution_results["providers"].keys()),
            "cache_stats": resolution_results["cache_stats"]
        })
        
        # Store resolution results in metadata for later use
        ir.metadata["resolution_results"] = resolution_results
        
        return ir
        
    except Exception as e:
        # Add resolution error to metadata but don't fail the IR
        ir.metadata.update({
            "resolution_completed": False,
            "resolution_error": str(e),
            "resolution_timestamp": datetime.now().isoformat()
        })
        
        # Re-raise for caller to handle
        raise ResolutionError(f"Failed to resolve references: {e}")


# Export main classes
__all__ = [
    'Resolver', 'ModuleResolver', 'ProviderResolver', 'CacheManager',
    'ResolutionError', 'ResolutionResult', 'resolve_references',
    'VersionManager', 'VersionConstraint'
]