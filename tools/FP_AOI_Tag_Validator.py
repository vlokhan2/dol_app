import streamlit as st
import lxml.etree as ET
import pandas as pd
import re
import os
import glob
from collections import defaultdict


def parse_aoi_tags(aoi_content):
    """
    Parse an unlocked AOI L5X file and extract:
    - Parameters (Name, Usage, DataType, ExternalAccess, Dimensions, TagType, AliasFor)
    - LocalTags (Name, DataType, ExternalAccess, Dimensions)
    - UDT member definitions (DataType -> list of members with access info)
    Returns (parameters_dict, local_tags_dict, udt_members_dict)
    """
    parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
    root = ET.fromstring(aoi_content, parser=parser)

    parameters = {}
    local_tags = {}
    udt_members = {}  # DataType name -> { member_name: {DataType, ExternalAccess, Dimensions, Hidden, ...} }

    # Parse DataType definitions (UDTs) for member lookup
    for dt in root.iter("DataType"):
        dt_name = dt.attrib.get("Name", "")
        if not dt_name:
            continue
        members = {}
        for member in dt.findall(".//Members/Member"):
            m_name = member.attrib.get("Name", "")
            if not m_name:
                continue
            hidden = member.attrib.get("Hidden", "false").lower() == "true"
            members[m_name] = {
                "DataType": member.attrib.get("DataType", ""),
                "ExternalAccess": member.attrib.get("ExternalAccess", "Read/Write"),
                "Dimension": member.attrib.get("Dimension", "0"),
                "Hidden": hidden,
                "Radix": member.attrib.get("Radix", ""),
                "Target": member.attrib.get("Target", ""),
                "BitNumber": member.attrib.get("BitNumber", ""),
            }
        udt_members[dt_name] = members

    # Find the AddOnInstructionDefinition
    aoi_def = root.find(".//AddOnInstructionDefinition[@Use='Target']")
    if aoi_def is None:
        # Fallback: try any AddOnInstructionDefinition
        aoi_def = root.find(".//AddOnInstructionDefinition")

    if aoi_def is None:
        return parameters, local_tags, udt_members

    aoi_name = aoi_def.attrib.get("Name", "Unknown")

    # Parse Parameters
    for param in aoi_def.findall(".//Parameters/Parameter"):
        name = param.attrib.get("Name", "")
        if not name:
            continue
        parameters[name] = {
            "Name": name,
            "TagType": param.attrib.get("TagType", "Base"),
            "DataType": param.attrib.get("DataType", ""),
            "Usage": param.attrib.get("Usage", ""),
            "ExternalAccess": param.attrib.get("ExternalAccess", "None"),
            "Dimensions": param.attrib.get("Dimensions", ""),
            "Required": param.attrib.get("Required", "false"),
            "Visible": param.attrib.get("Visible", "true"),
            "AliasFor": param.attrib.get("AliasFor", ""),
            "Constant": param.attrib.get("Constant", "false"),
            "Source": "Parameter",
        }

    # Parse LocalTags
    for ltag in aoi_def.findall(".//LocalTags/LocalTag"):
        name = ltag.attrib.get("Name", "")
        if not name:
            continue
        local_tags[name] = {
            "Name": name,
            "DataType": ltag.attrib.get("DataType", ""),
            "ExternalAccess": ltag.attrib.get("ExternalAccess", "None"),
            "Dimensions": ltag.attrib.get("Dimensions", ""),
            "Radix": ltag.attrib.get("Radix", ""),
            "Source": "LocalTag",
        }

    return parameters, local_tags, udt_members


