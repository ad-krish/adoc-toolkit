"""Immutable blockchain-based audit logging system for ADOC toolkit.

This module provides a functional programming implementation of blockchain-based
audit logging with immutable data structures and pure functions.
"""

# Core functional implementation
from .core import (
    Block,
    BlockHeader,
    BlockData,
    BlockchainState,
    create_block_header,
    create_block_data,
    create_block,
    calculate_merkle_root,
    mine_block,
    mine_block_with_merkle_root,
    create_log_entry,
    should_commit_batch,
    commit_batch,
    add_log_entry,
    get_log_entries,
    verify_blockchain_integrity,
    get_blockchain_info,
    create_genesis_block,
    initialize_blockchain_state,
    map_blocks,
    filter_blocks,
    reduce_blocks,
    compose_functions,
    calculate_blockchain_stats,
)

# Functional storage
from .storage import (
    FunctionalStorage,
    create_storage_connection,
    initialize_storage_schema,
    save_block_pure,
    load_blocks_pure,
    get_block_by_hash_pure,
    clear_blocks_pure,
    get_block_count_pure,
    load_blockchain_state_from_storage,
    save_blockchain_state_to_storage,
    commit_pending_batch_pure,
    with_storage_transaction,
    map_storage_blocks,
    filter_storage_blocks,
    reduce_storage_blocks,
)

# Functional logger interface
from .logger import (
    FunctionalLogger,
    create_logger,
    log_entry_pure,
    commit_batch_pure,
    get_logs_pure,
    map_logger_operations,
    filter_logger_entries,
    compose_logger_operations,
    create_operation_logger,
    create_http_request_logger,
)

__all__ = [
    # Core functional types
    "Block",
    "BlockHeader", 
    "BlockData",
    "BlockchainState",
    
    # Core functional functions
    "create_block_header",
    "create_block_data",
    "create_block",
    "calculate_merkle_root",
    "mine_block",
    "mine_block_with_merkle_root",
    "create_log_entry",
    "should_commit_batch",
    "commit_batch",
    "add_log_entry",
    "get_log_entries",
    "verify_blockchain_integrity",
    "get_blockchain_info",
    "create_genesis_block",
    "initialize_blockchain_state",
    
    # Higher-order functions
    "map_blocks",
    "filter_blocks",
    "reduce_blocks",
    "compose_functions",
    "calculate_blockchain_stats",
    
    # Functional storage
    "FunctionalStorage",
    "create_storage_connection",
    "initialize_storage_schema",
    "save_block_pure",
    "load_blocks_pure",
    "get_block_by_hash_pure",
    "clear_blocks_pure",
    "get_block_count_pure",
    "load_blockchain_state_from_storage",
    "save_blockchain_state_to_storage",
    "commit_pending_batch_pure",
    "with_storage_transaction",
    "map_storage_blocks",
    "filter_storage_blocks",
    "reduce_storage_blocks",
    
    # Functional logger
    "FunctionalLogger",
    "create_logger",
    "log_entry_pure",
    "commit_batch_pure",
    "get_logs_pure",
    "map_logger_operations",
    "filter_logger_entries",
    "compose_logger_operations",
    "create_operation_logger",
    "create_http_request_logger",
] 