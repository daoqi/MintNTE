// Launcher.cpp
// 编译命令：cl /EHsc /O2 /DUNICODE /D_UNICODE Launcher.cpp /link /SUBSYSTEM:WINDOWS advapi32.lib user32.lib shell32.lib /OUT:Launcher.exe

#ifndef UNICODE
#define UNICODE
#endif

#include <windows.h>
#include <shellapi.h>
#include <string>

constexpr const wchar_t* TARGET_EXE = L"MintNTE.exe";

std::wstring GetLaunchDir()
{
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    std::wstring dir(path);
    // 移除文件名
    size_t pos = dir.find_last_of(L"\\/");
    if (pos != std::wstring::npos)
        dir = dir.substr(0, pos);
    // 再取上一级目录（因为 Launcher.exe 在 _internal 里，主程序在上级）
    pos = dir.find_last_of(L"\\/");
    if (pos != std::wstring::npos)
        dir = dir.substr(0, pos);
    return dir;
}

bool IsAdmin()
{
    BOOL isAdmin = FALSE;
    PSID adminGroup = nullptr;
    SID_IDENTIFIER_AUTHORITY ntAuthority = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&ntAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &adminGroup))
    {
        CheckTokenMembership(nullptr, adminGroup, &isAdmin);
        FreeSid(adminGroup);
    }
    return isAdmin;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    std::wstring workDir = GetLaunchDir();
    std::wstring targetPath = workDir + L"\\" + TARGET_EXE;

    if (!IsAdmin())
    {
        SHELLEXECUTEINFOW sei = { sizeof(sei) };
        sei.lpVerb = L"runas";
        sei.lpFile = targetPath.c_str();
        sei.lpDirectory = workDir.c_str();
        sei.nShow = SW_SHOWNORMAL;
        sei.fMask = SEE_MASK_FLAG_NO_UI | SEE_MASK_NOASYNC;
        if (ShellExecuteExW(&sei))
            return 0;
        else
        {
            MessageBoxW(nullptr, L"Failed to obtain administrator privileges.", L"Error", MB_ICONERROR);
            return 1;
        }
    }
    else
    {
        STARTUPINFOW si = { sizeof(si) };
        PROCESS_INFORMATION pi = {};
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_SHOWNORMAL;
        if (!CreateProcessW(targetPath.c_str(), nullptr, nullptr, nullptr, FALSE,
            CREATE_NEW_CONSOLE, nullptr, workDir.c_str(), &si, &pi))
        {
            MessageBoxW(nullptr, L"Failed to launch MintNTE.exe. Check if the file exists.", L"Error", MB_ICONERROR);
            return 1;
        }
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 0;
    }
}