"""
ACM Button XML Converter
========================
Converts FactoryTalk View SE/ME button XML to ACM template format.

Usage:
    python acm_button_converter.py input.xml [--scope program|controller] [--output output.xml]
    
Or run interactively:
    python acm_button_converter.py
"""

import re
import sys
import argparse
from pathlib import Path


def detect_platform(xml_content: str) -> str:
    """Detect if XML is for SE or ME based on linkBaseObject references."""
    if "(raC-4-SE)" in xml_content:
        return "SE"
    elif "(raC-4-ME)" in xml_content:
        return "ME"
    else:
        # Fallback: check for SE-specific elements
        if 'exposeToVba=' in xml_content or '<command pressAction=' in xml_content:
            return "SE"
        return "ME"


def detect_style(xml_content: str) -> str:
    """Detect if XML is Icon or Text style based on content."""
    # Icon style has device image and FLA display
    if 'imageName="raC_Dvc_' in xml_content or 'grp_FLA' in xml_content or 'nd_FLA' in xml_content:
        return "Icon"
    # Text style is simpler with just button and labels
    return "Text"


def find_base_position(xml_content: str) -> tuple:
    """
    Find the minimum left/top values to use as base offset.
    Returns (min_left, min_top) from the main button element.
    """
    # Look for the main button/gotoButton position
    button_match = re.search(r'<(?:button|gotoButton)[^>]+left="(\d+)"[^>]+top="(\d+)"', xml_content)
    if button_match:
        return int(button_match.group(1)), int(button_match.group(2))
    
    # Fallback: find minimum values
    left_values = [int(m) for m in re.findall(r'\bleft="(\d+)"', xml_content)]
    top_values = [int(m) for m in re.findall(r'\btop="(\d+)"', xml_content)]
    
    if left_values and top_values:
        return min(left_values), min(top_values)
    return 0, 0


def add_object_name_prefix(xml_content: str) -> str:
    """Add {ObjectName}_ prefix to all element name attributes."""
    
    # Pattern to match name="..." but not other attributes like imageName, parameterName, etc.
    # We want to match: name="ElementName" at the start of element definitions
    
    def replace_name(match):
        element_type = match.group(1)
        name_value = match.group(2)
        rest = match.group(3)
        
        # Don't prefix if already has {ObjectName}
        if name_value.startswith("{ObjectName}_"):
            return match.group(0)
        
        return f'<{element_type} name="{{ObjectName}}_{name_value}"{rest}'
    
    # Match element declarations with name attribute
    pattern = r'<(group|button|gotoButton|text|image|numericDisplay|multistateIndicator)\s+name="([^"]+)"([^>]*)'
    
    result = re.sub(pattern, replace_name, xml_content)
    return result


def convert_positions(xml_content: str, base_left: int, base_top: int) -> str:
    """Convert absolute positions to {Calc(...)} expressions."""
    
    def convert_left(match):
        prefix = match.group(1)
        value = int(match.group(2))
        offset = value - base_left
        return f'{prefix}left="{{Calc({offset} + {{SymbolWidth}}*{{LeftIndex}})}}"'
    
    def convert_top(match):
        prefix = match.group(1)
        value = int(match.group(2))
        offset = value - base_top
        return f'{prefix}top="{{Calc({offset} + {{SymbolHeight}}*{{TopIndex}})}}"'
    
    # Convert left positions (avoid matching inside expressions)
    result = re.sub(r'(\s)left="(\d+)"', convert_left, xml_content)
    
    # Convert top positions
    result = re.sub(r'(\s)top="(\d+)"', convert_top, result)
    
    return result


def update_parameters(xml_content: str, scope: str) -> str:
    """Update parameter #102 with proper ACM template variables."""
    
    if scope.lower() == "program":
        new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPath}}Program:{ProgramName}.{TagName}"/>'
    else:  # controller
        new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPath}}{TagName}"/>'
    
    # Replace existing #102 parameter
    result = re.sub(
        r'<parameter\s+name="#102"[^/]*/>', 
        new_param, 
        xml_content
    )
    
    return result


def format_xml(xml_content: str) -> str:
    """Clean up XML formatting."""
    # Ensure consistent newlines
    result = xml_content.replace('\r\n', '\n')
    
    # Remove extra blank lines
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
    
    return result.strip()


def convert_button_xml(xml_content: str, scope: str = "program", base_offset: tuple = None) -> dict:
    """
    Main conversion function.
    
    Args:
        xml_content: Raw button XML from FactoryTalk View
        scope: "program" or "controller" for tag scope
        base_offset: Optional (left, top) tuple for custom base position
    
    Returns:
        Dictionary with conversion results and metadata
    """
    
    # Detect platform and style
    platform = detect_platform(xml_content)
    style = detect_style(xml_content)
    
    # Find base position
    if base_offset:
        base_left, base_top = base_offset
    else:
        base_left, base_top = find_base_position(xml_content)
    
    # Apply transformations
    result = xml_content
    result = add_object_name_prefix(result)
    result = convert_positions(result, base_left, base_top)
    result = update_parameters(result, scope)
    result = format_xml(result)
    
    return {
        "platform": platform,
        "style": style,
        "scope": scope.capitalize(),
        "base_left": base_left,
        "base_top": base_top,
        "include_condition": f"'{{TagScope}}' = '{scope.capitalize()}' AND '{{Symbol_style}}' = '{style}'",
        "converted_xml": result
    }


