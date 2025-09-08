import streamlit as st
import io
import lxml.etree as ET
import pandas as pd
import zipfile
import os

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

# # Mapping of Description to Extraction_Path
# DESCRIPTION_TO_EXTRACTION_PATH = {
#     'Toolbox SE': '{ProjectName}\\Visualization\\FTViewSE\\GlobalObjects', #'(raC-5-SE) Toolbox - IO Device.ggfx'
#     'Toolbox ME': '{ProjectName}\\Visualization\\FTViewME\\GlobalObjects', #'(raC-5-ME) Toolbox - IO Device.ggfx'
#     'Graphic Symbols ME': '{ProjectName}\\Visualization\\FTViewME\\GlobalObjects', #'(raC-5-ME) Graphic Symbols - IO Device.ggfx'
#     'Graphic Symbols SE': '{ProjectName}\\Visualization\\FTViewSE\\GlobalObjects', #'(raC-5-SE) Graphic Symbols - IO Device.ggfx'
#     'Faceplate ME': '{ProjectName}\\Visualization\\FTViewME\\Displays', #'(raC-4_00-ME) raC_Dvc_PF755-Faceplate.gfx'
#     'Faceplate SE': '{ProjectName}\\Visualization\\FTViewSE\\Displays', #'(raC-4_00-SE) raC_Dvc_PF755-Faceplate.gfx'
#     'View Designer': '{ProjectName}\\Visualization\\ViewDesigner', #'raC_Dvc_5034IO_wDesc.vpd'
#     'Reference Manual': '{ProjectName}\\Documentation', #'DEVICE-RM100F-EN-P.pdf'
#     'HMI Image Set': '{ProjectName}\\Visualization\\Images', #'HMI-FactoryTalk-View-Images.zip'
#     'HMI Tag': '{ProjectName}\\Visualization' #'FTViewStudio_IOLibrary_Tags_5_00.CSV'
# }



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
            # Read text file content
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
                
                # Extract required fields without derivation
                file_name_attr = attributes.get('File_Name', '')
                description = attributes.get('Description', '')
                extraction_path = attributes.get('Extraction_Path', '')
                # Handle typo in Revision_Description
                revision_description = attributes.get('Revison_Description', attributes.get('Revision_Description', ''))
                modified_date = attributes.get('Modified_Date', '')
                modified_by = attributes.get('Modified_By', '')

                attachment_attributes[file_name]["attributes"].append({
                    "File_Name": file_name_attr,
                    "Description": description,
                    "Extraction_Path": extraction_path,
                    "Revision_Description": revision_description,
                    "Modified_Date": modified_date,
                    "Modified_By": modified_by,
                    "original_line_index": i
                })
                attachment_attributes[file_name]["line_indices"].append(i)

        except Exception as e:
            st.error(f"Failed to process attachment {uploaded_file.name}: {e}")
    return attachment_attributes

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

    # File uploader shared across Attribute Editor and Extraction Path Validator
    uploaded_hsl_files = st.file_uploader(
        "Select one or more .HSL4 XML files",
        type=["HSL4", "xml"],
        accept_multiple_files=True,
        key="uploader_shared"
    )

    # File uploader for Attachments (text files or ZIP)
    uploaded_attachment_files = st.file_uploader(
        "Select one or more Attachment .txt files or a ZIP file",
        type=["txt", "zip"],
        accept_multiple_files=True,
        key="uploader_attachments"
    )

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Attribute Editor", "Extraction Path Validator", "Attachments Validator"])

    with tab1:
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
                        print("hsl---", attr["ModifiedBy"])
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
            st.info("Please upload .HSL4 files above to validate Extraction Paths.")

    with tab3:
        st.markdown("""
        ### Attachments Validator
        - Upload one or more `.txt` files from the Attachments folder or a ZIP containing them.
        - The table shows File_Name, Found Description, New Description, Found Extraction_Path, New Extraction_Path, Revision_Description, Modified_Date, and Modified_By.
        - Found values are the original values from the file, validated for correctness.
        - New values are automatically suggested when found values are invalid (based on file name); edit them if needed or leave blank to keep the found value.
        - Invalid fields are highlighted with ❌ in the Status Check column.
        - Apply changes to update the files and download as a ZIP archive.
        """)

        # Process uploaded attachment files
        attachment_files = []
        if uploaded_attachment_files:
            for uploaded_file in uploaded_attachment_files:
                if uploaded_file.name.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(uploaded_file, 'r') as zip_file:
                            for file_name in zip_file.namelist():
                                if file_name.endswith('.txt'):
                                    with zip_file.open(file_name) as txt_file:
                                        attachment_files.append(
                                            type('UploadedFile', (), {
                                                'name': file_name,
                                                'read': lambda: txt_file.read(),
                                                'seek': lambda x: None
                                            })()
                                        )
                    except zipfile.BadZipFile:
                        st.error(f"File '{uploaded_file.name}' is not a valid ZIP file.")
                elif uploaded_file.name.endswith('.txt'):
                    attachment_files.append(uploaded_file)

        if attachment_files:
            attachment_attributes = extract_attachment_attributes(attachment_files)
            if not attachment_attributes:
                st.warning("No valid .txt files were uploaded or parsed successfully.")
            else:
                # Initialize session state for attachments
                if "pending_attachment_changes" not in st.session_state:
                    st.session_state.pending_attachment_changes = []
                if "attachment_updates" not in st.session_state:
                    st.session_state.attachment_updates = {}
                if "attachment_updates_applied" not in st.session_state:
                    st.session_state.attachment_updates_applied = False

                attachment_data = []
                for file_name, attr_data in attachment_attributes.items():
                    for i, attr in enumerate(attr_data["attributes"]):
                        issues = []
                        # Store original (found) values for validation
                        found_description = attr["Description"]
                        found_extraction_path = attr["Extraction_Path"]

                        # Validate Description
                        valid_descriptions = [
                            'Toolbox SE', 'Toolbox ME', 'Graphic Symbols SE', 'Graphic Symbols ME',
                            'Faceplate SE', 'Faceplate ME', 'View Designer', 'Reference Manual',
                            'HMI Image Set', 'HMI Tag'
                        ]
                        if not found_description or found_description not in valid_descriptions:
                            issues.append(f"Invalid Description: {found_description if found_description else 'blank'}")

                        # Validate Extraction_Path
                        if not found_extraction_path or found_extraction_path not in COMPARISON_STRINGS:
                            issues.append(f"Invalid Extraction_Path: {found_extraction_path if found_extraction_path else 'blank'}")

                        # Derive new values if found values are invalid
                        derived_description, derived_extraction_path = derive_description_and_path(attr["File_Name"])
                        new_description = derived_description if (not found_description or found_description not in valid_descriptions) else found_description
                        new_extraction_path = derived_extraction_path if (not found_extraction_path or found_extraction_path not in COMPARISON_STRINGS) else found_extraction_path

                        status_check = "❌" if issues else "✅"
                        issue_details = "; ".join(issues) if issues else "All okay"

                        attachment_data.append({
                            "File Name": file_name,
                            "Index": f"Entry {i+1}",
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
                            for change in st.session_state.pending_attachment_changes:
                                file_name = change["_file_name"]
                                entry_index = change["_entry_index"]
                                attr_data = attachment_attributes[file_name]
                                original_lines = attr_data["original_content"]
                                updated_lines = original_lines.copy()

                                for c in change["Changes"]:
                                    field = c["Field"]
                                    new_value = c["New Value"]
                                    if field == "Description":
                                        attr_data["attributes"][entry_index]["Description"] = new_value
                                    elif field == "Extraction_Path":
                                        attr_data["attributes"][entry_index]["Extraction_Path"] = new_value
                                    else:
                                        attr_data["attributes"][entry_index][field] = new_value

                                # Reconstruct the text file content
                                updated_content = []
                                attr_index_map = {attr["original_line_index"]: i for i, attr in enumerate(attr_data["attributes"])}
                                for i, line in enumerate(original_lines):
                                    if i in attr_index_map:
                                        attr = attr_data["attributes"][attr_index_map[i]]
                                        updated_attrs = []
                                        for attr_pair in line.split(','):
                                            attr_name = attr_pair.split('=')[0].strip()
                                            # Map Revison_Description to Revision_Description in output
                                            if attr_name == 'Revison_Description':
                                                attr_name = 'Revision_Description'
                                            if attr_name in attr:
                                                updated_attrs.append(f"{attr_name}='{attr[attr_name]}'")
                                            else:
                                                updated_attrs.append(attr_pair.strip())
                                        updated_content.append(", ".join(updated_attrs))
                                    else:
                                        updated_content.append(line)

                                attachment_updates[file_name] = "\n".join(updated_content)

                            st.session_state.attachment_updates = attachment_updates
                            st.session_state.attachment_updates_applied = True
                            st.success("Attachment changes applied successfully!")

                    # Show download button for attachment updates
                    if st.session_state.attachment_updates_applied and st.session_state.attachment_updates:
                        st.markdown("### Download Updated Attachment Files")
                        out_io = io.BytesIO()
                        with zipfile.ZipFile(out_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
                            for file_name, content in st.session_state.attachment_updates.items():
                                zout.writestr(file_name, content.encode('utf-8'))
                        out_io.seek(0)

                        st.download_button(
                            label="Download Updated Attachment ZIP",
                            data=out_io,
                            file_name="updated_attachment_files.zip",
                            mime="application/zip",
                            key="download_zip_attachments"
                        )
                    elif not st.session_state.pending_attachment_changes:
                        st.info("No attachment changes detected to apply or download.")

                    # Reset updates_applied if table is edited again
                    if st.session_state.attachment_table.get("edited_rows"):
                        st.session_state.attachment_updates_applied = False
        else:
            st.info("Please upload .txt files or a ZIP containing .txt files to validate attachments.")

if __name__ == "__main__":
    main()