def extract_fp_tag_references(fp_content):
    """
    Parse an FP (Faceplate) XML file and extract all tag references.
    Looks for patterns like:
      {#N.TagName}
      {#N.TagName[index]}
      {#N.TagName[index].Member}
      {#N.TagName.Member}
      #N.TagName (in caption text like /*N:2 #N.TagName*/)
      {#N.@Description} (display property references)
    Returns a list of dicts with: raw_ref, param_number, root_tag, member_path, location_info
    """
    text = fp_content if isinstance(fp_content, str) else fp_content.decode("utf-8", errors="replace")

    references = []
    seen = set()

    # Pattern 1: {#N.TagPath} - curly brace references
    # Captures: {#2.HMI_Tab}, {#2.Sts_Eventlist[#201].Component_Type}, etc.
    pattern_curly = re.compile(
        r'\{#(\d+)\.([A-Za-z_@][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)*)\}'
    )

    # Pattern 2: #N.TagPath in caption text (without curly braces)
    # e.g. /*N:2 #2.Sts_Eventlist[#201].EventTime_D[0] ...*/
    # or /*S:0 {#2.Tag}*/
    pattern_caption = re.compile(
        r'(?<!\{)#(\d+)\.([A-Za-z_@][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)*)'
    )

    for m in pattern_curly.finditer(text):
        param_num = m.group(1)
        tag_path = m.group(2)
        raw = m.group(0)
        key = (param_num, tag_path)
        if key not in seen:
            seen.add(key)
            root_tag, member_path = _split_tag_path(tag_path)
            references.append({
                "raw_ref": raw,
                "param_number": param_num,
                "root_tag": root_tag,
                "member_path": member_path,
                "full_path": tag_path,
            })

    for m in pattern_caption.finditer(text):
        param_num = m.group(1)
        tag_path = m.group(2)
        key = (param_num, tag_path)
        if key not in seen:
            seen.add(key)
            root_tag, member_path = _split_tag_path(tag_path)
            references.append({
                "raw_ref": f"#{param_num}.{tag_path}",
                "param_number": param_num,
                "root_tag": root_tag,
                "member_path": member_path,
                "full_path": tag_path,
            })

    return references


def _split_tag_path(tag_path):
    """
    Split a tag path like 'Sts_Eventlist[#201].Component_Type' into:
      root_tag = 'Sts_Eventlist'
      member_path = 'Component_Type'
    Or 'HMI_Tab' -> ('HMI_Tab', '')
    Or 'Sts_Eventlist[#201].EventTime_D[3]' -> ('Sts_Eventlist', 'EventTime_D')
    """
    # Remove array indices for root extraction
    # Split on first '.' after removing leading array index from root
    clean = re.sub(r'\[[^\]]*\]', '', tag_path)
    parts = clean.split('.')
    root_tag = parts[0]
    member_path = '.'.join(parts[1:]) if len(parts) > 1 else ''
    return root_tag, member_path


def extract_optix_tag_references(yaml_files_content):
    """
    Extract tag references from Optix YAML files.
    Optix uses slash-separated paths like:
      Ref_Tag/TagName
      Ref_Tag/TagName[{index}]/Member
      Ref_Tag/TagName@NodeId  (property suffix stripped)
    Also via relative paths like:
      ../../Ref_Tag/TagName
    Returns list of dicts matching the same format as extract_fp_tag_references.
    """
    references = []
    seen = set()

    # Pattern: Ref_Tag/TagName or Ref_Tag/TagName[...]/Member...
    # Captures everything after Ref_Tag/
    pattern = re.compile(
        r'Ref_Tag/([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:/[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)*)'
    )

    for file_name, content in yaml_files_content:
        for m in pattern.finditer(content):
            raw_path = m.group(1)
            # Strip property suffixes like @NodeId, @BrowseName
            clean_path = re.sub(r'@\w+$', '', raw_path)
            if not clean_path:
                continue

            # Convert slash-separated to dot-separated for consistency
            # e.g. Sts_Sort_Data[{0}]/Component_Type -> Sts_Sort_Data[{0}].Component_Type
            dot_path = clean_path.replace('/', '.')

            key = dot_path
            if key in seen:
                continue
            seen.add(key)

            root_tag, member_path = _split_tag_path(dot_path)

            # Skip Description (it's a built-in display property, not an AOI tag)
            if root_tag == "Description":
                references.append({
                    "raw_ref": f"Ref_Tag/{raw_path}",
                    "param_number": "-",
                    "root_tag": root_tag,
                    "member_path": member_path or "-",
                    "full_path": dot_path,
                })
                continue

            references.append({
                "raw_ref": f"Ref_Tag/{raw_path}",
                "param_number": "-",
                "root_tag": root_tag,
                "member_path": member_path,
                "full_path": dot_path,
            })

    return references


