Attribute VB_Name = "ntwebsrv_client"
' ntwebsrv_client.bas - VBA/Access Basic client for ntwebsrv (Automation Agent)
' 
' Requires: MS Access 2010+ / VBA 7+, WinHttp.WinHttpRequest.5.1
' For SHA256: Windows CAPI (advapi32.dll) via late binding, fallback to CAPICOM
' 
' Supports three modes:
'   1. LEGACY UPLOAD (multipart) - POST /ricevi
'   2. COMMANDS (JSON RPC) - POST /api/command
'   3. DOWNLOAD - GET /api/download/{target}?zip_mode=true
' 
' JSON formats:
'   Legacy: { "parametri": {...}, "files": {...}, "auth": {...} }
'   Command: { "comando": "save|exit|restart|reboot|poweroff|exec", "target": "...", "payload": {...} }
' 
' Usage:
'   ' Legacy upload
'   ok = ntwebsrv_SendJson("C:\path\upload.json", "http://localhost:8000", "MySecretKey")
'   
'   ' Command (JSON RPC)
'   ok = ntwebsrv_SendCommand("C:\path\cmd_exit.json", "http://localhost:8000", , "my_base_secret")
'   
'   ' Download
'   ok = ntwebsrv_Download("report.pdf", "http://localhost:8000", "C:\downloads\report.pdf", , "my_base_secret")
'   ok = ntwebsrv_Download("logs", "http://localhost:8000", "C:\downloads\logs.zip", True, "my_base_secret")
' 
' Returns: Boolean (True = success, False = failure)
' Response JSON stored in g_ntwebsrv_LastResponse
' Error message in g_ntwebsrv_LastError

Option Explicit

' Globals
Public g_ntwebsrv_LastResponse As String
Public g_ntwebsrv_LastStatusCode As Long
Public g_ntwebsrv_LastError As String

' Constants
Private Const DEFAULT_BASE_URL = "http://localhost:8000"
Private Const DEFAULT_TIMEOUT = 30
Private Const BOUNDARY_PREFIX = "----ntwebsrvBoundary"

' ============================================================================
' PUBLIC FUNCTIONS
' ============================================================================

