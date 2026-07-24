import secrets


def generate_canary_token(prefix: str = "BCGPT_CANARY") -> str:
    token_hex = secrets.token_hex(4)
    return f"<!-- {prefix}_{token_hex} -->"


def inject_canary_into_prompt(
    system_prompt: str, position: str = "system_prompt_end"
) -> tuple[str, str]:
    canary = generate_canary_token()

    if position == "system_prompt_end":
        modified = f"{system_prompt}\n{canary}"
    elif position == "system_prompt_start":
        modified = f"{canary}\n{system_prompt}"
    else:
        modified = f"{system_prompt}\n{canary}"

    return modified, canary


def check_canary_leakage(response: str, canary_tokens: list[str] | str) -> bool:
    if isinstance(canary_tokens, str):
        canary_tokens = [canary_tokens]

    for token in canary_tokens:
        stripped = token.strip()
        if stripped and stripped in response:
            return True

    return False
