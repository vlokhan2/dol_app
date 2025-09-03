"""
Naming Conventions Tool with Full Excel Formula Support
Supports VLOOKUP, complex formulas, and exact Excel functionality
"""

import streamlit as st
import pandas as pd
import os
import tempfile
import shutil
from typing import Dict, List, Any
import subprocess
import sys

# Method 1: Using formulas package (Python Excel engine)
try:
    from formulas import XlsxFile, excel
    FORMULAS_AVAILABLE = True
except ImportError:
    FORMULAS_AVAILABLE = False

# Method 2: Using pycel (Excel in pure Python)  
try:
    from pycel import ExcelCompiler
    PYCEL_AVAILABLE = True
except ImportError:
    PYCEL_AVAILABLE = False

# Method 3: Using xlwings (requires Excel on server)
try:
    import xlwings as xw
    XLWINGS_AVAILABLE = True
except ImportError:
    XLWINGS_AVAILABLE = False

class ExcelFormulaEngine:
    """Full Excel formula execution engine for web deployment"""
    
    def __init__(self, excel_path: str = "data/naming_conventions.xlsx"):
        self.excel_path = os.path.abspath(excel_path)
        self.method = self.detect_best_method()
        self.engine = None
        self.initialize_engine()
    
    def detect_best_method(self):
        """Detect the best available method for Excel execution"""
        if FORMULAS_AVAILABLE:
            return "formulas"  # Best for web hosting
        elif PYCEL_AVAILABLE:
            return "pycel"     # Good alternative
        elif XLWINGS_AVAILABLE:
            return "xlwings"   # Requires Excel on server
        else:
            return "fallback"  # Basic pattern matching
    
    def initialize_engine(self):
        """Initialize the Excel execution engine"""
        try:
            if self.method == "formulas":
                # Use formulas package - pure Python Excel engine
                self.engine = XlsxFile(self.excel_path)
                
            elif self.method == "pycel":
                # Use pycel - compile Excel to Python
                self.engine = ExcelCompiler(filename=self.excel_path)
                
            elif self.method == "xlwings":
                # Use xlwings - requires Excel
                self.engine = "xlwings_placeholder"
                
        except Exception as e:
            st.warning(f"Could not initialize {self.method} engine: {e}")
            self.method = "fallback"
    
    def get_input_fields(self) -> Dict[str, Dict]:
        """Get input field definitions from Excel"""
        try:
            # Read Excel normally to get field definitions
            df = pd.read_excel(self.excel_path, sheet_name="Naming Tool", header=None)
            
            fields = {}
            for i in range(8):  # B2 to B9
                row_idx = i + 1  # Excel row 2-9 = pandas index 1-8
                if row_idx < len(df):
                    label = df.iloc[row_idx, 0]  # Column A
                    current_value = df.iloc[row_idx, 1]  # Column B
                    
                    fields[f"field_b{i+2}"] = {
                        'label': str(label) if pd.notna(label) else f"Field B{i+2}",
                        'current_value': str(current_value) if pd.notna(current_value) else "",
                        'cell': f"B{i+2}"
                    }
            
            return fields
            
        except Exception as e:
            st.error(f"Error reading Excel structure: {e}")
            return {}
    
    def execute_formulas(self, user_inputs: Dict[str, str]) -> List[Dict]:
        """Execute Excel formulas with user inputs"""
        
        if self.method == "formulas":
            return self._execute_with_formulas_package(user_inputs)
        elif self.method == "pycel":
            return self._execute_with_pycel(user_inputs)
        elif self.method == "xlwings":
            return self._execute_with_xlwings(user_inputs)
        else:
            return self._execute_fallback(user_inputs)
    
    def _execute_with_formulas_package(self, user_inputs: Dict[str, str]) -> List[Dict]:
        """Execute using formulas package - best for web hosting"""
        try:
            results = []
            
            # Create Excel model from file
            xl_file = XlsxFile(self.excel_path)
            xl_model = xl_file.xl_book
            
            # Update input cells
            for field_key, value in user_inputs.items():
                if field_key.startswith('field_b') and value.strip():
                    row_num = int(field_key.split('_b')[1])
                    cell_address = f"'Naming Tool'!B{row_num}"
                    xl_model.set_value(cell_address, value)
            
            # Get calculated results from output range (rows 12+)
            for row in range(12, 50):  # Check broader range
                try:
                    # Get values from different columns
                    label_addr = f"'Naming Tool'!A{row}"
                    app_addr = f"'Naming Tool'!B{row}"
                    filename_addr = f"'Naming Tool'!C{row}"
                    ext_addr = f"'Naming Tool'!D{row}"
                    
                    label = xl_model.get_value(label_addr)
                    app = xl_model.get_value(app_addr) 
                    filename = xl_model.get_value(filename_addr)
                    extension = xl_model.get_value(ext_addr)
                    
                    if label and str(label).strip():
                        results.append({
                            'file_type': str(label).strip(),
                            'application': str(app) if app else "",
                            'generated_name': str(filename) if filename else "",
                            'extension': str(extension) if extension else "",
                            'full_filename': f"{filename}.{extension}" if filename and extension else str(filename) if filename else ""
                        })
                        
                except Exception:
                    continue  # Skip problematic rows
            
            return results
            
        except Exception as e:
            st.error(f"Error with formulas package: {e}")
            return self._execute_fallback(user_inputs)
    
    def _execute_with_pycel(self, user_inputs: Dict[str, str]) -> List[Dict]:
        """Execute using pycel package"""
        try:
            results = []
            
            # Compile Excel file
            excel_compiler = ExcelCompiler(filename=self.excel_path)
            
            # Update input cells
            for field_key, value in user_inputs.items():
                if field_key.startswith('field_b') and value.strip():
                    row_num = int(field_key.split('_b')[1])
                    cell_address = f"'Naming Tool'!B{row_num}"
                    excel_compiler.set_value(cell_address, value)
            
            # Get results
            for row in range(12, 50):
                try:
                    label = excel_compiler.evaluate(f"'Naming Tool'!A{row}")
                    app = excel_compiler.evaluate(f"'Naming Tool'!B{row}")
                    filename = excel_compiler.evaluate(f"'Naming Tool'!C{row}")
                    extension = excel_compiler.evaluate(f"'Naming Tool'!D{row}")
                    
                    if label and str(label).strip():
                        results.append({
                            'file_type': str(label).strip(),
                            'application': str(app) if app else "",
                            'generated_name': str(filename) if filename else "",
                            'extension': str(extension) if extension else "",
                            'full_filename': f"{filename}.{extension}" if filename and extension else str(filename) if filename else ""
                        })
                except Exception:
                    continue
            
            return results
            
        except Exception as e:
            st.error(f"Error with pycel: {e}")
            return self._execute_fallback(user_inputs)
    
    def _execute_with_xlwings(self, user_inputs: Dict[str, str]) -> List[Dict]:
        """Execute using xlwings (requires Excel on server)"""
        try:
            results = []
            
            # This would only work if Excel is installed on server
            with xw.App(visible=False) as app:
                wb = app.books.open(self.excel_path)
                ws = wb.sheets["Naming Tool"]
                
                # Update inputs
                for field_key, value in user_inputs.items():
                    if field_key.startswith('field_b') and value.strip():
                        row_num = int(field_key.split('_b')[1])
                        ws[f"B{row_num}"].value = value
                
                # Get results
                for row in range(12, 50):
                    label = ws[f"A{row}"].value
                    app = ws[f"B{row}"].value
                    filename = ws[f"C{row}"].value
                    extension = ws[f"D{row}"].value
                    
                    if label and str(label).strip():
                        results.append({
                            'file_type': str(label).strip(),
                            'application': str(app) if app else "",
                            'generated_name': str(filename) if filename else "",
                            'extension': str(extension) if extension else "",
                            'full_filename': f"{filename}.{extension}" if filename and extension else str(filename) if filename else ""
                        })
                
                wb.close()
            
            return results
            
        except Exception as e:
            st.error(f"xlwings not available on server: {e}")
            return self._execute_fallback(user_inputs)
    
    def _execute_fallback(self, user_inputs: Dict[str, str]) -> List[Dict]:
        """Fallback method with basic pattern matching"""
        st.warning("⚠️ Using fallback method - complex formulas may not work correctly")
        
        try:
            # Read Excel data
            df = pd.read_excel(self.excel_path, sheet_name="Naming Tool", header=None)
            lookup_df = pd.read_excel(self.excel_path, sheet_name="Lookups")
            
            results = []
            
            # Process rows 12+ for file patterns
            for row in range(11, min(50, len(df))):  # Row 12+ in Excel = index 11+
                try:
                    label = df.iloc[row, 0]  # Column A
                    pattern = df.iloc[row, 2]  # Column C - filename pattern
                    extension = df.iloc[row, 3]  # Column D - extension
                    
                    if pd.notna(label) and pd.notna(pattern):
                        # Basic pattern replacement
                        generated_name = str(pattern)
                        
                        # Replace B2-B9 references with user inputs
                        for field_key, value in user_inputs.items():
                            if field_key.startswith('field_b') and value.strip():
                                row_num = int(field_key.split('_b')[1])
                                generated_name = generated_name.replace(f"B{row_num}", value)
                        
                        # Simple VLOOKUP simulation (very basic)
                        generated_name = self._simulate_basic_vlookup(generated_name, lookup_df, user_inputs)
                        
                        results.append({
                            'file_type': str(label).strip(),
                            'application': "",
                            'generated_name': generated_name,
                            'extension': str(extension) if pd.notna(extension) else "",
                            'full_filename': f"{generated_name}.{extension}" if pd.notna(extension) else generated_name
                        })
                        
                except Exception:
                    continue
            
            return results
            
        except Exception as e:
            st.error(f"Fallback method failed: {e}")
            return []
    
    def _simulate_basic_vlookup(self, text: str, lookup_df: pd.DataFrame, user_inputs: Dict) -> str:
        """Very basic VLOOKUP simulation"""
        try:
            # This is a simplified VLOOKUP - you'd need to customize based on your actual formulas
            # Example: Replace common lookup patterns
            
            for col in lookup_df.columns:
                if col in text:
                    # Simple replacement logic
                    lookup_values = lookup_df[col].dropna().tolist()
                    if lookup_values:
                        text = text.replace(col, str(lookup_values[0]))
            
            return text
            
        except Exception:
            return text

