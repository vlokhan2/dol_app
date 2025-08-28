# DOL Tools Suite - Common Documentation

Welcome to the DOL Tools Suite. This documentation provides an overview and usage guidelines for all available tools.

---

## Available Tools

### 1. AOI XML Standardizer

- **Purpose:** Standardizes and validates AOI XML tag names and descriptions.
- **Features:**  
  - Checks parameter naming conventions  
  - Suggests corrected names  
  - Allows inline editing of names and descriptions  
  - Updates XML content accordingly  
- **Usage Tips:**  
  Upload your `.L5X` XML file, review suggestions, edit if needed, and download the updated file.

#### AOI XML Naming Rules — Quick Reference

| **Type**               | **Prefix Required**      | **Data Type** | **Other Rules**                                                                                       | **Notes/Exceptions**                             |
|------------------------|--------------------------|---------------|-----------------------------------------------------------------------------------------------------|-------------------------------------------------|
| System Parameters      | EnableIn/EnableOut        | BOOL          | No checks needed; keep as is                                                                        |                                                 |
| raC_Dvc_… Parameters   | raC_Dvc_                 | BOOL          | Usage must be Input or Output; Description required                                                 | Only DataType, Usage, Description validated     |
| InOut Parameters       | Ref_                     | Any           | Name must start with Ref_ and use one underscore;<br>Required and Visible must be True; ExternalAccess must be empty | Ref_Ctrl_Inf/Set/Cmd/Sts are allowed as is      |
| Input BOOL Parameters  | Cmd_                     | BOOL          | Name must start with Cmd_ and use one underscore                                                    | Removes extra prefixes                           |
| Input (non-BOOL)       | Cfg_ or Set_             | Not BOOL      | Name must start with Cfg_ or Set_ and use one underscore                                            | Removes extra prefixes                           |
| Output BOOL Parameters | Sts_                     | BOOL          | Name must start with Sts_ and use one underscore                                                    | Removes extra prefixes                           |
| Output (non-BOOL)      | Val_, Sts_b, or Sts_e    | Not BOOL      | Name must start with one of these and use one underscore                                            | Removes extra prefixes                           |
| Local Tags             | Wrk_                     | Any           | Name must start with Wrk_ and use one underscore                                                    | Except for certain special tags (see below)     |
| Local Tag Exceptions   | Exact name               | Any           | Must have ExternalAccess = Read/Write                                                              | E.g. HMI_Tab, Inf_Type, Sts_eEventType, etc.    |

---

**Note:**  
All suggested names should have exactly one underscore unless noted as an exception above.

---

#### Local Tag Exceptions Include:

HMI_Tab, HMI_Version, Inf_Type, Inf_Lib, Sts_eEventValue, Sts_tEventTime, D1, Sts_tEventTimeD0, Sts_tEventTimeD2, Sts_tEventTimeD3, Sts_EventMessage, Sts_eEventType

---

# AOI Local Tags Naming Convention Rules

## When to Use Local Tags
Use Local tags for arrays and custom datatypes that cannot be defined as Output parameters but need HMI access.

## Primary Naming Convention Rules

### **Based on ExternalAccess Property:**

| ExternalAccess | Prefix | Data Types | Purpose | Examples |
|----------------|--------|------------|---------|----------|
| **Read Only / Read Write** | **Val_** | DINT, INT, REAL, USINT, SINT, UDINT arrays<br>Custom UDTs<br>STRING (data/config) | Numeric values, measurements, calculations, configurations, identifiers | `Val_HistoryData[10]`<br>`Val_ProcessConfig_UDT`<br>`Val_PartNumber`<br>`Val_SetpointArray[5]` |
| **Read Only / Read Write** | **Sts_** | BOOL<br>STRING (status/messages) | Status flags, conditions, status messages, state descriptions | `Sts_DataValid`<br>`Sts_EventMessage`<br>`Sts_AlarmText`<br>`Sts_SystemState` |
| **None** | **Wrk_** | All data types | Internal calculations, temporary variables, working data | `Wrk_TempBuffer[10]`<br>`Wrk_Counter`<br>`Wrk_ProcessingFlag`<br>`Wrk_InternalTimer` |

## **Standard Exceptions (Reserved Prefixes)**

| Prefix | Purpose | Data Types | Examples | Usage |
|--------|---------|------------|----------|--------|
| **HMI_** | HMI interface control | SINT, BOOL, STRING | `HMI_Tab: SINT`<br>`HMI_Version: BOOL`<br>`HMI_ActiveScreen: STRING` | HMI navigation, version control, screen management |
| **Inf_** | AOI information/metadata | STRING primarily | `Inf_Type: STRING`<br>`Inf_Lib: STRING`<br>`Inf_Version: STRING`<br>`Inf_Description: STRING` | AOI identification, library info, documentation |

## Complete Examples by Category

### **Val_** Examples (Values/Data)
**Numeric Arrays:**
- `Val_HistoryData: DINT[10]` - Historical process values for trending
- `Val_TrendBuffer: REAL[50]` - Real-time trending data  
- `Val_SetpointSchedule: REAL[24]` - Hourly setpoint values
- `Val_QualityMetrics: REAL[5]` - Quality measurement array

