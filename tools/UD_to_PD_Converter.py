import streamlit as st
import re
import io

# ============================================================
# DataType mapping table: Parameter Name -> (UDT name, PD name)
# ============================================================
DEFAULT_PARAM_DT_MAP = {
    "Ref_Ctrl_Sts": ("raC_UDT_ItfAD_PwrVelocity_Sts", "RAC_ITF_DVC_PWRVELOCITY_STS"),
    "Ref_Ctrl_Set": ("raC_UDT_ItfAD_PwrVelocity_Set", "RAC_ITF_DVC_PWRVELOCITY_SET"),
    "Ref_Ctrl_Cmd": ("raC_UDT_ItfAD_PwrVelocity_Cmd", "RAC_ITF_DVC_PWRVELOCITY_CMD"),
}

INF_LOOKUP_PD_DT = "RAC_CODE_DESCRIPTION"
INF_LOOKUP_PD_DIM = "2"

DEFAULT_REV_MAJOR_OFFSET = 7
DEFAULT_REV_MINOR_OFFSET = 1


def parse_blocks(content: str):
    """Find all AddOnInstructionDefinitions blocks and extract metadata."""
    pattern = r'(<AddOnInstructionDefinitions>.*?</AddOnInstructionDefinitions>)'
    blocks = list(re.finditer(pattern, content, re.DOTALL))

    block_info = []
    for i, bm in enumerate(blocks):
        text = bm.group(1)
        name_m = re.search(r'Name="([^"]+)"', text)
        rev_m = re.search(r'Revision="([^"]+)"', text)
        revext_m = re.search(r'RevisionExtension="([^"]+)"', text)
        icond_m = re.search(r'<ICond>(.*?)</ICond>', text)

        name = name_m.group(1) if name_m else "?"
        rev = rev_m.group(1) if rev_m else "?"
        revext = revext_m.group(1) if revext_m else ""
        icond = icond_m.group(1) if icond_m else "(no ICond)"
        is_udt = "UserDefinedDatatype" in icond

        block_info.append({
            "index": i,
            "match": bm,
            "name": name,
            "revision": rev,
            "revision_ext": revext,
            "icond": icond,
            "is_udt": is_udt,
            "text": text,
        })
    return block_info


def extract_revision_note(block_text: str) -> str:
    """Extract the RevisionNote CDATA content from a block."""
    m = re.search(r'<RevisionNote><!\[CDATA\[(.*?)\]\]></RevisionNote>', block_text)
    return m.group(1) if m else ""


def extract_helptext_revisions(block_text: str) -> str:
    """Extract the revision notes section from AdditionalHelpText CDATA."""
    m = re.search(r'<AdditionalHelpText><!\[CDATA\[(.*?)\]\]></AdditionalHelpText>', block_text, re.DOTALL)
    if not m:
        return ""
    helptext = m.group(1)
    parts = helptext.split('Revision Notes:')
    if len(parts) > 1:
        return parts[1]
    return ""


def convert_udt_to_predefined(udt_block: str, param_dt_map: dict,
                                rev_major_offset: int, rev_minor_offset: int,
                                inf_lookup_pd_dt: str = INF_LOOKUP_PD_DT,
                                inf_lookup_pd_dim: str = INF_LOOKUP_PD_DIM,
                                user_revision_note: str | None = None,
                                user_helptext_revisions: str | None = None) -> tuple:
    """
    Convert a UserDefined AOI block to PredefinedDatatype.
    Returns (converted_text, list_of_log_messages).
    """
    result = udt_block
    log = []

    # 1. ICond: UserDefinedDatatype -> PredefinedDatatype
    result = result.replace("'UserDefinedDatatype'", "'PredefinedDatatype'")
    log.append("ICond: `UserDefinedDatatype` → `PredefinedDatatype`")

    # 2. Revision in EncodedData: major + offset
    rev_bumped = False
    def bump_revision(m):
        nonlocal rev_bumped
        prefix = m.group(1)
        major = int(m.group(2))
        minor = m.group(3)
        rev_bumped = True
        return f'{prefix}Revision="{major + rev_major_offset}.{minor}"'

    result = re.sub(
        r'(<EncodedData\s[^>]*?)Revision="(\d+)\.(\d+)"',
        bump_revision, result
    )
    if rev_bumped:
        log.append(f"Revision bumped: major **+{rev_major_offset}**")

    # 3. RevisionNote: replace with user-supplied text if provided
    if user_revision_note is not None:
        result = re.sub(
            r'(<RevisionNote><!\[CDATA\[)(.*?)(\]\]></RevisionNote>)',
            lambda m: m.group(1) + user_revision_note + m.group(3),
            result
        )
        log.append("RevisionNote: replaced with user-edited text")

    # 4a. Swap parameter DataTypes for known params
    swapped_udts = set()
    for param_name, (udt_name, pd_name) in param_dt_map.items():
        pattern = rf'(Name="{param_name}"[^>]*DataType="){re.escape(udt_name)}(")'
        if re.search(pattern, result):
            result = re.sub(pattern, rf'\g<1>{pd_name}\2', result)
            swapped_udts.add(udt_name)
            log.append(f"Param swap: **{param_name}** → `{pd_name}`")

    # 4b. Inf_Lookup: swap DataType and Dimensions
    inf_pattern = r'(Name="Inf_Lookup"[^>]*DataType=")([^"]+)("[^>]*Dimensions=")(\d+)(")'
    inf_match = re.search(inf_pattern, result)
    if inf_match:
        old_dt = inf_match.group(2)
        old_dim = inf_match.group(4)
        result = re.sub(
            inf_pattern,
            rf'\g<1>{inf_lookup_pd_dt}\g<3>{inf_lookup_pd_dim}\5',
            result
        )
        swapped_udts.add(old_dt)
        log.append(f"Inf_Lookup: `{old_dt}[{old_dim}]` → `{inf_lookup_pd_dt}[{inf_lookup_pd_dim}]`")

    # 5. Dependencies: remove swapped UDT names
    for udt_name in swapped_udts:
        dep_pattern = rf'\s*<Dependency Type="DataType" Name="{re.escape(udt_name)}"\s*/>\s*\n?'
        if re.search(dep_pattern, result):
            result = re.sub(dep_pattern, '\n', result)
            log.append(f"Removed dependency: `{udt_name}`")

    # 6. Revision history in AdditionalHelpText: replace with user-supplied text if provided
    if user_helptext_revisions is not None:
        def replace_helptext(match):
            helptext = match.group(2)
            parts = helptext.split('Revision Notes:')
            if len(parts) > 1:
                helptext = parts[0] + 'Revision Notes:' + user_helptext_revisions
                log.append("Revision history replaced with user-edited text")
            return match.group(1) + helptext + match.group(3)

        result = re.sub(
            r'(<AdditionalHelpText><!\[CDATA\[)(.*?)(\]\]></AdditionalHelpText>)',
            replace_helptext, result, flags=re.DOTALL
        )

    return result, log