def validate_tags(parameters, local_tags, udt_members, fp_references):
    """
    Validate FP tag references against AOI parameters and local tags.
    Returns a list of validation results.
    """
    results = []
    # Merge parameters and local tags for lookup
    all_tags = {}
    for name, info in parameters.items():
        all_tags[name] = info
    for name, info in local_tags.items():
        all_tags[name] = info

    # Case-insensitive lookup map
    tag_lookup = {k.lower(): (k, v) for k, v in all_tags.items()}

    for ref in fp_references:
        root_tag = ref["root_tag"]
        member_path = ref["member_path"]
        full_path = ref["full_path"]
        raw_ref = ref["raw_ref"]

        # Skip display property references like @Description
        if root_tag.startswith("@"):
            results.append({
                "FP Reference": raw_ref,
                "Root Tag": root_tag,
                "Member Path": member_path or "-",
                "Status": "SKIP",
                "Details": "Display property reference (not an AOI tag)",
                "AOI Source": "-",
                "ExternalAccess": "-",
                "Usage": "-",
            })
            continue

        # Look up root tag (case-insensitive to catch case mismatches)
        root_lower = root_tag.lower()
        if root_lower in tag_lookup:
            actual_name, tag_info = tag_lookup[root_lower]
            source = tag_info.get("Source", "Unknown")
            ext_access = tag_info.get("ExternalAccess", "None")
            usage = tag_info.get("Usage", "-")
            data_type = tag_info.get("DataType", "")

            # Check case mismatch
            case_mismatch = (actual_name != root_tag)

            # Check external access for HMI usage
            access_issue = ""
            if ext_access == "None":
                access_issue = "ExternalAccess is None - NOT accessible from HMI"
            elif source == "LocalTag" and ext_access not in ("Read Only", "Read/Write"):
                access_issue = f"ExternalAccess={ext_access} - may not be accessible from HMI"

            # Validate member path if present
            member_issue = ""
            if member_path:
                member_issue = _validate_member_path(data_type, member_path, udt_members)

            # Determine overall status
            if access_issue:
                status = "ACCESS ERROR"
                details = access_issue
            elif member_issue:
                status = "MEMBER ERROR"
                details = member_issue
            elif case_mismatch:
                status = "CASE MISMATCH"
                details = f"FP uses '{root_tag}' but AOI defines '{actual_name}'"
            else:
                status = "OK"
                details = "Tag found in AOI with valid access"

            results.append({
                "FP Reference": raw_ref,
                "Root Tag": root_tag,
                "Member Path": member_path or "-",
                "Status": status,
                "Details": details,
                "AOI Source": source,
                "ExternalAccess": ext_access,
                "Usage": usage,
            })
        else:
            results.append({
                "FP Reference": raw_ref,
                "Root Tag": root_tag,
                "Member Path": member_path or "-",
                "Status": "MISSING",
                "Details": "Tag NOT found in AOI (not a Parameter or accessible LocalTag)",
                "AOI Source": "-",
                "ExternalAccess": "-",
                "Usage": "-",
            })

    return results


def _validate_member_path(data_type, member_path, udt_members):
    """
    Validate that a member path exists in the UDT definition.
    Returns empty string if valid, or error message if not.
    """
    if not data_type or not member_path:
        return ""

    # Walk the member path
    current_type = data_type
    parts = member_path.split('.')

    for part in parts:
        # Remove array index if present
        clean_part = re.sub(r'\[[^\]]*\]', '', part)
        if not clean_part:
            continue

        if current_type not in udt_members:
            # Primitive type or unknown UDT - can't validate further
            return ""

        members = udt_members[current_type]
        # Case-insensitive member lookup
        member_lower_map = {k.lower(): k for k in members}
        if clean_part.lower() in member_lower_map:
            actual_member = member_lower_map[clean_part.lower()]
            member_info = members[actual_member]
            if member_info.get("Hidden", False):
                return f"Member '{clean_part}' is Hidden in UDT '{current_type}'"
            current_type = member_info.get("DataType", "")
        else:
            return f"Member '{clean_part}' not found in UDT '{current_type}'"

    return ""


