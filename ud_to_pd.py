"""
UD-to-PD Converter for RA Library HSL4 files.
==============================================
Takes a UserDefined AOI AddOnInstructionDefinitions block from an HSL4 file
and generates the PredefinedDatatype equivalent.

Transformations:
  1. ICond: 'UserDefinedDatatype' -> 'PredefinedDatatype'
  2. Revision in EncodedData: major+7 (e.g. 4.0 -> 11.0)
  3. RevisionNote: append '.' if missing
  4. Parameter DataType swaps (if present):
       Ref_Ctrl_Sts  : raC_UDT_ItfAD_PwrVelocity_Sts      -> RAC_ITF_DVC_PWRVELOCITY_STS
       Ref_Ctrl_Set  : raC_UDT_ItfAD_PwrVelocity_Set      -> RAC_ITF_DVC_PWRVELOCITY_SET
       Ref_Ctrl_Cmd  : raC_UDT_ItfAD_PwrVelocity_Cmd      -> RAC_ITF_DVC_PWRVELOCITY_CMD
       Inf_Lookup    : <any UDT> Dimensions="<N>"          -> RAC_CODE_DESCRIPTION Dimensions="2"
  5. Dependencies: remove swapped UDT names from <Dependency> list
  6. Revision history in AdditionalHelpText: major+7, minor+1 for sub-versions;
     remove "Released" entry; fix leading dash on first rev note

Usage:
  python ud_to_pd.py <HSL4_file> [block_number]

  - Without block_number: lists all blocks, converts all UserDefined ones
  - With block_number: converts only that specific block
"""

import re
import sys
import os

# ============================================================
# DataType mapping table: Parameter Name -> (UDT name, PD name)
# If the Parameter is found with the UDT DataType, swap to PD.
# ============================================================
PARAM_DT_MAP = {
    "Ref_Ctrl_Sts": ("raC_UDT_ItfAD_PwrVelocity_Sts", "RAC_ITF_DVC_PWRVELOCITY_STS"),
    "Ref_Ctrl_Set": ("raC_UDT_ItfAD_PwrVelocity_Set", "RAC_ITF_DVC_PWRVELOCITY_SET"),
    "Ref_Ctrl_Cmd": ("raC_UDT_ItfAD_PwrVelocity_Cmd", "RAC_ITF_DVC_PWRVELOCITY_CMD"),
}

# Inf_Lookup is special: any UDT with any Dimensions -> RAC_CODE_DESCRIPTION Dimensions="2"
INF_LOOKUP_PD_DT = "RAC_CODE_DESCRIPTION"
INF_LOOKUP_PD_DIM = "2"

# Collect all UDT names that get removed from Dependencies
UDT_NAMES_TO_REMOVE = {v[0] for v in PARAM_DT_MAP.values()}

REV_MAJOR_OFFSET = 7   # 4 -> 11
REV_MINOR_OFFSET = 1   # 3.x -> 10.(x+1)


