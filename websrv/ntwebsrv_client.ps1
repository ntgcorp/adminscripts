<#
.SYNOPSIS
    ntwebsrv_client.ps1 - PowerShell client for ntwebsrv (Automation Agent)

.DESCRIPTION
    Sends API calls to ntwebsrv with support for:
    - Legacy multipart upload (POST /ricevi)
    - JSON RPC commands (POST /api/command): save, exit, restart, reboot, poweroff, exec
    - File/folder download (GET /api/download/{target}?zip_mode=true)

.PARAMETER JsonFile
    Path to JSON file with request data (required for upload/commands).

.PARAMETER BaseUrl
    Base server URL (default: http://localhost:8000).

.PARAMETER Key
    Secret key for _k authentication (X-API-Key header).

.PARAMETER KeyHash
    Base secret for _kh calculation (SHA256(base + day_of_month)).

.PARAMETER Timeout
    Request timeout in seconds (default: 30).

.PARAMETER Verbose
    Show detailed output.

.PARAMETER Download
    Target file/folder to download (no JsonFile required).

.PARAMETER Zip
    Zip folder on-the-fly (requires -Download).

.PARAMETER OutputFile
    Output filename for download (default: from server).

.EXAMPLE
    # Legacy upload
    .\ntwebsrv_client.ps1 -JsonFile "upload.json" -Key "my_secret_key" -Verbose

.EXAMPLE
    # JSON RPC command
    .\ntwebsrv_client.ps1 -JsonFile "cmd_exit.json" -KeyHash "my_base_secret"

.EXAMPLE
    # Download file
    .\ntwebsrv_client.ps1 -Download "report.pdf" -Key "my_secret_key"

.EXAMPLE
    # Download folder as zip
    .\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "my_secret_key"

.NOTES
    JSON formats:
    
    Legacy upload:
    {
      "parametri": { "field1": "value1" },
      "files": { "document": "C:\path\file.pdf" },
      "auth": { "key": "secret", "keyhash": "base_secret" }
    }
    
    Commands (JSON RPC):
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "script_name"}
    
    auth.keyhash is the BASE secret (not precalculated hash). Client calculates _kh = SHA256(keyhash + day).
    CLI parameters -Key/-KeyHash override JSON auth section.
#>

[CmdletBinding(DefaultParameterSetName="Upload")]
param(
    [Parameter(ParameterSetName="Upload", Mandatory=$true, Position=0)]
    [Parameter(ParameterSetName="Command", Mandatory=$true, Position=0)]
    [string]$JsonFile,

    [Parameter()]
    [string]$BaseUrl = "http://localhost:8000",

    [Parameter()]
    [string]$Key = "",

    [Parameter()]
    [string]$KeyHash = "",

    [Parameter()]
    [int]$Timeout = 30,

    [Parameter()]
    [switch]$Verbose,

    # Download parameters
    [Parameter(ParameterSetName="Download", Mandatory=$true)]
    [string]$Download,

    [Parameter(ParameterSetName="Download")]
    [switch]$Zip,

    [Parameter(ParameterSetName="Download")]
    [string]$OutputFile = ""
)

# Detect system language
$sysLang = (Get-Culture).Name
$isItalian = $sysLang -like "it-*"

function Write-Localized {
    param([string]$It, [string]$En)
    if ($isItalian) { Write-Host $It } else { Write-Host $En }
}

