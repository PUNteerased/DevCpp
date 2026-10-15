# Bloodshed / Orwell Dev-C++ 5.11 — AI Chat patch notes

This project ships a working `DevCpp-AI.exe` that bundles the Bloodshed 5.11 binaries
and docks an AI Chat panel (Delphi is not required on end-user PCs).

The upstream Delphi sources live in `../orwelldevcpp/Source/`.

To merge AI Chat as a native `MessageControl` tab inside the IDE (when Delphi is available):

1. Open `main.dfm` / `main.pas`
2. Add a `TTabSheet` named `AIChatSheet` to `MessageControl` (next to `FindSheet`)
3. Host an HTTP client (Indy) calling OpenAI-compatible `/v1/chat/completions`
4. Bind sockets to the Personal Hotspot adapter only (skip Ethernet)
5. Wire Uninstall to delete only `%LOCALAPPDATA%\DevCpp-AI` via `install-manifest.json`

Until Delphi rebuild is done, the Python/Win32 companion panel provides the same UX.
