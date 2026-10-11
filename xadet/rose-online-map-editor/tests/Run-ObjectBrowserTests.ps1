param(
    [string]$MSBuildPath = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe'
)
# Builds the editor, compiles tests/ObjectBrowserTests.cs against it and runs it
# from the data folder: catalogue + search over the real tables, a foreign object
# appended into a scratch copy of Junon Polis' decoration table and read back,
# thumbnails rendered and cached, the browser and rotation editor drawn to PNGs
# (build/object-browser-tests/browser.png, rotation.png).
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$editor = Join-Path $repo 'xadet\rose-online-map-editor'
$testOutput = Join-Path $repo 'build\object-browser-tests'
New-Item -ItemType Directory -Force $testOutput | Out-Null
& $MSBuildPath "$editor\Map Editor.sln" /p:Configuration=Release /p:Platform=x86 "/p:ReferencePath=$repo\data" /m:1 /v:minimal
if ($LASTEXITCODE -ne 0) { throw 'Editor build failed.' }
Copy-Item "$editor\Map Editor\bin\x86\Release\Map Editor.exe" $testOutput -Force
$xnaRoot = "$env:WINDIR\assembly\GAC_32"
$wpfRoot = Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies\Microsoft\Framework\v3.0'
$responseFile = Join-Path $testOutput 'test.rsp'
@"
/nologo
/target:exe
/platform:x86
/out:"$testOutput\ObjectBrowserTests.exe"
/r:"$testOutput\Map Editor.exe"
/r:"$xnaRoot\Microsoft.Xna.Framework\3.1.0.0__6d5c3888ef60e27d\Microsoft.Xna.Framework.dll"
/r:"$xnaRoot\Microsoft.Xna.Framework.Game\3.1.0.0__6d5c3888ef60e27d\Microsoft.Xna.Framework.Game.dll"
/r:System.Core.dll
/r:System.Windows.Forms.dll
/r:System.Drawing.dll
/r:"$wpfRoot\PresentationFramework.dll"
/r:"$wpfRoot\PresentationCore.dll"
/r:"$wpfRoot\WindowsBase.dll"
"$PSScriptRoot\ObjectBrowserTests.cs"
"@ | Set-Content $responseFile
& "$env:WINDIR\Microsoft.NET\Framework\v3.5\csc.exe" "@$responseFile"
if ($LASTEXITCODE -ne 0) { throw 'Test compilation failed.' }
# The editor's data readers resolve paths against the working directory.
Push-Location "$repo\data"
try {
    & "$testOutput\ObjectBrowserTests.exe" "$repo\data" "$testOutput"
    if ($LASTEXITCODE -ne 0) { throw 'Object browser tests failed.' }
} finally { Pop-Location }
