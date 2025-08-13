"""
Tests for functional immutable_log implementation.

This module tests the functional programming approach to immutable
blockchain-based audit logging.
"""

import pytest
import tempfile
import os
import time
from typing import Dict, Any

from adoc_toolkit.audit.immutable_log.core import (
    BlockHeader, BlockData, Block, BlockchainState,
    create_block_header, create_block_data, create_block,
    calculate_merkle_root, mine_block, create_log_entry,
    should_commit_batch, commit_batch, add_log_entry,
    get_log_entries, verify_blockchain_integrity,
    get_blockchain_info, create_genesis_block,
    initialize_blockchain_state, map_blocks, filter_blocks,
    reduce_blocks, compose_functions, calculate_blockchain_stats
)

from adoc_toolkit.audit.immutable_log.storage import (
    FunctionalStorage, create_storage_connection,
    initialize_storage_schema, save_block_pure, load_blocks_pure,
    get_block_by_hash_pure, clear_blocks_pure, get_block_count_pure
)

from adoc_toolkit.audit.immutable_log.logger import (
    FunctionalLogger, create_logger, log_entry_pure,
    commit_batch_pure, get_logs_pure, map_logger_operations,
    filter_logger_entries, compose_logger_operations
)


class TestFunctionalDataStructures:
    """Test immutable data structures."""
    
    def test_block_header_creation(self):
        """Test BlockHeader creation and immutability."""
        header = create_block_header(previous_hash="abc123", difficulty=4)
        
        assert header.previous_hash == "abc123"
        assert header.difficulty == 4
        assert header.timestamp is not None
        
        # Test immutability
        with pytest.raises(Exception):
            header.previous_hash = "def456"
    
    def test_block_data_creation(self):
        """Test BlockData creation and immutability."""
        log_entries = [
            {"operation": "test", "user_id": "user1", "timestamp": time.time()}
        ]
        
        data = create_block_data(log_entries=log_entries)
        
        assert len(data.log_entries) == 1
        assert data.log_entries[0]["operation"] == "test"
        assert data.log_entry_id is not None
        
        # Test immutability
        with pytest.raises(Exception):
            data.log_entries = []
    
    def test_block_creation(self):
        """Test Block creation and verification."""
        header = create_block_header(difficulty=1)  # Low difficulty for testing
        data = create_block_data(log_entries=[{"test": "data"}])
        
        block = create_block(header, data)
        
        assert block.header == header
        assert block.data == data
        assert block.hash is not None
        assert len(block.hash) == 64
        
        # Test mining
        mined_block = mine_block(block)
        assert mined_block is not None
        assert mined_block.verify() is True
    
    def test_blockchain_state_creation(self):
        """Test BlockchainState creation and immutability."""
        state = initialize_blockchain_state(batch_size=50, batch_timeout=60.0)
        
        assert len(state.blocks) == 1  # Genesis block
        assert state.batch_size == 50
        assert state.batch_timeout == 60.0
        assert len(state.current_batch) == 0
        
        # Test immutability
        with pytest.raises(Exception):
            state.blocks = []


