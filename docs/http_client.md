# HTTP Client Library

## Overview
The ADOC Toolkit includes a robust HTTP client library specifically designed for interacting with ADOC (AccelData Observability Cloud) APIs. The client provides automatic authentication, retry logic, error handling, and configuration management.

## Features

- **Full HTTP Method Support**: GET, POST, PUT, DELETE operations
- **Environment Integration**: Automatic base URL and authentication from environment settings
- **Configuration Management**: Timeout, retry, and proxy settings via `set-config`
- **File Upload Support**: Upload files using `@file-path` syntax
- **Automatic Retries**: Configurable retry logic for transient failures
- **Response Delegation**: Pluggable response handling for different commands
- **Comprehensive Error Handling**: Network, timeout, and HTTP error management

## Architecture

### Key Components

#### `ADOCHTTPClient`
The main HTTP client class that handles all API interactions.

```python
from adoc_toolkit.http_client import ADOCHTTPClient

# Initialize with environment and response callbacks
client = ADOCHTTPClient(
    environment_info_callback=get_current_env,
    response_handler=handle_responses
)
```

#### `HTTPResponse`
Wrapper class for HTTP responses with additional metadata and convenience methods.

```python
response = client.get("/api/data")
print(f"Status: {response.status_code}")
print(f"Success: {response.is_success}")
data = response.json()  # Parse JSON response
```

#### `HTTPError`
Comprehensive error class for HTTP-related exceptions.

```python
try:
    response = client.get("/api/endpoint")
except HTTPError as e:
    print(f"HTTP error: {e}")
    if e.response:
        print(f"Status: {e.response.status_code}")
```

## Configuration

The HTTP client uses settings configured via the `set-config` command:

### Timeout Configuration
```bash
# Set request timeout to 60 seconds
ADOC > set-config http.timeout 60
```

### Retry Configuration
```bash
# Set retry attempts to 5
ADOC > set-config http.retries 5
```

### Proxy Configuration
```bash
# Set HTTP proxy
ADOC > set-config http.proxy https://proxy.company.com:8080

# Remove proxy
ADOC > set-config http.proxy none
```

## Authentication

The HTTP client automatically handles authentication using credentials from the currently selected environment:

```bash
# First, select an environment
ADOC > use production-env

# HTTP client automatically uses production-env credentials
# Adds headers: accessKey and secretKey
```

### Authentication Headers
- `accessKey`: Access key from environment configuration
- `secretKey`: Secret key from environment configuration

## HTTP Methods

### GET Requests
```python
# Simple GET
response = client.get("/api/users")

# GET with query parameters
response = client.get("/api/users", params={"limit": 10, "offset": 0})

# GET with custom headers
response = client.get("/api/data", headers={"X-Custom": "value"})
```

### POST Requests
```python
# POST with JSON data
data = {"name": "John", "email": "john@example.com"}
response = client.post("/api/users", data=data)

# POST with string data
response = client.post("/api/logs", data="log entry text")

# POST with file upload
response = client.post("/api/upload", file_path="/path/to/file.json")

# POST with custom headers
response = client.post("/api/data", data=data, headers={"Content-Type": "application/xml"})
```

### PUT Requests
```python
# PUT with JSON data
updated_data = {"name": "Jane", "email": "jane@example.com"}
response = client.put("/api/users/123", data=updated_data)

# PUT with file upload
response = client.put("/api/config", file_path="/path/to/config.yaml")
```

### DELETE Requests
```python
# Simple DELETE
response = client.delete("/api/users/123")

# DELETE with query parameters
response = client.delete("/api/sessions", params={"expired": True})
```

## File Upload Support

The HTTP client supports file uploads for POST and PUT requests:

### Automatic Content-Type Detection
```python
# JSON file - automatically sets Content-Type: application/json
response = client.post("/api/config", file_path="config.json")

# Text file - automatically sets Content-Type: text/plain  
response = client.post("/api/logs", file_path="app.log")

# Binary file - automatically sets Content-Type: application/octet-stream
response = client.post("/api/upload", file_path="data.bin")
```

### File Upload Examples
```python
# Upload configuration file
response = client.post("/api/configuration", file_path="/etc/app/config.json")

# Upload log file for analysis
response = client.put("/api/logs/upload", file_path="/var/log/app.log")
```

## Error Handling

### Network Errors
```python
try:
    response = client.get("/api/data")
except HTTPError as e:
    if "Connection error" in str(e):
        print("Network connection failed")
    elif "timeout" in str(e):
        print("Request timed out")
```

