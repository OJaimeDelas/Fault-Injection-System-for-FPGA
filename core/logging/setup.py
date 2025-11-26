# =============================================================================
# FATORI-V • FI Engine Logging Setup
# File: engine/logging_setup.py
# -----------------------------------------------------------------------------
# Setup logging infrastructure including log file and console output.
#=============================================================================

from pathlib import Path
from typing import Dict

from fi import fi_settings
from fi.core.logging import events as log_events


def setup_logging(cfg) -> Dict:
    """
    Setup logging infrastructure for the FI campaign.
    
    This function:
    1. Loads custom log config file if provided (overrides fi_settings)
    2. Creates log directory and opens log file
    3. Configures logging behavior based on Config settings
    4. Returns logging context with file path info
    
    Args:
        cfg: Config object with logging settings
        
    Returns:
        Dictionary with logging context (log file path, etc.)
    """
    # Load custom log config file if provided
    # This allows users to override LOG_MESSAGES settings per-run
    if hasattr(cfg, 'log_config_file') and cfg.log_config_file:
        _load_custom_log_config(cfg.log_config_file)
    
    # Use log settings from Config
    log_root = cfg.log_root_override or fi_settings.LOG_ROOT
    log_filename = cfg.log_filename
    
    # Setup log file (creates directory and opens file handle)
    log_events.setup_log_file(log_root, log_filename)
    
    # Configure log events module with Config settings
    # This allows events.py to access runtime config
    log_events.configure_logging(cfg)
    
    # Create logging context dictionary
    log_ctx = {
        'log_file_path': Path(log_root) / log_filename,
        'log_level': cfg.log_level if hasattr(cfg, 'log_level') else 'normal',
    }
    
    return log_ctx


def _load_custom_log_config(config_path: str):
    """
    Load custom log configuration from YAML file.
    
    The YAML file should contain message type keys (e.g., 'injection',
    'sem_command') mapping to dicts with 'enabled', 'to_file', and
    'to_console' boolean keys.
    
    Example YAML:
        injection:
          enabled: true
          to_file: true
          to_console: false
        
        sem_response:
          to_console: true
    
    Partial configs are supported - only specified keys are overridden.
    
    Args:
        config_path: Path to YAML configuration file
    """
    try:
        import yaml
        
        # Load YAML file
        with open(config_path, 'r') as f:
            custom_config = yaml.safe_load(f)
        
        if not isinstance(custom_config, dict):
            print(f"Warning: Log config file '{config_path}' did not contain a dictionary")
            print(f"Continuing with default log configuration")
            return
        
        # Merge custom config into LOG_MESSAGES
        # Only override keys that are explicitly specified
        for msg_type, overrides in custom_config.items():
            if msg_type not in fi_settings.LOG_MESSAGES:
                print(f"Warning: Unknown message type '{msg_type}' in log config file")
                continue
            
            if not isinstance(overrides, dict):
                print(f"Warning: Overrides for '{msg_type}' must be a dictionary")
                continue
            
            # Apply overrides for this message type
            fi_settings.LOG_MESSAGES[msg_type].update(overrides)
        
        print(f"[Logging] Loaded custom log config from: {config_path}")
        
    except FileNotFoundError:
        print(f"Warning: Log config file not found: {config_path}")
        print(f"Continuing with default log configuration")
    
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse YAML in log config file: {e}")
        print(f"Continuing with default log configuration")
    
    except Exception as e:
        print(f"Warning: Failed to load custom log config: {e}")
        print(f"Continuing with default log configuration")