# Immutable Log - Functional Implementation

A functional programming implementation of blockchain-based immutable audit logging for the ADOC toolkit.

## Overview

This module provides a pure functional approach to blockchain-based audit logging with immutable data structures, pure functions, and functional composition. It replaces the original object-oriented implementation with a more composable and testable design.

## Key Features

- **Immutable Data Structures** - All data structures use `@dataclass(frozen=True)`
- **Pure Functions** - No side effects, predictable behavior
- **Functional Composition** - Higher-order functions for combining operations
- **Batching Support** - Configurable batch size and timeout
- **Blockchain Integrity** - Cryptographic verification of log integrity
- **SQLite Storage** - Persistent storage with proper indexing
- **Type Safety** - Strong typing throughout

## Quick Start

```python
from adoc_toolkit.audit.immutable_log import create_logger, log_entry_pure

# Create a functional logger
logger = create_logger("audit.db", batch_size=100, batch_timeout=120.0)

# Add log entries using pure functions
logger, block = log_entry_pure(
    logger,
    operation="COMMAND",
    user_id="user1",
    resource="cli",
    action="EXECUTE",
    details={"command": "help"}
)

# Get logs
logs = logger.get_logs(user_id="user1")
```

## Core Components

### Functional Data Structures

```python
from adoc_toolkit.audit.immutable_log import Block, BlockHeader, BlockData, BlockchainState

# Immutable block header
header = BlockHeader(previous_hash="abc123", difficulty=4)

# Immutable block data
data = BlockData(log_entries=tuple([{"test": "data"}]))

# Immutable block
block = Block(header=header, data=data)
```

### Pure Functions

```python
from adoc_toolkit.audit.immutable_log import (
    create_log_entry, add_log_entry, commit_batch,
    get_log_entries, verify_blockchain_integrity
)

# Create log entry
entry = create_log_entry("TEST", "user1", "resource", "action", {"details": "data"})

# Add to blockchain state
new_state, block = add_log_entry(state, "TEST", "user1", "resource", "action", {"details": "data"})

# Commit pending batch
new_state, block = commit_batch(state, difficulty=4)
```

### Higher-Order Functions

```python
from adoc_toolkit.audit.immutable_log import map_blocks, filter_blocks, reduce_blocks

# Map over all blocks
hashes = map_blocks(state, lambda block: block.hash)

# Filter blocks
valid_blocks = filter_blocks(state, lambda block: block.verify())

# Reduce blocks
total_entries = reduce_blocks(state, lambda acc, block: acc + len(block.data.log_entries), 0)
```

### Functional Composition

```python
from adoc_toolkit.audit.immutable_log import compose_logger_operations, create_operation_logger

# Create specialized operations
command_logger = create_operation_logger("COMMAND", "user1", "cli")

# Compose operations
workflow = compose_logger_operations(
    lambda l: command_logger(l, {"command": "help"}),
    lambda l: command_logger(l, {"command": "show"}),
    lambda l: commit_batch_pure(l)
)

# Execute workflow
final_logger, result = workflow(logger)
```

## Storage

```python
from adoc_toolkit.audit.immutable_log import FunctionalStorage

# Create storage
storage = FunctionalStorage("audit.db")

# Load state from storage
state = load_blockchain_state_from_storage(storage, batch_size=100, batch_timeout=120.0)

# Save state to storage
success = save_blockchain_state_to_storage(state, storage)
```

## Configuration

The functional logger supports configurable batching:

```python
logger = create_logger(
    db_path="audit.db",
    batch_size=100,      # Number of entries per block
    batch_timeout=120.0  # Timeout in seconds
)
```

## Testing

All functions are pure and easily testable:

```python
def test_log_entry():
    state = initialize_blockchain_state(batch_size=2)
    
    new_state, block = add_log_entry(
        state,
        operation="TEST",
        user_id="user1",
        resource="test",
        action="EXECUTE",
        details={"test": "data"}
    )
    
    assert len(new_state.current_batch) == 1
    assert block is None  # No commit yet
```

## Architecture

```
core.py                   # Core functional implementation
storage.py                # Functional storage layer
logger.py                 # Functional logger interface
example.py                # Comprehensive examples
```

## Benefits

1. **Immutability** - No side effects, predictable behavior
2. **Composability** - Functions can be combined easily
3. **Testability** - Pure functions are easy to test
4. **Type Safety** - Strong typing throughout
5. **Performance** - Efficient immutable data structures
6. **Maintainability** - Clear separation of concerns 