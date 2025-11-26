# =============================================================================
# FATORI-V • FI Console
# File: printing.py
# -----------------------------------------------------------------------------
# Formatted console output helpers.
#=============================================================================


def print_header(title: str):
    """
    Print formatted header to console.
    
    Creates a large header with the title centered between lines of equal signs.
    Used for major sections like campaign start.
    
    Args:
        title: Header title text
    
    Example:
        >>> print_header("Campaign Starting")
        
        ================================================================================
                                    Campaign Starting
        ================================================================================
    """
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def print_section(title: str):
    """
    Print section divider.
    
    Creates a smaller section header with the title above a line of dashes.
    Used for subsections within a campaign.
    
    Args:
        title: Section title
    
    Example:
        >>> print_section("Configuration")
        
        --------------------------------------------------------------------------------
        Configuration
        --------------------------------------------------------------------------------
    """
    print("\n" + "-" * 80)
    print(title)
    print("-" * 80)


def print_key_value(key: str, value: str):
    """
    Print key-value pair with consistent formatting.
    
    Left-aligns the key in a 30-character column, then prints the value.
    Used for displaying configuration parameters.
    
    Args:
        key: Left-aligned key name
        value: Right-aligned value
    
    Example:
        >>> print_key_value("Board", "basys3")
          Board                          basys3
        >>> print_key_value("Area Profile", "modules")
          Area Profile                   modules
    """
    print(f"  {key:<30} {value}")