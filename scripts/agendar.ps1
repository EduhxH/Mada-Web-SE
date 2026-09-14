<#
.SYNOPSIS
    Registra (ou remove) as tarefas agendadas da Madalena Search no Windows.

.DESCRIPTION
    Cinco tarefas, todas em \Madalena\ no Agendador de Tarefas:

        conteudos-manha   07:30   todos os dias
        conteudos-tarde   14:30   todos os dias
        conteudos-noite   21:30   todos os dias
        horario           de hora a hora, todos os dias
        no-ar             ao entrar na sessao, e vigiada de 5 em 5 minutos

    As tres primeiras procuram material novo no Moodle e reindexam so quando
    ha. Sao tres e nao uma porque um professor publica a ficha quando lhe da
    jeito: quem so verifica de madrugada anda um dia atrasado em relacao a
    aula da tarde.

    A quarta le um ficheiro JSON e sai, excepto de quinta a domingo - a regra
    de quando o horario sai vive no codigo (app/crawler/horarios.py), que e
    onde esta testada. O agendador nao sabe nada sobre horarios de escola de
    proposito: se a escola mudar o dia de publicacao, muda-se uma constante e
    nao se toca aqui.

    As tarefas expiram a 30 de setembro de 2026 (ver -Ate). Isto e deliberado:
    um programa que bate no servidor da escola nao deve ficar a correr para
    sempre sem ninguem reparar. A 1 de outubro ha de ser uma decisao, nao um
    esquecimento.

.PARAMETER Ate
    Data e hora em que as tarefas deixam de correr. Por omissao, o fim de
    setembro de 2026.

.PARAMETER Remover
    Remove as quatro tarefas em vez de as criar.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1
    powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1 -Ate '2026-12-19 23:59'
    powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1 -Remover
#>

[CmdletBinding()]
param(
    [datetime] $Ate = '2026-09-30 23:59',
    [int]      $Porta = 8080,
    [switch]   $Remover
)

$ErrorActionPreference = 'Stop'

$raiz    = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pasta   = '\Madalena\'
$tarefas = @(
    @{ Nome = 'conteudos-manha'; Passo = 'conteudos'; Etiqueta = 'manha'; As = '07:30' }
    @{ Nome = 'conteudos-tarde'; Passo = 'conteudos'; Etiqueta = 'tarde'; As = '14:30' }
    @{ Nome = 'conteudos-noite'; Passo = 'conteudos'; Etiqueta = 'noite'; As = '21:30' }
    @{ Nome = 'horario';         Passo = 'horario';   Etiqueta = '';      As = '00:05'; DeHoraEmHora = $true }
)

# A quinta tarefa e de outra natureza e por isso esta a parte: as quatro de cima
# correm, fazem uma coisa e saem; esta fica a correr. E o vigia que mantem o
# servidor e o tunel de pe e impede a maquina de suspender - ver scripts/no_ar.py.
# Arranca com a sessao e repete-se de cinco em cinco minutos: como so pode haver
# uma instancia, a repeticao nao duplica nada e serve de vigia do proprio vigia.
$VIGIA = 'no-ar'

# pythonw.exe e nao python.exe: nao aloca consola, portanto nada pisca no ecra.
# A tarefa do horario corre vinte e quatro vezes por dia - uma janela preta a
# aparecer de hora a hora seria inaceitavel com o projetor da sala ligado.
$interprete = Join-Path $raiz '.venv\Scripts\pythonw.exe'
$guiao      = Join-Path (Join-Path $raiz 'scripts') 'tarefa.py'
foreach ($caminho in @($interprete, $guiao)) {
    if (-not (Test-Path $caminho)) { throw "Nao encontrei: $caminho" }
}

foreach ($nome in (@($tarefas | ForEach-Object { $_.Nome }) + $VIGIA)) {
    $existente = Get-ScheduledTask -TaskPath $pasta -TaskName $nome -ErrorAction SilentlyContinue
    if ($existente) {
        Unregister-ScheduledTask -TaskPath $pasta -TaskName $nome -Confirm:$false
        Write-Host "removida  $pasta$nome"
    }
}
if ($Remover) {
    Write-Host ''
    Write-Host 'Nada mais corre sozinho. Para voltar a ligar, corra este guiao sem -Remover.'
    return
}

# Uma tarefa nao pode ter um fim no passado: o Agendador aceita o registo e a
# tarefa nunca corre, sem dizer nada. Mais vale recusar aqui.
if ($Ate -le (Get-Date)) {
    throw "A data -Ate ($Ate) ja passou. As tarefas nunca correriam."
}

# Comum as quatro. StartWhenAvailable: o portatil esta fechado as 07:30, a
# corrida perdida acontece quando ele abrir - senao a manha de sabado nunca
# era verificada. ExecutionTimeLimit: um pedido pendurado no servidor da
# escola nao pode ficar la uma semana a segurar a tarefa seguinte.
$opcoes = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 15)

