# AOI XML Naming Rules — Quick Reference

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

## Local Tag Exceptions Include:

HMI_Tab, HMI_Version, Inf_Type, Inf_Lib, Sts_eEventValue, Sts_tEventTime, D1, Sts_tEventTimeD0, Sts_tEventTimeD2, Sts_tEventTimeD3, Sts_EventMessage, Sts_eEventType
