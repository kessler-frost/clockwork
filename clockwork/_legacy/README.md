# Legacy Design Documents

This directory contains early design concepts and philosophical foundations for Clockwork.

## Contents

- `main.py`: Core design philosophy about intelligence levels in task automation
- `engines/declaration.py`: Early HCL-based declarative syntax ideas
- `engines/execution.py`: Execution engine concepts

## Design Philosophy

The files here capture the original vision for Clockwork as a "factory of intelligent declarative tasks" with the following key concepts:

1. **Adjustable Intelligence**: Tasks should have configurable levels of intelligence rather than always requiring AI agents
2. **Deterministic Building Blocks**: Start with simple, deterministic functions and compose them into more intelligent tasks
3. **Declarative Configuration**: HCL-inspired syntax for defining tasks and their target states
4. **State Awareness**: Tasks should be aware of their environment and able to manipulate their own state

## Evolution to Current Architecture

These concepts evolved into the current three-phase architecture:
- **Intake**: Parse .cw files into IR (inspired by HCL concepts here)
- **Assembly**: Convert IR to ActionList (incorporates state awareness)
- **Forge**: Compile and execute with configurable intelligence levels

This legacy documentation serves as important context for understanding the design decisions in the current implementation.