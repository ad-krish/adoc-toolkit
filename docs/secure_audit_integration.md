# Secure Audit Log Integration

This document describes the integration of the secure audit logging system with the existing ADOC toolkit audit framework.

## Overview

The secure audit integration provides a tamper-proof audit logging system that can be used alongside or as a replacement for traditional file-based audit logging. It ensures data integrity and verifiability of audit logs through cryptographic hashing and blockchain structure (internal implementation details).

## Key Features

- **Dual Logging**: Supports both traditional file logging and secure audit logging simultaneously
- **Configuration Driven**: All settings managed through the existing configuration system
- **Command Integration**: New `audit` command for managing and querying secure audit logs
- **Integrity Verification**: Built-in verification of audit log integrity
- **Advanced Querying**: Filter audit logs by user, operation, resource, and time

## Configuration

The secure audit system is configured through the existing `set-config` command and configuration file. All settings are under the `audit.log` namespace.

### Configuration Options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `audit.log.enabled` | boolean | false | Enable secure audit logging |
| `audit.log.database_path` | string | audit/audit_log.db | Path to audit log database |
| `audit.log.difficulty` | integer | 4 | Mining difficulty (2-6) |

### Configuration Examples

```bash
# Enable secure audit logging
set-config audit.log.enabled true

# Set custom database path
set-config audit.log.database_path ./my_audit.db

# Increase mining difficulty
set-config audit.log.difficulty 5
```

## Usage

### Audit Command

The new `audit` command provides comprehensive management of the secure audit system:

```bash
# Show audit system status
audit status

# Show audit log information
audit info

# Verify audit log integrity
audit verify

# Query audit logs
audit logs
audit logs --user john.doe --limit 10
audit logs --operation authentication

# Enable/disable secure logging
audit enable
audit disable

# Reconfigure audit system
audit reconfigure
```

### Programmatic Usage

The secure audit system can be used programmatically:

```python
from adoc_toolkit.audit import get_audit_logger

# Get the audit logger
audit_logger = get_audit_logger()

# Log operations
audit_logger.log_operation(
    command_object="user_management",
    operation_type="user_login",
    details={"ip": "192.168.1.100", "success": True},
    user_id="john.doe",
    ip_address="192.168.1.100"
)

# Check status
if audit_logger.is_blockchain_enabled():
    info = audit_logger.get_blockchain_info()
    print(f"Audit log has {info['total_blocks']} entries")

# Verify integrity
result = audit_logger.verify_blockchain_integrity()
if result['integrity_verified']:
    print("Audit log integrity verified")
```



## Integration with Existing Audit System

The secure audit system integrates seamlessly with the existing audit framework:

### Dual Logging

When both file logging and blockchain logging are enabled, audit entries are written to both systems:

```python
from adoc_toolkit.audit import log_operation_secure

# This will log to both file (if configured) and blockchain (if enabled)
log_operation_secure(
    command_object="data_access",
    operation_type="read",
    details={"resource": "users", "count": 100},
    user_id="admin"
)
```

### Configuration Integration

The secure audit system uses the same configuration management as the rest of the toolkit:

```python
from adoc_toolkit.config import get_config_manager

cm = get_config_manager()

# Check if blockchain logging is enabled
if cm.get("audit.log.enabled"):
    print("Blockchain audit logging is enabled")

# Get blockchain configuration
database_path = cm.get("audit.log.database_path")
difficulty = cm.get("audit.log.difficulty")
```

## Security Features

### Data Integrity

- Each audit entry is cryptographically linked to the previous one
- Any alteration of a previous entry invalidates all subsequent entries
- Blockchain structure ensures tamper detection

### Proof-of-Work

- Configurable mining difficulty (2-6 leading zeros)
- Computational effort required to add new blocks
- Prevents rapid creation of fake audit entries

### Integrity Verification

- Built-in verification of entire blockchain
- Automatic detection of tampering
- Cryptographic proof of data integrity

## Performance Considerations

### Storage

- SQLite database for efficient storage and querying
- Indexed fields for fast lookups
- Configurable database path

### Mining

- Difficulty level affects mining time
- Higher difficulty = more security but slower logging
- Recommended: 4 for most use cases



## Migration from File Logging

To migrate from file-based audit logging to blockchain logging:

1. **Enable blockchain logging**:
   ```bash
   set-config audit.log.enabled true
   ```

2. **Configure database path**:
   ```bash
   set-config audit.log.database_path ./audit_blockchain.db
   ```

3. **Optional: Disable file logging**:
   ```bash
   set-config audit.log.enabled false
   ```

4. **Verify integration**:
   ```bash
   audit status
   audit verify
   ```

## Troubleshooting

### Common Issues

1. **Blockchain not enabled**: Check `audit.log.enabled` setting
2. **Database errors**: Verify database path and permissions
3. **API server issues**: Check host/port configuration
4. **Performance issues**: Adjust difficulty level

### Debug Commands

```bash
# Check audit system status
audit status

# Verify blockchain integrity
audit verify

# Get detailed blockchain info
audit info

# Query recent logs
audit logs --limit 5
```

## Best Practices

1. **Start with lower difficulty** (2-3) for testing, increase for production
2. **Regular integrity checks** using `audit verify`
3. **Backup database** regularly
4. **Monitor storage** as blockchain grows
5. **Use API server** for remote monitoring and querying
6. **Combine with file logging** for redundancy

## Architecture

The secure audit system consists of several components:

- **AuditLogger**: Main integration class
- **BlockchainLogger**: Core blockchain functionality
- **SQLiteBlockchainStorage**: Persistent storage
- **AuditCommand**: CLI management interface

All components integrate with the existing audit framework and configuration system. 