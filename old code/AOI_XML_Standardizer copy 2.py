import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import io
from copy import deepcopy
import re

st.title("AOI XML Tag Name Standardizer with Editor")

# Global dictionary for system parameters that are exceptions
SYSTEM_PARAMETERS = {
    "EnableIn": {"Usage": "Input", "DataType": "BOOL"},
    "EnableOut": {"Usage": "Output", "DataType": "BOOL"}
}

# System parameter prefixes that should be validated with special rules
SYSTEM_PARAMETER_PREFIXES = [
    "raC_Dvc_",
    # Add more prefixes here as needed
]

def is_system_parameter(param_name):
    """Check if parameter is a standard system parameter (EnableIn/EnableOut)"""
    return param_name in SYSTEM_PARAMETERS

def is_rac_dvc_parameter(param_name):
    """Check if parameter is a raC_Dvc_ system parameter"""
    for prefix in SYSTEM_PARAMETER_PREFIXES:
        if param_name.startswith(prefix):
            return True
    return False

def update_xml_parameter_names(xml_content, name_changes):
    """Update parameter names throughout the entire XML content using regex for exact matches"""
    updated_content = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
    changes_made = 0
    
    # Track all changes for reporting
    change_details = []
    
    # Perform find and replace for each name change
    for old_name, new_name in name_changes.items():
        if old_name != new_name:  # Only process actual changes
            # Escape special regex characters in the old_name
            escaped_old_name = re.escape(old_name)
            
            # Create regex pattern for exact word match
            # This pattern looks for the old_name as a complete word:
            # - (?<![a-zA-Z0-9_]) : negative lookbehind - not preceded by alphanumeric or underscore
            # - (?![a-zA-Z0-9_]) : negative lookahead - not followed by alphanumeric or underscore
            pattern = r'(?<![a-zA-Z0-9_])' + escaped_old_name + r'(?![a-zA-Z0-9_])'
            
            # Find all matches to count occurrences
            matches = re.findall(pattern, updated_content)
            occurrences = len(matches)
            
            if occurrences > 0:
                # Replace all exact matches
                updated_content = re.sub(pattern, new_name, updated_content)
                changes_made += occurrences
                change_details.append({
                    "old_name": old_name,
                    "new_name": new_name,
                    "occurrences": occurrences
                })
    
    return updated_content.encode('utf-8'), changes_made, change_details

