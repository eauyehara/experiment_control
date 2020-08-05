@echo off
set PATH=%PATH%;C:\ProgramData\Anaconda3\Scripts
%windir%\system32\cmd.exe "/K" C:\ProgramData\Anaconda3\Scripts\activate.bat py36
hash -r