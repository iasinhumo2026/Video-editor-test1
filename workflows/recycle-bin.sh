#!/usr/bin/env bash
# recycle-bin.sh <folder> [--apply] — send a job folder to the Windows Recycle Bin, provably, and never delete it
# permanently (S16, 2026-09-28). Windows only (Git Bash, MSYS, Cygwin). There a folder moved into ~/.Trash is a plain
# folder Windows never empties (the space never comes back), and the other delete commands can skip the bin:
# PowerShell's VisualBasic DeleteDirectory deletes for good outside a desktop session, and with its quiet option
# also a folder too big for the bin. archive.sh --trash calls this, and so does a client's clear-out (client CLAUDE.md).
#
#   bash workflows/recycle-bin.sh <folder>           dry run: says whether the Recycle Bin can take it whole
#   bash workflows/recycle-bin.sh <folder> --apply   recycles it, then proves it is gone and in the bin
#
# Dry run: exit 0 = it fits, 3 = refused (nothing touched), 5 = PowerShell failed. --apply: exit 0 = moved and
# confirmed, 1 = not done (the folder is still here, or it went and the bin did not confirm it: look there).
# Exit 2 = usage, or not Windows. Stays clean under stock /bin/bash 3.2.
set -euo pipefail

# The Recycle Bin side, run by Windows PowerShell with its inputs in the environment
# (VE_RECYCLE_MODE check|recycle, VE_RECYCLE_PATH a Windows path, VE_RECYCLE_KB the job's
# size), so no path or quote ever passes through a command line. check refuses (exit 3,
# nothing touched) when Windows would delete the job for good instead of recycling it: no
# desktop session, no bin on that drive, the bin set to delete immediately, or a job bigger than the bin's free
# room (bigger than the whole bin: Windows deletes it outright; bigger than what is free:
# Windows empties the bin's oldest items to make room). recycle runs the same check, then
# SHFileOperation FO_DELETE with FOF_ALLOWUNDO (the Recycle Bin), FOF_NOCONFIRMATION,
# FOF_SILENT, FOF_NOERRORUI and FOF_WANTNUKEWARNING (a permanent delete still asks), and
# proves the bin gained an item: exit 4 = the call failed, 6 = the folder went but the bin
# shows nothing new, 5 = PowerShell itself failed. Output stays ASCII (the console code page).
recycle_ps() {
  cat <<'PS'
$ErrorActionPreference = 'Stop'
try {
  Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class VeRecycleBin {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct SHFILEOPSTRUCT {
    public IntPtr hwnd;
    public uint wFunc;
    public string pFrom;
    public string pTo;
    public ushort fFlags;
    [MarshalAs(UnmanagedType.Bool)] public bool fAnyOperationsAborted;
    public IntPtr hNameMappings;
    public string lpszProgressTitle;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct SHQUERYRBINFO {
    public int cbSize;
    public long i64Size;
    public long i64NumItems;
  }
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  static extern int SHFileOperation(ref SHFILEOPSTRUCT op);
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  static extern int SHQueryRecycleBin(string root, ref SHQUERYRBINFO info);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  static extern bool GetVolumePathName(string path, StringBuilder mount, int len);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  static extern bool GetVolumeNameForVolumeMountPoint(string mount, StringBuilder name, int len);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
  static extern uint GetDriveType(string root);
  public static bool Fixed(string mount) { return GetDriveType(mount) == 3; }   // DRIVE_FIXED
  public static string Mount(string path) {
    StringBuilder sb = new StringBuilder(1024);
    return GetVolumePathName(path, sb, sb.Capacity) ? sb.ToString() : null;
  }
  public static string Volume(string mount) {
    StringBuilder sb = new StringBuilder(64);
    return GetVolumeNameForVolumeMountPoint(mount, sb, sb.Capacity) ? sb.ToString() : null;
  }
  public static SHQUERYRBINFO Query(string root) {
    SHQUERYRBINFO q = new SHQUERYRBINFO();
    q.cbSize = Marshal.SizeOf(typeof(SHQUERYRBINFO));
    int hr = SHQueryRecycleBin(root, ref q);
    if (hr != 0) throw new Exception("SHQueryRecycleBin failed: 0x" + hr.ToString("X8"));
    return q;
  }
  public static int Recycle(string path, out bool aborted) {
    SHFILEOPSTRUCT op = new SHFILEOPSTRUCT();
    op.wFunc = 3;                                     // FO_DELETE
    op.pFrom = path + "\0";                           // double-NUL list (the marshaller adds one)
    op.fFlags = 0x40 | 0x10 | 0x4 | 0x400 | 0x4000;   // ALLOWUNDO NOCONFIRMATION SILENT NOERRORUI WANTNUKEWARNING
    int rc = SHFileOperation(ref op);
    aborted = op.fAnyOperationsAborted;
    return rc;
  }
}
'@
  function Refuse($why) { "refused: $why Nothing was touched."; exit 3 }
  if (-not [Environment]::UserInteractive) { Refuse "this is not a desktop session (a service, an SSH login or a background task), and the Recycle Bin belongs to the signed-in desktop: run it from there." }
  $path = $env:VE_RECYCLE_PATH
  if ($env:VE_RECYCLE_KB -notmatch '^\d+$') { Refuse "the job's size was not measured." }
  $bytes = [long]$env:VE_RECYCLE_KB * 1024
  $jobMB = [math]::Ceiling($bytes / 1MB)
  foreach ($hive in 'HKCU:', 'HKLM:') {
    $pol = Get-ItemProperty -Path "$hive\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" -Name NoRecycleFiles -ErrorAction SilentlyContinue
    if ($pol -and $pol.NoRecycleFiles -eq 1) { Refuse "a policy ($hive NoRecycleFiles) turns the Recycle Bin off, so Windows would delete the job permanently." }
  }
  # GetVolumePathName answers a UNC path with the CURRENT drive, so a share is refused by its form
  if ($path -notmatch '^[A-Za-z]:\\') { Refuse "$path is not on a drive letter (a network share has no Recycle Bin: Windows would delete the job permanently)." }
  $mount = [VeRecycleBin]::Mount($path)
  $volume = if ($mount -and [VeRecycleBin]::Fixed($mount)) { [VeRecycleBin]::Volume($mount) } else { $null }
  if (-not $volume) { Refuse "$path is not on a local fixed drive (a network or removable drive has no Recycle Bin: Windows would delete the job permanently)." }
  $drive = $mount.TrimEnd('\')
  $guid = $volume -replace '^\\\\\?\\Volume', '' -replace '\\$', ''
  $vol = Get-ItemProperty -LiteralPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume\$guid" -ErrorAction SilentlyContinue
  if (-not $vol -or $null -eq $vol.MaxCapacity) { Refuse "Windows keeps no Recycle Bin settings for $drive (a removable drive has no Recycle Bin). If $drive is a fixed drive, open the Recycle Bin's Properties once, press OK, and re-run." }
  if ($vol.NukeOnDelete -eq 1) { Refuse "the Recycle Bin on $drive is set to remove files immediately (Recycle Bin, Properties), so the job would be deleted permanently." }
  $maxMB = [long]$vol.MaxCapacity
  $before = [VeRecycleBin]::Query($mount)
  $freeMB = [math]::Floor(($maxMB * 1MB - $before.i64Size) / 1MB)
  if ($bytes -gt $maxMB * 1MB) { Refuse ("the job is {0:N0} MB and the Recycle Bin on {1} holds at most {2:N0} MB: Windows deletes an item that big permanently. Raise the bin's size (Recycle Bin, Properties, Custom size) or archive the job to a drive." -f $jobMB, $drive, $maxMB) }
  if ($bytes -gt $maxMB * 1MB - $before.i64Size) { Refuse ("the job is {0:N0} MB and the Recycle Bin on {1} has {2:N0} MB free of {3:N0} MB: Windows would permanently delete its oldest items to make room. Empty the Recycle Bin or raise its size first." -f $jobMB, $drive, [math]::Max($freeMB, 0), $maxMB) }
  "fits: the job is {0:N0} MB; the Recycle Bin on {1} has {2:N0} MB free of {3:N0} MB" -f $jobMB, $drive, $freeMB, $maxMB
  if ($env:VE_RECYCLE_MODE -ne 'recycle') { exit 0 }
  $aborted = $false
  $rc = [VeRecycleBin]::Recycle($path, [ref]$aborted)
  if ($rc -ne 0 -or $aborted -or (Test-Path -LiteralPath $path)) {
    "the Recycle Bin move failed (SHFileOperation 0x{0:X}, aborted={1}): a file in the job may be open in another app. Anything it moved is in the Recycle Bin; nothing was deleted permanently." -f $rc, $aborted
    exit 4
  }
  $after = [VeRecycleBin]::Query($mount)
  if ($after.i64NumItems -le $before.i64NumItems) {
    "the folder is gone but the Recycle Bin on {0} shows no new item ({1} before, {2} after): look for it there before anything else." -f $drive, $before.i64NumItems, $after.i64NumItems
    exit 6
  }
  "in the Recycle Bin on {0} ({1:N0} item(s) now, {2:N0} MB of {3:N0} MB)" -f $drive, $after.i64NumItems, [math]::Ceiling($after.i64Size / 1MB), $maxMB
  exit 0
} catch {
  'PowerShell could not reach the Recycle Bin: ' + $_.Exception.Message
  exit 5
}
PS
}

# $1 = check | recycle, $2 = the folder. Windows PowerShell ships with every Windows 10 and 11.
recycle_bin() {
  SRC="$2"
  WIN=$(cygpath -aw "$SRC") || { echo "cygpath could not name $SRC as a Windows path"; return 5; }
  # measured or refused: a size that reads 0 would pass the capacity check
  KB=$(du -sk "$SRC" 2>/dev/null | cut -f1) || KB=""
  case "$KB" in ''|*[!0-9]*) echo "refused: du could not measure $SRC. Nothing was touched."; return 3 ;; esac
  VE_RECYCLE_MODE="$1" VE_RECYCLE_PATH="$WIN" VE_RECYCLE_KB="$KB" VE_RECYCLE_PS="$(recycle_ps)" \
    powershell.exe -NoProfile -NonInteractive -Command 'Invoke-Expression $env:VE_RECYCLE_PS'
}

case "$#:${2:-}" in 1:|2:--apply) ;; *) echo "usage: bash workflows/recycle-bin.sh <folder> [--apply]"; exit 2 ;; esac
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *) echo "recycle-bin.sh is for Windows; on macOS and Linux the folder goes to the system Trash"; exit 2 ;;
esac
DIR="$1"; APPLY=0; [ "$#" = 2 ] && APPLY=1
[ -d "$DIR" ] || { echo "no such folder: $DIR"; exit 2; }
SIZE=$(du -sh "$DIR" 2>/dev/null | cut -f1) || SIZE="size unknown"

if [ "$APPLY" = 0 ]; then
  echo "DRY RUN — would move $DIR ($SIZE) to the Recycle Bin"
  RC=0; recycle_bin check "$DIR" || RC=$?
  exit "$RC"
fi
RC=0; recycle_bin recycle "$DIR" || RC=$?
if [ -e "$DIR" ]; then
  echo "✗ $DIR is still here (exit $RC) — not moved, and nothing was deleted permanently"
  exit 1
fi
if [ "$RC" != 0 ]; then
  echo "✗ $DIR is gone but the Recycle Bin did not confirm it (exit $RC) — look for it in the Recycle Bin"
  exit 1
fi
echo "✓ moved $DIR ($SIZE) to the Recycle Bin — restorable until the Recycle Bin is emptied, and the space comes back only then"
