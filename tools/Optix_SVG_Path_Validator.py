import streamlit as st
import yaml
import os
from pathlib import Path

def extract_svg_paths(obj):
    """Recursively extract all SVG file paths from a YAML object."""
    paths = []
    
    def traverse(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    traverse(value)
                elif isinstance(value, str) and value.endswith('.svg'):
                    paths.append(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)
    
    traverse(obj)
    return paths

def check_path_format(paths, correct_format):
    """Check if paths match the correct format."""
    good_paths = []
    bad_paths = []
    
    for path in paths:
        if path.startswith(correct_format):
            good_paths.append(path)
        else:
            bad_paths.append(path)
    
    return good_paths, bad_paths

def process_yaml_file(file_content, file_name):
    """Process a single YAML file and extract SVG paths."""
    try:
        yaml_data = yaml.safe_load(file_content)
        svg_paths = extract_svg_paths(yaml_data)
        return svg_paths, None
    except Exception as e:
        return [], str(e)

def main():
    st.markdown(
        """
        <h2 style="color: #2c3e50; font-family: Arial, sans-serif;">
            SVG File Path Extractor From YAML
        </h2>
        <hr style="border: 1px solid #f0f2f6;">
        """,
        unsafe_allow_html=True
    )
    
    # Path format configuration
    st.markdown("### Path Format Configuration")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        correct_format = st.text_input(
            "Enter correct path format:",
            value="%PROJECTDIR%/res/",
            help="Specify the expected prefix for SVG file paths"
        )
    
    # Initialize session state for results
    if 'svg_results' not in st.session_state:
        st.session_state.svg_results = []
    if 'show_format_check' not in st.session_state:
        st.session_state.show_format_check = False
    if 'processing_mode' not in st.session_state:
        st.session_state.processing_mode = None
    
    # Upload mode selection
    st.markdown("---")
    st.markdown("### Select Upload Mode")
    
    upload_mode = st.radio(
        "Choose how to upload files:",
        ["📄 Individual YAML Files", "📁 Multiple Files (Folder Upload)"],
        horizontal=True,
        help="Select individual files or upload all files from a folder at once"
    )
    
    # File upload section based on mode
    st.markdown("---")
    
    if upload_mode == "📄 Individual YAML Files":
        st.markdown("### Upload YAML Files")
        
        uploaded_files = st.file_uploader(
            "Select YAML files to process",
            type=['yml', 'yaml'],
            accept_multiple_files=True,
            help="Upload one or more YAML files to extract SVG paths"
        )
        
        if uploaded_files:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("🔍 Process Files", type="primary", use_container_width=True):
                    st.session_state.svg_results = []
                    st.session_state.show_format_check = False
                    st.session_state.processing_mode = 'files'
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_files = len(uploaded_files)
                    
                    for idx, uploaded_file in enumerate(uploaded_files):
                        status_text.text(f"Processing: {uploaded_file.name}")
                        
                        file_content = uploaded_file.read()
                        try:
                            yaml_data = yaml.safe_load(file_content)
                            svg_paths = extract_svg_paths(yaml_data)
                            error = None
                        except Exception as e:
                            svg_paths = []
                            error = str(e)
                        
                        st.session_state.svg_results.append({
                            'filename': uploaded_file.name,
                            'folder': None,
                            'paths': svg_paths,
                            'error': error
                        })
                        
                        progress_bar.progress((idx + 1) / total_files)
                    
                    status_text.text(f"✅ Processed {total_files} file(s)")
                    st.session_state.show_format_check = True
            
            with col2:
                if st.session_state.svg_results and st.button("✓ Check Format", type="secondary", use_container_width=True):
                    st.session_state.show_format_check = True
    
    else:  # Folder mode
        st.markdown("### Upload Multiple YAML Files from Folder")
        st.info("💡 **Tip:** You can select multiple files at once. Hold Ctrl (Windows/Linux) or Cmd (Mac) to select multiple files, or select all files in a folder.")
        
        uploaded_files = st.file_uploader(
            "Select all YAML files from your folder",
            type=['yml', 'yaml'],
            accept_multiple_files=True,
            help="Select all YAML files from your folder - you can select multiple files at once",
            key="folder_upload"
        )
        
        if uploaded_files:
            # Try to detect folder structure from file names
            st.success(f"📁 Selected {len(uploaded_files)} file(s)")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("🔍 Process Files", type="primary", use_container_width=True, key="process_folder_btn"):
                    st.session_state.svg_results = []
                    st.session_state.show_format_check = False
                    st.session_state.processing_mode = 'folder'
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total_files = len(uploaded_files)
                    
                    for idx, uploaded_file in enumerate(uploaded_files):
                        status_text.text(f"Processing: {uploaded_file.name}")
                        
                        file_content = uploaded_file.read()
                        svg_paths, error = process_yaml_file(file_content, uploaded_file.name)
                        
                        # Try to extract folder info from filename if available
                        # (some browsers preserve path info)
                        folder = "Root"
                        
                        st.session_state.svg_results.append({
                            'filename': uploaded_file.name,
                            'folder': folder,
                            'paths': svg_paths,
                            'error': error
                        })
                        
                        progress_bar.progress((idx + 1) / total_files)
                    
                    status_text.text(f"✅ Processed {total_files} file(s)")
                    st.session_state.show_format_check = True
            
            with col2:
                if st.session_state.svg_results and st.button("✓ Check Format", type="secondary", use_container_width=True, key="check_folder_format"):
                    st.session_state.show_format_check = True
    
    # Display results
    if st.session_state.svg_results:
        st.markdown("---")
        st.markdown("### Results")
        
        # Calculate total statistics
        all_paths = []
        all_results_with_format = []
        
        for result in st.session_state.svg_results:
            all_paths.extend(result['paths'])
            if result['paths']:
                good_paths, bad_paths = check_path_format(result['paths'], correct_format)
                all_results_with_format.append({
                    **result,
                    'good_paths': good_paths,
                    'bad_paths': bad_paths
                })
        
        if st.session_state.show_format_check and all_paths:
            good_paths_total, bad_paths_total = check_path_format(all_paths, correct_format)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Paths", len(all_paths))
            with col2:
                st.metric("✅ Good Format", len(good_paths_total))
            with col3:
                st.metric("❌ Bad Format", len(bad_paths_total))
        
        # Display format check view with two columns
        if st.session_state.show_format_check and all_paths:
            st.markdown("---")
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["📋 Summary View", "📂 Detailed View"])
            
            with tab1:
                # Two column view: Good vs Bad
                col_good, col_bad = st.columns(2)
                
                with col_good:
                    st.markdown("### ✅ Correct Format")
                    st.markdown(f"**{len(good_paths_total)} paths with correct format**")
                    
                    if good_paths_total:
                        # Group good paths by file
                        good_by_file = {}
                        for result in all_results_with_format:
                            if result.get('good_paths'):
                                file_label = result['filename']
                                if st.session_state.processing_mode == 'folder' and result.get('folder'):
                                    file_label = f"{result['folder']}/{result['filename']}"
                                good_by_file[file_label] = result['good_paths']
                        
                        for file_label, paths in good_by_file.items():
                            with st.expander(f"✅ {file_label} ({len(paths)} paths)", expanded=False):
                                for path in paths:
                                    st.markdown(f"- `{path}`")
                    else:
                        st.success("🎉 No issues found!")
                
                with col_bad:
                    st.markdown("### ❌ Incorrect Format")
                    st.markdown(f"**{len(bad_paths_total)} paths with incorrect format**")
                    
                    if bad_paths_total:
                        # Group bad paths by file
                        bad_by_file = {}
                        for result in all_results_with_format:
                            if result.get('bad_paths'):
                                file_label = result['filename']
                                if st.session_state.processing_mode == 'folder' and result.get('folder'):
                                    file_label = f"{result['folder']}/{result['filename']}"
                                bad_by_file[file_label] = result['bad_paths']
                        
                        for file_label, paths in bad_by_file.items():
                            with st.expander(f"❌ {file_label} ({len(paths)} paths)", expanded=True):
                                for path in paths:
                                    st.markdown(f"- <span style='color: #e74c3c; font-weight: bold;'>`{path}`</span>", unsafe_allow_html=True)
                    else:
                        st.success("🎉 All paths are correct!")
            
            with tab2:
                # Original detailed view
                # Group by folder if in folder mode
                if st.session_state.processing_mode == 'folder':
                    folders = {}
                    for result in st.session_state.svg_results:
                        folder = result.get('folder', 'Root')
                        if folder not in folders:
                            folders[folder] = []
                        folders[folder].append(result)
                    
                    # Display by folder
                    for folder, files in sorted(folders.items()):
                        st.markdown(f"#### 📁 {folder}")
                        
                        for result in files:
                            # Get good/bad counts for this file
                            good_count = len([r for r in all_results_with_format if r['filename'] == result['filename'] and r.get('good_paths')])
                            bad_count = len([r for r in all_results_with_format if r['filename'] == result['filename'] and r.get('bad_paths')])
                            
                            if result['error']:
                                with st.expander(f"📄 {result['filename']} ⚠️ Error", expanded=False):
                                    st.error(f"Error processing file: {result['error']}")
                            elif not result['paths']:
                                with st.expander(f"📄 {result['filename']} (No SVG paths)", expanded=False):
                                    st.info("No SVG paths found in this file.")
                            else:
                                good_paths, bad_paths = check_path_format(result['paths'], correct_format)
                                status_emoji = "❌" if bad_paths else "✅"
                                with st.expander(f"📄 {result['filename']} {status_emoji} ({len(good_paths)} good, {len(bad_paths)} bad)", expanded=bool(bad_paths)):
                                    if good_paths:
                                        st.markdown("**✅ Correct Format:**")
                                        for path in good_paths:
                                            st.markdown(f"- `{path}`")
                                    
                                    if bad_paths:
                                        st.markdown("**❌ Incorrect Format:**")
                                        for path in bad_paths:
                                            st.markdown(f"- <span style='color: #e74c3c; font-weight: bold;'>`{path}`</span>", unsafe_allow_html=True)
                else:
                    # Display individual file results
                    for result in st.session_state.svg_results:
                        if result['error']:
                            with st.expander(f"📄 {result['filename']} ⚠️ Error", expanded=False):
                                st.error(f"Error processing file: {result['error']}")
                        elif not result['paths']:
                            with st.expander(f"📄 {result['filename']} (No SVG paths)", expanded=False):
                                st.info("No SVG paths found in this file.")
                        else:
                            good_paths, bad_paths = check_path_format(result['paths'], correct_format)
                            status_emoji = "❌" if bad_paths else "✅"
                            with st.expander(f"📄 {result['filename']} {status_emoji} ({len(good_paths)} good, {len(bad_paths)} bad)", expanded=bool(bad_paths)):
                                if good_paths:
                                    st.markdown("**✅ Correct Format:**")
                                    for path in good_paths:
                                        st.markdown(f"- `{path}`")
                                
                                if bad_paths:
                                    st.markdown("**❌ Incorrect Format:**")
                                    for path in bad_paths:
                                        st.markdown(f"- <span style='color: #e74c3c; font-weight: bold;'>`{path}`</span>", unsafe_allow_html=True)
        
        # Show all paths if format check hasn't been run yet
        elif st.session_state.svg_results and not st.session_state.show_format_check:
            st.info("👆 Click 'Check Format' button to validate paths")
            # Group by folder if in folder mode
            if st.session_state.processing_mode == 'folder':
                folders = {}
                for result in st.session_state.svg_results:
                    folder = result.get('folder', 'Root')
                    if folder not in folders:
                        folders[folder] = []
                    folders[folder].append(result)
                
                # Display by folder
                for folder, files in sorted(folders.items()):
                    st.markdown(f"#### 📁 {folder}")
                    
                    for result in files:
                        with st.expander(f"📄 {result['filename']}", expanded=False):
                            if result['error']:
                                st.error(f"Error processing file: {result['error']}")
                            elif not result['paths']:
                                st.info("No SVG paths found in this file.")
                            else:
                                st.write(f"**Found {len(result['paths'])} SVG path(s):**")
                                for path in result['paths']:
                                    st.markdown(f"- `{path}`")
            else:
                # Display individual file results
                for result in st.session_state.svg_results:
                    with st.expander(f"📄 {result['filename']}", expanded=True):
                        if result['error']:
                            st.error(f"Error processing file: {result['error']}")
                        elif not result['paths']:
                            st.info("No SVG paths found in this file.")
                        else:
                            st.write(f"**Found {len(result['paths'])} SVG path(s):**")
                            for path in result['paths']:
                                st.markdown(f"- `{path}`")
    
    # Information section
    st.markdown("---")
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        **Steps to validate SVG paths:**
        
        1. **Enter the correct path format** (e.g., `%PROJECTDIR%/res/`)
        2. **Choose upload mode:**
           - **Individual Files**: Upload one or more YAML files
           - **Multiple Files**: Select all YAML files from your folder at once
        3. **Process files** by clicking the appropriate button
        4. **Click "Check Format"** to validate paths against the correct format
        
        **Features:**
        - ✅ Process multiple YAML files at once
        - ✅ Upload all files from a folder (select multiple files)
        - ✅ Validates paths against a specified format
        - ✅ Color-coded results (green for correct, red for incorrect format)
        - ✅ Two-column view to quickly identify bad paths
        - ✅ Summary and detailed views available
        
        **How to upload multiple files:**
        1. Choose "Multiple Files (Folder Upload)" mode
        2. Click "Browse files" or drag & drop
        3. Hold **Ctrl** (Windows/Linux) or **Cmd** (Mac) to select multiple files
        4. Or press **Ctrl+A** / **Cmd+A** to select all files in a folder
        5. Click "Open" to upload all selected files
        
        **Note:** SVG paths are identified by checking for strings ending with `.svg`
        """)
    
    # Footer contact info
    st.markdown("---")
    st.markdown(
        """
        <p style="text-align: center; color: #7f8c8d; font-size: 12px; opacity: 0.7;">
            For any issues, contact: @VRL
        </p>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()