def convert_file(input_path: str, scope: str = "program", output_path: str = None):
    """Convert an XML file and optionally save output."""
    
    with open(input_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    result = convert_button_xml(xml_content, scope)
    
    # Print info
    print(f"\n{'='*60}")
    print(f"Platform: {result['platform']}")
    print(f"Style: {result['style']}")
    print(f"Scope: {result['scope']}")
    print(f"Base Position: left={result['base_left']}, top={result['base_top']}")
    print(f"Include Condition: {result['include_condition']}")
    print(f"{'='*60}\n")
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result['converted_xml'])
        print(f"Output saved to: {output_path}")
    else:
        print("Converted XML:")
        print("-" * 60)
        print(result['converted_xml'])
    
    return result


def interactive_mode():
    """Run in interactive mode for pasting XML directly."""
    
    print("\n" + "="*60)
    print("ACM Button XML Converter - Interactive Mode")
    print("="*60)
    print("\nPaste your button XML below, then press Enter twice when done:")
    print("(Or type 'quit' to exit)\n")
    
    while True:
        lines = []
        empty_count = 0
        
        while empty_count < 2:
            try:
                line = input()
            except EOFError:
                break
            
            if line.lower() == 'quit':
                print("Goodbye!")
                return
            
            if line.strip() == '':
                empty_count += 1
            else:
                empty_count = 0
                lines.append(line)
        
        if not lines:
            continue
        
        xml_content = '\n'.join(lines)
        
        # Ask for scope
        print("\nSelect tag scope:")
        print("  1. Program (default)")
        print("  2. Controller")
        scope_input = input("Choice [1]: ").strip()
        scope = "controller" if scope_input == "2" else "program"
        
        # Convert
        try:
            result = convert_button_xml(xml_content, scope)
            
            print(f"\n{'='*60}")
            print(f"Platform: {result['platform']}")
            print(f"Style: {result['style']}")
            print(f"Scope: {result['scope']}")
            print(f"Base Position: left={result['base_left']}, top={result['base_top']}")
            print(f"\nInclude Condition:")
            print(f"  {result['include_condition']}")
            print(f"{'='*60}")
            print("\nConverted XML:\n")
            print(result['converted_xml'])
            print(f"\n{'='*60}")
            
            # Ask to save
            save = input("\nSave to file? (Enter filename or press Enter to skip): ").strip()
            if save:
                with open(save, 'w', encoding='utf-8') as f:
                    f.write(result['converted_xml'])
                print(f"Saved to: {save}")
            
        except Exception as e:
            print(f"\nError: {e}")
        
        print("\n" + "-"*60)
        print("Paste another XML or type 'quit' to exit:\n")


def batch_convert(xml_content: str) -> dict:
    """
    Convert a single XML to both Program and Controller scope versions.
    Returns dict with both versions.
    """
    program_result = convert_button_xml(xml_content, "program")
    controller_result = convert_button_xml(xml_content, "controller")
    
    return {
        "platform": program_result["platform"],
        "style": program_result["style"],
        "program_scope": program_result["converted_xml"],
        "controller_scope": controller_result["converted_xml"],
        "program_condition": program_result["include_condition"],
        "controller_condition": controller_result["include_condition"]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert FactoryTalk View button XML to ACM template format"
    )
    parser.add_argument(
        "input", 
        nargs="?", 
        help="Input XML file path (omit for interactive mode)"
    )
    parser.add_argument(
        "--scope", "-s",
        choices=["program", "controller"],
        default="program",
        help="Tag scope: program or controller (default: program)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (optional)"
    )
    parser.add_argument(
        "--both", "-b",
        action="store_true",
        help="Generate both Program and Controller scope versions"
    )
    
    args = parser.parse_args()
    
    if args.input:
        if args.both:
            with open(args.input, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            result = batch_convert(xml_content)
            
            print(f"\nPlatform: {result['platform']}")
            print(f"Style: {result['style']}")
            
            print(f"\n{'='*60}")
            print(f"PROGRAM SCOPE")
            print(f"Condition: {result['program_condition']}")
            print(f"{'='*60}")
            print(result['program_scope'])
            
            print(f"\n{'='*60}")
            print(f"CONTROLLER SCOPE")
            print(f"Condition: {result['controller_condition']}")
            print(f"{'='*60}")
            print(result['controller_scope'])
        else:
            convert_file(args.input, args.scope, args.output)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
