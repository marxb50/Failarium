# Failarium

[![CI](https://github.com/marxb50/Failarium/actions/workflows/ci.yml/badge.svg)](https://github.com/marxb50/Failarium/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-0B7285)](LICENSE)

**Cultive o menor mundo capaz de reproduzir a falha de um agente de IA.**

Failarium grava um comando, seus arquivos de entrada, variáveis de ambiente
selecionadas e saídas esperadas em um único arquivo aberto
<code>.failarium</code>. Qualquer pessoa pode verificar o artefato e repetir a
mesma falha sem reconstruir manualmente o ambiente original.

[English](README.md) | [Especificação do formato](docs/FORMAT.md)

## Por que existe

Bugs de agentes de IA costumam depender de uma combinação exata de arquivos,
estado do repositório, argumentos e ambiente. Um print ou log não preserva esse
estado. O Failarium transforma a falha em um caso de teste portátil:

- um arquivo aberto e inspecionável;
- bytes determinísticos para o mesmo estado capturado;
- verificação criptográfica de integridade;
- replay em um diretório temporário limpo;
- saída humana e JSON estável para automação.

## Começo rápido

Requer Python 3.11 ou superior.

~~~powershell
python -m pip install -e .
failarium --json doctor
failarium capture --root examples/known-failure --out failure.failarium -- python task.py
failarium inspect failure.failarium
failarium verify failure.failarium
failarium replay failure.failarium
~~~

O exemplo incluído encerra intencionalmente com código 7. O replay é considerado
bem-sucedido quando reproduz essa mesma falha, incluindo stdout, stderr e código
de saída.

## Comandos

~~~text
failarium init [directory]
failarium capture --root PATH --out CASE.failarium -- COMMAND...
failarium inspect CASE.failarium
failarium verify CASE.failarium
failarium replay CASE.failarium
failarium cases list [directory]
failarium format dump CASE.failarium
failarium --json doctor
~~~

Use <code>--json</code> antes do comando para receber um envelope estável para
automação.

## Formato aberto

Um arquivo <code>.failarium</code> é um ZIP determinístico:

~~~text
case.json
expected/stdout.bin
expected/stderr.bin
files/...
~~~

O manifesto registra a versão, comando, diretório relativo de execução,
ambiente determinístico, hashes dos arquivos e resultado esperado. O contrato
v1 completo está em [docs/FORMAT.md](docs/FORMAT.md).

## Limite determinístico

A versão 1 reproduz o sistema de arquivos capturado, vetor de argumentos,
diretório de trabalho, variáveis controladas, código de saída, stdout e stderr.
Quebras de linha e o caminho temporário do workspace são normalizados.

O Failarium ainda **não** virtualiza relógio, rede, sistema operacional,
executáveis instalados ou serviços externos. Essas dependências devem ser
simuladas ou fixadas pelo caso.

## Segurança

Trate um arquivo <code>.failarium</code> como código-fonte desconhecido.
Verificar e inspecionar não executam o caso. O replay executa o comando gravado
e não é um sandbox do sistema operacional. Reproduza somente artefatos
confiáveis, preferencialmente em contêiner ou máquina virtual descartável.

## Desenvolvimento

~~~powershell
python -m unittest discover -s tests -v
python -m compileall -q src
~~~

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) e [SECURITY.md](SECURITY.md).

## Licença

MIT. Consulte [LICENSE](LICENSE).
