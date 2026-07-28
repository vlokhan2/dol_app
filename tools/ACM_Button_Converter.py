import streamlit as st
import re

# --- Core conversion functions (from acm_button_converter.py) ---

def detect_platform(xml_content: str) -> str:
    """Detect SE or ME from linkBaseObject attribute."""
    if 'linkBaseObject="(raC-4-SE)' in xml_content:
        return "SE"
    elif 'linkBaseObject="(raC-4-ME)' in xml_content:
        return "ME"
    # Fallback patterns
    if "(raC-4-SE)" in xml_content:
        return "SE"
    elif "(raC-4-ME)" in xml_content:
        return "ME"
    return "Unknown"


def extract_element_names(xml_content: str) -> list:
    """Extract all group/button element names from XML for user display."""
    pattern = r'<(group|button|gotoButton)\s+name="([^"]+)"'
    matches = re.findall(pattern, xml_content)
    return [(elem_type, name) for elem_type, name in matches]


def extract_button_groups(xml_content: str) -> list:
    """
    Extract group names that are direct children of <gfx> and have 
    linkBaseObject containing 'Graphic Symbols'.
    These are the actual button groups (Icon or Text style).
    Returns list of group names.
    """
    # Find content directly under <gfx> tag - first level groups only
    # Match <gfx ...> then find <group> tags at the first level
    gfx_match = re.search(r'<gfx[^>]*>(.*)</gfx>', xml_content, re.DOTALL)
    if not gfx_match:
        return []
    
    gfx_content = gfx_match.group(1)
    
    # Find groups at the top level of gfx content that have Graphic Symbols linkBaseObject
    # We need to find <group> tags that are not nested inside other groups
    # Simple approach: find all <group ...> that appear right after <gfx> or after </group>
    
    # Split by </group> and look for <group at start of each section
    button_groups = []
    
    # Pattern to match top-level group with Graphic Symbols linkBaseObject
    # Look for <group name="..." ... linkBaseObject="..Graphic Symbols.." at the start or after newlines
    pattern = r'^\s*<group\s+name="([^"]+)"[^>]*linkBaseObject="\(raC-4-(?:SE|ME)\)\s*Graphic Symbols[^"]*"'
    
    # Find all matches - we'll look at lines that start a group
    lines = gfx_content.split('\n')
    depth = 0
    for line in lines:
        # Track depth
        depth += line.count('<group ') + line.count('<group>')
        depth -= line.count('</group>')
        
        # Only look at depth 0 (direct children of gfx)
        if depth == 1:  # Just entered a group
            match = re.search(r'<group\s+name="([^"]+)"[^>]*linkBaseObject="\(raC-4-(?:SE|ME)\)\s*Graphic Symbols[^"]*"', line, re.IGNORECASE)
            if match:
                button_groups.append(match.group(1))
    
    return button_groups


def extract_group_xml(xml_content: str, group_name: str) -> str:
    """
    Extract the full XML of a specific group by name (from <group name="..."> to </group>).
    Returns only that group's XML content.
    """
    # Escape special regex chars in group_name
    escaped_name = re.escape(group_name)
    
    # Find the start of this group
    start_pattern = rf'<group\s+name="{escaped_name}"[^>]*>'
    start_match = re.search(start_pattern, xml_content)
    if not start_match:
        return ""
    
    start_pos = start_match.start()
    
    # Now find the matching </group> by counting depth
    content_after_start = xml_content[start_pos:]
    depth = 0
    i = 0
    while i < len(content_after_start):
        # Check for <group (opening)
        if content_after_start[i:i+6] == '<group':
            # Make sure it's a tag start, not text
            rest = content_after_start[i+6:]
            if rest and (rest[0] == ' ' or rest[0] == '>'):
                depth += 1
        # Check for </group>
        elif content_after_start[i:i+8] == '</group>':
            depth -= 1
            if depth == 0:
                # Found the closing tag
                end_pos = i + 8
                return content_after_start[:end_pos]
        i += 1
    
    return ""


def find_base_position(xml_content: str) -> tuple:
    button_match = re.search(r'<(?:button|gotoButton)[^>]+left="(\d+)"[^>]+top="(\d+)"', xml_content)
    if button_match:
        return int(button_match.group(1)), int(button_match.group(2))
    left_values = [int(m) for m in re.findall(r'\bleft="(\d+)"', xml_content)]
    top_values = [int(m) for m in re.findall(r'\btop="(\d+)"', xml_content)]
    if left_values and top_values:
        return min(left_values), min(top_values)
    return 0, 0


def add_object_name_prefix(xml_content: str) -> str:
    def replace_name(match):
        element_type = match.group(1)
        name_value = match.group(2)
        rest = match.group(3)
        if name_value.startswith("{ObjectName}_"):
            return match.group(0)
        return f'<{element_type} name="{{ObjectName}}_{name_value}"{rest}'

    pattern = r'<(group|button|gotoButton|text|image|numericDisplay|multistateIndicator)\s+name="([^"]+)"([^>]*)'
    return re.sub(pattern, replace_name, xml_content)


def convert_positions(xml_content: str, base_left: int, base_top: int) -> str:
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

    result = re.sub(r'(\s)left="(\d+)"', convert_left, xml_content)
    result = re.sub(r'(\s)top="(\d+)"', convert_top, result)
    return result


def update_parameters(xml_content: str, scope: str, platform: str = "SE") -> str:
    if platform == "ME":
        if scope.lower() == "program":
            new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPathME}Program:{ProgramName}.{TagName}}"/>'
        else:
            new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPathME}{TagName}}"/>'
    else:
        if scope.lower() == "program":
            new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPath}Program:{ProgramName}.{TagName}}"/>'
        else:
            new_param = '<parameter name="#102" description="Add-On Instruction Backing Tag" value="{{AreaPath}{TagName}}"/>'
    return re.sub(r'<parameter\s+name="#102"[^/]*/>', new_param, xml_content)


