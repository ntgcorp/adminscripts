<#
.SYNOPSIS
    Scarica e scompatta SeleniumBasic e ChromeDriver nella cartella specificata.
.DESCRIPTION
    Scarica la versione indicata di ChromeDriver ed estrae i file di supporto
    (Selenium.dll, Selenium.pdb, Selenium32.tlb, Selenium64.tlb) nella cartella target.
.PARAMETER TargetDir
    Cartella di destinazione (es. C:\seleniumbasic)
.PARAMETER ChromeDriverVersion
    Versione di ChromeDriver (es. 146 oppure 146.0.7100.0)
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$TargetDir,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$ChromeDriverVersion
)

# Abilita TLS 1.2 per connessioni HTTPS sicure
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== Avvio preparazione SeleniumBasic e ChromeDriver ===" -ForegroundColor Cyan
Write-Host "Cartella target     : $TargetDir" -ForegroundColor Yellow
Write-Host "Versione richiesta  : $ChromeDriverVersion" -ForegroundColor Yellow

# 1. Verifica e creazione della cartella target
if (-not (Test-Path -Path $TargetDir)) {
    Write-Host "Creazione cartella di destinazione: $TargetDir" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# Lista completa dei 5 file da verificare alla fine
$requiredFiles = @(
    "chromedriver.exe",
    "Selenium.dll",
    "Selenium.pdb",
    "Selenium32.tlb",
    "Selenium64.tlb"
)

# 2. Estrazione componenti SeleniumBasic se mancanti
$dllPath = Join-Path -Path $TargetDir -ChildPath "Selenium.dll"
if (-not (Test-Path -Path $dllPath)) {
    Write-Host "Librerie Selenium non trovate in $TargetDir. Scompattamento in corso..." -ForegroundColor Yellow
    $sbUrl = "https://github.com/florentbr/SeleniumBasic/releases/download/v2.0.9.0/SeleniumBasic-2.0.9.0.exe"
    $sbInstaller = Join-Path -Path $env:TEMP -ChildPath "SeleniumBasic-2.0.9.0.exe"
    
    try {
        Invoke-WebRequest -Uri $sbUrl -OutFile $sbInstaller -UseBasicParsing
        Write-Host "Estrazione diretta dei file nella cartella $TargetDir..." -ForegroundColor Cyan
        
        # /VERYSILENT /DIR estrae i file DLL/TLB/PDB direttamente nella cartella senza setup visivo
        $argList = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$TargetDir")
        $proc = Start-Process -FilePath $sbInstaller -ArgumentList $argList -Wait -PassThru
        
        if ($proc.ExitCode -eq 0) {
            Write-Host "File Selenium estratti correttamente." -ForegroundColor Green
        } else {
            Write-Host "Estrazione completata con codice: $($proc.ExitCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Errore durante il download/estrazione di SeleniumBasic: $_" -ForegroundColor Red
    } finally {
        if (Test-Path -Path $sbInstaller) {
            Remove-Item -Path $sbInstaller -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "Librerie Selenium gia' presenti in $TargetDir." -ForegroundColor Green
}

# 3. Determinazione versione completa ChromeDriver
$fullVersion = $ChromeDriverVersion
if ($ChromeDriverVersion -notmatch '\.') {
    Write-Host "Ricerca release LATEST per il ramo $ChromeDriverVersion..." -ForegroundColor Cyan
    try {
        $cftUrl = "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${ChromeDriverVersion}"
        $fullVersion = (Invoke-RestMethod -Uri $cftUrl -ErrorAction Stop).Trim()
    } catch {
        try {
            $oldUrl = "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${ChromeDriverVersion}"
            $fullVersion = (Invoke-RestMethod -Uri $oldUrl -ErrorAction Stop).Trim()
        } catch {
            Write-Host "Impossibile recuperare versione esatta via API. Tentativo con: $ChromeDriverVersion" -ForegroundColor Yellow
        }
    }
}

Write-Host "Versione ChromeDriver identificata: $fullVersion" -ForegroundColor Green

# 4. Download ed estrazione ZIP di ChromeDriver
$zipPath = Join-Path -Path $env:TEMP -ChildPath "chromedriver_download.zip"
$extractPath = Join-Path -Path $env:TEMP -ChildPath "chromedriver_extracted"

if (Test-Path -Path $extractPath) {
    Remove-Item -Path $extractPath -Recurse -Force -ErrorAction SilentlyContinue
}

$downloadUrls = @(
    "https://storage.googleapis.com/chrome-for-testing-public/$fullVersion/win32/chromedriver-win32.zip",
    "https://storage.googleapis.com/chrome-for-testing-public/$fullVersion/win64/chromedriver-win64.zip",
    "https://chromedriver.storage.googleapis.com/$fullVersion/chromedriver_win32.zip"
)

$downloadSuccess = $false
foreach ($url in $downloadUrls) {
    try {
        Write-Host "Tentativo download ChromeDriver da: $url" -ForegroundColor Cyan
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -ErrorAction Stop
        $downloadSuccess = $true
        break
    } catch {
        # Prova l'URL successivo
    }
}

if (-not $downloadSuccess) {
    Write-Host "ERRORE: Impossibile scaricare ChromeDriver per la versione $fullVersion." -ForegroundColor Red
} else {
    try {
        Write-Host "Scompattamento ZIP di ChromeDriver..." -ForegroundColor Cyan
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
        
        $chromeDriverFile = Get-ChildItem -Path $extractPath -Filter "chromedriver.exe" -Recurse | Select-Object -First 1
        
        if ($chromeDriverFile) {
            $destinationDriver = Join-Path -Path $TargetDir -ChildPath "chromedriver.exe"
            Copy-Item -Path $chromeDriverFile.FullName -Destination $destinationDriver -Force
            Write-Host "chromedriver.exe copiato con successo in: $destinationDriver" -ForegroundColor Green
        } else {
            Write-Host "ERRORE: chromedriver.exe non trovato nell'archivio ZIP." -ForegroundColor Red
        }
    } catch {
        Write-Host "Errore durante lo scompattamento di ChromeDriver: $_" -ForegroundColor Red
    } finally {
        if (Test-Path -Path $zipPath) {
            Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -Path $extractPath) {
            Remove-Item -Path $extractPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# 5. Verifica rigorosa dei 5 file richiesti
$missingFiles = @()

foreach ($file in $requiredFiles) {
    $filePath = Join-Path -Path $TargetDir -ChildPath $file
    if (-not (Test-Path -Path $filePath)) {
        $missingFiles += $file
    }
}

Write-Host "----------------------------------------" -ForegroundColor Gray
if ($missingFiles.Count -eq 0) {
    Write-Host "COMPLETATO: Tutti i file richiesti sono presenti in ${TargetDir}:" -ForegroundColor Green
    foreach ($file in $requiredFiles) {
        Write-Host "  [OK] $file" -ForegroundColor Green
    }
} else {
    Write-Host "ATTENZIONE: Mancano alcuni file in ${TargetDir}:" -ForegroundColor Yellow
    foreach ($file in $missingFiles) {
        Write-Host "  [MANCANTE] $file" -ForegroundColor Red
    }
}
Write-Host "----------------------------------------" -ForegroundColor Gray