def install_required_packages():
    """Install required packages for Excel formula execution"""
    required_packages = [
        "formulas",  # Best option for web hosting
        "pycel",     # Alternative option
        "xlwings"    # For local Excel (not recommended for web)
    ]
    
    st.markdown("### 📦 Required Packages for Full Excel Support")
    
    for package in required_packages:
        if st.button(f"Install {package}", key=f"install_{package}"):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                st.success(f"✅ {package} installed successfully!")
                st.info("Please restart the application")
            except Exception as e:
                st.error(f"❌ Failed to install {package}: {e}")

def main():
    """Main function for full Excel formula support"""
    
    st.markdown("""
    ### 🏷️ Naming Conventions Tool
    **Full Excel Formula Support (VLOOKUP, Complex Functions)**
    """)
    
    # Check if Excel file exists
    excel_path = "data/naming_conventions.xlsx"
    if not os.path.exists(excel_path):
        st.error(f"❌ Excel file not found: {excel_path}")
        return
    
    # Initialize Excel engine
    try:
        engine = ExcelFormulaEngine(excel_path)
        
        # Show which method is being used
        method_info = {
            "formulas": "🔥 Using formulas package (Recommended for web)",
            "pycel": "⚡ Using pycel package (Good alternative)", 
            "xlwings": "🖥️ Using xlwings (Requires Excel on server)",
            "fallback": "⚠️ Using basic fallback (Limited functionality)"
        }
        
        st.info(method_info.get(engine.method, "Unknown method"))
        
        if engine.method == "fallback":
            with st.expander("📦 Install Full Excel Support"):
                install_required_packages()
        
    except Exception as e:
        st.error(f"❌ Failed to initialize Excel engine: {e}")
        return
    
    # Get input fields
    fields = engine.get_input_fields()
    if not fields:
        st.error("Could not read Excel field definitions")
        return
    
    # Create input form
    st.markdown("#### 📝 Input Fields")
    
    col1, col2 = st.columns(2)
    user_inputs = {}
    field_items = list(fields.items())
    mid_point = len(field_items) // 2
    
    with col1:
        for field_key, field_info in field_items[:mid_point]:
            user_inputs[field_key] = st.text_input(
                field_info['label'],
                value=field_info['current_value'],
                key=f"excel_{field_key}",
                help=f"Excel cell: {field_info['cell']}"
            )
    
    with col2:
        for field_key, field_info in field_items[mid_point:]:
            user_inputs[field_key] = st.text_input(
                field_info['label'], 
                value=field_info['current_value'],
                key=f"excel_{field_key}",
                help=f"Excel cell: {field_info['cell']}"
            )
    
    # Execute formulas button
    if st.button("🧮 Execute Excel Formulas", type="primary"):
        if any(v.strip() for v in user_inputs.values()):
            with st.spinner("Executing Excel formulas..."):
                results = engine.execute_formulas(user_inputs)
            
            if results:
                st.markdown("#### 🎯 Generated File Names")
                
                # Display as table
                display_data = []
                for result in results:
                    if result['generated_name'].strip():
                        display_data.append({
                            'File Type': result['file_type'],
                            'Application': result['application'],
                            'Generated Filename': result['full_filename'],
                            'Extension': result['extension']
                        })
                
                if display_data:
                    df = pd.DataFrame(display_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Export option
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Results",
                        data=csv_data,
                        file_name="naming_results.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No file names generated")
            else:
                st.error("No results generated - check your Excel formulas")
        else:
            st.warning("Please enter some input values")
    
    # Show current method and recommendations
    with st.expander("🔧 Technical Details"):
        st.markdown(f"**Current Method**: {engine.method}")
        
        if engine.method == "fallback":
            st.markdown("""
            **⚠️ Limited Functionality Warning**
            
            Currently using basic pattern matching. For full Excel support:
            
            1. **Install formulas package** (Recommended):
               ```bash
               pip install formulas
               ```
            
            2. **Alternative - Install pycel**:
               ```bash
               pip install pycel
               ```
            
            3. **For local development only**:
               ```bash
               pip install xlwings
               ```
            """)
        else:
            st.success("✅ Full Excel formula support active!")

if __name__ == "__main__":
    main()