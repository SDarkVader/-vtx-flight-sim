Unicode True
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "x64.nsh"
!define PRODUCT "VTX Vaderland 33 Preview"
!define PRODUCT_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\VTXVaderland33-${BUILD_ID}"
!define SHORTCUT "${PRODUCT} ${BUILD_ID}.lnk"

Name "${PRODUCT}"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\VTX\Vaderland 33\${BUILD_ID}"
InstallDirRegKey HKCU "${PRODUCT_KEY}" "InstallLocation"

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Vaderland requires 64-bit Windows."
    Abort
  ${EndIf}
FunctionEnd

Section "Vaderland"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  SetOutPath "$INSTDIR\game"
  CreateDirectory "$SMPROGRAMS\VTX"
  CreateShortcut "$SMPROGRAMS\VTX\${SHORTCUT}" "$INSTDIR\runtime\python.exe" '-B $\"$INSTDIR\game\scripts\launch_unified.py$\" --desktop --initial-environment vaderland-33 --port 8776 --data-root $\"$LOCALAPPDATA\VTX\installed-v33\${BUILD_ID}$\"'
  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayName" "${PRODUCT} (${BUILD_ID})"
  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayVersion" "${BUILD_ID}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_KEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKCU "${PRODUCT_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$SMPROGRAMS\VTX\${SHORTCUT}"
  RMDir "$SMPROGRAMS\VTX"
  !include "${UNINSTALL_FILES}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${PRODUCT_KEY}"
SectionEnd
