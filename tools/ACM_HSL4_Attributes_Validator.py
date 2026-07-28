import streamlit as st
import io
import lxml.etree as ET
import pandas as pd
import zipfile
import os
from datetime import datetime
import re

class InMemoryUpload:
    """Simple in-memory UploadedFile-like object for zip entries."""
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data
    def read(self):
        return self._data
    def seek(self, *_):
        pass

def normalize_change_date(value: str) -> str:
    """
    Normalize various date/time inputs to ISO 'YYYY-MM-DDTHH:MM:SS'.
    If blank or format unknown, return the original string (or '').
    """
    v = (value or "").strip()
    if not v:
        return ""
    # Already ISO-like?
    try:
        # Accept full ISO without timezone
        dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        pass

    # Try common patterns
    patterns = [
        "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y",
        "%m/%d/%Y %I:%M:%S %p", "%d-%m-%Y %I:%M:%S %p"  
    ]
    for fmt in patterns:
        try:
            dt = datetime.strptime(v, fmt)
            # If no time in the format, set 00:00:00
            if "H" not in fmt:
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    # As a fallback, keep whatever user typed
    return v

def extract_hz1_index(uploaded_hz1_files):
    """
    Parse .HZ1 XML files and index them by Attachment @ID.
    Returns: { id: {"tree": ElementTree, "root": Element, "file_name": str} }
    """
    index = {}
    parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
    for uf in uploaded_hz1_files:
        try:
            data = uf.read()
            # .HZ1 content is a single <Attachment ...> root
            root = ET.fromstring(data, parser=parser)
            # Tolerate xmlns or bare tag: check tag suffix
            if not str(root.tag).endswith("Attachment"):
                st.warning(f"'{uf.name}' does not look like an Attachment XML; skipped.")
                continue
            att_id = root.attrib.get("ID", "").strip()
            if not att_id:
                st.warning(f"'{uf.name}' has no Attachment ID; skipped.")
                continue
            index[att_id] = {
                "tree": ET.ElementTree(root),
                "root": root,
                "file_name": uf.name
            }
        except Exception as e:
            st.warning(f"Could not parse HZ1 '{uf.name}': {e}")
    return index


# Comparison strings for ExtractionPath validation
COMPARISON_STRINGS = [
    '{ProjectName}\\Visualization\\FTViewME\\GlobalObjects',
    '{ProjectName}\\Visualization\\FTViewME\\Displays',
    '{ProjectName}\\Visualization\\FTViewSE\\GlobalObjects',
    '{ProjectName}\\Visualization\\FTViewSE\\Displays',
    '{ProjectName}\\Visualization\\Images',
    '{ProjectName}\\Documentation',
    '{ProjectName}\\Visualization\\ViewDesigner',
    '{ProjectName}\\Visualization'
]


def extract_attributes_from_files(uploaded_files):
    file_attributes = {}
    for uploaded_file in uploaded_files:
        try:
            parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
            tree = ET.parse(uploaded_file, parser=parser)
            root = tree.getroot()
            status = root.attrib.get("Status", "Pending")
            file_attributes[uploaded_file.name] = {
                "Status": status,
                "attributes": [],
                "tree": tree,
                "extraction_paths": []
            }

            # Existing attribute extraction
            rev_elements = root.findall(".//Rev")
            modules = root.findall(".//Module")
            for rev in rev_elements:
                modified_by = rev.attrib.get("ModifiedBy", "")
                modified_date = rev.attrib.get("ModifiedDate", "")
                headers = rev.findall(".//Header")
                for header in headers:
                    owner = header.attrib.get("Owner", "")
                    data_exchange_ids = [module.attrib.get("DataExchangeId", "") for module in modules]
                    data_exchange_id = "; ".join([id for id in data_exchange_ids if id])
                    file_attributes[uploaded_file.name]["attributes"].append({
                        "Rev": rev,
                        "Header": header,
                        "ModifiedBy": modified_by,
                        "ModifiedDate": modified_date,
                        "Owner": owner,
                        "DataExchangeId": data_exchange_id,
                        "Modules": modules
                    })

            # Existing ExtractionPath extraction
            for item in root.findall(".//Item/Attributes/Attribute[@Name='ExtractionPath']"):
                value = item.find("Value").text if item.find("Value") is not None else ""
                file_attributes[uploaded_file.name]["extraction_paths"].append({
                    "Item": item,
                    "Value": value
                })

        except ET.XMLSyntaxError:
            st.warning(f"File '{uploaded_file.name}' is not valid XML and was skipped.")
        except Exception as e:
            st.error(f"Failed to process {uploaded_file.name}: {e}")
    return file_attributes

def extract_attachment_attributes(uploaded_files):
    attachment_attributes = {}
    for uploaded_file in uploaded_files:
        try:
            content = uploaded_file.read().decode('utf-8')
            lines = content.splitlines()
            file_name = uploaded_file.name
            attachment_attributes[file_name] = {"attributes": [], "original_content": lines, "line_indices": []}

            for i, line in enumerate(lines):
                # Skip first line (header) and blank lines
                if i == 0 or not line.strip():
                    attachment_attributes[file_name]["line_indices"].append(None)
                    continue

                attributes = {}
                for attr in line.strip().split(','):
                    if '=' in attr:
                        key, value = attr.strip().split('=', 1)
                        attributes[key.strip()] = value.strip().strip("'").strip('"')  # Remove quotes

                # Extract required fields (now includes File_ID)
                file_name_attr = attributes.get('File_Name', '')
                description = attributes.get('Description', '')
                extraction_path = attributes.get('Extraction_Path', '')
                revision_description = attributes.get('Revison_Description', attributes.get('Revision_Description', ''))
                modified_date = attributes.get('Modified_Date', '')
                modified_by = attributes.get('Modified_By', '')
                file_id = attributes.get('File_ID', '')

                attachment_attributes[file_name]["attributes"].append({
                    "File_Name": file_name_attr,
                    "Description": description,
                    "Extraction_Path": extraction_path,
                    "Revision_Description": revision_description,
                    "Modified_Date": modified_date,
                    "Modified_By": modified_by,
                    "File_ID": file_id,
                    "original_line_index": i
                })
                attachment_attributes[file_name]["line_indices"].append(i)
        except Exception as e:
            st.error(f"Failed to process attachment {uploaded_file.name}: {e}")
    return attachment_attributes