class TestFunctionalPureFunctions:
    """Test pure functions."""
    
    def test_calculate_merkle_root(self):
        """Test merkle root calculation."""
        entries = [
            {"operation": "test1", "timestamp": time.time()},
            {"operation": "test2", "timestamp": time.time()},
        ]
        
        merkle_root = calculate_merkle_root(tuple(entries))
        assert merkle_root is not None
        assert len(merkle_root) == 64  # SHA256 hash length
    
    def test_create_log_entry(self):
        """Test log entry creation."""
        entry = create_log_entry(
            operation="TEST",
            user_id="user1",
            resource="test",
            action="EXECUTE",
            details={"key": "value"},
            metadata={"meta": "data"}
        )
        
        assert entry["operation"] == "TEST"
        assert entry["user_id"] == "user1"
        assert entry["log_entry_id"] is not None
        assert entry["timestamp"] is not None
    
    def test_should_commit_batch(self):
        """Test batch commit decision logic."""
        # Test size-based commit
        state = BlockchainState(
            current_batch=tuple([{"test": i} for i in range(100)]),
            batch_size=100,
            batch_timeout=120.0
        )
        assert should_commit_batch(state) is True
        
        # Test timeout-based commit
        state = BlockchainState(
            current_batch=tuple([{"test": 1}]),
            batch_size=100,
            batch_timeout=120.0,
            batch_start_time=time.time() - 130.0  # Past timeout
        )
        assert should_commit_batch(state) is True
        
        # Test no commit needed
        state = BlockchainState(
            current_batch=tuple([{"test": 1}]),
            batch_size=100,
            batch_timeout=120.0,
            batch_start_time=time.time()
        )
        assert should_commit_batch(state) is False
    
    def test_commit_batch(self):
        """Test batch commitment."""
        state = BlockchainState(
            current_batch=tuple([
                {"operation": "test1", "user_id": "user1"},
                {"operation": "test2", "user_id": "user2"}
            ]),
            batch_size=2,
            batch_timeout=120.0
        )
        
        new_state, block = commit_batch(state, difficulty=1)
        
        assert block is not None
        assert len(block.data.log_entries) == 2
        assert len(new_state.current_batch) == 0
        assert len(new_state.blocks) == 1
    
    def test_add_log_entry(self):
        """Test adding log entries."""
        state = initialize_blockchain_state(batch_size=2, batch_timeout=60.0)
        
        # Add first entry (no commit)
        new_state, block = add_log_entry(
            state,
            operation="TEST1",
            user_id="user1",
            resource="test",
            action="EXECUTE",
            details={"test": 1}
        )
        
        assert block is None
        assert len(new_state.current_batch) == 1
        
        # Add second entry (should commit)
        final_state, block = add_log_entry(
            new_state,
            operation="TEST2",
            user_id="user2",
            resource="test",
            action="EXECUTE",
            details={"test": 2}
        )
        
        assert block is not None
        assert len(final_state.current_batch) == 0
        assert len(final_state.blocks) == 2  # Genesis block + new block
    
    def test_get_log_entries(self):
        """Test log entry retrieval with filtering."""
        state = BlockchainState(
            blocks=tuple([
                Block(
                    header=create_block_header(),
                    data=create_block_data(log_entries=[
                        {"operation": "TEST1", "user_id": "user1", "timestamp": 100},
                        {"operation": "TEST2", "user_id": "user2", "timestamp": 200},
                    ])
                )
            ])
        )
        
        # Test filtering by user
        user1_logs = get_log_entries(state, user_id="user1")
        assert len(user1_logs) == 1
        assert user1_logs[0]["user_id"] == "user1"
        
        # Test filtering by operation
        test1_logs = get_log_entries(state, operation="TEST1")
        assert len(test1_logs) == 1
        assert test1_logs[0]["operation"] == "TEST1"
    
    def test_verify_blockchain_integrity(self):
        """Test blockchain integrity verification."""
        # Create valid chain
        genesis = create_genesis_block()
        header = create_block_header(previous_hash=genesis.hash)
        data = create_block_data(log_entries=[{"test": "data"}])
        block = create_block(header, data)
        mined_block = mine_block(block)
        
        state = BlockchainState(blocks=tuple([genesis, mined_block]))
        assert verify_blockchain_integrity(state) is True
        
        # Test invalid chain
        invalid_state = BlockchainState(blocks=tuple([genesis, block]))  # Unmined block
        assert verify_blockchain_integrity(invalid_state) is False


