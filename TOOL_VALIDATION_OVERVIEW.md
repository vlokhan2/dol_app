# Device Object Library (DOL) Tools Suite - Detailed Validation Guide

## Executive Summary

This document provides a detailed technical overview of two critical validation tools in the DOL Tools Suite:

1. **ACM HSL4 Attributes Validator** - Metadata validation and synchronization for HSL4 XML files and attachments
2. **AOI XML Standardizer** - Comprehensive naming standardization and metadata consistency for Add-On Instructions

**Purpose:** Ensure consistency, compliance, and correctness of device object definitions before deployment to production.

---

## 1. ACM HSL4 Attributes Validator

### What It Validates
This tool validates and edits metadata attributes for HSL4 XML files used in Application Code Manager libraries.

### Key Validation Points
- **File Status** - Ensures files are marked as "Published"
- **Modified By** - Verifies attribution to "Rockwell Automation"
- **Modified Date** - Ensures date field is cleared for release versions
- **Owner** - Confirms ownership assignment to "Rockwell Automation"
- **Data Exchange ID** - Ensures field is blank for clean releases

### Three Core Features

#### Tab 1: Attribute Editor
- Upload one or more HSL4 XML files
- Review attributes in an editable table
- Visual status indicators (✅ passing / ❌ issues)
- Detailed issue descriptions for each validation failure
- Edit and apply changes directly in the UI
- Download updated files as ZIP archive

#### Tab 2: Extraction Path Validator
- Validates "ExtractionPath" attributes against predefined valid paths
- Valid paths include:
  - Visualization paths (FTViewME/SE, GlobalObjects, Displays)
  - Documentation paths
  - ViewDesigner, Images, and general Visualization folders
- Corrects invalid paths via dropdown selection
- Tracks changes and exports corrected files

#### Tab 3: Attachments Validator
- Processes .txt attachment metadata files and linked .HZ1 XML files
- Normalizes dates to ISO format (YYYY-MM-DDTHH:MM:SS)
- Syncs metadata updates between formats:
  - Description → Desc
  - Revision_Description → RevDesc
  - Modified_Date → ChangeDate
  - Modified_By → ChangeUser
  - File_Name → FileName + Ext
- Maintains file linkage by File_ID

**Use Case:** Prepare HSL4 library files for release with consistent, validated metadata.

---

## 2. AOI XML Standardizer

### Overview
The AOI XML Standardizer is a comprehensive tool for validating and standardizing Add-On Instruction (AOI) definitions. AOIs are custom instructions used in FactoryTalk Studio 5000 for industrial control logic. This tool ensures that AOI parameters, local tags, metadata, and faceplates conform to organizational standards and maintain internal consistency.

### Complete Validation Checklist

#### **Parameter Naming Validation**

**System Parameters (Reserved)**
- `EnableIn` - Required for logic control (Usage: Input, Type: BOOL)
- `EnableOut` - Required output control (Usage: Output, Type: BOOL)
- Cannot be renamed or deleted

**raC_Dvc_* Parameters (Special Handling)**
- Prefix used for device-specific parameters
- Subject to special validation rules
- Must maintain consistent naming across AOI definitions
- Examples: `raC_Dvc_E300_Config`, `raC_Dvc_Status`

**Standard Parameter Prefixes**
| Prefix | Purpose | Valid Usage | Example |
|--------|---------|------------|---------|
| `Cmd_` | Command input | Input | `Cmd_Start`, `Cmd_Stop` |
| `Cfg_` | Configuration | Input/Parameter | `Cfg_Timeout`, `Cfg_Mode` |
| `Set_` | Setpoint | Input/Parameter | `Set_Temperature`, `Set_Speed` |
| `Sts_` | Status output | Output | `Sts_Running`, `Sts_Error` |
| `Val_` | Value/General | Input/Output | `Val_Measurement`, `Val_Result` |
| `Ref_` | Reference/Lookup | Input/Parameter | `Ref_Ctrl_Inf`, `Ref_Lookup` |

**Validation Rules for Parameters**
- ✅ Must start with letter (not number or underscore)
- ✅ Contain only alphanumeric characters and underscores
- ✅ No spaces or special characters
- ✅ Prefix must match intended usage (e.g., input commands start with `Cmd_`)
- ✅ Boolean parameters identified correctly (aliases detected)
- ✅ Data types match parameter purpose

**Boolean Alias Detection**
- Flags parameters intended as boolean but incorrectly typed
- Common aliases: DINT with values 0/1, SINT with boolean logic
- Recommends type correction to BOOL

#### **Local Tag Naming Validation**

**Purpose**
- Internal tags used only within AOI logic routine
- Should follow consistent naming pattern
- Must be distinct from parameter names

