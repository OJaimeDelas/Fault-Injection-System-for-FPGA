# FI Console Utilities

Interactive console and formatting utilities for the FI system.

## Files

- `sem_console.py`: Interactive SEM console (manual mode)
- `console_settings.py`: Color schemes and display styles
- `printing.py`: Formatted output helpers

## Formatted Output

Use `printing.py` for consistent console formatting:
```python
from fi.console.printing import print_header, print_section, print_key_value

# Large header
print_header("Campaign Starting")
# ================================================================================
#                            Campaign Starting
# ================================================================================

# Section divider
print_section("Configuration")
# --------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------

# Key-value pair
print_key_value("Board", "basys3")
#   Board                          basys3
```

## Interactive SEM Console

The SEM console (`sem_console.py`) provides manual control of the SEM
IP core for debugging and testing. Features:

- Direct SEM command execution
- Status monitoring
- Manual fault injection
- Cheat sheets and help

Launch with:
```bash
python -m fi.console.sem_console
```

## Console Settings

Configure appearance in `console_settings.py`:

- Color schemes
- Header styles
- Section dividers
- Prompt behavior

## Adding New Formatting

To add new formatting helpers:

1. Add function to `printing.py`
2. Use consistent 80-column width
3. Document with example in docstring
4. Update this README

## Usage Examples

### Campaign Output
```python
from fi.console.printing import print_header, print_section, print_key_value

print_header("FI Campaign")
print_section("Configuration")
print_key_value("Board", cfg.board_name)
print_key_value("Area Profile", cfg.area_profile)
print_key_value("Time Profile", cfg.time_profile)

# Output:
# ================================================================================
#                              FI Campaign
# ================================================================================
#
# --------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------
#   Board                          basys3
#   Area Profile                   modules
#   Time Profile                   uniform
```

### Progress Updates
```python
print_section("Injection Progress")
print(f"  {current}/{total} injections complete ({percent:.1f}%)")
print(f"  Success rate: {success_rate:.1f}%")
```