uploaded_file = st.file_uploader("Upload AOI .L5X (XML) file", type="L5X")
if uploaded_file:
    # Store original content for download
    if 'original_content' not in st.session_state:
        st.session_state.original_content = uploaded_file.getvalue()
    
    tree = ET.parse(io.BytesIO(st.session_state.original_content))
    root = tree.getroot()

    # Extract Parameters data with descriptions
    parameters = root.find(".//Parameters")
    param_data = []
    if parameters is not None:
        for tag in parameters:
            param_info = {**{"Tag": tag.tag}, **tag.attrib}
            
            # Extract description
            desc_element = tag.find('Description')
            description = ""
            if desc_element is not None:
                # First try direct text in Description
                if desc_element.text is not None and desc_element.text.strip():
                    description = desc_element.text.strip()
                else:
                    # Fallback to LocalizedDescription
                    localized_desc = desc_element.find("LocalizedDescription[@Lang='en-US']")
                    if localized_desc is not None and localized_desc.text is not None:
                        description = localized_desc.text.strip()
            
            param_info["Description"] = description
            param_data.append(param_info)
    else:
        param_data = []

    # Helper functions
    def clean_prefix(prefix, name):
        known_prefixes = ["Cmd_", "Cfg_", "Set_", "Sts_", "Val_", "Sts_b"]
        usage_substrings = ["Inp_", "Out_", "Val_", "Sts_", "Cmd_", "Cfg_", "Set_"]
        for pfx in known_prefixes:
            if name.startswith(pfx):
                name = name[len(pfx):]
                break
        for sub in usage_substrings:
            if name.startswith(sub):
                name = name[len(sub):]
                break
        name_clean = name.replace("_", "")
        prefix_clean = prefix.rstrip("_")
        return prefix_clean + "_" + name_clean

    def is_boolean_alias(row):
        alias_for = row.get("AliasFor", "")
        if alias_for and '.' in alias_for:
            bit_suffix = alias_for.split('.')[-1]
            if bit_suffix.isdigit():
                return True
        return False

    exceptions_ref_names = {
        "Ref_Ctrl_Inf",
        "Ref_Ctrl_Set",
        "Ref_Ctrl_Cmd",
        "Ref_Ctrl_Sts"
    }

    def clean_ref_prefix(name):
        if name in exceptions_ref_names:
            return name
        name_no_underscore = name.replace("_", "")
        if name_no_underscore.startswith("Ref"):
            return "Ref_" + name_no_underscore[3:]
        else:
            return "Ref_" + name_no_underscore

    def suggest_parameter_name(row):
        reasons = []
        original_name = row.get("Name", "")
        usage = row.get("Usage", "")
        dtype = row.get("DataType")
        tagtype = row.get("TagType", "")
        required = str(row.get("Required", "")).lower() == "true"
        visible = str(row.get("Visible", "")).lower() == "true"
        external = row.get("ExternalAccess", None)
        description = row.get("Description", "")

        # Check if parameter is a standard system parameter (EnableIn/EnableOut)
        if is_system_parameter(original_name):
            # Skip all checks, keep original name, mark as correct
            return original_name, False, ""

        # Check if parameter is a raC_Dvc_ system parameter
        if is_rac_dvc_parameter(original_name):
            # Validate DataType, Usage, and Description only
            if dtype != "BOOL":
                reasons.append("DataType must be BOOL for raC_Dvc_ parameters")
            if usage not in ["Input", "Output"]:
                reasons.append("Usage must be Input or Output for raC_Dvc_ parameters")
            if not description:
                reasons.append("Description is required for raC_Dvc_ parameters")
            
            # Return original name, mark as wrong only if there are validation issues
            wrong = len(reasons) > 0
            failure_reason = "; ".join(reasons) if reasons else ""
            return original_name, wrong, failure_reason

        effective_dtype = dtype
        if tagtype == "Alias":
            if is_boolean_alias(row):
                effective_dtype = "BOOL"
            else:
                effective_dtype = "NON-BOOL"
        elif tagtype == "Base":
            effective_dtype = dtype

        suggestion = original_name
        wrong = False

        if usage == "InOut":
            expected_name = clean_ref_prefix(original_name)
            if not original_name.startswith("Ref_"):
                reasons.append("Name prefix missing 'Ref_'")
                suggestion = expected_name
                wrong = True
            elif original_name not in exceptions_ref_names and original_name != expected_name:
                reasons.append("Name format incorrect for InOut")
                suggestion = expected_name
                wrong = True

            if not required:
                reasons.append("Required is not true")
                wrong = True
            if not visible:
                reasons.append("Visible is not true")
                wrong = True
            if not pd.isna(external) and external != '':
                reasons.append("ExternalAccess not None")
                wrong = True

        elif usage == "Input":
            if effective_dtype == "BOOL":
                if not original_name.startswith("Cmd_"):
                    reasons.append("Input BOOL name missing 'Cmd_' prefix")
                    suggestion = clean_prefix("Cmd_", original_name)
                    wrong = True
            else:
                if not (original_name.startswith("Cfg_") or original_name.startswith("Set_")):
                    reasons.append("Input non-BOOL name missing 'Cfg_' or 'Set_' prefix")
                    suggestion = clean_prefix("Cfg_", original_name)
                    wrong = True

        elif usage == "Output":
            if effective_dtype == "BOOL":
                if not original_name.startswith("Sts_"):
                    reasons.append("Output BOOL name missing 'Sts_' prefix")
                    suggestion = clean_prefix("Sts_", original_name)
                    wrong = True
            else:
                if not (original_name.startswith("Val_") or original_name.startswith("Sts_b") or original_name.startswith("Sts_e")):
                    reasons.append("Output non-BOOL name missing 'Val_', 'Sts_b' or 'Sts_e' prefix")
                    suggestion = clean_prefix("Val_", original_name)
                    wrong = True

        # Final underscore check unless exception
        if suggestion.count("_") != 1 and suggestion not in exceptions_ref_names:
            reasons.append("Suggested name does not have exactly one underscore")
            parts = suggestion.split("_")
            if len(parts) > 1:
                suggestion = f"{parts[0]}_{''.join(parts[1:])}"
            wrong = True

        failure_reason = "; ".join(reasons) if reasons else ""
        return suggestion, wrong, failure_reason

    tabs = st.tabs(["Parameters Editor", "Local Tags", "Download Updated File"])

    with tabs[0]:  # Parameters Editor Tab
        if param_data:
            df_params = pd.DataFrame(param_data)
            
            # Get suggestion, wrong, and failure reasons for each row
            results = df_params.apply(suggest_parameter_name, axis=1)
            df_params["SuggestedName"] = [r[0] for r in results]
            df_params["NamingIssue"] = [r[1] for r in results]
            df_params["FailureReasons"] = [r[2] for r in results]

            st.markdown("### Parameters Naming Check and Editor")
            st.markdown("**Instructions:** Review the suggested names below. You can edit the 'SuggestedName' column directly. Red rows indicate naming issues.")
            
            # Create editable dataframe - include Description column
            edit_columns = ["Name", "Usage", "DataType", "TagType", "Description", "SuggestedName", "FailureReasons"]
            display_df = df_params[edit_columns].copy()
            
            # Add a visual indicator column for issues
            display_df["🚨"] = df_params["NamingIssue"].apply(lambda x: "❌" if x else "✅")
            
            # Reorder columns to put indicator first
            cols = ["🚨"] + edit_columns
            display_df = display_df[cols]
            
            # Use st.data_editor for inline editing
            edited_df = st.data_editor(
                display_df,
                disabled=["🚨", "Name", "Usage", "DataType", "TagType", "Description", "FailureReasons"],  # Make these read-only
                column_config={
                    "🚨": st.column_config.TextColumn(
                        "Status",
                        help="❌ = Has naming issues, ✅ = Follows naming rules",
                        width="small"
                    ),
                    "SuggestedName": st.column_config.TextColumn(
                        "Suggested Name (Editable)",
                        help="Edit this field to change the suggested parameter name",
                        max_chars=50,
                        width="medium"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description",
                        help="Parameter description (read-only)",
                        width="large"
                    ),
                    "FailureReasons": st.column_config.TextColumn(
                        "Issue Details",
                        help="Specific reasons for naming issues",
                        width="large"
                    ),
                    "Name": st.column_config.TextColumn(
                        "Current Name",
                        width="medium"
                    ),
                    "Usage": st.column_config.TextColumn(
                        "Usage",
                        width="small"
                    ),
                    "DataType": st.column_config.TextColumn(
                        "Data Type",
                        width="small"
                    ),
                    "TagType": st.column_config.TextColumn(
                        "Tag Type",
                        width="small"
                    ),
                },
                use_container_width=True,
                height=600,
                key="param_editor",
                hide_index=True
            )
            
            # Remove the indicator column from edited_df for processing and add back NamingIssue
            edited_df = edited_df.drop("🚨", axis=1)
            edited_df["NamingIssue"] = df_params["NamingIssue"].values

            # Show summary
            issues_count = edited_df["NamingIssue"].sum()
            changes_count = (edited_df["SuggestedName"] != edited_df["Name"]).sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Parameters", len(edited_df))
            with col2:
                st.metric("Naming Issues", issues_count)
            with col3:
                st.metric("Proposed Changes", changes_count)

            # Show what changes will be made
            if changes_count > 0:
                st.markdown("### Proposed Changes")
                changes_df = edited_df[edited_df["SuggestedName"] != edited_df["Name"]][["Name", "SuggestedName", "Usage"]]
                st.dataframe(changes_df, use_container_width=True)
                
                # Store changes in session state for download tab
                name_mapping = dict(zip(changes_df["Name"], changes_df["SuggestedName"]))
                st.session_state.name_changes = name_mapping
                st.session_state.edited_df = edited_df
            else:
                st.info("No changes proposed.")
                st.session_state.name_changes = {}

        else:
            st.write("No parameter tags found.")

    with tabs[1]:  # Local Tags Tab
        localtags = root.find(".//LocalTags")
        if localtags is not None:
            local_tags_data = []
            for tag in localtags:
                local_tags_data.append({**{"Tag": tag.tag}, **tag.attrib})

            if local_tags_data:
                df_localtags = pd.DataFrame(local_tags_data)
                st.markdown("### Local Tags (display only)")
                st.dataframe(
                    df_localtags,
                    use_container_width=True,
                    height=600
                )
            else:
                st.write("No local tags found.")
        else:
            st.write("No <LocalTags> found.")

    with tabs[2]:  # Download Tab
        st.markdown("### Download Updated AOI File")
        
        if 'name_changes' in st.session_state and st.session_state.name_changes:
            st.markdown("**Proposed Changes:**")
            changes_df = pd.DataFrame([
                {"Original Name": old, "New Name": new} 
                for old, new in st.session_state.name_changes.items()
            ])
            st.dataframe(changes_df, use_container_width=True)
            
            # Add Apply Changes button
            if st.button("Apply Changes", key="apply_changes"):
                try:
                    # Apply the name changes using string replacement on entire XML content
                    updated_xml, changes_made, change_details = update_xml_parameter_names(
                        st.session_state.original_content, 
                        st.session_state.name_changes
                    )
                    
                    # Store updated XML in session state
                    st.session_state.updated_xml = updated_xml
                    st.session_state.changes_made = changes_made
                    st.session_state.change_details = change_details
                    
                    st.success(f"Successfully updated {changes_made} parameter references throughout the entire XML file!")
                    
                    # Show detailed breakdown of changes
                    if change_details:
                        st.markdown("**Change Details:**")
                        details_df = pd.DataFrame(change_details)
                        details_df.columns = ["Original Name", "New Name", "Total Occurrences Replaced"]
                        st.dataframe(details_df, use_container_width=True)
                        
                        st.info("💡 This includes parameter definitions, ladder logic references, HMI bindings, and any other occurrences throughout the file.")
                    
                    # Provide download button
                    original_filename = uploaded_file.name
                    new_filename = original_filename.replace('.L5X', '_updated.L5X')
                    
                    st.download_button(
                        label=f"Download {new_filename}",
                        data=st.session_state.updated_xml,
                        file_name=new_filename,
                        mime="application/xml",
                        type="secondary"
                    )
                    
                except Exception as e:
                    st.error(f"Error updating XML: {str(e)}")
            else:
                st.info("Click 'Apply Changes' to process the proposed changes.")
        else:
            st.info("No changes to apply. Make edits in the Parameters Editor tab first.")
            
        # Always provide option to download original file
        st.markdown("---")
        st.markdown("**Download Original File:**")
        st.download_button(
            label=f"Download {uploaded_file.name}",
            data=st.session_state.original_content,
            file_name=uploaded_file.name,
            mime="application/xml"
        )