' ------------------------------------------------------------
' MODE 1: LEGACY UPLOAD (multipart) - POST /ricevi
' ------------------------------------------------------------
Public Function ntwebsrv_SendJson( _
    ByVal jsonFilePath As String, _
    Optional ByVal baseUrl As String = "", _
    Optional ByVal key As String = "", _
    Optional ByVal keyhashBase As String = "", _
    Optional ByVal timeoutSec As Long = DEFAULT_TIMEOUT _
) As Boolean
    
    Dim jsonContent As String
    Dim jsonDict As Object
    Dim parametri As Object
    Dim files As Object
    Dim authKey As String
    Dim authKhBase As String
    Dim authKh As String
    Dim dayOfMonth As Long
    Dim boundary As String
    Dim body() As Byte
    Dim winHttp As Object
    Dim responseText As String
    Dim statusCode As Long
    Dim contentType As String
    Dim fso As Object
    
    ' Initialize globals
    g_ntwebsrv_LastResponse = ""
    g_ntwebsrv_LastStatusCode = 0
    g_ntwebsrv_LastError = ""
    
    If baseUrl = "" Then baseUrl = DEFAULT_BASE_URL
    Dim url As String
    url = baseUrl
    If Right(url, 1) <> "/" Then url = url & "/"
    url = url & "ricevi"
    
    ' Validate JSON file
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(jsonFilePath) Then
        g_ntwebsrv_LastError = "JSON file not found: " & jsonFilePath
        ntwebsrv_SendJson = False
        Exit Function
    End If
    
    ' Read JSON file
    jsonContent = ntwebsrv_ReadTextFile(jsonFilePath)
    If jsonContent = "" Then
        g_ntwebsrv_LastError = "Failed to read JSON file"
        ntwebsrv_SendJson = False
        Exit Function
    End If
    
    ' Parse JSON
    Set jsonDict = ntwebsrv_ParseJson(jsonContent)
    If jsonDict Is Nothing Then
        g_ntwebsrv_LastError = "Failed to parse JSON"
        ntwebsrv_SendJson = False
        Exit Function
    End If
    
    ' Extract sections
    Set parametri = ntwebsrv_GetDict(jsonDict, "parametri")
    Set files = ntwebsrv_GetDict(jsonDict, "files")
    authKey = ntwebsrv_GetString(jsonDict, "auth.key", "")
    authKhBase = ntwebsrv_GetString(jsonDict, "auth.keyhash", "")
    
    ' Function parameter overrides
    If key <> "" Then authKey = key
    If keyhashBase <> "" Then authKhBase = keyhashBase
    
    ' Calculate _kh for legacy form field
    authKh = ""
    If authKhBase <> "" Then
        dayOfMonth = Day(Date)
        authKh = ntwebsrv_SHA256(authKhBase & CStr(dayOfMonth))
        If authKh = "" Then
            g_ntwebsrv_LastError = "Failed to calculate SHA256 hash"
            ntwebsrv_SendJson = False
            Exit Function
        End If
    End If
    
    ' Verify files exist
    If Not files Is Nothing Then
        Dim fieldName As Variant
        Dim filePath As String
        For Each fieldName In files.Keys
            filePath = files(fieldName)
            If Not fso.FileExists(filePath) Then
                g_ntwebsrv_LastError = "Missing file: " & fieldName & " -> " & filePath
                ntwebsrv_SendJson = False
                Exit Function
            End If
        Next fieldName
    End If
    
    ' Build multipart body
    boundary = BOUNDARY_PREFIX & Replace(CStr(Timer), ".", "")
    body = ntwebsrv_BuildMultipartBody(parametri, files, authKey, authKh, boundary)
    If Not IsArray(body) Then
        g_ntwebsrv_LastError = "Failed to build request body"
        ntwebsrv_SendJson = False
        Exit Function
    End If
    
    ' Build auth header (for header-based auth)
    Dim authHeader As String
    authHeader = ntwebsrv_BuildAuthHeader(key, keyhashBase)
    
    ' Send request
    contentType = "multipart/form-data; boundary=" & boundary
    
    Set winHttp = CreateObject("WinHttp.WinHttpRequest.5.1")
    On Error Resume Next
    winHttp.SetTimeouts timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000
    winHttp.Open "POST", url, False
    winHttp.SetRequestHeader "Content-Type", contentType
    If authHeader <> "" Then winHttp.SetRequestHeader "X-API-Key", authHeader
    winHttp.Send body
    
    If Err.Number <> 0 Then
        g_ntwebsrv_LastError = "HTTP request failed: " & Err.Description
        ntwebsrv_SendJson = False
        Exit Function
    End If
    On Error GoTo 0
    
    statusCode = winHttp.Status
    responseText = winHttp.ResponseText
    
    g_ntwebsrv_LastStatusCode = statusCode
    g_ntwebsrv_LastResponse = responseText
    
    If statusCode = 200 Then
        ntwebsrv_SendJson = True
    Else
        g_ntwebsrv_LastError = "HTTP " & statusCode & ": " & responseText
        ntwebsrv_SendJson = False
    End If
    
End Function

