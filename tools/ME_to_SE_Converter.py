import streamlit as st
from pathlib import Path
import lxml.etree as ET
import copy
import datetime
import os
import re
import tempfile
import zipfile


def createBatchFile(importList, batchFileName, outFolder):
    root = ET.Element("gfxImport")
    for file in importList:
        ET.SubElement(root, "import").set("importFile", file)
    tree = ET.ElementTree(root)
    tree.write(
        str(Path(outFolder) / batchFileName),
        encoding="UTF-8",
        xml_declaration=False,
        pretty_print=True,
    )


def listFiles(folder, extension):
    files = [f for f in os.listdir(folder) if f.endswith(extension)]
    return files


def createTimestampedFolder(basePath, folderName, useTimestamp=True):
    if useTimestamp:
        now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        outFolder = Path(basePath) / f"{folderName}{now}"
    else:
        outFolder = Path(basePath) / folderName
    outFolder.mkdir(parents=True, exist_ok=True)
    return str(outFolder)


def getXMLRoot(file_obj):
    parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
    tree = ET.parse(file_obj, parser=parser)
    root = copy.deepcopy(tree.getroot())
    return root


def removeElementByName(root, name):
    cPath = f".//*[@name='{name}']"
    pPath = f".//*[@name='{name}']/.."
    child = root.find(cPath)
    parent = root.find(pPath)
    if child is None:
        return
    if parent is not None and parent.get("name") is not None:
        parent.remove(child)
    else:
        root.remove(child)


def convert_ME_to_SE(xml_file_obj, out_folder, move_left=0, move_top=0, *args, **kwargs):
    st.write(f"Working on: {xml_file_obj.name}")
    root = getXMLRoot(xml_file_obj)

    display = root.find("displaySettings")
    if display is None:
        st.error(f"{xml_file_obj.name} is not a valid FTV XML file.")
        return None

    height = int(display.get("height")) - move_top - 5
    width = int(display.get("width")) - 2 * move_left
    display.set("height", str(height))
    display.set("width", str(width))
    display.set("titleBar", "true")
    display.set("titleBarText", "/*S:0 #2.@Description*/")
    display.set("maximumUpdateRate", "0.5")

    for element_to_remove in args:
        removeElementByName(root, element_to_remove)

    for el in root.findall(".//*"):
        if el.tag == "button":
            el.set("style", "noborder")
            el.attrib.pop("bevelWidth", None)

    if "Toolbox - Common" not in xml_file_obj.name:
        for el in root.findall(".//*[@top]"):
            el.attrib["top"] = str(int(el.attrib["top"]) - move_top)
        for el in root.findall(".//*[@left]"):
            if "VersionI" not in el.get("name", ""):
                el.attrib["left"] = str(int(el.attrib["left"]) - move_left)

    for el in root.findall(".//*"):
        for attrib in el.keys():
            val = el.get(attrib)
            if val and kwargs.get("find") in val:
                el.set(attrib, val.replace(kwargs["find"], kwargs["replace"]))

    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.ElementTree(root, parser=parser)

    out_file_name = xml_file_obj.name.replace(kwargs.get("find"), kwargs.get("replace"))
    out_file_path = Path(out_folder) / out_file_name
    tree.write(str(out_file_path), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    return out_file_name


def main():
    st.title("ME to SE Faceplate Converter")

    st.markdown(
        """
### Instructions
1. From ME, select the faceplates you want to convert.
2. Take those faceplates (`.gfx` files) and add them into your SE project using "Add Component".
3. Export these added faceplates as XML files from SE and save them to a folder.
4. Upload the `.xml` files below (multiple selection allowed).
5. Click **Convert** to begin processing.
6. After conversion completes, download the resulting ZIP archive containing converted files and batch import XML.
"""
    )

    uploaded_files = st.file_uploader(
        "Select ME faceplate XML files",
        type="xml",
        accept_multiple_files=True,
    )

    if uploaded_files:
        if st.button("Convert"):
            out_folder = Path(createTimestampedFolder(".", "MEtoSE_", useTimestamp=True))
            st.info(f"Converting {len(uploaded_files)} files to folder: {out_folder}")

            converted_files = []
            prog_bar = st.progress(0)

            for i, file_obj in enumerate(uploaded_files):
                out_file = convert_ME_to_SE(
                    file_obj,
                    out_folder,
                    5,
                    30,
                    "Common_Framework",
                    find="-ME)",
                    replace="-SE)",
                )
                if out_file:
                    converted_files.append(out_file)
                prog_bar.progress((i + 1) / len(uploaded_files))

            if converted_files:
                createBatchFile(converted_files, "BatchImport_raX.xml", out_folder)

                zip_path = Path(tempfile.gettempdir()) / "MEtoSE_Converted.zip"
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for f in out_folder.iterdir():
                        zipf.write(f, arcname=f.name)

                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="Download Converted ZIP",
                        data=f,
                        file_name="MEtoSE_Converted.zip",
                        mime="application/zip",
                    )
                st.success("Conversion completed successfully.")
            else:
                st.warning("No files were converted.")


if __name__ == "__main__":
    main()
