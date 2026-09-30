# Repository Working Rules

## Scope and structure

- Treat every directory under `prototypes/` as an independent experiment.
- Keep prototype-specific firmware, tests, diagrams, and notes inside that
  prototype.
- Do not add shared abstractions until at least two prototypes need them.
- Prefer small, reversible iterations. Document hardware assumptions before
  writing firmware that depends on them.
- If a prototype becomes a maintained product or grows substantial tooling,
  recommend extracting it into its own repository.

## Hardware safety

- Never guess supply voltage, pin numbering, polarity, or current capacity.
  Verify them against the exact board/module revision and record the source.
- Keep a pin table and power notes in the prototype README or `docs/wiring.md`.

## Secrets and generated files

- Never commit Wi-Fi credentials, API keys, device tokens, private certificates,
  serial numbers intended to stay private, or personal network scan captures.
- Store local secrets in ignored files such as `secrets.h`, `secrets.yaml`,
  `.env`, or `credentials.local.*`.
- Commit a sanitized `*.example.*` file whenever setup needs a secret schema.
- Use only the repository-root `.gitignore`; do not create nested `.gitignore`
  files unless a tool requires one and the reason is documented.
- Do not commit build directories, downloaded toolchains, firmware binaries,
  serial logs, packet captures, or runtime dumps by default.

## Firmware conventions

- Prefer Arduino IDE for firmware development and flashing across all
  prototypes. Use a different toolchain only when a prototype documents why it
  is needed.
- Pin toolchain/framework and library versions where practical.
- Put PlatformIO dependencies in `platformio.ini`, not in a checked-in package
  cache.
- Keep Arduino sketches self-contained and document the ESP32 board package and
  required Library Manager dependencies.
- For ESP-IDF, prefer committed `sdkconfig.defaults` and keep generated
  `sdkconfig` local.
- Commit ESP-IDF `dependencies.lock` when it contains only registry or Git
  dependencies; inspect it first and keep it local if it contains machine-local
  dependency paths.
- Separate hardware access from parsing/presentation code so logic can be tested
  without a connected board.
- Add a short verification procedure for every prototype and update its status
  after a hardware test.

## Documentation

- Use English for source code, comments, filenames, commit messages, and all
  repository documentation.
- Each prototype README should contain: purpose, status, hardware, wiring,
  power/safety notes, build/flash steps, verification, known limitations, and
  next steps.
- Prefer relative links inside the repository.
- Date experimental observations when the result may depend on hardware or
  firmware revision.
