"""
Functional programming implementation of immutable audit logging.

This module provides a pure functional approach to blockchain-based audit logging
with immutable data structures and pure functions.
"""

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from functools import reduce
from operator import add


# =============================================================================
# Pure Data Structures (Immutable)
# =============================================================================

@dataclass(frozen=True)
class BlockHeader:
    """Immutable block header containing metadata and cryptographic information."""
    
    version: str = "1.0"
    timestamp: float = None
    previous_hash: str = ""
    merkle_root: str = ""
    nonce: int = 0
    difficulty: int = 4
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', time.time())
    
    def with_nonce(self, nonce: int) -> 'BlockHeader':
        """Create a new header with updated nonce."""
        return replace(self, nonce=nonce)
    
    def with_merkle_root(self, merkle_root: str) -> 'BlockHeader':
        """Create a new header with updated merkle root."""
        return replace(self, merkle_root=merkle_root)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert header to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
        }
    
    def to_json(self) -> str:
        """Convert header to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True)
class BlockData:
    """Immutable data payload for a blockchain block."""
    
    log_entries: Tuple[Dict[str, Any], ...] = None
    log_entry_id: str = None
    metadata: Tuple[Tuple[str, Any], ...] = None
    
    def __post_init__(self):
        if self.log_entries is None:
            object.__setattr__(self, 'log_entries', ())
        if self.metadata is None:
            object.__setattr__(self, 'metadata', ())
        if self.log_entry_id is None:
            object.__setattr__(self, 'log_entry_id', str(uuid.uuid4()))
    
    def add_log_entry(self, entry: Dict[str, Any]) -> 'BlockData':
        """Create a new BlockData with an additional log entry."""
        new_entries = self.log_entries + (entry,)
        return replace(self, log_entries=new_entries)
    
    def get_entry_count(self) -> int:
        """Get the number of log entries in this block."""
        return len(self.log_entries)
    
    def get_metadata_dict(self) -> Dict[str, Any]:
        """Convert metadata tuple to dictionary."""
        return dict(self.metadata)
    
    def with_metadata(self, key: str, value: Any) -> 'BlockData':
        """Create a new BlockData with additional metadata."""
        new_metadata = self.metadata + ((key, value),)
        return replace(self, metadata=new_metadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert data to dictionary."""
        return {
            "log_entry_id": self.log_entry_id,
            "log_entries": list(self.log_entries),
            "metadata": self.get_metadata_dict(),
        }
    
    def to_json(self) -> str:
        """Convert data to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True)
class Block:
    """Immutable block in the blockchain."""
    
    header: BlockHeader
    data: BlockData
    hash_value: str = None
    
    def __post_init__(self):
        # Don't calculate hash here - it will be calculated dynamically
        pass
    
    @property
    def hash(self) -> str:
        """Calculate and return the block hash dynamically."""
        content = self.header.to_json() + self.data.to_json()
        return hashlib.sha256(content.encode()).hexdigest()
    
    def with_mined_header(self, mined_header: BlockHeader) -> 'Block':
        """Create a new block with a mined header."""
        return replace(self, header=mined_header)
    
    def verify(self) -> bool:
        """Verify the block's hash meets difficulty requirements."""
        return self.hash.startswith('0' * self.header.difficulty)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary."""
        return {
            "header": self.header.to_dict(),
            "data": self.data.to_dict(),
            "hash": self.hash
        }
    
    def to_json(self) -> str:
        """Convert block to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True)
class BlockchainState:
    """Immutable blockchain state."""
    
    blocks: Tuple[Block, ...] = None
    current_batch: Tuple[Dict[str, Any], ...] = None
    batch_start_time: float = None
    batch_size: int = 100
    batch_timeout: float = 120.0
    
    def __post_init__(self):
        if self.blocks is None:
            object.__setattr__(self, 'blocks', ())
        if self.current_batch is None:
            object.__setattr__(self, 'current_batch', ())
        if self.batch_start_time is None:
            object.__setattr__(self, 'batch_start_time', time.time())
    
    def with_block(self, block: Block) -> 'BlockchainState':
        """Create a new state with an additional block."""
        new_blocks = self.blocks + (block,)
        return replace(self, blocks=new_blocks)
    
    def with_batch_entry(self, entry: Dict[str, Any]) -> 'BlockchainState':
        """Create a new state with an additional batch entry."""
        new_batch = self.current_batch + (entry,)
        return replace(self, current_batch=new_batch)
    
    def with_cleared_batch(self) -> 'BlockchainState':
        """Create a new state with cleared batch."""
        return replace(
            self,
            current_batch=(),
            batch_start_time=time.time()
        )


# =============================================================================
# Pure Functions
# =============================================================================

def create_block_header(
    previous_hash: str = "",
    difficulty: int = 4,
    timestamp: float = None
) -> BlockHeader:
    """Create a new block header."""
    return BlockHeader(
        previous_hash=previous_hash,
        difficulty=difficulty,
        timestamp=timestamp
    )