**Validation Points**
- ✅ Name uniqueness (no duplicate tag names within AOI)
- ✅ Naming consistency (follow organizational conventions)
- ✅ Type appropriateness (tag data type matches usage)
- ✅ Not conflicting with system reserved words

#### **AOI Identity Validation**

**Name Attribute**
- **Format Rule**: `^[a-zA-Z][a-zA-Z0-9_]*$`
- Must start with letter
- Can contain letters, numbers, underscores only
- No spaces or special characters
- Example: ✅ `raC_Dvc_E300_AOI` | ❌ `raC-Dvc-E300`

**Revision Attribute**
- **Format Rule**: `^\d+\.\d+$` (Major.Minor)
- Example: ✅ `1.0`, `2.5`, `10.15` | ❌ `1`, `1.0.0`, `v1.0`
- Typically incremented for each release

**RevisionExtension Attribute**
- **Format Rule**: `^\.\d+$` (dot followed by number)
- Used for minor updates within same revision
- Example: ✅ `.1`, `.2`, `.15` | ❌ `1`, `.`, `_1`

**Vendor Attribute**
- ✅ Must be populated (not blank)
- Typically: "Rockwell Automation"
- Alternative organizational vendors accepted

**Validation Output**
- 🔴 **Missing** - Field required but not populated
- 🔴 **Invalid Format** - Doesn't match required pattern
- 🔴 **Invalid Type** - Wrong data type for field
- ✅ **Valid** - All checks passed

#### **AOI Metadata Consistency Validation**

**Description Field**
- Text field describing AOI purpose
- Validates against `<Description>` element in XML
- Should be consistent with LocalizedDescription

**LocalizedDescription (en-US)**
- English localized version of description
- Multi-language support attribute: `Lang='en-US'`
- Must align with primary Description

**RevisionNote**
- Documents changes in current revision
- Populated in `<RevisionNote>` element
- Should be specific and meaningful

**LocalizedRevisionNote (en-US)**
- Localized revision notes for English
- Consistency check with primary RevisionNote

**AdditionalHelpText**
- Supplementary help information
- Optional field but should be consistent if present

**Consistency Rules**
- ✅ Description ↔ LocalizedDescription should match in meaning
- ✅ RevisionNote ↔ LocalizedRevisionNote should convey same information
- ✅ All metadata fields should be non-empty for published AOIs
- ✅ Revision notes should reference actual changes

#### **Rung Comment Validation**

**Purpose**
- Ladder logic rungs can contain comments describing logic
- Comments should be clear and consistent

**Validation Points**
- ✅ Comment presence (important rungs documented)
- ✅ Comment clarity (descriptive language)
- ✅ Localization consistency (Routine and RungType match)
- ✅ Valid routine references (rungs exist in specified routine)

**Rung Types Supported**
- `RLL` - Relay Ladder Logic
- Other control logic types per FactoryTalk standard

#### **Faceplate Validation**

**DefaultData Consistency**
- Faceplates use LocalTag data with DefaultData elements
- Two formats must match:
  - **L5K Format**: Binary/encoded representation `[length,'value$00...']`
  - **String Format**: Human-readable text value

**Format Checking**
```
L5K Format:  [5,'Hello$00$00$00...']
String:      Hello
Length must match!
```

**Validation Errors**
- 🔴 **Length Mismatch** - L5K length ≠ String length
- 🔴 **Value Mismatch** - L5K value ≠ String value
- 🔴 **Missing Format** - One of the two formats missing
- ✅ **Consistent** - Both formats match

**Faceplate Naming**
- Expected pattern: `(LibraryID-SE/ME) Type-Faceplate.gfx`
- Examples:
  - ✅ `(raC-4_00-SE) raC_Dvc_E300-Faceplate.gfx`
  - ✅ `(raC-4_00-ME) raC_Dvc_E300-Faceplate.gfx`
  - ❌ `raC_Dvc_E300-Faceplate.gfx` (missing library/platform info)

**Inf_Type & Inf_Lib Tags**
- `Inf_Type` - Component type (e.g., "raC_Dvc_E300")
- `Inf_Lib` - Library identifier (e.g., "raC-4_00")
- Combined to derive expected faceplate name
- Must be present and non-empty for faceplate-enabled AOIs

### Detailed Features

#### Feature 1: Parameter Editor Tab
- **Input**: L5X (AOI) XML file
- **Display**: Editable table with all parameters
- **Columns**:
  - Name (parameter identifier)
  - Usage (Input/Output/InOut/Local)
  - Data Type (BOOL, INT, DINT, REAL, STRING, etc.)
  - Required (yes/no)
  - Visible (yes/no)
  - Suggested Name (AI-generated correction)
  - Status (✅ Valid / ⚠️ Warning / ❌ Error)

- **Actions**:
  - Accept suggested names with one click
  - View validation warnings inline
  - Edit directly in table
  - Apply bulk corrections
  - Export corrected file as ZIP