def main():
    st.title("NPDT AOI Def Generator")
    st.markdown(
        "Convert **UserDefined** AOI `AddOnInstructionDefinitions` blocks from HSL4 files "
        "to their **PredefinedDatatype** equivalents."
    )

    # ── Sidebar-style settings in an expander ──
    with st.expander("⚙️ Conversion Settings", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            rev_major_offset = st.number_input(
                "Revision Major Offset", min_value=1, max_value=20,
                value=DEFAULT_REV_MAJOR_OFFSET, help="Added to the major revision number (default: 7)"
            )
        with col_b:
            rev_minor_offset = st.number_input(
                "Revision Minor Offset (sub-versions)", min_value=0, max_value=10,
                value=DEFAULT_REV_MINOR_OFFSET, help="Added to minor version for sub-versions (default: 1)"
            )

        st.markdown("**Parameter DataType Mappings**")
        st.caption("Edit the UDT → PD mappings applied during conversion.")

        param_dt_map = {}
        for param_name, (udt_default, pd_default) in DEFAULT_PARAM_DT_MAP.items():
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1:
                st.text_input("Param", value=param_name, disabled=True, key=f"pn_{param_name}")
            with c2:
                udt_val = st.text_input("UDT DataType", value=udt_default, key=f"udt_{param_name}")
            with c3:
                pd_val = st.text_input("PD DataType", value=pd_default, key=f"pd_{param_name}")
            param_dt_map[param_name] = (udt_val, pd_val)

        st.markdown("**Inf_Lookup Mapping**")
        st.caption("Inf_Lookup: any UDT with any Dimensions → target PD DataType with fixed Dimensions.")
        cl1, cl2 = st.columns(2)
        with cl1:
            inf_lookup_pd_dt = st.text_input(
                "PD DataType", value=INF_LOOKUP_PD_DT, key="inf_lookup_pd_dt",
                help="Target PredefinedDatatype for Inf_Lookup parameter"
            )
        with cl2:
            inf_lookup_pd_dim = st.text_input(
                "PD Dimensions", value=INF_LOOKUP_PD_DIM, key="inf_lookup_pd_dim",
                help="Fixed Dimensions value for the PD Inf_Lookup parameter"
            )

    # ── File upload ──
    st.markdown("---")
    uploaded_file = st.file_uploader(
        "Upload HSL4 File", type=["HSL4", "xml", "L5X"],
        help="Select an HSL4 file containing AddOnInstructionDefinitions blocks."
    )

    if uploaded_file is None:
        st.info("Upload an HSL4 file to get started.")
        return

    content = uploaded_file.read().decode("utf-8")
    blocks = parse_blocks(content)

    if not blocks:
        st.error("No `<AddOnInstructionDefinitions>` blocks found in the file.")
        return

    # ── Block overview table ──
    st.markdown("### Detected AOI Blocks")
    udt_count = sum(1 for b in blocks if b["is_udt"])

    table_rows = []
    for b in blocks:
        table_rows.append({
            "#": b["index"] + 1,
            "Name": b["name"],
            "Revision": f'{b["revision"]}{b["revision_ext"]}',
            "ICond": b["icond"],
            "Type": "🔶 UserDefined" if b["is_udt"] else "✅ Predefined / Other",
        })

    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    udt_blocks = [b for b in blocks if b["is_udt"]]

    if not udt_blocks:
        st.success("No UserDefinedDatatype blocks to convert.")
        return

    st.markdown(f"**{udt_count}** UserDefined block(s) ready for conversion.")

    # ── Block selection ──
    block_options = {f"Block {b['index']+1}: {b['name']} (Rev {b['revision']}{b['revision_ext']})": b["index"]
                     for b in udt_blocks}

    selected_labels = st.multiselect(
        "Select blocks to convert",
        options=list(block_options.keys()),
        default=list(block_options.keys()),
        help="Choose which UserDefined blocks to convert."
    )

    if not selected_labels:
        st.warning("Select at least one block.")
        return

    # ── Editable Revision Notes per selected block ──
    selected_indices = {block_options[lbl] for lbl in selected_labels}
    selected_blocks = [b for b in udt_blocks if b["index"] in selected_indices]

    st.markdown("### ✏️ Edit Revision Notes")
    st.caption(
        "Below are the revision notes extracted from each selected block. "
        "Edit them as needed — the updated text will be used in the converted output."
    )

    user_rev_notes = {}   # block index -> edited RevisionNote string
    user_helptext = {}    # block index -> edited revision history string

    for b in selected_blocks:
        with st.expander(f"📝 {b['name']} (Rev {b['revision']}{b['revision_ext']})", expanded=True):
            orig_revnote = extract_revision_note(b["text"])
            orig_helptext_revs = extract_helptext_revisions(b["text"])

            user_rev_notes[b["index"]] = st.text_input(
                "RevisionNote",
                value=orig_revnote,
                key=f"revnote_{b['index']}",
                help="Single-line revision note (appears in RevisionNote CDATA)."
            )

            user_helptext[b["index"]] = st.text_area(
                "Revision History (from AdditionalHelpText)",
                value=orig_helptext_revs,
                height=250,
                key=f"helptext_{b['index']}",
                help="Full revision history section. Update version numbers and notes as needed."
            )

    # ── Convert button ──
    if st.button("🔄 Convert to PredefinedDatatype", type="primary", use_container_width=True):
        results = []

        progress = st.progress(0, text="Converting...")
        total = len(selected_blocks)

        for step, b in enumerate(selected_blocks):
            converted, log_msgs = convert_udt_to_predefined(
                b["text"], param_dt_map, rev_major_offset, rev_minor_offset,
                inf_lookup_pd_dt, inf_lookup_pd_dim,
                user_revision_note=user_rev_notes.get(b["index"]),
                user_helptext_revisions=user_helptext.get(b["index"]),
            )

            new_rev_major = int(b["revision"].split(".")[0]) + rev_major_offset
            new_rev_minor = b["revision"].split(".")[1] if "." in b["revision"] else "0"
            out_name = f"{b['name']}_PD_Rev{new_rev_major}.{new_rev_minor}{b['revision_ext']}.xml"

            results.append({
                "block": b,
                "converted": converted,
                "log": log_msgs,
                "filename": out_name,
            })

            progress.progress((step + 1) / total, text=f"Converted {b['name']}")

        progress.empty()

        # ── Results ──
        st.markdown("---")
        st.markdown("### Conversion Results")

        for r in results:
            with st.expander(f"✅ {r['block']['name']} → {r['filename']}", expanded=True):
                # Transformation log
                st.markdown("**Transformations applied:**")
                for msg in r["log"]:
                    st.markdown(f"- {msg}")

                # Preview & Download side by side
                tab_preview, tab_diff = st.tabs(["📄 Preview", "🔍 Before / After"])

                with tab_preview:
                    st.code(r["converted"][:3000] + ("\n... (truncated)" if len(r["converted"]) > 3000 else ""),
                            language="xml")

                with tab_diff:
                    col_left, col_right = st.columns(2)
                    with col_left:
                        st.markdown("**Original (UserDefined)**")
                        st.code(r["block"]["text"][:2000] + ("\n..." if len(r["block"]["text"]) > 2000 else ""),
                                language="xml")
                    with col_right:
                        st.markdown("**Converted (PredefinedDatatype)**")
                        st.code(r["converted"][:2000] + ("\n..." if len(r["converted"]) > 2000 else ""),
                                language="xml")

                # Download button
                st.download_button(
                    label=f"⬇️ Download {r['filename']}",
                    data=r["converted"].encode("utf-8"),
                    file_name=r["filename"],
                    mime="application/xml",
                    key=f"dl_{r['block']['index']}",
                )

        # Combined download if multiple
        if len(results) > 1:
            st.markdown("---")
            combined = "\n\n".join(r["converted"] for r in results)
            combined_name = f"{uploaded_file.name.rsplit('.', 1)[0]}_PD_all.xml"
            st.download_button(
                label=f"⬇️ Download All ({len(results)} blocks combined)",
                data=combined.encode("utf-8"),
                file_name=combined_name,
                mime="application/xml",
                key="dl_combined",
                use_container_width=True,
            )

        st.success(f"Converted {len(results)} block(s) successfully.")
