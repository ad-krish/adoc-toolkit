"""
Functional logger interface for immutable audit logging.

This module provides a clean functional API for the immutable blockchain
implementation, making it easy to use in a functional programming style.
"""

import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from functools import partial
from .core import (
    BlockchainState, Block, create_log_entry, add_log_entry,
    get_log_entries, verify_blockchain_integrity, get_blockchain_info,
    initialize_blockchain_state, commit_batch, calculate_blockchain_stats
)
from .storage import FunctionalStorage, load_blockchain_state_from_storage


# =============================================================================
# Functional Logger Interface
# =============================================================================

class FunctionalLogger:
    """Functional logger interface for immutable audit logging."""
    
    def __init__(
        self,
        storage: FunctionalStorage,
        batch_size: int = 100,
        batch_timeout: float = 120.0
    ):
        self.storage = storage
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._state = load_blockchain_state_from_storage(
            storage, batch_size, batch_timeout
        )
    
    def log_entry(
        self,
        operation: str,
        user_id: str,
        resource: str,
        action: str,
        details: Dict[str, Any],
        metadata: Dict[str, Any] = None,
        difficulty: int = None,
        force_commit: bool = False
    ) -> Tuple['FunctionalLogger', Optional[Block]]:
        """Add a log entry and return new logger state."""
        new_state, block = add_log_entry(
            self._state,
            operation=operation,
            user_id=user_id,
            resource=resource,
            action=action,
            details=details,
            metadata=metadata,
            difficulty=difficulty,
            force_commit=force_commit
        )
        
        # Create new logger with updated state
        new_logger = FunctionalLogger.__new__(FunctionalLogger)
        new_logger.storage = self.storage
        new_logger.batch_size = self.batch_size
        new_logger.batch_timeout = self.batch_timeout
        new_logger._state = new_state
        
        return new_logger, block
    
    def commit_pending_batch(self, difficulty: int = None) -> Tuple['FunctionalLogger', Optional[Block]]:
        """Commit pending batch and return new logger state."""
        new_state, block = commit_batch(self._state, difficulty)
        
        # Save block to storage if created
        if block:
            self.storage.save_block(block)
        
        # Create new logger with updated state
        new_logger = FunctionalLogger.__new__(FunctionalLogger)
        new_logger.storage = self.storage
        new_logger.batch_size = self.batch_size
        new_logger.batch_timeout = self.batch_timeout
        new_logger._state = new_state
        
        return new_logger, block
    
    def get_logs(
        self,
        user_id: str = None,
        operation: str = None,
        resource: str = None,
        action: str = None,
        start_time: float = None,
        end_time: float = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get filtered log entries."""
        entries = get_log_entries(
            self._state,
            user_id=user_id,
            operation=operation,
            resource=resource,
            action=action,
            start_time=start_time,
            end_time=end_time
        )
        
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def get_info(self) -> Dict[str, Any]:
        """Get blockchain information."""
        return get_blockchain_info(self._state)
    
    def verify_integrity(self) -> bool:
        """Verify blockchain integrity."""
        return verify_blockchain_integrity(self._state)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get blockchain statistics."""
        return calculate_blockchain_stats(self._state)
    
    def get_pending_count(self) -> int:
        """Get number of pending entries in current batch."""
        return len(self._state.current_batch)
    
    def get_total_blocks(self) -> int:
        """Get total number of blocks."""
        return len(self._state.blocks)
    
    def get_total_entries(self) -> int:
        """Get total number of log entries."""
        return sum(len(block.data.log_entries) for block in self._state.blocks)


# =============================================================================
# Pure Function Wrappers
# =============================================================================

def create_logger(
    db_path: str = "blockchain_audit.db",
    batch_size: int = 100,
    batch_timeout: float = 120.0
) -> FunctionalLogger:
    """Create a new functional logger."""
    storage = FunctionalStorage(db_path)
    return FunctionalLogger(storage, batch_size, batch_timeout)


def log_entry_pure(
    logger: FunctionalLogger,
    operation: str,
    user_id: str,
    resource: str,
    action: str,
    details: Dict[str, Any],
    metadata: Dict[str, Any] = None,
    difficulty: int = None,
    force_commit: bool = False
) -> Tuple[FunctionalLogger, Optional[Block]]:
    """Pure function to add a log entry."""
    return logger.log_entry(
        operation=operation,
        user_id=user_id,
        resource=resource,
        action=action,
        details=details,
        metadata=metadata,
        difficulty=difficulty,
        force_commit=force_commit
    )


def commit_batch_pure(
    logger: FunctionalLogger,
    difficulty: int = None
) -> Tuple[FunctionalLogger, Optional[Block]]:
    """Pure function to commit pending batch."""
    return logger.commit_pending_batch(difficulty)


def get_logs_pure(
    logger: FunctionalLogger,
    user_id: str = None,
    operation: str = None,
    resource: str = None,
    action: str = None,
    start_time: float = None,
    end_time: float = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """Pure function to get filtered logs."""
    return logger.get_logs(
        user_id=user_id,
        operation=operation,
        resource=resource,
        action=action,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )


# =============================================================================
# Higher-Order Functions for Logger Operations
# =============================================================================

def with_logger_operation(
    logger: FunctionalLogger,
    operation: Callable[[FunctionalLogger], Tuple[FunctionalLogger, Any]]
) -> Tuple[FunctionalLogger, Any]:
    """Execute an operation on a logger and return new state."""
    return operation(logger)


def map_logger_operations(
    logger: FunctionalLogger,
    operations: List[Callable[[FunctionalLogger], Tuple[FunctionalLogger, Any]]]
) -> Tuple[FunctionalLogger, List[Any]]:
    """Apply multiple operations to a logger sequentially."""
    current_logger = logger
    results = []
    
    for operation in operations:
        current_logger, result = operation(current_logger)
        results.append(result)
    
    return current_logger, results


def filter_logger_entries(
    logger: FunctionalLogger,
    predicate: Callable[[Dict[str, Any]], bool]
) -> List[Dict[str, Any]]:
    """Filter log entries using a predicate."""
    all_entries = logger.get_logs()
    return [entry for entry in all_entries if predicate(entry)]


def reduce_logger_entries(
    logger: FunctionalLogger,
    func: Callable[[Any, Dict[str, Any]], Any],
    initial: Any
) -> Any:
    """Reduce log entries using a function."""
    entries = logger.get_logs()
    return reduce(func, entries, initial)


# =============================================================================
# Functional Composition Utilities
# =============================================================================

def compose_logger_operations(*operations: Callable) -> Callable:
    """Compose multiple logger operations."""
    def composed(logger: FunctionalLogger) -> Tuple[FunctionalLogger, Any]:
        current_logger = logger
        result = None
        
        for operation in operations:
            current_logger, result = operation(current_logger)
        
        return current_logger, result
    
    return composed


def create_log_entry_operation(
    operation: str,
    user_id: str,
    resource: str,
    action: str,
    details: Dict[str, Any],
    metadata: Dict[str, Any] = None,
    difficulty: int = None,
    force_commit: bool = False
) -> Callable[[FunctionalLogger], Tuple[FunctionalLogger, Optional[Block]]]:
    """Create a logger operation for adding a log entry."""
    return partial(
        log_entry_pure,
        operation=operation,
        user_id=user_id,
        resource=resource,
        action=action,
        details=details,
        metadata=metadata,
        difficulty=difficulty,
        force_commit=force_commit
    )


def create_commit_batch_operation(
    difficulty: int = None
) -> Callable[[FunctionalLogger], Tuple[FunctionalLogger, Optional[Block]]]:
    """Create a logger operation for committing pending batch."""
    return partial(commit_batch_pure, difficulty=difficulty)


# =============================================================================
# Utility Functions
# =============================================================================

def create_operation_logger(
    operation: str,
    user_id: str,
    resource: str,
    action: str = "EXECUTE"
) -> Callable[[FunctionalLogger, Dict[str, Any]], Tuple[FunctionalLogger, Optional[Block]]]:
    """Create a specialized logger for operations."""
    def operation_logger(logger: FunctionalLogger, details: Dict[str, Any]) -> Tuple[FunctionalLogger, Optional[Block]]:
        return logger.log_entry(
            operation=operation,
            user_id=user_id,
            resource=resource,
            action=action,
            details=details
        )
    return operation_logger


def create_http_request_logger(
    method: str,
    url: str,
    user_id: str,
    status_code: int = None
) -> Callable[[FunctionalLogger, Dict[str, Any]], Tuple[FunctionalLogger, Optional[Block]]]:
    """Create a specialized logger for HTTP requests."""
    def http_logger(logger: FunctionalLogger, details: Dict[str, Any]) -> Tuple[FunctionalLogger, Optional[Block]]:
        metadata = {
            "method": method,
            "url": url,
            "status_code": status_code
        }
        return logger.log_entry(
            operation="HTTP_REQUEST",
            user_id=user_id,
            resource=url,
            action=method,
            details=details,
            metadata=metadata
        )
    return http_logger 