' ------------------------------------------------------------
' MODE 2: COMMANDS (JSON RPC) - POST /api/command
' ------------------------------------------------------------
Public Function ntwebsrv_SendCommand( _
    ByVal jsonFilePath As String, _
    Optional ByVal baseUrl As String = "", _
    Optional ByVal key As String = "", _
    Optional ByVal keyhashBase As String = "", _
    Optional ByVal timeoutSec As Long = DEFAULT_TIMEOUT _
) As Boolean
    
    Dim jsonContent As String
    Dim winHttp As Object
    Dim responseText As String
    Dim statusCode As Long
    Dim authHeader As String
    Dim url As String
    Dim fso As Object
    
    ' Initialize globals
    g_ntwebsrv_LastResponse = ""
    g_ntwebsrv_LastStatusCode = 0
    g_ntwebsrv_LastError = ""
    
    If baseUrl = "" Then baseUrl = DEFAULT_BASE_URL
    url = baseUrl
    If Right(url, 1) <> "/" Then url = url & "/"
    url = url & "api/command"
    
    ' Validate JSON file
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(jsonFilePath) Then
        g_ntwebsrv_LastError = "JSON file not found: " & jsonFilePath
        ntwebsrv_SendCommand = False
        Exit Function
    End If
    
    ' Read JSON file
    jsonContent = ntwebsrv_ReadTextFile(jsonFilePath)
    If jsonContent = "" Then
        g_ntwebsrv_LastError = "Failed to read JSON file"
        ntwebsrv_SendCommand = False
        Exit Function
    End If
    
    ' Build auth header
    authHeader = ntwebsrv_BuildAuthHeader(key, keyhashBase)
    
    ' Send request (JSON body)
    Set winHttp = CreateObject("WinHttp.WinHttpRequest.5.1")
    On Error Resume Next
    winHttp.SetTimeouts timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000
    winHttp.Open "POST", url, False
    winHttp.SetRequestHeader "Content-Type", "application/json"
    If authHeader <> "" Then winHttp.SetRequestHeader "X-API-Key", authHeader
    winHttp.Send jsonContent
    
    If Err.Number <> 0 Then
        g_ntwebsrv_LastError = "HTTP request failed: " & Err.Description
        ntwebsrv_SendCommand = False
        Exit Function
    End If
    On Error GoTo 0
    
    statusCode = winHttp.Status
    responseText = winHttp.ResponseText
    
    g_ntwebsrv_LastStatusCode = statusCode
    g_ntwebsrv_LastResponse = responseText
    
    If statusCode = 200 Then
        ntwebsrv_SendCommand = True
    Else
        g_ntwebsrv_LastError = "HTTP " & statusCode & ": " & responseText
        ntwebsrv_SendCommand = False
    End If
    
End Function

