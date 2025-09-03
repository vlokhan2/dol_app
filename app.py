import streamlit as st
from tools import AOI_XML_Standardizer
from tools import ME_to_SE_Converter
from tools import ACM_HSL4_Attributes_Validator
from tools import Naming_Conventions  # Import the new tool
import base64

TOOLS = {
    "AOI XML Standardizer": AOI_XML_Standardizer,
    "ME to SE Converter": ME_to_SE_Converter,
    "ACM Attributes Validator": ACM_HSL4_Attributes_Validator,
    "Naming Conventions": Naming_Conventions,  # Add the new tool
}

tool_names = list(TOOLS.keys()) + ["Help / Documentation"]

# Function to encode image to base64 for sidebar
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.error(f"Error loading logo: {e}")
        return ""

# Set page configuration
st.set_page_config(page_title="Automation Tools Suite", layout="wide")

# Add logo to sidebar
logo_path = r"res\logo.png"  # Adjust path to your logo file
logo_base64 = get_base64_image(logo_path)
if logo_base64:
    st.sidebar.markdown(
        f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{logo_base64}" width="150">
        </div>
        """,
        unsafe_allow_html=True
    )

# Sidebar tool selection
st.sidebar.title("Select Tool")
selected_tool = st.sidebar.radio("Tools", tool_names, key="tool_selector")

# Main title
st.markdown(
    """
    <h1 style="text-align: left; color: #2c3e50; font-family: Arial, sans-serif;">
        Device Object Library Tools Suite
    </h1>
    <hr style="border: 1px solid #f0f2f6;">
    """,
    unsafe_allow_html=True
)

# Tool content
if selected_tool == "Help / Documentation":
    try:
        with open("docs/help_doc.md", "r", encoding="utf-8") as f:
            help_text = f.read()
        st.markdown(help_text)
    except Exception as e:
        st.error(f"Unable to load help documentation: {e}")
else:
    tool_module = TOOLS[selected_tool]
    tool_module.main()

# Footer
st.markdown(
    """
    <hr style="border: 1px solid #f0f2f6;">
    <p style="text-align: center; color: #7f8c8d; font-size: 12px; font-family: Arial, sans-serif;">
        &copy; 2025 DOL Tools Suite - Product Engineering | Developed with ❤️ for Industrial Automation
    </p>
    """,
    unsafe_allow_html=True
)