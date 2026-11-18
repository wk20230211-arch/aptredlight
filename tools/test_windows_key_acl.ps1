#Requires -Version 5.1
# Run in a dedicated Windows CI step. This never loads a real key or runs setup.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'This test requires Windows PowerShell 5.1 and .NET Framework.'
}

$NativeSource = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class APTAclTokenProbe {
    [StructLayout(LayoutKind.Sequential)]
    private struct Luid { public UInt32 Low; public Int32 High; }
    [StructLayout(LayoutKind.Sequential)]
    private struct OnePrivilege {
        public UInt32 Count;
        public Luid Id;
        public UInt32 Attributes;
    }
    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", SetLastError=true)]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")]
    private static extern void SetLastError(UInt32 error);
    [DllImport("advapi32.dll", SetLastError=true)]
    private static extern bool OpenProcessToken(IntPtr process, UInt32 rights, out IntPtr token);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern bool LookupPrivilegeValue(string system, string name, out Luid value);
    [DllImport("advapi32.dll", SetLastError=true)]
    private static extern bool GetTokenInformation(IntPtr token, Int32 type,
        IntPtr buffer, Int32 length, out Int32 returned);
    [DllImport("advapi32.dll", SetLastError=true)]
    private static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll,
        ref OnePrivilege value, Int32 length, IntPtr previous, IntPtr returned);

    private static bool HasPrivilege(IntPtr token, Luid target) {
        Int32 size;
        bool sized = GetTokenInformation(token, 3, IntPtr.Zero, 0, out size);
        Int32 code = Marshal.GetLastWin32Error();
        if (sized || code != 122 || size < 4 || size > 1048576)
            throw new InvalidOperationException("Token privilege sizing failed.");
        IntPtr buffer = Marshal.AllocHGlobal(size);
        try {
            Int32 returned;
            if (!GetTokenInformation(token, 3, buffer, size, out returned))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            Int32 count = Marshal.ReadInt32(buffer);
            if (count < 0 || returned < 4 || (long)4 + (long)count * 12 > returned)
                throw new InvalidOperationException("Invalid token privilege layout.");
            for (Int32 i = 0; i < count; i++) {
                Int32 offset = 4 + i * 12;
                UInt32 low = unchecked((UInt32)Marshal.ReadInt32(buffer, offset));
                Int32 high = Marshal.ReadInt32(buffer, offset + 4);
                if (low == target.Low && high == target.High) return true;
            }
            return false;
        } finally { Marshal.FreeHGlobal(buffer); }
    }

    public static void RemoveAndAssertAbsent() {
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), 0x0008 | 0x0020, out token))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try {
            Luid target;
            if (!LookupPrivilegeValue(null, "SeSecurityPrivilege", out target))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            if (HasPrivilege(token, target)) {
                OnePrivilege remove = new OnePrivilege();
                remove.Count = 1;
                remove.Id = target;
                remove.Attributes = 0x00000004; // SE_PRIVILEGE_REMOVED, never ENABLED.
                SetLastError(0);
                bool adjusted = AdjustTokenPrivileges(token, false, ref remove, 0,
                    IntPtr.Zero, IntPtr.Zero);
                Int32 code = Marshal.GetLastWin32Error();
                if (!adjusted || code != 0) throw new Win32Exception(code);
            }
            if (HasPrivilege(token, target))
                throw new InvalidOperationException("SeSecurityPrivilege was not removed.");
        } finally { CloseHandle(token); }
    }
}
'@
Add-Type -TypeDefinition $NativeSource -Language CSharp | Out-Null
[APTAclTokenProbe]::RemoveAndAssertAbsent()
Write-Host 'Confirmed: this test process has no SeSecurityPrivilege. No privilege was enabled.'
Write-Host 'Scope: this is not full standard-user emulation; other token privileges are unchanged.'

$SetupPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'setup\Connect-APTREDLIGHT.ps1'
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile($SetupPath, [ref]$Tokens, [ref]$ParseErrors)
if (@($ParseErrors).Count -ne 0) { throw 'The setup script did not parse; bootstrap was not executed.' }
$Functions = @($Ast.FindAll({
    param($Node)
    $Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -ceq 'Protect-PrivateKey'
}, $true))
if ($Functions.Count -ne 1) { throw 'Expected exactly one Protect-PrivateKey function.' }
# Only define the selected AST function. Never dot-source the setup main block.
. ([ScriptBlock]::Create($Functions[0].Extent.Text))

