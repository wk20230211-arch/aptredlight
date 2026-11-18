#Requires -Version 5.1
# Run on the website administrator's Windows computer. No private key is sent to chat.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$TargetHost = '45.87.81.210'
$TargetPort = 65002
$TargetUser = 'u469397229'
$ExpectedFingerprint = 'SHA256:4mfb2c67Lhi/idZu+pyYocKONELisV4IInwlFdR8t98'
$Repository = 'wk20230211-arch/aptredlight'
$PrivateText = $null
$ClipboardContainsKey = $false

function Assert-RegularPath([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $Item = Get-Item -LiteralPath $Path -Force
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'A setup path is a link. Stop and ask your administrator to verify it.'
        }
    }
}

function Protect-PrivateKey([string]$Path) {
    $Sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $PrivateFile = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($PrivateFile -isnot [IO.FileInfo] -or ($PrivateFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The dedicated key must be a regular local file.'
    }
    # Read owner and DACL only. Audit/SACL access requires SeSecurityPrivilege.
    # Retain the existing owner and persist only modified access rules through .NET.
    $Sections = [Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner
    $Acl = $PrivateFile.GetAccessControl($Sections)
    if ($Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $Sid.Value) {
        throw 'The dedicated key is owned by a different account. Ask the device administrator to verify it.'
    }
    $Acl.SetAccessRuleProtection($true, $false)
    foreach ($ExistingRule in @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))) {
        $Acl.RemoveAccessRuleSpecific($ExistingRule)
    }
    $Rule = New-Object Security.AccessControl.FileSystemAccessRule -ArgumentList $Sid, 'FullControl', 'Allow'
    $Acl.AddAccessRule($Rule)
    $PrivateFile.SetAccessControl($Acl)

    $CheckedAcl = $PrivateFile.GetAccessControl($Sections)
    $CheckedRules = @($CheckedAcl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($CheckedAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $Sid.Value -or
        -not $CheckedAcl.AreAccessRulesProtected -or $CheckedRules.Count -ne 1 -or
        $CheckedRules[0].IdentityReference.Value -cne $Sid.Value -or
        $CheckedRules[0].AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
        ($CheckedRules[0].FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne [Security.AccessControl.FileSystemRights]::FullControl) {
        throw 'The dedicated key permissions could not be confirmed. No private key was uploaded.'
    }
}


function Get-PublicKeyIdentity([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text) -or $Text.Length -gt 4096) {
        throw 'A single public key record is required.'
    }
    $Record = $Text.Trim()
    if ($Record.Contains("`r") -or $Record.Contains("`n") -or $Record.Contains([char]0)) {
        throw 'The public key must contain exactly one record.'
    }
    $Columns = $Record -split '\s+'
    if ($Columns.Count -lt 2 -or $Columns[0] -cne 'ssh-ed25519') {
        throw 'The dedicated public key must use ssh-ed25519.'
    }
    try { $Blob = [Convert]::FromBase64String($Columns[1]) }
    catch { throw 'Invalid dedicated public key encoding.' }
    $Prefix = [byte[]]@(0, 0, 0, 11, 115, 115, 104, 45, 101, 100, 50, 53, 53, 49, 57, 0, 0, 0, 32)
    if ($Blob.Length -ne 51 -or [Convert]::ToBase64String($Blob) -cne $Columns[1]) {
        throw 'Invalid dedicated public key wire data.'
    }
    for ($Index = 0; $Index -lt $Prefix.Length; $Index++) {
        if ($Blob[$Index] -ne $Prefix[$Index]) { throw 'Invalid dedicated public key wire data.' }
    }
    # Comments are labels, not part of the SSH public-key identity.
    return 'ssh-ed25519 ' + $Columns[1]
}

function Get-DerivedPublicKeyIdentity([string]$KeygenPath, [string]$Path) {
    if ($Path.Contains('"')) { throw 'Unsupported local key path.' }
    $Info = New-Object Diagnostics.ProcessStartInfo
    $Info.FileName = $KeygenPath
    # Keep an explicit empty passphrase even in Windows PowerShell 5.1.
    $Info.Arguments = '-y -P "" -f "' + $Path + '"'
    $Info.UseShellExecute = $false
    $Info.RedirectStandardInput = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $Info.CreateNoWindow = $true
    $Process = [Diagnostics.Process]::Start($Info)
    try {
        $Process.StandardInput.Close()
        $OutputTask = $Process.StandardOutput.ReadToEndAsync()
        $ErrorTask = $Process.StandardError.ReadToEndAsync()
        if (-not $Process.WaitForExit(15000)) {
            try { $Process.Kill() } catch { }
            throw 'Public-key derivation timed out. Existing keys were not overwritten.'
        }
        $DerivedText = $OutputTask.Result
        $UnusedError = $ErrorTask.Result
        if ($Process.ExitCode -ne 0) {
            throw 'The dedicated CI key must be readable without a passphrase. Existing keys were not overwritten.'
        }
        return Get-PublicKeyIdentity -Text $DerivedText
    } finally { $Process.Dispose() }
}

try {
    if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true') {
        throw 'Run this setup on your own Windows computer, not in a CI runner.'
    }
    if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') {
        throw 'Open Windows PowerShell 5.1 (powershell.exe), then run this script there.'
    }
    $Ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
    $Keygen = (Get-Command ssh-keygen.exe -ErrorAction Stop).Source
    $Keyscan = (Get-Command ssh-keyscan.exe -ErrorAction Stop).Source
    $Clip = (Get-Command clip.exe -ErrorAction Stop).Source
    Add-Type -AssemblyName System.Windows.Forms

    $SshDirectory = Join-Path $env:USERPROFILE '.ssh'
    Assert-RegularPath $SshDirectory
    New-Item -ItemType Directory -Path $SshDirectory -Force | Out-Null
    $State = Join-Path $SshDirectory 'aptredlight-bootstrap'
    Assert-RegularPath $State
    New-Item -ItemType Directory -Path $State -Force | Out-Null
    $Key = Join-Path $SshDirectory 'aptredlight-github-deploy'
    $PublicKeyPath = $Key + '.pub'
    $KnownHosts = Join-Path $State 'known_hosts'
    $EmptyConfig = Join-Path $State 'ssh_config'
    foreach ($Path in @($Key, $PublicKeyPath, $KnownHosts, $EmptyConfig)) { Assert-RegularPath $Path }
    if ($Key.Contains('"')) { throw 'Unsupported local key path.' }
    $Utf8 = New-Object Text.UTF8Encoding($false)
    # Quote paths inside a dedicated SSH config so Windows profiles with spaces work.
    $KnownHostsConfigPath = $KnownHosts.Replace('\', '/')
    [IO.File]::WriteAllText($EmptyConfig, 'Host *' + "`n" + '    UserKnownHostsFile "' + $KnownHostsConfigPath + '"' + "`n", $Utf8)

    Write-Host '1/4 Verify the Hostinger server identity before asking for any password.'
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $Scan = @(& $Keyscan -T 15 -p $TargetPort -t ed25519 $TargetHost 2>$null)
        $ScanCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $PreviousPreference }
    $Records = @($Scan | Where-Object { $_ -is [string] -and $_.Trim() -and -not $_.StartsWith('#') })
    if ($ScanCode -ne 0 -or $Records.Count -ne 1) { throw 'The SSH server identity could not be read. No password was requested.' }
    $Columns = $Records[0].Trim() -split '\s+'
    if ($Columns.Count -ne 3 -or $Columns[0] -cne ('[' + $TargetHost + ']:' + $TargetPort) -or $Columns[1] -cne 'ssh-ed25519') {
        throw 'The scanned SSH endpoint or key algorithm is unexpected.'
    }
    $Blob = [Convert]::FromBase64String($Columns[2])
    if ($Blob.Length -ne 51 -or [Convert]::ToBase64String($Blob) -cne $Columns[2]) { throw 'Invalid SSH public key data.' }
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try { $ActualFingerprint = 'SHA256:' + [Convert]::ToBase64String($Hasher.ComputeHash($Blob)).TrimEnd('=') }
    finally { $Hasher.Dispose() }
    if ($ActualFingerprint -cne $ExpectedFingerprint) { throw 'The server fingerprint does not match the verified hPanel identity. Stop and verify with the hosting administrator.' }
    [IO.File]::WriteAllText($KnownHosts, $Records[0].Trim() + "`n", $Utf8)
    Write-Host ('Verified: ' + $ActualFingerprint)

    Write-Host '2/4 Create a dedicated key locally, or reuse the matching existing dedicated key.'
    if ((Test-Path -LiteralPath $Key) -ne (Test-Path -LiteralPath $PublicKeyPath)) { throw 'Only one half of the dedicated key pair exists. Do not overwrite it; ask your administrator.' }
    if (-not (Test-Path -LiteralPath $Key)) {
        Write-Host 'When ssh-keygen asks for a passphrase, press Enter twice. The dedicated CI key is stored in your protected user profile and GitHub Secrets.'
        Write-Host '出现 Enter passphrase 及再次确认时，分别直接按 Enter；这里留空供自动部署使用。'
        & $Keygen -t ed25519 -C aptredlight-github-deploy -f $Key
        if ($LASTEXITCODE -ne 0) { throw 'Key generation did not finish.' }
    }
    if (-not (Test-Path -LiteralPath $Key -PathType Leaf) -or -not (Test-Path -LiteralPath $PublicKeyPath -PathType Leaf)) { throw 'The dedicated key files are unavailable.' }
    if ((Get-Item -LiteralPath $Key).Length -gt 16384) { throw 'Unexpected private key format or size.' }
    Protect-PrivateKey $Key

    $PublicKey = Get-PublicKeyIdentity -Text ([IO.File]::ReadAllText($PublicKeyPath))
    $DerivedPublic = Get-DerivedPublicKeyIdentity -KeygenPath $Keygen -Path $Key
    if ($PublicKey -cne $DerivedPublic) {
        throw 'The dedicated public and private keys do not match. Existing keys were not overwritten.'
    }

    $Base = @('-F', $EmptyConfig, '-p', [string]$TargetPort, '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlgorithms=ssh-ed25519', '-o', 'GlobalKnownHostsFile=none', '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=20')
    $Destination = $TargetUser + '@' + $TargetHost
    $CheckCommand = 'test -s /home/u469397229/domains/aptredlight.com/public_html/source-release.json && command -v python3 >/dev/null && command -v tar >/dev/null'
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Ssh @Base -i $Key -o 'IdentityAgent=none' -o 'IdentitiesOnly=yes' -o 'BatchMode=yes' $Destination $CheckCommand 2>$null | Out-Null
        $KeyWorks = $LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference = $PreviousPreference }

    if (-not $KeyWorks) {
        Write-Host '3/4 Authorize only the public key. Enter the Hostinger SSH password in the native ssh.exe prompt on THIS computer. Do not send that password to chat.'
        Write-Host '等待 SSH 明确显示 password: 后输入 SSH 密码；输入不显示字符属于正常现象。'
        # The reviewed installer is embedded, not downloaded or taken from shell startup files.
        $InstallerBase64 = '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'
        $InstallerBytes = [Convert]::FromBase64String($InstallerBase64)
        $Authorize = "python3 -c 'import zlib;exec(zlib.decompress(bytes([" + ($InstallerBytes -join ',') + "])))'"
        if ($Authorize.Length -gt 27000) { throw 'The key installer exceeds the supported Windows command length.' }
        $Payload = 'no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty ' + $PublicKey
        $PreviousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $Payload | & $Ssh @Base -o 'PubkeyAuthentication=no' -o 'PreferredAuthentications=keyboard-interactive,password' -o 'NumberOfPasswordPrompts=2' $Destination $Authorize
            $Authorized = $LASTEXITCODE -eq 0
        } finally { $ErrorActionPreference = $PreviousPreference }
        if (-not $Authorized) { throw 'Public key authorization failed. The private key was not sent or saved to GitHub.' }
    }
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Ssh @Base -i $Key -o 'IdentityAgent=none' -o 'IdentitiesOnly=yes' -o 'BatchMode=yes' $Destination $CheckCommand 2>$null | Out-Null
        $KeyWorks = $LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference = $PreviousPreference }
    if (-not $KeyWorks) { throw 'Public key login or the server prerequisites were not confirmed. No private key was uploaded.' }

    Write-Host '4/4 Save ONE GitHub secret. The private key never goes to chat or the console.'
    $PrivateText = [IO.File]::ReadAllText($Key)
    $Saved = $false
    $GhCommand = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($null -ne $GhCommand) {
        $PreviousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $GhCommand.Source auth status 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $PrivateText | & $GhCommand.Source secret set HOSTINGER_SSH_PRIVATE_KEY --repo $Repository 2>$null | Out-Null
                $Saved = $LASTEXITCODE -eq 0
            }
        } finally { $ErrorActionPreference = $PreviousPreference }
    }
    if (-not $Saved) {
        $PrivateText | & $Clip
        if ($LASTEXITCODE -ne 0) { throw 'The key could not be copied to the local clipboard.' }
        $ClipboardContainsKey = $true
        Start-Process 'https://github.com/wk20230211-arch/aptredlight/settings/secrets/actions/new'
        Write-Host 'Name: HOSTINGER_SSH_PRIVATE_KEY'
        Write-Host 'Secret: press Ctrl+V in GitHub, then click Add secret.'
        Read-Host 'After saving the GitHub secret, press Enter here to clear this key from the clipboard' | Out-Null
    }
    Write-Host 'Local setup finished. Reply in ChatGPT: configured. The assistant will rerun the latest production deployment and check the actual website.'
} catch {
    Write-Error -Message ('Setup stopped: ' + $_.Exception.Message) -ErrorAction Continue
    Write-Host 'Do not change system execution policy. Ask the device or hosting administrator if a step is blocked.'
    Write-Host '脚本已停止。请记录上方报错；不要在 PS C:\...> 命令提示符后输入密码。'
    exit 1
} finally {
    if ($ClipboardContainsKey -and $null -ne $PrivateText) {
        try {
            $CurrentClipboard = [Windows.Forms.Clipboard]::GetText()
            if ($CurrentClipboard.Replace("`r`n", "`n").TrimEnd("`n") -ceq $PrivateText.Replace("`r`n", "`n").TrimEnd("`n")) {
                [Windows.Forms.Clipboard]::Clear()
            }
        } catch { Write-Host 'Clipboard cleanup could not be confirmed. Clear the copied deployment key from your local clipboard.' }
    }
    $PrivateText = $null
}
