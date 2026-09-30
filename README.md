# ESP Incubator

Repository for small and experimental ESP projects. Each prototype is
independent and may later be moved to its own repository.

## Structure

```text
prototypes/   independent projects
templates/    new prototype template
```

Create a project by copying `templates/prototype/` to
`prototypes/<project-name>/`.

Each project keeps its source code, build configuration, and documentation in
its own directory. Build output, logs, network captures, and local configuration
are not committed.

Store sensitive data in ignored files such as `secrets.h`, `secrets.yaml`, or
`.env`. Commit only sanitized templates such as `secrets.example.h`.

## Projects

- [2.4 GHz Signal Lab](prototypes/2g4-signal-lab/README.md) — ESP32-C3 a
  nRF24L01+ PA/LNA