def convert_udt_to_predefined(udt_block: str) -> str:
    result = udt_block

    # 1. ICond: UserDefinedDatatype -> PredefinedDatatype
    result = result.replace("'UserDefinedDatatype'", "'PredefinedDatatype'")

    # 2. Revision in EncodedData: major+7
    def bump_revision(m):
        prefix = m.group(1)
        major = int(m.group(2))
        minor = m.group(3)
        return f'{prefix}Revision="{major + REV_MAJOR_OFFSET}.{minor}"'
    result = re.sub(
        r'(<EncodedData\s[^>]*?)Revision="(\d+)\.(\d+)"',
        bump_revision, result
    )

    # 3. RevisionNote: append '.' if not ending with one
    result = re.sub(
        r'(<RevisionNote><!\[CDATA\[)(.*?)(\]\]></RevisionNote>)',
        lambda m: m.group(1) + (m.group(2) if m.group(2).rstrip().endswith('.') else m.group(2) + '.') + m.group(3),
        result
    )

    # 4a. Swap parameter DataTypes for known params
    swapped_udts = set()
    for param_name, (udt_name, pd_name) in PARAM_DT_MAP.items():
        pattern = rf'(Name="{param_name}"[^>]*DataType="){udt_name}(")'
        if re.search(pattern, result):
            result = re.sub(pattern, rf'\g<1>{pd_name}\2', result)
            swapped_udts.add(udt_name)
            print(f"    Swapped {param_name}: {udt_name} -> {pd_name}")

    # 4b. Inf_Lookup: swap DataType and Dimensions
    inf_pattern = r'(Name="Inf_Lookup"[^>]*DataType=")([^"]+)("[^>]*Dimensions=")(\d+)(")'
    inf_match = re.search(inf_pattern, result)
    if inf_match:
        old_dt = inf_match.group(2)
        old_dim = inf_match.group(4)
        result = re.sub(
            inf_pattern,
            rf'\g<1>{INF_LOOKUP_PD_DT}\g<3>{INF_LOOKUP_PD_DIM}\5',
            result
        )
        swapped_udts.add(old_dt)
        print(f"    Swapped Inf_Lookup: {old_dt}[{old_dim}] -> {INF_LOOKUP_PD_DT}[{INF_LOOKUP_PD_DIM}]")

    # 5. Dependencies: remove swapped UDT names
    for udt_name in swapped_udts:
        dep_pattern = rf'\s*<Dependency Type="DataType" Name="{re.escape(udt_name)}"\s*/>\s*\n?'
        if re.search(dep_pattern, result):
            result = re.sub(dep_pattern, '\n', result)
            print(f"    Removed dependency: {udt_name}")

    # 6. Revision history in AdditionalHelpText
    def convert_helptext(match):
        helptext = match.group(2)

        # Convert version lines: X.Y.ZZ
        def version_replace(vm):
            full = vm.group(0)
            major = int(vm.group(1))
            minor = int(vm.group(2))
            patch = vm.group(3)

            # Find the main AOI revision from EncodedData
            # Sub-versions (major < main_major) get minor+1
            new_major = major + REV_MAJOR_OFFSET
            # Determine if this is a sub-version by checking if it's below the newest
            # We check all versions: the highest major is the main one
            # For sub-versions, bump the minor too
            return f"{new_major}.{minor + REV_MINOR_OFFSET}.{patch}"

        # Only convert version lines that appear after "Revision Notes:" section
        rev_notes_split = helptext.split('Revision Notes:')
        if len(rev_notes_split) > 1:
            before_notes = rev_notes_split[0]
            after_notes = rev_notes_split[1]

            # Find the main revision first (the one listed first after -----)
            first_ver = re.search(r'-----\s*\n(\d+)\.(\d+)\.(\d+)', after_notes)
            main_major = int(first_ver.group(1)) if first_ver else 4

            def version_replace_smart(vm):
                major = int(vm.group(1))
                minor = int(vm.group(2))
                patch = vm.group(3)
                new_major = major + REV_MAJOR_OFFSET
                if major < main_major:
                    new_minor = minor + REV_MINOR_OFFSET
                else:
                    new_minor = minor
                return f"{new_major}.{new_minor}.{patch}"

            after_notes = re.sub(r'\b(\d+)\.(\d+)\.(0{2})\b', version_replace_smart, after_notes)

            # Remove "Released" entry
            after_notes = re.sub(
                r'\n\d+\.\d+\.\d+\s*\n-\s*Released\s*\n*(?=\n=)',
                '', after_notes
            )

            # Fix first note: remove leading "- " or "-  " from first entry after main version
            after_notes = re.sub(
                r'(-----\s*\n\d+\.\d+\.\d+\s*\n)-\s+',
                r'\1',
                after_notes
            )

            helptext = before_notes + 'Revision Notes:' + after_notes

        return match.group(1) + helptext + match.group(3)

    result = re.sub(
        r'(<AdditionalHelpText><!\[CDATA\[)(.*?)(\]\]></AdditionalHelpText>)',
        convert_helptext, result, flags=re.DOTALL
    )

    return result