**Custom UDT Arrays:**
- `Val_RecipeSteps: Recipe_UDT[10]` - Recipe step parameters
- `Val_AlarmBuffer: Alarm_UDT[20]` - Structured alarm history
- `Val_BatchData: Batch_UDT[5]` - Batch processing data

**Configuration Strings:**
- `Val_PartNumber: STRING` - Product part number
- `Val_OperatorName: STRING` - Current operator name
- `Val_ProductCode: STRING` - Active product code
- `Val_RecipeName: STRING` - Current recipe name

### **Sts_** Examples (Status/State)
**Status Booleans:**
- `Sts_DataValid: BOOL` - Data integrity status
- `Sts_BufferFull: BOOL` - History buffer full condition
- `Sts_TrendingActive: BOOL` - Trending function status
- `Sts_ProcessComplete: BOOL` - Process completion status

**Status/Message Strings:**
- `Sts_EventMessage: STRING` - Current event message
- `Sts_AlarmText: STRING` - Active alarm description  
- `Sts_SystemState: STRING` - Current operational state
- `Sts_ErrorDescription: STRING` - Detailed error information

### **HMI_** Examples (HMI Interface Control)
- `HMI_Tab: SINT` - Active HMI tab selection
- `HMI_Version: BOOL` - HMI version control flag
- `HMI_ActiveScreen: STRING` - Current screen identifier
- `HMI_NavigationState: DINT` - Navigation state control

### **Inf_** Examples (AOI Information/Metadata)
- `Inf_Type: STRING` - AOI type identification
- `Inf_Lib: STRING` - Library version information
- `Inf_Version: STRING` - AOI version number
- `Inf_Description: STRING` - AOI functional description

### **Wrk_** Examples (Internal Only - ExternalAccess = None)
- `Wrk_TempBuffer: DINT[10]` - Internal calculation buffer
- `Wrk_Counter: INT` - Internal loop counter
- `Wrk_ProcessingFlag: BOOL` - Internal processing state
- `Wrk_InternalTimer: TIMER` - Internal timing function

## Decision Tree for Local Tag Naming

```
Local Tag Created
    ↓
Is ExternalAccess = None?
    ↓                    ↓
   YES                  NO
    ↓                    ↓
Use Wrk_ prefix    Is it HMI interface control?
                        ↓                    ↓
                       YES                  NO
                        ↓                    ↓
                   Use HMI_ prefix    Is it AOI metadata?
                                           ↓                    ↓
                                          YES                  NO
                                           ↓                    ↓
                                      Use Inf_ prefix    Is it status/state/message?
                                                              ↓                    ↓
                                                             YES                  NO
                                                              ↓                    ↓
                                                         Use Sts_ prefix    Use Val_ prefix
```

## Implementation Benefits

1. **Automatic Classification:** ExternalAccess property drives naming decision
2. **Clear Separation:** Immediate identification of tag purpose and accessibility
3. **HMI Development:** Developers know to only look for Val_/Sts_/HMI_/Inf_ prefixes
4. **Code Maintenance:** Wrk_ tags can be modified without external impact
5. **Standardization:** Consistent across all AOIs and development teams
6. **Future-Proof:** Scales with project complexity and team size

---

### 2. ME to SE convertor

- **Purpose:** Convert Machine Edition (ME) faceplate XML files into FTView SE compatible format. This involves resizing display elements, repositioning graphical components, removing unwanted elements, and updating internal references.
- **Workflow:**  
  - In ME, select the faceplates you want to convert.
  - Export the selected faceplates as .gfx files.
  - Import these .gfx files into your SE project using the Add Component feature.
  - Export the imported faceplates from SE as XML (.xml) files.
  - Use this tool to upload those exported .xml files for batch conversion.
  - The app will process all uploaded files, creating resized and repositioned SE-compatible XML files.
  - A batch import XML file will be generated to facilitate easy import of all converted faceplates into SE.
  - Download all the converted XML files bundled as a ZIP archive.
  - Unzip downloaded file and use BatchImport file to import all converted faceplates into ME
  - Make sure before import delete all old faceplates and then use BatchImport and import updated faceplate
  
- **Instructions:**  
  - Prepare your ME faceplate XML files as described above.
  - Upload all .xml files using the multi-select uploader in the app.
  - Click Convert to start the batch processing.
  - Monitor progress and status messages to track conversion.
  - Once complete, download the ZIP archive containing all converted files plus the batch import file.
  
- **Important Notes:**

  - Make sure the input files are valid ME faceplate XML exports.
  - The tool adjusts display sizes by shifting elements 5 pixels left and 30 pixels up by default.
  - You can customize which graphical elements to remove by modifying the predefined removal list in the app code (currently includes elements like styles and borders).
  - atch import XML is named BatchImport_raX.xml and contains entries for all converted files.
  - Output files are saved in a timestamped folder for easy reference.

---

## General Instructions

- Use the sidebar to select the tool you want to use.
- Each tool has its own interface and workflows.
- Use the "Apply Changes" or equivalent buttons within each tool to perform updates.
- Download updated files or reports as needed.

---

## Support & Contributions

For questions, bug reports, or feature requests, please contact the development team or submit issues via the project repository.

Thank you for using DOL Tools Suite!

---

Vikram R. L.  Library & Solution Architect

Device Object Library 2025