def create_block_data(
    log_entries: List[Dict[str, Any]] = None,
    metadata: Dict[str, Any] = None
) -> BlockData:
    """Create new block data."""
    entries_tuple = tuple(log_entries or ())
    metadata_tuple = tuple((k, v) for k, v in (metadata or {}).items())
    return BlockData(log_entries=entries_tuple, metadata=metadata_tuple)


def create_block(
    header: BlockHeader,
    data: BlockData
) -> Block:
    """Create a new block."""
    return Block(header=header, data=data)


def calculate_merkle_root(entries: Tuple[Dict[str, Any], ...]) -> str:
    """Calculate merkle root from log entries."""
    if not entries:
        return ""
    
    # Create hashes of all entries
    entry_hashes = [
        hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        for entry in entries
    ]
    
    # Build merkle tree
    while len(entry_hashes) > 1:
        if len(entry_hashes) % 2 == 1:
            entry_hashes.append(entry_hashes[-1])
        
        new_level = []
        for i in range(0, len(entry_hashes), 2):
            combined = entry_hashes[i] + entry_hashes[i + 1]
            new_level.append(hashlib.sha256(combined.encode()).hexdigest())
        entry_hashes = new_level
    
    return entry_hashes[0] if entry_hashes else ""


def mine_block(block: Block, max_attempts: int = 1000000) -> Optional[Block]:
    """Mine a block by finding a valid nonce."""
    for nonce in range(max_attempts):
        new_header = block.header.with_nonce(nonce)
        new_block = block.with_mined_header(new_header)
        
        if new_block.verify():
            return new_block
    
    return None


def mine_block_with_merkle_root(block: Block, max_attempts: int = 1000000) -> Optional[Block]:
    """Mine a block with merkle root calculation."""
    # Calculate merkle root first
    merkle_root = calculate_merkle_root(block.data.log_entries)
    header_with_merkle = block.header.with_merkle_root(merkle_root)
    
    # Create new block with merkle root
    block_with_merkle = block.with_mined_header(header_with_merkle)
    
    # Mine the block
    return mine_block(block_with_merkle, max_attempts)


