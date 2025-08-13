"""
Functional programming example for immutable audit logging.

This example demonstrates how to use the functional immutable_log module
with pure functions, immutable data structures, and functional composition.
"""

import time
import tempfile
import os
from typing import Dict, Any, List
from .functional_logger import (
    create_logger, FunctionalLogger, log_entry_pure, commit_batch_pure,
    get_logs_pure, map_logger_operations, filter_logger_entries,
    compose_logger_operations, create_operation_logger, create_http_request_logger
)


def demonstrate_basic_functional_logging():
    """Demonstrate basic functional logging operations."""
    print("=== Basic Functional Logging ===")
    
    # Create a temporary database for this example
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create a functional logger
        logger = create_logger(db_path, batch_size=3, batch_timeout=60.0)
        
        # Log some entries using pure functions
        logger, block1 = log_entry_pure(
            logger,
            operation="COMMAND",
            user_id="user1",
            resource="cli",
            action="EXECUTE",
            details={"command": "help", "args": []}
        )
        
        logger, block2 = log_entry_pure(
            logger,
            operation="COMMAND",
            user_id="user1",
            resource="cli",
            action="EXECUTE",
            details={"command": "show", "args": ["config"]}
        )
        
        # Force commit the pending batch
        logger, committed_block = commit_batch_pure(logger)
        
        if committed_block:
            print(f"Committed block with {len(committed_block.data.log_entries)} entries")
        
        # Get logs using pure function
        logs = get_logs_pure(logger, user_id="user1")
        print(f"Retrieved {len(logs)} log entries")
        
        # Get blockchain info
        info = logger.get_info()
        print(f"Blockchain info: {info}")
        
    finally:
        os.unlink(db_path)


def demonstrate_functional_composition():
    """Demonstrate functional composition of logging operations."""
    print("\n=== Functional Composition ===")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        logger = create_logger(db_path, batch_size=5, batch_timeout=60.0)
        
        # Create specialized logging operations
        command_logger = create_operation_logger("COMMAND", "user1", "cli")
        http_logger = create_http_request_logger("GET", "/api/config", "user1", 200)
        
        # Compose multiple operations
        operations = [
            lambda l: command_logger(l, {"command": "help", "args": []}),
            lambda l: command_logger(l, {"command": "show", "args": ["config"]}),
            lambda l: http_logger(l, {"response_time": 150, "status": "success"}),
            lambda l: command_logger(l, {"command": "set", "args": ["timeout", "30"]}),
            lambda l: commit_batch_pure(l),  # Force commit
        ]
        
        # Execute all operations sequentially
        final_logger, results = map_logger_operations(logger, operations)
        
        print(f"Executed {len(operations)} operations")
        print(f"Final state: {final_logger.get_total_blocks()} blocks, {final_logger.get_total_entries()} entries")
        
        # Filter logs using functional approach
        command_logs = filter_logger_entries(
            final_logger,
            lambda entry: entry.get("operation") == "COMMAND"
        )
        print(f"Found {len(command_logs)} command operations")
        
    finally:
        os.unlink(db_path)


def demonstrate_immutable_state_transitions():
    """Demonstrate immutable state transitions."""
    print("\n=== Immutable State Transitions ===")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initial state
        logger1 = create_logger(db_path, batch_size=2, batch_timeout=60.0)
        print(f"Initial state: {logger1.get_pending_count()} pending entries")
        
        # First transition
        logger2, block1 = log_entry_pure(
            logger1,
            operation="LOGIN",
            user_id="user1",
            resource="auth",
            action="ATTEMPT",
            details={"ip": "192.168.1.1", "success": True}
        )
        print(f"After first log: {logger2.get_pending_count()} pending entries")
        
        # Second transition
        logger3, block2 = log_entry_pure(
            logger2,
            operation="LOGIN",
            user_id="user1",
            resource="auth",
            action="SUCCESS",
            details={"session_id": "abc123", "duration": 2.5}
        )
        print(f"After second log: {logger3.get_pending_count()} pending entries")
        
        # Third transition (should trigger batch commit)
        logger4, block3 = log_entry_pure(
            logger3,
            operation="LOGOUT",
            user_id="user1",
            resource="auth",
            action="SUCCESS",
            details={"session_duration": 1800}
        )
        print(f"After third log: {logger4.get_pending_count()} pending entries")
        
        # Verify all states are immutable (original logger unchanged)
        print(f"Original logger still has: {logger1.get_pending_count()} pending entries")
        
        # Get final stats
        stats = logger4.get_stats()
        print(f"Final stats: {stats}")
        
    finally:
        os.unlink(db_path)


