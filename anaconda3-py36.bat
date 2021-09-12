
@echo off
cd "C:\Users\POE\Documents\GitHub\experiment_control"
set PATH=%PATH%;C:\ProgramData\Anaconda3\Scripts
%windir%\system32\cmd.exe "/K" C:\ProgramData\Anaconda3\Scripts\activate.bat py36
hash -r