function Show-Help {
    if ($isItalian) {
        @"
ntwebsrv_client.ps1 - Client PowerShell per ntwebsrv (Automation Agent)

USO:
    .\ntwebsrv_client.ps1 -JsonFile FILE_JSON [opzioni]      # Upload legacy o Comandi
    .\ntwebsrv_client.ps1 -Download TARGET [opzioni]         # Download file/cartella

PARAMETRI COMUNI:
    -BaseUrl      URL base server (default: http://localhost:8000)
    -Key          Chiave segreta (header X-API-Key)
    -KeyHash      Segreto base per _kh (calcola SHA256(base + giorno))
    -Timeout      Timeout secondi (default: 30)
    -Verbose      Output dettagliato

PARAMETRI DOWNLOAD:
    -Download     File/cartella da scaricare (non richiede -JsonFile)
    -Zip          Zippa cartella al volo (richiede -Download)
    -OutputFile   Nome file output (default: dal server)

MODALITÀ 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON con "parametri" e/o "files":
    {
      "parametri": { "campo1": "valore1" },
      "files": { "documento": "C:\\percorso\\file.pdf" },
      "auth": { "key": "chiave", "keyhash": "base_secret" }
    }

MODALITÀ 2: COMANDI (JSON RPC) - POST /api/command
    JSON con "comando":
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "nome_script"}

MODALITÀ 3: DOWNLOAD - GET /api/download/{target}
    .\ntwebsrv_client.ps1 -Download "report.pdf" -Key "chiave"
    .\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "chiave"

AUTENTICAZIONE:
    - Header X-API-Key: <key|kh>  (o Authorization: Bearer <key|kh>)
    - "auth.keyhash" nel JSON è il segreto base (NON l'hash). Client calcola _kh = SHA256(keyhash + giorno_corrente)
    - -Key/-KeyHash sovrascrivono "auth" nel JSON

ESEMPI:
    # Legacy upload
    .\ntwebsrv_client.ps1 -JsonFile upload.json -Key "mia_chiave" -Verbose
    
    # Comandi
    .\ntwebsrv_client.ps1 -JsonFile cmd_save.json -Key "mia_chiave" -Verbose
    .\ntwebsrv_client.ps1 -JsonFile cmd_exit.json -KeyHash "mio_base_secret"
    
    # Download
    .\ntwebsrv_client.ps1 -Download "report.pdf" -Key "mia_chiave"
    .\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "mia_chiave"
"@
    } else {
        @"
ntwebsrv_client.ps1 - PowerShell client for ntwebsrv (Automation Agent)

USAGE:
    .\ntwebsrv_client.ps1 -JsonFile JSON_FILE [options]      # Legacy upload or Commands
    .\ntwebsrv_client.ps1 -Download TARGET [options]         # Download file/folder

COMMON PARAMETERS:
    -BaseUrl      Base server URL (default: http://localhost:8000)
    -Key          Secret key (X-API-Key header)
    -KeyHash      Base secret for _kh (calculates SHA256(base + day))
    -Timeout      Timeout seconds (default: 30)
    -Verbose      Verbose output

DOWNLOAD PARAMETERS:
    -Download     File/folder to download (no -JsonFile required)
    -Zip          Zip folder on-the-fly (requires -Download)
    -OutputFile   Output filename (default: from server)

MODE 1: LEGACY UPLOAD (multipart) - POST /ricevi
    JSON with "parametri" and/or "files":
    {
      "parametri": { "field1": "value1" },
      "files": { "document": "C:\path\file.pdf" },
      "auth": { "key": "secret", "keyhash": "base_secret" }
    }

MODE 2: COMMANDS (JSON RPC) - POST /api/command
    JSON with "comando":
    {"comando": "save", "payload": {...}}
    {"comando": "exit"}
    {"comando": "restart"}
    {"comando": "reboot"}
    {"comando": "poweroff"}
    {"comando": "exec", "target": "script_name"}

MODE 3: DOWNLOAD - GET /api/download/{target}
    .\ntwebsrv_client.ps1 -Download "report.pdf" -Key "secret"
    .\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "secret"

AUTHENTICATION:
    - Header X-API-Key: <key|kh>  (or Authorization: Bearer <key|kh>)
    - "auth.keyhash" in JSON is base secret (NOT hash). Client calculates _kh = SHA256(keyhash + day)
    - -Key/-KeyHash override JSON "auth"

EXAMPLES:
    # Legacy upload
    .\ntwebsrv_client.ps1 -JsonFile upload.json -Key "my_key" -Verbose
    
    # Commands
    .\ntwebsrv_client.ps1 -JsonFile cmd_save.json -Key "my_key" -Verbose
    .\ntwebsrv_client.ps1 -JsonFile cmd_exit.json -KeyHash "my_base_secret"
    
    # Download
    .\ntwebsrv_client.ps1 -Download "report.pdf" -Key "my_key"
    .\ntwebsrv_client.ps1 -Download "logs" -Zip -Key "my_key"
"@
    }
    exit 0
}

# Show help if requested
if ($JsonFile -eq "-h" -or $JsonFile -eq "-help" -or $JsonFile -eq "--help" -or $Download -eq "-h") {
    Show-Help
}

# Calculate _kh from base secret
function Calc-Kh {
    param([string]$BaseSecret)
    $day = (Get-Date).Day
    $input = $BaseSecret + $day
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($input)
    $hashBytes = $sha256.ComputeHash($bytes)
    return ($hashBytes | ForEach-Object { "{0:x2}" -f $_ }) -join ""
}

# Build auth header
function Get-AuthHeader {
    param([string]$Key, [string]$KeyHashBase)
    if ($KeyHashBase) {
        return @{ "X-API-Key" = (Calc-Kh $KeyHashBase) }
    } elseif ($Key) {
        return @{ "X-API-Key" = $Key }
    }
    return @{}
}

# DOWNLOAD MODE
if ($PSCmdlet.ParameterSetName -eq "Download") {
    $downloadUrl = "$($BaseUrl.TrimEnd('/'))/api/download/$Download"
    if ($Zip) { $downloadUrl += "?zip_mode=true" }
    
    $headers = Get-AuthHeader $Key $KeyHash
    if ($Verbose) { Write-Localized -It "[INFO] Download da $downloadUrl" -En "[INFO] Downloading from $downloadUrl" }
    
    try {
        $response = Invoke-WebRequest -Uri $downloadUrl -Method Get -Headers $headers -TimeoutSec $Timeout -ErrorAction Stop
        if ($Verbose) { Write-Localized -It "[INFO] Status: $($response.StatusCode)" -En "[INFO] Status: $($response.StatusCode)" }
        
        $outFile = $OutputFile
        if (-not $outFile) {
            $cd = $response.Headers["Content-Disposition"]
            if ($cd -and $cd -match 'filename="?([^"]+)"?') {
                $outFile = $Matches[1]
            } else {
                $outFile = "download_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
            }
        }
        
        [System.IO.File]::WriteAllBytes($outFile, $response.Content)
        Write-Localized -It "SUCCESSO: Scaricato come $outFile" -En "SUCCESS: Downloaded as $outFile"
        exit 0
    } catch {
        $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
        $errorBody = if ($_.Exception.Response) { 
            $_.Exception.Response.GetResponseStream() | ForEach-Object { (New-Object System.IO.StreamReader($_)).ReadToEnd() } 
        } else { $_.Exception.Message }
        
        Write-Localized -It "FALLITO (HTTP $statusCode): $errorBody" -En "FAILED (HTTP $statusCode): $errorBody"
        exit 1
    }
}

# UPLOAD/COMMAND MODE - requires JsonFile
if (-not (Test-Path -Path $JsonFile -PathType Leaf)) {
    Write-Error (Write-Localized -It "ERRORE: File JSON non trovato: $JsonFile" -En "ERROR: JSON file not found: $JsonFile")
    exit 1
}

# Read and parse JSON
try {
    $jsonContent = Get-Content -Path $JsonFile -Raw -Encoding UTF8
    $data = $jsonContent | ConvertFrom-Json
} catch {
    Write-Error (Write-Localized -It "ERRORE: JSON non valido: $_" -En "ERROR: Invalid JSON: $_")
    exit 1
}

# Check if it's a command (has "comando" property)
$isCommandMode = $data.PSObject.Properties.Match('comando')

# Build auth header (CLI overrides JSON)
$authHeader = Get-AuthHeader $Key $KeyHash
if ($authHeader.Count -eq 0) {
    # Try from JSON
    $jsonKey = if ($data.auth -and $data.auth.key) { $data.auth.key } else { "" }
    $jsonKhBase = if ($data.auth -and $data.auth.keyhash) { $data.auth.keyhash } else { "" }
    $authHeader = Get-AuthHeader $jsonKey $jsonKhBase
}

if ($Verbose) { Write-Localized -It "[INFO] Autenticazione: $($authHeader.Keys -join ', ')" -En "[INFO] Auth: $($authHeader.Keys -join ', ')" }

if ($isCommandMode) {
    # COMMAND MODE: POST /api/command with JSON
    $commandUrl = "$($BaseUrl.TrimEnd('/'))/api/command"
    if ($Verbose) { Write-Localized -It "[INFO] Comando a $commandUrl: $($data.comando)" -En "[INFO] Command to $commandUrl: $($data.comando)" }
    
    try {
        $response = Invoke-RestMethod -Uri $commandUrl -Method Post -Headers $authHeader -Body ($jsonContent) -ContentType "application/json" -TimeoutSec $Timeout -ErrorAction Stop
        Write-Localized -It "SUCCESSO" -En "SUCCESS"
        $response | ConvertTo-Json -Depth 5
        exit 0
    } catch {
        $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
        $errorBody = if ($_.Exception.Response) { 
            $_.Exception.Response.GetResponseStream() | ForEach-Object { (New-Object System.IO.StreamReader($_)).ReadToEnd() } 
        } else { $_.Exception.Message }
        
        Write-Localized -It "FALLITO (HTTP $statusCode): $errorBody" -En "FAILED (HTTP $statusCode): $errorBody"
        exit 1
    }
} else {
    # LEGACY MODE: POST /ricevi multipart
    $uploadUrl = "$($BaseUrl.TrimEnd('/'))/ricevi"
    
    $parametri = if ($data.parametri) { $data.parametri } else { @{} }
    $files = if ($data.files) { $data.files } else { @{} }
    $authKey = if ($data.auth -and $data.auth.key) { $data.auth.key } else { "" }
    $authKhBase = if ($data.auth -and $data.auth.keyhash) { $data.auth.keyhash } else { "" }
    
    # CLI overrides
    if ($Key) { $authKey = $Key }
    if ($KeyHash) { $authKhBase = $KeyHash }
    
    # Calculate _kh for legacy form field
    $legacyKh = ""
    if ($authKhBase) {
        $legacyKh = Calc-Kh $authKhBase
        if ($Verbose) { Write-Localized -It "[INFO] Calcolato _kh legacy da keyhash + giorno" -En "[INFO] Calculated legacy _kh from keyhash + day" }
    }
    
    # Verify files exist
    $missingFiles = @()
    $fileParams = @()
    
    foreach ($field in $files.Keys) {
        $path = $files[$field]
        $fullPath = Resolve-Path -Path $path -ErrorAction SilentlyContinue
        if ($fullPath) {
            $fileParams += @{
                Name = $field
                Path = $fullPath.Path
            }
            if ($Verbose) { Write-Localized -It "[INFO] File verificato: $field -> $($fullPath.Path)" -En "[INFO] File verified: $field -> $($fullPath.Path)" }
        } else {
            $missingFiles += "$field: $path"
        }
    }
    
    if ($missingFiles.Count -gt 0) {
        Write-Error (Write-Localized -It "ERRORE: File mancanti:" -En "ERROR: Missing files:")
        $missingFiles | ForEach-Object { Write-Error "  - $_" }
        exit 1
    }
    
    # Build form fields
    $formFields = @{}
    foreach ($key in $parametri.Keys) {
        $formFields[$key] = $parametri[$key]
    }
    if ($legacyKh) {
        $formFields["_kh"] = $legacyKh
    } elseif ($authKey) {
        $formFields["_k"] = $authKey
    }
    
    if ($formFields.Count -eq 0 -and $fileParams.Count -eq 0) {
        Write-Error (Write-Localized -It "ERRORE: Nessun parametro o file da inviare" -En "ERROR: No parameters or files to send")
        exit 1
    }
    
    # Prepare multipart form data
    $boundary = "----ntwebsrvBoundary$(Get-Random)"
    $contentType = "multipart/form-data; boundary=$boundary"
    $body = [System.Text.StringBuilder]::new()
    
    foreach ($key in $formFields.Keys) {
        $value = $formFields[$key]
        [void]$body.AppendLine("--$boundary")
        [void]$body.AppendLine("Content-Disposition: form-data; name=`"$key`"")
        [void]$body.AppendLine("")
        [void]$body.AppendLine("$value")
    }
    
    foreach ($file in $fileParams) {
        $fileName = Split-Path -Path $file.Path -Leaf
        $fileBytes = [System.IO.File]::ReadAllBytes($file.Path)
        $fileContent = [System.Convert]::ToBase64String($fileBytes)
        
        [void]$body.AppendLine("--$boundary")
        [void]$body.AppendLine("Content-Disposition: form-data; name=`"$($file.Name)`"; filename=`"$fileName`"")
        [void]$body.AppendLine("Content-Type: application/octet-stream")
        [void]$body.AppendLine("Content-Transfer-Encoding: base64")
        [void]$body.AppendLine("")
        [void]$body.AppendLine($fileContent)
    }
    
    [void]$body.AppendLine("--$boundary--")
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body.ToString())
    
    if ($Verbose) {
        Write-Localized -It "[INFO] Upload a $uploadUrl" -En "[INFO] Uploading to $uploadUrl"
        Write-Localized -It "[INFO] Campi form: $($formFields.Count), File: $($fileParams.Count)" -En "[INFO] Form fields: $($formFields.Count), Files: $($fileParams.Count)"
    }
    
    # Send request
    try {
        $response = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $authHeader -ContentType $contentType -Body $bodyBytes -TimeoutSec $Timeout -ErrorAction Stop
        Write-Localized -It "SUCCESSO" -En "SUCCESS"
        $response | ConvertTo-Json -Depth 5
        exit 0
    } catch {
        $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
        $errorBody = if ($_.Exception.Response) { 
            $_.Exception.Response.GetResponseStream() | ForEach-Object { (New-Object System.IO.StreamReader($_)).ReadToEnd() } 
        } else { $_.Exception.Message }
        
        Write-Localized -It "FALLITO (HTTP $statusCode): $errorBody" -En "FAILED (HTTP $statusCode): $errorBody"
        exit 1
    }
}