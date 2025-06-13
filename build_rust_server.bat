@echo off
echo Building Rust MCP Server...
cargo build --release
if errorlevel 1 (
    echo Failed to build Rust MCP Server. Ensure Rust and Cargo are installed and configured correctly.
    goto :eof
)

echo Rust MCP Server built successfully.
echo Executable should be in target\release\rbx-studio-mcp.exe
:eof
pause
