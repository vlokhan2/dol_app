import streamlit as st
import io
import lxml.etree as ET
import pandas as pd
import zipfile


def extract_attributes_from_files(uploaded_files):
    file_attributes = {}
    for uploaded_file in uploaded_files:
        try:
            parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
            tree = ET.parse(uploaded_file, parser=parser)
            root = tree.getroot()
            status = root.attrib.get("Status", "Pending")
            file_attributes[uploaded_file.name] = {"Status": status, "attributes": [], "tree": tree}

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
        except ET.XMLSyntaxError:
            st.warning(f"File '{uploaded_file.name}' is not valid XML and was skipped.")
        except Exception as e:
            st.error(f"Failed to process {uploaded_file.name}: {e}")
    return file_attributes


def main():
    st.title("ACM HSL4 Attribute Validator and Editor")
    st.set_page_config(layout="wide")

    st.markdown("""
    ### Instructions
    - Upload one or more `.HSL4` XML files (usually from `ApplicationCodeManagerLibraries`).
    - Review and edit the attributes in the table below.
    - The 'Status Check' column shows ❌ for rows with issues and ✅ for rows with no issues.
    - The 'Issue Details' column lists specific validation errors for each row.
    - After editing, review detected changes in a second table and click 'Apply Changes' to update the files.
    - Download the updated files as a ZIP archive.
    """)

    uploaded_files = st.file_uploader(
        "Select one or more .HSL4 XML files",
        type=["HSL4", "xml"],
        accept_multiple_files=True
    )

    if uploaded_files:
        file_attributes = extract_attributes_from_files(uploaded_files)
        if not file_attributes:
            st.warning("No valid .HSL4 XML files were uploaded or parsed.")
            return

        # Initialize session state
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

            if st.button("Apply Changes"):
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
            # Create ZIP file
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
                key="download_zip"
            )
        elif not st.session_state.pending_changes:
            st.info("No changes detected to apply or download.")

        # Reset updates_applied if table is edited again
        if st.session_state.attribute_table.get("edited_rows"):
            st.session_state.updates_applied = False


if __name__ == "__main__":
    main()