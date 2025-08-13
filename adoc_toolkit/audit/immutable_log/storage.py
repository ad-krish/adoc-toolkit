"""
Functional storage layer for immutable blockchain data.

This module provides pure functional storage operations for the immutable
blockchain implementation.
"""

import sqlite3
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Callable
from pathlib import Path
from .core import Block, BlockHeader, BlockData, BlockchainState


# =============================================================================
# Pure Storage Functions
# =============================================================================

def create_storage_connection(db_path: str) -> sqlite3.Connection:
    """Create a database connection."""
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def initialize_storage_schema(conn: sqlite3.Connection) -> None:
    """Initialize the database schema."""
    cursor = conn.cursor()
    
    # Create blocks table with functional schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_hash TEXT UNIQUE NOT NULL,
            header_version TEXT NOT NULL,
            header_timestamp REAL NOT NULL,
            header_previous_hash TEXT NOT NULL,
            header_merkle_root TEXT NOT NULL,
            header_nonce INTEGER NOT NULL,
            header_difficulty INTEGER NOT NULL,
            data_log_entry_id TEXT NOT NULL,
            data_log_entries TEXT NOT NULL,
            data_metadata TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_block_hash ON blocks(block_hash)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON blocks(header_timestamp)
    """)
    
    conn.commit()


def save_block_pure(conn: sqlite3.Connection, block: Block) -> bool:
    """Save a block to storage (pure function)."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO blocks (
                block_hash,
                header_version,
                header_timestamp,
                header_previous_hash,
                header_merkle_root,
                header_nonce,
                header_difficulty,
                data_log_entry_id,
                data_log_entries,
                data_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            block.hash,  # Use dynamic hash property
            block.header.version,
            block.header.timestamp,
            block.header.previous_hash,
            block.header.merkle_root,
            block.header.nonce,
            block.header.difficulty,
            block.data.log_entry_id,
            json.dumps(list(block.data.log_entries)),
            json.dumps(block.data.get_metadata_dict())
        ))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Block already exists
        return False
    except Exception:
        return False


def load_blocks_pure(conn: sqlite3.Connection) -> List[Block]:
    """Load all blocks from storage (pure function)."""
    blocks = []
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                block_hash,
                header_version,
                header_timestamp,
                header_previous_hash,
                header_merkle_root,
                header_nonce,
                header_difficulty,
                data_log_entry_id,
                data_log_entries,
                data_metadata
            FROM blocks
            ORDER BY id ASC
        """)
        
        for row in cursor.fetchall():
            # Reconstruct block header
            header = BlockHeader(
                version=row[1],
                timestamp=row[2],
                previous_hash=row[3],
                merkle_root=row[4],
                nonce=row[5],
                difficulty=row[6]
            )
            
            # Reconstruct block data
            log_entries = tuple(json.loads(row[8]))
            metadata_dict = json.loads(row[9])
            metadata_tuple = tuple((k, v) for k, v in metadata_dict.items())
            
            data = BlockData(
                log_entry_id=row[7],
                log_entries=log_entries,
                metadata=metadata_tuple
            )
            
            # Create block
            block = Block(header=header, data=data)  # Remove hash_value parameter
            blocks.append(block)
    
    except Exception:
        pass
    
    return blocks


def get_block_by_hash_pure(conn: sqlite3.Connection, block_hash: str) -> Optional[Block]:
    """Get a specific block by its hash (pure function)."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                block_hash,
                header_version,
                header_timestamp,
                header_previous_hash,
                header_merkle_root,
                header_nonce,
                header_difficulty,
                data_log_entry_id,
                data_log_entries,
                data_metadata
            FROM blocks
            WHERE block_hash = ?
        """, (block_hash,))
        
        row = cursor.fetchone()
        if row:
            # Reconstruct block header
            header = BlockHeader(
                version=row[1],
                timestamp=row[2],
                previous_hash=row[3],
                merkle_root=row[4],
                nonce=row[5],
                difficulty=row[6]
            )
            
            # Reconstruct block data
            log_entries = tuple(json.loads(row[8]))
            metadata_dict = json.loads(row[9])
            metadata_tuple = tuple((k, v) for k, v in metadata_dict.items())
            
            data = BlockData(
                log_entry_id=row[7],
                log_entries=log_entries,
                metadata=metadata_tuple
            )
            
            # Create block
            return Block(header=header, data=data)  # Remove hash_value parameter
    
    except Exception:
        pass
    
    return None


def clear_blocks_pure(conn: sqlite3.Connection) -> bool:
    """Clear all blocks from storage (pure function)."""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blocks")
        conn.commit()
        return True
    except Exception:
        return False


def get_block_count_pure(conn: sqlite3.Connection) -> int:
    """Get the total number of blocks in storage (pure function)."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM blocks")
        return cursor.fetchone()[0]
    except Exception:
        return 0