### HTTP Status Errors
```python
response = client.get("/api/users")

if response.is_client_error:
    print(f"Client error: {response.status_code}")
    
if response.is_server_error:
    print(f"Server error: {response.status_code}")
```

### Comprehensive Error Information
```python
try:
    response = client.post("/api/users", data=invalid_data)
except HTTPError as e:
    print(f"Error: {e}")
    if e.response:
        print(f"Status: {e.response.status_code}")
        print(f"Response: {e.response.text}")
```

## Retry Logic

The HTTP client implements intelligent retry logic:

### Automatic Retries
- **Timeout Errors**: Automatically retried
- **Connection Errors**: Automatically retried
- **HTTP Errors**: Not retried (fail fast)

### Retry Configuration
```python
# Retry behavior is controlled by set-config
# Default: 3 retries with exponential backoff
```

### Retry Information
```python
# Retry information is included in response metadata
response = client.get("/api/data")
retries = response.request_info.get("retries_attempted", 0)
print(f"Request completed after {retries} retries")
```

## Response Handling

### Default Response Handler
The HTTP client includes a default response handler that:

- Logs request success/failure with visual indicators
- Shows retry information
- Displays error messages from JSON responses
- Handles both structured and plain text errors

### Custom Response Handlers
```python
def custom_handler(response):
    if response.is_success:
        print(f"✅ Success: {response.status_code}")
        # Custom success handling
    else:
        print(f"❌ Failed: {response.status_code}")
        # Custom error handling

client = ADOCHTTPClient(response_handler=custom_handler)
```

## Health Check

The HTTP client includes a built-in health check method:

```python
# Check if current environment is reachable
if client.health_check():
    print("Environment is healthy")
else:
    print("Environment is unreachable")
```

## Integration with Commands

The HTTP client is automatically integrated into the interactive processor and available to all commands:

### Accessing HTTP Client in Commands
```python
class MyAPICommand(Command):
    def execute(self, args):
        # Access via processor's http_client
        processor = self.get_processor()  # Implementation specific
        response = processor.http_client.get("/api/data")
        
        if response.is_success:
            data = response.json()
            # Process data...
        
        return True
```

## Response Format Examples

### Successful Response
```
✅ GET /api/users - 200
```

### Client Error Response
```
⚠️  POST /api/users - 400
Error: Email address is required
```

### Server Error with Retries
```
❌ GET /api/data - 500 (after 3 retries)
Error: Internal server error
```

## Best Practices

### 1. Environment Selection
Always ensure an environment is selected before making API calls:
```python
env_info = client._get_environment_info()
if not env_info.get("base_url"):
    raise HTTPError("No environment selected. Use 'use <environment>' first.")
```

### 2. Error Handling
Always handle potential HTTP errors:
```python
try:
    response = client.get("/api/data")
    data = response.json()
except HTTPError as e:
    # Handle error appropriately
    return False
```

### 3. Response Validation
Validate responses before processing:
```python
response = client.get("/api/users")
if response.is_success:
    try:
        users = response.json()
        # Process users...
    except ValueError:
        print("Invalid JSON response")
```

### 4. Configuration Management
Configure HTTP settings appropriately for your environment:
```bash
# Development - fail fast
ADOC > set-config http.timeout 30
ADOC > set-config http.retries 1

# Production - more resilient
ADOC > set-config http.timeout 120
ADOC > set-config http.retries 5
```

### 5. File Upload Validation
Validate files before upload:
```python
file_path = "/path/to/upload.json"
if not Path(file_path).exists():
    print(f"File not found: {file_path}")
    return False

try:
    response = client.post("/api/upload", file_path=file_path)
except HTTPError as e:
    print(f"Upload failed: {e}")
```

## Debugging

### Request Information
All responses include detailed request information:
```python
response = client.get("/api/data")
print(f"Method: {response.request_info['method']}")
print(f"URL: {response.request_info['url']}")
print(f"Retries: {response.request_info['retries_attempted']}")
```

### Verbose Logging
The default response handler provides verbose logging of all requests and responses, making it easy to debug API interactions.

## Security Considerations

1. **Credential Handling**: Access and secret keys are automatically managed and never logged
2. **Proxy Support**: Supports authenticated proxies for corporate environments
3. **Timeout Protection**: Prevents hanging requests with configurable timeouts
4. **Error Information**: Sensitive information is not exposed in error messages

## Future Enhancements

The HTTP client library is designed to be extensible:

- **Custom Authentication**: Support for different auth methods
- **Request Middleware**: Pre/post request processing hooks
- **Response Caching**: Configurable response caching
- **Metrics Collection**: Request timing and success rate metrics
- **Custom Serialization**: Support for different content types