def demonstrate_higher_order_functions():
    """Demonstrate higher-order functions with logging."""
    print("\n=== Higher-Order Functions ===")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        logger = create_logger(db_path, batch_size=10, batch_timeout=60.0)
        
        # Create a list of operations to perform
        operations_data = [
            ("COMMAND", "user1", "cli", "EXECUTE", {"command": "help"}),
            ("COMMAND", "user1", "cli", "EXECUTE", {"command": "show"}),
            ("HTTP_REQUEST", "user1", "/api/data", "GET", {"response_time": 100}),
            ("COMMAND", "user2", "cli", "EXECUTE", {"command": "config"}),
            ("HTTP_REQUEST", "user2", "/api/users", "POST", {"response_time": 200}),
        ]
        
        # Create operations using map
        operations = [
            lambda l, op_data=op_data: log_entry_pure(
                l, operation=op_data[0], user_id=op_data[1], 
                resource=op_data[2], action=op_data[3], details=op_data[4]
            )
            for op_data in operations_data
        ]
        
        # Execute all operations
        final_logger, results = map_logger_operations(logger, operations)
        
        # Use functional filtering
        user1_logs = filter_logger_entries(
            final_logger,
            lambda entry: entry.get("user_id") == "user1"
        )
        
        command_logs = filter_logger_entries(
            final_logger,
            lambda entry: entry.get("operation") == "COMMAND"
        )
        
        print(f"Total entries: {final_logger.get_total_entries()}")
        print(f"User1 entries: {len(user1_logs)}")
        print(f"Command entries: {len(command_logs)}")
        
    finally:
        os.unlink(db_path)


def demonstrate_functional_utilities():
    """Demonstrate functional utility functions."""
    print("\n=== Functional Utilities ===")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        logger = create_logger(db_path, batch_size=3, batch_timeout=60.0)
        
        # Create a workflow using composition
        workflow = compose_logger_operations(
            lambda l: log_entry_pure(l, "SETUP", "system", "init", "START", {"version": "1.0"}),
            lambda l: log_entry_pure(l, "CONFIG", "system", "config", "LOAD", {"file": "config.json"}),
            lambda l: log_entry_pure(l, "STARTUP", "system", "service", "START", {"port": 8080}),
            lambda l: commit_batch_pure(l),  # Commit the workflow
        )
        
        # Execute the workflow
        final_logger, result = workflow(logger)
        
        print(f"Workflow completed: {final_logger.get_total_blocks()} blocks created")
        
        # Verify integrity
        is_valid = final_logger.verify_integrity()
        print(f"Blockchain integrity: {'✓ Valid' if is_valid else '✗ Invalid'}")
        
        # Get detailed info
        info = final_logger.get_info()
        print(f"Blockchain info: {info}")
        
    finally:
        os.unlink(db_path)


def run_all_demonstrations():
    """Run all functional programming demonstrations."""
    print("🚀 Functional Programming Immutable Logging Demonstrations")
    print("=" * 60)
    
    demonstrate_basic_functional_logging()
    demonstrate_functional_composition()
    demonstrate_immutable_state_transitions()
    demonstrate_higher_order_functions()
    demonstrate_functional_utilities()
    
    print("\n✅ All demonstrations completed successfully!")
    print("\nKey Functional Programming Features Demonstrated:")
    print("• Pure functions with no side effects")
    print("• Immutable data structures")
    print("• Functional composition")
    print("• Higher-order functions")
    print("• State transitions through function application")
    print("• Declarative programming style")


if __name__ == "__main__":
    run_all_demonstrations() 