def extract_inf_lib_type_from_files(uploaded_files):
    """
    Extract Inf_Lib and Inf_Type values from Tags in HSL4 files.
    Only processes raC_LD files (Library Device files), skips Asset-Control definition files.
    Returns: { file_name: { "tags": [...], "tree": ElementTree, "catalog_number": str, "is_ld_file": bool } }
    """
    file_inf_data = {}
    for uploaded_file in uploaded_files:
        try:
            uploaded_file.seek(0)
            parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
            tree = ET.parse(uploaded_file, parser=parser)
            root = tree.getroot()
            
            # Get CatalogNumber to determine if this is a raC_LD file
            catalog_number = root.attrib.get("CatalogNumber", "")
            is_ld_file = "raC_LD" in catalog_number or "raC_LD" in uploaded_file.name
            
            file_inf_data[uploaded_file.name] = {
                "tags": [],
                "tree": tree,
                "catalog_number": catalog_number,
                "is_ld_file": is_ld_file
            }
            
            # Only extract Inf_Lib/Inf_Type for raC_LD files
            if not is_ld_file:
                continue
            
            # Find all Tag elements
            tags = root.findall(".//Tag")
            for tag in tags:
                tag_name = tag.attrib.get("Name", "")
                scope = tag.attrib.get("Scope", "Unknown")
                
                # Determine human-readable scope
                if scope == "ControllerScope":
                    scope_display = "Controller"
                elif "Program" in scope:
                    scope_display = "Program"
                else:
                    scope_display = scope
                
                # Extract Inf_Lib value
                inf_lib = ""
                inf_lib_elem = tag.find(".//StructureMember[@Name='Inf_Lib']/DataValueMember[@Name='DATA']")
                if inf_lib_elem is not None and inf_lib_elem.text:
                    # Remove CDATA wrapper and quotes: <![CDATA['raC-4_02']]> -> raC-4_02
                    inf_lib = inf_lib_elem.text.strip().strip("'")
                
                # Extract Inf_Type value
                inf_type = ""
                inf_type_elem = tag.find(".//StructureMember[@Name='Inf_Type']/DataValueMember[@Name='DATA']")
                if inf_type_elem is not None and inf_type_elem.text:
                    inf_type = inf_type_elem.text.strip().strip("'")
                
                # Extract Library value from extended properties (Librarys/Library)
                ext_library = ""
                ext_library_elem = tag.find("Librarys/Library")
                if ext_library_elem is not None and ext_library_elem.text:
                    ext_library = ext_library_elem.text.strip()
                
                # Extract Instruction value from extended properties (Instructions/Instruction)
                ext_instruction = ""
                ext_instruction_elem = tag.find("Instructions/Instruction")
                if ext_instruction_elem is not None and ext_instruction_elem.text:
                    ext_instruction = ext_instruction_elem.text.strip()
                
                # Only include tags that have Inf_Lib or Inf_Type (these are the relevant AOI tags)
                if inf_lib or inf_type:
                    file_inf_data[uploaded_file.name]["tags"].append({
                        "TagName": tag_name,
                        "Scope": scope_display,
                        "Inf_Lib": inf_lib,
                        "Inf_Type": inf_type,
                        "ExtLibrary": ext_library,
                        "ExtInstruction": ext_instruction,
                        "_tag_element": tag,
                        "_inf_lib_elem": inf_lib_elem,
                        "_inf_type_elem": inf_type_elem,
                        "_ext_library_elem": ext_library_elem,
                        "_ext_instruction_elem": ext_instruction_elem
                    })
                    
        except ET.XMLSyntaxError:
            st.warning(f"File '{uploaded_file.name}' is not valid XML and was skipped.")
        except Exception as e:
            st.error(f"Failed to process {uploaded_file.name} for Inf_Lib/Inf_Type: {e}")
    return file_inf_data


def derive_description_and_path(file_name):
    """Derive Description and Extraction_Path based on File_Name."""
    file_name = file_name.lower()  # Case-insensitive matching
    if file_name.endswith('.ggfx') and '-se) toolbox' in file_name:
        return 'Toolbox SE', '{ProjectName}\\Visualization\\FTViewSE\\GlobalObjects'
    elif file_name.endswith('.ggfx') and '-me) toolbox' in file_name:
        return 'Toolbox ME', '{ProjectName}\\Visualization\\FTViewME\\GlobalObjects'
    elif file_name.endswith('.ggfx') and '-se) graphic symbols' in file_name:
        return 'Graphic Symbols SE', '{ProjectName}\\Visualization\\FTViewSE\\GlobalObjects'
    elif file_name.endswith('.ggfx') and '-me) graphic symbols' in file_name:
        return 'Graphic Symbols ME', '{ProjectName}\\Visualization\\FTViewME\\GlobalObjects'
    elif file_name.endswith('.gfx') and '-se)' in file_name:
        return 'Faceplate SE', '{ProjectName}\\Visualization\\FTViewSE\\Displays'
    elif file_name.endswith('.gfx') and '-me)' in file_name:
        return 'Faceplate ME', '{ProjectName}\\Visualization\\FTViewME\\Displays'
    elif file_name.endswith('.vpd'):
        return 'View Designer', '{ProjectName}\\Visualization\\ViewDesigner'
    elif file_name.endswith('.pdf'):
        return 'Reference Manual', '{ProjectName}\\Documentation'
    elif file_name.endswith ('images.zip'):
        return 'HMI Image Set', '{ProjectName}\\Visualization\\Images'
    elif file_name.endswith('.csv'):
        return 'HMI Tag', '{ProjectName}\\Visualization'
    else:
        return '', ''  # Default for unmatched files



