@echo off
REM Vigia do horario da escola, para o Agendador de Tarefas do Windows.
REM
REM Pode correr de hora a hora sem problema: quem decide se e altura de
REM verificar e o proprio programa, e ele so bate no servidor da escola de
REM quinta a domingo, e nunca mais depois de apanhar o horario da semana.
REM Deixar a decisao no codigo e nao no agendador significa que a regra esta
REM testada - e o agendador nao sabe se o horario ja saiu.
REM
REM So reindexa quando ha ficheiro novo: reindexar sao dois minutos e nao
REM faz sentido gasta-los para nada.

cd /d "%~dp0.."

set REGISTO=data\horario.log

.venv\Scripts\python.exe main.py horario > "%TEMP%\madalena-horario.txt" 2>&1
set CODIGO=%errorlevel%

echo. >> "%REGISTO%"
echo ===== %DATE% %TIME% ===== >> "%REGISTO%"
type "%TEMP%\madalena-horario.txt" >> "%REGISTO%"

if not "%CODIGO%"=="0" (
  echo FALHOU a verificacao ^(codigo %CODIGO%^) >> "%REGISTO%"
  exit /b 1
)

findstr /c:"Horario novo" "%TEMP%\madalena-horario.txt" >nul
if errorlevel 1 (
  exit /b 0
)

echo Horario novo: a reindexar... >> "%REGISTO%"
.venv\Scripts\python.exe main.py atualizar --sem-rastreio >> "%REGISTO%" 2>&1
if errorlevel 1 (
  echo FALHOU a reindexacao >> "%REGISTO%"
  exit /b 1
)
echo Concluido. >> "%REGISTO%"
