"""
Input validation and sanitization utilities for llmcode.

This module provides functions to validate and sanitize user inputs,
command arguments, file paths, and other data to prevent security
issues and ensure proper error handling.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from llmcode.exceptions import ValidationError


def validate_url(url: str) -> bool:
    """
    Validate that a string is a properly formatted URL.

    Args:
        url: The URL string to validate

    Returns:
        True if valid URL format, False otherwise

    Raises:
        ValidationError: If URL format is invalid
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL cannot be empty", field_name="url", value=url)

    # Basic URL pattern validation
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    if not url_pattern.match(url):
        raise ValidationError(f"Invalid URL format: {url}", field_name="url", value=url)

    return True


def validate_file_path(
    file_path: Union[str, Path], allow_absolute: bool = True, check_exists: bool = False
) -> Path:
    """
    Validate and sanitize a file path.

    Args:
        file_path: File path to validate
        allow_absolute: Whether to allow absolute paths
        check_exists: Whether to check if file exists

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path is invalid or unsafe
    """
    if not file_path:
        raise ValidationError("File path cannot be empty", field_name="file_path")

    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        raise ValidationError(
            f"Invalid file path: {file_path}", field_name="file_path", value=file_path
        ) from e

    # Prevent directory traversal attacks
    if ".." in str(path):
        raise ValidationError(
            f"Directory traversal not allowed in path: {file_path}",
            field_name="file_path",
            value=file_path,
        )

    if not allow_absolute and path.is_absolute():
        raise ValidationError(
            f"Absolute paths not allowed: {file_path}",
            field_name="file_path",
            value=file_path,
        )

    if check_exists and not path.exists():
        raise ValidationError(
            f"File does not exist: {file_path}", field_name="file_path", value=file_path
        )

    return path


def validate_model_name(model_name: str) -> str:
    """
    Validate a model name string.

    Args:
        model_name: Model name to validate

    Returns:
        Sanitized model name

    Raises:
        ValidationError: If model name is invalid
    """
    if not model_name or not isinstance(model_name, str):
        raise ValidationError(
            "Model name cannot be empty", field_name="model_name", value=model_name
        )

    # Remove potentially harmful characters
    sanitized = re.sub(r"[^\w\-/.:]", "", model_name)

    if len(sanitized) < 2:
        raise ValidationError(
            f"Model name too short: {model_name}",
            field_name="model_name",
            value=model_name,
        )

    if len(sanitized) > 100:
        raise ValidationError(
            f"Model name too long: {model_name}",
            field_name="model_name",
            value=model_name,
        )

    return sanitized


def validate_command_args(args: str, max_length: int = 10000) -> str:
    """
    Validate command arguments string.

    Args:
        args: Command arguments to validate
        max_length: Maximum allowed length

    Returns:
        Validated arguments string

    Raises:
        ValidationError: If arguments are invalid
    """
    if not isinstance(args, str):
        raise ValidationError(
            f"Arguments must be string, got {type(args)}", field_name="args", value=args
        )

    if len(args) > max_length:
        raise ValidationError(
            f"Arguments too long (max {max_length} chars)",
            field_name="args",
            value=args[:100],
        )

    # Check for potentially dangerous patterns
    dangerous_patterns = [
        r"rm\s+-rf",  # rm -rf commands
        r"sudo\s+",  # sudo commands
        r"chmod\s+777",  # dangerous chmod
        r"eval\s*\(",  # eval statements
        r"exec\s*\(",  # exec statements
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, args, re.IGNORECASE):
            raise ValidationError(
                f"Potentially dangerous command: {args}", field_name="args", value=args
            )

    return args


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove or replace unsafe characters.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        return "unnamed"

    # Replace unsafe characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove control characters
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", sanitized)

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")

    # Ensure we have a valid filename
    if not sanitized:
        return "unnamed"

    # Limit length to reasonable filesystem limits
    if len(sanitized) > 255:
        sanitized = sanitized[:255]

    return sanitized


def validate_environment_variable_name(name: str) -> str:
    """
    Validate an environment variable name.

    Args:
        name: Environment variable name to validate

    Returns:
        Validated environment variable name

    Raises:
        ValidationError: If name is invalid
    """
    if not name:
        raise ValidationError(
            "Environment variable name cannot be empty", field_name="env_var_name"
        )

    # Environment variable names should match [A-Z_][A-Z0-9_]*
    if not re.match(r"^[A-Z_][A-Z0-9_]*$", name.upper()):
        raise ValidationError(
            f"Invalid environment variable name: {name}",
            field_name="env_var_name",
            value=name,
        )

    return name.upper()


def validate_numeric_input(
    value: Union[str, int, float],
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
) -> Union[int, float]:
    """
    Validate numeric input with optional range checking.

    Args:
        value: Numeric value to validate
        field_name: Name of the field for error reporting
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Validated numeric value

    Raises:
        ValidationError: If value is invalid or out of range
    """
    try:
        if isinstance(value, str):
            # Handle common suffixes
            value = value.strip().lower()
            if value.endswith("k"):
                numeric_value = float(value[:-1]) * 1000
            elif value.endswith("m"):
                numeric_value = float(value[:-1]) * 1000000
            elif value.endswith("g"):
                numeric_value = float(value[:-1]) * 1000000000
            else:
                numeric_value = float(value)
        else:
            numeric_value = float(value)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid numeric value for {field_name}: {value}",
            field_name=field_name,
            value=value,
        ) from e

    if min_value is not None and numeric_value < min_value:
        raise ValidationError(
            f"Value {numeric_value} is below minimum {min_value} for {field_name}",
            field_name=field_name,
            value=value,
        )

    if max_value is not None and numeric_value > max_value:
        raise ValidationError(
            f"Value {numeric_value} is above maximum {max_value} for {field_name}",
            field_name=field_name,
            value=value,
        )

    return numeric_value


def validate_api_key_format(api_key: str, provider: str) -> bool:
    """
    Validate API key format for common providers.

    Args:
        api_key: API key to validate
        provider: Provider name (openai, anthropic, etc.)

    Returns:
        True if format looks valid

    Raises:
        ValidationError: If API key format is invalid
    """
    if not api_key or not isinstance(api_key, str):
        raise ValidationError(
            f"API key cannot be empty for {provider}",
            field_name="api_key",
            value=api_key,
        )

    # Basic format checks for common providers
    if provider.lower() == "openai":
        # OpenAI keys typically start with 'sk-'
        if not api_key.startswith("sk-"):
            raise ValidationError(
                f"OpenAI API key should start with 'sk-': {api_key}",
                field_name="api_key",
                value=api_key,
            )

    elif provider.lower() == "anthropic":
        # Anthropic keys typically start with 'sk-ant-'
        if not (api_key.startswith("sk-ant-") or api_key.startswith("sk-")):
            raise ValidationError(
                f"Anthropic API key format looks incorrect: {api_key}",
                field_name="api_key",
                value=api_key,
            )

    # Minimum length check
    if len(api_key) < 20:
        raise ValidationError(
            f"API key too short for {provider}: {api_key}",
            field_name="api_key",
            value=api_key,
        )

    return True
