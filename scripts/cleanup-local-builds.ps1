param([datetime]$Before = '2026-11-03T20:23:00', [string]$KeepPackage = 'portable-1.14.0')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$buildRoot = Join-Path $projectRoot 'build'
$distRoot = Join-Path $projectRoot 'dist'
$auditRoot = Join-Path $projectRoot '.nbtcreator/maintenance'
New-Item -ItemType Directory -Path $auditRoot -Force | Out-Null
$processes = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(node|electron|NBTCreator|python|chrome|esbuild).*' } | ForEach-Object CommandLine)
$targets = @()
foreach ($scope in @($buildRoot, $distRoot)) {
  foreach ($item in Get-ChildItem -LiteralPath $scope -Directory) {
    if ($scope -eq $buildRoot -and ($item.Name -in @('downloads','portable-browser') -or $item.LastWriteTime -ge $Before)) { continue }
    if ($scope -eq $distRoot -and $item.Name -eq $KeepPackage) { continue }
    $resolved = [IO.Path]::GetFullPath($item.FullName)
    if (-not $resolved.StartsWith($scope + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe cleanup path: $resolved" }
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked directory: $resolved" }
    if (@($processes | Where-Object { $_ -and $_.Contains($resolved, [StringComparison]::OrdinalIgnoreCase) }).Count) { continue }
    $targets += $item
  }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archive = Join-Path $auditRoot "old-build-diagnostics-$stamp.zip"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
$records = @(); $saved = 0
try {
  foreach ($item in $targets) {
    $files = @(Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force -ErrorAction SilentlyContinue)
    if (@($files | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Linked files in $($item.FullName)" }
    $records += [pscustomobject]@{path=[IO.Path]::GetRelativePath($projectRoot,$item.FullName); bytes=($files | Measure-Object Length -Sum).Sum; reason= $(if($item.Parent.FullName -eq $distRoot){'superseded local package staging'}else{'previous generated test/build run'})}
    foreach ($file in $files) {
      $relative = [IO.Path]::GetRelativePath($projectRoot,$file.FullName)
      if ($relative -match '[\\/](profile[^\\/]*|node_modules|resources|runtime|runtimes|Cache|Code Cache|GPUCache)[\\/]') { continue }
      if ($file.Length -le 8MB -and ($file.Name -match '^(results?\.json|.*\.log|request\.json|job\.json|.*report.*\.json|.*diagnos.*\.json|.*\.manifest\.json|.*\.sha256)$')) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$file.FullName,$relative.Replace('\','/'),[IO.Compression.CompressionLevel]::Optimal) | Out-Null
        $saved++
      }
    }
  }
} finally { $zip.Dispose() }
$manifest = Join-Path $auditRoot "cleanup-$stamp.json"
[IO.File]::WriteAllText($manifest, (@{created=(Get-Date).ToString('o'); archive=$archive; diagnostic_files=$saved; targets=$records} | ConvertTo-Json -Depth 6))
foreach ($item in $targets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
[pscustomobject]@{removed_directories=$targets.Count; freed_bytes=($records | Measure-Object bytes -Sum).Sum; diagnostics_saved=$saved; manifest=$manifest; latest_package_retained="dist/$KeepPackage"} | ConvertTo-Json -Compress