def main():
    st.markdown(
        """
        <h2 style="color: #2c3e50; font-family: Arial, sans-serif;">
            Faceplate vs AOI Tag Validator
        </h2>
        <hr style="border: 1px solid #f0f2f6;">
        """,
        unsafe_allow_html=True
    )

    st.markdown("""
    This tool validates that all tag references used in a **Faceplate** file actually exist
    in the corresponding **AOI (L5X)** file with correct access permissions.

    **Supported Platforms:**
    - **SE / ME** — Upload the Faceplate XML file
    - **Optix** — Upload all YAML files from the Optix faceplate folder

    **What it checks:**
    - All tag references in the FP are present as Parameters or accessible LocalTags in the AOI
    - ExternalAccess is not `None` (which would make the tag invisible to HMI)
    - UDT member paths (e.g., `.Component_Type`, `.EventTime_D`) exist in the UDT definition
    - Case mismatches between FP references and AOI tag names
    """)

    st.markdown("---")

    # Platform selection
    platform = st.radio(
        "Select Faceplate Platform",
        options=["SE / ME (XML)", "Optix (YAML)"],
        horizontal=True,
        key="fp_platform",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Upload AOI File (.L5X)")
        aoi_file = st.file_uploader(
            "Upload the unlocked AOI L5X file",
            type=["l5x", "L5X"],
            key="aoi_upload",
            help="The exported/unlocked Add-On Instruction definition file"
        )

    with col2:
        if platform == "SE / ME (XML)":
            st.markdown("### Upload Faceplate File (.xml)")
            fp_file = st.file_uploader(
                "Upload the Faceplate XML file",
                type=["xml", "XML"],
                key="fp_upload",
                help="The SE/ME Faceplate display XML file"
            )
            optix_folder = None
        else:
            st.markdown("### Optix Faceplate Folder")
            optix_folder = st.text_input(
                "Paste the full path to the Optix faceplate folder",
                key="optix_folder",
                placeholder=r"e.g. C:\Projects\PMv11",
                help="The root folder of the Optix faceplate project. All .yaml files inside will be scanned recursively."
            )
            fp_file = None

    # Determine if we have enough to proceed
    has_fp_input = (platform == "SE / ME (XML)" and fp_file) or (platform == "Optix (YAML)" and optix_folder)

    if aoi_file and has_fp_input:
        st.markdown("---")

        try:
            aoi_content = aoi_file.read()

            with st.spinner("Parsing AOI file..."):
                parameters, local_tags, udt_members = parse_aoi_tags(aoi_content)

            with st.spinner("Extracting FP tag references..."):
                if platform == "SE / ME (XML)":
                    fp_content = fp_file.read()
                    fp_references = extract_fp_tag_references(fp_content)
                    source_label = f"Faceplate XML: {fp_file.name}"
                else:
                    # Scan Optix folder for all YAML files
                    folder = optix_folder.strip().strip('"').strip("'")
                    if not os.path.isdir(folder):
                        st.error(f"Folder not found: {folder}")
                        return
                    yaml_paths = glob.glob(os.path.join(folder, "**", "*.yaml"), recursive=True)
                    yaml_paths += glob.glob(os.path.join(folder, "**", "*.yml"), recursive=True)
                    if not yaml_paths:
                        st.error("No .yaml/.yml files found in the specified folder.")
                        return
                    yaml_contents = []
                    for yp in yaml_paths:
                        with open(yp, "r", encoding="utf-8", errors="replace") as f:
                            yaml_contents.append((os.path.basename(yp), f.read()))
                    fp_references = extract_optix_tag_references(yaml_contents)
                    source_label = f"Optix folder: {folder} ({len(yaml_paths)} YAML files scanned)"

            # Display AOI summary
            st.markdown("### AOI Summary")
            st.caption(source_label)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Parameters", len(parameters))
            with col_b:
                accessible_locals = sum(
                    1 for lt in local_tags.values()
                    if lt.get("ExternalAccess", "None") != "None"
                )
                st.metric("Accessible Local Tags", f"{accessible_locals} / {len(local_tags)}")
            with col_c:
                st.metric("UDT Definitions", len(udt_members))

            st.markdown(f"**FP Tag References Found:** {len(fp_references)}")

            if not fp_references:
                st.warning("No tag references found in the Faceplate file(s).")
                return

            # Validate
            with st.spinner("Validating tags..."):
                results = validate_tags(parameters, local_tags, udt_members, fp_references)

            # Summary counts
            status_counts = defaultdict(int)
            for r in results:
                status_counts[r["Status"]] += 1

            st.markdown("### Validation Results")

            # Status summary
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("OK", status_counts.get("OK", 0))
            with col2:
                st.metric("Missing", status_counts.get("MISSING", 0))
            with col3:
                st.metric("Access Errors", status_counts.get("ACCESS ERROR", 0))
            with col4:
                st.metric("Member Errors", status_counts.get("MEMBER ERROR", 0))
            with col5:
                st.metric("Case Mismatches", status_counts.get("CASE MISMATCH", 0))

            # Build DataFrame
            df = pd.DataFrame(results)

            # Filter options
            st.markdown("### Filter Results")
            status_filter = st.multiselect(
                "Filter by Status",
                options=sorted(df["Status"].unique()),
                default=[s for s in ["MISSING", "ACCESS ERROR", "MEMBER ERROR", "CASE MISMATCH"]
                         if s in df["Status"].values],
                help="Select which statuses to display"
            )

            if status_filter:
                filtered_df = df[df["Status"].isin(status_filter)]
            else:
                filtered_df = df

            # Color-code the status with readable text
            def highlight_status(row):
                color_map = {
                    "OK": "background-color: #1e7e34; color: #ffffff",
                    "MISSING": "background-color: #c0392b; color: #ffffff",
                    "ACCESS ERROR": "background-color: #e74c3c; color: #ffffff",
                    "MEMBER ERROR": "background-color: #e67e22; color: #ffffff",
                    "CASE MISMATCH": "background-color: #f39c12; color: #1a1a1a",
                    "SKIP": "background-color: #6c757d; color: #ffffff",
                }
                style = color_map.get(row["Status"], "")
                return [style] * len(row)

            st.dataframe(
                filtered_df.style.apply(highlight_status, axis=1),
                use_container_width=True,
                height=500,
            )

            # Show all results option
            with st.expander("Show All Results (including OK)"):
                st.dataframe(
                    df.style.apply(highlight_status, axis=1),
                    use_container_width=True,
                    height=500,
                )

            # AOI Tag Reference
            with st.expander("AOI Parameters Reference"):
                param_data = []
                for name, info in sorted(parameters.items()):
                    param_data.append({
                        "Name": name,
                        "Usage": info.get("Usage", ""),
                        "DataType": info.get("DataType", ""),
                        "ExternalAccess": info.get("ExternalAccess", ""),
                        "TagType": info.get("TagType", ""),
                        "Dimensions": info.get("Dimensions", "") or "-",
                    })
                if param_data:
                    st.dataframe(pd.DataFrame(param_data), use_container_width=True)

            with st.expander("AOI Local Tags Reference (Accessible Only)"):
                ltag_data = []
                for name, info in sorted(local_tags.items()):
                    if info.get("ExternalAccess", "None") != "None":
                        ltag_data.append({
                            "Name": name,
                            "DataType": info.get("DataType", ""),
                            "ExternalAccess": info.get("ExternalAccess", ""),
                            "Dimensions": info.get("Dimensions", "") or "-",
                        })
                if ltag_data:
                    st.dataframe(pd.DataFrame(ltag_data), use_container_width=True)
                else:
                    st.info("No accessible local tags found.")

            # Download results
            st.markdown("---")
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Full Results as CSV",
                data=csv,
                file_name="fp_aoi_tag_validation.csv",
                mime="text/csv",
            )

        except ET.XMLSyntaxError as e:
            st.error(f"XML parsing error: {e}")
        except Exception as e:
            st.error(f"Error during validation: {e}")
            st.exception(e)

    elif aoi_file or has_fp_input:
        st.info("Please upload both the AOI (.L5X) file and the Faceplate file(s) to begin validation.")
