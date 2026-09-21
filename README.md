# PersonaCUABench

The runnable benchmark on this branch lives under [`odyssey/`](odyssey/README.md).

## Local Azure configuration

The runner reads `.env` from the repository root. It is parsed by
`odyssey/run.py`; it is not a system-wide environment file and is not created
automatically. Start from the tracked, secret-free example:

```bash
cp .env.example .env
# Copy the key from your existing secure location; do not paste it into Git.
cp /secure/path/to/azure_api_key.txt ./azure_api_key.txt
chmod 600 azure_api_key.txt
```

The local `.env` points at `azure_api_key.txt`; it does not contain the secret.
Both files are ignored by Git. Exported shell variables take precedence over
same-named dotenv values.

For the complete setup, single-task commands, P1-P5 experience grading and the
independent persona-fidelity stage, see [`odyssey/README.md`](odyssey/README.md).
