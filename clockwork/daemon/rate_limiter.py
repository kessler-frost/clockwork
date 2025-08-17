"""
Rate Limiter and Cooldown Manager for Clockwork Daemon.

This module implements rate limiting and cooldown mechanisms to ensure safe
auto-fix operations as specified in the README (≤2 auto-fixes/hour/task).
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List


logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter implementing sliding window rate limiting.
    
    Ensures that no more than max_operations occur within the time window,
    as specified in the README (≤2 auto-fixes/hour/task).
    """
    
    def __init__(self, max_operations: int, time_window_hours: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_operations: Maximum operations allowed in time window
            time_window_hours: Time window in hours (default 1.0)
        """
        self.max_operations = max_operations
        self.time_window_seconds = time_window_hours * 3600
        self.operations: deque = deque()
        self.lock = threading.Lock()
        
        logger.info(f"RateLimiter initialized: {max_operations} operations per {time_window_hours} hours")
    
    def can_perform_operation(self) -> bool:
        """
        Check if an operation can be performed without exceeding rate limit.
        
        Returns:
            True if operation is allowed, False if rate limited
        """
        with self.lock:
            self._cleanup_old_operations()
            return len(self.operations) < self.max_operations
    
    def record_operation(self) -> bool:
        """
        Record an operation if rate limit allows.
        
        Returns:
            True if operation was recorded, False if rate limited
        """
        with self.lock:
            self._cleanup_old_operations()
            
            if len(self.operations) >= self.max_operations:
                logger.warning(f"Rate limit exceeded: {len(self.operations)}/{self.max_operations} operations")
                return False
            
            current_time = time.time()
            self.operations.append(current_time)
            logger.debug(f"Operation recorded: {len(self.operations)}/{self.max_operations} operations")
            return True
    
    def get_remaining_operations(self) -> int:
        """Get number of operations remaining before rate limit."""
        with self.lock:
            self._cleanup_old_operations()
            return max(0, self.max_operations - len(self.operations))
    
    def get_reset_time(self) -> Optional[datetime]:
        """Get time when rate limit will reset (oldest operation expires)."""
        with self.lock:
            if not self.operations:
                return None
            
            oldest_operation = self.operations[0]
            reset_time = oldest_operation + self.time_window_seconds
            return datetime.fromtimestamp(reset_time)
    
    def get_statistics(self) -> dict:
        """Get rate limiter statistics."""
        with self.lock:
            self._cleanup_old_operations()
            
            return {
                "max_operations": self.max_operations,
                "time_window_hours": self.time_window_seconds / 3600,
                "current_operations": len(self.operations),
                "remaining_operations": self.get_remaining_operations(),
                "reset_time": self.get_reset_time().isoformat() if self.get_reset_time() else None,
                "operations_timestamps": [
                    datetime.fromtimestamp(ts).isoformat() 
                    for ts in list(self.operations)
                ]
            }
    
    def reset(self) -> None:
        """Reset the rate limiter (clear all recorded operations)."""
        with self.lock:
            self.operations.clear()
            logger.info("Rate limiter reset")
    
    def _cleanup_old_operations(self) -> None:
        """Remove operations outside the time window."""
        current_time = time.time()
        cutoff_time = current_time - self.time_window_seconds
        
        # Remove operations older than the time window
        while self.operations and self.operations[0] < cutoff_time:
            self.operations.popleft()


class CooldownManager:
    """
    Cooldown manager to enforce cooldown periods after operations.
    
    Implements the README requirement for cooldown after each fix.
    """
    
    def __init__(self, cooldown_minutes: int):
        """
        Initialize cooldown manager.
        
        Args:
            cooldown_minutes: Cooldown period in minutes
        """
        self.cooldown_seconds = cooldown_minutes * 60
        self.last_operation_time: Optional[float] = None
        self.lock = threading.Lock()
        
        logger.info(f"CooldownManager initialized: {cooldown_minutes} minute cooldown")
    
    def start_cooldown(self) -> None:
        """Start a cooldown period from now."""
        with self.lock:
            self.last_operation_time = time.time()
            logger.info(f"Cooldown started for {self.cooldown_seconds / 60} minutes")
    
    def in_cooldown(self) -> bool:
        """Check if currently in cooldown period."""
        with self.lock:
            if self.last_operation_time is None:
                return False
            
            elapsed = time.time() - self.last_operation_time
            return elapsed < self.cooldown_seconds
    
    def get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds."""
        with self.lock:
            if self.last_operation_time is None:
                return 0.0
            
            elapsed = time.time() - self.last_operation_time
            remaining = self.cooldown_seconds - elapsed
            return max(0.0, remaining)
    
    def get_cooldown_end(self) -> Optional[datetime]:
        """Get datetime when cooldown will end."""
        with self.lock:
            if self.last_operation_time is None:
                return None
            
            if not self.in_cooldown():
                return None
            
            end_time = self.last_operation_time + self.cooldown_seconds
            return datetime.fromtimestamp(end_time)
    
    def reset_cooldown(self) -> None:
        """Reset cooldown (clear last operation time)."""
        with self.lock:
            self.last_operation_time = None
            logger.info("Cooldown reset")
    
    def get_statistics(self) -> dict:
        """Get cooldown manager statistics."""
        with self.lock:
            return {
                "cooldown_minutes": self.cooldown_seconds / 60,
                "in_cooldown": self.in_cooldown(),
                "cooldown_remaining_seconds": self.get_cooldown_remaining(),
                "cooldown_end": self.get_cooldown_end().isoformat() if self.get_cooldown_end() else None,
                "last_operation": datetime.fromtimestamp(self.last_operation_time).isoformat() if self.last_operation_time else None
            }


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting and cooldowns."""
    
    # Rate limiting
    max_fixes_per_hour: int = 2
    rate_limit_window_hours: float = 1.0
    
    # Cooldown
    cooldown_minutes: int = 10
    
    # Safety limits
    max_consecutive_failures: int = 3
    emergency_stop_threshold: int = 10  # Total failures before emergency stop
    
    def validate(self) -> List[str]:
        """Validate configuration parameters."""
        issues = []
        
        if self.max_fixes_per_hour < 1:
            issues.append("max_fixes_per_hour must be at least 1")
        
        if self.rate_limit_window_hours <= 0:
            issues.append("rate_limit_window_hours must be positive")
        
        if self.cooldown_minutes < 0:
            issues.append("cooldown_minutes cannot be negative")
        
        if self.max_consecutive_failures < 1:
            issues.append("max_consecutive_failures must be at least 1")
        
        return issues


class SafetyController:
    """
    Combined safety controller managing rate limiting, cooldowns, and emergency stops.
    
    Implements all the safety mechanisms specified in the README.
    """
    
    def __init__(self, config: RateLimitConfig):
        """Initialize safety controller."""
        self.config = config
        
        # Validate configuration
        issues = config.validate()
        if issues:
            raise ValueError(f"Invalid safety configuration: {'; '.join(issues)}")
        
        # Initialize components
        self.rate_limiter = RateLimiter(
            max_operations=config.max_fixes_per_hour,
            time_window_hours=config.rate_limit_window_hours
        )
        self.cooldown_manager = CooldownManager(config.cooldown_minutes)
        
        # Failure tracking
        self.consecutive_failures = 0
        self.total_failures = 0
        self.emergency_stop = False
        self.lock = threading.Lock()
        
        logger.info("SafetyController initialized")
    
    def can_perform_fix(self) -> tuple[bool, str]:
        """
        Check if a fix operation can be performed.
        
        Returns:
            Tuple of (can_perform, reason)
        """
        with self.lock:
            # Check emergency stop
            if self.emergency_stop:
                return False, "Emergency stop activated"
            
            # Check total failure threshold
            if self.total_failures >= self.config.emergency_stop_threshold:
                self.emergency_stop = True
                logger.critical(f"Emergency stop: {self.total_failures} total failures exceeded threshold")
                return False, f"Too many failures ({self.total_failures}), emergency stop activated"
            
            # Check consecutive failures
            if self.consecutive_failures >= self.config.max_consecutive_failures:
                return False, f"Too many consecutive failures ({self.consecutive_failures})"
            
            # Check cooldown
            if self.cooldown_manager.in_cooldown():
                remaining = self.cooldown_manager.get_cooldown_remaining()
                return False, f"In cooldown for {remaining:.1f} more seconds"
            
            # Check rate limit
            if not self.rate_limiter.can_perform_operation():
                reset_time = self.rate_limiter.get_reset_time()
                return False, f"Rate limit exceeded, resets at {reset_time}"
            
            return True, "OK"
    
    def record_fix_attempt(self, success: bool) -> None:
        """Record the result of a fix attempt."""
        with self.lock:
            if success:
                # Record successful operation
                self.rate_limiter.record_operation()
                self.cooldown_manager.start_cooldown()
                self.consecutive_failures = 0  # Reset consecutive failure count
                logger.info("Fix attempt succeeded, cooldown started")
            else:
                # Record failure
                self.consecutive_failures += 1
                self.total_failures += 1
                logger.warning(f"Fix attempt failed: {self.consecutive_failures} consecutive, {self.total_failures} total")
    
    def reset_emergency_stop(self) -> None:
        """Reset emergency stop (requires manual intervention)."""
        with self.lock:
            self.emergency_stop = False
            self.consecutive_failures = 0
            self.total_failures = 0
            logger.warning("Emergency stop reset - manual intervention")
    
    def get_status(self) -> dict:
        """Get comprehensive safety controller status."""
        with self.lock:
            can_perform, reason = self.can_perform_fix()
            
            return {
                "can_perform_fix": can_perform,
                "status_reason": reason,
                "emergency_stop": self.emergency_stop,
                "consecutive_failures": self.consecutive_failures,
                "total_failures": self.total_failures,
                "rate_limiter": self.rate_limiter.get_statistics(),
                "cooldown": self.cooldown_manager.get_statistics(),
                "config": {
                    "max_fixes_per_hour": self.config.max_fixes_per_hour,
                    "cooldown_minutes": self.config.cooldown_minutes,
                    "max_consecutive_failures": self.config.max_consecutive_failures,
                    "emergency_stop_threshold": self.config.emergency_stop_threshold
                }
            }


# =============================================================================
# Utility Functions
# =============================================================================

def create_default_safety_config() -> RateLimitConfig:
    """Create default safety configuration matching README specs."""
    return RateLimitConfig(
        max_fixes_per_hour=2,  # README: ≤2 auto-fixes/hour/task
        cooldown_minutes=10    # README: cooldown after each fix
    )


def create_conservative_safety_config() -> RateLimitConfig:
    """Create conservative safety configuration."""
    return RateLimitConfig(
        max_fixes_per_hour=1,
        cooldown_minutes=30,
        max_consecutive_failures=2,
        emergency_stop_threshold=5
    )


def create_test_safety_config() -> RateLimitConfig:
    """Create safety configuration suitable for testing."""
    return RateLimitConfig(
        max_fixes_per_hour=10,
        rate_limit_window_hours=0.1,  # 6 minutes
        cooldown_minutes=1,
        max_consecutive_failures=5,
        emergency_stop_threshold=20
    )