class TestFunctionalStorage:
    """Test functional storage operations."""
    
    def test_storage_operations(self):
        """Test basic storage operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Test connection and schema
            conn = create_storage_connection(db_path)
            initialize_storage_schema(conn)
            conn.close()
            
            # Test block save and load
            block = create_genesis_block()
            
            with create_storage_connection(db_path) as conn:
                success = save_block_pure(conn, block)
                assert success is True
                
                loaded_blocks = load_blocks_pure(conn)
                assert len(loaded_blocks) == 1
                assert loaded_blocks[0].hash == block.hash
                
                # Test get by hash
                retrieved_block = get_block_by_hash_pure(conn, block.hash)
                assert retrieved_block is not None
                assert retrieved_block.hash == block.hash
                
                # Test block count
                count = get_block_count_pure(conn)
                assert count == 1
                
                # Test clear
                success = clear_blocks_pure(conn)
                assert success is True
                assert get_block_count_pure(conn) == 0
        
        finally:
            os.unlink(db_path)


class TestFunctionalLogger:
    """Test functional logger interface."""
    
    def test_logger_creation(self):
        """Test logger creation and basic operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            logger = create_logger(db_path, batch_size=2, batch_timeout=60.0)
            
            assert logger.get_total_blocks() == 1  # Genesis block
            assert logger.get_pending_count() == 0
            assert logger.verify_integrity() is True
        
        finally:
            os.unlink(db_path)
    
    def test_logger_operations(self):
        """Test logger operations with pure functions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            logger = create_logger(db_path, batch_size=2, batch_timeout=60.0)
            
            # Add log entries
            logger, block1 = log_entry_pure(
                logger,
                operation="TEST1",
                user_id="user1",
                resource="test",
                action="EXECUTE",
                details={"test": 1}
            )
            
            assert logger.get_pending_count() == 1
            
            logger, block2 = log_entry_pure(
                logger,
                operation="TEST2",
                user_id="user2",
                resource="test",
                action="EXECUTE",
                details={"test": 2}
            )
            
            assert logger.get_pending_count() == 0  # Should have committed
            assert block2 is not None
            
            # Get logs
            logs = get_logs_pure(logger)
            assert len(logs) == 2
        
        finally:
            os.unlink(db_path)
    
    def test_logger_composition(self):
        """Test functional composition of logger operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            logger = create_logger(db_path, batch_size=3, batch_timeout=60.0)
            
            # Create operations
            operations = [
                lambda l: log_entry_pure(l, "TEST1", "user1", "test", "EXECUTE", {"test": 1}),
                lambda l: log_entry_pure(l, "TEST2", "user2", "test", "EXECUTE", {"test": 2}),
                lambda l: log_entry_pure(l, "TEST3", "user3", "test", "EXECUTE", {"test": 3}),
                lambda l: commit_batch_pure(l),
            ]
            
            # Execute operations
            final_logger, results = map_logger_operations(logger, operations)
            
            assert final_logger.get_total_entries() == 3
            assert len(results) == 4
        
        finally:
            os.unlink(db_path)
    
    def test_logger_filtering(self):
        """Test functional filtering of log entries."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            logger = create_logger(db_path, batch_size=5, batch_timeout=60.0)
            
            # Add various log entries
            for i in range(5):
                logger, _ = log_entry_pure(
                    logger,
                    operation=f"TEST{i}",
                    user_id=f"user{i % 2}",  # Alternate users
                    resource="test",
                    action="EXECUTE",
                    details={"test": i}
                )
            
            # Filter by user
            user0_logs = filter_logger_entries(
                logger,
                lambda entry: entry.get("user_id") == "user0"
            )
            assert len(user0_logs) == 3  # user0, user2, user4
            
            # Filter by operation
            test0_logs = filter_logger_entries(
                logger,
                lambda entry: entry.get("operation") == "TEST0"
            )
            assert len(test0_logs) == 1
        
        finally:
            os.unlink(db_path)


class TestFunctionalHigherOrderFunctions:
    """Test higher-order functions."""
    
    def test_map_blocks(self):
        """Test mapping over blocks."""
        state = BlockchainState(
            blocks=tuple([
                create_genesis_block(),
                create_genesis_block(),  # Another block for testing
            ])
        )
        
        # Map to get block hashes
        hashes = map_blocks(state, lambda block: block.hash)
        assert len(hashes) == 2
        assert all(len(hash_val) == 64 for hash_val in hashes)
    
    def test_filter_blocks(self):
        """Test filtering blocks."""
        state = BlockchainState(
            blocks=tuple([
                create_genesis_block(),
                create_genesis_block(),
            ])
        )
        
        # Filter blocks with difficulty > 3
        filtered = filter_blocks(state, lambda block: block.header.difficulty > 3)
        assert len(filtered) == 2  # Both genesis blocks have difficulty 4
    
    def test_reduce_blocks(self):
        """Test reducing blocks."""
        state = BlockchainState(
            blocks=tuple([
                create_genesis_block(),
                create_genesis_block(),
            ])
        )
        
        # Count total entries
        total_entries = reduce_blocks(
            state,
            lambda acc, block: acc + len(block.data.log_entries),
            0
        )
        assert total_entries == 0  # Genesis blocks have no entries
    
    def test_compose_functions(self):
        """Test function composition."""
        def add_one(x: int) -> int:
            return x + 1
        
        def multiply_by_two(x: int) -> int:
            return x * 2
        
        def square(x: int) -> int:
            return x ** 2
        
        # Compose: square(multiply_by_two(add_one(x)))
        composed = compose_functions(square, multiply_by_two, add_one)
        result = composed(3)
        assert result == 64  # (3 + 1) * 2 = 8, 8^2 = 64


class TestFunctionalStatistics:
    """Test functional statistics calculation."""
    
    def test_calculate_blockchain_stats(self):
        """Test blockchain statistics calculation."""
        state = BlockchainState(
            blocks=tuple([
                Block(
                    header=create_block_header(),
                    data=create_block_data(log_entries=[
                        {"operation": "TEST1", "user_id": "user1", "timestamp": 100},
                        {"operation": "TEST2", "user_id": "user2", "timestamp": 200},
                    ])
                )
            ])
        )
        
        stats = calculate_blockchain_stats(state)
        
        assert stats["total_entries"] == 2
        assert stats["unique_operations"] == 2
        assert stats["unique_users"] == 2
        assert stats["time_range"] == (100, 200)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 