def process_hsl_file(input_file: str, block_num: int = None):
    """
    Read file, find AOI blocks, convert UserDefined to Predefined.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(<AddOnInstructionDefinitions>.*?</AddOnInstructionDefinitions>)'
    blocks = list(re.finditer(pattern, content, re.DOTALL))

    print(f"\nFound {len(blocks)} AddOnInstructionDefinitions block(s):\n")

    udt_blocks = []
    for i, bm in enumerate(blocks):
        text = bm.group(1)
        name = (re.search(r'Name="([^"]+)"', text) or type('', (), {'group': lambda s, n: '?'})()).group(1)
        rev  = (re.search(r'Revision="([^"]+)"', text) or type('', (), {'group': lambda s, n: '?'})()).group(1)
        revext = (re.search(r'RevisionExtension="([^"]+)"', text) or type('', (), {'group': lambda s, n: ''})()).group(1)
        icond_m = re.search(r'<ICond>(.*?)</ICond>', text)
        icond = icond_m.group(1) if icond_m else '(no ICond)'
        is_udt = 'UserDefinedDatatype' in icond

        tag = " ** UserDefined **" if is_udt else ""
        print(f"  Block {i+1}: {name}  Rev={rev}{revext}  |  {icond}{tag}")

        if is_udt:
            udt_blocks.append((i, bm, name, rev, revext))

    if not udt_blocks:
        print("\n  No UserDefinedDatatype blocks found. Nothing to convert.")
        return

    # Filter to specific block if requested
    if block_num is not None:
        udt_blocks = [(i, m, n, r, re_) for (i, m, n, r, re_) in udt_blocks if i == block_num - 1]
        if not udt_blocks:
            print(f"\n  Block {block_num} is not a UserDefined block.")
            return

    print(f"\n{'='*70}")
    print(f"Converting {len(udt_blocks)} block(s) to PredefinedDatatype...\n")

    for idx, (block_idx, block_match, aoi_name, rev, revext) in enumerate(udt_blocks):
        print(f"--- Block {block_idx+1}: {aoi_name} Rev={rev}{revext} ---")
        block_text = block_match.group(1)
        converted = convert_udt_to_predefined(block_text)

        out_name = f"{aoi_name}_PD_Rev{int(rev.split('.')[0]) + REV_MAJOR_OFFSET}.{rev.split('.')[1]}{revext}.xml"
        out_path = os.path.join(os.path.dirname(input_file) or '.', out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(converted)

        print(f"    Output: {out_name}")
        print()

    print("="*70)
    print("Done! Review the generated file(s).")
    print("Paste the content as a new <AddOnInstructionDefinitions> block")
    print("after the existing UserDefined block in your HSL4 file.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ud_to_pd.py <HSL4_file> [block_number]")
        print()
        print("  Reads an HSL4 file, finds AddOnInstructionDefinitions blocks")
        print("  with UserDefinedDatatype, and generates PredefinedDatatype versions.")
        print()
        print("  block_number: optional, convert only that specific block (1-based)")
        print()
        print("  DataType mappings applied (if parameter exists in AOI):")
        print("    Ref_Ctrl_Sts  -> RAC_ITF_DVC_PWRVELOCITY_STS")
        print("    Ref_Ctrl_Set  -> RAC_ITF_DVC_PWRVELOCITY_SET")
        print("    Ref_Ctrl_Cmd  -> RAC_ITF_DVC_PWRVELOCITY_CMD")
        print("    Inf_Lookup    -> RAC_CODE_DESCRIPTION[2]")
        sys.exit(1)

    input_file = sys.argv[1]
    blk = int(sys.argv[2]) if len(sys.argv) > 2 else None
    process_hsl_file(input_file, blk)