#### Feature 2: Local Tags Tab
- **Input**: L5X file
- **Display**: Editable table with local tags
- **Columns**:
  - Name (tag identifier)
  - Data Type
  - Default Value
  - Scope (Routine or AOI-level)
  - Status (✅ Valid / ❌ Error)

- **Validation Rules**:
  - No duplicate names
  - Type consistency
  - Default values match type

#### Feature 3: AOI Identity Tab
- **Input**: AOI attributes from XML header
- **Display**: Form-based editor for:
  - AOI Name
  - Revision
  - RevisionExtension
  - Vendor
  - Description
  - LocalizedDescription
  - RevisionNote
  - LocalizedRevisionNote
  - AdditionalHelpText

- **Real-Time Validation**:
  - Format checking as user types
  - Color-coded feedback (red = invalid, green = valid)
  - Requirement indicators (required vs. optional)

#### Feature 4: Rung Comments Tab
- **Input**: L5X file with RLL routines
- **Display**: Table of ladder logic rungs
- **Columns**:
  - Routine Name
  - Rung Number
  - Rung Type
  - Rung Text (ladder logic preview)
  - Comment (editable)
  - Localized Comment (en-US, editable)

- **Features**:
  - Add/edit comments
  - Localization support
  - Batch comment updates

#### Feature 5: Faceplate Validator Tab
- **Input**: Expected faceplate name + XML tags
- **Process**:
  1. User enters expected faceplate name format
  2. Tool validates Inf_Type and Inf_Lib tag values
  3. Checks DefaultData L5K ↔ String consistency
  4. Verifies derived name matches expected format

- **Output**:
  - ✅ All validations passed
  - 🔴 List of failed validations with details
  - Suggested corrections for mismatches

#### Feature 6: Change Tracking & Export
- **Change Detection**:
  - Compares original vs. edited values
  - Tracks changes by parameter/tag/property

- **Change Summary Table**:
  - Field name
  - Old value
  - New value
  - File affected

- **Export Process**:
  - Click "Apply Changes"
  - Updated XML written to ZIP
  - Original file name preserved
  - Complete audit trail maintained

### Workflow & Data Flow

```
User uploads L5X file
        ↓
Parse XML → Extract all parameters, tags, metadata
        ↓
Run validation checks on each element
        ↓
Display results in tabs with status indicators
        ↓
User edits values in UI tables/forms
        ↓
Detect changes (original vs. current)
        ↓
Show change summary
        ↓
User clicks "Apply Changes"
        ↓
Update XML tree with new values
        ↓
Export to ZIP with updated file
        ↓
User downloads ZIP for deployment
```

### Exception Handling

**System Parameters** (Cannot be modified)
- EnableIn
- EnableOut
- Flagged as "System Reserved" in UI

**Reference Parameter Exceptions**
- Special reference parameters treated differently:
  - Ref_Ctrl_Inf
  - Ref_Ctrl_Set
  - Ref_Ctrl_Cmd
  - Ref_Ctrl_Sts
  - Ref_Ctrl_Itf
  - Inf_Lookup

**Validation Bypass**
- User can override validation warnings
- All changes logged for audit trail
- Confirmation required for critical changes

---

## Detailed Comparison: ACM Attributes Validator vs. AOI Standardizer

| Aspect | ACM HSL4 Validator | AOI Standardizer |
|--------|-------------------|------------------|
| **Input File Type** | HSL4 XML + Attachments (.txt, .HZ1) | L5X (AOI XML) |
| **Primary Focus** | Release metadata consistency | Internal naming & structure standards |
| **Validation Scope** | 5 core attributes + extraction paths | 20+ validation points across 6 dimensions |
| **Output Format** | Updated HSL4/HZ1 files in ZIP | Updated L5X file in ZIP |
| **Edit Capability** | Full attribute editing | Full parameter/tag/metadata editing |
| **Automation Level** | Manual editing + batch export | AI-suggested corrections + batch apply |
| **Integration Points** | Attachment sync, path validation | Parameter suggestions, format enforcement |
| **Release Stage** | Pre-release validation | Development & pre-release validation |

---

## Testing Scenarios

### ACM HSL4 Attributes Validator Testing

**Scenario 1: Status Validation**
- Upload HSL4 file with Status="Draft"
- Expected: ❌ Error: "Status should be 'Published'"
- Action: Edit to "Published"
- Result: ✅ Pass validation

**Scenario 2: Multi-Revision File**
- Upload HSL4 with 3 revisions
- Each revision has different ModifiedBy values
- Expected: All 3 show validation errors
- Action: Update all to "Rockwell Automation"
- Result: All pass after update

**Scenario 3: Extraction Path Correction**
- Upload HSL4 with invalid ExtractionPath
- Expected: Dropdown shows valid path options
- Action: Select correct path from dropdown
- Result: Path corrected, exported in ZIP

