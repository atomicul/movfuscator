# Movfuscator

> ⚠️ **Status: Active Development**
>
> This project is currently under construction. While the parsing and memory
management pipelines are functional, the core obfuscation logic is currently
being implemented.

## Overview

This is a Python-based implementation of a **Movfuscator** for x86 assembly.
The goal of this tool is to transform standard x86 assembly code into a
functionally equivalent version that uses (almost) exclusively `mov` instructions.

## Usage
As of now, the project is not packaged on the PyPI. Refer to `CONTRIBUTING.md` for details regarding running the project.

## Inspiration
This project exists thanks to Stephen Dolan, who formally proved the [turing
completness of the mov instruction](https://harrisonwl.github.io/assets/courses/malware/spring2017/papers/mov-is-turing-complete.pdf),
and Christopher Domas who wrote the [original movfuscator](https://github.com/xoreaxeaxeax/movfuscator).
