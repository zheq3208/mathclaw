"""Vision transcribe skill tools."""


def register():
    from ...tools.math_input import inspect_math_media

    return {"inspect_math_media": inspect_math_media}
