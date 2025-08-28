import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import io
import re
from copy import deepcopy
import uuid

def main():
    st.title("AOI XML Tag Name Standardizer with Editor")
    
    # Global dictionary for system parameters that are exceptions
    SYSTEM_PARAMETERS = {
        "EnableIn": {"Usage": "Input", "DataType": "BOOL"},
        "EnableOut": {"Usage": "Output", "DataType": "BOOL"}
    }

    # System parameter prefixes that should be validated with special rules
    SYSTEM_PARAMETER_PREFIXES = [
        "raC_Dvc_",
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

    def update_xml_names_and_descriptions(xml_content, name_changes, description_changes, tag_type="Parameter"):
        """Update parameter or local tag names and descriptions throughout the entire XML content"""
        updated_content = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        changes_made = 0
        
        # Track all changes for reporting
        change_details = []
        
        # Handle description changes
        for param_name, new_description in description_changes.items():
            escaped_param_name = re.escape(param_name)
            pattern1 = (
                rf'(<{tag_type}[^>]*Name="' + escaped_param_name + r'"[^>]*>.*?'
                r'<Description>\s*)'
                r'(<!\[CDATA\[)(.*?)(\]\]>)'
                r'(\s*(?=<LocalizedDescription|</Description>))'
            )
            
            def replace_main_description(match):
                return match.group(1) + match.group(2) + new_description + match.group(4) + match.group(5)
            
            new_content = re.sub(pattern1, replace_main_description, updated_content, flags=re.DOTALL)
            main_desc_changed = new_content != updated_content
            updated_content = new_content
            
            pattern2 = (
                rf'(<{tag_type}[^>]*Name="' + escaped_param_name + r'"[^>]*>.*?'
                r'<LocalizedDescription[^>]*Lang="en-US"[^>]*>\s*)'
                r'(<!\[CDATA\[)(.*?)(\]\]>)'
                r'(\s*</LocalizedDescription>)'
            )
            
            def replace_localized_description(match):
                return match.group(1) + match.group(2) + new_description + match.group(4) + match.group(5)
            
            new_content = re.sub(pattern2, replace_localized_description, updated_content, flags=re.DOTALL)
            localized_desc_changed = new_content != updated_content
            updated_content = new_content
            
            if main_desc_changed or localized_desc_changed:
                changes_made += 1
                change_details.append({
                    "type": "description",
                    "parameter": param_name,
                    "new_description": new_description,
                    "main_updated": main_desc_changed,
                    "localized_updated": localized_desc_changed,
                    "tag_type": tag_type
                })
        
        # Handle name changes
        for old_name, new_name in name_changes.items():
            if old_name != new_name:
                escaped_old_name = re.escape(old_name)
                pattern = r'(?<![a-zA-Z0-9_])' + escaped_old_name + r'(?![a-zA-Z0-9_])'
                matches = re.findall(pattern, updated_content)
                occurrences = len(matches)
                
                if occurrences > 0:
                    updated_content = re.sub(pattern, new_name, updated_content)
                    changes_made += occurrences
                    change_details.append({
                        "type": "name",
                        "old_name": old_name,
                        "new_name": new_name,
                        "occurrences": occurrences,
                        "tag_type": tag_type
                    })
        
        return updated_content.encode('utf-8'), changes_made, change_details

    def update_aoi_identity(xml_content, aoi_changes):
        """Update AOI identity attributes and elements"""
        updated_content = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        changes_made = 0
        change_details = []
        
        # Parse XML
        tree = ET.fromstring(updated_content)
        aoi = tree.find(".//AddOnInstructionDefinition")
        
        # Update attributes
        original_values = {
            "Name": aoi.get("Name", ""),
            "Revision": aoi.get("Revision", ""),
            "RevisionExtension": aoi.get("RevisionExtension", ""),
            "Vendor": aoi.get("Vendor", "")
        }
        
        for attr, new_value in aoi_changes.get("attributes", {}).items():
            if attr in original_values and original_values[attr] != new_value:
                aoi.set(attr, new_value)
                changes_made += 1
                change_details.append({
                    "type": "attribute",
                    "attribute": attr,
                    "old_value": original_values[attr],
                    "new_value": new_value,
                    "tag_type": "AOI"
                })
        
        # Update Description
        desc_element = aoi.find("Description")
        if desc_element is not None and "Description" in aoi_changes:
            old_desc = desc_element.text.strip() if desc_element.text else ""
            new_desc = aoi_changes["Description"]
            if old_desc != new_desc:
                desc_element.text = None
                cdata = ET.SubElement(desc_element, "![CDATA[")
                cdata.text = new_desc
                changes_made += 1
                change_details.append({
                    "type": "description",
                    "element": "Description",
                    "old_value": old_desc,
                    "new_value": new_desc,
                    "tag_type": "AOI"
                })
        
        # Update LocalizedDescription
        loc_desc_element = aoi.find("LocalizedDescription[@Lang='en-US']")
        if loc_desc_element is not None and "LocalizedDescription" in aoi_changes:
            old_loc_desc = loc_desc_element.text.strip() if loc_desc_element.text else ""
            new_loc_desc = aoi_changes["LocalizedDescription"]
            if old_loc_desc != new_loc_desc:
                loc_desc_element.text = None
                cdata = ET.SubElement(loc_desc_element, "![CDATA[")
                cdata.text = new_loc_desc
                changes_made += 1
                change_details.append({
                    "type": "description",
                    "element": "LocalizedDescription",
                    "old_value": old_loc_desc,
                    "new_value": new_loc_desc,
                    "tag_type": "AOI"
                })
        
        # Update RevisionNote
        rev_note_element = aoi.find("RevisionNote")
        if rev_note_element is not None and "RevisionNote" in aoi_changes:
            old_rev_note = rev_note_element.text.strip() if rev_note_element.text else ""
            new_rev_note = aoi_changes["RevisionNote"]
            if old_rev_note != new_rev_note:
                rev_note_element.text = None
                cdata = ET.SubElement(rev_note_element, "![CDATA[")
                cdata.text = new_rev_note
                changes_made += 1
                change_details.append({
                    "type": "revision_note",
                    "element": "RevisionNote",
                    "old_value": old_rev_note,
                    "new_value": new_rev_note,
                    "tag_type": "AOI"
                })
        
        # Update LocalizedRevisionNote
        loc_rev_note_element = aoi.find("LocalizedRevisionNote[@Lang='en-US']")
        if loc_rev_note_element is not None and "LocalizedRevisionNote" in aoi_changes:
            old_loc_rev_note = loc_rev_note_element.text.strip() if loc_rev_note_element.text else ""
            new_loc_rev_note = aoi_changes["LocalizedRevisionNote"]
            if old_loc_rev_note != new_loc_rev_note:
                loc_rev_note_element.text = None
                cdata = ET.SubElement(loc_rev_note_element, "![CDATA[")
                cdata.text = new_loc_rev_note
                changes_made += 1
                change_details.append({
                    "type": "revision_note",
                    "element": "LocalizedRevisionNote",
                    "old_value": old_loc_rev_note,
                    "new_value": new_loc_rev_note,
                    "tag_type": "AOI"
                })
        
        # Update AdditionalHelpText
        help_text_element = aoi.find("AdditionalHelpText")
        if help_text_element is not None and "AdditionalHelpText" in aoi_changes:
            old_help_text = help_text_element.text.strip() if help_text_element.text else ""
            new_help_text = aoi_changes["AdditionalHelpText"]
            if old_help_text != new_help_text:
                help_text_element.text = None
                cdata = ET.SubElement(help_text_element, "![CDATA[")
                cdata.text = new_help_text
                changes_made += 1
                change_details.append({
                    "type": "help_text",
                    "element": "AdditionalHelpText",
                    "old_value": old_help_text,
                    "new_value": new_help_text,
                    "tag_type": "AOI"
                })
        
        updated_content = ET.tostring(tree, encoding='utf-8')
        return updated_content, changes_made, change_details

    def validate_aoi_identity(row):
        """Validate AOI identity attributes and elements"""
        reasons = []
        name = row.get("Name", "")
        revision = row.get("Revision", "")
        revision_extension = row.get("RevisionExtension", "")
        vendor = row.get("Vendor", "")
        
        # Validation rules
        if not name:
            reasons.append("Name is required")
        elif not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            reasons.append("Name must start with a letter and contain only letters, numbers, or underscores")
        
        if not revision:
            reasons.append("Revision is required")
        elif not re.match(r'^\d+\.\d+$', revision):
            reasons.append("Revision must be in format X.Y (e.g., 4.0)")
        
        if not revision_extension:
            reasons.append("RevisionExtension is required")
        elif not re.match(r'^\.\d+$', revision_extension):
            reasons.append("RevisionExtension must be in format .XX (e.g., .00)")
        
        if not vendor:
            reasons.append("Vendor is required")
        
        wrong = len(reasons) > 0
        failure_reason = "; ".join(reasons) if reasons else ""
        return wrong, failure_reason

    # --- NEW: Extract rung comments -------------------------------------------------
    def extract_rung_comments(root):
        """
        Return a list of dicts: Routine, RungNumber, RungType, RungText, Comment, LocalizedComment
        """
        data = []
        for routine in root.findall(".//Routine[@Type='RLL']"):
            rname = routine.get("Name", "")
            rll = routine.find("RLLContent")
            if rll is None:
                continue
            for rung in rll.findall("Rung"):
                num = rung.get("Number", "")
                rtype = rung.get("Type", "")
                # Comment + LocalizedComment(en-US)
                main_comment = ""
                loc_comment = ""
                c = rung.find("Comment")
                if c is not None:
                    if c.text and c.text.strip():
                        main_comment = c.text.strip()
                    loc = c.find("LocalizedComment[@Lang='en-US']")
                    if loc is not None and loc.text:
                        loc_comment = loc.text.strip()

                # Rung Text (e.g., NOP();)
                text_elem = rung.find("Text")
                rung_text = text_elem.text.strip() if (text_elem is not None and text_elem.text) else ""

                data.append({
                    "Routine": rname,
                    "RungNumber": num,
                    "RungType": rtype,
                    "RungText": rung_text,
                    "Comment": main_comment,
                    "LocalizedComment": loc_comment,
                })
        return data

    # --- NEW: Update rung comments throughout XML (preserving CDATA) ---------------
    def update_rung_comments(xml_content, changes):
        """
        changes: iterable of dicts with keys:
            Routine, RungNumber, Comment (new main), LocalizedComment (new en-US)
        Returns: (updated_bytes, total_changes_count, change_details_list)
        """
        updated = xml_content.decode("utf-8") if isinstance(xml_content, bytes) else xml_content
        total_changes = 0
        change_details = []

        for ch in changes:
            rname = str(ch.get("Routine", ""))
            rnum  = str(ch.get("RungNumber", ""))
            new_main = ch.get("Comment", "")
            new_loc  = ch.get("LocalizedComment", "")

            esc_name = re.escape(rname)
            esc_num  = re.escape(rnum)

            # Find the specific Rung's inner content to operate safely within it
            rung_pat = rf'(<Routine[^>]*\bName="{esc_name}"[^>]*>.*?<RLLContent>.*?<Rung[^>]*\bNumber="{esc_num}"[^>]*>)(.*?)(</Rung>)'
            m = re.search(rung_pat, updated, flags=re.DOTALL)
            if not m:
                # Not found; skip
                continue

            inner = m.group(2)
            changed_main = False
            changed_loc  = False

            # Replace main Comment CDATA
            main_pat = r'(<Comment>\s*<!\[CDATA\[)(.*?)(\]\]>)'
            if re.search(main_pat, inner, flags=re.DOTALL):
                def repl_main(mm):
                    return mm.group(1) + new_main + mm.group(3)
                inner_new = re.sub(main_pat, repl_main, inner, count=1, flags=re.DOTALL)
                if inner_new != inner:
                    inner = inner_new
                    changed_main = True

            # Replace or insert LocalizedComment(en-US)
            loc_pat = r'(<LocalizedComment[^>]*\bLang="en-US"[^>]*>\s*<!\[CDATA\[)(.*?)(\]\]>)'
            if re.search(loc_pat, inner, flags=re.DOTALL):
                def repl_loc(mm):
                    return mm.group(1) + new_loc + mm.group(3)
                inner_new = re.sub(loc_pat, repl_loc, inner, count=1, flags=re.DOTALL)
                if inner_new != inner:
                    inner = inner_new
                    changed_loc = True
            else:
                # Insert if user provided a localized comment and none exists
                if new_loc.strip():
                    insertion = f'<LocalizedComment Lang="en-US"><![CDATA[{new_loc}]]></LocalizedComment>'
                    # Insert just before </Comment>
                    inner_new = re.sub(r'(</Comment>)', insertion + r'\1', inner, count=1, flags=re.DOTALL)
                    if inner_new != inner:
                        inner = inner_new
                        changed_loc = True

            if changed_main or changed_loc:
                # Stitch the modified inner rung back into the full XML text
                updated = updated[:m.start(2)] + inner + updated[m.end(2):]
                total_changes += int(changed_main) + int(changed_loc)
                change_details.append({
                    "type": "rung_comment",
                    "routine": rname,
                    "rung_number": rnum,
                    "main_updated": changed_main,
                    "localized_updated": changed_loc
                })

        return updated.encode("utf-8"), total_changes, change_details

    
    uploaded_file = st.file_uploader("Upload Unlocked AOI .L5X (XML) file", type="L5X")
    if uploaded_file:
        if 'original_content' not in st.session_state:
            st.session_state.original_content = uploaded_file.getvalue()
        
        tree = ET.parse(io.BytesIO(st.session_state.original_content))
        root = tree.getroot()
        
        # Get the main AOI name from TargetName attribute
        target_name = root.get("TargetName")
        if not target_name:
            st.error("TargetName attribute not found in root element")
            st.stop()
            
        # Find the main AOI definition
        main_aoi = root.find(f".//AddOnInstructionDefinition[@Name='{target_name}']")
        if main_aoi is None:
            st.error(f"Main AOI '{target_name}' not found in AddOnInstructionDefinitions")
            st.stop()

        st.info(f"Processing main AOI: **{target_name}**")

        # Extract Parameters data
        #parameters = root.find(".//Parameters")
        parameters = main_aoi.find("Parameters")
        param_data = []
        if parameters is not None:
            for tag in parameters:
                param_info = {**{"Tag": tag.tag}, **tag.attrib}
                desc_element = tag.find('Description')
                description = ""
                if desc_element is not None:
                    if desc_element.text is not None and desc_element.text.strip():
                        description = desc_element.text.strip()
                    else:
                        localized_desc = desc_element.find("LocalizedDescription[@Lang='en-US']")
                        if localized_desc is not None and localized_desc.text is not None:
                            description = localized_desc.text.strip()
                
                param_info["Description"] = description
                param_data.append(param_info)

        # Extract AOI Identity data
        aoi = main_aoi
        aoi_data = []
        if aoi is not None:
            aoi_info = {
                "Name": aoi.get("Name", ""),
                "Revision": aoi.get("Revision", ""),
                "RevisionExtension": aoi.get("RevisionExtension", ""),
                "Vendor": aoi.get("Vendor", ""),
                "Description": "",
                "LocalizedDescription": "",
                "RevisionNote": "",
                "LocalizedRevisionNote": "",
                "AdditionalHelpText": ""
            }
            
            desc_element = aoi.find("Description")
            if desc_element is not None and desc_element.text is not None:
                aoi_info["Description"] = desc_element.text.strip()
            
            loc_desc_element = aoi.find("LocalizedDescription[@Lang='en-US']")
            if loc_desc_element is not None and loc_desc_element.text is not None:
                aoi_info["LocalizedDescription"] = loc_desc_element.text.strip()
            
            rev_note_element = aoi.find("RevisionNote")
            if rev_note_element is not None and rev_note_element.text is not None:
                aoi_info["RevisionNote"] = rev_note_element.text.strip()
            
            loc_rev_note_element = aoi.find("LocalizedRevisionNote[@Lang='en-US']")
            if loc_rev_note_element is not None and loc_rev_note_element.text is not None:
                aoi_info["LocalizedRevisionNote"] = loc_rev_note_element.text.strip()
            
            help_text_element = aoi.find("AdditionalHelpText")
            if help_text_element is not None and help_text_element.text is not None:
                aoi_info["AdditionalHelpText"] = help_text_element.text.strip()
            
            aoi_data.append(aoi_info)

        # Helper functions for Parameters
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

            if is_system_parameter(original_name):
                return original_name, False, ""

            if is_rac_dvc_parameter(original_name):
                if dtype != "BOOL":
                    reasons.append("DataType must be BOOL for raC_Dvc_ parameters")
                if usage not in ["Input", "Output"]:
                    reasons.append("Usage must be Input or Output for raC_Dvc_ parameters")
                if not description:
                    reasons.append("Description is required for raC_Dvc_ parameters")
                
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

            if suggestion.count("_") != 1 and suggestion not in exceptions_ref_names:
                reasons.append("Suggested name does not have exactly one underscore")
                parts = suggestion.split("_")
                if len(parts) > 1:
                    suggestion = f"{parts[0]}_{''.join(parts[1:])}"
                wrong = True

            failure_reason = "; ".join(reasons) if reasons else ""
            return suggestion, wrong, failure_reason

        # Helper functions for Local Tags
        def suggest_local_tag_name(row):
            reasons = []
            original_name = row.get("Name", "")
            external_access = row.get("ExternalAccess", "None")
            dtype = row.get("DataType", "")

            if original_name.startswith(("HMI_", "Inf_")):
                return original_name, False, ""

            suggestion = original_name
            wrong = False

            if external_access in ["Read Only", "Read/Write"]:
                if dtype == "BOOL":
                    if not original_name.startswith("Sts_"):
                        reasons.append("BOOL tag with Read Only or Read/Write ExternalAccess should start with 'Sts_'")
                        suggestion = clean_prefix("Sts_", original_name)
                        wrong = True
                else:
                    if not original_name.startswith("Val_"):
                        reasons.append("Non-BOOL tag with Read Only or Read/Write ExternalAccess should start with 'Val_'")
                        suggestion = clean_prefix("Val_", original_name)
                        wrong = True
            elif external_access == "None":
                if not original_name.startswith("Wrk_"):
                    reasons.append("Tag with None ExternalAccess should start with 'Wrk_'")
                    suggestion = clean_prefix("Wrk_", original_name)
                    wrong = True

            if suggestion.count("_") != 1:
                reasons.append("Suggested name does not have exactly one underscore")
                parts = suggestion.split("_")
                if len(parts) > 1:
                    suggestion = f"{parts[0]}_{''.join(parts[1:])}"
                wrong = True

            failure_reason = "; ".join(reasons) if reasons else ""
            return suggestion, wrong, failure_reason

        tabs = st.tabs(["Parameters Editor", "Local Tags Editor", "AOI Identity Editor","Rung Comments Editor", "Download Updated File"])

        with tabs[0]:  # Parameters Editor Tab
            if param_data:
                df_params = pd.DataFrame(param_data)
                results = df_params.apply(suggest_parameter_name, axis=1)
                df_params["SuggestedName"] = [r[0] for r in results]
                df_params["NamingIssue"] = [r[1] for r in results]
                df_params["FailureReasons"] = [r[2] for r in results]

                st.markdown("### Parameters Naming Check and Editor")
                st.markdown("**Instructions:** Review the suggested names and descriptions below. You can edit the 'SuggestedName' and 'Description' columns directly. Red rows indicate naming issues.")
                
                edit_columns = ["Name", "Usage", "DataType", "TagType", "Description", "SuggestedName", "FailureReasons"]
                display_df = df_params[edit_columns].copy()
                display_df["🚨"] = df_params["NamingIssue"].apply(lambda x: "❌" if x else "✅")
                cols = ["🚨"] + edit_columns
                display_df = display_df[cols]
                
                edited_df = st.data_editor(
                    display_df,
                    disabled=["🚨", "Name", "Usage", "DataType", "TagType", "FailureReasons"],
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
                            "Description (Editable)",
                            help="Edit this field to update the parameter description",
                            max_chars=200,
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
                
                edited_df = edited_df.drop("🚨", axis=1)
                edited_df["NamingIssue"] = df_params["NamingIssue"].values

                issues_count = edited_df["NamingIssue"].sum()
                name_changes_count = (edited_df["SuggestedName"] != edited_df["Name"]).sum()
                desc_changes_count = (edited_df["Description"] != df_params["Description"]).sum()
                total_changes_count = name_changes_count + desc_changes_count
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Parameters", len(edited_df))
                with col2:
                    st.metric("Naming Issues", issues_count)
                with col3:
                    st.metric("Name Changes", name_changes_count)
                with col4:
                    st.metric("Description Changes", desc_changes_count)

                if total_changes_count > 0:
                    st.markdown("### Proposed Changes")
                    if name_changes_count > 0:
                        st.markdown("#### Parameter Name Changes")
                        name_changes_df = edited_df[edited_df["SuggestedName"] != edited_df["Name"]][["Name", "SuggestedName", "Usage"]]
                        st.dataframe(name_changes_df, use_container_width=True)
                    
                    if desc_changes_count > 0:
                        st.markdown("#### Description Changes")
                        desc_changes_df = edited_df[edited_df["Description"] != df_params["Description"]][["Name", "Description"]]
                        desc_changes_df["Original Description"] = df_params.loc[desc_changes_df.index, "Description"]
                        desc_changes_df = desc_changes_df[["Name", "Original Description", "Description"]]
                        desc_changes_df.columns = ["Parameter Name", "Original Description", "New Description"]
                        st.dataframe(desc_changes_df, use_container_width=True)
                    
                    name_mapping = {}
                    description_mapping = {}
                    if name_changes_count > 0:
                        name_changes_subset = edited_df[edited_df["SuggestedName"] != edited_df["Name"]]
                        name_mapping = dict(zip(name_changes_subset["Name"], name_changes_subset["SuggestedName"]))
                    
                    if desc_changes_count > 0:
                        desc_changes_subset = edited_df[edited_df["Description"] != df_params["Description"]]
                        description_mapping = dict(zip(desc_changes_subset["Name"], desc_changes_subset["Description"]))
                    
                    st.session_state.param_name_changes = name_mapping
                    st.session_state.param_description_changes = description_mapping
                    st.session_state.edited_param_df = edited_df
                else:
                    st.info("No parameter changes proposed.")
                    st.session_state.param_name_changes = {}
                    st.session_state.param_description_changes = {}

        with tabs[1]:  # Local Tags Editor Tab
            localtags = main_aoi.find("LocalTags")
            if localtags is not None:
                local_tags_data = []
                for tag in localtags:
                    tag_info = {**{"Tag": tag.tag}, **tag.attrib}
                    desc_element = tag.find('Description')
                    description = ""
                    if desc_element is not None:
                        if desc_element.text is not None and desc_element.text.strip():
                            description = desc_element.text.strip()
                        else:
                            localized_desc = desc_element.find("LocalizedDescription[@Lang='en-US']")
                            if localized_desc is not None and localized_desc.text is not None:
                                description = localized_desc.text.strip()
                    tag_info["Description"] = description
                    local_tags_data.append(tag_info)

                if local_tags_data:
                    df_localtags = pd.DataFrame(local_tags_data)
                    results = df_localtags.apply(suggest_local_tag_name, axis=1)
                    df_localtags["SuggestedName"] = [r[0] for r in results]
                    df_localtags["NamingIssue"] = [r[1] for r in results]
                    df_localtags["FailureReasons"] = [r[2] for r in results]

                    st.markdown("### Local Tags Naming Check and Editor")
                    st.markdown("**Instructions:** Review the suggested names and descriptions below. You can edit the 'SuggestedName' and 'Description' columns directly. Red rows indicate naming issues.")
                    
                    edit_columns = ["Name", "DataType", "ExternalAccess", "Description", "SuggestedName", "FailureReasons"]
                    display_df = df_localtags[edit_columns].copy()
                    display_df["🚨"] = df_localtags["NamingIssue"].apply(lambda x: "❌" if x else "✅")
                    cols = ["🚨"] + edit_columns
                    display_df = display_df[cols]
                    
                    edited_df = st.data_editor(
                        display_df,
                        disabled=["🚨", "Name", "DataType", "ExternalAccess", "FailureReasons"],
                        column_config={
                            "🚨": st.column_config.TextColumn(
                                "Status",
                                help="❌ = Has naming issues, ✅ = Follows naming rules",
                                width="small"
                            ),
                            "SuggestedName": st.column_config.TextColumn(
                                "Suggested Name (Editable)",
                                help="Edit this field to change the suggested tag name",
                                max_chars=50,
                                width="medium"
                            ),
                            "Description": st.column_config.TextColumn(
                                "Description (Editable)",
                                help="Edit this field to update the tag description",
                                max_chars=200,
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
                            "DataType": st.column_config.TextColumn(
                                "Data Type",
                                width="small"
                            ),
                            "ExternalAccess": st.column_config.TextColumn(
                                "External Access",
                                width="small"
                            ),
                        },
                        use_container_width=True,
                        height=600,
                        key="localtag_editor",
                        hide_index=True
                    )
                    
                    edited_df = edited_df.drop("🚨", axis=1)
                    edited_df["NamingIssue"] = df_localtags["NamingIssue"].values

                    issues_count = edited_df["NamingIssue"].sum()
                    name_changes_count = (edited_df["SuggestedName"] != edited_df["Name"]).sum()
                    desc_changes_count = (edited_df["Description"] != df_localtags["Description"]).sum()
                    total_changes_count = name_changes_count + desc_changes_count
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Local Tags", len(edited_df))
                    with col2:
                        st.metric("Naming Issues", issues_count)
                    with col3:
                        st.metric("Name Changes", name_changes_count)
                    with col4:
                        st.metric("Description Changes", desc_changes_count)

                    if total_changes_count > 0:
                        st.markdown("### Proposed Changes")
                        if name_changes_count > 0:
                            st.markdown("#### Local Tag Name Changes")
                            name_changes_df = edited_df[edited_df["SuggestedName"] != edited_df["Name"]][["Name", "SuggestedName", "ExternalAccess"]]
                            st.dataframe(name_changes_df, use_container_width=True)
                        
                        if desc_changes_count > 0:
                            st.markdown("#### Description Changes")
                            desc_changes_df = edited_df[edited_df["Description"] != df_localtags["Description"]][["Name", "Description"]]
                            desc_changes_df["Original Description"] = df_localtags.loc[desc_changes_df.index, "Description"]
                            desc_changes_df = desc_changes_df[["Name", "Original Description", "Description"]]
                            desc_changes_df.columns = ["Tag Name", "Original Description", "New Description"]
                            st.dataframe(desc_changes_df, use_container_width=True)
                        
                        name_mapping = {}
                        description_mapping = {}
                        if name_changes_count > 0:
                            name_changes_subset = edited_df[edited_df["SuggestedName"] != edited_df["Name"]]
                            name_mapping = dict(zip(name_changes_subset["Name"], name_changes_subset["SuggestedName"]))
                        
                        if desc_changes_count > 0:
                            desc_changes_subset = edited_df[edited_df["Description"] != df_localtags["Description"]]
                            description_mapping = dict(zip(desc_changes_subset["Name"], desc_changes_subset["Description"]))
                        
                        st.session_state.local_name_changes = name_mapping
                        st.session_state.local_description_changes = description_mapping
                        st.session_state.edited_local_df = edited_df
                    else:
                        st.info("No local tag changes proposed.")
                        st.session_state.local_name_changes = {}
                        st.session_state.local_description_changes = {}

        with tabs[2]:  # AOI Identity Editor Tab
            if aoi_data:
                df_aoi = pd.DataFrame(aoi_data)
                results = df_aoi.apply(validate_aoi_identity, axis=1)
                df_aoi["NamingIssue"] = [r[0] for r in results]
                df_aoi["FailureReasons"] = [r[1] for r in results]

                st.markdown("### AOI Identity Check and Editor")
                st.markdown("**Instructions:** Review and edit the AOI identity information below. Red rows indicate validation issues.")
                
                edit_columns = ["Name", "Revision", "RevisionExtension", "Vendor", 
                              "Description", "LocalizedDescription", 
                              "RevisionNote", "LocalizedRevisionNote", 
                              "AdditionalHelpText", "FailureReasons"]
                display_df = df_aoi[edit_columns].copy()
                display_df["🚨"] = df_aoi["NamingIssue"].apply(lambda x: "❌" if x else "✅")
                cols = ["🚨"] + edit_columns
                display_df = display_df[cols]
                
                edited_df = st.data_editor(
                    display_df,
                    disabled=["🚨", "FailureReasons"],
                    column_config={
                        "🚨": st.column_config.TextColumn(
                            "Status",
                            help="❌ = Has validation issues, ✅ = Follows rules",
                            width="small"
                        ),
                        "Name": st.column_config.TextColumn(
                            "Name (Editable)",
                            help="Edit the AOI name",
                            max_chars=50,
                            width="medium"
                        ),
                        "Revision": st.column_config.TextColumn(
                            "Revision (Editable)",
                            help="Edit the revision (format: X.Y)",
                            max_chars=10,
                            width="small"
                        ),
                        "RevisionExtension": st.column_config.TextColumn(
                            "Revision Extension (Editable)",
                            help="Edit the revision extension (format: .XX)",
                            max_chars=10,
                            width="small"
                        ),
                        "Vendor": st.column_config.TextColumn(
                            "Vendor (Editable)",
                            help="Edit the vendor name",
                            max_chars=50,
                            width="medium"
                        ),
                        "Description": st.column_config.TextColumn(
                            "Description (Editable)",
                            help="Edit the main description",
                            max_chars=200,
                            width="large"
                        ),
                        "LocalizedDescription": st.column_config.TextColumn(
                            "Localized Description (Editable)",
                            help="Edit the en-US localized description",
                            max_chars=200,
                            width="large"
                        ),
                        "RevisionNote": st.column_config.TextColumn(
                            "Revision Note (Editable)",
                            help="Edit the main revision note",
                            max_chars=200,
                            width="large"
                        ),
                        "LocalizedRevisionNote": st.column_config.TextColumn(
                            "Localized Revision Note (Editable)",
                            help="Edit the en-US localized revision note",
                            max_chars=200,
                            width="large"
                        ),
                        "AdditionalHelpText": st.column_config.TextColumn(
                            "Additional Help Text (Editable)",
                            help="Edit the additional help text",
                            max_chars=1000,
                            width="large"
                        ),
                        "FailureReasons": st.column_config.TextColumn(
                            "Issue Details",
                            help="Specific reasons for validation issues",
                            width="large"
                        ),
                    },
                    use_container_width=True,
                    height=200,
                    key="aoi_editor",
                    hide_index=True
                )
                
                edited_df = edited_df.drop("🚨", axis=1)
                edited_df["NamingIssue"] = df_aoi["NamingIssue"].values

                issues_count = edited_df["NamingIssue"].sum()
                changes_count = sum(edited_df[col] != df_aoi[col] for col in edit_columns[:-1]).sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Validation Issues", issues_count)
                with col2:
                    st.metric("Changes", changes_count)

                if changes_count > 0:
                    st.markdown("### Proposed Changes")
                    changes_df = pd.DataFrame()
                    for col in edit_columns[:-1]:
                        if (edited_df[col] != df_aoi[col]).any():
                            temp_df = edited_df[[col]][edited_df[col] != df_aoi[col]].copy()
                            temp_df["Original Value"] = df_aoi.loc[temp_df.index, col]
                            temp_df["New Value"] = edited_df.loc[temp_df.index, col]
                            temp_df["Field"] = col
                            temp_df = temp_df[["Field", "Original Value", "New Value"]]
                            changes_df = pd.concat([changes_df, temp_df])
                    
                    if not changes_df.empty:
                        st.dataframe(changes_df, use_container_width=True)
                    
                    aoi_changes = {
                        "attributes": {
                            "Name": edited_df["Name"].iloc[0],
                            "Revision": edited_df["Revision"].iloc[0],
                            "RevisionExtension": edited_df["RevisionExtension"].iloc[0],
                            "Vendor": edited_df["Vendor"].iloc[0]
                        },
                        "Description": edited_df["Description"].iloc[0],
                        "LocalizedDescription": edited_df["LocalizedDescription"].iloc[0],
                        "RevisionNote": edited_df["RevisionNote"].iloc[0],
                        "LocalizedRevisionNote": edited_df["LocalizedRevisionNote"].iloc[0],
                        "AdditionalHelpText": edited_df["AdditionalHelpText"].iloc[0]
                    }
                    st.session_state.aoi_changes = aoi_changes
                    st.session_state.edited_aoi_df = edited_df
                else:
                    st.info("No AOI identity changes proposed.")
                    st.session_state.aoi_changes = {}
            else:
                st.write("No AOI identity information found.")

        # --- NEW: Rung Comments Editor Tab --------------------------------------------
        with tabs[3]:
            rungs_data = extract_rung_comments(main_aoi)
            if rungs_data:
                df_rungs = pd.DataFrame(rungs_data)

                st.markdown("### Rung Comments Check and Editor")
                st.markdown("**Instructions:** Review and edit **Comment** and **LocalizedComment**. Other columns are read-only for context.")

                # Order and flag columns
                edit_cols = ["Routine", "RungNumber", "RungType", "RungText", "Comment", "LocalizedComment"]
                display_df = df_rungs[edit_cols].copy()

                edited_df = st.data_editor(
                    display_df,
                    disabled=["Routine", "RungNumber", "RungType", "RungText"],
                    column_config={
                        "Routine": st.column_config.TextColumn("Routine", width="medium"),
                        "RungNumber": st.column_config.TextColumn("Rung #", width="small"),
                        "RungType": st.column_config.TextColumn("Type", width="small"),
                        "RungText": st.column_config.TextColumn("Rung Text", help="Instruction text", width="large"),
                        "Comment": st.column_config.TextColumn("Comment (Editable)", max_chars=2000, width="large"),
                        "LocalizedComment": st.column_config.TextColumn("Localized (en-US) (Editable)", max_chars=2000, width="large"),
                    },
                    use_container_width=True,
                    height=600,
                    key="rung_comments_editor",
                    hide_index=True
                )

                # Compute changes
                changed_mask = (edited_df["Comment"] != df_rungs["Comment"]) | \
                            (edited_df["LocalizedComment"] != df_rungs["LocalizedComment"])
                changes_count = int(changed_mask.sum())

                c1, c2, c3 = st.columns(3)
                with c1: st.metric("Total Rungs", len(edited_df))
                with c2: st.metric("Changed Comments", changes_count)
                with c3: st.metric("Routines", edited_df["Routine"].nunique())

                if changes_count > 0:
                    st.markdown("#### Proposed Rung Comment Changes")
                    proposed = edited_df.loc[changed_mask, ["Routine", "RungNumber", "Comment", "LocalizedComment"]].copy()
                    proposed["Original Comment"] = df_rungs.loc[changed_mask, "Comment"]
                    proposed["Original Localized"] = df_rungs.loc[changed_mask, "LocalizedComment"]
                    # Reorder for readability
                    proposed = proposed[["Routine", "RungNumber",
                                        "Original Comment", "Comment",
                                        "Original Localized", "LocalizedComment"]]
                    st.dataframe(proposed, use_container_width=True)

                    # Store changes for Apply step
                    change_rows = []
                    for idx in proposed.index:
                        change_rows.append({
                            "Routine": edited_df.at[idx, "Routine"],
                            "RungNumber": edited_df.at[idx, "RungNumber"],
                            "Comment": edited_df.at[idx, "Comment"],
                            "LocalizedComment": edited_df.at[idx, "LocalizedComment"],
                        })
                    st.session_state.rung_comment_changes = change_rows
                    st.session_state.edited_rungs_df = edited_df
                else:
                    st.info("No rung comment changes proposed.")
                    st.session_state.rung_comment_changes = []
                    st.session_state.edited_rungs_df = edited_df
            else:
                st.info("No RLL routines / rung comments found.")
                st.session_state.rung_comment_changes = []

        with tabs[4]:  # Download Updated File Tab
            st.markdown("### Download Updated AOI File")
            
            has_param_changes = ('param_name_changes' in st.session_state and st.session_state.param_name_changes) or \
                              ('param_description_changes' in st.session_state and st.session_state.param_description_changes)
            has_local_changes = ('local_name_changes' in st.session_state and st.session_state.local_name_changes) or \
                              ('local_description_changes' in st.session_state and st.session_state.local_description_changes)
            has_aoi_changes = 'aoi_changes' in st.session_state and st.session_state.aoi_changes
            
            has_rung_changes  = 'rung_comment_changes' in st.session_state and st.session_state.rung_comment_changes  # NEW

            
            if has_param_changes or has_local_changes or has_aoi_changes or has_rung_changes:
                st.markdown("**Proposed Changes:**")
                
                if has_param_changes:
                    if 'param_name_changes' in st.session_state and st.session_state.param_name_changes:
                        st.markdown("#### Parameter Name Changes")
                        name_changes_df = pd.DataFrame([
                            {"Original Name": old, "New Name": new} 
                            for old, new in st.session_state.param_name_changes.items()
                        ])
                        st.dataframe(name_changes_df, use_container_width=True)
                    
                    if 'param_description_changes' in st.session_state and st.session_state.param_description_changes:
                        st.markdown("#### Parameter Description Changes")
                        desc_changes_df = pd.DataFrame([
                            {"Parameter Name": name, "New Description": desc} 
                            for name, desc in st.session_state.param_description_changes.items()
                        ])
                        st.dataframe(desc_changes_df, use_container_width=True)
                
                if has_local_changes:
                    if 'local_name_changes' in st.session_state and st.session_state.local_name_changes:
                        st.markdown("#### Local Tag Name Changes")
                        name_changes_df = pd.DataFrame([
                            {"Original Name": old, "New Name": new} 
                            for old, new in st.session_state.local_name_changes.items()
                        ])
                        st.dataframe(name_changes_df, use_container_width=True)
                    
                    if 'local_description_changes' in st.session_state and st.session_state.local_description_changes:
                        st.markdown("#### Local Tag Description Changes")
                        desc_changes_df = pd.DataFrame([
                            {"Tag Name": name, "New Description": desc} 
                            for name, desc in st.session_state.local_description_changes.items()
                        ])
                        st.dataframe(desc_changes_df, use_container_width=True)
                
                if has_aoi_changes:
                    st.markdown("#### AOI Identity Changes")
                    changes_df = pd.DataFrame()
                    original_aoi = pd.DataFrame(aoi_data)
                    edited_aoi = st.session_state.edited_aoi_df
                    for col in edit_columns[:-1]:
                        if (edited_aoi[col] != original_aoi[col]).any():
                            temp_df = edited_aoi[[col]][edited_aoi[col] != original_aoi[col]].copy()
                            temp_df["Original Value"] = original_aoi.loc[temp_df.index, col]
                            temp_df["New Value"] = edited_aoi.loc[temp_df.index, col]
                            temp_df["Field"] = col
                            temp_df = temp_df[["Field", "Original Value", "New Value"]]
                            changes_df = pd.concat([changes_df, temp_df])
                    
                    if not changes_df.empty:
                        st.dataframe(changes_df, use_container_width=True)
                
                if has_rung_changes:
                    st.markdown("#### Rung Comment Changes")
                    rc_df = pd.DataFrame(st.session_state.rung_comment_changes)
                    st.dataframe(rc_df, use_container_width=True)

                if st.button("Apply Changes", key="apply_changes"):
                    try:
                        updated_xml = st.session_state.original_content
                        total_changes_made = 0
                        all_change_details = []
                        
                        # Apply parameter changes
                        if has_param_changes:
                            param_name_changes = st.session_state.get('param_name_changes', {})
                            param_desc_changes = st.session_state.get('param_description_changes', {})
                            updated_xml, changes_made, change_details = update_xml_names_and_descriptions(
                                updated_xml, 
                                param_name_changes,
                                param_desc_changes,
                                tag_type="Parameter"
                            )
                            total_changes_made += changes_made
                            all_change_details.extend(change_details)
                        
                        # Apply local tag changes
                        if has_local_changes:
                            local_name_changes = st.session_state.get('local_name_changes', {})
                            local_desc_changes = st.session_state.get('local_description_changes', {})
                            updated_xml, changes_made, change_details = update_xml_names_and_descriptions(
                                updated_xml, 
                                local_name_changes,
                                local_desc_changes,
                                tag_type="Tag"
                            )
                            total_changes_made += changes_made
                            all_change_details.extend(change_details)
                        
                        # Apply AOI identity changes
                        if has_aoi_changes:
                            aoi_changes = st.session_state.get('aoi_changes', {})
                            updated_xml, changes_made, change_details = update_aoi_identity(
                                updated_xml, 
                                aoi_changes
                            )
                            total_changes_made += changes_made
                            all_change_details.extend(change_details)
                        
                        
                        if has_rung_changes:
                            rung_changes = st.session_state.get('rung_comment_changes', [])
                            updated_xml, changes_made, change_details = update_rung_comments(
                                updated_xml,
                                rung_changes
                            )
                            total_changes_made += changes_made
                            all_change_details.extend(change_details)

                        st.session_state.updated_xml = updated_xml
                        st.session_state.changes_made = total_changes_made
                        st.session_state.change_details = all_change_details
                        
                        st.success(f"Successfully updated {total_changes_made} references and descriptions throughout the XML file!")
                        
                        if all_change_details:
                            st.markdown("**Change Details:**")
                            param_name_details = [d for d in all_change_details if d.get("type") == "name" and d.get("tag_type") == "Parameter"]
                            param_desc_details = [d for d in all_change_details if d.get("type") == "description" and d.get("tag_type") == "Parameter"]
                            local_name_details = [d for d in all_change_details if d.get("type") == "name" and d.get("tag_type") == "Tag"]
                            local_desc_details = [d for d in all_change_details if d.get("type") == "description" and d.get("tag_type") == "Tag"]
                            aoi_attr_details = [d for d in all_change_details if d.get("type") == "attribute" and d.get("tag_type") == "AOI"]
                            aoi_desc_details = [d for d in all_change_details if d.get("type") == "description" and d.get("tag_type") == "AOI"]
                            aoi_rev_note_details = [d for d in all_change_details if d.get("type") == "revision_note" and d.get("tag_type") == "AOI"]
                            aoi_help_text_details = [d for d in all_change_details if d.get("type") == "help_text" and d.get("tag_type") == "AOI"]
                            
                            if param_name_details:
                                st.markdown("##### Parameter Name Changes:")
                                name_details_df = pd.DataFrame(param_name_details)
                                name_details_df = name_details_df[["old_name", "new_name", "occurrences"]]
                                name_details_df.columns = ["Original Name", "New Name", "Total Occurrences Replaced"]
                                st.dataframe(name_details_df, use_container_width=True)
                            
                            if param_desc_details:
                                st.markdown("##### Parameter Description Updates:")
                                desc_details_df = pd.DataFrame(param_desc_details)
                                desc_details_df = desc_details_df[["parameter", "new_description"]]
                                desc_details_df.columns = ["Parameter Name", "New Description"]
                                st.dataframe(desc_details_df, use_container_width=True)
                            
                            if local_name_details:
                                st.markdown("##### Local Tag Name Changes:")
                                name_details_df = pd.DataFrame(local_name_details)
                                name_details_df = name_details_df[["old_name", "new_name", "occurrences"]]
                                name_details_df.columns = ["Original Name", "New Name", "Total Occurrences Replaced"]
                                st.dataframe(name_details_df, use_container_width=True)
                            
                            if local_desc_details:
                                st.markdown("##### Local Tag Description Updates:")
                                desc_details_df = pd.DataFrame(local_desc_details)
                                desc_details_df = desc_details_df[["parameter", "new_description"]]
                                desc_details_df.columns = ["Tag Name", "New Description"]
                                st.dataframe(desc_details_df, use_container_width=True)
                            
                            if aoi_attr_details:
                                st.markdown("##### AOI Attribute Changes:")
                                attr_details_df = pd.DataFrame(aoi_attr_details)
                                attr_details_df = attr_details_df[["attribute", "old_value", "new_value"]]
                                attr_details_df.columns = ["Attribute", "Original Value", "New Value"]
                                st.dataframe(attr_details_df, use_container_width=True)
                            
                            if aoi_desc_details:
                                st.markdown("##### AOI Description Updates:")
                                desc_details_df = pd.DataFrame(aoi_desc_details)
                                desc_details_df = desc_details_df[["element", "old_value", "new_value"]]
                                desc_details_df.columns = ["Element", "Original Value", "New Value"]
                                st.dataframe(desc_details_df, use_container_width=True)
                            
                            if aoi_rev_note_details:
                                st.markdown("##### AOI Revision Note Updates:")
                                rev_note_details_df = pd.DataFrame(aoi_rev_note_details)
                                rev_note_details_df = rev_note_details_df[["element", "old_value", "new_value"]]
                                rev_note_details_df.columns = ["Element", "Original Value", "New Value"]
                                st.dataframe(rev_note_details_df, use_container_width=True)
                            
                            if aoi_help_text_details:
                                st.markdown("##### AOI Additional Help Text Updates:")
                                help_text_details_df = pd.DataFrame(aoi_help_text_details)
                                help_text_details_df = help_text_details_df[["element", "old_value", "new_value"]]
                                help_text_details_df.columns = ["Element", "Original Value", "New Value"]
                                st.dataframe(help_text_details_df, use_container_width=True)
                            
                            if param_name_details or local_name_details:
                                st.info("💡 Name changes include definitions, ladder logic references, HMI bindings, and any other occurrences throughout the file.")
                        
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
                st.info("No changes to apply. Make edits in the Parameters Editor, Local Tags Editor, or AOI Identity Editor tabs first.")
                
            st.markdown("---")
            st.markdown("**Download Original File:**")
            st.download_button(
                label=f"Download {uploaded_file.name}",
                data=st.session_state.original_content,
                file_name=uploaded_file.name,
                mime="application/xml"
            )

if __name__ == "__main__":
    main()