' ------------------------------------------------------------
' MODE 3: DOWNLOAD - GET /api/download/{target}
' ------------------------------------------------------------
Public Function ntwebsrv_Download( _
    ByVal target As String, _
    Optional ByVal baseUrl As String = "", _
    Optional ByVal outputFile As String = "", _
    Optional ByVal zipMode As Boolean = False, _
    Optional ByVal key As String = "", _
    Optional ByVal keyhashBase As String = "", _
    Optional ByVal timeoutSec As Long = DEFAULT_TIMEOUT _
) As Boolean
    
    Dim winHttp As Object
    Dim responseBytes() As Byte
    Dim statusCode As Long
    Dim authHeader As String
    Dim url As String
    Dim fso As Object
    Dim stream As Object
    
    ' Initialize globals
    g_ntwebsrv_LastResponse = ""
    g_ntwebsrv_LastStatusCode = 0
    g_ntwebsrv_LastError = ""
    
    If baseUrl = "" Then baseUrl = DEFAULT_BASE_URL
    url = baseUrl
    If Right(url, 1) <> "/" Then url = url & "/"
    url = url & "api/download/" & target
    If zipMode Then url = url & "?zip_mode=true"
    
    ' Build auth header
    authHeader = ntwebsrv_BuildAuthHeader(key, keyhashBase)
    
    ' Send request
    Set winHttp = CreateObject("WinHttp.WinHttpRequest.5.1")
    On Error Resume Next
    winHttp.SetTimeouts timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000, timeoutSec * 1000
    winHttp.Open "GET", url, False
    If authHeader <> "" Then winHttp.SetRequestHeader "X-API-Key", authHeader
    winHttp.Send
    
    If Err.Number <> 0 Then
        g_ntwebsrv_LastError = "HTTP request failed: " & Err.Description
        ntwebsrv_Download = False
        Exit Function
    End If
    On Error GoTo 0
    
    statusCode = winHttp.Status
    responseBytes = winHttp.ResponseBody
    
    g_ntwebsrv_LastStatusCode = statusCode
    
    If statusCode = 200 Then
        ' Determine output filename
        Dim outFile As String
        outFile = outputFile
        If outFile = "" Then
            ' Try to get from Content-Disposition
            Dim cd As String
            cd = winHttp.GetResponseHeader("Content-Disposition")
            If InStr(cd, "filename=") > 0 Then
                outFile = Mid(cd, InStr(cd, "filename=") + 9)
                outFile = Replace(outFile, """", "")
                outFile = Trim(outFile)
            Else
                outFile = "download_" & Format(Date, "yyyymmdd") & "_" & Format(Time, "hhnnss")
                If zipMode Then outFile = outFile & ".zip"
            End If
        End If
        
        ' Save file
        Set stream = CreateObject("ADODB.Stream")
        stream.Type = 1 ' adTypeBinary
        stream.Open
        stream.Write responseBytes
        stream.SaveToFile outFile, 2 ' adSaveCreateOverWrite
        stream.Close
        Set stream = Nothing
        
        g_ntwebsrv_LastResponse = "Downloaded to: " & outFile
        ntwebsrv_Download = True
    Else
        g_ntwebsrv_LastError = "HTTP " & statusCode
        g_ntwebsrv_LastResponse = ""
        ntwebsrv_Download = False
    End If
    
End Function

' ============================================================================
' HELPER FUNCTIONS
' ============================================================================

' Builds X-API-Key header from key or keyhashBase
Private Function ntwebsrv_BuildAuthHeader(ByVal key As String, ByVal keyhashBase As String) As String
    If keyhashBase <> "" Then
        Dim dayOfMonth As Long
        dayOfMonth = Day(Date)
        ntwebsrv_BuildAuthHeader = ntwebsrv_SHA256(keyhashBase & CStr(dayOfMonth))
    ElseIf key <> "" Then
        ntwebsrv_BuildAuthHeader = key
    Else
        ntwebsrv_BuildAuthHeader = ""
    End If
End Function

' Reads a text file (UTF-8)
Private Function ntwebsrv_ReadTextFile(ByVal filePath As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2 ' adTypeText
    stream.Charset = "UTF-8"
    stream.Open
    stream.LoadFromFile filePath
    ntwebsrv_ReadTextFile = stream.ReadText
    stream.Close
    Set stream = Nothing
End Function

' Parses JSON using Microsoft Script Control (fallback to simple parser)
Private Function ntwebsrv_ParseJson(ByVal jsonText As String) As Object
    Dim scriptControl As Object
    Dim result As Object
    
    On Error Resume Next
    Set scriptControl = CreateObject("MSScriptControl.ScriptControl")
    If Err.Number = 0 Then
        scriptControl.Language = "JScript"
        scriptControl.AddCode "function parse(json) { return JSON.parse(json); }"
        Set result = scriptControl.Run("parse", jsonText)
        Set ntwebsrv_ParseJson = ntwebsrv_JSObjectToDict(result)
        Exit Function
    End If
    On Error GoTo 0
    
    ' Fallback: simple parser for basic cases
    Set ntwebsrv_ParseJson = ntwebsrv_SimpleJsonParse(jsonText)
End Function

' Converts JScript object to Scripting.Dictionary
Private Function ntwebsrv_JSObjectToDict(ByVal jsObj As Object) As Object
    Dim dict As Object
    Dim key As Variant
    Dim value As Variant
    Dim item As Object
    
    Set dict = CreateObject("Scripting.Dictionary")
    
    For Each key In jsObj
        value = jsObj(key)
        If VarType(value) = vbObject Then
            If ntwebsrv_IsArray(value) Then
                Set item = ntwebsrv_JSArrayToArray(value)
            Else
                Set item = ntwebsrv_JSObjectToDict(value)
            End If
            dict.Add key, item
        Else
            dict.Add key, value
        End If
    Next key
    
    Set ntwebsrv_JSObjectToDict = dict
End Function

' Converts JScript array to VBA array
Private Function ntwebsrv_JSArrayToArray(ByVal jsArray As Object) As Variant
    Dim arr() As Variant
    Dim i As Long
    Dim length As Long
    
    length = jsArray.length
    ReDim arr(0 To length - 1)
    
    For i = 0 To length - 1
        If VarType(jsArray(i)) = vbObject Then
            If ntwebsrv_IsArray(jsArray(i)) Then
                arr(i) = ntwebsrv_JSArrayToArray(jsArray(i))
            Else
                Set arr(i) = ntwebsrv_JSObjectToDict(jsArray(i))
            End If
        Else
            arr(i) = jsArray(i)
        End If
    Next i
    
    ntwebsrv_JSArrayToArray = arr
End Function

' Simple JSON parser fallback (handles basic objects/arrays)
Private Function ntwebsrv_SimpleJsonParse(ByVal jsonText As String) As Object
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    
    Dim parametri As Object, files As Object, auth As Object
    Set parametri = CreateObject("Scripting.Dictionary")
    Set files = CreateObject("Scripting.Dictionary")
    Set auth = CreateObject("Scripting.Dictionary")
    
    Call ntwebsrv_ExtractJsonObject(jsonText, "parametri", parametri)
    Call ntwebsrv_ExtractJsonObject(jsonText, "files", files)
    Call ntwebsrv_ExtractJsonObject(jsonText, "auth", auth)
    
    dict.Add "parametri", parametri
    dict.Add "files", files
    dict.Add "auth", auth
    
    Set ntwebsrv_SimpleJsonParse = dict
End Function

' Extracts a JSON object by key into a Dictionary
Private Sub ntwebsrv_ExtractJsonObject(ByVal jsonText As String, ByVal keyName As String, ByRef targetDict As Object)
    Dim startPos As Long, endPos As Long
    Dim objText As String
    Dim i As Long
    Dim ch As String
    Dim inString As Boolean
    Dim escaped As Boolean
    Dim readingKey As Boolean
    Dim keyBuffer As String, valBuffer As String
    Dim currentKey As String, currentValue As String
    
    startPos = InStr(1, jsonText, """" & keyName & """", vbTextCompare)
    If startPos = 0 Then Exit Sub
    
    startPos = InStr(startPos, jsonText, "{")
    If startPos = 0 Then Exit Sub
    
    endPos = startPos
    inString = False
    escaped = False
    For i = startPos + 1 To Len(jsonText)
        ch = Mid(jsonText, i, 1)
        If escaped Then
            escaped = False
        ElseIf ch = "\" Then
            escaped = True
        ElseIf ch = """" Then
            inString = Not inString
        ElseIf Not inString Then
            If ch = "}" Then
                endPos = i
                Exit For
            End If
        End If
    Next i
    
    If endPos <= startPos Then Exit Sub
    
    objText = Mid(jsonText, startPos + 1, endPos - startPos - 1)
    
    inString = False
    escaped = False
    readingKey = True
    keyBuffer = ""
    valBuffer = ""
    
    For i = 1 To Len(objText)
        ch = Mid(objText, i, 1)
        If escaped Then
            If readingKey Then keyBuffer = keyBuffer & ch Else valBuffer = valBuffer & ch
            escaped = False
        ElseIf ch = "\" Then
            escaped = True
        ElseIf ch = """" Then
            inString = Not inString
        ElseIf Not inString And ch = ":" Then
            readingKey = False
        ElseIf Not inString And ch = "," Then
            currentKey = Trim(keyBuffer)
            currentValue = Trim(valBuffer)
            If Left(currentKey, 1) = """" Then currentKey = Mid(currentKey, 2, Len(currentKey) - 2)
            If Left(currentValue, 1) = """" Then currentValue = Mid(currentValue, 2, Len(currentValue) - 2)
            If currentKey <> "" Then targetDict.Add currentKey, currentValue
            keyBuffer = ""
            valBuffer = ""
            readingKey = True
        Else
            If readingKey Then keyBuffer = keyBuffer & ch Else valBuffer = valBuffer & ch
        End If
    Next i
    
    If keyBuffer <> "" Then
        currentKey = Trim(keyBuffer)
        currentValue = Trim(valBuffer)
        If Left(currentKey, 1) = """" Then currentKey = Mid(currentKey, 2, Len(currentKey) - 2)
        If Left(currentValue, 1) = """" Then currentValue = Mid(currentValue, 2, Len(currentValue) - 2)
        If currentKey <> "" Then targetDict.Add currentKey, currentValue
    End If
End Sub

' Gets a Dictionary from a Dictionary (by key)
Private Function ntwebsrv_GetDict(ByVal dict As Object, ByVal key As String) As Object
    On Error Resume Next
    Set ntwebsrv_GetDict = dict(key)
    On Error GoTo 0
End Function

' Gets a String from a nested path (e.g., "auth.key")
Private Function ntwebsrv_GetString(ByVal dict As Object, ByVal path As String, ByVal defaultValue As String) As String
    Dim parts() As String
    Dim current As Object
    Dim part As Variant
    Dim value As Variant
    
    parts = Split(path, ".")
    Set current = dict
    
    For Each part In parts
        If current Is Nothing Then
            ntwebsrv_GetString = defaultValue
            Exit Function
        End If
        On Error Resume Next
        value = current(part)
        On Error GoTo 0
        If VarType(value) = vbObject Then
            Set current = value
        Else
            If IsNull(value) Then
                ntwebsrv_GetString = defaultValue
            Else
                ntwebsrv_GetString = CStr(value)
            End If
            Exit Function
        End If
    Next part
    
    ntwebsrv_GetString = defaultValue
End Function

' Checks if object is a JScript array
Private Function ntwebsrv_IsArray(ByVal obj As Object) As Boolean
    On Error Resume Next
    ntwebsrv_IsArray = (TypeName(obj) = "JScriptTypeInfo" Or TypeName(obj) = "Array") Or _
                       (IsObject(obj) And Not IsError(obj.length))
    On Error GoTo 0
End Function

' Builds multipart/form-data body
Private Function ntwebsrv_BuildMultipartBody( _
    ByVal parametri As Object, _
    ByVal files As Object, _
    ByVal authKey As String, _
    ByVal authKh As String, _
    ByVal boundary As String _
) As Variant
    
    Dim stream As Object
    Dim fieldName As Variant
    Dim value As String
    Dim filePath As String
    Dim fileName As String
    Dim fileBytes() As Byte
    Dim fileNum As Long
    Dim header As String
    Dim boundaryBytes() As Byte
    Dim crlfBytes() As Byte
    Dim fso As Object
    
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 1 ' adTypeBinary
    stream.Open
    
    crlfBytes = StrConv(vbCrLf, vbFromUnicode)
    boundaryBytes = StrConv("--" & boundary & vbCrLf, vbFromUnicode)
    
    ' Add parametri fields
    If Not parametri Is Nothing Then
        For Each fieldName In parametri.Keys
            value = CStr(parametri(fieldName))
            header = "Content-Disposition: form-data; name=""" & fieldName & """" & vbCrLf & vbCrLf & value & vbCrLf
            stream.Write boundaryBytes
            stream.Write StrConv(header, vbFromUnicode)
        Next fieldName
    End If
    
    ' Add legacy auth as form fields
    If authKh <> "" Then
        header = "Content-Disposition: form-data; name=""_kh""" & vbCrLf & vbCrLf & authKh & vbCrLf
        stream.Write boundaryBytes
        stream.Write StrConv(header, vbFromUnicode)
    ElseIf authKey <> "" Then
        header = "Content-Disposition: form-data; name=""_k""" & vbCrLf & vbCrLf & authKey & vbCrLf
        stream.Write boundaryBytes
        stream.Write StrConv(header, vbFromUnicode)
    End If
    
    ' Add files
    If Not files Is Nothing Then
        Set fso = CreateObject("Scripting.FileSystemObject")
        For Each fieldName In files.Keys
            filePath = files(fieldName)
            fileName = fso.GetFileName(filePath)
            
            fileNum = FreeFile
            Open filePath For Binary Access Read As #fileNum
            ReDim fileBytes(0 To LOF(fileNum) - 1)
            Get #fileNum, , fileBytes
            Close #fileNum
            
            header = "Content-Disposition: form-data; name=""" & fieldName & """; filename=""" & fileName & """" & vbCrLf & _
                     "Content-Type: application/octet-stream" & vbCrLf & vbCrLf
            
            stream.Write boundaryBytes
            stream.Write StrConv(header, vbFromUnicode)
            stream.Write fileBytes
            stream.Write crlfBytes
        Next fieldName
    End If
    
    ' End boundary
    stream.Write StrConv("--" & boundary & "--" & vbCrLf, vbFromUnicode)
    
    stream.Position = 0
    ntwebsrv_BuildMultipartBody = stream.Read
    stream.Close
    Set stream = Nothing
    
End Function

' ============================================================================
' SHA256 IMPLEMENTATION (Windows CAPI via advapi32.dll)
' ============================================================================

Private Function ntwebsrv_SHA256(ByVal input As String) As String
    Dim cryptProv As Long
    Dim cryptHash As Long
    Dim dataBytes() As Byte
    Dim hashBytes() As Byte
    Dim hashLen As Long
    Dim result As String
    Dim i As Long
    Dim advapi32 As Long
    Dim cryptAcquireContext As Long
    Dim cryptCreateHash As Long
    Dim cryptHashData As Long
    Dim cryptGetHashParam As Long
    Dim cryptReleaseContext As Long
    Dim cryptDestroyHash As Long
    
    advapi32 = LoadLibrary("advapi32.dll")
    If advapi32 = 0 Then
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    cryptAcquireContext = GetProcAddress(advapi32, "CryptAcquireContextW")
    cryptCreateHash = GetProcAddress(advapi32, "CryptCreateHash")
    cryptHashData = GetProcAddress(advapi32, "CryptHashData")
    cryptGetHashParam = GetProcAddress(advapi32, "CryptGetHashParam")
    cryptReleaseContext = GetProcAddress(advapi32, "CryptReleaseContext")
    cryptDestroyHash = GetProcAddress(advapi32, "CryptDestroyHash")
    
    If cryptAcquireContext = 0 Or cryptCreateHash = 0 Or cryptHashData = 0 Or _
       cryptGetHashParam = 0 Or cryptReleaseContext = 0 Or cryptDestroyHash = 0 Then
        FreeLibrary advapi32
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    dataBytes = StrConv(input, vbFromUnicode)
    
    If CallFunction(cryptAcquireContext, cryptProv, 0, 0, 1, &HF0000000) = 0 Then
        If CallFunction(cryptAcquireContext, cryptProv, 0, 0, 1, 0) = 0 Then
            FreeLibrary advapi32
            ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
            Exit Function
        End If
    End If
    
    If CallFunction(cryptCreateHash, cryptProv, &H800C, 0, 0, cryptHash) = 0 Then
        CallFunction cryptReleaseContext, cryptProv, 0
        FreeLibrary advapi32
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    If CallFunction(cryptHashData, cryptHash, VarPtr(dataBytes(0)), UBound(dataBytes) + 1, 0) = 0 Then
        CallFunction cryptDestroyHash, cryptHash
        CallFunction cryptReleaseContext, cryptProv, 0
        FreeLibrary advapi32
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    hashLen = 0
    If CallFunction(cryptGetHashParam, cryptHash, 4, 0, hashLen, 4) = 0 Then
        CallFunction cryptDestroyHash, cryptHash
        CallFunction cryptReleaseContext, cryptProv, 0
        FreeLibrary advapi32
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    ReDim hashBytes(0 To hashLen - 1)
    If CallFunction(cryptGetHashParam, cryptHash, 2, VarPtr(hashBytes(0)), hashLen, 0) = 0 Then
        CallFunction cryptDestroyHash, cryptHash
        CallFunction cryptReleaseContext, cryptProv, 0
        FreeLibrary advapi32
        ntwebsrv_SHA256 = ntwebsrv_SHA256_CAPICOM(input)
        Exit Function
    End If
    
    CallFunction cryptDestroyHash, cryptHash
    CallFunction cryptReleaseContext, cryptProv, 0
    FreeLibrary advapi32
    
    result = ""
    For i = 0 To hashLen - 1
        result = result & Right("0" & Hex(hashBytes(i)), 2)
    Next i
    
    ntwebsrv_SHA256 = LCase(result)
    
End Function

Private Function ntwebsrv_SHA256_CAPICOM(ByVal input As String) As String
    On Error Resume Next
    Dim capicom As Object
    Set capicom = CreateObject("CAPICOM.HashedData")
    If Err.Number = 0 Then
        capicom.Algorithm = 4
        capicom.Hash StrConv(input, vbFromUnicode)
        ntwebsrv_SHA256_CAPICOM = LCase(capicom.Value)
        Exit Function
    End If
    On Error GoTo 0
    ntwebsrv_SHA256_CAPICOM = ""
End Function

' Windows API declarations
Private Declare PtrSafe Function LoadLibrary Lib "kernel32" Alias "LoadLibraryA" (ByVal lpLibFileName As String) As LongPtr
Private Declare PtrSafe Function FreeLibrary Lib "kernel32" (ByVal hLibModule As LongPtr) As Long
Private Declare PtrSafe Function GetProcAddress Lib "kernel32" (ByVal hModule As LongPtr, ByVal lpProcName As String) As LongPtr
Private Declare PtrSafe Function CallWindowProc Lib "user32" Alias "CallWindowProcA" (ByVal lpPrevWndFunc As LongPtr, ByVal hWnd As LongPtr, ByVal Msg As Long, ByVal wParam As LongPtr, ByVal lParam As LongPtr) As LongPtr

Private Function CallFunction(ByVal funcPtr As LongPtr, ParamArray args()) As Long
    Dim result As LongPtr
    result = CallWindowProc(funcPtr, 0, 0, ByVal args(0), ByVal args(1))
    CallFunction = CLng(result)
End Function

#If VBA7 Then
    Private Declare PtrSafe Function VarPtrArray Lib "msvbvm60" Alias "VarPtr" (ByRef ptr As Any) As LongPtr
    Private Function VarPtr(arr As Byte) As LongPtr
        VarPtr = VarPtrArray(arr(0))
    End Function
#Else
    Private Declare Function VarPtr Lib "msvbvm60" Alias "VarPtr" (ByRef ptr As Any) As Long
#End If

' ============================================================================
' TEST HELPER
' ============================================================================
' Sub TestNtwebsrv()
'     Dim ok As Boolean
'     ' Legacy upload
'     ok = ntwebsrv_SendJson("C:\path\upload.json", "http://localhost:8000", "MySecretKey")
'     ' Command
'     ok = ntwebsrv_SendCommand("C:\path\cmd_exit.json", "http://localhost:8000", , "my_base_secret")
'     ' Download
'     ok = ntwebsrv_Download("report.pdf", "http://localhost:8000", "C:\downloads\report.pdf", False, , "my_base_secret")
'     ok = ntwebsrv_Download("logs", "http://localhost:8000", "C:\downloads\logs.zip", True, , "my_base_secret")
' End Sub