def main():
    st.title("ACM HSL4 Attribute Validator and Editor")
    st.set_page_config(layout="wide")

    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Attribute Editor", "Extraction Path Validator", "Attachments Validator", "Inf_Lib / Inf_Type Validator", "DataExchangeId Remover", "ParentModPortId Updater"])

    with tab1:
        # File uploader shared across Attribute Editor, Extraction Path Validator, and Inf_Lib/Inf_Type Validator
        uploaded_hsl_files = st.file_uploader(
            "Select one or more .HSL4 XML files",
            type=["HSL4", "xml"],
            accept_multiple_files=True,
            key="uploader_shared"
        )

        st.markdown("""
        ### Instructions
        - Upload one or more `.HSL4` XML files (usually from `ApplicationCodeManagerLibraries`).
        - Review and edit the attributes in the table below.
        - The 'Status Check' column shows ❌ for rows with issues and ✅ for rows with no issues.
        - The 'Issue Details' column lists specific validation errors for each row.
        - After editing, review detected changes in a second table and click 'Apply Changes' to update the files.
        - Download the updated files as a ZIP archive.
        """)

        if uploaded_hsl_files:
            file_attributes = extract_attributes_from_files(uploaded_hsl_files)
            if not file_attributes:
                st.warning("No valid .HSL4 XML files were uploaded or parsed.")
            else:
                # Initialize session state for attributes
                if "pending_changes" not in st.session_state:
                    st.session_state.pending_changes = []
                if "updates" not in st.session_state:
                    st.session_state.updates = {}
                if "updates_applied" not in st.session_state:
                    st.session_state.updates_applied = False

                data = []
                for file_name, attr_data in file_attributes.items():
                    for i, attr in enumerate(attr_data["attributes"]):
                        issues = []
                        if attr_data["Status"] != "Published":
                            issues.append("Status should be 'Published'")
                        #print("hsl---", attr["ModifiedBy"])
                        if attr["ModifiedBy"] != "Rockwell Automation":
                            issues.append("ModifiedBy should be 'Rockwell Automation'")
                        if attr["ModifiedDate"] != "":
                            issues.append("ModifiedDate should be blank")
                        if attr["Owner"] != "Rockwell Automation":
                            issues.append("Owner should be 'Rockwell Automation'")
                        if attr["DataExchangeId"] != "":
                            issues.append("DataExchangeId should be blank")
                        
                        status_check = "❌" if issues else "✅"
                        issue_details = "; ".join(issues) if issues else "All okay"

                        data.append({
                            "File Name": file_name,
                            "Status": attr_data["Status"],
                            "Rev": f"Rev {i+1}",
                            "ModifiedBy": attr["ModifiedBy"],
                            "ModifiedDate": attr["ModifiedDate"],
                            "Owner": attr["Owner"],
                            "DataExchangeId": attr["DataExchangeId"],
                            "Status Check": status_check,
                            "Issue Details": issue_details,
                            "_file_name": file_name,
                            "_rev_index": i
                        })

                df = pd.DataFrame(data)

                st.markdown("### Edit Attributes Table")
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "File Name": st.column_config.TextColumn("File Name", disabled=True),
                        "Status": st.column_config.TextColumn("Status"),
                        "Rev": st.column_config.TextColumn("Rev", disabled=True),
                        "ModifiedBy": st.column_config.TextColumn("ModifiedBy"),
                        "ModifiedDate": st.column_config.TextColumn("ModifiedDate"),
                        "Owner": st.column_config.TextColumn("Owner"),
                        "DataExchangeId": st.column_config.TextColumn("DataExchangeId"),
                        "Status Check": st.column_config.TextColumn("Status Check", disabled=True),
                        "Issue Details": st.column_config.TextColumn("Issue Details", disabled=True),
                        "_file_name": None,
                        "_rev_index": None
                    },
                    key="attribute_table",
                    num_rows="fixed",
                    hide_index=True
                )

                # Detect changes
                st.session_state.pending_changes = []
                for i, row in edited_df.iterrows():
                    file_name = row["_file_name"]
                    rev_index = row["_rev_index"]
                    attr_data = file_attributes[file_name]
                    changes = []

                    if row["Status"] != attr_data["Status"]:
                        changes.append({
                            "Field": "Status",
                            "Old Value": attr_data["Status"],
                            "New Value": row["Status"]
                        })
                    if row["ModifiedBy"] != attr_data["attributes"][rev_index]["ModifiedBy"]:
                        changes.append({
                            "Field": "ModifiedBy",
                            "Old Value": attr_data["attributes"][rev_index]["ModifiedBy"],
                            "New Value": row["ModifiedBy"]
                        })
                    if row["ModifiedDate"] != attr_data["attributes"][rev_index]["ModifiedDate"]:
                        changes.append({
                            "Field": "ModifiedDate",
                            "Old Value": attr_data["attributes"][rev_index]["ModifiedDate"],
                            "New Value": row["ModifiedDate"]
                        })
                    if row["Owner"] != attr_data["attributes"][rev_index]["Owner"]:
                        changes.append({
                            "Field": "Owner",
                            "Old Value": attr_data["attributes"][rev_index]["Owner"],
                            "New Value": row["Owner"]
                        })
                    if row["DataExchangeId"] != attr_data["attributes"][rev_index]["DataExchangeId"]:
                        changes.append({
                            "Field": "DataExchangeId",
                            "Old Value": attr_data["attributes"][rev_index]["DataExchangeId"],
                            "New Value": row["DataExchangeId"]
                        })

                    if changes:
                        st.session_state.pending_changes.append({
                            "File Name": file_name,
                            "Rev": row["Rev"],
                            "_file_name": file_name,
                            "_rev_index": rev_index,
                            "Changes": changes
                        })

                # Display changes table if there are pending changes
                if st.session_state.pending_changes and not st.session_state.updates_applied:
                    st.markdown("### Detected Changes")
                    change_data = []
                    for change in st.session_state.pending_changes:
                        for c in change["Changes"]:
                            change_data.append({
                                "File Name": change["File Name"],
                                "Rev": change["Rev"],
                                "Field": c["Field"],
                                "Old Value": c["Old Value"],
                                "New Value": c["New Value"]
                            })

                    change_df = pd.DataFrame(change_data)
                    st.dataframe(
                        change_df,
                        column_config={
                            "File Name": st.column_config.TextColumn("File Name"),
                            "Rev": st.column_config.TextColumn("Rev"),
                            "Field": st.column_config.TextColumn("Field"),
                            "Old Value": st.column_config.TextColumn("Old Value"),
                            "New Value": st.column_config.TextColumn("New Value")
                        },
                        hide_index=True
                    )

                    if st.button("Apply Changes", key="apply_changes_attributes"):
                        updates = {}
                        for change in st.session_state.pending_changes:
                            file_name = change["_file_name"]
                            rev_index = change["_rev_index"]
                            attr_data = file_attributes[file_name]

                            for c in change["Changes"]:
                                if c["Field"] == "Status":
                                    root = attr_data["tree"].getroot()
                                    root.attrib["Status"] = c["New Value"]
                                    attr_data["Status"] = c["New Value"]
                                else:
                                    rev = attr_data["attributes"][rev_index]["Rev"]
                                    header = attr_data["attributes"][rev_index]["Header"]
                                    modules = attr_data["attributes"][rev_index]["Modules"]
                                    if c["Field"] == "ModifiedBy":
                                        rev.attrib["ModifiedBy"] = c["New Value"]
                                        attr_data["attributes"][rev_index]["ModifiedBy"] = c["New Value"]
                                    elif c["Field"] == "ModifiedDate":
                                        rev.attrib["ModifiedDate"] = c["New Value"]
                                        attr_data["attributes"][rev_index]["ModifiedDate"] = c["New Value"]
                                    elif c["Field"] == "Owner":
                                        header.attrib["Owner"] = c["New Value"]
                                        attr_data["attributes"][rev_index]["Owner"] = c["New Value"]
                                    elif c["Field"] == "DataExchangeId":
                                        for module in modules:
                                            if c["New Value"] == "":
                                                if "DataExchangeId" in module.attrib:
                                                    del module.attrib["DataExchangeId"]
                                            else:
                                                module.attrib["DataExchangeId"] = c["New Value"]
                                        attr_data["attributes"][rev_index]["DataExchangeId"] = c["New Value"]

                            updates[file_name] = attr_data["tree"]

                        st.session_state.updates = updates
                        st.session_state.updates_applied = True
                        st.success("Changes applied successfully!")

                # Show download button only after updates are applied
                if st.session_state.updates_applied and st.session_state.updates:
                    st.markdown("### Download Updated Files")
                    out_io = io.BytesIO()
                    with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                        for file_name, tree in st.session_state.updates.items():
                            xml_bytes = io.BytesIO()
                            tree.write(xml_bytes, encoding='utf-8', xml_declaration=True, pretty_print=True)
                            zout.writestr(file_name, xml_bytes.getvalue())
                    out_io.seek(0)

                    st.download_button(
                        label="Download Updated ZIP",
                        data=out_io,
                        file_name="updated_HSL4_files.zip",
                        mime="application/zip",
                        key="download_zip_attributes"
                    )
                elif not st.session_state.pending_changes:
                    st.info("No changes detected to apply or download.")

                # Reset updates_applied if table is edited again
                if st.session_state.attribute_table.get("edited_rows"):
                    st.session_state.updates_applied = False

    with tab2:
        st.markdown("""
        ### Extraction Path Validator
        - Uses the same `.HSL4` XML files uploaded above to validate ExtractionPath attributes.
        - The table shows ExtractionPath values and checks if they match valid paths.
        - Invalid paths are displayed in the table and can be edited using the dropdown menu with valid options.
        - Apply changes and download the updated files as a ZIP archive.
        """)

        uploaded_hsl_files = st.session_state.get("uploader_shared", [])
        if uploaded_hsl_files:
            file_attributes = extract_attributes_from_files(uploaded_hsl_files)
            if not file_attributes:
                st.warning("No valid .HSL4 XML files were uploaded or parsed.")
            else:
                # Initialize session state for extraction paths
                if "pending_path_changes" not in st.session_state:
                    st.session_state.pending_path_changes = []
                if "path_updates" not in st.session_state:
                    st.session_state.path_updates = {}
                if "path_updates_applied" not in st.session_state:
                    st.session_state.path_updates_applied = False

                path_data = []
                for file_name, attr_data in file_attributes.items():
                    for i, path in enumerate(attr_data["extraction_paths"]):
                        is_valid = path["Value"] in COMPARISON_STRINGS
                        status_check = "✅" if is_valid else "❌"
                        issue_details = "Valid path" if is_valid else f"Invalid ExtractionPath: {path['Value']}"

                        path_data.append({
                            "File Name": file_name,
                            "Path Index": f"Path {i+1}",
                            "ExtractionPath": path["Value"],
                            "Status Check": status_check,
                            "Issue Details": issue_details,
                            "_file_name": file_name,
                            "_path_index": i
                        })

                path_df = pd.DataFrame(path_data)

                st.markdown("### Edit Extraction Paths")
                edited_path_df = st.data_editor(
                    path_df,
                    column_config={
                        "File Name": st.column_config.TextColumn("File Name", disabled=True),
                        "Path Index": st.column_config.TextColumn("Path Index", disabled=True),
                        "ExtractionPath": st.column_config.SelectboxColumn(
                            "ExtractionPath",
                            options=[""] + COMPARISON_STRINGS,
                            required=False
                        ),
                        "Status Check": st.column_config.TextColumn("Status Check", disabled=True),
                        "Issue Details": st.column_config.TextColumn("Issue Details", disabled=True),
                        "_file_name": None,
                        "_path_index": None
                    },
                    key="extraction_path_table",
                    num_rows="fixed",
                    hide_index=True
                )

                # Detect changes
                st.session_state.pending_path_changes = []
                for i, row in edited_path_df.iterrows():
                    file_name = row["_file_name"]
                    path_index = row["_path_index"]
                    attr_data = file_attributes[file_name]
                    if row["ExtractionPath"] != attr_data["extraction_paths"][path_index]["Value"]:
                        st.session_state.pending_path_changes.append({
                            "File Name": file_name,
                            "Path Index": row["Path Index"],
                            "_file_name": file_name,
                            "_path_index": path_index,
                            "Changes": [{
                                "Field": "ExtractionPath",
                                "Old Value": attr_data["extraction_paths"][path_index]["Value"],
                                "New Value": row["ExtractionPath"]
                            }]
                        })

                # Display changes table if there are pending changes
                if st.session_state.pending_path_changes and not st.session_state.path_updates_applied:
                    st.markdown("### Detected ExtractionPath Changes")
                    path_change_data = []
                    for change in st.session_state.pending_path_changes:
                        for c in change["Changes"]:
                            path_change_data.append({
                                "File Name": change["File Name"],
                                "Path Index": change["Path Index"],
                                "Field": c["Field"],
                                "Old Value": c["Old Value"],
                                "New Value": c["New Value"]
                            })

                    path_change_df = pd.DataFrame(path_change_data)
                    st.dataframe(
                        path_change_df,
                        column_config={
                            "File Name": st.column_config.TextColumn("File Name"),
                            "Path Index": st.column_config.TextColumn("Path Index"),
                            "Field": st.column_config.TextColumn("Field"),
                            "Old Value": st.column_config.TextColumn("Old Value"),
                            "New Value": st.column_config.TextColumn("New Value")
                        },
                        hide_index=True
                    )

                    if st.button("Apply ExtractionPath Changes", key="apply_changes_paths"):
                        path_updates = {}
                        for change in st.session_state.pending_path_changes:
                            file_name = change["_file_name"]
                            path_index = change["_path_index"]
                            attr_data = file_attributes[file_name]

                            for c in change["Changes"]:
                                if c["Field"] == "ExtractionPath":
                                    item = attr_data["extraction_paths"][path_index]["Item"]
                                    value_element = item.find("Value")
                                    if value_element is not None:
                                        value_element.text = c["New Value"]
                                    attr_data["extraction_paths"][path_index]["Value"] = c["New Value"]

                            path_updates[file_name] = attr_data["tree"]

                        st.session_state.path_updates = path_updates
                        st.session_state.path_updates_applied = True
                        st.success("ExtractionPath changes applied successfully!")

                # Show download button for ExtractionPath updates
                if st.session_state.path_updates_applied and st.session_state.path_updates:
                    st.markdown("### Download Updated Files (Extraction Paths)")
                    out_io = io.BytesIO()
                    with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                        for file_name, tree in st.session_state.path_updates.items():
                            xml_bytes = io.BytesIO()
                            tree.write(xml_bytes, encoding='utf-8', xml_declaration=True, pretty_print=True)
                            zout.writestr(file_name, xml_bytes.getvalue())
                    out_io.seek(0)

                    st.download_button(
                        label="Download Updated ZIP (Extraction Paths)",
                        data=out_io,
                        file_name="updated_HSL4_extraction_paths.zip",
                        mime="application/zip",
                        key="download_zip_paths"
                    )
                elif not st.session_state.pending_path_changes:
                    st.info("No ExtractionPath changes detected to apply or download.")

                # Reset updates_applied if table is edited again
                if st.session_state.extraction_path_table.get("edited_rows"):
                    st.session_state.path_updates_applied = False
        else:
            st.info("Please upload .HSL4 files in the **Attribute Editor** tab to validate Extraction Paths.")

    with tab3:
        st.markdown("""
        ### Attachments Validator
        - Upload a mix of `.txt` and `.HZ1` files (or a ZIP containing them).
        - Review/edit fields from `.txt`. When you apply, the linked `.HZ1` (matched by `File_ID`) is updated:
        - `Desc` ← **Description**
        - `RevDesc` ← **Revision_Description**
        - `ChangeDate` ← **Modified_Date** (normalized to `YYYY-MM-DDTHH:MM:SS`)
        - `ChangeUser` ← **Modified_By**
        - `FileName` + `Ext` ← **File_Name** (if present)
        - Download a ZIP containing **both** updated `.txt` and `.HZ1`.
        """)

        # File uploader for Attachments (text files or ZIP)
        uploaded_attachment_files = st.file_uploader(
            "Select one or more Attachment .txt files or a ZIP file",
            type=["txt", "hz1", "zip"],
            accept_multiple_files=True,
            key="uploader_attachments"
        )

        # Separate file lists from uploads (+ zip expansion)
        attachment_txt_files, hz1_files = [], []

        if uploaded_attachment_files:
            for uploaded_file in uploaded_attachment_files:
                name_lower = uploaded_file.name.lower()

                if name_lower.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(uploaded_file, 'r') as zip_file:
                            for member in zip_file.namelist():
                                ml = member.lower()
                                if ml.endswith('.txt') or ml.endswith('.hz1'):
                                    data = zip_file.read(member)
                                    if ml.endswith('.txt'):
                                        attachment_txt_files.append(InMemoryUpload(member, data))
                                    else:
                                        hz1_files.append(InMemoryUpload(member, data))
                    except zipfile.BadZipFile:
                        st.error(f"File '{uploaded_file.name}' is not a valid ZIP file.")
                elif name_lower.endswith('.txt'):
                    attachment_txt_files.append(uploaded_file)
                elif name_lower.endswith('.hz1'):
                    hz1_files.append(uploaded_file)

        if attachment_txt_files:
            attachment_attributes = extract_attachment_attributes(attachment_txt_files)
            if not attachment_attributes:
                st.warning("No valid .txt files were uploaded or parsed successfully.")
            else:
                # Parse HZ1 index for cross-updates
                hz1_index = extract_hz1_index(hz1_files)
                # Keep index in state for later apply
                st.session_state["hz1_index"] = hz1_index

                # Initialize session state for attachments
                if "pending_attachment_changes" not in st.session_state:
                    st.session_state.pending_attachment_changes = []
                if "attachment_updates" not in st.session_state:
                    st.session_state.attachment_updates = {}
                if "hz1_updates" not in st.session_state:
                    st.session_state.hz1_updates = {}
                if "attachment_updates_applied" not in st.session_state:
                    st.session_state.attachment_updates_applied = False

                attachment_data = []
                for file_name, attr_data in attachment_attributes.items():
                    for i, attr in enumerate(attr_data["attributes"]):
                        issues = []

                        found_description = attr["Description"]
                        found_extraction_path = attr["Extraction_Path"]

                        valid_descriptions = [
                            'Toolbox SE', 'Toolbox ME', 'Graphic Symbols SE', 'Graphic Symbols ME',
                            'Faceplate SE', 'Faceplate ME', 'View Designer', 'Reference Manual',
                            'HMI Image Set', 'HMI Tag'
                        ]
                        if not found_description or found_description not in valid_descriptions:
                            issues.append(f"Invalid Description: {found_description if found_description else 'blank'}")

                        if not found_extraction_path or found_extraction_path not in COMPARISON_STRINGS:
                            issues.append(f"Invalid Extraction_Path: {found_extraction_path if found_extraction_path else 'blank'}")

                        # Derive new values if found values are invalid
                        derived_description, derived_extraction_path = derive_description_and_path(attr["File_Name"])
                        new_description = derived_description if (not found_description or found_description not in valid_descriptions) else found_description
                        new_extraction_path = derived_extraction_path if (not found_extraction_path or found_extraction_path not in COMPARISON_STRINGS) else found_extraction_path

                        status_check = "❌" if issues else "✅"
                        issue_details = "; ".join(issues) if issues else "All okay"

                        file_id = attr.get("File_ID", "")
                        hz1_match = "✅" if file_id and file_id in hz1_index else "❌"

                        attachment_data.append({
                            "File Name": file_name,
                            "Index": f"Entry {i+1}",
                            "File_ID": file_id,
                            "HZ1 Match": hz1_match,
                            "File_Name": attr["File_Name"],
                            "Found Description": found_description,
                            "New Description": new_description,
                            "Found Extraction_Path": found_extraction_path,
                            "New Extraction_Path": new_extraction_path,
                            "Revision_Description": attr["Revision_Description"],
                            "Modified_Date": attr["Modified_Date"],
                            "Modified_By": attr["Modified_By"],
                            "Status Check": status_check,
                            "Issue Details": issue_details,
                            "_file_name": file_name,
                            "_entry_index": i
                        })

                if not attachment_data:
                    st.warning("No valid attributes were extracted from the uploaded files.")
                else:
                    attachment_df = pd.DataFrame(attachment_data)

                    st.markdown("### Edit Attachment Attributes")
                    edited_attachment_df = st.data_editor(
                        attachment_df,
                        column_config={
                            "File Name": st.column_config.TextColumn("File Name", disabled=True),
                            "Index": st.column_config.TextColumn("Index", disabled=True),
                            "File_ID": st.column_config.TextColumn("File_ID", disabled=True),
                            "HZ1 Match": st.column_config.TextColumn("HZ1 Match", disabled=True),
                            "File_Name": st.column_config.TextColumn("File_Name", disabled=True),
                            "Found Description": st.column_config.TextColumn("Found Description", disabled=True),
                            "New Description": st.column_config.TextColumn("New Description", default='', required=False),
                            "Found Extraction_Path": st.column_config.TextColumn("Found Extraction_Path", disabled=True),
                            "New Extraction_Path": st.column_config.TextColumn("New Extraction_Path", default='', required=False),
                            "Revision_Description": st.column_config.TextColumn("Revision_Description"),
                            "Modified_Date": st.column_config.TextColumn("Modified_Date"),
                            "Modified_By": st.column_config.TextColumn("Modified_By"),
                            "Status Check": st.column_config.TextColumn("Status Check", disabled=True),
                            "Issue Details": st.column_config.TextColumn("Issue Details", disabled=True),
                            "_file_name": None,
                            "_entry_index": None
                        },
                        key="attachment_table",
                        num_rows="fixed",
                        hide_index=True
                    )

                    # Detect changes in attachment attributes
                    st.session_state.pending_attachment_changes = []
                    for i, row in edited_attachment_df.iterrows():
                        file_name = row["_file_name"]
                        entry_index = row["_entry_index"]
                        attr_data = attachment_attributes[file_name]["attributes"][entry_index]

                        changes = []
                        found_description = row["Found Description"]
                        found_extraction_path = row["Found Extraction_Path"]

                        new_description = row["New Description"] if row["New Description"] else found_description
                        new_extraction_path = row["New Extraction_Path"] if row["New Extraction_Path"] else found_extraction_path

                        if new_description != found_description:
                            changes.append({
                                "Field": "Description",
                                "Old Value": found_description,
                                "New Value": new_description
                            })
                        if new_extraction_path != found_extraction_path:
                            changes.append({
                                "Field": "Extraction_Path",
                                "Old Value": found_extraction_path,
                                "New Value": new_extraction_path
                            })
                        if row["Revision_Description"] != attr_data["Revision_Description"]:
                            changes.append({
                                "Field": "Revision_Description",
                                "Old Value": attr_data["Revision_Description"],
                                "New Value": row["Revision_Description"]
                            })
                        if row["Modified_Date"] != attr_data["Modified_Date"]:
                            changes.append({
                                "Field": "Modified_Date",
                                "Old Value": attr_data["Modified_Date"],
                                "New Value": row["Modified_Date"]
                            })
                        if row["Modified_By"] != attr_data["Modified_By"]:
                            changes.append({
                                "Field": "Modified_By",
                                "Old Value": attr_data["Modified_By"],
                                "New Value": row["Modified_By"]
                            })

                        if changes:
                            st.session_state.pending_attachment_changes.append({
                                "File Name": file_name,
                                "Index": row["Index"],
                                "_file_name": file_name,
                                "_entry_index": entry_index,
                                "Changes": changes
                            })

                    # Display changes table if there are pending changes
                    if st.session_state.pending_attachment_changes and not st.session_state.attachment_updates_applied:
                        st.markdown("### Detected Attachment Changes")
                        attachment_change_data = []
                        for change in st.session_state.pending_attachment_changes:
                            for c in change["Changes"]:
                                attachment_change_data.append({
                                    "File Name": change["File Name"],
                                    "Index": change["Index"],
                                    "Field": c["Field"],
                                    "Old Value": c["Old Value"],
                                    "New Value": c["New Value"]
                                })
                        attachment_change_df = pd.DataFrame(attachment_change_data)
                        st.dataframe(
                            attachment_change_df,
                            column_config={
                                "File Name": st.column_config.TextColumn("File Name"),
                                "Index": st.column_config.TextColumn("Index"),
                                "Field": st.column_config.TextColumn("Field"),
                                "Old Value": st.column_config.TextColumn("Old Value"),
                                "New Value": st.column_config.TextColumn("New Value")
                            },
                            hide_index=True
                        )

                    if st.button("Apply Attachment Changes", key="apply_changes_attachments"):
                        attachment_updates = {}
                        hz1_updates = st.session_state.get("hz1_updates", {})
                        hz1_index = st.session_state.get("hz1_index", {})

                        # First: apply edits to in-memory .txt attributes
                        for change in st.session_state.pending_attachment_changes:
                            file_name = change["_file_name"]
                            entry_index = change["_entry_index"]
                            attr_file = attachment_attributes[file_name]
                            original_lines = attr_file["original_content"]

                            # Apply changes to structured dict
                            for c in change["Changes"]:
                                field = c["Field"]
                                new_value = c["New Value"]
                                if field == "Description":
                                    attr_file["attributes"][entry_index]["Description"] = new_value
                                elif field == "Extraction_Path":
                                    attr_file["attributes"][entry_index]["Extraction_Path"] = new_value
                                else:
                                    attr_file["attributes"][entry_index][field] = new_value

                            # Reconstruct the text only once per file (after all its entries are updated)
                            # We'll rebuild after the loop over all changes for this file
                        # Rebuild ALL .txt contents (reflecting the latest in-memory attributes)
                        for file_name, attr_file in attachment_attributes.items():
                            original_lines = attr_file["original_content"]
                            updated_content = []
                            attr_index_map = {attr["original_line_index"]: i for i, attr in enumerate(attr_file["attributes"])}
                            for i, line in enumerate(original_lines):
                                if i in attr_index_map:
                                    a = attr_file["attributes"][attr_index_map[i]]
                                    # Rebuild this CSV-like line preserving order where possible
                                    updated_attrs = []
                                    for attr_pair in line.split(','):
                                        key = attr_pair.split('=')[0].strip()
                                        # Map Revison_Description -> Revision_Description on output
                                        out_key = 'Revision_Description' if key == 'Revison_Description' else key
                                        if out_key in a:
                                            updated_attrs.append(f"{out_key}='{a[out_key]}'")
                                        else:
                                            updated_attrs.append(attr_pair.strip())
                                    updated_content.append(", ".join(updated_attrs))
                                else:
                                    updated_content.append(line)
                            attachment_updates[file_name] = "\n".join(updated_content)

                        # Now: propagate to HZ1 per entry using the final values currently in attr_file["attributes"]
                        missing_hz1 = []
                        for file_name, attr_file in attachment_attributes.items():
                            for a in attr_file["attributes"]:
                                file_id = (a.get("File_ID") or "").strip()
                                if not file_id:
                                    continue
                                hz1 = hz1_index.get(file_id)
                                if not hz1:
                                    missing_hz1.append(file_id)
                                    continue

                                root = hz1["root"]
                                # Apply mapping (blank values do not overwrite)
                                if a.get("Description"):
                                    root.attrib["Desc"] = a["Description"]
                                if a.get("Revision_Description"):
                                    root.attrib["RevDesc"] = a["Revision_Description"]
                                if a.get("Modified_By"):
                                    root.attrib["ChangeUser"] = a["Modified_By"]
                                if a.get("Modified_Date"):
                                    root.attrib["ChangeDate"] = normalize_change_date((a["Modified_Date"]))
                                    print(root.attrib["ChangeDate"])
                                if a.get("File_Name"):
                                    root.attrib["FileName"] = a["File_Name"]
                                    # Derive Ext from File_Name extension
                                    m = re.search(r"\.([A-Za-z0-9]+)$", a["File_Name"])
                                    if m:
                                        root.attrib["Ext"] = m.group(1)

                                # Keep the tree ready for zip
                                hz1_updates[hz1["file_name"]] = hz1["tree"]

                        if missing_hz1:
                            st.warning(f"No matching .HZ1 found for File_ID(s): {', '.join(sorted(set(missing_hz1)))}")

                        st.session_state.attachment_updates = attachment_updates
                        st.session_state.hz1_updates = hz1_updates
                        st.session_state.attachment_updates_applied = True
                        st.success("Attachment and HZ1 changes applied successfully!")

                    # Show download button for attachment + HZ1 updates
                    if st.session_state.attachment_updates_applied and (st.session_state.attachment_updates or st.session_state.hz1_updates):
                        st.markdown("### Download Updated Attachment + HZ1 Files")
                        out_io = io.BytesIO()
                        with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                            # .txt files
                            for file_name, content in st.session_state.attachment_updates.items():
                                zout.writestr(file_name, content.encode('utf-8'))
                            # .HZ1 files
                            for file_name, tree in st.session_state.hz1_updates.items():
                                xml_bytes = io.BytesIO()
                                tree.write(xml_bytes, encoding='utf-8', xml_declaration=True, pretty_print=True)
                                zout.writestr(file_name, xml_bytes.getvalue())
                        out_io.seek(0)
                        st.download_button(
                            label="Download Updated ZIP (.txt + .HZ1)",
                            data=out_io,
                            file_name="updated_attachment_and_hz1_files.zip",
                            mime="application/zip",
                            key="download_zip_attachments_hz1"
                        )
                    elif not st.session_state.pending_attachment_changes:
                        st.info("No attachment changes detected to apply or download.")

                    # Reset updates_applied if table is edited again
                    if st.session_state.attachment_table.get("edited_rows"):
                        st.session_state.attachment_updates_applied = False
        else:
            st.info("Please upload .txt/.HZ1 files or a ZIP containing them to validate attachments.")

    with tab4:
        st.markdown("""
        ### Inf_Lib / Inf_Type Validator
        - Validates `Inf_Lib` and `Inf_Type` tag attributes from **raC_LD** (Library Device) files only.
        - Asset-Control definition files are skipped (they don't contain these values).
        - When both Controller and Program scope tags exist, their `Inf_Lib` and `Inf_Type` values must match.
        - Also validates that `Librarys > Library` (extended properties) matches `Inf_Lib` for each scope.
        - The 'Status Check' column shows ❌ for mismatches and ✅ when values match.
        """)

        uploaded_hsl_files = st.session_state.get("uploader_shared", [])
        if uploaded_hsl_files:
            inf_file_data = extract_inf_lib_type_from_files(uploaded_hsl_files)
            if not inf_file_data:
                st.warning("No valid .HSL4 XML files were uploaded or parsed.")
            else:
                inf_data = []
                skipped_files = []
                
                for file_name, data in inf_file_data.items():
                    # Skip non-raC_LD files
                    if not data["is_ld_file"]:
                        skipped_files.append(file_name)
                        continue
                    
                    if not data["tags"]:
                        inf_data.append({
                            "File Name": file_name,
                            "Controller Inf_Lib": "",
                            "Controller Inf_Type": "",
                            "Controller ExtProp Library": "",
                            "Controller ExtProp Instruction": "",
                            "Program Inf_Lib": "",
                            "Program Inf_Type": "",
                            "Program ExtProp Library": "",
                            "Program ExtProp Instruction": "",
                            "Status Check": "⚠️",
                            "Issue Details": "No AOI tags with Inf_Lib/Inf_Type found"
                        })
                    else:
                        # Group tags by scope
                        controller_tags = [t for t in data["tags"] if t["Scope"] == "Controller"]
                        program_tags = [t for t in data["tags"] if t["Scope"] == "Program"]
                        
                        # Get values (use first tag of each scope if multiple exist)
                        ctrl_inf_lib = controller_tags[0]["Inf_Lib"] if controller_tags else ""
                        ctrl_inf_type = controller_tags[0]["Inf_Type"] if controller_tags else ""
                        ctrl_ext_library = controller_tags[0]["ExtLibrary"] if controller_tags else ""
                        ctrl_ext_instruction = controller_tags[0]["ExtInstruction"] if controller_tags else ""
                        prog_inf_lib = program_tags[0]["Inf_Lib"] if program_tags else ""
                        prog_inf_type = program_tags[0]["Inf_Type"] if program_tags else ""
                        prog_ext_library = program_tags[0]["ExtLibrary"] if program_tags else ""
                        prog_ext_instruction = program_tags[0]["ExtInstruction"] if program_tags else ""
                        
                        issues = []
                        
                        # Check if both scopes exist
                        if controller_tags and program_tags:
                            # Compare Inf_Lib values
                            if ctrl_inf_lib != prog_inf_lib:
                                issues.append(f"Inf_Lib mismatch: Controller='{ctrl_inf_lib}' vs Program='{prog_inf_lib}'")
                            # Compare Inf_Type values
                            if ctrl_inf_type != prog_inf_type:
                                issues.append(f"Inf_Type mismatch: Controller='{ctrl_inf_type}' vs Program='{prog_inf_type}'")
                        elif not controller_tags and not program_tags:
                            issues.append("No Controller or Program scope tags found")
                        
                        # Check for empty values
                        if controller_tags:
                            if not ctrl_inf_lib:
                                issues.append("Controller Inf_Lib is empty")
                            if not ctrl_inf_type:
                                issues.append("Controller Inf_Type is empty")
                        if program_tags:
                            if not prog_inf_lib:
                                issues.append("Program Inf_Lib is empty")
                            if not prog_inf_type:
                                issues.append("Program Inf_Type is empty")
                        
                        # Validate Library (extended properties) matches Inf_Lib
                        if controller_tags:
                            if not ctrl_ext_library:
                                issues.append("Controller Library (extended property) is empty")
                            elif ctrl_ext_library != ctrl_inf_lib:
                                issues.append(f"Controller Library mismatch: Library='{ctrl_ext_library}' vs Inf_Lib='{ctrl_inf_lib}'")
                        if program_tags:
                            if not prog_ext_library:
                                issues.append("Program Library (extended property) is empty")
                            elif prog_ext_library != prog_inf_lib:
                                issues.append(f"Program Library mismatch: Library='{prog_ext_library}' vs Inf_Lib='{prog_inf_lib}'")
                        
                        # Validate Instruction (extended properties) matches Inf_Type
                        if controller_tags:
                            if not ctrl_ext_instruction:
                                issues.append("Controller Instruction (extended property) is empty")
                            elif ctrl_ext_instruction != ctrl_inf_type:
                                issues.append(f"Controller Instruction mismatch: Instruction='{ctrl_ext_instruction}' vs Inf_Type='{ctrl_inf_type}'")
                        if program_tags:
                            if not prog_ext_instruction:
                                issues.append("Program Instruction (extended property) is empty")
                            elif prog_ext_instruction != prog_inf_type:
                                issues.append(f"Program Instruction mismatch: Instruction='{prog_ext_instruction}' vs Inf_Type='{prog_inf_type}'")
                        
                        status_check = "❌" if issues else "✅"
                        issue_details = "; ".join(issues) if issues else "All okay - values match"
                        
                        inf_data.append({
                            "File Name": file_name,
                            "Controller Inf_Lib": ctrl_inf_lib,
                            "Controller Inf_Type": ctrl_inf_type,
                            "Controller ExtProp Library": ctrl_ext_library,
                            "Controller ExtProp Instruction": ctrl_ext_instruction,
                            "Program Inf_Lib": prog_inf_lib,
                            "Program Inf_Type": prog_inf_type,
                            "Program ExtProp Library": prog_ext_library,
                            "Program ExtProp Instruction": prog_ext_instruction,
                            "Status Check": status_check,
                            "Issue Details": issue_details
                        })
                
                # Show skipped files info
                if skipped_files:
                    st.info(f"**Skipped {len(skipped_files)} Asset-Control/Definition file(s):** {', '.join(skipped_files)}")
                
                if inf_data:
                    inf_df = pd.DataFrame(inf_data)
                    
                    st.markdown("### Inf_Lib / Inf_Type / Library Comparison (Controller vs Program)")
                    st.dataframe(
                        inf_df,
                        column_config={
                            "File Name": st.column_config.TextColumn("File Name"),
                            "Controller Inf_Lib": st.column_config.TextColumn("Controller Inf_Lib"),
                            "Controller Inf_Type": st.column_config.TextColumn("Controller Inf_Type"),
                            "Controller ExtProp Library": st.column_config.TextColumn("Controller ExtProp Library"),
                            "Controller ExtProp Instruction": st.column_config.TextColumn("Controller ExtProp Instruction"),
                            "Program Inf_Lib": st.column_config.TextColumn("Program Inf_Lib"),
                            "Program Inf_Type": st.column_config.TextColumn("Program Inf_Type"),
                            "Program ExtProp Library": st.column_config.TextColumn("Program ExtProp Library"),
                            "Program ExtProp Instruction": st.column_config.TextColumn("Program ExtProp Instruction"),
                            "Status Check": st.column_config.TextColumn("Status Check"),
                            "Issue Details": st.column_config.TextColumn("Issue Details")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Summary statistics
                    total_files = len(inf_data)
                    valid_files = len([d for d in inf_data if d["Status Check"] == "✅"])
                    invalid_files = len([d for d in inf_data if d["Status Check"] == "❌"])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total raC_LD Files", total_files)
                    with col2:
                        st.metric("Valid (Match)", valid_files)
                    with col3:
                        st.metric("Issues (Mismatch)", invalid_files)
                else:
                    st.info("No raC_LD files found. Only raC_LD (Library Device) files contain Inf_Lib/Inf_Type values.")
        else:
            st.info("Please upload .HSL4 files in the **Attribute Editor** tab to validate Inf_Lib and Inf_Type values.")

    with tab5:
        st.markdown("""
        ### DataExchangeId Remover
        - Upload one or more **Module-type** `.HSL4` / `.HSL` files.
        - The tool scans every file for `DataExchangeId="..."` attributes (added during export).
        - Review the occurrences found, then click **Remove & Download** to get cleaned files.
        - **No other content in the files is modified.**
        """)

        uploaded_dxid_files = st.file_uploader(
            "Select one or more Module-type HSL files",
            type=["HSL4", "HSL", "xml"],
            accept_multiple_files=True,
            key="uploader_dxid"
        )

        if uploaded_dxid_files:
            # Read raw content and find DataExchangeId occurrences
            dxid_pattern = re.compile(r'\s+DataExchangeId="[^"]*"')
            dxid_summary = []
            dxid_file_contents = {}

            for uf in uploaded_dxid_files:
                raw = uf.read().decode("utf-8")
                matches = dxid_pattern.findall(raw)
                dxid_file_contents[uf.name] = raw
                for m in matches:
                    # Extract just the GUID value for display
                    val_match = re.search(r'DataExchangeId="([^"]*)"', m)
                    dxid_summary.append({
                        "File Name": uf.name,
                        "DataExchangeId": val_match.group(1) if val_match else m.strip(),
                    })

            if dxid_summary:
                st.markdown(f"**Found {len(dxid_summary)} DataExchangeId attribute(s) across {len(dxid_file_contents)} file(s).**")

                dxid_df = pd.DataFrame(dxid_summary)
                st.dataframe(
                    dxid_df,
                    column_config={
                        "File Name": st.column_config.TextColumn("File Name"),
                        "DataExchangeId": st.column_config.TextColumn("DataExchangeId Value"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                if st.button("Remove All DataExchangeId & Download", key="btn_remove_dxid"):
                    out_io = io.BytesIO()
                    with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                        for fname, content in dxid_file_contents.items():
                            cleaned = dxid_pattern.sub("", content)
                            zout.writestr(fname, cleaned.encode("utf-8"))
                    out_io.seek(0)

                    st.success(f"Removed {len(dxid_summary)} DataExchangeId attribute(s). Download below.")
                    st.download_button(
                        label="Download Cleaned HSL Files (ZIP)",
                        data=out_io,
                        file_name="cleaned_HSL_files.zip",
                        mime="application/zip",
                        key="download_zip_dxid",
                    )
            else:
                st.success("No DataExchangeId attributes found in the uploaded files. Files are already clean.")
        else:
            st.info("Upload Module-type HSL files to scan and remove DataExchangeId attributes.")

    with tab6:
        st.markdown("""
        ### ParentModPortId Updater
        - Upload one or more **Module-type** `.HSL4` / `.HSL` files.
        - The tool finds all `ParentModPortId="..."` attributes and replaces the value with `{ParentModulePort}`.
        - Review the occurrences found, then click **Update & Download** to get the modified files.
        - **No other content in the files is modified.**
        """)

        uploaded_pmpid_files = st.file_uploader(
            "Select one or more Module-type HSL files",
            type=["HSL4", "HSL", "xml"],
            accept_multiple_files=True,
            key="uploader_pmpid"
        )

        if uploaded_pmpid_files:
            pmpid_pattern = re.compile(r'ParentModPortId="[^"]*"')
            pmpid_summary = []
            pmpid_file_contents = {}

            for uf in uploaded_pmpid_files:
                raw = uf.read().decode("utf-8")
                matches = pmpid_pattern.findall(raw)
                pmpid_file_contents[uf.name] = raw
                for m in matches:
                    val_match = re.search(r'ParentModPortId="([^"]*)"', m)
                    current_val = val_match.group(1) if val_match else m
                    already_set = current_val == "{ParentModulePort}"
                    pmpid_summary.append({
                        "File Name": uf.name,
                        "Current Value": current_val,
                        "Status": "\u2705 Already correct" if already_set else "\u274c Needs update",
                    })

            if pmpid_summary:
                needs_update = [s for s in pmpid_summary if "Needs update" in s["Status"]]
                st.markdown(f"**Found {len(pmpid_summary)} ParentModPortId attribute(s) across {len(pmpid_file_contents)} file(s). {len(needs_update)} need updating.**")

                pmpid_df = pd.DataFrame(pmpid_summary)
                st.dataframe(
                    pmpid_df,
                    column_config={
                        "File Name": st.column_config.TextColumn("File Name"),
                        "Current Value": st.column_config.TextColumn("Current Value"),
                        "Status": st.column_config.TextColumn("Status"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                if needs_update:
                    if st.button("Update All ParentModPortId & Download", key="btn_update_pmpid"):
                        replacement = 'ParentModPortId="{ParentModulePort}"'
                        out_io = io.BytesIO()
                        with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                            for fname, content in pmpid_file_contents.items():
                                cleaned = pmpid_pattern.sub(replacement, content)
                                zout.writestr(fname, cleaned.encode("utf-8"))
                        out_io.seek(0)

                        st.success(f"Updated {len(needs_update)} ParentModPortId attribute(s) to '{{ParentModulePort}}'. Download below.")
                        st.download_button(
                            label="Download Updated HSL Files (ZIP)",
                            data=out_io,
                            file_name="updated_ParentModPortId_HSL_files.zip",
                            mime="application/zip",
                            key="download_zip_pmpid",
                        )
                else:
                    st.success("All ParentModPortId attributes are already set to '{ParentModulePort}'. No changes needed.")
            else:
                st.info("No ParentModPortId attributes found in the uploaded files.")
        else:
            st.info("Upload Module-type HSL files to scan and update ParentModPortId attributes.")


if __name__ == "__main__":
    main()