**Scenario 4: Attachment Sync**
- Upload .txt metadata + matching .HZ1 file
- Edit Description in .txt
- Expected: Changes sync to .HZ1 Desc field
- Result: Both files updated in export ZIP

### AOI Standardizer Testing

**Scenario 1: Parameter Naming**
- Upload L5X with parameter "InputCommand"
- Expected: Suggestion to rename "Cmd_InputCommand"
- Action: Accept suggestion
- Result: Parameter renamed, exported

**Scenario 2: Invalid Revision Format**
- AOI has Revision="1" (should be "1.0")
- Expected: ❌ Error with format requirement
- Action: Edit to "1.0"
- Result: ✅ Pass validation

**Scenario 3: DefaultData Mismatch**
- LocalTag has L5K=[5,'Hello$00'] but String="Goodbye"
- Expected: 🔴 Value Mismatch error
- Action: Correct String to "Hello"
- Result: Formats now consistent

**Scenario 4: Faceplate Name Validation**
- Inf_Type="E300", Inf_Lib="raC-4_00", but faceplate name missing platform
- Expected: Suggest "(raC-4_00-SE) E300-Faceplate.gfx"
- Action: Accept suggestion
- Result: Faceplate name corrected

---

## Error Codes & Resolution

### ACM HSL4 Validator Errors

| Error Code | Message | Cause | Resolution |
|------------|---------|-------|-----------|
| `ACM-001` | Status should be 'Published' | File in draft state | Change Status dropdown to "Published" |
| `ACM-002` | ModifiedBy should be 'Rockwell Automation' | Wrong attribution | Edit ModifiedBy field |
| `ACM-003` | ModifiedDate should be blank | Date leftover from development | Clear ModifiedDate field |
| `ACM-004` | Owner should be 'Rockwell Automation' | Incorrect ownership | Update Owner field |
| `ACM-005` | DataExchangeId should be blank | Leftover development data | Clear DataExchangeId field |
| `ACM-010` | Invalid ExtractionPath | Path not in approved list | Select from dropdown of valid paths |
| `ACM-020` | Date format invalid | Date doesn't parse | Use format YYYY-MM-DD HH:MM:SS |
| `ACM-030` | File_ID mismatch | .txt and .HZ1 IDs don't match | Verify file pairs before upload |

### AOI Standardizer Errors

| Error Code | Message | Cause | Resolution |
|------------|---------|-------|-----------|
| `AOI-001` | Name format invalid | Starts with number/special char | Rename to start with letter |
| `AOI-002` | Revision format invalid | Not X.Y format | Change to semantic versioning (e.g., 1.0) |
| `AOI-003` | RevisionExtension format invalid | Not .Z format | Change to .1, .2, etc. |
| `AOI-010` | Parameter name violates prefix | Wrong prefix for usage type | Rename with correct prefix (Cmd_, Sts_, etc.) |
| `AOI-011` | Boolean alias detected | DINT used for boolean logic | Change type to BOOL |
| `AOI-020` | DefaultData mismatch | L5K and String don't match | Correct String to match L5K decoded value |
| `AOI-030` | Faceplate name mismatch | Name doesn't match Inf_Type/Inf_Lib | Use format (Lib-SE/ME) Type-Faceplate.gfx |
| `AOI-040` | Duplicate tag name | Two tags with same name | Rename one of the tags |

---

## Key Benefits for Testing Team

| Benefit | ACM Validator | AOI Standardizer |
|---------|---------------|------------------|
| **Automated Validation** | ✅ 5-point release checklist | ✅ 20+ validation rules |
| **Batch Processing** | ✅ Multiple files at once | ✅ Multiple files at once |
| **AI Suggestions** | ⚠️ Limited (dropdown options) | ✅ Auto-generates corrections |
| **Metadata Sync** | ✅ .txt ↔ .HZ1 synchronization | N/A |
| **Audit Trail** | ✅ Change tracking | ✅ Change tracking |
| **Export Control** | ✅ ZIP format with version control | ✅ ZIP format with version control |

---

## Technical Specifications

### ACM HSL4 Validator
- **XML Parser**: ElementTree with CDATA preservation
- **Max File Size**: 50MB per file
- **Supported Extensions**: .HSL4, .xml, .txt, .hz1, .zip
- **Concurrent Files**: Unlimited (batch mode)
- **Processing Time**: ~100ms per file average

### AOI Standardizer  
- **XML Parser**: ElementTree with blank text removal
- **Max File Size**: 100MB per file
- **Supported Extensions**: .L5X, .xml
- **Parsing Depth**: Recursive (entire XML tree)
- **Processing Time**: ~200ms per file average

---

**Last Updated:** January 12, 2026  
**Version:** 2.0 - Detailed Focus  
**Audience:** QA/Testing Teams, Product Engineering, DevOps, Development Teams
