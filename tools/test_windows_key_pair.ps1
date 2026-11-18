#Requires -Version 5.1
# Isolated non-operational fixtures only. Never runs the bootstrap main block.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Windows PowerShell 5.1 is required.'
}
$SetupPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'setup\Connect-APTREDLIGHT.ps1'
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile($SetupPath, [ref]$Tokens, [ref]$ParseErrors)
if (@($ParseErrors).Count -ne 0) { throw 'Setup syntax failed.' }
foreach ($FunctionName in @('Get-PublicKeyIdentity', 'Get-DerivedPublicKeyIdentity')) {
    $Functions = @($Ast.FindAll({
        param($Node)
        $Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -ceq $FunctionName
    }, $true))
    if ($Functions.Count -ne 1) { throw 'Expected exactly one public-key helper.' }
    . ([ScriptBlock]::Create($Functions[0].Extent.Text))
}

$Header = [byte[]]@(0, 0, 0, 11, 115, 115, 104, 45, 101, 100, 50, 53, 53, 49, 57, 0, 0, 0, 32)
$Wire = New-Object byte[] 51
[Array]::Copy($Header, $Wire, $Header.Length)
for ($Index = 19; $Index -lt 51; $Index++) { $Wire[$Index] = 1 }
$Blob = [Convert]::ToBase64String($Wire)
$Canonical = 'ssh-ed25519 ' + $Blob
foreach ($Record in @($Canonical, ($Canonical + ' label with spaces'), ("`t" + $Canonical + " trailing label`r`n"))) {
    if ((Get-PublicKeyIdentity -Text $Record) -cne $Canonical) { throw 'A valid comment or whitespace changed key identity.' }
}
$Wire[50] = 2
$Different = 'ssh-ed25519 ' + [Convert]::ToBase64String($Wire)
if ((Get-PublicKeyIdentity -Text $Different) -ceq $Canonical) { throw 'Different public-key data was accepted as equal.' }
$Invalid = @('', ('ssh-rsa ' + $Blob), 'ssh-ed25519 not-base64',
    ('ssh-ed25519 ' + [Convert]::ToBase64String([byte[]]@(1, 2, 3))),
    ($Canonical + "`n" + $Canonical))
foreach ($Record in $Invalid) {
    $Rejected = $false
    try { Get-PublicKeyIdentity -Text $Record | Out-Null } catch { $Rejected = $true }
    if (-not $Rejected) { throw 'Malformed or multiple public-key records were accepted.' }
}

function Invoke-FixtureKeygen([string]$Executable, [string]$Arguments) {
    $Info = New-Object Diagnostics.ProcessStartInfo
    $Info.FileName = $Executable
    $Info.Arguments = $Arguments
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.RedirectStandardInput = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $Process = [Diagnostics.Process]::Start($Info)
    try {
        $Process.StandardInput.Close()
        $Output = $Process.StandardOutput.ReadToEndAsync()
        $ErrorOutput = $Process.StandardError.ReadToEndAsync()
        if (-not $Process.WaitForExit(15000)) {
            try { $Process.Kill() } catch { }
            throw 'Fixture ssh-keygen timed out.'
        }
        $Text = $Output.Result
        $UnusedError = $ErrorOutput.Result
        if ($Process.ExitCode -ne 0) { throw 'Fixture ssh-keygen failed.' }
        return $Text
    } finally { $Process.Dispose() }
}

$FixtureDirectory = $null
try {
    $Keygen = (Get-Command ssh-keygen.exe -ErrorAction Stop).Source
    $FixtureDirectory = Join-Path ([IO.Path]::GetTempPath()) ('apt key fixture ' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $FixtureDirectory | Out-Null
    $FixtureKey = Join-Path $FixtureDirectory 'temporary non operational key'
    Invoke-FixtureKeygen -Executable $Keygen -Arguments ('-q -t ed25519 -N "" -C "one-time fixture comment with spaces" -f "' + $FixtureKey + '"') | Out-Null
    $PublicText = [IO.File]::ReadAllText($FixtureKey + '.pub')
    $Expected = Get-PublicKeyIdentity -Text $PublicText
    $Derived = Get-DerivedPublicKeyIdentity -KeygenPath $Keygen -Path $FixtureKey
    if ($Derived -cne $Expected) { throw 'Windows OpenSSH fixture key identity did not match.' }
    $Raw = Invoke-FixtureKeygen -Executable $Keygen -Arguments ('-y -P "" -f "' + $FixtureKey + '"')
    $FieldCount = @($Raw.Trim() -split '\s+').Count
    if ((Get-PublicKeyIdentity -Text ($Raw.Trim() + ' another comment')) -cne $Expected) {
        throw 'A Windows exported public-key comment caused a false mismatch.'
    }
    Write-Host ('Windows OpenSSH exported public-key field count: ' + $FieldCount)
    Write-Host 'PASS: actual Windows OpenSSH key matching, comments, empty passphrase, space-containing path, and malformed public-record rejection.'
    Write-Host 'Only one temporary non-operational fixture key pair was generated; no real key, account, network, or bootstrap main flow was used.'
} finally {
    if ($null -ne $FixtureDirectory -and (Test-Path -LiteralPath $FixtureDirectory)) {
        Remove-Item -LiteralPath $FixtureDirectory -Recurse -Force
    }
}