# =============================================================================
# Functional Storage Interface
# =============================================================================

class FunctionalStorage:
    """Functional storage interface for blockchain data."""
    
    def __init__(self, db_path: str = "blockchain_audit.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database."""
        with create_storage_connection(self.db_path) as conn:
            initialize_storage_schema(conn)
    
    def save_block(self, block: Block) -> bool:
        """Save a block to storage."""
        with create_storage_connection(self.db_path) as conn:
            return save_block_pure(conn, block)
    
    def load_blocks(self) -> List[Block]:
        """Load all blocks from storage."""
        with create_storage_connection(self.db_path) as conn:
            return load_blocks_pure(conn)
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get a specific block by its hash."""
        with create_storage_connection(self.db_path) as conn:
            return get_block_by_hash_pure(conn, block_hash)
    
    def clear_blocks(self) -> bool:
        """Clear all blocks from storage."""
        with create_storage_connection(self.db_path) as conn:
            return clear_blocks_pure(conn)
    
    def get_block_count(self) -> int:
        """Get the total number of blocks in storage."""
        with create_storage_connection(self.db_path) as conn:
            return get_block_count_pure(conn)


# =============================================================================
# Functional State Management
# =============================================================================

def load_blockchain_state_from_storage(
    storage: FunctionalStorage,
    batch_size: int = 100,
    batch_timeout: float = 120.0
) -> BlockchainState:
    """Load blockchain state from storage."""
    blocks = storage.load_blocks()
    
    if not blocks:
        # Create genesis block if no blocks exist
        from .core import create_genesis_block, initialize_blockchain_state
        genesis = create_genesis_block()
        return initialize_blockchain_state(batch_size, batch_timeout)
    
    return BlockchainState(
        blocks=tuple(blocks),
        batch_size=batch_size,
        batch_timeout=batch_timeout
    )


def save_blockchain_state_to_storage(
    state: BlockchainState,
    storage: FunctionalStorage
) -> bool:
    """Save blockchain state to storage."""
    # Only save committed blocks, not pending batch
    success = True
    for block in state.blocks:
        if not storage.save_block(block):
            success = False
    return success


def commit_pending_batch_pure(
    state: BlockchainState,
    storage: FunctionalStorage,
    difficulty: int = None
) -> Tuple[BlockchainState, Optional[Block]]:
    """Commit pending batch to storage."""
    from .core import commit_batch
    
    new_state, block = commit_batch(state, difficulty)
    
    if block:
        # Save the new block to storage
        storage.save_block(block)
    
    return new_state, block


# =============================================================================
# Higher-Order Storage Functions
# =============================================================================

def with_storage_transaction(
    storage: FunctionalStorage,
    operation: Callable[[sqlite3.Connection], Any]
) -> Any:
    """Execute an operation within a storage transaction."""
    with create_storage_connection(storage.db_path) as conn:
        return operation(conn)


def map_storage_blocks(
    storage: FunctionalStorage,
    func: Callable[[Block], Any]
) -> List[Any]:
    """Apply a function to all blocks in storage."""
    blocks = storage.load_blocks()
    return [func(block) for block in blocks]


def filter_storage_blocks(
    storage: FunctionalStorage,
    predicate: Callable[[Block], bool]
) -> List[Block]:
    """Filter blocks in storage based on a predicate."""
    blocks = storage.load_blocks()
    return [block for block in blocks if predicate(block)]


def reduce_storage_blocks(
    storage: FunctionalStorage,
    func: Callable[[Any, Block], Any],
    initial: Any
) -> Any:
    """Reduce blocks in storage using a function."""
    blocks = storage.load_blocks()
    return reduce(func, blocks, initial) 