# S4U ("correr esteja ou nao a sessao iniciada", sem guardar senha) e o que se
# quer: nao abre janela de consola de hora a hora e nao obriga a ter a sessao
# aberta. Nem todas as maquinas o permitem sem privilegios, por isso ha
# recurso a sessao interactiva - que funciona, mas pisca uma janela preta.
$utilizador = "$env:USERDOMAIN\$env:USERNAME"
$principais = @(
    (New-ScheduledTaskPrincipal -UserId $utilizador -LogonType S4U         -RunLevel Limited),
    (New-ScheduledTaskPrincipal -UserId $utilizador -LogonType Interactive -RunLevel Limited)
)

foreach ($tarefa in $tarefas) {
    $argumentos = "`"$guiao`" $($tarefa.Passo)"
    if ($tarefa.Etiqueta) { $argumentos += " --etiqueta $($tarefa.Etiqueta)" }

    $accao = New-ScheduledTaskAction -Execute $interprete `
        -Argument $argumentos -WorkingDirectory $raiz

    $gatilho = New-ScheduledTaskTrigger -Daily -At $tarefa.As
    if ($tarefa.DeHoraEmHora) {
        # A repeticao nao se define no construtor de um gatilho diario; tem de
        # se enxertar o padrao no objeto CIM depois de o criar.
        $repeticao = (New-ScheduledTaskTrigger -Once -At $tarefa.As `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration (New-TimeSpan -Hours 23)).Repetition
        $gatilho.Repetition = $repeticao
    }
    $gatilho.EndBoundary = $Ate.ToString('yyyy-MM-ddTHH:mm:ss')

    $registada = $null
    foreach ($principal in $principais) {
        try {
            $registada = Register-ScheduledTask -TaskPath $pasta -TaskName $tarefa.Nome `
                -Action $accao -Trigger $gatilho -Settings $opcoes -Principal $principal `
                -Description "Madalena Search - $($tarefa.Nome). Criada por scripts\agendar.ps1." `
                -Force
            break
        } catch {
            $ultimo = $_
        }
    }
    if (-not $registada) { throw $ultimo }

    $modo = $registada.Principal.LogonType
    $quando = if ($tarefa.DeHoraEmHora) { "de hora a hora a partir das $($tarefa.As)" }
              else { "todos os dias as $($tarefa.As)" }
    Write-Host ("criada    {0}{1,-16} {2,-34} [{3}]" -f $pasta, $tarefa.Nome, $quando, $modo)
}

# ---------------------------------------------------------------- o vigia
#
# `ExecutionTimeLimit` a zero quer dizer "sem limite". As outras quatro tem uma
# hora, que e a defesa contra um pedido pendurado no servidor da escola; esta
# e suposto nao acabar, e uma hora mata-la-ia a meio da tarde de beta.
$opcoesVigia = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$accaoVigia = New-ScheduledTaskAction -Execute $interprete `
    -Argument "`"$(Join-Path (Join-Path $raiz 'scripts') 'no_ar.py')`" --porta $Porta" `
    -WorkingDirectory $raiz

$aoEntrar = New-ScheduledTaskTrigger -AtLogOn -User $utilizador
$deCincoEmCinco = New-ScheduledTaskTrigger -Daily -At '00:02'
$deCincoEmCinco.Repetition = (New-ScheduledTaskTrigger -Once -At '00:02' `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Hours 23)).Repetition
$deCincoEmCinco.EndBoundary = $Ate.ToString('yyyy-MM-ddTHH:mm:ss')

$registada = $null
foreach ($principal in $principais) {
    try {
        $registada = Register-ScheduledTask -TaskPath $pasta -TaskName $VIGIA `
            -Action $accaoVigia -Trigger @($aoEntrar, $deCincoEmCinco) `
            -Settings $opcoesVigia -Principal $principal `
            -Description 'Madalena Search - mantem o servidor e o tunel no ar. Criada por scripts\agendar.ps1.' `
            -Force
        break
    } catch { $ultimo = $_ }
}
if (-not $registada) { throw $ultimo }
Write-Host ("criada    {0}{1,-16} {2,-34} [{3}]" -f $pasta, $VIGIA,
    'ao entrar, e vigiada de 5 em 5 min', $registada.Principal.LogonType)

Write-Host ''
Write-Host "Ate $($Ate.ToString('yyyy-MM-dd HH:mm')). Registos em data\verificacao.log e data\horario.log."
Write-Host 'O projeto no ar: data\no-ar.log e o endereco em data\tunel-estado.json.'
Write-Host 'Para desligar tudo:  powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1 -Remover'
