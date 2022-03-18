:: run in vscode terminal only
:: in console 1
FOR /L %L IN (0,0,1) DO @(python main.py&echo Restarting...)

:: in console 2
FOR /L %L IN (0,0,1) DO @(E:\script\inotifywait.exe cogs\ -e modify
wmic process where "commandline like 'python  main.py'" delete
timeout 4)
