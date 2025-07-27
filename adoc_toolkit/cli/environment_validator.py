"""Environment configuration validation with detailed error reporting."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import yaml

class EnvironmentValidationError(Exception):
    """Custom exception for environment validation errors."""
    
    def __init__(self, message: str, line_number: Optional[int] = None, field_path: Optional[str] = None):
        self.message = message
        self.line_number = line_number
        self.field_path = field_path
        super().__init__(self.message)


class EnvironmentValidator:
    """Validates environment configuration with detailed error reporting."""
    
    def __init__(self, config_path: Path):
        """Initialize validator with config file path.
        
        Args:
            config_path: Path to the environments.yaml file
        """
        self.config_path = config_path
        self._file_lines: Optional[List[str]] = None
    
    def _load_file_lines(self) -> List[str]:
        """Load the file lines for line number reporting."""
        if self._file_lines is None:
            try:
                with open(self.config_path, 'r') as f:
                    self._file_lines = f.readlines()
            except Exception:
                self._file_lines = []
        return self._file_lines
    
    def _find_line_number(self, field_path: str, value: str) -> Optional[int]:
        """Find the line number for a specific field and value.
        
        Args:
            field_path: Path to the field (e.g., 'environments.dev.base_url')
            value: The value to search for
            
        Returns:
            Line number where the field is found, or None
        """
        lines = self._load_file_lines()
        field_parts = field_path.split('.')
        
        for i, line in enumerate(lines, 1):
            stripped_line = line.strip()
            if value in stripped_line:
                # Check if this line contains the field we're looking for
                if len(field_parts) == 3:  # environments.env.field
                    env_name = field_parts[1]
                    field_name = field_parts[2]
                    if f"{field_name}:" in stripped_line and env_name in "".join(lines[:i]):
                        return i
                elif len(field_parts) == 2:  # environments.env
                    env_name = field_parts[1]
                    if f"{env_name}:" in stripped_line:
                        return i
                elif len(field_parts) == 1:  # environments
                    if "environments:" in stripped_line:
                        return i
        
        return None
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate the environment configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check if file exists
        if not self.config_path.exists():
            errors.append(
                f"❌ Configuration file not found: {self.config_path}\n"
                f"   Please create the file with your environment configurations.\n"
                f"   See docs/environment-setup.md for detailed instructions."
            )
            return False, errors
        
        # Try to load YAML
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            line_number = getattr(e, 'line', None)
            if line_number:
                errors.append(
                    f"❌ Invalid YAML syntax at line {line_number}:\n"
                    f"   {str(e)}\n"
                    f"   Please fix the YAML syntax and try again."
                )
            else:
                errors.append(
                    f"❌ Invalid YAML format:\n"
                    f"   {str(e)}\n"
                    f"   Please fix the YAML syntax and try again."
                )
            return False, errors
        except Exception as e:
            errors.append(
                f"❌ Error reading configuration file:\n"
                f"   {str(e)}\n"
                f"   Please check file permissions and try again."
            )
            return False, errors
        
        # Validate structure
        structure_errors = self._validate_structure(config_data)
        errors.extend(structure_errors)
        
        if structure_errors:
            return False, errors
        
        # Validate environments
        environment_errors = self._validate_environments(config_data.get("environments", {}))
        errors.extend(environment_errors)
        
        # Validate default environment
        default_errors = self._validate_default_environment(config_data)
        errors.extend(default_errors)
        
        return len(errors) == 0, errors
    
    def _validate_structure(self, config_data: Any) -> List[str]:
        """Validate the basic structure of the configuration."""
        errors = []
        
        if not isinstance(config_data, dict):
            errors.append(
                f"❌ Invalid configuration format:\n"
                f"   Configuration must be a YAML object (dictionary).\n"
                f"   Found: {type(config_data).__name__}"
            )
            return errors
        
        if "environments" not in config_data:
            errors.append(
                f"❌ Missing required section:\n"
                f"   The 'environments' section is required but not found.\n"
                f"   Add this section to your configuration:\n"
                f"   ```yaml\n"
                f"   environments:\n"
                f"     your-env-name:\n"
                f"       name: your-env-name\n"
                f"       base_url: https://your-instance.acceldata.app\n"
                f"       access_key: YOUR_ADOC_ACCESS_KEY\n"
                f"       secret_key: YOUR_ADOC_SECRET_KEY\n"
                f"   ```"
            )
            return errors
        
        environments = config_data["environments"]
        if not isinstance(environments, dict):
            errors.append(
                f"❌ Invalid environments section:\n"
                f"   The 'environments' section must be a YAML object (dictionary).\n"
                f"   Found: {type(environments).__name__}"
            )
            return errors
        
        if not environments:
            errors.append(
                f"❌ No environments defined:\n"
                f"   The 'environments' section is empty.\n"
                f"   Please add at least one environment to the 'environments' section.\n"
                f"   Example:\n"
                f"   ```yaml\n"
                f"   environments:\n"
                f"     dev:\n"
                f"       name: dev\n"
                f"       base_url: https://dev.acceldata.app\n"
                f"       access_key: DEV123456789\n"
                f"       secret_key: DEVSECRET123456789\n"
                f"   ```"
            )
            return errors
        
        return errors
    
    def _validate_environments(self, environments: Dict[str, Any]) -> List[str]:
        """Validate each environment configuration."""
        errors = []
        
        for env_name, env_config in environments.items():
            env_errors = self._validate_single_environment(env_name, env_config)
            errors.extend(env_errors)
        
        return errors
    
    def _validate_single_environment(self, env_name: str, env_config: Any) -> List[str]:
        """Validate a single environment configuration."""
        errors = []
        
        # Check if env_config is a dictionary
        if not isinstance(env_config, dict):
            line_num = self._find_line_number(f"environments.{env_name}", env_name)
            errors.append(
                f"❌ Invalid environment configuration for '{env_name}':\n"
                f"   Environment configuration must be a YAML object (dictionary).\n"
                f"   Found: {type(env_config).__name__}"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
            return errors
        
        # Check required fields
        required_fields = ["name", "base_url", "access_key", "secret_key"]
        for field in required_fields:
            if field not in env_config:
                line_num = self._find_line_number(f"environments.{env_name}", env_name)
                errors.append(
                    f"❌ Missing required field in environment '{env_name}':\n"
                    f"   Field '{field}' is required but not found.\n"
                    f"   Add this field to your environment configuration:\n"
                    f"   ```yaml\n"
                    f"   {env_name}:\n"
                    f"     name: {env_name}\n"
                    f"     base_url: https://your-instance.acceldata.app\n"
                    f"     access_key: YOUR_ACCESS_KEY\n"
                    f"     secret_key: YOUR_SECRET_KEY\n"
                    f"   ```"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
                return errors
        
        # Validate field types and formats
        field_errors = self._validate_environment_fields(env_name, env_config)
        errors.extend(field_errors)
        
        return errors
    
    def _validate_environment_fields(self, env_name: str, env_config: Dict[str, Any]) -> List[str]:
        """Validate individual fields of an environment."""
        errors = []
        
        # Validate environment name format
        if not re.match(r"^[a-zA-Z0-9_-]+$", env_name):
            line_num = self._find_line_number(f"environments.{env_name}", env_name)
            errors.append(
                f"❌ Invalid environment name '{env_name}':\n"
                f"   Environment names can only contain letters, numbers, hyphens, and underscores.\n"
                f"   Please use a name like 'dev', 'staging', or 'production'."
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        
        # Validate name field
        name_value = env_config["name"]
        if not isinstance(name_value, str):
            line_num = self._find_line_number(f"environments.{env_name}.name", str(name_value))
            errors.append(
                f"❌ Invalid 'name' field in environment '{env_name}':\n"
                f"   The 'name' field must be a string.\n"
                f"   Found: {type(name_value).__name__}"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        elif name_value != env_name:
            line_num = self._find_line_number(f"environments.{env_name}.name", name_value)
            errors.append(
                f"❌ Name mismatch in environment '{env_name}':\n"
                f"   The 'name' field should match the environment key.\n"
                f"   Expected: '{env_name}', Found: '{name_value}'"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        
        # Validate base_url
        base_url = env_config["base_url"]
        if not isinstance(base_url, str):
            line_num = self._find_line_number(f"environments.{env_name}.base_url", str(base_url))
            errors.append(
                f"❌ Invalid 'base_url' field in environment '{env_name}':\n"
                f"   The 'base_url' field must be a string.\n"
                f"   Found: {type(base_url).__name__}"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        else:
            if not base_url.startswith(("http://", "https://")):
                line_num = self._find_line_number(f"environments.{env_name}.base_url", base_url)
                errors.append(
                    f"❌ Invalid 'base_url' in environment '{env_name}':\n"
                    f"   URL must start with 'http://' or 'https://'.\n"
                    f"   Current: '{base_url}'\n"
                    f"   Example: 'https://your-instance.acceldata.app'"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
            else:
                try:
                    parsed_url = urlparse(base_url)
                    if not parsed_url.netloc:
                        line_num = self._find_line_number(f"environments.{env_name}.base_url", base_url)
                        errors.append(
                            f"❌ Invalid 'base_url' in environment '{env_name}':\n"
                            f"   URL must have a valid domain.\n"
                            f"   Current: '{base_url}'\n"
                            f"   Example: 'https://your-instance.acceldata.app'"
                            + (f"\n   Line: {line_num}" if line_num else "")
                        )
                except Exception:
                    line_num = self._find_line_number(f"environments.{env_name}.base_url", base_url)
                    errors.append(
                        f"❌ Invalid 'base_url' in environment '{env_name}':\n"
                        f"   URL is not properly formatted.\n"
                        f"   Current: '{base_url}'\n"
                        f"   Example: 'https://your-instance.acceldata.app'"
                        + (f"\n   Line: {line_num}" if line_num else "")
                    )
        
        # Validate access_key
        access_key = env_config["access_key"]
        if not isinstance(access_key, str):
            line_num = self._find_line_number(f"environments.{env_name}.access_key", str(access_key))
            errors.append(
                f"❌ Invalid 'access_key' field in environment '{env_name}':\n"
                f"   The 'access_key' field must be a string.\n"
                f"   Found: {type(access_key).__name__}"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        else:
            if not re.match(r"^[A-Z0-9]+$", access_key):
                line_num = self._find_line_number(f"environments.{env_name}.access_key", access_key)
                errors.append(
                    f"❌ Invalid 'access_key' in environment '{env_name}':\n"
                    f"   Access key should contain only uppercase letters and numbers.\n"
                    f"   Current: '{access_key}'\n"
                    f"   Example: 'ABC123456789'"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
            elif len(access_key) < 8:
                line_num = self._find_line_number(f"environments.{env_name}.access_key", access_key)
                errors.append(
                    f"❌ Access key too short in environment '{env_name}':\n"
                    f"   Access key must be at least 8 characters long.\n"
                    f"   Current length: {len(access_key)} characters\n"
                    f"   Example: 'ABC123456789'"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
        
        # Validate secret_key
        secret_key = env_config["secret_key"]
        if not isinstance(secret_key, str):
            line_num = self._find_line_number(f"environments.{env_name}.secret_key", str(secret_key))
            errors.append(
                f"❌ Invalid 'secret_key' field in environment '{env_name}':\n"
                f"   The 'secret_key' field must be a string.\n"
                f"   Found: {type(secret_key).__name__}"
                + (f"\n   Line: {line_num}" if line_num else "")
            )
        else:
            if not re.match(r"^[A-Z0-9]+$", secret_key):
                line_num = self._find_line_number(f"environments.{env_name}.secret_key", secret_key)
                errors.append(
                    f"❌ Invalid 'secret_key' in environment '{env_name}':\n"
                    f"   Secret key should contain only uppercase letters and numbers.\n"
                    f"   Current: '{secret_key}'\n"
                    f"   Example: 'SECRET123456789'"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
            elif len(secret_key) < 8:
                line_num = self._find_line_number(f"environments.{env_name}.secret_key", secret_key)
                errors.append(
                    f"❌ Secret key too short in environment '{env_name}':\n"
                    f"   Secret key must be at least 8 characters long.\n"
                    f"   Current length: {len(secret_key)} characters\n"
                    f"   Example: 'SECRET123456789'"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
        
        return errors
    
    def _validate_default_environment(self, config_data: Dict[str, Any]) -> List[str]:
        """Validate the default_environment field."""
        errors = []
        
        if "default_environment" in config_data:
            default_env = config_data["default_environment"]
            environments = config_data.get("environments", {})
            
            if not isinstance(default_env, str):
                line_num = self._find_line_number("default_environment", str(default_env))
                errors.append(
                    f"❌ Invalid 'default_environment' field:\n"
                    f"   The 'default_environment' field must be a string.\n"
                    f"   Found: {type(default_env).__name__}"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
            elif default_env not in environments:
                line_num = self._find_line_number("default_environment", default_env)
                errors.append(
                    f"❌ Invalid 'default_environment':\n"
                    f"   Environment '{default_env}' does not exist in the environments list.\n"
                    f"   Available environments: {list(environments.keys())}"
                    + (f"\n   Line: {line_num}" if line_num else "")
                )
        
        return errors


def validate_environments_at_startup() -> Tuple[bool, List[str]]:
    """Validate environments.yaml at startup.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    config_path = Path("config/environments.yaml")
    validator = EnvironmentValidator(config_path)
    return validator.validate_config()


def load_default_environment() -> Optional[Tuple[str, Dict[str, Any]]]:
    """Load the default environment from environments.yaml.
    
    Returns:
        Tuple of (environment_name, environment_config) or None if no default
    """
    config_path = Path("config/environments.yaml")
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data or not isinstance(config_data, dict):
            return None
        
        default_env = config_data.get("default_environment")
        if not default_env:
            return None
        
        environments = config_data.get("environments", {})
        if default_env not in environments:
            return None
        
        return default_env, environments[default_env]
        
    except Exception:
        return None 