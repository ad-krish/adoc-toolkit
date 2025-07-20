# ADOC Toolkit Tracing Guide

This guide explains how to add comprehensive tracing to ADOC toolkit commands using the reusable tracing system.

## Overview

The ADOC toolkit provides a powerful tracing system that allows commands to emit detailed nested trace information when the log level is set to TRACE. This is extremely valuable for debugging complex operations and understanding execution flow.

### Key Features

- **Nested tracing** - Shows call hierarchy with indentation  
- **Conditional logging** - Only active when log level is TRACE
- **Thread-safe** - Uses thread-local storage for depth tracking
- **Easy integration** - Simple mixin and decorator approach
- **Detailed context** - Includes method names, argument counts, and custom details

## Quick Start

### 1. Make Your Command Traceable

```python
from ...tracing import TraceableMixin, trace_method
from .base import Command

class MyCommand(Command, TraceableMixin):
    @property
    def trace_prefix(self) -> Optional[str]:
        return "my_command"  # This will prefix all trace messages
    
    @trace_method("execute_command", "my_command")  
    def execute(self, args: list[str]) -> bool:
        self.trace("execution_started", args_count=len(args))
        
        # Your command logic here
        result = self._process_data()
        
        self.trace("execution_completed", success=True)
        return result
    
    @trace_method("process_data", "my_command")
    def _process_data(self) -> bool:
        self.trace("data_processing_started")
        # Processing logic...
        self.trace("data_processing_completed", records_processed=100)
        return True
```

### 2. Enable Tracing

Set the log level to TRACE to see tracing output:

```bash
# In the ADOC toolkit
log.level TRACE
my-command --option value
```

### 3. Example Output

```
→ my_command.execute_command
  → my_command.execution_started
    → my_command.process_data
      → my_command.data_processing_started  
      → my_command.data_processing_completed
    → my_command.process_data_completed
  → my_command.execution_completed
→ my_command.execute_command_completed
```

## Detailed Usage

### TraceableMixin Methods

The `TraceableMixin` provides several convenient methods:

```python
# Basic tracing
self.trace("operation_name", detail1="value1", detail2="value2")

# Convenience methods  
self.trace_start("processing")        # Adds "_started" suffix
self.trace_complete("processing")     # Adds "_completed" suffix  
self.trace_error("processing", error) # Adds "_failed" suffix with error details

# Reset trace depth (rarely needed)
self.reset_trace()
```

### @trace_method Decorator

The decorator automatically traces method entry, success, and failure:

```python
@trace_method()  # Uses method name as operation name
def simple_method(self):
    pass

@trace_method("custom_operation")  # Custom operation name
def another_method(self):
    pass

@trace_method("fetch_data", "my_command")  # Custom name + prefix
def fetch_data(self):
    pass
```

### Manual Tracing

For fine-grained control, use manual tracing:

```python
def complex_operation(self):
    self.trace("operation_started", input_size=len(data))
    
    try:
        for i, item in enumerate(data):
            self.trace("processing_item", item_index=i, item_id=item.id)
            # Process item...
            
        self.trace("operation_completed", items_processed=len(data))
        
    except Exception as e:
        self.trace_error("operation", e)
        raise
```

## Advanced Examples

### HTTP Client Tracing

```python
class DataFetchCommand(Command, TraceableMixin):
    @property 
    def trace_prefix(self) -> Optional[str]:
        return "data_fetch"
        
    @trace_method("fetch_all_endpoints", "data_fetch")
    def _fetch_data(self, endpoints: list[str]) -> dict:
        self.trace("fetch_started", endpoint_count=len(endpoints))
        
        results = {}
        for endpoint in endpoints:
            result = self._fetch_single(endpoint)
            results[endpoint] = result
            
        self.trace("fetch_completed", total_endpoints=len(endpoints))
        return results
    
    @trace_method("fetch_single_endpoint", "data_fetch")  
    def _fetch_single(self, endpoint: str) -> dict:
        self.trace("http_request_started", endpoint=endpoint)
        
        try:
            response = http_client.get(endpoint)
            self.trace("http_request_completed", 
                      status_code=response.status_code,
                      response_size=len(response.content))
            return response.json()
            
        except Exception as e:
            self.trace_error("http_request", e, endpoint=endpoint)
            raise
```

### Data Processing with Progress Tracing

```python
@trace_method("process_large_dataset", "data_processor")
def process_data(self, data: list) -> list:
    self.trace("processing_started", total_records=len(data))
    
    processed = []
    batch_size = 100
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        self.trace("processing_batch", 
                  batch_number=i // batch_size + 1,
                  batch_size=len(batch))
        
        batch_result = self._process_batch(batch)
        processed.extend(batch_result)
        
        # Progress update every 10 batches
        if (i // batch_size) % 10 == 0:
            self.trace("progress_update", 
                      completed_records=len(processed),
                      progress_percent=round(len(processed) / len(data) * 100, 1))
    
    self.trace("processing_completed", 
              total_processed=len(processed),
              success_rate=len(processed) / len(data))
    
    return processed
```

## Best Practices

### 1. Use Meaningful Operation Names
```python
# Good
self.trace("database_connection_established")
self.trace("user_authentication_successful") 

# Less useful
self.trace("step1")
self.trace("done")
```

### 2. Include Relevant Context
```python
# Good - provides useful debugging information
self.trace("query_executed", 
          query_type="SELECT", 
          table_name="users",
          execution_time_ms=45,
          rows_returned=156)

# Basic - still useful but less detailed
self.trace("query_executed")
```

### 3. Trace Both Success and Failure Paths
```python
try:
    result = risky_operation()
    self.trace("operation_successful", result_count=len(result))
    return result
except SpecificError as e:
    self.trace_error("operation", e, error_context="specific_failure")
    handle_specific_error()
except Exception as e:
    self.trace_error("operation", e, error_context="unexpected_failure")
    raise
```

### 4. Use Appropriate Trace Levels
```python
# High-level operations - always trace
self.trace("command_execution_started")
self.trace("data_export_completed")

# Mid-level operations - trace key steps  
self.trace("http_requests_started")
self.trace("data_validation_completed")

# Low-level operations - trace sparingly
# Only for very detailed debugging needs
self.trace("processing_single_record", record_id=record.id)
```

## Log Level Hierarchy

The tracing system respects the log level hierarchy:

- **TRACE**: Shows all messages (TRACE + DEBUG + INFO + ERROR) including tracing
- **DEBUG**: Shows DEBUG + INFO + ERROR (no tracing)
- **INFO**: Shows INFO + ERROR (no tracing)  
- **ERROR**: Shows only ERROR (no tracing)

## Integration with Existing Commands

To add tracing to an existing command:

1. Add `TraceableMixin` to the class inheritance
2. Implement the `trace_prefix` property
3. Add `@trace_method` decorators to key methods
4. Add manual `self.trace()` calls for important operations
5. Test with `log.level TRACE` to verify output

## Performance Considerations

- Tracing has minimal overhead when disabled (log level != TRACE)
- When enabled, tracing adds small overhead for string formatting
- Thread-local storage is efficient and thread-safe
- No significant impact on command performance

## Testing

The tracing system automatically disables itself in pytest environments to avoid interfering with tests. Commands with tracing work normally in tests without any special configuration.