def format_xml(xml_content: str) -> str:
    result = xml_content.replace('\r\n', '\n')
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
    return result.strip()


def convert_button_xml(xml_content: str, scope: str = "program", base_offset: tuple = None) -> dict:
    platform = detect_platform(xml_content)
    if base_offset:
        base_left, base_top = base_offset
    else:
        base_left, base_top = find_base_position(xml_content)

    result = xml_content
    result = add_object_name_prefix(result)
    result = convert_positions(result, base_left, base_top)
    result = update_parameters(result, scope, platform)
    result = format_xml(result)

    return {
        "platform": platform,
        "scope": scope.capitalize(),
        "base_left": base_left,
        "base_top": base_top,
        "converted_xml": result
    }


def main():
    st.title("ACM Launch Buttons Attachments Generator")

    st.markdown("""
    ### How to use
    1. **In FactoryTalk View Studio:** Create a blank display for SE or ME.
    2. **Add button instances:** Place one **Icon** button and one **Text** button on the display.
    3. **Export to XML:** Export the display to XML format.
    4. **Upload here:** Upload the exported `.xml` file(s).
    5. The tool auto-detects **Platform** (SE/ME) from `linkBaseObject`.
    6. Review the detected button groups and **select which is Icon style and which is Text style**.
    7. Click **Generate** to create Program and Controller scope versions.
    8. Copy the XML block you need and paste it into **SCM Library Designer**.
    """)

    uploaded_files = st.file_uploader(
        "Upload button XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="btn_converter_upload",
    )

    if not uploaded_files:
        st.info("Upload one or more button XML files to get started.")
        return

    # Parse each file
    file_data = []  # list of {name, content, platform, button_groups}
    for uf in uploaded_files:
        raw = uf.read().decode("utf-8")
        platform = detect_platform(raw)
        button_groups = extract_button_groups(raw)
        file_data.append({
            "name": uf.name,
            "content": raw,
            "platform": platform,
            "button_groups": button_groups,
        })

    # Show detected info for each file
    st.markdown("---")
    st.markdown("### Detected Files")

    for i, fd in enumerate(file_data):
        with st.expander(f"**{fd['name']}** — Platform: **{fd['platform']}**", expanded=True):
            if fd["button_groups"]:
                st.caption(f"Found {len(fd['button_groups'])} button group(s) with `linkBaseObject` containing 'Graphic Symbols':")
                for grp in fd["button_groups"]:
                    st.markdown(f"- `{grp}`")
            else:
                st.warning("No button groups with 'Graphic Symbols' linkBaseObject found")

    # User assigns style to each button group
    st.markdown("---")
    st.markdown("### Assign Style to Each Button Group")
    st.caption("Select whether each button group is **Icon** style or **Text** style.")

    # Build a flat list of all button groups across files for assignment
    all_groups = []  # list of (file_index, group_name, platform)
    for i, fd in enumerate(file_data):
        for grp in fd["button_groups"]:
            all_groups.append((i, grp, fd["platform"]))

    if not all_groups:
        st.warning("No button groups detected. Please upload XML files containing groups with `linkBaseObject` referencing 'Graphic Symbols'.")
        return

    group_styles = {}  # (file_index, group_name) -> style
    for idx, (file_idx, grp_name, platform) in enumerate(all_groups):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{grp_name}** ({platform})")
        with col2:
            style = st.selectbox(
                "Style",
                options=["Icon", "Text"],
                key=f"grp_style_{idx}",
                label_visibility="collapsed",
            )
            group_styles[(file_idx, grp_name)] = style

    # Generate button
    st.markdown("---")
    if st.button("Generate Converted XML", type="primary", key="btn_generate"):
        # Group by (platform, style) -> collect only the group XML (not full file)
        source_map = {}  # (platform, style) -> group_xml
        for (file_idx, grp_name), style in group_styles.items():
            fd = file_data[file_idx]
            platform = fd["platform"]
            key = (platform, style)
            # Extract only the group XML, not the full file content
            group_xml = extract_group_xml(fd["content"], grp_name)
            if group_xml:
                source_map[key] = group_xml

        # Generate outputs
        st.markdown("### Converted XML Blocks")
        st.caption("Copy any block below and paste directly into SCM Library Designer.")

        for platform in ("SE", "ME"):
            platform_has_data = any(k[0] == platform for k in source_map.keys())
            if not platform_has_data:
                continue

            st.markdown(f"#### {platform}")

            for style in ("Icon", "Text"):
                key = (platform, style)
                if key not in source_map:
                    continue

                content = source_map[key]
                st.markdown(f"##### {platform} — {style}")

                col_prog, col_ctrl = st.columns(2)

                # Program scope
                r_prog = convert_button_xml(content, "program")
                include_cond_prog = f"'{{TagScope}}' = 'Program' AND '{{Symbol_style}}' = '{style}'"
                with col_prog:
                    st.markdown("**Program Scope**")
                    st.caption(f"Include: `{include_cond_prog}`")
                    st.code(r_prog["converted_xml"], language="xml")

                # Controller scope
                r_ctrl = convert_button_xml(content, "controller")
                include_cond_ctrl = f"'{{TagScope}}' = 'Controller' AND '{{Symbol_style}}' = '{style}'"
                with col_ctrl:
                    st.markdown("**Controller Scope**")
                    st.caption(f"Include: `{include_cond_ctrl}`")
                    st.code(r_ctrl["converted_xml"], language="xml")

                st.markdown("---")


if __name__ == "__main__":
    main()
