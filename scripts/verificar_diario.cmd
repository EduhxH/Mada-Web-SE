@echo off
REM Verificacao diaria do Moodle, para o Agendador de Tarefas do Windows.
REM Procura material novo, descarrega so esse e reindexa. Guarda tudo o que
REM imprimir num registo, porque uma tarefa agendada corre sem ninguem a ver:
REM se falhar em silencio, o registo e a unica forma de dar por isso.

cd /d "%~dp0.."

set REGISTO=data\verificacao.log

echo. >> "%REGISTO%"
echo ===== %DATE% %TIME% ===== >> "%REGISTO%"

.venv\Scripts\python.exe main.py moodle --verificar >> "%REGISTO%" 2>&1
if errorlevel 1 (
  echo FALHOU a verificacao ^(codigo %errorlevel%^) >> "%REGISTO%"
  exit /b 1
)

.venv\Scripts\python.exe main.py atualizar --sem-rastreio >> "%REGISTO%" 2>&1
if errorlevel 1 (
  echo FALHOU a reindexacao ^(codigo %errorlevel%^) >> "%REGISTO%"
  exit /b 1
)

echo Concluido. >> "%REGISTO%"