def create_log_entry(
    operation: str,
    user_id: str,
    resource: str,
    action: str,
    details: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create a new log entry."""
    return {
        "log_entry_id": str(uuid.uuid4()),
        "operation": operation,
        "user_id": user_id,
        "resource": resource,
        "action": action,
        "details": details,
        "metadata": metadata or {},
        "timestamp": time.time()
    }


def should_commit_batch(state: BlockchainState) -> bool:
    """Check if current batch should be committed."""
    batch_size_reached = len(state.current_batch) >= state.batch_size
    timeout_reached = (time.time() - state.batch_start_time) >= state.batch_timeout
    return batch_size_reached or timeout_reached


def commit_batch(
    state: BlockchainState,
    difficulty: int = None
) -> Tuple[BlockchainState, Optional[Block]]:
    """Commit current batch to a new block."""
    if not state.current_batch:
        return state, None
    
    # Create block data from batch
    data = create_block_data(
        log_entries=list(state.current_batch),
        metadata={"batch_size": len(state.current_batch)}
    )
    
    # Get previous hash
    previous_hash = state.blocks[-1].hash if state.blocks else "0" * 64
    
    # Create header
    header = create_block_header(
        previous_hash=previous_hash,
        difficulty=difficulty or state.blocks[0].header.difficulty if state.blocks else 4
    )
    
    # Create block
    block = create_block(header, data)
    
    # Mine block with merkle root
    mined_block = mine_block_with_merkle_root(block)
    if not mined_block:
        return state, None
    
    # Update state
    new_state = state.with_block(mined_block).with_cleared_batch()
    return new_state, mined_block


def add_log_entry(
    state: BlockchainState,
    operation: str,
    user_id: str,
    resource: str,
    action: str,
    details: Dict[str, Any],
    metadata: Dict[str, Any] = None,
    difficulty: int = None,
    force_commit: bool = False
) -> Tuple[BlockchainState, Optional[Block]]:
    """Add a log entry to the blockchain state."""
    # Create log entry
    entry = create_log_entry(
        operation=operation,
        user_id=user_id,
        resource=resource,
        action=action,
        details=details,
        metadata=metadata
    )
    
    # Add to batch
    new_state = state.with_batch_entry(entry)
    
    # Check if we should commit
    if force_commit or should_commit_batch(new_state):
        return commit_batch(new_state, difficulty)
    
    return new_state, None


def get_log_entries(
    state: BlockchainState,
    user_id: str = None,
    operation: str = None,
    resource: str = None,
    action: str = None,
    start_time: float = None,
    end_time: float = None
) -> List[Dict[str, Any]]:
    """Get filtered log entries from all blocks."""
    all_entries = []
    
    for block in state.blocks:
        for entry in block.data.log_entries:
            # Apply filters
            if user_id and entry.get("user_id") != user_id:
                continue
            if operation and entry.get("operation") != operation:
                continue
            if resource and entry.get("resource") != resource:
                continue
            if action and entry.get("action") != action:
                continue
            if start_time and entry.get("timestamp", 0) < start_time:
                continue
            if end_time and entry.get("timestamp", 0) > end_time:
                continue
            
            all_entries.append(entry)
    
    return sorted(all_entries, key=lambda x: x.get("timestamp", 0), reverse=True)


def verify_blockchain_integrity(state: BlockchainState) -> bool:
    """Verify the integrity of the entire blockchain."""
    if not state.blocks:
        return True
    
    # Check each block's hash
    for block in state.blocks:
        if not block.verify():
            return False
    
    # Check chain continuity
    for i in range(1, len(state.blocks)):
        current_block = state.blocks[i]
        previous_block = state.blocks[i - 1]
        
        if current_block.header.previous_hash != previous_block.hash:
            return False
    
    return True


def get_blockchain_info(state: BlockchainState) -> Dict[str, Any]:
    """Get information about the blockchain state."""
    total_entries = sum(len(block.data.log_entries) for block in state.blocks)
    pending_entries = len(state.current_batch)
    
    # Get the last block hash if blocks exist
    last_block_hash = ""
    if state.blocks:
        last_block = state.blocks[-1]  # Get the most recent block
        last_block_hash = last_block.hash
    
    return {
        "total_blocks": len(state.blocks),
        "total_entries": total_entries,
        "pending_entries": pending_entries,
        "last_block_hash": last_block_hash,
        "batch_size": state.batch_size,
        "batch_timeout": state.batch_timeout,
        "batch_start_time": state.batch_start_time,
        "integrity_verified": verify_blockchain_integrity(state)
    }


def create_genesis_block() -> Block:
    """Create the genesis block."""
    header = create_block_header(previous_hash="0" * 64, difficulty=4)
    data = create_block_data(
        metadata={"block_type": "genesis", "description": "Initial blockchain block"}
    )
    block = create_block(header, data)
    mined_block = mine_block(block)
    return mined_block or block


def initialize_blockchain_state(
    batch_size: int = 100,
    batch_timeout: float = 120.0
) -> BlockchainState:
    """Initialize a new blockchain state."""
    genesis = create_genesis_block()
    return BlockchainState(
        blocks=(genesis,),
        batch_size=batch_size,
        batch_timeout=batch_timeout
    )


# =============================================================================
# Higher-Order Functions for Composition
# =============================================================================

def map_blocks(state: BlockchainState, func: Callable[[Block], Any]) -> List[Any]:
    """Apply a function to all blocks in the state."""
    return [func(block) for block in state.blocks]


def filter_blocks(state: BlockchainState, predicate: Callable[[Block], bool]) -> List[Block]:
    """Filter blocks based on a predicate."""
    return [block for block in state.blocks if predicate(block)]


def reduce_blocks(
    state: BlockchainState,
    func: Callable[[Any, Block], Any],
    initial: Any
) -> Any:
    """Reduce blocks using a function."""
    return reduce(func, state.blocks, initial)


def compose_functions(*functions: Callable) -> Callable:
    """Compose multiple functions."""
    def composed(*args, **kwargs):
        result = functions[-1](*args, **kwargs)
        for func in reversed(functions[:-1]):
            result = func(result)
        return result
    return composed


# =============================================================================
# Utility Functions
# =============================================================================

def calculate_blockchain_stats(state: BlockchainState) -> Dict[str, Any]:
    """Calculate statistics for the blockchain."""
    all_entries = []
    for block in state.blocks:
        all_entries.extend(block.data.log_entries)
    
    if not all_entries:
        return {
            "total_entries": 0,
            "unique_operations": 0,
            "unique_users": 0,
            "unique_resources": 0,
            "time_range": (0, 0)
        }
    
    operations = set(entry.get("operation") for entry in all_entries)
    users = set(entry.get("user_id") for entry in all_entries)
    resources = set(entry.get("resource") for entry in all_entries)
    timestamps = [entry.get("timestamp", 0) for entry in all_entries]
    
    return {
        "total_entries": len(all_entries),
        "unique_operations": len(operations),
        "unique_users": len(users),
        "unique_resources": len(resources),
        "time_range": (min(timestamps), max(timestamps)) if timestamps else (0, 0)
    }


def export_blockchain_state(state: BlockchainState) -> Dict[str, Any]:
    """Export blockchain state to dictionary."""
    return {
        "blocks": [block.to_dict() for block in state.blocks],
        "current_batch": list(state.current_batch),
        "batch_start_time": state.batch_start_time,
        "batch_size": state.batch_size,
        "batch_timeout": state.batch_timeout
    }


def import_blockchain_state(data: Dict[str, Any]) -> BlockchainState:
    """Import blockchain state from dictionary."""
    # This would need to be implemented based on your serialization format
    # For now, return a new state
    return initialize_blockchain_state(
        batch_size=data.get("batch_size", 100),
        batch_timeout=data.get("batch_timeout", 120.0)
    ) 