$TemporaryDirectory = $null
$Stream = $null
try {
    $TemporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ('aptredlight-acl-fixture-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $TemporaryDirectory | Out-Null
    $FixturePath = Join-Path $TemporaryDirectory 'ordinary-fixture.txt'
    $Sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $Everyone = New-Object Security.Principal.SecurityIdentifier -ArgumentList 'S-1-1-0'
    $InitialAcl = New-Object Security.AccessControl.FileSecurity
    # Specifying the creator's own SID on a NEW fixture is not an owner change
    # to an existing file and does not request or enable any privilege.
    $InitialAcl.SetOwner($Sid)
    $UserRule = New-Object Security.AccessControl.FileSystemAccessRule -ArgumentList $Sid, 'FullControl', 'Allow'
    $EveryoneRule = New-Object Security.AccessControl.FileSystemAccessRule -ArgumentList $Everyone, 'Read', 'Allow'
    $InitialAcl.AddAccessRule($UserRule)
    $InitialAcl.AddAccessRule($EveryoneRule)
    $OriginalBytes = [Text.Encoding]::UTF8.GetBytes('Ordinary ACL test fixture. This is not a credential.')
    $Stream = [IO.File]::Create($FixturePath, 4096, [IO.FileOptions]::None, $InitialAcl)
    $Stream.Write($OriginalBytes, 0, $OriginalBytes.Length)
    $Stream.Dispose()
    $Stream = $null

    $Sections = [Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner
    $Before = (Get-Item -LiteralPath $FixturePath).GetAccessControl($Sections)
    $OwnerBefore = $Before.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($OwnerBefore -cne $Sid.Value) { throw 'Fixture owner must be the current user before the test.' }
    $BeforeRules = @($Before.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if (@($BeforeRules | Where-Object { $_.IdentityReference.Value -eq 'S-1-1-0' }).Count -eq 0) {
        throw 'Fixture must start with an Everyone rule, so its removal is observable.'
    }

    Protect-PrivateKey -Path $FixturePath | Out-Null
    [APTAclTokenProbe]::RemoveAndAssertAbsent()
    $After = (Get-Item -LiteralPath $FixturePath).GetAccessControl($Sections)
    $Rules = @($After.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($After.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $OwnerBefore -or
        -not $After.AreAccessRulesProtected -or $Rules.Count -ne 1 -or
        $Rules[0].IdentityReference.Value -cne $Sid.Value -or
        $Rules[0].AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
        $Rules[0].IsInherited -or
        ($Rules[0].FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne [Security.AccessControl.FileSystemRights]::FullControl) {
        throw 'Owner-only protected DACL was not confirmed.'
    }
    $ActualBytes = [IO.File]::ReadAllBytes($FixturePath)
    if ([Convert]::ToBase64String($ActualBytes) -cne [Convert]::ToBase64String($OriginalBytes)) {
        throw 'Changing the DACL modified ordinary file bytes.'
    }
    $Stream = [IO.File]::Open($FixturePath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $Stream.Seek(0, [IO.SeekOrigin]::End) | Out-Null
    $Stream.WriteByte(10)
    $Stream.Flush()
    $Stream.SetLength($OriginalBytes.Length)
    $Stream.Dispose()
    $Stream = $null
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($FixturePath)) -cne [Convert]::ToBase64String($OriginalBytes)) {
        throw 'Ordinary file read/write verification failed.'
    }
    $RejectedDirectory = $false
    try { Protect-PrivateKey -Path $TemporaryDirectory | Out-Null }
    catch { $RejectedDirectory = $true }
    if (-not $RejectedDirectory) { throw 'A directory was incorrectly accepted as a key file.' }
    Write-Host 'PASS: real .NET Framework file ACL update without SeSecurityPrivilege; owner and bytes retained, Everyone removed, read/write available.'
    Write-Host 'Only a random ordinary text fixture was used. No real key was accessed; setup main flow was not executed.'
} finally {
    if ($null -ne $Stream) { $Stream.Dispose() }
    if ($null -ne $TemporaryDirectory -and (Test-Path -LiteralPath $TemporaryDirectory)) {
        Remove-Item -LiteralPath $TemporaryDirectory -Recurse -Force
    }
}
