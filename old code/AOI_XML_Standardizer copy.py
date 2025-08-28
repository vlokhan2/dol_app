import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

st.title("AOI XML Tag Name Standardizer with Failure Reasons")

# Global dictionary for system parameters that are exceptions
SYSTEM_PARAMETERS = {
    "EnableIn": {"Usage": "Input", "DataType": "BOOL"},
    "EnableOut": {"Usage": "Output", "DataType": "BOOL"}
}

uploaded_file = st.file_uploader("Upload AOI .L5X (XML) file", type="L5X")
if uploaded_file:
    tree = ET.parse(uploaded_file)
    root = tree.getroot()

    # Extract Parameters data
    parameters = root.find(".//Parameters")
    param_data = []
    if parameters is not None:
        for tag in parameters:
            param_data.append({**{"Tag": tag.tag}, **tag.attrib})
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

        # Check if parameter is a system parameter (EnableIn or EnableOut)
        if original_name in SYSTEM_PARAMETERS:
            # Skip all checks, keep original name, mark as correct
            return original_name, False, ""

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

    tabs = st.tabs(["Parameters", "Local Tags"])

    with tabs[0]:  # Parameters Tab
        if param_data:
            df_params = pd.DataFrame(param_data)
            # Get suggestion, wrong, and failure reasons for each row
            results = df_params.apply(suggest_parameter_name, axis=1)
            df_params["SuggestedName"] = [r[0] for r in results]
            df_params["NamingIssue"] = [r[1] for r in results]
            df_params["FailureReasons"] = [r[2] for r in results]

            def highlight_wrong(row):
                return ['background-color: #ffcccc' if row.NamingIssue else '' for _ in row]

            st.markdown("### Parameters Naming Check (red = naming issue)")
            st.dataframe(
                df_params.style.apply(highlight_wrong, axis=1),
                use_container_width=True,  # Stretch to full container width
                height=1000  # Fixed height for vertical scrolling
            )

            issues_count = df_params["NamingIssue"].sum()
            if issues_count > 0:
                st.warning(f"Found {issues_count} parameter naming issues. Reasons shown in 'FailureReasons' column.")
            else:
                st.success("All parameter names follow the naming rules!")
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
                    use_container_width=True,  # Stretch to full container width
                    height=1000  # Fixed height for vertical scrolling
                )
            else:
                st.write("No local tags found.")
        else:
            st.write("No <LocalTags> found.")